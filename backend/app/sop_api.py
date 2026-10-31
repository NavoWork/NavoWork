from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from .agent import KEYWORDS, NODE_FIELDS, extract_without_model
from .core import case_view, create_item, decode, encode, fail, item_view, items, store_blob, uid
from .models import Blob, Case, Item, Job, User, now


def _row(db: Session, case: Case, value: str, kind: str) -> Item:
    row = db.get(Item, value)
    if not row or row.case_id != case.id or row.kind != kind:
        fail("NOT_FOUND", "对象不存在或无权访问", 404)
    return row


def _list(db: Session, case: Case, kind: str, parent: str | None = None):
    return {"items": [item_view(i) for i in items(db, kind, case_id=case.id, parent_id=parent)]}


def _create(db: Session, case: Case, kind: str, body: dict, status: str = "draft", parent: str | None = None):
    item_id = f"artifact_{case.id}_{parent}_v{body['version']}" if kind == "artifact" else uid(kind)
    value = {**body, "id": item_id, "caseId": case.id, "createdAt": now(), "status": status}
    row = create_item(db, kind, value, case_id=case.id, status=status, parent_id=parent, item_id=value["id"], version=int(value.get("version", 1)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail("ARTIFACT_CONFLICT", "指定版本已有更新", 409)
    return item_view(row)


def _extract_file(data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".eml", ".csv", ".md"):
        return data.decode("utf-8-sig", errors="replace")[:50000]
    if ext == ".docx":
        try:
            from zipfile import ZipFile
            from xml.etree import ElementTree
            with ZipFile(io.BytesIO(data)) as archive:
                if archive.getinfo("word/document.xml").file_size > 5 * 1024 * 1024:
                    return ""
                document = ElementTree.fromstring(archive.read("word/document.xml"))
            namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            return "\n".join("".join(p.itertext()) for p in document.findall(".//w:p", namespace))[:50000]
        except Exception:
            return ""
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages[:100])[:50000]
        except Exception:
            return ""
    if ext == ".xlsx":
        try:
            from openpyxl import load_workbook
            book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            lines = []
            for sheet in book.worksheets[:5]:
                lines.append(f"[{sheet.title}]")
                for row in sheet.iter_rows(max_row=500, values_only=True):
                    lines.append("\t".join(str(cell) if cell is not None else "" for cell in row[:30]))
            return "\n".join(lines)[:50000]
        except Exception:
            return ""
    return ""


EVIDENCE_ROLES = {"customer_request", "supplier_quote", "customer_change", "customer_po", "customer_approval", "supplier_confirmation", "internal_note", "payment_receipt", "sample_inspection", "shipping_document"}


def _impact(text: str, case: Case):
    lower = text.lower()
    fields = [field for field, words in KEYWORDS.items() if any(word.lower() in lower for word in words)] or ["unclassified"]
    seen = {}
    for field in fields:
        for pos, node in enumerate(NODE_FIELDS.get(field, [])):
            entry = seen.setdefault(node, {"nodeKey": node, "stage": "sop", "impactType": "direct" if pos == 0 else "downstream", "triggerFields": [], "reason": [], "severity": "review", "state": "potentially_impacted", "requiredAction": "edit_or_review", "editTarget": {"caseId": case.id, "nodeKey": node}})
            entry["triggerFields"].append(field)
            entry["reason"].append(f"{field} 变化可能影响该节点输入或其下游成果")
    if not seen:
        return [{"nodeKey": "manual_review", "stage": "sop", "impactType": "uncertain", "triggerFields": fields, "reason": ["无法可靠分类，需人工标注影响范围"], "severity": "review", "state": "potentially_impacted", "requiredAction": "classify", "editTarget": {"caseId": case.id, "nodeKey": "manual_review"}}]
    return list(seen.values())


def _artifact_validation(value: dict) -> dict:
    kind = value.get("kind")
    content = value.get("content") or {}
    required = {
        "spec": ("product", "quantity", "material", "dimensions", "packaging", "inspectionStandard"),
        "quotation": ("product", "quantity", "quote", "selectedSupplierOfferId", "incoterm", "namedPlace", "paymentTerms", "validUntil"),
        "pi": ("buyer", "seller", "product", "quantity", "unitPrice", "total", "incoterm", "paymentTerms"),
        "cost": ("input", "result", "selectedSupplierOfferId"),
        "comparison": ("supplierOffers",),
        "rfq": ("product", "quantity", "requiredSpecVersion"),
    }.get(kind, ())
    missing = [name for name in required if content.get(name) in (None, "", [], {})]
    if kind == "quotation" and content.get("pendingReconfirmation"):
        missing.append("changeReconfirmation")
    return {"status": "blocked" if missing else "passed", "results": [{"code": "MISSING_FIELD", "fieldPath": name, "message": f"{name} 待确认"} for name in missing], "targetVersionId": value["id"]}


def _check_release(db: Session, case: Case) -> list[str]:
    reasons = []
    approvals = [item_view(i) for i in items(db, "approval", case_id=case.id) if item_view(i).get("decision") == "approved"]
    samples = [item_view(i) for i in items(db, "sample", case_id=case.id)]
    orders = [item_view(i) for i in items(db, "order_confirmation", case_id=case.id)]
    payments = [item_view(i) for i in items(db, "payment_assurance", case_id=case.id)]
    spec_versions = [i for i in items(db, "artifact", case_id=case.id) if decode(i.payload).get("kind") == "spec"]
    current_spec = max(spec_versions, key=lambda i: i.version).id if spec_versions else None
    current_target = str(case.current_revision)
    current_spec_target = current_spec
    current_quote_versions = [i for i in items(db, "artifact", case_id=case.id) if decode(i.payload).get("kind") == "quotation"]
    current_quote_target = max(current_quote_versions, key=lambda i: i.version).id if current_quote_versions else None
    if not any(a.get("scope") == "customer_spec_approval" and a.get("targetVersionId") == current_spec_target for a in approvals):
        reasons.append("客户尚未书面确认最终规格")
    if not any(s.get("customerApproved") is True and s.get("evidenceSourceId") and s.get("specVersionId") == current_spec for s in samples):
        reasons.append("最终样品尚未获得有证据的客户批准")
    if not any(a.get("scope") == "commercial_quotation_approval" and a.get("targetVersionId") == current_quote_target for a in approvals):
        reasons.append("报价尚未获得内部商业批准")
    if not any(o.get("buyerConfirmed") and o.get("sellerConfirmed") and o.get("documentVersionId") and o.get("buyerEvidenceSourceId") and o.get("sellerEvidenceSourceId") for o in orders):
        reasons.append("订单文件尚未由双方确认同一版本")
    if not any(p.get("decision") == "verified" and p.get("evidenceSourceId") and p.get("verifiedBy") and p.get("verificationBasis") for p in payments):
        reasons.append("定金或付款保障尚未经责任人核验")
    if not any(a.get("scope") == "supplier_production_confirmation" and a.get("targetVersionId") == current_target for a in approvals):
        reasons.append("供应商生产条件尚未确认")
    if any(item_view(i).get("status") not in ("applied", "rejected", "cancelled") for i in items(db, "change_set", case_id=case.id)):
        reasons.append("仍有未关闭的业务变更")
    return reasons


def sop_case_routes(request: Request, db: Session, user: User, case: Case, tail: list[str], body: dict, form):
    if not tail:
        fail("NOT_FOUND", "接口不存在", 404)
    method, group = request.method, tail[0]
    if group == "message-suggestions" and method == "GET" and len(tail) == 1:
        from .message_suggestions import next_messages
        return next_messages(db, case)
    if group == "node-generations" and method == "POST" and len(tail) == 1:
        from .main import create_run
        kinds = {"customer": "qualify_inquiry", "requirements": "confirm_requirements", "risks": "confirm_requirements", "quote": "prepare_quote", "reply": "confirm_requirements", "sample": "manage_sample", "order": "confirm_order", "production": "prepare_production"}
        target = body.get("node")
        if target not in kinds:
            fail("INVALID_INPUT", "该节点尚不支持生成")
        if any(item_view(c).get("status") not in ("applied", "rejected", "cancelled") for c in items(db, "change_set", case_id=case.id)):
            fail("CHANGE_ACTIVATION_BLOCKED", "请先完成开放变更的节点维护，避免生成任务改变变更基线", 409)
        return create_run(request, db, user, case, {**body, "generationTarget": target, "action": "generate_node", "instruction": body.get("instruction") or f"从已选择的询盘和来源生成 {target} 节点草稿，未知信息保持待确认"}, kind=kinds[target])
    if group == "supplier-offers":
        if len(tail) == 1 and method == "GET":
            return _list(db, case, "supplier_offer")
        if len(tail) == 1 and method == "POST":
            source_id = body.get("evidenceSourceId")
            if not source_id or item_view(_row(db, case, str(source_id), "evidence")).get("sourceRole") != "supplier_quote":
                fail("INVALID_INPUT", "供应商报价须关联供应商原件")
            supplier = str(body.get("supplier") or "").strip()
            if not supplier:
                fail("INVALID_INPUT", "请填写供应商")
            try:
                base = Decimal(str(body["baseCny"]))
                packaging = Decimal(str(body["packagingCny"]))
                local = Decimal(str(body.get("localCny", 0)))
                minimum = int(body.get("moq", 1))
                lead = int(body.get("leadDays", 0))
                if min(base, packaging, local) < 0 or minimum < 1 or lead < 0:
                    raise ValueError()
            except (KeyError, InvalidOperation, ValueError):
                fail("INVALID_INPUT", "供应商单价、起订量或交期无效")
            return _create(db, case, "supplier_offer", {"supplier": supplier, "evidenceSourceId": source_id, "baseCny": str(base), "packagingCny": str(packaging), "localCny": str(local), "moq": minimum, "leadDays": lead, "currency": "CNY", "includesPackaging": bool(body.get("includesPackaging", False)), "notes": str(body.get("notes") or "")}, status="observed")
        if len(tail) == 2 and method == "GET":
            return item_view(_row(db, case, tail[1], "supplier_offer"))
        fail("NOT_FOUND", "接口不存在", 404)
    if group == "jobs":
        if len(tail) == 1 and method == "GET":
            return {"items": [{"id": job.id, "caseId": case.id, "kind": job.kind, "goal": job.goal, "status": job.status, "createdAt": job.created_at} for job in db.query(Job).filter(Job.case_id == case.id).order_by(Job.created_at.desc())]}
        if len(tail) == 1 and method == "POST":
            from .main import create_run
            kind = str(body.get("kind", ""))
            return create_run(request, db, user, case, {**body, "action": kind, "instruction": body.get("goal", "处理当前业务目标")}, kind=kind)
        job = db.get(Job, tail[1])
        if not job or job.case_id != case.id:
            fail("NOT_FOUND", "任务不存在", 404)
        return {"id": job.id, "caseId": case.id, "kind": job.kind, "goal": job.goal, "status": job.status, "createdAt": job.created_at, "runs": [{"id": run.id, "status": run.status, "outputRevision": run.output_revision} for run in job_runs(db, job.id)]}
    if group == "sop-status" and method == "GET":
        revisions = items(db, "revision", case_id=case.id)
        artifact_rows = items(db, "artifact", case_id=case.id)
        kinds = {decode(i.payload).get("kind") for i in artifact_rows}
        change_rows = [item_view(i) for i in items(db, "change_set", case_id=case.id)]
        open_changes = [i for i in change_rows if i.get("status") not in ("applied", "rejected", "cancelled")]
        release_reasons = _check_release(db, case)
        stages = [
            ("qualify_inquiry", bool(items(db, "customer_profile", case_id=case.id)) or bool(revisions)),
            ("confirm_requirements", "spec" in kinds),
            ("prepare_quote", bool(kinds & {"cost", "comparison", "quotation"})),
            ("manage_sample", bool(kinds & {"sample", "sample_feedback"}) or bool(items(db, "sample", case_id=case.id))),
            ("confirm_order", bool(kinds & {"pi", "po_check"}) or bool(items(db, "order_confirmation", case_id=case.id))),
            ("prepare_production", bool(kinds & {"production", "ta"}) or bool(items(db, "production_pack", case_id=case.id))),
            ("inspect_quality", "qc" in kinds),
            ("manage_shipment", "shipment" in kinds),
            ("reconcile_payment", "payment" in kinds),
        ]
        return {"caseId": case.id, "currentRevision": case.current_revision, "stages": [{"kind": kind, "status": "needs_review" if present else "not_started"} for kind, present in stages], "openChangeCount": len(open_changes), "productionRelease": {"status": "blocked" if release_reasons else "ready_for_manual_release", "missing": release_reasons}}
    if group == "evidence":
        if len(tail) == 1:
            if method == "GET":
                return _list(db, case, "evidence")
            if method == "POST":
                upload = form.get("file") if form else None
                if upload and isinstance(upload, UploadFile):
                    data = upload.file.read(20 * 1024 * 1024 + 1)
                    ext = Path(upload.filename or "").suffix.lower()
                    if ext not in (".txt", ".eml", ".csv", ".pdf", ".xlsx", ".docx", ".jpg", ".jpeg", ".png", ".webp"):
                        fail("INVALID_INPUT", "文件类型不受支持")
                    blob = store_blob(db, data, upload.filename or "evidence", upload.content_type or "application/octet-stream", case.id)
                    value = {"title": upload.filename, "sourceRole": str(form.get("sourceRole") or "internal_note"), "blobId": blob.id, "sha256": blob.sha256, "text": _extract_file(data, upload.filename or ""), "parseStatus": "pending"}
                else:
                    text_value = str(body.get("text", "")).strip()
                    if not text_value or len(text_value) > 50000:
                        fail("INVALID_INPUT", "请提供原文或文件")
                    value = {"title": str(body.get("title") or "粘贴原文"), "sourceRole": str(body.get("sourceRole") or "internal_note"), "blobId": None, "sha256": __import__("hashlib").sha256(text_value.encode()).hexdigest(), "text": text_value, "parseStatus": "pending"}
                if value["sourceRole"] not in EVIDENCE_ROLES:
                    fail("INVALID_INPUT", "证据来源角色不支持")
                return _create(db, case, "evidence", value, status="observed")
        row = _row(db, case, tail[1], "evidence")
        value = item_view(row)
        if len(tail) == 2:
            return value
        if tail[2] == "download":
            blob = db.get(Blob, value.get("blobId")) if value.get("blobId") else None
            if not blob:
                fail("NOT_FOUND", "没有原始文件", 404)
            return FileResponse(blob.path, media_type=blob.media_type, filename=blob.filename)
        if tail[2] == "parse" and method == "POST":
            extracted = extract_without_model(value.get("text", ""))
            facts = []
            for field, result in extracted.model_dump().items():
                if field == "missing_fields" or result is None:
                    continue
                fact = _create(db, case, "fact", {"sourceId": row.id, "fieldPath": field, "value": result, "status": "observed", "purpose": "drafting", "provenanceType": "parsed"}, status="observed")
                facts.append(fact)
            value["parseStatus"] = "succeeded" if facts else "partial"
            row.payload = encode(value)
            db.commit()
            return {"id": uid("parse"), "status": value["parseStatus"], "factIds": [f["id"] for f in facts], "missingFields": extracted.missing_fields}
    if group == "facts":
        if len(tail) == 1:
            if method == "GET":
                return _list(db, case, "fact")
            return _create(db, case, "fact", {"fieldPath": str(body.get("fieldPath") or ""), "value": body.get("value"), "sourceId": body.get("sourceId"), "purpose": str(body.get("purpose") or "drafting"), "provenanceType": "manual", "createdBy": user.id, "status": "proposed"}, status="proposed")
        row = _row(db, case, tail[1], "fact")
        value = item_view(row)
        if len(tail) == 3 and tail[2] in ("confirmations", "reject") and method == "POST":
            if tail[2] == "reject":
                value["status"] = "rejected"
            else:
                evidence_id = body.get("evidenceSourceId") or (body.get("evidenceRefs") or [None])[0]
                if evidence_id:
                    _row(db, case, evidence_id, "evidence")
                value["status"] = "confirmed"
                value["confirmation"] = {"type": body.get("type"), "purpose": body.get("purpose"), "evidenceSourceId": evidence_id, "actorId": user.id, "createdAt": now()}
            row.status = value["status"]
            row.payload = encode(value)
            db.commit()
        return value
    if group == "artifacts":
        if len(tail) == 1:
            if method == "GET":
                return _list(db, case, "artifact")
            kind = str(body.get("kind") or "")
            if kind not in ("spec", "rfq", "comparison", "cost", "quotation", "sample", "sample_feedback", "po_check", "pi", "production", "ta", "qc", "shipment", "payment", "followup"):
                fail("INVALID_INPUT", "成果类型不支持")
            if any(decode(i.payload).get("kind") == kind for i in items(db, "artifact", case_id=case.id)):
                fail("ARTIFACT_CONFLICT", "该成果已有版本，请编辑最新版本", 409)
            if not isinstance(body.get("content") or {}, dict):
                fail("INVALID_INPUT", "成果内容必须是 JSON 对象")
            return _create(db, case, "artifact", {"kind": kind, "title": body.get("title") or kind, "version": 1, "content": body.get("content") or {}, "createdBy": user.id}, parent=kind)
        row = _row(db, case, tail[1], "artifact")
        value = item_view(row)
        if len(tail) == 2:
            return value
        if tail[2] == "exports" and method == "POST":
            from .exports import export_artifact
            return export_artifact(db, case, row, str(body.get("format") or "pdf"))
        if tail[2] == "restore" and method == "POST":
            from sqlalchemy import text
            db.execute(text("BEGIN IMMEDIATE"))
            db.refresh(case)
            if case.active_run_id or decode(case.payload).get("pendingRunId") or case.status in ("waiting", "done"):
                fail("INVALID_STATUS_TRANSITION", "请先恢复处理并完成当前任务", 409)
            if any(item_view(c).get("status") not in ("applied", "rejected", "cancelled") for c in items(db, "change_set", case_id=case.id)):
                fail("CHANGE_ACTIVATION_BLOCKED", "请先完成当前变更的节点修订", 409)
            same_kind = [i for i in items(db, "artifact", case_id=case.id) if decode(i.payload).get("kind") == value["kind"]]
            latest = max(same_kind, key=lambda i: i.version)
            if body.get("baseVersion") != latest.version:
                fail("ARTIFACT_CONFLICT", "成果版本已有更新，请刷新", 409)
            content = {**value["content"], "status": "draft"}
            for key in ("released", "customerApproved"):
                if key in content:
                    content[key] = False
            return _create(db, case, "artifact", {"kind": value["kind"], "title": value["title"], "version": latest.version + 1, "content": content, "basedOnId": latest.id, "restoredFromId": row.id, "createdBy": user.id}, parent=value["kind"])
        if tail[2] == "versions":
            group_rows = [i for i in items(db, "artifact", case_id=case.id) if decode(i.payload).get("kind") == value["kind"]]
            if len(tail) == 3 and method == "GET":
                return {"items": [item_view(i) for i in group_rows]}
            if len(tail) == 3 and method == "POST":
                latest = max(group_rows, key=lambda i: i.version)
                if latest.id != row.id or int(body.get("baseVersion", -1)) != value["version"]:
                    fail("ARTIFACT_CONFLICT", "成果版本已有更新", 409)
                if not isinstance(body.get("content") or {}, dict):
                    fail("INVALID_INPUT", "成果内容必须是 JSON 对象")
                return _create(db, case, "artifact", {"kind": value["kind"], "title": body.get("title") or value["title"], "version": value["version"] + 1, "content": body.get("content") or {}, "createdBy": user.id, "basedOnId": row.id}, parent=value["kind"])
            if len(tail) > 3:
                found = next((i for i in group_rows if i.version == int(tail[3])), None)
                if not found:
                    fail("NOT_FOUND", "版本不存在", 404)
                return item_view(found)
        if tail[2] == "validate":
            return _artifact_validation(value)
        if tail[2] == "diff":
            base = next((item_view(i) for i in items(db, "artifact", case_id=case.id) if i.version == int(request.query_params.get("from", 0)) and decode(i.payload).get("kind") == value["kind"]), None)
            if not base:
                fail("NOT_FOUND", "原版本不存在", 404)
            return {"from": base, "to": value, "changedFields": [k for k in set(base.get("content", {})) | set(value.get("content", {})) if base.get("content", {}).get(k) != value.get("content", {}).get(k)]}
    if group == "change-sets":
        if len(tail) == 1:
            if method == "GET":
                return _list(db, case, "change_set")
            text = str(body.get("instruction") or body.get("text") or "").strip()
            if not text:
                fail("INVALID_INPUT", "请描述变更")
            source_id = body.get("sourceId")
            if source_id:
                _row(db, case, source_id, "evidence")
            impacts = _impact(text, case)
            value = _create(db, case, "change_set", {"triggerType": body.get("triggerType") or "manual", "sourceId": source_id, "instruction": text, "baseRevision": case.current_revision, "nodeImpacts": impacts, "status": "proposed"}, status="proposed")
            for impact in impacts:
                _create(db, case, "node_impact", {"changeSetId": value["id"], **impact}, status="potentially_impacted", parent=value["id"])
            return value
        row = _row(db, case, tail[1], "change_set")
        value = item_view(row)
        if len(tail) == 2:
            return value
        if tail[2] == "node-impacts":
            return _list(db, case, "node_impact", parent=row.id)
        if tail[2] == "node-actions" and method == "GET":
            return {"items": [item_view(i) for i in items(db, "node_action", case_id=case.id) if decode(i.payload).get("changeSetId") == row.id]}
        if tail[2] == "reject" and method == "POST":
            if value.get("status") in ("applied", "rejected", "cancelled"):
                fail("CHANGE_CLOSED", "变更已关闭", 409)
            if user.role != "admin" or not str(body.get("reason") or "").strip():
                fail("INVALID_INPUT", "管理员需填写拒绝原因")
            value["status"] = "rejected"
            value["rejectedBy"] = user.id
            value["rejectionReason"] = str(body["reason"]).strip()
            row.payload = encode(value)
            db.commit()
            return value
        if tail[2] == "node-actions" and method == "POST":
            if value["status"] in ("applied", "rejected", "cancelled"):
                fail("CHANGE_CLOSED", "变更已关闭", 409)
            impact = next((x for x in value["nodeImpacts"] if x["nodeKey"] == body.get("nodeKey")), None)
            if not impact:
                fail("NOT_FOUND", "受影响节点不存在", 404)
            action = body.get("action")
            if action not in ("edit", "regenerate", "request_evidence", "review", "no_impact"):
                fail("INVALID_INPUT", "节点动作不支持")
            reason = str(body.get("reason") or "").strip()
            if not reason:
                fail("INVALID_INPUT", "请记录节点处理依据")
            artifact_id = body.get("targetArtifactVersionId")
            if action in ("edit", "regenerate"):
                if not artifact_id:
                    fail("INVALID_INPUT", "编辑或重生成须关联新的成果版本")
                artifact = _row(db, case, str(artifact_id), "artifact")
                if artifact.version < 2:
                    fail("INVALID_INPUT", "请先保存新的成果版本")
                if decode(artifact.payload).get("basedOnId") not in set(value.get("candidateArtifactIds") or []):
                    fail("INVALID_INPUT", "请选择本次变更候选成果编辑后的版本")
            return _create(db, case, "node_action", {"changeSetId": row.id, "nodeKey": impact["nodeKey"], "action": action, "reason": reason, "targetArtifactVersionId": artifact_id, "editTarget": impact["editTarget"]})
        if tail[2] in ("decisions", "activate") and method == "POST":
            if value["status"] in ("applied", "rejected", "cancelled"):
                fail("CHANGE_CLOSED", "变更已关闭", 409)
            if tail[2] == "activate":
                if user.role != "admin":
                    fail("FORBIDDEN", "仅管理员可激活变更", 403)
                actions = [item_view(i) for i in items(db, "node_action", case_id=case.id) if item_view(i).get("changeSetId") == row.id]
                candidate_ids = set(value.get("candidateArtifactIds") or [])
                edited_ids = {i.id for i in items(db, "artifact", case_id=case.id) if decode(i.payload).get("basedOnId") in candidate_ids}
                handled = {a["nodeKey"] for a in actions if (a.get("action") == "no_impact" and a.get("reason")) or (a.get("action") in ("edit", "regenerate") and a.get("targetArtifactVersionId") in edited_ids)}
                required = {i["nodeKey"] for i in value["nodeImpacts"]}
                relevant = {i["nodeKey"] for i in value["nodeImpacts"] if i.get("impactType") == "direct"}
                if any(a.get("action") == "no_impact" and a.get("nodeKey") in relevant for a in actions):
                    fail("CHANGE_ACTIVATION_BLOCKED", "直接受影响节点不能直接标记无影响", 422)
                handled -= {a["nodeKey"] for a in actions if a.get("action") == "no_impact" and a.get("nodeKey") in relevant}
                if any(a.get("action") in ("edit", "regenerate") and a.get("targetArtifactVersionId") not in edited_ids for a in actions):
                    fail("CHANGE_ACTIVATION_BLOCKED", "节点修订必须关联经人工编辑的本次变更成果", 422)
                if not value.get("regeneratedByRunId"):
                    fail("CHANGE_ACTIVATION_BLOCKED", "请先生成联动修订草稿并逐节点复核", 422)
                if not value.get("sourceId") or value.get("baseRevision") != case.current_revision or value.get("missingArtifactBaseline") or not required <= handled:
                    fail("CHANGE_ACTIVATION_BLOCKED", "变更缺少来源、节点处理或基线版本已更新", 422, {"unhandledNodes": sorted(required - handled)})
                for candidate_id in candidate_ids:
                    candidate = _row(db, case, candidate_id, "artifact")
                    descendants = [i for i in items(db, "artifact", case_id=case.id) if decode(i.payload).get("basedOnId") == candidate_id]
                    if not descendants:
                        fail("CHANGE_ACTIVATION_BLOCKED", "候选成果尚未人工编辑成新版本", 422)
                value["status"] = "applied"
                value["activatedBy"] = user.id
                value["activatedAt"] = now()
            else:
                value["status"] = "awaiting_confirmation"
            row.payload = encode(value)
            db.commit()
            return value
        if tail[2] == "regenerate" and method == "POST":
            from .main import create_run
            if value.get("status") in ("applied", "rejected", "cancelled"):
                fail("CHANGE_CLOSED", "变更已关闭", 409)
            return create_run(request, db, user, case, {"baseRevision": case.current_revision, "instruction": value["instruction"], "action": "apply_change", "changeSetId": row.id, "inputRefs": [value["sourceId"]] if value.get("sourceId") else []}, kind="apply_change")
    if group == "approvals":
        if len(tail) == 1:
            if method == "GET":
                return _list(db, case, "approval")
            if user.role != "admin":
                fail("FORBIDDEN", "内部批准需要管理员", 403)
            target = body.get("targetVersionId") or body.get("targetManifestHash")
            if not target:
                fail("INVALID_INPUT", "批准必须指向固定版本或清单")
            scope = body.get("scope")
            if scope not in ("commercial_quotation_approval", "customer_spec_approval", "supplier_production_confirmation") or body.get("decision") not in ("approved", "rejected"):
                fail("INVALID_INPUT", "批准范围或决定无效")
            target_id = body.get("targetVersionId")
            if target_id:
                target_row = db.get(Item, str(target_id))
                valid_revision = str(target_id).isdigit() and int(target_id) in [i.version for i in items(db, "revision", case_id=case.id)]
                if not valid_revision and not (target_row and target_row.case_id == case.id and target_row.kind in ("artifact", "revision", "production_pack")):
                    fail("NOT_FOUND", "批准目标版本不存在", 404)
                required_kind = {"commercial_quotation_approval": "quotation", "customer_spec_approval": "spec"}.get(scope)
                if required_kind and (not target_row or target_row.kind != "artifact" or decode(target_row.payload).get("kind") != required_kind):
                    fail("INVALID_INPUT", "批准目标与业务范围不匹配")
            refs = body.get("evidenceRefs") or []
            if scope != "commercial_quotation_approval" and not refs:
                fail("INVALID_INPUT", "外部确认必须有原始证据")
            expected_role = {"customer_spec_approval": "customer_approval", "supplier_production_confirmation": "supplier_confirmation"}.get(scope)
            for ref in refs:
                evidence = item_view(_row(db, case, str(ref), "evidence"))
                if expected_role and evidence.get("sourceRole") != expected_role:
                    fail("INVALID_INPUT", "证据来源角色与批准范围不匹配")
            if scope == "commercial_quotation_approval" and body.get("decision") == "approved":
                quote_value = item_view(target_row)
                quote_content = quote_value.get("content", {})
                offer_id = quote_content.get("selectedSupplierOfferId")
                offer = db.get(Item, str(offer_id)) if offer_id else None
                validation = _artifact_validation(quote_value)
                if validation["status"] != "passed" or not offer or offer.case_id != case.id or offer.kind != "supplier_offer":
                    fail("BUSINESS_VALIDATION_FAILED", "报价草稿尚无可核验的核价结果或需重新确认", 422)
            return _create(db, case, "approval", {"targetVersionId": body.get("targetVersionId"), "targetManifestHash": body.get("targetManifestHash"), "scope": body.get("scope"), "decision": body.get("decision"), "evidenceRefs": body.get("evidenceRefs", []), "note": body.get("note"), "actorId": user.id}, status=body.get("decision", "pending"))
        row = _row(db, case, tail[1], "approval")
        value = item_view(row)
        if len(tail) == 3 and tail[2] == "revoke" and method == "POST":
            if user.role != "admin":
                fail("FORBIDDEN", "仅管理员可撤回批准", 403)
            value["decision"] = "revoked"
            value["revocationReason"] = body.get("reason")
            row.payload = encode(value)
            db.commit()
        return value
    if group in ("customer-profile", "followups", "samples", "order-confirmations", "payment-assurance-checks", "operational-events"):
        kind = {"customer-profile": "customer_profile", "followups": "followup", "samples": "sample", "order-confirmations": "order_confirmation", "payment-assurance-checks": "payment_assurance", "operational-events": "operational_event"}[group]
        if len(tail) == 1:
            if method == "GET":
                return _list(db, case, kind)
            if group == "order-confirmations" and (body.get("buyerConfirmed") or body.get("sellerConfirmed")):
                document_id = body.get("documentVersionId")
                if not document_id:
                    fail("INVALID_INPUT", "须指定双方确认的订单文件版本")
                if item_view(_row(db, case, str(document_id), "evidence")).get("sourceRole") != "customer_po":
                    fail("INVALID_INPUT", "订单文件须来自客户 PO")
                for party, role in (("buyer", "customer_approval"), ("seller", "internal_note")):
                    if body.get(f"{party}Confirmed"):
                        evidence_id = body.get(f"{party}EvidenceSourceId")
                        if not evidence_id or item_view(_row(db, case, str(evidence_id), "evidence")).get("sourceRole") != role:
                            fail("INVALID_INPUT", f"{party} 确认缺少对应角色的独立证据")
                if body.get("buyerConfirmed") and body.get("sellerConfirmed") and body["buyerEvidenceSourceId"] == body["sellerEvidenceSourceId"]:
                    fail("INVALID_INPUT", "买卖双方确认不可复用同一证据")
            if group == "payment-assurance-checks" and body.get("decision") == "verified":
                source_id = body.get("evidenceSourceId")
                if not source_id or not str(body.get("verificationBasis") or "").strip():
                    fail("INVALID_INPUT", "核验付款保障必须提供证据及人工核验依据")
                if item_view(_row(db, case, source_id, "evidence")).get("sourceRole") != "payment_receipt":
                    fail("INVALID_INPUT", "付款保障核验须使用财务或银行凭据")
                if user.role != "admin":
                    fail("FORBIDDEN", "付款保障仅可由管理员核验", 403)
                body["verifiedBy"] = user.id
            if group == "operational-events" and body.get("eventType") in ("production_started", "qc_passed", "shipped", "payment_received"):
                fail("NOT_IMPLEMENTED", "生产、验货、出运及到账实况尚未接入可信业务来源", 422)
            if group in ("customer-profile", "followups"):
                body["createdBy"] = user.id
            if group == "samples" and body.get("customerApproved"):
                source_id = body.get("evidenceSourceId")
                if not source_id:
                    fail("INVALID_INPUT", "客户批准样品必须提供书面证据")
                if item_view(_row(db, case, source_id, "evidence")).get("sourceRole") != "customer_approval":
                    fail("INVALID_INPUT", "样品批准须使用客户批准证据")
                if not body.get("specVersionId") or item_view(_row(db, case, str(body["specVersionId"]), "artifact")).get("kind") != "spec":
                    fail("INVALID_INPUT", "样品批准须绑定规格成果版本")
            return _create(db, case, kind, body)
        row = _row(db, case, tail[1], kind)
        return item_view(row)
    if group == "production-packs":
        if len(tail) == 1 and method == "GET":
            return _list(db, case, "production_pack")
        if len(tail) == 1 and method == "POST":
            if not isinstance(body.get("revision"), int) or body["revision"] != case.current_revision or not body["revision"]:
                fail("INVALID_INPUT", "生产资料包必须绑定当前业务版本")
            return _create(db, case, "production_pack", {"manifest": body, "released": False})
        row = _row(db, case, tail[1], "production_pack")
        value = item_view(row)
        if len(tail) == 3 and tail[2] in ("validate", "release"):
            reasons = _check_release(db, case)
            if value.get("manifest", {}).get("revision") != case.current_revision:
                reasons.append("生产资料包引用的业务版本不是当前版本")
            if tail[2] == "release":
                if reasons:
                    fail("PRODUCTION_RELEASE_BLOCKED", "生产资料门禁未通过", 422, {"missing": reasons})
                if user.role != "admin":
                    fail("FORBIDDEN", "需要管理员放行", 403)
                value["released"] = True
                value["status"] = "released"
                row.payload = encode(value)
                db.commit()
                return value
            return {"status": "blocked" if reasons else "passed", "missing": reasons, "manifest": value["manifest"]}
        return value
    fail("NOT_FOUND", "接口不存在", 404)


def job_runs(db: Session, job_id: str):
    from .models import Run
    return db.query(Run).filter(Run.job_id == job_id).order_by(Run.created_at).all()
