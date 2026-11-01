"""Freeze authorized inputs at dispatch; resume the existing checkpointed task."""
import hashlib
import re

from .agent import price_quote
from .core import create_item, decode, encode, fail, idem_store, item_view, items, touch, uid
from .models import Blob, Item, Job, Run, WorkItem, now
from .workspace_api import asset_rows, asset_version, canvas_file


def require_capability(db, key):
    row = db.get(Item, f"cap_{key}")
    if row and not item_view(row).get("enabled", True):
        fail("CAPABILITY_DISABLED", "该能力已被管理员停用", 422)


def route_intent(action, instruction):
    if action == "accept_proposal":
        return "confirm_requirements"
    if action not in ("analyze", "revise"):
        return action
    if re.search(r"变更|改为|改成|修改包装|change\s+(?:the\s+)?(?:material|quantity|packaging)", instruction, re.I):
        return "apply_change"
    if re.search(r"核价|核算|计算.*报价|生成.*报价|准备.*报价|calculate.*(?:cost|price)|prepare.*quot", instruction, re.I):
        return "prepare_quote"
    if re.search(r"打样|样品计划|sample plan", instruction, re.I):
        return "manage_sample"
    if re.search(r"形式发票|生成.*PI|订单核对", instruction, re.I):
        return "confirm_order"
    if re.search(r"生产资料包", instruction):
        return "prepare_production"
    return "confirm_requirements"


def ref_list(body, name):
    refs = body.get(name) or []
    if not isinstance(refs, list) or len(refs) > 50 or any(not isinstance(r, str) for r in refs):
        fail("INVALID_INPUT", f"{name} 必须为不超过 50 个版本 ID 的列表")
    return list(dict.fromkeys(refs))


def inquiry_knowledge(db, case):
    """Latest published versions of this inquiry's references and shared knowledge."""
    latest = {}
    for row in items(db, "resource"):
        value = item_view(row)
        if (value.get("kind") != "knowledge" or value.get("status") != "published"
            or value.get("space") == "personal"
            or (value.get("caseId") and value["caseId"] != case.id)
            or (row.case_id and row.case_id != case.id)):
            continue
        key = value.get("sourceId", row.id)
        if key not in latest or row.version > latest[key].version:
            latest[key] = row
    return sorted(latest.values(), key=lambda row: (decode(row.payload).get("caseId") != case.id, row.id))


def inquiry_canvas_manifest(db, user, case, body):
    refs = ref_list(body, "canvasFileIds")
    canvas = db.get(Item, f"canvas:{case.id}:{user.id}")
    if canvas:
        refs.extend(file["serverFileId"] for file in decode(canvas.payload).get("files", []) if file.get("serverFileId"))
    manifest = []
    for ref in dict.fromkeys(refs):
        row = canvas_file(db, user, case, ref)
        blob = db.get(Blob, decode(row.payload)["blobId"])
        if not blob:
            fail("NOT_FOUND", "画板附件不存在", 404)
        manifest.append({"id": row.id, "blobId": blob.id, "sha256": blob.sha256,
                         "name": blob.filename, "mediaType": blob.media_type})
    return manifest


def prepare_context(db, user, case, body):
    source_refs, asset_refs, evidence, source_texts = [], [], [], []
    auto = body.get("agentMode") or body.get("contextScope") == "inquiry"
    refs = {name: ref_list(body, name) for name in ("inputRefs", "sourceVersionIds", "assetVersionIds")}
    if auto:
        refs["inputRefs"].extend(row.id for row in items(db, "evidence", case_id=case.id))
        refs["sourceVersionIds"].extend(row.id for row in inquiry_knowledge(db, case))
        latest_assets = {}
        for row in asset_rows(db, user):
            value = item_view(row)
            if value.get("space") == "personal" or not value.get("blobId"):
                continue
            key = value.get("id", row.id)
            if key not in latest_assets or row.version > latest_assets[key].version:
                latest_assets[key] = row
        refs["assetVersionIds"].extend(f"{key}:v{row.version}" for key, row in latest_assets.items())
    budget = 32000
    for ref in dict.fromkeys(refs["inputRefs"]):
        row = db.get(Item, ref)
        if not row or row.case_id != case.id or row.kind != "evidence":
            fail("NOT_FOUND", "证据不属于当前询盘", 404)
        evidence.append({"id": row.id, "version": row.version, **item_view(row)})
    for ref in dict.fromkeys(refs["sourceVersionIds"]):
        row = db.get(Item, ref)
        if not row or row.kind != "resource" or row.workspace_id != case.workspace_id:
            fail("NOT_FOUND", "资料版本不存在", 404)
        value = item_view(row)
        if ((value.get("caseId") and value["caseId"] != case.id) or (row.case_id and row.case_id != case.id)
            or value.get("space") == "personal"):
            fail("NOT_FOUND", "资料不属于当前询盘或共享知识库", 404)
        if value.get("status") == "revoked":
            fail("SOURCE_REVOKED", "所选资料已撤销", 422)
        source_refs.append({"sourceVersionId": row.id, "sourceId": value["sourceId"], "version": row.version,
                            "title": value["title"], "locator": {}, "supports": ["reference"],
                            "contentHash": hashlib.sha256(value["content"].encode()).hexdigest()})
        excerpt = value["content"][:min(budget, 8000)]
        budget -= len(excerpt)
        source_texts.append({"id": row.id, "content": excerpt, "truncated": len(excerpt) < len(value["content"]), "status": value["status"]})
    for ref in dict.fromkeys(refs["assetVersionIds"]):
        match = re.fullmatch(r"(.+):v(\d+)", ref)
        if not match:
            fail("INVALID_INPUT", "素材引用必须指定版本")
        row = asset_version(db, user, match[1], int(match[2]))
        value = item_view(row)
        # Personal material cannot be exposed to other case collaborators through revisions.
        if value.get("space") == "personal":
            fail("PRIVATE_ASSET", "请先将用于业务协作的资料上传到公司资产库", 422)
        blob = db.get(Blob, value["blobId"])
        asset_refs.append({"id": ref, "blobId": blob.id, "sha256": blob.sha256, "name": blob.filename})
    revisions = [r for r in items(db, "revision", case_id=case.id) if r.version == case.current_revision]
    baseline = item_view(revisions[0]).get("requirements", {}) if revisions else {}
    prior = {field: baseline.get(source) for field, source in (("product", "requestedProduct"), ("quantity", "quantity"), ("destination", "destination"), ("requested_arrival", "requestedArrival"), ("customization", "customization"), ("specification", "specification"))}
    prior["missing_fields"] = baseline.get("missingFields", [])
    proposal = None
    if body.get("action") == "accept_proposal":
        proposal = item_view(revisions[0])["proposal"] if revisions else None
        ref = body.get("proposalRef")
        if not proposal or not isinstance(ref, dict) or ref.get("proposalId") != proposal["proposalId"] or ref.get("version") != proposal["version"]:
            fail("PROPOSAL_CONFLICT", "方案版本已变化，请刷新后确认", 409)
        evidence_text = body.get("acceptanceEvidence")
        if not isinstance(evidence_text, str) or not evidence_text.strip():
            fail("INVALID_INPUT", "请填写方案确认依据")
        proposal = {**proposal, "status": "accepted", "acceptanceEvidence": evidence_text[:20000]}
    offers = []
    if body.get("selectedSupplierOfferId"):
        row = db.get(Item, str(body["selectedSupplierOfferId"]))
        if not row or row.kind != "supplier_offer" or row.case_id != case.id:
            fail("NOT_FOUND", "供应商报价不存在", 404)
        offers.append(item_view(row))
    return {"originalText": decode(case.payload).get("originalText", ""), "evidence": evidence,
            "sourceRefs": source_refs, "sourceTexts": source_texts, "assetManifest": asset_refs,
            "canvasManifest": inquiry_canvas_manifest(db, user, case, body) if auto else [],
            "supplierOffers": offers, "acceptedProposal": proposal, "priorExtracted": prior if baseline else {}, "createdBy": user.id}


def resume_run(request, db, user, case, body, marker):
    from .worker import run_view
    run = db.get(Run, str(body["replyToRunId"]))
    if not run or run.case_id != case.id:
        fail("NOT_FOUND", "任务不存在", 404)
    if run.status != "needs_input" or case.current_revision != run.base_revision or body.get("baseRevision") != run.base_revision:
        fail("REVISION_CONFLICT", "任务或业务版本已更新，请刷新", 409)
    job = db.get(Job, run.job_id)
    payload = decode(job.payload)
    is_agent = bool(payload.get("agentMode") or payload.get("agentFileTools"))
    if job.kind == "prepare_quote" and not is_agent:
        require_capability(db, "costing")
    answers = body.get("answers")
    questions = decode(run.payload).get("clarification", {}).get("questions", [])
    expected = {q["id"] for q in questions}
    if not isinstance(answers, list) or len(answers) != len(expected) or any(not isinstance(a, dict) or not isinstance(a.get("value"), str) or not a["value"].strip() or len(a["value"]) > 20000 for a in answers) or {a.get("questionId") for a in answers} != expected:
        fail("INVALID_INPUT", "请逐项填写当前任务的澄清答案")
    resume = {"text": "\n".join(a["value"].strip() for a in answers)}
    if job.kind == "prepare_quote" and not is_agent:
        row = db.get(Item, str(body.get("selectedSupplierOfferId", "")))
        if not row or row.kind != "supplier_offer" or row.case_id != case.id:
            fail("SUPPLIER_EVIDENCE_REQUIRED", "请选择当前询盘的供应商报价", 422)
        offer = item_view(row)
        cost = body.get("costInputs") or {}
        if not isinstance(cost, dict):
            fail("INVALID_INPUT", "成本参数格式无效")
        cost = {**cost, "base": offer["baseCny"], "packaging": offer["packagingCny"], "local": offer["localCny"]}
        calculated = price_quote(cost)
        if not calculated or calculated["quantity"] < offer["moq"]:
            fail("INVALID_INPUT", "请填写有效汇率、毛利率及不低于 MOQ 的数量")
        resume.update(costInputs=cost, selectedSupplierOfferId=row.id, supplierOffers=[offer])
        payload.update(costInputs=cost, selectedSupplierOfferId=row.id, supplierOffers=[offer])
    if is_agent:
        from .agent_files import confirmed_facts
        if payload.get("agentFileTools"):
            require_capability(db, "costing")
        payload["agentFacts"] = {**payload.get("agentFacts", {}), **confirmed_facts(resume["text"])}
        payload["agentMessages"] = [*payload.get("agentMessages", []), resume["text"]]
        case.payload = encode({**decode(case.payload), "agentFacts": payload["agentFacts"]})
        # New evidence may resolve the question; freeze current authorized sources for the next attempt.
        payload["evidence"] = [{"id": row.id, **item_view(row)} for row in items(db, "evidence", case_id=case.id)]
        from .workspace_api import canvas_file
        canvas_refs = body.get("canvasFileIds") or []
        if not isinstance(canvas_refs, list) or len(canvas_refs) > 50 or any(not isinstance(v, str) for v in canvas_refs):
            fail("INVALID_INPUT", "画板附件引用无效")
        manifest = {x["id"]: x for x in payload.get("canvasManifest", [])}
        if payload.get("agentMode"):
            manifest.update({x["id"]: x for x in inquiry_canvas_manifest(db, user, case, body)})
        for ref in canvas_refs:
            row = canvas_file(db, user, case, ref)
            blob = db.get(Blob, decode(row.payload)["blobId"])
            manifest[row.id] = {"id": row.id, "blobId": blob.id, "sha256": blob.sha256}
        payload["canvasManifest"] = list(manifest.values())
    payload["resume"] = resume
    job.payload = encode(payload)
    job.status = "pending"
    run.status = "queued"
    run.last_seq += 1
    data = decode(run.payload)
    data.pop("clarification", None)
    run.payload = encode(data)
    work = next(w for w in db.query(WorkItem).filter(WorkItem.run_id == run.id))
    work.status = "queued"
    work.available_at = now()
    data = decode(case.payload)
    data.pop("pendingRunId", None)
    case.payload = encode(data)
    case.active_run_id = run.id
    touch(case)
    create_item(db, "message", {"id": uid("msg"), "inquiryId": case.id, "role": "user", "text": resume["text"], "runId": run.id, "createdAt": now()}, case_id=case.id)
    result = run_view(run)
    idem_store(db, marker, result)
    db.commit()
    return result
