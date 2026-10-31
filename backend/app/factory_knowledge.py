"""Versioned factory knowledge used as a quotation's fixed pricing basis."""
import hashlib
from .core import item_view, items


def content_hash(value):
    return hashlib.sha256(value.get("content", "").encode()).hexdigest()


def latest_knowledge(db, workspace_id):
    latest = {}
    for row in items(db, "resource"):
        value = item_view(row)
        if row.workspace_id != workspace_id or value.get("kind") != "knowledge":
            continue
        key = value.get("sourceId")
        if key and (key not in latest or row.version > latest[key].version):
            latest[key] = row
    return latest


def require_current_factory_source(db, case, row, expected_hash=None):
    value = item_view(row)
    latest = latest_knowledge(db, case.workspace_id).get(value.get("sourceId"))
    if not latest or latest.id != row.id:
        raise ValueError("工厂资料已有新版本，请重新读取知识库中的最新版本并核价")
    if value.get("status") == "revoked":
        raise ValueError("工厂资料已撤销，请维护知识库后重新核价")
    if expected_hash and content_hash(value) != expected_hash:
        raise ValueError("工厂资料内容已变更，请重新读取知识库并核价")
    return value


def quotation_knowledge_status(db, case):
    artifacts = {}
    for row in items(db, "artifact", case_id=case.id):
        kind = item_view(row).get("kind")
        if kind in ("cost", "quotation") and (kind not in artifacts or row.version > artifacts[kind].version):
            artifacts[kind] = row
    sources = latest_knowledge(db, case.workspace_id)
    current = None
    for row in artifacts.values():
        ref = item_view(row).get("content", {}).get("factorySource")
        if not ref:
            continue
        latest = sources.get(ref.get("sourceId"))
        stale = not latest or latest.id != ref.get("sourceVersionId") or item_view(latest).get("status") == "revoked" or content_hash(item_view(latest)) != ref.get("contentHash")
        current = {**ref, "outdated": stale, "latestVersion": latest.version if latest else None}
        if stale:
            return current
    return current
