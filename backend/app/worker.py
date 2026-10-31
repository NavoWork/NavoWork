from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from sqlalchemy import select, text

from .agent import build_graph
from .core import create_item, decode, encode, items, uid
from .db import SessionLocal, engine
from .models import Case, Item, Job, Run, WorkItem, now


NODE_ARTIFACTS = {
    "extract_bag_requirements": {"spec"}, "draft_spec_pack": {"spec"},
    "build_supplier_rfq": {"rfq"}, "normalize_quotes": {"comparison"},
    "calculate_cost": {"cost"}, "draft_quotation": {"quotation"},
    "plan_sample": {"sample"}, "sample_approval_gate": {"sample"},
    "compare_po_to_baseline": {"pi"}, "draft_contract_or_pi": {"pi"},
    "prepare_production_pack": {"production"},
}


def run_view(run: Run) -> dict:
    value = {"id": run.id, "runId": run.id, "inquiryId": run.case_id, "baseRevision": run.base_revision, "status": run.status, "phase": run.phase, "action": run.action, "instruction": run.instruction, "lastSeq": run.last_seq, "createdAt": run.created_at}
    if run.output_revision is not None:
        value["outputRevision"] = run.output_revision
    if run.error:
        value["error"] = decode(run.error)
    if decode(run.payload).get("clarification"):
        value["clarification"] = decode(run.payload)["clarification"]
    value["completedPhases"] = decode(run.payload).get("completedPhases", [])
    value["fileOutputs"] = decode(run.payload).get("fileOutputs", [])
    value["agentVerification"] = decode(run.payload).get("agentVerification")
    return value


def claim_work(owner: str) -> tuple[str, int] | None:
    with engine.connect() as conn:
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        current = now()
        row = conn.execute(text("SELECT w.id,w.lease_generation FROM work_items w JOIN runs r ON r.id=w.run_id WHERE ((w.status='queued' AND w.available_at<=:current) OR (w.status='running' AND w.lease_expires_at<:current)) AND r.status IN ('queued','running') ORDER BY w.available_at,w.id LIMIT 1"), {"current": current}).first()
        if not row:
            conn.commit()
            return None
        generation = row.lease_generation + 1
        lease = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(timespec="seconds").replace("+00:00", "Z")
        conn.execute(text("UPDATE work_items SET status='running',lease_owner=:owner,lease_expires_at=:lease,lease_generation=:generation,attempts=attempts+1 WHERE id=:id"), {"owner": owner, "lease": lease, "generation": generation, "id": row.id})
        conn.commit()
        return row.id, generation


def build_revision(case: Case, run: Run, state: dict, previous: dict | None = None) -> dict:
    facts = state.get("extracted", {})
    quote_result = state.get("quote")
    quote = None
    if quote_result:
        source_ids = [state["selectedSupplierOfferId"]] if state.get("selectedSupplierOfferId") else []
        quote = {"sku": facts.get("product") or "CUSTOM", "quantity": quote_result["quantity"], "currency": "USD", "unitPriceMinor": quote_result["unitPriceMinor"], "goodsSubtotalMinor": quote_result["goodsSubtotalMinor"], "freightMinor": None, "taxMinor": None, "totalMinor": None, "quoteStatus": "draft", "sourceVersionIds": source_ids, "timing": {"dispatchDays": None, "productionDays": None, "startsAfter": "以客户/工厂确认及付款条件为准", "transitDays": None, "arrivalGuaranteed": False}}
    risks = [{"id": uid("risk"), "severity": risk.get("severity", "warning"), "category": risk.get("code", "business"), "message": risk["message"], "suggestedAction": "补充可核验的资料并人工确认", "status": "open", "evidenceRefs": []} for risk in state.get("risks", [])]
    for field in facts.get("missing_fields", []):
        risks.append({"id": uid("risk"), "severity": "info", "category": "missing_field", "message": f"{field} 尚未得到证实", "suggestedAction": "向客户或供应商澄清", "status": "open", "evidenceRefs": []})
    case_data = decode(case.payload)
    if previous and state.get("kind") == "apply_change":
        old_requirements = previous.get("requirements", {})
        requirements = {**old_requirements, "missingFields": sorted(set(old_requirements.get("missingFields", [])) | {"changed_requirements_reconfirmation"}), "evidenceRefs": sorted(set(old_requirements.get("evidenceRefs", [])) | set(state.get("input_refs", [])))}
        return {**previous, "number": case.current_revision + 1, "runId": run.id, "requirements": requirements, "quote": None, "risks": [*previous.get("risks", []), {"id": uid("risk"), "severity": "warning", "category": "change_pending", "message": "业务变更待逐节点复核，原报价不可作为当前最终价", "suggestedAction": "核对新版成本与报价", "status": "open", "evidenceRefs": state.get("input_refs", [])}], "createdAt": now(), "changeSummary": [state.get("summary", "已生成待审核变更")], "jobId": run.job_id}
    return {"inquiryId": case.id, "number": case.current_revision + 1, "runId": run.id, "requirements": {"requestedProduct": facts.get("product"), "specification": facts.get("specification"), "quantity": facts.get("quantity"), "destination": facts.get("destination") or case_data.get("destination"), "requestedArrival": facts.get("requested_arrival"), "customization": facts.get("customization"), "certificationRequests": [], "missingFields": facts.get("missing_fields", []), "evidenceRefs": state.get("input_refs", [])}, "proposal": {"proposalId": uid("proposal"), "version": case.current_revision + 1, "requestedSku": facts.get("product"), "selectedSku": None, "differences": [], "status": "requested"}, "quote": quote, "replies": {"en-US": f"Thank you for your inquiry about {facts.get('product') or 'the requested product'}. We are reviewing the specification, pricing and delivery conditions. We will confirm the missing details before making a firm offer.", "es-MX": "Gracias por su consulta. Estamos revisando las especificaciones, el precio y las condiciones de entrega. Confirmaremos los datos pendientes antes de presentar una oferta firme."}, "risks": risks, "checks": [{"label": "来源与未知字段", "status": "warning" if risks else "passed"}], "sourceRefs": [], "assetRefs": decode(run.payload).get("assetVersionIds", []), "ruleSetVersion": "trade-p0-v1", "createdAt": now(), "changeSummary": [state.get("summary", "已生成待审核草稿")], "jobId": run.job_id}


def finish_work(item_id: str, generation: int, state: dict):
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        item = db.get(WorkItem, item_id)
        if not item or item.lease_generation != generation or item.status != "running":
            return
        run = db.get(Run, item.run_id)
        if not run or run.status == "cancelled":
            item.status = "done"
            db.commit()
            return
        case = db.get(Case, run.case_id)
        job = db.get(Job, run.job_id)
        if case.active_run_id != run.id or case.current_revision != run.base_revision:
            item.status = "done"
            db.commit()
            return
        previous = next((decode(i.payload) for i in items(db, "revision", case_id=case.id) if i.version == case.current_revision), None)
        rev = build_revision(case, run, state, previous)
        context = decode(job.payload)
        rev["sourceRefs"] = context.get("sourceRefs", [])
        rev["inputManifest"] = {"evidence": context.get("evidence", []), "assets": context.get("assetManifest", []), "sourceRefs": rev["sourceRefs"]}
        if context.get("acceptedProposal"):
            rev["proposal"] = context["acceptedProposal"]
        if job.kind == "prepare_quote" and rev.get("quote"):
            if not decode(job.payload).get("selectedSupplierOfferId"):
                raise ValueError("核价缺少供应商原件")
        create_item(db, "revision", rev, case_id=case.id, parent_id=case.id, version=rev["number"])
        for locale, value in rev["replies"].items():
            create_item(db, "draft", {"inquiryId": case.id, "revision": rev["number"], "locale": locale, "draftVersion": 1, "text": value, "reviewStatus": "needs_review", "updatedAt": now()}, case_id=case.id, parent_id=f"{case.id}:{rev['number']}:{locale}")
        for artifact in ([] if job.kind == "apply_change" else state.get("artifacts", [])):
            existing = [i for i in items(db, "artifact", case_id=case.id) if decode(i.payload).get("kind") == artifact["kind"]]
            version = max((i.version for i in existing), default=0) + 1
            create_item(db, "artifact", {"caseId": case.id, "kind": artifact["kind"], "title": artifact["title"], "version": version, "content": artifact["content"], "status": "draft", "jobId": job.id, "runId": run.id, "createdAt": now()}, case_id=case.id, parent_id=artifact["kind"], version=version, item_id=f"artifact_{case.id}_{artifact['kind']}_v{version}")
        if job.kind == "apply_change":
            change_id = decode(job.payload).get("changeSetId")
            change = db.get(Item, change_id) if change_id else None
            if change and change.case_id != case.id:
                raise ValueError("变更不属于当前项目")
            if not change:
                impacts = state.get("impacts", [])
                change = create_item(db, "change_set", {"caseId": case.id, "jobId": job.id, "status": "proposed", "sourceText": run.instruction, "baseRevision": run.base_revision, "nodeImpacts": impacts, "createdAt": now()}, case_id=case.id)
                db.flush()
                for impact in impacts:
                    create_item(db, "node_impact", {"changeSetId": change.id, **impact}, case_id=case.id, parent_id=change.id)
            changed = decode(change.payload)
            candidate_ids = []
            impacted_kinds = set().union(*(NODE_ARTIFACTS.get(impact.get("nodeKey"), set()) for impact in changed.get("nodeImpacts", [])))
            for kind in sorted(impacted_kinds):
                previous = [i for i in items(db, "artifact", case_id=case.id) if decode(i.payload).get("kind") == kind]
                if not previous:
                    continue
                latest = max(previous, key=lambda i: i.version)
                old = decode(latest.payload)
                content = {**old.get("content", {}), "changeNotice": changed.get("instruction") or run.instruction, "pendingReconfirmation": True}
                if kind in ("cost", "quotation"):
                    content["quote"] = None
                    content["result"] = None
                    content["missingFields"] = sorted(set(content.get("missingFields", [])) | {"updated_supplier_cost"})
                next_version = latest.version + 1
                candidate_id = f"artifact_{case.id}_{kind}_v{next_version}"
                candidate = create_item(db, "artifact", {**old, "id": candidate_id, "version": next_version, "content": content, "status": "draft", "basedOnId": latest.id, "changeSetId": change.id, "createdAt": now()}, case_id=case.id, parent_id=kind, version=next_version, item_id=candidate_id)
                candidate_ids.append(candidate.id)
            if not candidate_ids:
                changed["missingArtifactBaseline"] = True
            changed["status"] = "awaiting_confirmation"
            changed["candidateArtifactIds"] = candidate_ids
            changed["baseRevision"] = rev["number"]
            changed["regeneratedByRunId"] = run.id
            change.payload = encode(changed)
        case.current_revision = rev["number"]
        if job.kind == "apply_change":
            for approval in items(db, "approval", case_id=case.id):
                old_approval = decode(approval.payload)
                if old_approval.get("decision") == "approved":
                    old_approval["decision"] = "superseded"
                    old_approval["supersededByRunId"] = run.id
                    approval.payload = encode(old_approval)
        case.active_run_id = None
        case.status = "active"
        case.metadata_version += 1
        case.updated_at = now()
        run.output_revision = rev["number"]
        run.status = "succeeded"
        run.phase = "committing"
        data = decode(run.payload)
        data["completedPhases"] = list(dict.fromkeys([*data.get("completedPhases", []), "committing"]))
        run.payload = encode(data)
        run.last_seq += 1
        create_item(db, "run_event", {"runId": run.id, "inquiryId": case.id, "seq": run.last_seq, "type": "run.succeeded", "payload": {"phase": "committing"}, "createdAt": now()}, case_id=case.id, parent_id=run.id)
        job.status = "needs_review" if job.kind in ("prepare_quote", "manage_sample", "confirm_order", "apply_change") else "completed"
        item.status = "done"
        create_item(db, "message", {"id": uid("msg"), "inquiryId": case.id, "role": "assistant", "text": state.get("summary", "已生成草稿和待办"), "runId": run.id, "createdAt": now()}, case_id=case.id)
        db.commit()


def fail_work(item_id: str, generation: int, exc: Exception):
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        item = db.get(WorkItem, item_id)
        if not item or item.lease_generation != generation:
            return
        run = db.get(Run, item.run_id)
        if not run or run.status == "cancelled":
            item.status = "done"
            db.commit()
            return
        case = db.get(Case, run.case_id)
        job = db.get(Job, run.job_id)
        run.status = "failed"
        run.error = encode({"code": "AGENT_FAILED", "message": str(exc)[:300]})
        run.last_seq += 1
        job.status = "failed"
        if case.active_run_id == run.id:
            case.active_run_id = None
            case.metadata_version += 1
        item.status = "done"
        db.commit()


def record_progress(item_id, generation, phase, clarification=None):
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        item = db.get(WorkItem, item_id)
        run = db.get(Run, item.run_id) if item else None
        if not item or item.lease_generation != generation or not run or run.status == "cancelled":
            return False
        run.phase = phase
        run.last_seq += 1
        data = decode(run.payload)
        if phase != "committing":
            data["completedPhases"] = list(dict.fromkeys([*data.get("completedPhases", []), phase]))
        run.payload = encode(data)
        if clarification:
            run.status = "needs_input"
            run.payload = encode({**decode(run.payload), "clarification": clarification})
            job = db.get(Job, run.job_id)
            job.status = "needs_input"
            data = decode(job.payload)
            data.pop("resume", None)
            job.payload = encode(data)
            case = db.get(Case, run.case_id)
            case.active_run_id = None
            case.payload = encode({**decode(case.payload), "pendingRunId": run.id})
            case.metadata_version += 1
            item.status = "waiting"
        create_item(db, "run_event", {"runId": run.id, "inquiryId": run.case_id, "seq": run.last_seq,
                    "type": f"run.{run.status}", "payload": {"phase": phase, "clarification": clarification}, "createdAt": now()},
                    case_id=run.case_id, parent_id=run.id)
        db.commit()
        return True


def work_once(graph, owner: str = "worker-local") -> bool:
    claimed = claim_work(owner)
    if not claimed:
        return False
    item_id, generation = claimed
    try:
        with SessionLocal() as db:
            item = db.get(WorkItem, item_id)
            run = db.get(Run, item.run_id)
            if run.status == "cancelled":
                item.status = "done"
                db.commit()
                return True
            job = db.get(Job, run.job_id)
            case = db.get(Case, run.case_id)
            run.status = "running"
            run.phase = "understanding"
            run.last_seq += 1
            job.status = "running"
            db.commit()
            payload = decode(job.payload)
            if payload.get("agentFileTools"):
                from .file_worker import execute_file_work
                execute_file_work(item_id, generation)
                return True
            source_texts = [i.get("text", "") for i in payload.get("evidence", [])]
            if job.kind == "apply_change":
                text_input = "\n".join([run.instruction, *source_texts])[:20000]
            else:
                text_input = "\n".join([run.instruction, payload.get("originalText", decode(case.payload).get("originalText", "")), *source_texts])[:20000]
            state = {"job_id": job.id, "case_id": case.id, "kind": job.kind, "text": text_input, "input_refs": payload.get("inputRefs", []), "costInputs": payload.get("costInputs", {}), "supplierOffers": payload.get("supplierOffers", []), "selectedSupplierOfferId": payload.get("selectedSupplierOfferId"), "interactive": payload.get("interactive", False), "source_refs": payload.get("sourceRefs", []), "source_texts": payload.get("sourceTexts", []), "asset_manifest": payload.get("assetManifest", [])}
            state.update(prior_extracted=payload.get("priorExtracted", {}), instruction=run.instruction)
        config = {"configurable": {"thread_id": job.id}}
        snapshot = graph.get_state(config)
        if not snapshot.values:
            graph_input = state
        elif snapshot.next:
            graph_input = Command(resume=payload["resume"]) if payload.get("resume") else None
        else:
            graph_input = None
        if not snapshot.values or snapshot.next:
            phases = {"read_context": "retrieving", "understand": "understanding", "clarify": "understanding", "impact": "calculating", "calculate": "calculating", "draft": "composing", "validate": "validating"}
            for update in graph.stream(graph_input, config=config, stream_mode="updates"):
                if update.get("__interrupt__"):
                    record_progress(item_id, generation, "understanding", update["__interrupt__"][0].value)
                    return True
                for node in update:
                    if not record_progress(item_id, generation, phases.get(node, "understanding")):
                        return True
        output = graph.get_state(config).values
        if not record_progress(item_id, generation, "committing"):
            return True
        finish_work(item_id, generation, output)
    except Exception as exc:
        fail_work(item_id, generation, exc)
    return True


def main():
    checkpoint_path = Path(os.getenv("GRAPH_CHECKPOINT_DB", "./data/agent-checkpoints.sqlite3"))
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with SqliteSaver.from_conn_string(str(checkpoint_path)) as checkpointer:
        checkpointer.setup()
        graph = build_graph(checkpointer)
        while True:
            if not work_once(graph):
                time.sleep(0.5)


if __name__ == "__main__":
    main()
