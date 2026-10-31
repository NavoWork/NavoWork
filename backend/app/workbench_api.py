"""HTTP routes for the node-by-node workbench and its human gates."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from .core import create_item, decode, encode, fail, item_view, items, now, touch
from .domain import (
    QUOTE_REQUIRED_FIELDS,
    DomainError,
    merge_spec,
    missing_quote_fields,
    normalize_bom,
    normalize_spec,
    order_diff,
    payment_schedule_errors,
    spec_ready,
)
from .models import Case, Item, User
from .workbench import (
    APPROVAL_SCOPES,
    append_artifact,
    latest_artifact,
    latest_artifacts,
    latest_customer_profile,
    record_approval,
    release_gate,
    save_customer_profile,
    stage_state,
    workbench_view,
)

NODE_KINDS = {
    "inquiry": "qualify_inquiry",
    "requirements": "confirm_requirements",
    "costing": "prepare_quote",
    "sample": "manage_sample",
    "order": "confirm_order",
    "production": "prepare_production",
}


def _admin(user: User):
    if user.role != "admin":
        fail("FORBIDDEN", "该确认需要管理员执行", 403)


def _latest_target(db: Session, case: Case, kind: str) -> dict:
    value = latest_artifact(db, case, kind)
    if not value:
        fail("NOT_FOUND", "该项目还没有对应成果，请先生成草稿", 404)
    return value


def _evidence_role(db: Session, case: Case, evidence_id: str) -> str:
    row = db.get(Item, str(evidence_id))
    if not row or row.case_id != case.id or row.kind != "evidence":
        fail("INVALID_INPUT", "确认证据不属于本项目", 400)
    return item_view(row).get("sourceRole")


def _require_refs(db: Session, case: Case, refs: list, role: str):
    if not isinstance(refs, list) or not refs:
        fail("INVALID_INPUT", "该确认必须附原始证据", 400)
    for ref in refs:
        if not isinstance(ref, str) or _evidence_role(db, case, ref) != role:
            fail("INVALID_INPUT", "证据来源角色与确认类型不匹配", 400)


def _manual_edit(db: Session, case: Case, kind: str, body: dict) -> dict:
    if case.active_run_id or decode(case.payload).get("pendingRunId"):
        fail("RUN_IN_PROGRESS", "请等待当前任务完成后再编辑", 409)
    latest = latest_artifact(db, case, kind)
    base = int(body.get("baseVersion", 0) or 0)
    if latest:
        if base != latest["version"]:
            fail("ARTIFACT_CONFLICT", "成果版本已更新，请刷新后重试", 409)
    content = body.get("content")
    if not isinstance(content, dict):
        fail("INVALID_INPUT", "成果内容必须是对象", 400)
    try:
        if kind == "spec":
            merged = merge_spec((latest or {}).get("content"), content)
            merged["missing"] = [key for key in merged.get("missing", []) if not merged["fields"].get(key)]
        elif kind == "bom":
            merged = {"rows": normalize_bom(content.get("rows") if isinstance(content.get("rows"), list) else content)}
        elif kind == "quotation":
            cost = latest_artifacts(db, case).get("cost")
            if not cost:
                fail("BUSINESS_VALIDATION_FAILED", "需要先完成核价，才能修改报价条款", 422)
            cost_content = cost.get("content") or {}
            merged = {**((latest or {}).get("content") or {}), **content}
            # Price, total, quantity and the cost baseline are server-owned;
            # human edits may change terms but not invent money.
            merged["costVersionId"] = cost["itemId"]
            merged["unitPriceUsd"] = cost_content.get("unitPriceUsd")
            merged["totalUsd"] = cost_content.get("totalUsd")
            merged["quantity"] = cost_content.get("quantity")
            merged["selectedSupplierOfferId"] = cost_content.get("supplierOfferId")
            merged["product"] = merged.get("product") or (((latest_artifacts(db, case).get("spec") or {}).get("content") or {}).get("fields") or {}).get("product")
            merged["status"] = "draft"
        else:
            merged = {**((latest or {}).get("content") or {}), **content, "kind": kind}
    except DomainError as exc:
        fail("INVALID_INPUT", exc.message, 400)
    title = body.get("title") or (latest or {}).get("title") or kind
    artifact = append_artifact(db, case, kind, merged, title=title, status="draft")
    # Manual edits still produce a business revision so history and the stage
    # snapshot stay coherent with agent edits.
    from .workbench import commit_revision

    commit_revision(db, case, f"人工维护{title} V{artifact['version']}", node=kind)
    db.commit()
    return artifact


def _record(db: Session, case: Case, user: User, body: dict) -> dict:
    _admin(user)
    scope = str(body.get("scope") or "")
    if scope not in APPROVAL_SCOPES:
        fail("INVALID_INPUT", "未知的确认范围", 400)
    kind = {
        "customer_spec_approval": "spec",
        "commercial_quotation_approval": "quotation",
        "sample_approval": "sample",
        "order_buyer_confirmation": "order",
        "order_seller_confirmation": "order",
        "payment_verification": "payment",
        "supplier_production_confirmation": "production",
        "production_release": "production",
    }[scope]
    target = body.get("targetVersionId")
    if not target:
        target = _latest_target(db, case, kind)["itemId"]
    latest = _latest_target(db, case, kind)
    if target != latest["itemId"]:
        fail("ARTIFACT_CONFLICT", "确认目标必须是当前最新成果版本", 409)
    refs = body.get("evidenceRefs") or []
    if scope == "customer_spec_approval":
        _require_refs(db, case, refs, "customer_approval")
        if not spec_ready(latest.get("content")):
            fail("BUSINESS_VALIDATION_FAILED", "规格仍有必填项未确认", 422)
    if scope == "commercial_quotation_approval":
        missing = missing_quote_fields(latest.get("content"))
        if missing:
            fail("BUSINESS_VALIDATION_FAILED", "报价条款仍不完整", 422, {"missing": missing})
        cost = latest_artifact(db, case, "cost")
        content = latest.get("content") or {}
        if not cost:
            fail("BUSINESS_VALIDATION_FAILED", "报价没有可核验的核价版本", 422)
        cost_content = cost.get("content") or {}
        if (
            content.get("costVersionId") != cost["itemId"]
            or content.get("unitPriceUsd") != cost_content.get("unitPriceUsd")
            or content.get("selectedSupplierOfferId") != cost_content.get("supplierOfferId")
        ):
            fail("BUSINESS_VALIDATION_FAILED", "报价金额或成本基线已变化，请重新核价", 422)
    if scope == "sample_approval":
        _require_refs(db, case, refs, "customer_approval")
        if not latest.get("content", {}).get("specVersionId"):
            fail("BUSINESS_VALIDATION_FAILED", "样品尚未绑定规格版本", 422)
        spec = _latest_target(db, case, "spec")
        if latest.get("content", {}).get("specVersionId") != spec["itemId"]:
            fail("BUSINESS_VALIDATION_FAILED", "样品不是基于当前规格版本", 422)
    if scope in ("order_buyer_confirmation", "order_seller_confirmation"):
        if scope == "order_buyer_confirmation":
            _require_refs(db, case, refs, "customer_approval")
        else:
            _require_refs(db, case, refs, "internal_note")
        content = latest.get("content") or {}
        quotation = latest_artifact(db, case, "quotation")
        spec = latest_artifact(db, case, "spec")
        if (
            content.get("quotationVersionId") != (quotation or {}).get("itemId")
            or content.get("specVersionId") != (spec or {}).get("itemId")
        ):
            fail("BUSINESS_VALIDATION_FAILED", "订单引用的报价或规格版本已变化，请重新核对 PO", 422)
        conflicts = [row for row in order_diff(content, (quotation or {}).get("content") or {}, (spec or {}).get("content") or {}) if row.get("status") == "conflict"]
        if conflicts:
            fail("BUSINESS_VALIDATION_FAILED", "PO 与当前报价/规格仍有硬冲突，不能确认订单", 422, {"conflicts": conflicts})
    if scope == "payment_verification":
        _require_refs(db, case, refs, "payment_receipt")
        if not str(body.get("verificationBasis") or "").strip():
            fail("INVALID_INPUT", "请填写人工核验依据", 400)
        order = _latest_target(db, case, "order")
        errors = payment_schedule_errors(latest.get("content", {}).get("schedule"), (order.get("content", {}).get("po") or {}).get("totalUsd"))
        if errors:
            fail("BUSINESS_VALIDATION_FAILED", "付款计划不完整或金额与订单不一致", 422, {"errors": errors})
    if scope == "supplier_production_confirmation":
        _require_refs(db, case, refs, "supplier_confirmation")
    if scope == "production_release":
        gate = release_gate(db, case)
        if gate["status"] != "passed":
            fail("PRODUCTION_RELEASE_BLOCKED", "生产资料门禁未通过", 422, {"missing": gate["missing"]})
    approval = record_approval(
        db,
        case,
        user,
        scope=scope,
        target=target,
        decision="verified" if scope == "payment_verification" else "approved",
        evidence_refs=[ref for ref in refs if isinstance(ref, str)],
        note=str(body.get("note") or "")[:2000],
        details={"verificationBasis": body.get("verificationBasis"), "amountUsd": body.get("amountUsd")} if scope == "payment_verification" else {},
    )
    from .workbench import next_stage_action
    case.payload = encode({**decode(case.payload), "nextAction": next_stage_action(stage_state(db, case))})
    touch(case)
    db.commit()
    return approval


def workbench_routes(request: Request, db: Session, user: User, case: Case, tail: list[str], body: dict, form):
    method = request.method
    if not tail and method == "GET":
        return workbench_view(db, case, user)
    if tail == ["stages"] and method == "GET":
        return {"stages": stage_state(db, case), "gate": release_gate(db, case)}
    if tail == ["agent"] and method == "POST":
        from .main import create_run
        instruction = str(body.get("instruction") or body.get("goal") or "").strip()
        if not instruction:
            fail("INVALID_INPUT", "请描述本次要完成的工作", 400)
        node = body.get("node")
        if node is not None and node not in NODE_KINDS:
            fail("INVALID_INPUT", "未知的业务节点", 400)
        kind = NODE_KINDS.get(node or "", "confirm_requirements")
        return create_run(
            request,
            db,
            user,
            case,
            {
                **body,
                "action": "agent",
                "kind": kind,
                "instruction": instruction,
                "agentMode": True,
                "agentNode": node,
            },
            kind=kind,
        )
    if len(tail) >= 2 and tail[0] == "artifacts":
        kind = tail[1]
        if kind not in ("spec", "bom", "quotation", "sample", "order", "payment", "production", "ta", "qc", "comparison", "cost"):
            fail("INVALID_INPUT", "成果类型不支持", 400)
        if method == "GET":
            value = latest_artifact(db, case, kind)
            if not value:
                fail("NOT_FOUND", "该成果尚未生成", 404)
            if len(tail) >= 3:
                version = int(tail[2])
                row = db.get(Item, value["itemId"])
                found = next((i for i in items(db, "artifact", case_id=case.id) if decode(i.payload).get("kind") == kind and i.version == version), None)
                if not found:
                    fail("NOT_FOUND", "成果版本不存在", 404)
                return item_view(found)
            return value
        if method == "PUT":
            if len(tail) != 2:
                fail("NOT_FOUND", "接口不存在", 404)
            return _manual_edit(db, case, kind, body)
        if len(tail) == 3 and tail[2] == "export" and method == "POST":
            from .workbench import export_workbench_artifact
            return export_workbench_artifact(db, case, kind, str(body.get("format") or "pdf"))
    if tail == ["customer-profile"]:
        if method == "GET":
            return latest_customer_profile(db, case) or {}
        if method == "PUT":
            return save_customer_profile(db, case, body.get("profile") or body)
    if tail == ["approvals"] and method == "POST":
        return _record(db, case, user, body)
    if tail == ["release"] and method == "POST":
        return _record(db, case, user, {**body, "scope": "production_release"})
    if tail == ["gate"] and method == "GET":
        return release_gate(db, case)
    fail("NOT_FOUND", "接口不存在", 404)
