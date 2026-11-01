"""Case-scoped adapter for the independent BOM image candidate extractor."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from .core import create_item, decode, item_view, items
from .models import Blob, Item


def _vision_package():
    package_root = Path(__file__).resolve().parents[2] / "extensions" / "bom-vision"
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from bom_vision import correct, recognize, revalidate
    from bom_vision.adapters import AdapterError, OpenAICompatibleAdapter
    return correct, recognize, revalidate, AdapterError, OpenAICompatibleAdapter


def configured_adapter():
    _, _, _, AdapterError, Adapter = _vision_package()
    try:
        return Adapter.from_environment()
    except AdapterError:
        return None


def recognize_case_evidence(db, case, evidence, *, actor: str, adapter=None, persist=True):
    _, recognize, _, AdapterError, Adapter = _vision_package()
    value = item_view(evidence)
    if evidence.case_id != case.id or evidence.kind != "evidence":
        raise ValueError("BOM 图片原件不属于当前 Case")
    if value.get("sourceRole") not in ("supplier_quote", "internal_note"):
        raise ValueError("BOM 图片必须是供应商报价或用户提供的内部原件")
    blob = db.get(Blob, value.get("blobId")) if value.get("blobId") else None
    if not blob or blob.case_id != case.id or blob.media_type not in ("image/png", "image/jpeg"):
        raise ValueError("BOM 识别仅支持当前 Case 中的 PNG/JPEG 原件")
    data = Path(blob.path).read_bytes()
    actual_hash = hashlib.sha256(data).hexdigest()
    frozen_hash = value.get("sha256") or blob.sha256
    if actual_hash != blob.sha256 or frozen_hash != blob.sha256:
        raise ValueError("BOM 图片原件哈希不匹配")
    candidate_id = "bom_" + hashlib.sha256(f"{case.id}:{evidence.id}:{blob.sha256}".encode()).hexdigest()[:24]
    existing = [row for row in items(db, "bom_candidate", case_id=case.id)
                if decode(row.payload).get("candidate_id") == candidate_id]
    if existing:
        latest = max(existing, key=lambda row: row.version)
        return {**item_view(latest), "summary": "该图片哈希已有识别候选；保留当前候选版本"}
    selected_adapter = adapter if adapter is not None else Adapter.from_environment()
    file_ref = {"file_id": evidence.id, "case_id": case.id, "sha256": blob.sha256,
                "media_type": blob.media_type, "name": blob.filename, "version": evidence.version}
    candidate = recognize(data, file_ref, selected_adapter)
    candidate.update(candidate_id=candidate_id, case_id=case.id, source_evidence_id=evidence.id,
                     created_by=actor, status="candidate", revision=1,
                     validation={**candidate["validation"], "needs_review": True, "price_approved": False})
    if not persist:
        return candidate
    return save_case_candidate(db, case, candidate)


def save_case_candidate(db, case, candidate):
    """Commit a computed candidate after the caller rechecks its Run/lease."""
    candidate_id = candidate["candidate_id"]
    source = db.get(Item, candidate["source_evidence_id"])
    if not source or source.case_id != case.id or source.kind != "evidence":
        raise ValueError("BOM source is no longer available")
    source_value = item_view(source)
    blob = db.get(Blob, source_value.get("blobId"))
    if (not blob or blob.case_id != case.id or blob.sha256 != candidate["source"]["sha256"]
        or hashlib.sha256(Path(blob.path).read_bytes()).hexdigest() != blob.sha256):
        raise ValueError("BOM source changed during recognition")
    existing = [row for row in items(db, "bom_candidate", case_id=case.id)
                if decode(row.payload).get("candidate_id") == candidate_id]
    if existing:
        return {**item_view(max(existing, key=lambda row: row.version)), "summary": "该原件已有候选；保留当前候选版本"}
    row = create_item(db, "bom_candidate", candidate, case_id=case.id, parent_id=source.id,
        version=1, status="needs_review", item_id=f"{candidate_id}:v1")
    db.flush()
    return {**item_view(row), "summary": "已保存 BOM 识别候选，必须对照原图逐项复核；未核价或批准"}


def correct_case_candidate(db, case, candidate_row, *, expected_revision: int, patches: list[dict],
                           reason: str, actor: str):
    correct, _, revalidate, _, _ = _vision_package()
    if candidate_row.case_id != case.id or candidate_row.kind != "bom_candidate":
        raise ValueError("BOM 候选不属于当前 Case")
    current = item_view(candidate_row)
    latest = max((row.version for row in items(db, "bom_candidate", case_id=case.id)
                  if decode(row.payload).get("candidate_id") == current.get("candidate_id")), default=0)
    if latest != candidate_row.version or expected_revision != candidate_row.version:
        raise ValueError("BOM 候选版本已变化，请重新读取")
    result = correct(current, patches, expected_revision=expected_revision,
                     actor=actor, reason=reason)
    source_id = current.get("source_evidence_id")
    source = next((row for row in items(db, "evidence", case_id=case.id) if row.id == source_id), None)
    if source is None:
        raise ValueError("BOM 原件版本不可用")
    source_value = item_view(source)
    blob = db.get(Blob, source_value.get("blobId")) if source_value.get("blobId") else None
    if not blob or blob.case_id != case.id or hashlib.sha256(Path(blob.path).read_bytes()).hexdigest() != current["source"]["sha256"]:
        raise ValueError("BOM 原件哈希已变化，拒绝纠正")
    result.update(candidate_id=current["candidate_id"], case_id=case.id,
                  source_evidence_id=source.id, created_by=actor, status="candidate")
    result["validation"] = {**revalidate(result)["validation"], "needs_review": True, "price_approved": False}
    next_version = candidate_row.version + 1
    row = create_item(
        db, "bom_candidate", result, case_id=case.id, parent_id=source.id,
        version=next_version, status="needs_review", item_id=f"{current['candidate_id']}:v{next_version}")
    db.flush()
    return {**item_view(row), "summary": "已保存新的人工纠正版；仍待复核且未核价或批准"}
