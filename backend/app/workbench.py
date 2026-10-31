"""Workbench v2 domain services: artifacts, human gates, stage state, revisions.

This module is the only place that turns agent/tool output into versioned
business artifacts. It deliberately has no model dependency.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core import case_view, create_item, decode, encode, item_view, items, now, uid
from .domain import (
    COST_CATEGORIES,
    SAMPLE_CHECKS,
    SAMPLE_TYPES,
    SPEC_FIELDS,
    SPEC_GROUPS,
    STAGES,
    empty_spec,
    merge_spec,
    missing_quote_fields,
    missing_spec_fields,
    normalize_bom,
    normalize_spec,
    order_diff,
    quote_total,
    spec_ready,
)
from .models import Case, Item, Job, Run, User

ARTIFACT_KINDS = (
    "spec",
    "bom",
    "rfq",
    "comparison",
    "cost",
    "quotation",
    "sample",
    "order",
    "payment",
    "production",
    "ta",
    "qc",
    "inquiry_assessment",
)

APPROVAL_SCOPES = (
    "customer_spec_approval",
    "commercial_quotation_approval",
    "sample_approval",
    "order_buyer_confirmation",
    "order_seller_confirmation",
    "payment_verification",
    "supplier_production_confirmation",
    "production_release",
)


def _view(row: Item) -> dict:
    value = item_view(row)
    value["version"] = row.version
    value["itemId"] = row.id
    value["status"] = value.get("status") or row.status
    return value


def latest_artifacts(db: Session, case: Case) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in items(db, "artifact", case_id=case.id):
        value = decode(row.payload)
        kind = value.get("kind")
        if kind not in ARTIFACT_KINDS:
            continue
        if kind not in latest or row.version > latest[kind]["version"]:
            latest[kind] = _view(row)
    return latest


def latest_artifact(db: Session, case: Case, kind: str) -> dict | None:
    return latest_artifacts(db, case).get(kind)


def append_artifact(
    db: Session,
    case: Case,
    kind: str,
    content: dict,
    *,
    title: str | None = None,
    run_id: str | None = None,
    job_id: str | None = None,
    status: str = "draft",
) -> dict:
    if kind not in ARTIFACT_KINDS:
        raise ValueError(f"unsupported artifact kind: {kind}")
    rows = [
        row
        for row in items(db, "artifact", case_id=case.id)
        if decode(row.payload).get("kind") == kind
    ]
    version = max((row.version for row in rows), default=0) + 1
    payload = {
        "caseId": case.id,
        "kind": kind,
        "title": title or kind,
        "version": version,
        "content": {**content, "kind": kind},
        "status": status,
        "runId": run_id,
        "jobId": job_id,
        "createdAt": now(),
    }
    row = create_item(
        db,
        "artifact",
        payload,
        case_id=case.id,
        parent_id=kind,
        version=version,
        status=status,
        item_id=f"artifact_{case.id}_{kind}_v{version}",
    )
    db.flush()
    return _view(row)


def latest_customer_profile(db: Session, case: Case) -> dict | None:
    rows = [row for row in items(db, "customer_profile", case_id=case.id)]
    if not rows:
        return None
    value = _view(max(rows, key=lambda row: row.version))
    return value


def save_customer_profile(db: Session, case: Case, patch: dict, *, run_id: str | None = None) -> dict:
    current = latest_customer_profile(db, case) or {"profile": {}}
    profile = {**(current.get("profile") or {}), **patch}
    rows = items(db, "customer_profile", case_id=case.id)
    version = max((row.version for row in rows), default=0) + 1
    payload = {
        "caseId": case.id,
        "profile": profile,
        "version": version,
        "runId": run_id,
        "createdAt": now(),
    }
    row = create_item(
        db,
        "customer_profile",
        payload,
        case_id=case.id,
        parent_id="customer",
        version=version,
        item_id=f"customer_{case.id}_v{version}",
    )
    db.flush()
    return _view(row)


def approvals(db: Session, case: Case) -> list[dict]:
    return [item_view(row) for row in items(db, "approval", case_id=case.id)]


def latest_approval(db: Session, case: Case, scope: str, target: str, decisions=("approved", "verified")) -> dict | None:
    for value in approvals(db, case):
        if value.get("scope") == scope and value.get("targetVersionId") == target and value.get("decision") in decisions:
            return value
    return None


def record_approval(
    db: Session,
    case: Case,
    user: User,
    *,
    scope: str,
    target: str,
    decision: str = "approved",
    evidence_refs: list[str] | None = None,
    note: str = "",
    details: dict | None = None,
) -> dict:
    if scope not in APPROVAL_SCOPES:
        raise ValueError("未知的确认范围")
    if decision not in ("approved", "verified", "rejected", "revoked"):
        raise ValueError("未知的确认决定")
    target_row = db.get(Item, target)
    if not target_row or target_row.case_id != case.id or target_row.kind != "artifact":
        raise ValueError("确认目标必须是本项目成果版本")
    refs = [ref for ref in (evidence_refs or []) if isinstance(ref, str)]
    for ref in refs:
        row = db.get(Item, ref)
        if not row or row.case_id != case.id or row.kind != "evidence":
            raise ValueError("确认证据不属于本项目")
    value = {
        "targetVersionId": target,
        "scope": scope,
        "decision": decision,
        "evidenceRefs": refs,
        "note": note[:2000],
        "details": details or {},
        "actorId": user.id,
        "createdAt": now(),
    }
    return item_view(
        create_item(db, "approval", value, case_id=case.id, status=decision, item_id=uid("approval"))
    )


def open_changes(db: Session, case: Case) -> list[dict]:
    return [
        item_view(row)
        for row in items(db, "change_set", case_id=case.id)
        if item_view(row).get("status") not in ("applied", "rejected", "cancelled")
    ]


def _approval_for(db: Session, case: Case, scope: str, target: dict | None) -> dict | None:
    if not target:
        return None
    return latest_approval(db, case, scope, target["itemId"])


def release_gate(db: Session, case: Case) -> dict:
    latest = latest_artifacts(db, case)
    spec = latest.get("spec")
    quotation = latest.get("quotation")
    sample = latest.get("sample")
    order = latest.get("order")
    payment = latest.get("payment")
    production = latest.get("production")
    missing: list[dict] = []

    def gap(code: str, message: str, stage: str):
        missing.append({"code": code, "message": message, "stage": stage})

    if not spec:
        gap("SPEC_MISSING", "尚未生成客户需求与规格", "requirements")
    else:
        if not spec_ready(spec.get("content")):
            gap("SPEC_INCOMPLETE", "规格仍有必填项待确认", "requirements")
        if not _approval_for(db, case, "customer_spec_approval", spec):
            gap("SPEC_NOT_APPROVED", "客户尚未书面确认当前规格", "requirements")
    if not quotation:
        gap("QUOTE_MISSING", "尚未生成客户报价", "costing")
    else:
        if missing_quote_fields(quotation.get("content")):
            gap("QUOTE_INCOMPLETE", "报价条款仍不完整", "costing")
        if not _approval_for(db, case, "commercial_quotation_approval", quotation):
            gap("QUOTE_NOT_APPROVED", "报价尚未获得内部商业批准", "costing")
    if not sample:
        gap("SAMPLE_MISSING", "尚未记录样品", "sample")
    elif sample.get("content", {}).get("specVersionId") != (spec or {}).get("itemId"):
        gap("SAMPLE_SPEC_STALE", "样品批准的规格版本已不是当前规格", "sample")
    elif not _approval_for(db, case, "sample_approval", sample):
        gap("SAMPLE_NOT_APPROVED", "最终样品尚未获得客户书面批准", "sample")
    if not order:
        gap("ORDER_MISSING", "尚未登记 PO 与 PI", "order")
    else:
        diff = order.get("content", {}).get("diff") or []
        conflicts = [row for row in diff if row.get("status") == "conflict"]
        if conflicts:
            gap("ORDER_CONFLICT", f"PO 与报价/规格有 {len(conflicts)} 项冲突", "order")
        if not _approval_for(db, case, "order_buyer_confirmation", order):
            gap("ORDER_BUYER_PENDING", "买方尚未确认订单文件", "order")
        if not _approval_for(db, case, "order_seller_confirmation", order):
            gap("ORDER_SELLER_PENDING", "卖方尚未确认订单文件", "order")
    if not payment:
        gap("PAYMENT_MISSING", "尚未登记付款计划", "order")
    elif not _approval_for(db, case, "payment_verification", payment):
        gap("PAYMENT_NOT_VERIFIED", "定金或付款保障尚未核验", "order")
    if not production:
        gap("PRODUCTION_MISSING", "尚未生成生产资料", "production")
    else:
        if production.get("content", {}).get("specVersionId") != (spec or {}).get("itemId"):
            gap("PRODUCTION_SPEC_STALE", "生产资料引用的规格版本已不是当前规格", "production")
        if production.get("content", {}).get("sampleVersionId") and production.get("content", {}).get("sampleVersionId") != (sample or {}).get("itemId"):
            gap("PRODUCTION_SAMPLE_STALE", "生产资料引用的样品版本已不是当前样品", "production")
        if production.get("content", {}).get("orderVersionId") != (order or {}).get("itemId"):
            gap("PRODUCTION_ORDER_STALE", "生产资料引用的订单版本已不是当前订单", "production")
        if not _approval_for(db, case, "supplier_production_confirmation", production):
            gap("SUPPLIER_NOT_CONFIRMED", "供应商生产条件尚未确认", "production")
    if open_changes(db, case):
        gap("CHANGE_OPEN", "仍有未关闭的业务变更", "requirements")
    return {"status": "passed" if not missing else "blocked", "missing": missing}


def _status(base: str, missing: list, confirmed: bool) -> str:
    if confirmed:
        return "confirmed"
    if base == "empty":
        return "empty"
    if missing:
        return "draft"
    return "ready"


def _spec_summary(content: dict | None) -> str:
    if not content:
        return ""
    fields = content.get("fields") or {}
    parts = [str(fields.get(key) or "").strip() for key in ("product", "quantity", "dimensions", "fabric")]
    return " · ".join(part for part in parts if part)


def _quote_summary(content: dict | None) -> str:
    if not content:
        return ""
    unit = content.get("unitPriceUsd")
    currency = content.get("currency") or "USD"
    quantity = content.get("quantity")
    incoterm = content.get("incoterm")
    place = content.get("namedPlace")
    terms = " ".join(part for part in (incoterm, place) if part)
    if unit:
        return f"{currency} {unit} / 件 × {quantity or '—'} 件 · {terms}"
    return ""


def stage_state(db: Session, case: Case) -> list[dict]:
    latest = latest_artifacts(db, case)
    profile = latest_customer_profile(db, case)
    assessment = latest.get("inquiry_assessment")
    spec = latest.get("spec")
    bom = latest.get("bom")
    comparison = latest.get("comparison")
    cost = latest.get("cost")
    quotation = latest.get("quotation")
    sample = latest.get("sample")
    order = latest.get("order")
    payment = latest.get("payment")
    production = latest.get("production")
    ta = latest.get("ta")
    qc = latest.get("qc")
    gate = release_gate(db, case)

    stages = []
    for meta in STAGES:
        key = meta["key"]
        status, summary, missing, action = "empty", "", [], ""
        artifacts: list[str] = []
        if key == "inquiry":
            if profile:
                artifacts.append(profile["itemId"])
            if assessment:
                artifacts.append(assessment["itemId"])
            context = decode(case.payload).get("customerContext") or {}
            profile_data = {**context, **((profile or {}).get("profile") or {})}
            if not profile_data.get("company"):
                profile_data["company"] = decode(case.payload).get("customer")
            assessment_data = (assessment or {}).get("content") or {}
            missing = [
                label
                for label, value in (
                    ("公司名称", profile_data.get("company")),
                    ("来源渠道", profile_data.get("channel")),
                    ("联系方式", profile_data.get("email")),
                )
                if not value
            ]
            summary = " · ".join(part for part in (profile_data.get("company"), profile_data.get("country")) if part)
            status = _status("draft" if profile or assessment or context else "empty", missing, False)
            action = "核对客户背景，整理询盘关键信息与待确认项"
        elif key == "requirements":
            if spec:
                artifacts.append(spec["itemId"])
            if bom:
                artifacts.append(bom["itemId"])
            missing = (spec or {}).get("content", {}).get("missing") or ([] if spec else ["spec"])
            confirmed = bool(spec and _approval_for(db, case, "customer_spec_approval", spec))
            status = _status("draft" if spec else "empty", missing, confirmed)
            summary = _spec_summary((spec or {}).get("content"))
            action = "补齐箱包 Tech Pack 与 BOM，并取得客户书面确认"
        elif key == "costing":
            for item in (comparison, cost, quotation):
                if item:
                    artifacts.append(item["itemId"])
            missing = missing_quote_fields((quotation or {}).get("content")) if quotation else ["quotation"]
            confirmed = bool(quotation and _approval_for(db, case, "commercial_quotation_approval", quotation))
            status = _status("draft" if (comparison or cost or quotation) else "empty", missing, confirmed)
            summary = _quote_summary((quotation or {}).get("content"))
            action = "登记供应商报价，完成核价并形成可审核的客户报价"
        elif key == "sample":
            if sample:
                artifacts.append(sample["itemId"])
            content = (sample or {}).get("content") or {}
            missing = [] if sample else ["sample"]
            for label, value in (("样品种类", content.get("type")), ("样品编号", content.get("sampleRef")), ("规格版本", content.get("specVersionId"))):
                if not value:
                    missing.append(label)
            confirmed = bool(sample and _approval_for(db, case, "sample_approval", sample))
            status = _status("draft" if sample else "empty", missing, confirmed)
            summary = " · ".join(part for part in (content.get("sampleRef"), content.get("type")) if part)
            action = "记录样品轮次、检查与客户书面批准"
        elif key == "order":
            for item in (order, payment):
                if item:
                    artifacts.append(item["itemId"])
            content = (order or {}).get("content") or {}
            missing = [] if order else ["order"]
            for label, value in (("PO 编号", (content.get("po") or {}).get("number")), ("PI 编号", (content.get("pi") or {}).get("number"))):
                if not value:
                    missing.append(label)
            conflicts = [row for row in content.get("diff") or [] if row.get("status") == "conflict"]
            if conflicts:
                missing.append(f"{len(conflicts)} 项 PO 差异")
            buyer = bool(order and _approval_for(db, case, "order_buyer_confirmation", order))
            seller = bool(order and _approval_for(db, case, "order_seller_confirmation", order))
            paid = bool(payment and _approval_for(db, case, "payment_verification", payment))
            if order and not buyer:
                missing.append("买方确认")
            if order and not seller:
                missing.append("卖方确认")
            if payment and not paid:
                missing.append("付款核验")
            confirmed = buyer and seller and paid
            status = _status("draft" if (order or payment) else "empty", missing, confirmed)
            summary = " · ".join(part for part in ((content.get("po") or {}).get("number"), (content.get("pi") or {}).get("number")) if part)
            action = "核对 PO 与报价/规格差异，形成 PI 并登记双方确认与付款保障"
        elif key == "production":
            for item in (production, ta, qc):
                if item:
                    artifacts.append(item["itemId"])
            missing = [gap["message"] for gap in gate["missing"] if gap["stage"] == "production"]
            confirmed = bool(production and _approval_for(db, case, "production_release", production))
            status = _status("draft" if production else "empty", missing, confirmed)
            summary = "生产资料、T&A 与验货标准" if production else ""
            action = "生成生产资料与验货标准，逐项通过放行检查"
        elif key in ("shipment", "payment"):
            status = "locked"
            action = "附件未展开的后续阶段，当前不生成虚假单据或到账"
            summary = "未接入"
        else:
            status = "locked"
        stages.append(
            {
                "key": key,
                "title": meta["title"],
                "short": meta["short"],
                "status": status,
                "summary": summary,
                "missing": missing,
                "nextAction": action,
                "artifactVersionIds": artifacts,
                "available": key not in ("shipment", "payment"),
            }
        )
    # The gate belongs to production; surface it once for the header and stage.
    for stage in stages:
        if stage["key"] == "production":
            stage["gate"] = gate
    return stages


def _customer_context(case: Case, profile: dict | None) -> dict:
    payload = decode(case.payload)
    current = payload.get("customerContext") or {}
    data = (profile or {}).get("profile") or {}
    return {
        **current,
        "company": data.get("company") or current.get("company") or payload.get("customer"),
        "country": data.get("country") or current.get("country"),
        "channel": data.get("channel") or current.get("channel") or "unknown",
        "email": data.get("email") or current.get("email"),
        "website": data.get("website") or current.get("website"),
        "linkedin": data.get("linkedin") or current.get("linkedin"),
        "business": data.get("business") or current.get("business"),
        "sourceRef": data.get("sourceRef") or current.get("sourceRef"),
        "summary": data.get("summary") or current.get("summary"),
        "checks": data.get("checks") or current.get("checks") or [],
    }


def next_stage_action(stages: list[dict]) -> str:
    priority = {"blocked": 0, "draft": 1, "empty": 2, "ready": 3, "confirmed": 4, "locked": 5}
    core = [stage for stage in stages if stage["key"] in ("inquiry", "requirements", "costing", "sample", "order", "production")]
    if core and all(stage["status"] == "confirmed" for stage in core if stage["key"] != "inquiry"):
        return "完成当前业务"
    ordered = sorted(core, key=lambda stage: (priority.get(stage["status"], 9), core.index(stage)))
    for stage in ordered:
        if stage["status"] not in ("confirmed", "locked"):
            return stage["nextAction"]
    return "完成当前业务"


def workbench_view(db: Session, case: Case, user: User) -> dict:
    latest = latest_artifacts(db, case)
    profile = latest_customer_profile(db, case)
    stages = stage_state(db, case)
    payload = decode(case.payload)
    role_order = {
        "customer_request": 0,
        "customer_change": 1,
        "supplier_quote": 2,
        "customer_po": 3,
        "sample_inspection": 4,
        "customer_approval": 5,
        "supplier_confirmation": 6,
        "payment_receipt": 7,
        "internal_note": 8,
        "shipping_document": 9,
    }
    evidence = [
        {
            "id": row.id,
            "title": value.get("title"),
            "sourceRole": value.get("sourceRole"),
            "parseStatus": value.get("parseStatus"),
            "blobId": value.get("blobId"),
            "text": (value.get("text") or "")[:4000],
            "createdAt": value.get("createdAt"),
        }
        for row in sorted(
            items(db, "evidence", case_id=case.id),
            key=lambda row: (role_order.get(item_view(row).get("sourceRole"), 20), row.created_at, row.id),
        )
        for value in [item_view(row)]
    ]
    knowledge = []
    for row in items(db, "resource"):
        value = item_view(row)
        if value.get("kind") != "knowledge" or value.get("status") != "published":
            continue
        knowledge.append({"id": row.id, "sourceId": value.get("sourceId"), "title": value.get("title"), "version": row.version, "folder": value.get("folder")})
    from .workspace_api import asset_rows

    assets_by_id = {}
    for row in asset_rows(db, user):
        value = item_view(row)
        if value.get("space") == "personal":
            continue
        current = assets_by_id.get(value.get("id"))
        if current is None or row.version > current["version"]:
            assets_by_id[value.get("id")] = {
                "id": value.get("id"),
                "title": value.get("title"),
                "name": value.get("name"),
                "version": row.version,
                "mediaType": value.get("mediaType"),
                "size": value.get("size"),
                "folder": value.get("folder"),
            }
    assets = list(assets_by_id.values())
    offers = [item_view(row) for row in items(db, "supplier_offer", case_id=case.id)]
    return {
        "case": case_view(case),
        "customerContext": _customer_context(case, profile),
        "customerProfile": profile,
        "stages": stages,
        "artifacts": {kind: value for kind, value in latest.items()},
        "evidence": evidence,
        "knowledge": knowledge,
        "assets": assets,
        "supplierOffers": offers,
        "approvals": approvals(db, case),
        "gate": release_gate(db, case),
        "schema": {
            "specGroups": SPEC_GROUPS,
            "specFields": SPEC_FIELDS,
            "costCategories": COST_CATEGORIES,
            "sampleChecks": SAMPLE_CHECKS,
            "sampleTypes": SAMPLE_TYPES,
        },
        "nextAction": next_stage_action(stages),
    }


def _quantity(spec_fields: dict) -> int | None:
    raw = spec_fields.get("quantity")
    if raw in (None, ""):
        return None
    try:
        value = int(Decimal(str(raw)))
    except (InvalidOperation, ValueError):
        return None
    return value if value > 0 else None


def revision_from_artifacts(case: Case, latest: dict[str, dict], *, number: int, run_id: str, job_id: str | None, summary: str, node: str | None) -> dict:
    spec = (latest.get("spec") or {}).get("content") or {}
    fields = spec.get("fields") or {}
    quotation = (latest.get("quotation") or {}).get("content") or {}
    assessment = (latest.get("inquiry_assessment") or {}).get("content") or {}
    quantity = _quantity(fields)
    unit = quotation.get("unitPriceUsd")
    quote = None
    if unit and quantity:
        try:
            unit_decimal = Decimal(str(unit))
        except InvalidOperation:
            unit_decimal = None
        if unit_decimal is not None:
            quote = {
                "sku": fields.get("product") or quotation.get("product") or "CUSTOM",
                "quantity": int(quotation.get("quantity") or quantity),
                "currency": quotation.get("currency") or "USD",
                "unitPriceMinor": int(unit_decimal * 100),
                "goodsSubtotalMinor": int(unit_decimal * int(quotation.get("quantity") or quantity) * 100),
                "freightMinor": None,
                "taxMinor": None,
                "totalMinor": None,
                "quoteStatus": "draft",
                "sourceVersionIds": [
                    item["itemId"]
                    for key in ("cost", "comparison")
                    for item in [latest.get(key)]
                    if item
                ],
                "timing": {
                    "dispatchDays": None,
                    "productionDays": quotation.get("productionDays"),
                    "startsAfter": "以客户确认样品及付款条件为准",
                    "transitDays": None,
                    "arrivalGuaranteed": False,
                },
            }
    risks = []
    for message in assessment.get("risks") or []:
        if isinstance(message, str):
            risks.append({"id": uid("risk"), "severity": "warning", "category": "inquiry", "message": message, "suggestedAction": "向客户或供应商澄清", "status": "open", "evidenceRefs": []})
    for field_key in spec.get("missing") or []:
        risks.append({"id": uid("risk"), "severity": "info", "category": "missing_field", "message": f"{field_key} 尚未确认", "suggestedAction": "补充来源或向客户澄清", "status": "open", "evidenceRefs": []})
    generated = sorted(
        {
            "spec": "requirements",
            "bom": "requirements",
            "comparison": "costing",
            "cost": "costing",
            "quotation": "costing",
            "sample": "sample",
            "order": "order",
            "payment": "order",
            "production": "production",
            "ta": "production",
            "qc": "production",
            "inquiry_assessment": "inquiry",
        }[kind]
        for kind in latest
    )
    return {
        "inquiryId": case.id,
        "number": number,
        "runId": run_id,
        "jobId": job_id,
        "generatedNode": node,
        "generatedNodes": generated,
        "requirements": {
            "requestedProduct": fields.get("product"),
            "specification": " / ".join(part for part in (fields.get("fabric"), fields.get("dimensions")) if part) or None,
            "quantity": quantity,
            "destination": fields.get("destination"),
            "requestedArrival": fields.get("delivery"),
            "customization": fields.get("logo"),
            "certificationRequests": [fields["tests"]] if fields.get("tests") else [],
            "missingFields": spec.get("missing") or [],
            "evidenceRefs": [ref.get("evidenceId") for ref in spec.get("sourceRefs") or [] if ref.get("evidenceId")],
        },
        "proposal": {
            "proposalId": uid("proposal"),
            "version": number,
            "requestedSku": fields.get("product"),
            "selectedSku": quotation.get("sku") or fields.get("product"),
            "differences": [],
            "status": "proposed",
        },
        "quote": quote,
        "replies": {"en-US": "", "es-MX": ""},
        "risks": risks,
        "checks": [
            {"label": "规格完整性", "status": "passed" if spec_ready(spec) else "warning"},
            {"label": "报价条款", "status": "passed" if quotation and not missing_quote_fields(quotation) else "warning"},
        ],
        "sourceRefs": [],
        "assetRefs": [],
        "artifactVersionIds": {kind: value["itemId"] for kind, value in latest.items()},
        "ruleSetVersion": "workbench-v2",
        "changeSummary": [summary],
        "createdAt": now(),
    }


def commit_revision(db: Session, case: Case, summary: str, *, node: str | None = None, run_id: str = "", job_id: str | None = None) -> dict | None:
    """Create a new business revision from the latest artifact versions."""
    latest = latest_artifacts(db, case)
    if not latest:
        return None
    number = case.current_revision + 1
    revision = revision_from_artifacts(
        case,
        latest,
        number=number,
        run_id=run_id,
        job_id=job_id,
        summary=summary,
        node=node,
    )
    create_item(db, "revision", revision, case_id=case.id, parent_id=case.id, version=number)
    case.current_revision = number
    case.status = "active"
    case.active_run_id = None
    case.metadata_version += 1
    case.updated_at = now()
    case.payload = encode(
        {
            **decode(case.payload),
            "nextAction": next(
                (stage["nextAction"] for stage in stage_state(db, case) if stage["status"] not in ("confirmed", "locked")),
                "完成当前业务",
            ),
        }
    )
    return revision


def finalize_agent_run(
    db: Session,
    case: Case,
    run: Run,
    job: Job | None,
    summary: str,
    *,
    node: str | None = None,
    artifacts_changed: bool = False,
) -> dict | None:
    revision = None
    if artifacts_changed:
        revision = commit_revision(db, case, summary, node=node, run_id=run.id, job_id=job.id if job else None)
        if revision:
            run.output_revision = revision["number"]
    case.status = "active"
    case.active_run_id = None
    case.metadata_version += 1
    case.updated_at = now()
    run.status = "succeeded"
    run.phase = "committing"
    run.last_seq += 1
    data = decode(run.payload)
    data["completedPhases"] = list(dict.fromkeys([*data.get("completedPhases", []), "committing"]))
    data["agentSummary"] = summary
    if job:
        data["summary"] = summary
    run.payload = encode(data)
    if job:
        job.status = "needs_review" if artifacts_changed else "completed"
    create_item(
        db,
        "run_event",
        {"runId": run.id, "inquiryId": case.id, "seq": run.last_seq, "type": "run.succeeded", "payload": {"phase": "committing", "summary": summary}, "createdAt": now()},
        case_id=case.id,
        parent_id=run.id,
    )
    create_item(
        db,
        "message",
        {"inquiryId": case.id, "role": "assistant", "text": summary, "runId": run.id, "createdAt": now()},
        case_id=case.id,
    )
    return revision

def export_workbench_artifact(db: Session, case: Case, kind: str, fmt: str) -> dict:
    from .exports import export_artifact

    latest = latest_artifact(db, case, kind)
    if not latest:
        raise ValueError("成果尚未生成")
    row = db.get(Item, latest["itemId"])
    if not row:
        raise ValueError("成果版本不存在")
    return export_artifact(db, case, row, fmt)
