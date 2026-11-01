"""Persist inquiry files in the library in the same transaction as their source."""
from __future__ import annotations

import hashlib
import re

from sqlalchemy import select

from .core import decode, encode, store_blob
from .models import Blob, Case, Item, now

SOURCE_KINDS = {"evidence", "canvas_file", "artifact", "export", "office_file", "draft"}
FOLDERS = {
    "inquiry": "客户询盘", "analysis": "需求与方案", "replies": "客户回复",
    "materials": "资料与附件", "notes": "工作笔记",
}


def _key(*parts):
    return "inquiry_asset_" + hashlib.sha256(encode(parts).encode()).hexdigest()[:32]


def _text(value, depth=0):
    """Keep all supplied values, including nested tables, without inventing facts."""
    if isinstance(value, dict):
        return "\n".join(f"{'  ' * depth}- {key}:\n{_text(child, depth + 1)}"
                         if isinstance(child, (dict, list)) else f"{'  ' * depth}- {key}: {child}"
                         for key, child in value.items())
    if isinstance(value, list):
        return "\n".join(_text(child, depth) if isinstance(child, (dict, list))
                         else f"{'  ' * depth}- {child}" for child in value)
    return str(value or "")


def _save(db, case, *, logical_id, version, source_id, source_kind, folder,
          title, blob=None, text=None, private_owner=None, created_at=None):
    asset_id = _key(case.id, logical_id)
    row_id = f"{asset_id}:v{version}"
    if db.get(Item, row_id):
        return
    if blob is None:
        name = re.sub(r'[\\/:*?"<>|\r\n]', "-", title).strip()[:120] or "询盘资料"
        content = f"# {title}\n\n> 询盘：{decode(case.payload).get('title', case.id)}\n> 来源版本：V{version}\n\n{text or ''}\n"
        blob = store_blob(db, content.encode(), f"{name}-V{version}.md", "text/markdown", case.id)
    payload = {
        "id": asset_id, "title": title, "name": blob.filename, "version": version,
        "space": "personal", "ownerId": private_owner or case.owner_id,
        "privateOwnerId": private_owner, "folder": FOLDERS[folder],
        "mediaType": blob.media_type, "size": blob.byte_size, "blobId": blob.id,
        "sha256": blob.sha256, "createdAt": created_at or now(),
        "source": "询盘自动归档", "sourceKind": source_kind, "sourceId": source_id,
        "skuScope": [], "locale": "zh-CN",
        "inquiry": {"id": case.id, "title": decode(case.payload).get("title", case.id),
                    "documentId": source_id, "folderId": folder, "folderTitle": FOLDERS[folder]},
    }
    db.add(Item(id=row_id, kind="asset", workspace_id=case.workspace_id, case_id=case.id,
                parent_id=asset_id, version=version, status="draft", payload=encode(payload)))


def archive_original(db, case):
    original = decode(case.payload).get("originalText")
    if original:
        _save(db, case, logical_id=("original", hashlib.sha256(original.encode()).hexdigest()),
              version=1, source_id=case.id, source_kind="original", folder="inquiry",
              title="客户原始询盘", text=original, created_at=case.updated_at)


def archive_source(db, row):
    if row.kind not in SOURCE_KINDS or not row.case_id:
        return
    case = db.get(Case, row.case_id)
    if not case:
        return
    value = decode(row.payload)
    blob = db.get(Blob, value["blobId"]) if value.get("blobId") else None
    # A broken attachment is never silently replaced by extracted text.
    if value.get("blobId") and blob is None:
        return
    version = row.version
    logical_id = (row.kind, row.id)
    folder = "materials"
    title = value.get("title") or value.get("name") or (blob.filename if blob else "询盘资料")
    text = value.get("text")
    private_owner = None
    if row.kind == "canvas_file":
        private_owner = value.get("ownerId") or row.parent_id
    elif row.kind == "evidence":
        folder = "inquiry" if value.get("sourceRole") in {
            "customer_request", "customer_change", "customer_po", "customer_approval"
        } else "materials"
    elif row.kind == "artifact":
        content = value.get("content") or {}
        if "not_present_in_source_revision" in content.get("missingFields", []):
            return
        logical_id = (row.kind, value.get("kind", row.parent_id))
        folder = "replies" if value.get("kind") == "customer_reply" else "analysis"
        text = "> 业务草稿，保留原始状态及待确认项。\n\n" + _text(content)
    elif row.kind == "office_file":
        logical_id = (row.kind, value.get("documentId", row.parent_id))
        folder = "analysis"
    elif row.kind == "export":
        if not blob or value.get("status") not in ("ready", "stale", "needs_review", "superseded"):
            return
        logical_id = (row.kind, value.get("artifactVersionId") or value.get("revision") or row.id,
                      value.get("format"), blob.sha256)
        folder = "analysis"
    elif row.kind == "draft":
        logical_id = (row.kind, row.parent_id)
        title = f"回复草稿 {value.get('locale', '')}"
        folder = "replies"
    if blob and row.kind in ("evidence", "canvas_file"):
        logical_id = (row.kind, private_owner, blob.filename, blob.sha256)
    if not blob and not text:
        return
    _save(db, case, logical_id=logical_id, version=version, source_id=row.id,
          source_kind=row.kind, folder=folder, title=title, blob=blob, text=text,
          private_owner=private_owner, created_at=value.get("createdAt") or row.created_at)


def backfill_inquiry_assets(db):
    """Upgrade existing inquiry files once; deterministic IDs make reruns harmless."""
    for case in db.scalars(select(Case)):
        archive_original(db, case)
    rows = list(db.scalars(select(Item).where(Item.kind.in_(SOURCE_KINDS), Item.case_id.is_not(None))))
    for row in rows:
        archive_source(db, row)
