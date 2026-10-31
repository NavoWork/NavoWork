"""Composition of the real tool loop with existing Worker, authorization and Items."""
from __future__ import annotations

import os
from pathlib import Path
from decimal import Decimal
from sqlalchemy import text
from langgraph.checkpoint.sqlite import SqliteSaver
from navowork_agent.contracts import ExecutionContext, AgentError
from navowork_agent.runtime.agent import build_graph, configured_model
from navowork_agent.tools.service import ToolService
from .agent_files import HostAdapter
from .core import create_item, decode, encode, items, uid
from .db import SessionLocal
from .models import Case, Job, Run, WorkItem, now


def execute_file_work(item_id, generation, *, model=None):
    with SessionLocal() as db:
        work = db.get(WorkItem, item_id)
        run = db.get(Run, work.run_id)
        job = db.get(Job, run.job_id)
        payload = decode(job.payload)
        context = ExecutionContext(case_id=run.case_id, job_id=job.id, run_id=run.id, generation=generation)
        user_id, goal, resume = payload["createdBy"], run.instruction, payload.get("resume")
    adapter = HostAdapter(context, user_id, item_id)
    selected_model = model or configured_model()
    if selected_model is None:
        result = {"status": "error", "code": "MODEL_NOT_CONFIGURED", "live_executed": False,
                  "summary": "真实 Agent 未执行：宿主未配置模型。"}
    else:
        checkpoint_path = Path(os.getenv("FILE_GRAPH_CHECKPOINT_DB", "./data/file-agent-checkpoints.sqlite3"))
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        with SqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
            saver.setup()
            run_agent = build_graph(ToolService(adapter), selected_model, saver, max_tools=40, live_model=model is None)
            result = run_agent(resume=resume) if resume else run_agent(goal=goal)
    finish_file_work(adapter, result)
    return result


def finish_file_work(adapter, result):
    """Only project already-committed tool results; never regenerate artifacts here."""
    with SessionLocal() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        case = adapter._authorize(db, True)
        c = adapter.context()
        work, run, job = db.get(WorkItem, adapter.work_item_id), db.get(Run, c.run_id), db.get(Job, c.job_id)
        payload = decode(run.payload)
        payload["agentVerification"] = {"liveExecuted": result.get("live_executed", False), "mode": result.get("verification_mode", "model_not_run")}
        payload["agentOutputs"] = result.get("outputs", [])
        payload["agentArtifacts"] = result.get("artifacts", [])
        export_rows = [decode(row.payload) for row in items(db, "export", case_id=case.id)]
        payload["fileOutputs"] = []
        for file in result.get("outputs", []):
            export = next((v for v in export_rows if v.get("blobId") == file["file_id"]), None)
            if export is None:
                eid = uid("export")
                export = {"exportId": eid, "caseId": case.id, "blobId": file["file_id"], "status": "ready", "mode": "draft",
                    "downloadUrl": f"/api/v1/workspaces/{case.workspace_id}/exports/{eid}/download", "createdAt": now()}
                create_item(db, "export", export, case_id=case.id, item_id=eid)
            payload["fileOutputs"].append({**file, "downloadUrl": export["downloadUrl"]})
        job_data = decode(job.payload)
        job_data.pop("resume", None)
        job.payload = encode(job_data)
        status = result["status"]
        if status == "needs_info":
            questions = [{"id": q["question_id"], "question": q["prompt"], "field": ", ".join(q["missing_fields"]),
                          "missingFields": q["missing_fields"], "affectedArtifacts": q["affected_artifacts"]} for q in result.get("questions", [])]
            payload["clarification"] = {"questions": questions}
            run.status, job.status, work.status = "needs_input", "needs_input", "waiting"
            case.payload = encode({**decode(case.payload), "pendingRunId": run.id})
        elif status in ("error", "conflict", "blocked"):
            run.status, job.status, work.status = "failed", "failed", "done"
            run.error = encode({"code": result.get("code", "FILE_AGENT_INCOMPLETE"), "message": result["summary"]})
        elif not result.get("outputs"):
            # Analysis alone must not advance the effective business revision.
            run.status, job.status, work.status = "succeeded", "completed", "done"
        else:
            # Existing UI reads a Case Revision. Tie it to actual current agent artifacts and files.
            records = [decode(i.payload).get("agentRecord") for i in items(db, "artifact", case_id=case.id)]
            latest = {}
            for record in filter(None, records):
                ref = record["ref"]
                if ref["kind"] not in latest or ref["version"] > latest[ref["kind"]]["ref"]["version"]:
                    latest[ref["kind"]] = record
            spec, quotation = latest.get("spec"), latest.get("quotation")
            fields = spec["snapshot"]["fields"] if spec else {}
            value = lambda key: fields.get(key, {}).get("value")
            q = quotation.get("pricing", {}).get("quote") if quotation else None
            quote = None if not q else {"sku": value("product") or "待确认", "quantity": q["quantity"], "currency": "USD", "unitPriceMinor": int(Decimal(q["unit_usd"])*100),
                "goodsSubtotalMinor": int(Decimal(q["total_usd"])*100), "freightMinor": None, "taxMinor": None, "totalMinor": None,
                "quoteStatus": "draft", "sourceVersionIds": [i["file_id"] for i in quotation["ref"]["inputs"]],
                "timing": {"dispatchDays": None, "productionDays": None, "startsAfter": "待确认", "transitDays": None, "arrivalGuaranteed": False}}
            number = case.current_revision + 1
            rev = {"inquiryId": case.id, "number": number, "runId": run.id, "jobId": job.id,
                "requirements": {"requestedProduct": value("product"), "quantity": value("quantity"), "specification": value("material"), "certificationRequests": [],
                    "destination": value("named_place"), "requestedArrival": value("requested_arrival"), "customization": value("logo"),
                    "missingFields": [k for k, f in fields.items() if f.get("value") is None], "evidenceRefs": job_data.get("inputRefs", [])},
                "proposal": {"proposalId": uid("proposal"), "version": number, "requestedSku": value("product"), "selectedSku": None, "differences": [], "status": "requested"},
                "quote": quote, "replies": {"en-US": "", "es-MX": ""}, "risks": [], "checks": [{"label": "实际文件工具执行", "status": "warning", "message": "草稿待审核"}],
                "sourceRefs": job_data.get("sourceRefs", []), "assetRefs": [v["id"] for v in job_data.get("assetManifest", [])],
                "inputManifest": {"evidence": job_data.get("evidence", []), "assets": job_data.get("assetManifest", []), "canvas": job_data.get("canvasManifest", [])},
                "agentArtifactRefs": [r["ref"] for r in latest.values()], "agentFileRefs": result.get("outputs", []),
                "ruleSetVersion": "quote-v1", "createdAt": now(), "changeSummary": [result["summary"]]}
            create_item(db, "revision", rev, case_id=case.id, parent_id=case.id, version=number)
            case.current_revision, run.output_revision = number, number
            run.status, job.status, work.status = "succeeded", "needs_review", "done"
            payload.pop("clarification", None)
        case.active_run_id = None
        case.metadata_version += 1
        case.updated_at = now()
        run.payload = encode(payload)
        adapter._event(db, "run_state", result["summary"])
        create_item(db, "message", {"id": uid("msg"), "inquiryId": case.id, "role": "assistant", "runId": run.id,
            "text": result["summary"], "createdAt": now()}, case_id=case.id)
        db.commit()
