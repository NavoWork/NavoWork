"""Persistent projections for the canvas, Wiki and company/personal library.

Business revisions stay immutable. Canvas editVersion is an independent CAS token;
favorites and canvases are scoped to the authenticated user, never a client ownerId.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from starlette.datastructures import UploadFile

from .core import WORKSPACE_ID, create_item, decode, encode, fail, item_view, items, store_blob, uid
from .models import Blob, Case, CaseAccess, Item, now


def visible(row: Item, user) -> bool:
    value = decode(row.payload)
    return row.workspace_id == WORKSPACE_ID and (value.get("space", "company") == "company" or value.get("ownerId") == user.id)


def asset_rows(db, user):
    case_ids = set(db.scalars(select(CaseAccess.case_id).where(CaseAccess.user_id == user.id)))
    result = []
    for row in items(db, "asset"):
        value = decode(row.payload)
        if value.get("inquiry"):
            if row.case_id in case_ids and value.get("privateOwnerId") in (None, user.id):
                result.append(row)
        elif visible(row, user):
            result.append(row)
    return result


def asset_version(db, user, asset_id, version):
    row = next((r for r in asset_rows(db, user) if item_view(r).get("id") == asset_id and r.version == version), None)
    if not row:
        fail("NOT_FOUND", "文件不存在或无权访问", 404)
    return row


def attachment(db, row):
    blob = db.get(Blob, decode(row.payload)["blobId"])
    if not blob or not Path(blob.path).is_file():
        fail("NOT_FOUND", "原文件不可用", 404)
    return FileResponse(blob.path, media_type=blob.media_type, filename=blob.filename,
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


def required(body, name, limit=120):
    value = body.get(name)
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > limit:
        fail("INVALID_INPUT", f"{name} 不能为空且不得超过 {limit} 字节")
    return value.strip()


def favorite(db, user, target):
    row = db.get(Item, f"favorite:{user.id}:{target}")
    return bool(row and decode(row.payload).get("starred"))


def set_favorite(db, user, target, body):
    if not isinstance(body.get("starred"), bool):
        fail("INVALID_INPUT", "starred 必须是布尔值")
    key = f"favorite:{user.id}:{target}"
    from sqlalchemy.dialects.sqlite import insert
    stmt = insert(Item).values(id=key, kind="favorite", workspace_id=WORKSPACE_ID,
                              parent_id=user.id, payload=encode({"starred": body["starred"]}))
    db.execute(stmt.on_conflict_do_update(index_elements=[Item.id], set_={"payload": stmt.excluded.payload}))
    db.commit()
    return {"starred": body["starred"]}


def document_view(db, user, row):
    v = item_view(row)
    return {"id": v["sourceId"], "title": v["title"], "folder": v.get("folder", "业务流程"),
            "summary": re.sub(r"[#*`>]", "", v["content"]).strip()[:72], "content": v["content"],
            "updated": v["updatedAt"], "version": row.version, "sourceVersionId": row.id,
            "starred": favorite(db, user, v["sourceId"])}


def library_asset_view(db, user, row):
    v = item_view(row)
    size = v["size"]
    ext = Path(v["name"]).suffix.lower()
    mime = v["mediaType"]
    kind = "image" if mime.startswith("image/") else "video" if mime.startswith("video/") else "spreadsheet" if ext in (".xlsx", ".xls", ".csv", ".ods") else "document" if ext in (".pdf", ".docx", ".doc", ".ppt", ".pptx", ".txt", ".md") else "other"
    origin = v.get("inquiry")
    if origin:
        case = db.get(Case, row.case_id)
        origin = {**origin, "title": decode(case.payload).get("title", origin["title"])}
    return {"id": v["id"], "version": row.version, "assetVersionId": f"{v['id']}:v{row.version}",
            "name": v["name"], "folder": v.get("folder", "未分类"), "space": v.get("space", "company"),
            "size": f"{max(1, round(size / 1024))} KB" if size < 1024 * 1024 else f"{size / 1024 / 1024:.1f} MB",
            "byteSize": size, "updated": v["createdAt"], "mime": mime, "kind": kind, "art": "notes",
            "starred": favorite(db, user, v["id"]),
            **({"inquiry": origin, "sourceKind": v.get("sourceKind"), "sourceId": v.get("sourceId")} if origin else {}),
            "downloadPath": f"/workspaces/{WORKSPACE_ID}/assets/{v['id']}/versions/{row.version}/download"}


def library_routes(request, db, user, parts, body, form):
    method = request.method
    group = parts[1] if len(parts) > 1 else ""
    if group == "documents":
        rows = [r for r in items(db, "resource") if item_view(r).get("kind") == "knowledge"]
        latest = {}
        for row in rows:
            key = item_view(row)["sourceId"]
            if key not in latest or row.version > latest[key].version:
                latest[key] = row
        if len(parts) == 2 and method == "GET":
            return {"items": [document_view(db, user, r) for r in latest.values()]}
        row = latest.get(parts[2]) if len(parts) > 2 else None
        if len(parts) == 4 and parts[3] == "favorite" and method == "PUT":
            if not row:
                fail("NOT_FOUND", "文档不存在", 404)
            return set_favorite(db, user, parts[2], body)
        if method == "POST" and (len(parts) == 2 or len(parts) == 4 and parts[3] == "versions"):
            if len(parts) == 4:
                if not row:
                    fail("NOT_FOUND", "文档不存在", 404)
                if decode(row.payload).get("ownerId") not in (None, user.id) and user.role != "admin":
                    fail("FORBIDDEN", "仅文档创建人或管理员可更新", 403)
                if body.get("baseVersion") != row.version:
                    fail("VERSION_CONFLICT", "文档已有新版本，请刷新", 409)
            source_id = parts[2] if row else uid("knowledge")
            version = row.version + 1 if row else 1
            value = {"id": source_id, "sourceId": source_id, "kind": "knowledge", "status": "draft",
                     "title": required(body, "title", 300), "content": required(body, "content", 2 * 1024 * 1024),
                     "folder": required(body, "folder", 120), "ownerId": user.id, "editVersion": 1,
                     "version": version, "updatedAt": now()}
            created = create_item(db, "resource", value, item_id=f"{source_id}:v{version}", parent_id=source_id, version=version)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                fail("VERSION_CONFLICT", "文档已有新版本，请刷新", 409)
            return document_view(db, user, created)
    if group == "assets":
        if len(parts) == 2 and method == "GET":
            latest = {}
            for row in asset_rows(db, user):
                key = item_view(row)["id"]
                if key not in latest or row.version > latest[key].version:
                    latest[key] = row
            return {"items": [library_asset_view(db, user, r) for r in latest.values()]}
        if len(parts) == 4 and parts[3] == "favorite" and method == "PUT":
            if not any(item_view(r)["id"] == parts[2] for r in asset_rows(db, user)):
                fail("NOT_FOUND", "文件不存在", 404)
            return set_favorite(db, user, parts[2], body)
        if len(parts) == 2 and method == "POST":
            upload = form.get("file") if form else None
            if not isinstance(upload, UploadFile):
                fail("INVALID_INPUT", "请选择文件")
            space = form.get("space", "personal")
            if space not in ("company", "personal"):
                fail("INVALID_INPUT", "无效的资产空间")
            blob = store_blob(db, upload.file.read(100 * 1024 * 1024 + 1), upload.filename or "file",
                              upload.content_type or "application/octet-stream", max_mb=100)
            asset_id = uid("asset")
            row = create_item(db, "asset", {"id": asset_id, "title": blob.filename, "name": blob.filename,
                "version": 1, "space": space, "ownerId": user.id, "folder": str(form.get("folder") or "未分类")[:120],
                "mediaType": blob.media_type, "size": blob.byte_size, "blobId": blob.id, "createdAt": now(),
                "skuScope": [], "locale": "zh-CN", "source": "用户上传"}, parent_id=asset_id)
            db.commit()
            return library_asset_view(db, user, row)
    fail("NOT_FOUND", "接口不存在", 404)


class CanvasModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Position(CanvasModel):
    x: float
    y: float


class Viewport(Position):
    zoom: float = Field(gt=0, le=10)


class Folder(CanvasModel):
    id: str = Field(min_length=1, max_length=200)
    title: str = Field(max_length=300)


class Note(Folder):
    text: str = Field(max_length=200000)
    folder: str = Field(max_length=200)


class CanvasFile(Folder):
    name: str = Field(max_length=300)
    mediaType: str = Field(max_length=200)
    size: int = Field(ge=0)
    folder: str = Field(max_length=200)
    assetId: str | None = None
    version: int | None = Field(default=None, ge=1)
    serverFileId: str | None = None
    caseId: str | None = None


class SavedResult(CanvasModel):
    revision: int = Field(ge=1)
    title: str = Field(max_length=300)
    text: str = Field(max_length=200000)


class CanvasState(CanvasModel):
    schema_version: int = Field(alias="schema", ge=1, le=1)
    positions: dict[str, Position] = Field(default_factory=dict)
    viewport: Viewport | None = None
    directoryWidth: float | None = None
    tabs: list[str] = Field(default_factory=list, max_length=1000)
    active: str = "canvas"
    folders: list[Folder] = Field(default_factory=list, max_length=1000)
    notes: list[Note] = Field(default_factory=list, max_length=1000)
    files: list[CanvasFile] = Field(default_factory=list, max_length=1000)
    drafts: dict[str, str] = Field(default_factory=dict)
    initialRevision: int | None = None
    results: list[SavedResult] = Field(default_factory=list, max_length=1000)


def canvas_routes(request, db, user, case, tail, body, form):
    key = f"canvas:{case.id}:{user.id}"
    if len(tail) == 1:
        row = db.get(Item, key)
        if request.method == "GET":
            return {"editVersion": row.version if row else 0, "state": decode(row.payload) if row else None}
        if request.method == "PUT":
            if len(encode(body).encode()) > 3 * 1024 * 1024:
                fail("FILE_TOO_LARGE", "画板超过 3 MB，请精简笔记或附件", 413)
            try:
                state = CanvasState.model_validate(body.get("state")).model_dump(by_alias=True, exclude_none=True)
            except ValidationError:
                fail("INVALID_INPUT", "画板数据格式无效")
            version = body.get("editVersion")
            if type(version) is not int or version < 0:
                fail("INVALID_INPUT", "editVersion 无效")
            for file in state["files"]:
                if file.get("serverFileId"):
                    row_file = canvas_file(db, user, case, file["serverFileId"])
                    blob = db.get(Blob, decode(row_file.payload)["blobId"])
                    file.update(caseId=case.id, name=blob.filename, mediaType=blob.media_type, size=blob.byte_size)
                elif file.get("assetId"):
                    row_asset = asset_version(db, user, file["assetId"], file.get("version"))
                    asset = item_view(row_asset)
                    file.update(name=asset["name"], mediaType=asset["mediaType"], size=asset["size"])
                else:
                    fail("INVALID_INPUT", "请先上传文件到当前询盘")
            if any(result["revision"] > case.current_revision for result in state["results"]):
                fail("INVALID_INPUT", "成果必须属于当前询盘的已生成版本")
            if row:
                updated = db.execute(update(Item).where(Item.id == key, Item.version == version).values(
                    payload=encode(state), version=version + 1, updated_at=now()))
                if updated.rowcount != 1:
                    fail("CANVAS_CONFLICT", "画板已在其他页面更新。请下载当前草稿，再刷新合并。", 409)
            else:
                if version != 0:
                    fail("CANVAS_CONFLICT", "画板版本不匹配", 409)
                create_item(db, "canvas", state, item_id=key, case_id=case.id, parent_id=user.id)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                fail("CANVAS_CONFLICT", "画板已在其他页面创建，请刷新", 409)
            return {"editVersion": version + 1}
    if len(tail) == 2 and tail[1] == "files" and request.method == "POST":
        upload = form.get("file") if form else None
        if not isinstance(upload, UploadFile):
            fail("INVALID_INPUT", "请选择文件")
        blob = store_blob(db, upload.file.read(20 * 1024 * 1024 + 1), upload.filename or "file",
                          upload.content_type or "application/octet-stream", case.id)
        row = create_item(db, "canvas_file", {"blobId": blob.id, "ownerId": user.id}, case_id=case.id, parent_id=user.id)
        db.commit()
        return {"id": f"file:{row.id}", "serverFileId": row.id, "caseId": case.id, "name": blob.filename,
                "title": blob.filename, "mediaType": blob.media_type, "size": blob.byte_size, "folder": "materials"}
    if len(tail) == 4 and tail[1] == "files" and tail[3] == "download" and request.method == "GET":
        return attachment(db, canvas_file(db, user, case, tail[2]))
    fail("NOT_FOUND", "画板接口不存在", 404)


def canvas_file(db, user, case, file_id):
    row = db.get(Item, file_id)
    if not row or row.kind != "canvas_file" or row.case_id != case.id or row.parent_id != user.id:
        fail("NOT_FOUND", "文件不存在或不属于当前用户的画板", 404)
    return row


def skill_market(db):
    enabled = {item_view(r)["id"]: item_view(r)["enabled"] for r in items(db, "capability")}
    agent_ok = enabled.get("agent", True)
    skills = [
        ("inquiry-assessment", "客户与询盘评估", "核验客户背景、渠道、采购条件，输出待确认项与跟进建议。", ["客户档案", "风险核验"], ["客户背景", "询盘缺项", "跟进建议"]),
        ("requirements-techpack", "箱包 Tech Pack", "把客户要求整理成可询价、可打样、可生产的规格与 BOM。", ["Tech Pack", "BOM"], ["款式结构", "材料辅料", "包装与验货"]),
        ("costing-quotation", "核价与报价", "归一化多家供应商报价，用确定性工具核价并生成客户报价。", ["多供应商", "确定性计算"], ["成本行", "供应商比较", "报价条款"]),
        ("sample-management", "打样与样品确认", "记录样品轮次、费用、寄样、检查、反馈和客户批准。", ["样品台账", "批准证据"], ["开发样", "确认样", "产前样"]),
        ("order-confirmation", "PO 与 PI", "核对 PO 差异，形成 PI 草稿、双方确认与付款计划。", ["PO 差异", "付款计划"], ["PI", "合同条款", "付款保障"]),
        ("production-release", "生产资料与验货", "生成生产资料、T&A、QC 检查表并检查放行缺口。", ["生产包", "放行门禁"], ["BOM", "T&A", "QC"]),
        ("change-impact", "变更影响", "客户/供应商变更后的影响分析与联动修订。", ["版本追踪", "联动"], ["影响清单", "新草稿", "重审提示"]),
    ]
    items_out = [
        {"id": key, "tab": "skills", "name": name, "description": description, "category": "外贸业务流程", "tags": tags, "includes": includes, "status": "available" if agent_ok and (key != "costing-quotation" or enabled.get("costing", True)) else "disabled"}
        for key, name, description, tags, includes in skills
    ]
    items_out += [
        {"id": "mail-connector", "tab": "plugins", "name": "邮件连接器", "description": "将客户往来邮件带入项目；当前以原件上传为主。", "category": "连接器", "tags": ["邮件"], "includes": ["导入邮件", "关联询盘"], "status": "planned"},
        {"id": "excel-connector", "tab": "plugins", "name": "Excel 读取", "description": "读取供应商报价与订单明细。", "category": "连接器", "tags": ["XLSX"], "includes": ["报价表", "订单明细"], "status": "available"},
        {"id": "bag-export", "tab": "suites", "name": "包袋出口全流程", "description": "询盘、规格、报价、打样、订单、生产准备的连续工作台。", "category": "业务套件", "tags": ["LangGraph", "证据链"], "includes": ["Agent 工具", "版本与门禁", "知识/资产库"], "status": "available" if agent_ok else "disabled"},
    ]
    return {"items": items_out}
