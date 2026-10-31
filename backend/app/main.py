from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from starlette.datastructures import UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .agent import KEYWORDS, NODE_FIELDS, extract_without_model, price_quote
from .core import WORKSPACE_ID, WORKSPACE_NAME, bootstrap, case_view, create_item, current_user, decode, encode, fail, idem_lookup, idem_store, item_view, items, login_user, require_case, require_workspace, session_view, store_blob, touch, uid
from .db import Base, engine, get_db
from .models import Blob, Case, CaseAccess, Idempotency, Item, Job, LoginSession, Run, User, WorkItem, now
from .worker import run_view


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        bootstrap(db)
        if not items(db, "capability"):
            for key, name in (("evidence", "证据与事实"), ("costing", "确定性核价"), ("agent", "Agent 工作流"), ("exports", "成果导出")):
                create_item(db, "capability", {"id": key, "name": name, "description": name, "enabled": True, "required": key != "agent", "version": "1.0", "category": "core"}, item_id=f"cap_{key}")
            db.commit()
    yield


app = FastAPI(title="NavoWork API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    value = exc.detail if isinstance(exc.detail, dict) else {"code": "HTTP_ERROR", "message": str(exc.detail)}
    return JSONResponse({"error": value, "requestId": getattr(request.state, "request_id", uid("request"))}, status_code=exc.status_code)


@app.middleware("http")
async def secure_request(request: Request, call_next):
    request.state.request_id = uid("request")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        allowed = set(os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173").split(","))
        origin = request.headers.get("origin")
        if origin and origin not in allowed:
            return JSONResponse({"error": {"code": "BAD_ORIGIN", "message": "请求来源不受信任"}, "requestId": request.state.request_id}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"error": {"code": "BAD_ORIGIN", "message": "跨站写请求已拒绝"}, "requestId": request.state.request_id}, status_code=403)
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(select(User.id).limit(1))
    return {"status": "ok", "database": "sqlite"}


@app.post("/api/v1/auth/session")
async def login(request: Request, response: Response, db: Session = Depends(get_db)):
    data = await request.json()
    result, token = login_user(db, str(data.get("email", "")), str(data.get("password", "")))
    response.set_cookie("nv_session", token, httponly=True, samesite="lax", secure=os.getenv("APP_ENV", "demo") != "demo", max_age=7 * 86400)
    return result


@app.delete("/api/v1/auth/session", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("nv_session")
    if token:
        db.query(LoginSession).filter(LoginSession.token_hash == hashlib.sha256(token.encode()).hexdigest()).delete()
        db.commit()
    response.delete_cookie("nv_session")


@app.get("/api/v1/me")
def me(request: Request, db: Session = Depends(get_db)):
    return session_view(current_user(request, db))


def assert_admin(user: User):
    if user.role != "admin":
        fail("FORBIDDEN", "仅管理员可以执行此操作", 403)


def body_value(payload: dict, name: str, max_len: int = 50000) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip() or len(value) > max_len:
        fail("INVALID_INPUT", f"请填写有效的 {name}", 400)
    return value.strip()


def scoped_item(db: Session, user: User, case: Case, item_id: str, kind: str) -> Item:
    item = db.get(Item, item_id)
    if not item or item.kind != kind or item.case_id != case.id:
        fail("NOT_FOUND", "指定对象不存在", 404)
    return item


def latest_draft(db: Session, case_id: str, revision: int, locale: str, version: int | None = None):
    group = items(db, "draft", case_id=case_id, parent_id=f"{case_id}:{revision}:{locale}")
    if version is not None:
        group = [i for i in group if i.version == version]
    if not group:
        fail("NOT_FOUND", "草稿版本不存在", 404)
    return max(group, key=lambda i: i.version)


def revisions(db: Session, case_id: str):
    return sorted(items(db, "revision", case_id=case_id), key=lambda i: i.version)


def latest_resources(db: Session, kind: str):
    rows = items(db, "resource")
    if kind == "knowledge":
        rows = [i for i in rows if decode(i.payload).get("kind") == "knowledge"]
    elif kind == "products":
        rows = [i for i in rows if decode(i.payload).get("kind") in ("product", "price")]
    by_id = {}
    for item in rows:
        resource_id = decode(item.payload).get("sourceId")
        if resource_id not in by_id or item.version > by_id[resource_id].version:
            by_id[resource_id] = item
    return [item_view(v) for v in by_id.values()]


def case_routes(request: Request, db: Session, user: User, parts: list[str], body: dict, form):
    method = request.method
    if not parts:
        if method == "GET":
            values = [case_view(c) for c in db.scalars(select(Case).join(CaseAccess, CaseAccess.case_id == Case.id).where(CaseAccess.user_id == user.id, Case.workspace_id == WORKSPACE_ID))]
            status = request.query_params.get("status")
            q = request.query_params.get("q", "").lower()
            values = [v for v in values if (not status or status == "all" or v["businessStatus"] == status) and q in f"{v['title']} {v['customer']} {v['id']}".lower()]
            values.sort(key=lambda x: (x["updatedAt"], x["id"]), reverse=True)
            offset = max(0, int(request.query_params.get("cursor") or 0))
            limit = min(100, max(1, int(request.query_params.get("limit", 20))))
            return {"items": values[offset:offset+limit], "nextCursor": str(offset+limit) if offset+limit < len(values) else None, "matchedCount": len(values)}
        if method == "POST":
            result, marker = idem_lookup(db, request, body)
            if result:
                return result
            for key, size in (("title", 80), ("customer", 120), ("originalText", 20000)):
                body_value(body, key, size)
            case = Case(id=uid("inq"), workspace_id=WORKSPACE_ID, owner_id=user.id, payload=encode({"title": body["title"].strip(), "customer": body["customer"].strip(), "originalText": body["originalText"].strip(), "requestedLocales": body.get("requestedLocales") or ["en-US", "es-MX"], "destination": body.get("destination"), "nextAction": "读懂客户原文，确认需求与缺项"}), status="todo")
            db.add(case)
            db.flush()
            db.add(CaseAccess(case_id=case.id, user_id=user.id))
            create_item(db, "message", {"id": uid("msg"), "inquiryId": case.id, "role": "user", "text": body["originalText"].strip(), "createdAt": now()}, case_id=case.id)
            result = case_view(case)
            idem_store(db, marker, result)
            db.commit()
            return result
    if parts == ["summary"]:
        values = [c.status for c in db.scalars(select(Case).join(CaseAccess, CaseAccess.case_id == Case.id).where(CaseAccess.user_id == user.id))]
        return {key: values.count(key) for key in ("todo", "active", "waiting", "done")}
    case = require_case(db, user, parts[0])
    tail = parts[1:]
    if tail and tail[0] == "canvas":
        from .workspace_api import canvas_routes
        return canvas_routes(request, db, user, case, tail, body, form)
    if not tail:
        if method == "GET":
            return case_view(case)
        if method == "PATCH":
            if body.get("metadataVersion") != case.metadata_version:
                fail("METADATA_CONFLICT", "询盘信息已更新", 409, {"current": case_view(case)})
            payload = decode(case.payload)
            for key in ("title", "customer", "destination"):
                if key in body:
                    payload[key] = body[key]
            if "originalText" in body:
                if case.current_revision:
                    fail("INVALID_INPUT", "首次处理后原文不能覆盖，请追加证据")
                payload["originalText"] = body["originalText"]
            case.payload = encode(payload)
            touch(case)
            db.commit()
            return case_view(case)
    if tail == ["status-transitions"] and method == "POST":
        if case.active_run_id:
            fail("RUN_IN_PROGRESS", "请等待当前运行完成", 409)
        if body.get("metadataVersion") != case.metadata_version or body.get("from") != case.status:
            fail("METADATA_CONFLICT", "询盘状态已更新", 409, {"current": case_view(case)})
        allowed = {"todo": ("active", "done"), "active": ("waiting", "done"), "waiting": ("active", "done"), "done": ("active",)}
        to = body.get("to")
        if to not in allowed.get(case.status, ()):
            fail("INVALID_STATUS_TRANSITION", "不允许此状态转换", 409)
        payload = decode(case.payload)
        if to == "waiting":
            waiting = body.get("waiting") or {}
            if not all(waiting.get(x) for x in ("waitingFor", "waitingReason", "nextAction")):
                fail("INVALID_INPUT", "请填写等待对象、原因与下一步")
            payload["waiting"] = waiting
            payload["nextAction"] = waiting["nextAction"]
        if to == "done":
            payload["closeReason"] = body_value(body, "closeReason", 300)
            payload["nextAction"] = "已结束，可查看历史"
        if to == "active":
            payload.pop("waiting", None)
            payload.pop("closeReason", None)
            payload["nextAction"] = "继续处理当前工作"
        case.payload = encode(payload)
        case.status = to
        touch(case)
        db.commit()
        return case_view(case)
    if tail and tail[0] == "messages":
        if method == "GET":
            return {"items": [item_view(i) for i in items(db, "message", case_id=case.id)]}
        if method == "POST":
            value = body_value(body, "text", 20000)
            message = {"id": uid("msg"), "inquiryId": case.id, "role": "user", "text": value, "createdAt": now()}
            create_item(db, "message", message, case_id=case.id)
            touch(case)
            db.commit()
            return message
    if tail and tail[0] == "revisions":
        revs = revisions(db, case.id)
        if len(tail) == 1:
            return {"items": [item_view(i) for i in revs]}
        number = int(tail[1])
        found = next((i for i in revs if i.version == number), None)
        if not found:
            fail("NOT_FOUND", "业务版本不存在", 404)
        if len(tail) == 2:
            return item_view(found)
        if tail[2] == "reply-drafts":
            locale = tail[3] if len(tail) > 3 else request.query_params.get("locale")
            if method == "GET":
                if locale:
                    version = request.query_params.get("draftVersion")
                    return item_view(latest_draft(db, case.id, number, locale, int(version) if version else None))
                return {"items": [item_view(latest_draft(db, case.id, number, loc)) for loc in ("en-US", "es-MX")]}
            if method == "PUT":
                if number != case.current_revision or case.status in ("waiting", "done"):
                    fail("REVISION_CONFLICT", "历史或暂停状态不可编辑", 409)
                if locale not in ("en-US", "es-MX"):
                    fail("INVALID_INPUT", "语言不受支持")
                current = latest_draft(db, case.id, number, locale)
                value = item_view(current)
                if body.get("baseDraftVersion") != value["draftVersion"]:
                    fail("DRAFT_CONFLICT", "草稿已被其他人修改", 409, {"currentDraft": value, "latestDraft": value})
                text_value = body_value(body, "text", 50000)
                if text_value == value["text"]:
                    return value
                new_value = {**value, "text": text_value, "draftVersion": value["draftVersion"] + 1, "reviewStatus": "needs_review", "updatedAt": now()}
                create_item(db, "draft", new_value, case_id=case.id, parent_id=f"{case.id}:{number}:{locale}", version=new_value["draftVersion"])
                db.commit()
                return new_value
    if tail and tail[0] == "runs":
        if len(tail) == 1 and method == "POST":
            return create_run(request, db, user, case, body)
    if tail and tail[0] == "reviews" and method == "POST":
        number = int(body.get("revision", 0))
        found = next((i for i in revisions(db, case.id) if i.version == number), None)
        if not found:
            fail("NOT_FOUND", "业务版本不存在", 404)
        versions = body.get("draftVersions") or {}
        errors = []
        revision_value = item_view(found)
        quote = revision_value.get("quote")
        for locale, version in versions.items():
            draft = item_view(latest_draft(db, case.id, number, locale, int(version)))
            text_value = draft["text"].strip()
            if not text_value:
                errors.append({"message": f"{locale} 回复为空"})
            if re.search(r"\b(?:guaranteed?|confirmed)\s+(?:arrival|delivery)\b|保证(?:到货|交期)|确保\d+天", text_value, re.I):
                errors.append({"message": f"{locale} 包含未经核验的交期保证"})
            prices = re.findall(r"(?:USD|US\$|\$)\s*(\d+(?:\.\d{1,2})?)", text_value, re.I)
            if prices and (not quote or any(round(float(price) * 100) != quote["unitPriceMinor"] for price in prices)):
                errors.append({"message": f"{locale} 金额与固定版本单价不一致"})
            if not errors and number == case.current_revision and draft["reviewStatus"] != "reviewed":
                row = latest_draft(db, case.id, number, locale, int(version))
                draft["reviewStatus"] = "reviewed"
                row.payload = encode(draft)
        db.commit()
        return {"status": "blocked" if errors else "passed", "errors": errors, "warnings": [{"message": "正式报价仍需单独商业批准"}], "revision": number, "draftVersions": versions}
    if tail and tail[0] == "material-bundles":
        if method == "GET":
            return {"items": [item_view(i) for i in items(db, "bundle", case_id=case.id)]}
        revision = next((item_view(i) for i in revisions(db, case.id) if i.version == body.get("revision")), None)
        if not revision:
            fail("NOT_FOUND", "业务版本不存在", 404)
        asset_refs = body.get("assetVersionIds", revision.get("assetRefs", []))
        source_refs = body.get("sourceVersionIds", [r["sourceVersionId"] for r in revision.get("sourceRefs", [])])
        if not isinstance(asset_refs, list) or not isinstance(source_refs, list) or any(ref not in revision.get("assetRefs", []) for ref in asset_refs) or any(ref not in [s["sourceVersionId"] for s in revision.get("sourceRefs", [])] for ref in source_refs):
            fail("REVISION_CONFLICT", "材料清单只能使用该业务版本已引用的资料", 409)
        for locale, version in body.get("draftVersions", {}).items():
            latest_draft(db, case.id, revision["number"], locale, version)
        value = {"id": uid("bundle"), "inquiryId": case.id, "revision": revision["number"], "draftVersions": body.get("draftVersions", {}), "assetVersionIds": asset_refs, "sourceVersionIds": source_refs, "status": "draft", "createdAt": now()}
        create_item(db, "bundle", value, case_id=case.id, item_id=value["id"])
        db.commit()
        return value
    if tail and tail[0] == "exports":
        if len(tail) == 1 and method == "POST":
            from .exports import create_export
            return create_export(db, case, body)
    from .sop_api import sop_case_routes
    return sop_case_routes(request, db, user, case, tail, body, form)


def create_run(request: Request, db: Session, user: User, case: Case, body: dict, kind: str | None = None):
    db.execute(text("BEGIN IMMEDIATE"))
    db.refresh(case)
    previous, marker = idem_lookup(db, request, body)
    if previous:
        return previous
    if case.status in ("waiting", "done"):
        fail("INVALID_STATUS_TRANSITION", "请先恢复处理当前工作", 409)
    if case.active_run_id:
        fail("RUN_IN_PROGRESS", "当前工作正在执行", 409)
    from .run_context import prepare_context, resume_run, route_intent, require_capability
    require_capability(db, "agent")
    if body.get("replyToRunId"):
        return resume_run(request, db, user, case, body, marker)
    if decode(case.payload).get("pendingRunId"):
        fail("RUN_NEEDS_INPUT", "请先回答当前任务的问题或取消该任务", 409)
    base_revision = int(body.get("baseRevision", case.current_revision))
    if base_revision != case.current_revision:
        fail("REVISION_CONFLICT", "业务版本已有更新", 409, {"currentRevision": case.current_revision})
    action = str(body.get("action") or kind or "analyze")
    interactive = kind is None
    kind = kind or route_intent(action, str(body.get("instruction", "")))
    allowed = {"qualify_inquiry", "confirm_requirements", "prepare_quote", "manage_sample", "confirm_order", "prepare_production", "manage_shipment", "reconcile_payment", "handle_aftersales", "apply_change", "follow_up"}
    if kind not in allowed:
        fail("INVALID_INPUT", "未知任务类型")
    if kind in ("manage_shipment", "reconcile_payment", "handle_aftersales"):
        fail("CAPABILITY_NOT_AVAILABLE", "该阶段尚未接入可信的物流、财务或售后资料", 422)
    instruction = str(body.get("instruction") or body.get("goal") or "分析当前资料")[:20000]
    cost_inputs = body.get("costInputs") or {}
    selected_offer_id = body.get("selectedSupplierOfferId")
    if kind == "prepare_quote":
        require_capability(db, "costing")
    if kind == "prepare_quote" and not selected_offer_id and not interactive:
        fail("SUPPLIER_EVIDENCE_REQUIRED", "报价任务须选择已绑定原件的供应商报价", 422)
    if kind == "prepare_quote" and selected_offer_id:
        offer_row = db.get(Item, str(selected_offer_id))
        if not offer_row or offer_row.case_id != case.id or offer_row.kind != "supplier_offer":
            fail("NOT_FOUND", "供应商报价不存在", 404)
        offer = item_view(offer_row)
        cost_inputs = {**cost_inputs, "base": offer["baseCny"], "packaging": offer["packagingCny"], "local": offer["localCny"]}
        calculated = price_quote(cost_inputs)
        if calculated and calculated["quantity"] < offer["moq"]:
            fail("INVALID_INPUT", "询价数量低于供应商起订量")
        if not calculated and not interactive:
            fail("INVALID_INPUT", "请补齐有效的汇率、毛利率和数量")
    if not isinstance(body.get("inputRefs") or [], list):
        fail("INVALID_INPUT", "输入来源必须是列表")
    for ref in body.get("inputRefs") or []:
        source = db.get(Item, str(ref))
        if not source or source.case_id != case.id or source.kind != "evidence":
            fail("NOT_FOUND", "输入来源不存在或不属于当前项目", 404)
    context = prepare_context(db, user, case, body)
    job = Job(id=uid("job"), case_id=case.id, kind=kind, goal=instruction, graph_version="sop-v2", payload=encode({**context, "inputRefs": body.get("inputRefs", []), "costInputs": cost_inputs, "selectedSupplierOfferId": selected_offer_id, "changeSetId": body.get("changeSetId"), "interactive": interactive}))
    run = Run(id=uid("run"), job_id=job.id, case_id=case.id, base_revision=base_revision, action=action, instruction=instruction, payload=encode({"assetVersionIds": body.get("assetVersionIds", [])}))
    db.add(job)
    db.flush()
    db.add(run)
    db.flush()
    db.add(WorkItem(id=uid("work"), run_id=run.id))
    case.active_run_id = run.id
    case.status = "active"
    touch(case)
    create_item(db, "message", {"id": uid("msg"), "inquiryId": case.id, "role": "user", "text": instruction, "runId": run.id, "createdAt": now()}, case_id=case.id)
    result = run_view(run)
    idem_store(db, marker, result)
    db.commit()
    return result


@app.api_route("/api/v1/workspaces/{workspace_id}/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def workspace_dispatch(workspace_id: str, rest: str, request: Request, db: Session = Depends(get_db)):
    require_workspace(workspace_id)
    user = current_user(request, db)
    parts = [p for p in rest.split("/") if p]
    body = {}
    form = None
    if request.method in ("POST", "PUT", "PATCH"):
        if "multipart/form-data" in request.headers.get("content-type", ""):
            form = await request.form()
        else:
            try:
                raw = await request.body()
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                fail("INVALID_JSON", "请求 JSON 无效")
            if not isinstance(body, dict):
                fail("INVALID_INPUT", "请求正文必须是对象")
    if not parts:
        fail("NOT_FOUND", "接口不存在", 404)
    if parts[0] == "library":
        from .workspace_api import library_routes
        return library_routes(request, db, user, parts, body, form)
    if parts == ["skill-market"] and request.method == "GET":
        from .workspace_api import skill_market
        return skill_market(db)
    if parts[0] == "inquiries":
        return case_routes(request, db, user, parts[1:], body, form)
    if parts[0] == "runs":
        run = db.get(Run, parts[1]) if len(parts) > 1 else None
        if not run:
            fail("NOT_FOUND", "任务不存在", 404)
        require_case(db, user, run.case_id)
        if len(parts) > 2 and parts[2] == "cancel" and request.method == "POST":
            if run.status in ("queued", "running", "needs_input"):
                run.status = "cancelled"
                run.last_seq += 1
                case = db.get(Case, run.case_id)
                if decode(case.payload).get("pendingRunId") == run.id:
                    data = decode(case.payload)
                    data.pop("pendingRunId", None)
                    case.payload = encode(data)
                job = db.get(Job, run.job_id)
                job.status = "cancelled"
                if case.active_run_id == run.id:
                    case.active_run_id = None
                    touch(case)
                db.commit()
            return run_view(run)
        if len(parts) > 2 and parts[2] == "events":
            return {"items": sorted([item_view(i) for i in items(db, "run_event", parent_id=run.id)], key=lambda e: e["seq"])}
        return run_view(run)
    if parts[0] == "exports":
        from .exports import export_route
        return export_route(db, user, parts, request)
    return workspace_resources(request, db, user, parts, body, form)


def resource_row(db: Session, source_id: str, version: int | None = None) -> Item:
    values = [i for i in items(db, "resource") if decode(i.payload).get("sourceId") == source_id]
    if version is not None:
        values = [i for i in values if i.version == version]
    if not values:
        fail("NOT_FOUND", "资料版本不存在", 404)
    return max(values, key=lambda i: i.version)


def workspace_resources(request: Request, db: Session, user: User, parts: list[str], body: dict, form):
    group, method = parts[0], request.method
    if group in ("knowledge", "products", "sources") and method in ("POST", "PATCH", "PUT", "DELETE"):
        db.execute(text("BEGIN IMMEDIATE"))
    if group in ("knowledge", "products", "sources"):
        if len(parts) == 1 and method == "GET":
            return {"items": latest_resources(db, group)}
        if group == "knowledge" and len(parts) == 1 and method == "POST":
            title, content = body_value(body, "title", 120), body_value(body, "content")
            source_id = uid("knowledge")
            value = {"id": source_id, "sourceId": source_id, "title": title, "version": 1, "kind": "knowledge", "status": "draft", "content": content, "editVersion": 1, "updatedAt": now()}
            create_item(db, "resource", value, item_id=f"{source_id}:v1", parent_id=source_id)
            db.commit()
            return value
        if len(parts) >= 4 and parts[2] == "versions":
            row = resource_row(db, parts[1], int(parts[3]))
            value = item_view(row)
            if method == "GET":
                return value
            if len(parts) == 5 and parts[4] in ("publish", "revoke"):
                assert_admin(user)
                if parts[4] == "publish":
                    if value["status"] != "draft":
                        fail("INVALID_INPUT", "只能发布草稿")
                    value["status"] = "published"
                else:
                    body_value(body, "reason", 300)
                    value["status"] = "revoked"
                value["editVersion"] += 1
                row.status = value["status"]
                row.payload = encode(value)
                db.commit()
                return value
            if method == "PATCH":
                if value.get("ownerId") not in (None, user.id) and user.role != "admin":
                    fail("FORBIDDEN", "仅创建人或管理员可更新", 403)
                referenced = any(any(ref.get("sourceVersionId") == row.id for ref in decode(job.payload).get("sourceRefs", [])) for job in db.scalars(select(Job)))
                if referenced:
                    fail("SOURCE_VERSION_FROZEN", "此资料版本已被任务引用，请创建新版本", 409)
                if value["status"] != "draft":
                    fail("INVALID_INPUT", "已发布资料不可覆盖")
                if body.get("editVersion") != value["editVersion"]:
                    fail("METADATA_CONFLICT", "资料已修改", 409, {"current": value})
                for key in ("title", "content"):
                    if key in body:
                        value[key] = body_value(body, key)
                value["editVersion"] += 1
                value["updatedAt"] = now()
                row.payload = encode(value)
                db.commit()
                return value
        if len(parts) == 3 and parts[2] == "versions" and method == "POST":
            previous = resource_row(db, parts[1])
            old = item_view(previous)
            if old.get("ownerId") not in (None, user.id) and user.role != "admin":
                fail("FORBIDDEN", "仅创建人或管理员可更新", 403)
            value = {**old, "version": previous.version + 1, "status": "draft", "editVersion": 1, "title": body.get("title", old["title"]), "content": body.get("content", old["content"]), "updatedAt": now()}
            create_item(db, "resource", value, item_id=f"{parts[1]}:v{value['version']}", parent_id=parts[1], version=value["version"])
            db.commit()
            return value
    if group == "capabilities":
        if len(parts) == 1:
            return {"items": [item_view(i) for i in items(db, "capability")]}
        assert_admin(user)
        row = db.get(Item, f"cap_{parts[1]}")
        if not row:
            fail("NOT_FOUND", "能力不存在", 404)
        value = item_view(row)
        if "enabled" in body:
            if value.get("required") and body["enabled"] is False:
                fail("INVALID_INPUT", "核心能力不可停用")
            value["enabled"] = bool(body["enabled"])
            row.payload = encode(value)
            db.commit()
        return value
    if group == "product-imports":
        if len(parts) == 1 and method == "POST":
            upload = form.get("file") if form else None
            if not isinstance(upload, UploadFile):
                fail("INVALID_INPUT", "请选择 CSV 文件")
            data = upload.file.read(5 * 1024 * 1024 + 1)
            if len(data) > 5 * 1024 * 1024:
                fail("FILE_TOO_LARGE", "CSV 文件超过 5 MB", 413)
            try:
                decoded = data.decode("utf-8-sig")
                parsed = list(csv.DictReader(io.StringIO(decoded)))
            except (UnicodeDecodeError, csv.Error):
                fail("INVALID_INPUT", "CSV 格式或编码无效")
            errors = []
            if len(parsed) > 1000:
                errors.append({"row": 1, "field": "csv", "message": "最多 1000 行"})
            for index, row in enumerate(parsed, 2):
                for required in ("sku", "name", "minQuantity", "unitPriceMinor", "currency"):
                    if not row.get(required):
                        errors.append({"row": index, "field": required, "message": "必填"})
                try:
                    if int(row.get("unitPriceMinor", "0")) < 0 or int(row.get("minQuantity", "0")) < 1:
                        raise ValueError()
                except ValueError:
                    errors.append({"row": index, "field": "unitPriceMinor", "message": "金额或数量无效"})
            value = {"id": uid("import"), "status": "preview", "rows": parsed, "errors": errors, "validCount": len(parsed) - len({e["row"] for e in errors if e["row"] > 1}), "totalCount": len(parsed)}
            create_item(db, "product_import", value, item_id=value["id"])
            db.commit()
            return value
        row = db.get(Item, parts[1]) if len(parts) > 1 else None
        if not row or row.kind != "product_import":
            fail("NOT_FOUND", "导入不存在", 404)
        value = item_view(row)
        if len(parts) == 3 and parts[2] == "publish" and method == "POST":
            assert_admin(user)
            if value["errors"]:
                fail("BUSINESS_VALIDATION_FAILED", "导入含有错误，不能部分发布", 422)
            if value["status"] == "published":
                return value
            by_sku = {}
            for source in value["rows"]:
                by_sku.setdefault(source["sku"], []).append(source)
            for sku, rows in by_sku.items():
                source_id = f"product-{sku}"
                previous = [i for i in items(db, "resource") if decode(i.payload).get("sourceId") == source_id]
                version = max((i.version for i in previous), default=0) + 1
                dto = {"id": source_id, "sourceId": source_id, "title": rows[0]["name"], "version": version, "kind": "product", "status": "published", "content": encode(rows), "editVersion": 1, "updatedAt": now()}
                create_item(db, "resource", dto, item_id=f"{source_id}:v{version}", parent_id=source_id, version=version, status="published")
            value["status"] = "published"
            row.payload = encode(value)
            db.commit()
        return value
    if group == "assets":
        if len(parts) == 1 and method == "GET":
            from .workspace_api import asset_rows
            values = [item_view(i) for i in asset_rows(db, user)]
            return {"items": values}
        if method == "POST" and (len(parts) == 1 or len(parts) == 3 and parts[2] == "versions"):
            upload = form.get("file") if form else None
            if not isinstance(upload, UploadFile):
                fail("INVALID_INPUT", "请选择文件")
            data = upload.file.read(20 * 1024 * 1024 + 1)
            media = upload.content_type or "application/octet-stream"
            ext = Path(upload.filename or "").suffix.lower()
            if media not in ("image/jpeg", "image/png", "image/webp", "application/pdf") or ext not in (".jpg", ".jpeg", ".png", ".webp", ".pdf"):
                fail("INVALID_INPUT", "仅支持 JPEG、PNG、WebP 或 PDF")
            blob = store_blob(db, data, upload.filename or "asset", media)
            asset_id = parts[1] if len(parts) > 1 else uid("asset")
            previous_value = {}
            if len(parts) > 1:
                from .workspace_api import asset_rows
                owned = [i for i in asset_rows(db, user) if item_view(i)["id"] == asset_id]
                if not owned:
                    fail("NOT_FOUND", "文件不存在", 404)
                previous_value = item_view(owned[-1])
                if previous_value.get("ownerId") not in (None, user.id) and user.role != "admin":
                    fail("FORBIDDEN", "仅创建人或管理员可更新", 403)
            previous = [i for i in items(db, "asset") if decode(i.payload).get("id") == asset_id]
            version = max((i.version for i in previous), default=0) + 1
            sku = str(form.get("skuScope") or "[]")
            try:
                sku_scope = json.loads(sku)
            except json.JSONDecodeError:
                sku_scope = [x.strip() for x in sku.split(",") if x.strip()]
            value = {"id": asset_id, "title": str(form.get("title") or upload.filename), "name": upload.filename, "version": version, "skuScope": sku_scope, "locale": str(form.get("locale") or "zh-CN"), "mediaType": media, "source": str(form.get("source") or "用户上传"), "size": len(data), "createdAt": now(), "blobId": blob.id}
            value.update({"ownerId": previous_value.get("ownerId", user.id), "space": previous_value.get("space", "company"), "folder": previous_value.get("folder", "未分类")})
            create_item(db, "asset", value, parent_id=asset_id, version=version)
            db.commit()
            return value
        if len(parts) == 5 and parts[2] == "versions" and parts[4] == "download":
            asset_id, version = parts[1], int(parts[3])
            from .workspace_api import asset_version, attachment
            return attachment(db, asset_version(db, user, asset_id, version))
    fail("NOT_FOUND", "接口不存在", 404)
