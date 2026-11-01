"""Native workbench authorization fences and honest partial tool outcomes."""
from io import BytesIO
from pathlib import Path

import pytest

BASE = "/api/v1/workspaces/ws_demo"
CASE = BASE + "/inquiries/inq_demo_bag"


def start_with_file(client):
    from docx import Document
    from test_workbench_v2 import _start
    document = Document()
    document.add_paragraph("Original source")
    stream = BytesIO()
    document.save(stream)
    uploaded = client.post(CASE + "/evidence", files={"file": ("source.docx", stream.getvalue(),
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert uploaded.status_code == 200, uploaded.text
    revision = client.get(CASE).json()["currentRevision"]
    toolbox, run_id, job_id, work_id, case_id = _start(client, CASE, "requirements", "Edit source document", revision)
    toolbox.node = "requirements"
    copied = toolbox.call("file_create_working_copy", {"file_id": uploaded.json()["id"]})
    assert copied["status"] == "needs_review", copied
    return toolbox, run_id, job_id, work_id, case_id, copied


def persisted_state(case_id, run_id):
    from app.core import decode, items
    from app.db import SessionLocal
    from app.models import Blob, Case, Run
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        return {"revision": db.get(Case, case_id).current_revision, "runStatus": run.status,
            "runPayload": decode(run.payload), "runError": run.error,
            "items": {row.id: row.payload for kind in ("artifact", "run_event", "agent_tool", "message", "revision")
                      for row in items(db, kind, case_id=case_id)},
            "files": {blob.id: Path(blob.path).read_bytes() for blob in db.query(Blob).filter(Blob.case_id == case_id)}}


@pytest.mark.parametrize("fault", ["expired", "revoked", "cross_case_job"])
def test_native_context_rejects_read_write_and_finalization_when_fenced(client, monkeypatch, tmp_path, fault):
    from app.core import decode, encode
    from app.db import SessionLocal
    from app.models import CaseAccess, Job, WorkItem
    from app.agent_runtime import execute_agent_work, _fail, _mark_waiting
    foreign = client.post(BASE + "/inquiries", json={"title": "Other project", "customer": "Other customer", "originalText": "Other case data"}).json()
    toolbox, run_id, job_id, work_id, case_id, copied = start_with_file(client)
    with SessionLocal() as db:
        if fault == "expired":
            db.get(WorkItem, work_id).lease_expires_at = "2000-01-01T00:00:00Z"
        elif fault == "revoked":
            db.delete(db.get(CaseAccess, (case_id, toolbox.user_id)))
        else:
            db.get(Job, job_id).case_id = foreign["id"]
        db.commit()
    before = persisted_state(case_id, run_id)
    assert before["files"] and copied["outputs"]
    for name, args in (("get_case_context", {}), ("update_requirements", {"fields": {"product": "Unauthorized edit"}})):
        result = toolbox.call(name, args)
        assert result["status"] == "blocked", result
        assert result["code"] in ("CASE_SCOPE", "STALE_CONTEXT")

    class NeverInvoked:
        def bind_tools(self, schemas):
            raise AssertionError("A fenced context must not reach a model")

    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "agent.sqlite3"))
    execute_agent_work(work_id, 1, model=NeverInvoked())
    _fail(work_id, 1, "INJECTED", "Should not finalize revoked context")
    _mark_waiting(work_id, 1, [{"id": "q", "question": "Should not be emitted"}], "Should not commit", True)
    assert persisted_state(case_id, run_id) == before


def test_toolbox_cannot_substitute_another_existing_job(client):
    from app.core import encode
    from app.db import SessionLocal
    from app.models import Job
    toolbox, run_id, job_id, work_id, case_id, _ = start_with_file(client)
    with SessionLocal() as db:
        other_job = Job(id="job_substituted", case_id=case_id, kind="confirm_requirements", goal="Other task",
            status="running", payload=encode({"createdBy": toolbox.user_id}))
        db.add(other_job)
        db.commit()
    before = persisted_state(case_id, run_id)
    toolbox.job_id = "job_substituted"
    result = toolbox.call("update_requirements", {"fields": {"product": "Wrong task write"}})
    assert result["status"] == "blocked" and result["code"] == "STALE_CONTEXT"
    assert persisted_state(case_id, run_id) == before


def test_unresolved_tool_error_marks_partial_and_retains_downloads(client, monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage
    from test_runtime import ScriptedModel, call
    from app.agent_runtime import execute_agent_work
    from app.core import decode
    from app.db import SessionLocal
    from app.models import Run
    toolbox, run_id, job_id, work_id, case_id, copied = start_with_file(client)
    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "agent.sqlite3"))
    fake = ScriptedModel([call("file_edit_file", {"artifact_id": copied["artifacts"][0]["artifact_id"], "baseline": 99,
        "file_id": copied["outputs"][0]["file_id"], "operations": [{"op": "append_paragraph", "text": "Wrong baseline"}]}, id="bad-edit"),
        AIMessage(content="All files changed successfully")])
    # Workbench schemas use file_ names rather than AgentKit's unprefixed read tool.
    fake.bind_tools = lambda schemas: fake
    execute_agent_work(work_id, 1, model=fake)
    view = client.get(BASE + "/runs/" + run_id).json()
    assert view["status"] == "failed" and view["error"]["code"] == "TOOL_EXECUTION_INCOMPLETE", view
    assert view["fileOutputs"]
    assert all(client.get(file["downloadUrl"]).content.startswith(b"PK") for file in view["fileOutputs"])
    with SessionLocal() as db:
        payload = decode(db.get(Run, run_id).payload)
        assert payload["executionOutcome"] == "partial" and payload["failedTools"][0]["tool"] == "file_edit_file"
    messages = client.get(CASE + "/messages").json()["items"]
    assert "All files changed successfully" not in messages[-1]["text"]


def test_recovered_tool_branch_can_finish_successfully(client, monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage
    from test_runtime import ScriptedModel, call
    from app.agent_runtime import execute_agent_work, _unresolved_failures, _operation_key
    toolbox, run_id, job_id, work_id, case_id, copied = start_with_file(client)
    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "agent.sqlite3"))
    args = {"artifact_id": copied["artifacts"][0]["artifact_id"], "file_id": copied["outputs"][0]["file_id"],
        "operations": [{"op": "append_paragraph", "text": "Recovered review note"}]}
    fake = ScriptedModel([call("file_edit_file", {**args, "baseline": 99}, id="bad"),
        call("file_edit_file", {**args, "baseline": 1}, id="retry"), AIMessage(content="Saved new working version")])
    fake.bind_tools = lambda schemas: fake
    execute_agent_work(work_id, 1, model=fake)
    view = client.get(BASE + "/runs/" + run_id).json()
    assert view["status"] == "succeeded", view
    assert len(view["fileOutputs"]) == 2
    # Recovery of a different output format cannot erase the failed export.
    failed = {"_operation_key": _operation_key("export_artifact", {"kind": "quotation", "format": "xlsx"}), "status": "error"}
    other_format = {"_operation_key": _operation_key("export_artifact", {"kind": "quotation", "format": "pdf"}), "status": "success"}
    assert _unresolved_failures([failed, other_format]) == [failed]


def test_native_missing_pricing_basis_pauses_checkpoint_and_resumes(client, monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage
    from test_runtime import ScriptedModel, call
    from test_workbench_v2 import _start
    from app.agent_runtime import execute_agent_work
    from app.core import decode
    from app.db import SessionLocal
    from app.models import Case, Job, Run, WorkItem

    created = client.post(BASE + "/inquiries", json={"title": "Pricing confirmation", "customer": "Buyer",
        "originalText": "Please quote 3000 bags."}).json()
    path = BASE + "/inquiries/" + created["id"]
    source = client.post(path + "/evidence", json={"sourceRole": "supplier_quote", "title": "Factory quote",
        "text": "Base CNY 44, packaging CNY 2, local CNY 4, MOQ 1000, lead 28 days."}).json()
    toolbox, run_id, job_id, work_id, case_id = _start(client, path, "costing", "登记报价并核价")
    offer = toolbox.call("record_supplier_quote", {"supplier": "Factory A", "evidence_id": source["id"],
        "base_cny": "44", "packaging_cny": "2", "local_cny": "4", "moq": 1000, "lead_days": 28})
    assert offer["status"] == "success", offer
    args = {"supplier_offer_id": offer["data"]["offerId"], "quantity": 3000, "exchange_rate": "7.2", "margin": "0.2"}
    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "agent.sqlite3"))
    fake = ScriptedModel([call("calculate_cost", args, id="missing-basis"), AIMessage(content="报价已计算")])
    fake.bind_tools = lambda schemas: fake
    execute_agent_work(work_id, 1, model=fake)
    paused = client.get(BASE + "/runs/" + run_id).json()
    assert paused["status"] == "needs_input", paused
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        questions = decode(run.payload)["clarification"]["questions"]
        revision = run.base_revision
        assert questions and "汇率" in questions[0]["question"]
        assert db.get(WorkItem, work_id).status == "waiting"
    # A real host resume must continue the interrupted graph, preserving the
    # registered supplier and accepting only the user's explicit pricing facts.
    response = client.post(path + "/runs", json={"replyToRunId": run_id, "baseRevision": revision,
        "answers": [{"questionId": question["id"], "value": "汇率 7.2、毛利率 20%、数量 3000"} for question in questions]})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        run, job, work = db.get(Run, run_id), db.get(Job, job_id), db.get(WorkItem, work_id)
        run.status = job.status = work.status = "running"
        work.lease_generation = 2
        work.lease_expires_at = "2999-01-01T00:00:00Z"
        db.get(Case, case_id).active_run_id = run_id
        db.commit()
    resumed = ScriptedModel([call("calculate_cost", args, id="confirmed-basis"), AIMessage(content="报价已按确认依据计算")])
    resumed.bind_tools = lambda schemas: resumed
    execute_agent_work(work_id, 2, model=resumed)
    final = client.get(BASE + "/runs/" + run_id).json()
    assert final["status"] == "succeeded", final
    artifacts = client.get(path + "/workbench").json()["artifacts"]
    assert artifacts["cost"]["content"]["unitPriceUsd"] == "8.69"
    assert artifacts["cost"]["content"]["supplierOfferId"] == offer["data"]["offerId"]
    assert artifacts["comparison"]["content"]["supplierOffers"][0]["supplier"] == "Factory A"


def test_answered_request_info_does_not_remain_an_unresolved_tool(client, monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage
    from test_runtime import ScriptedModel, call
    from app.agent_runtime import execute_agent_work
    from app.core import decode
    from app.db import SessionLocal
    from app.models import Job, Run, WorkItem
    _, run_id, job_id, work_id, _, _ = start_with_file(client)
    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "agent.sqlite3"))
    fake = ScriptedModel([call("request_info", {"fields": ["包装"], "reason": "需要明确包装后再编辑"}, id="question")])
    fake.bind_tools = lambda schemas: fake
    execute_agent_work(work_id, 1, model=fake)
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == "needs_input"
        questions = decode(run.payload)["clarification"]["questions"]
        revision = run.base_revision
    resumed = client.post(CASE + "/runs", json={"replyToRunId": run_id, "baseRevision": revision,
        "answers": [{"questionId": question["id"], "value": "包装改为 recycled polybag"} for question in questions]})
    assert resumed.status_code == 200, resumed.text
    with SessionLocal() as db:
        run, job, work = db.get(Run, run_id), db.get(Job, job_id), db.get(WorkItem, work_id)
        run.status = job.status = work.status = "running"
        work.lease_generation = 2
        work.lease_expires_at = "2999-01-01T00:00:00Z"
        db.commit()
    completed = ScriptedModel([call("update_requirements", {"fields": {"packaging": "recycled polybag"}}, id="save"),
        AIMessage(content="包装已更新")])
    completed.bind_tools = lambda schemas: completed
    execute_agent_work(work_id, 2, model=completed)
    view = client.get(BASE + "/runs/" + run_id).json()
    assert view["status"] == "succeeded", view
    assert view["fileOutputs"]
    assert client.get(CASE + "/workbench").json()["artifacts"]["spec"]["content"]["fields"]["packaging"] == "recycled polybag"
