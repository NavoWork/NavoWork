from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Blob, Case, CaseAccess, Idempotency, Item, LoginSession, User, now

WORKSPACE_ID = "ws_demo"
WORKSPACE_NAME = "NavoWork 工作空间"
STORAGE_ROOT = Path(os.getenv("STORAGE_ROOT", "./storage")).resolve()
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def decode(value: str | None, default=None):
    return json.loads(value) if value else ({} if default is None else default)


def fail(code: str, message: str, status: int = 400, details=None):
    raise HTTPException(status_code=status, detail={"code": code, "message": message, "details": details or {}})


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    return salt.hex() + ":" + hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()


def password_ok(password: str, stored: str) -> bool:
    try:
        salt_hex, digest = stored.split(":", 1)
        return secrets.compare_digest(password_hash(password, bytes.fromhex(salt_hex)).split(":")[1], digest)
    except (ValueError, TypeError):
        return False


def login_user(db: Session, email: str, password: str) -> tuple[dict, str]:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not user or not password_ok(password, user.password_hash):
        fail("INVALID_CREDENTIALS", "邮箱或密码错误", 401)
    token = secrets.token_urlsafe(40)
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    db.add(LoginSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id, expires_at=expires))
    db.commit()
    return session_view(user), token


def session_view(user: User) -> dict:
    return {"user": {"id": user.id, "name": user.name, "role": user.role}, "workspace": {"id": WORKSPACE_ID, "name": WORKSPACE_NAME}}


def current_user(request: Request, db: Session) -> User:
    token = request.cookies.get("nv_session")
    if not token:
        fail("SESSION_EXPIRED", "请登录后继续", 401)
    record = db.get(LoginSession, hashlib.sha256(token.encode()).hexdigest())
    if not record or record.expires_at < datetime.now(timezone.utc).isoformat():
        fail("SESSION_EXPIRED", "会话已过期", 401)
    user = db.get(User, record.user_id)
    if not user:
        fail("SESSION_EXPIRED", "账户不可用", 401)
    return user


def require_workspace(workspace_id: str):
    if workspace_id != WORKSPACE_ID:
        fail("NOT_FOUND", "工作空间不存在", 404)


def require_case(db: Session, user: User, case_id: str, *, include_deleted: bool = False) -> Case:
    case = db.get(Case, case_id)
    if not case or case.workspace_id != WORKSPACE_ID or not db.get(CaseAccess, (case_id, user.id)):
        fail("NOT_FOUND", "询盘不存在或无权查看", 404)
    if not include_deleted and decode(case.payload).get("deletedAt"):
        fail("NOT_FOUND", "询盘已删除，可从已删除列表恢复", 404)
    return case


def item_view(item: Item) -> dict:
    result = decode(item.payload)
    result.setdefault("id", item.id)
    return result


def create_item(db: Session, kind: str, payload: dict, *, case_id: str | None = None, parent_id: str | None = None, version: int = 1, status: str = "draft", item_id: str | None = None) -> Item:
    item = Item(id=item_id or uid(kind), kind=kind, workspace_id=WORKSPACE_ID, case_id=case_id, parent_id=parent_id, version=version, status=status, payload=encode(payload))
    db.add(item)
    if case_id and kind in {"evidence", "canvas_file", "artifact", "export", "office_file", "draft"}:
        from .inquiry_assets import archive_source
        archive_source(db, item)
    return item


def items(db: Session, kind: str, *, case_id: str | None = None, parent_id: str | None = None) -> list[Item]:
    stmt = select(Item).where(Item.kind == kind, Item.workspace_id == WORKSPACE_ID)
    if case_id is not None:
        stmt = stmt.where(Item.case_id == case_id)
    if parent_id is not None:
        stmt = stmt.where(Item.parent_id == parent_id)
    return list(db.scalars(stmt.order_by(Item.created_at, Item.id)))


def case_view(case: Case) -> dict:
    value = decode(case.payload)
    return {"id": case.id, "workspaceId": case.workspace_id, **value, "ownerId": case.owner_id, "businessStatus": case.status, "metadataVersion": case.metadata_version, "currentRevision": case.current_revision, "activeRunId": case.active_run_id, "updatedAt": case.updated_at}


def touch(case: Case):
    case.metadata_version += 1
    case.updated_at = now()


def idem_lookup(db: Session, request: Request, body: dict):
    key = request.headers.get("Idempotency-Key")
    if not key:
        return None, None
    scope = f"{request.method}:{request.url.path}:{key}"
    hash_value = hashlib.sha256(encode(body).encode()).hexdigest()
    record = db.get(Idempotency, scope)
    if record:
        if record.body_hash != hash_value:
            fail("IDEMPOTENCY_CONFLICT", "同一幂等键不能用于不同内容", 409)
        return decode(record.response), None
    return None, (scope, hash_value)


def idem_store(db: Session, marker, response: dict):
    if marker:
        db.add(Idempotency(key=marker[0], body_hash=marker[1], response=encode(response)))


def store_blob(db: Session, data: bytes, filename: str, media_type: str, case_id: str | None = None, *, max_mb: int = 20) -> Blob:
    if len(data) > max_mb * 1024 * 1024:
        fail("FILE_TOO_LARGE", f"文件超过 {max_mb} MB", 413)
    blob_id = uid("blob")
    target = STORAGE_ROOT / blob_id
    tmp = STORAGE_ROOT / (blob_id + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(target)
    blob = Blob(id=blob_id, workspace_id=WORKSPACE_ID, case_id=case_id, media_type=media_type, filename=Path(filename).name[:180], sha256=hashlib.sha256(data).hexdigest(), byte_size=len(data), path=str(target))
    db.add(blob)
    return blob


def bootstrap(db: Session):
    if os.getenv("APP_ENV", "demo") != "demo":
        return
    email = os.getenv("DEMO_EMAIL", "demo@navowork.local").lower()
    if db.scalar(select(User).where(User.email == email)):
        return
    user = User(id=uid("user"), email=email, name="Alex", password_hash=password_hash(os.getenv("DEMO_PASSWORD", "ChangeMe123!")), role="admin")
    db.add(user)
    db.flush()
    case = Case(id="inq_demo_bag", workspace_id=WORKSPACE_ID, owner_id=user.id, payload=encode({"title": "德国客户 · 定制背包", "customer": "Michael Weber", "originalText": "Please quote 3,000 custom backpacks with our logo, FOB Ningbo. We would like them in Hamburg within 45 days if possible.", "requestedLocales": ["en-US", "es-MX"], "destination": "Hamburg", "nextAction": "确认规格、供应商报价与样品要求"}), status="todo")
    db.add(case)
    db.flush()
    db.add(CaseAccess(case_id=case.id, user_id=user.id))
    create_item(db, "message", {"id": uid("msg"), "inquiryId": case.id, "role": "user", "text": decode(case.payload)["originalText"], "createdAt": now()}, case_id=case.id)
    db.commit()
