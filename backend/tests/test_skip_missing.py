from langchain_core.messages import AIMessage
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent-kit/tests"))

from app.core import decode, encode
from app.db import SessionLocal
from app.models import Case, Job, Run, WorkItem
from test_runtime import ScriptedModel, call
from test_workbench_v2 import _start

BASE = "/api/v1/workspaces/ws_demo"


def model(steps):
    scripted = ScriptedModel(steps)
    scripted.bind_tools = lambda schemas: scripted
    return scripted


def claim_resume(run_id, job_id, work_id):
    with SessionLocal() as db:
        run, job, work = db.get(Run, run_id), db.get(Job, job_id), db.get(WorkItem, work_id)
        run.status = job.status = work.status = "running"
        work.lease_generation = 2
        work.lease_expires_at = "2999-01-01T00:00:00Z"
        db.commit()


def test_skip_resumes_without_reasking_and_preserves_unresolved_node_warning(client, monkeypatch, tmp_path):
    from app.agent_runtime import execute_agent_work
    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "skip.sqlite3"))
    inquiry = client.post(BASE + "/inquiries", json={"title": "Skip dimensions", "customer": "Buyer", "originalText": "Please quote backpacks."}).json()
    path = BASE + "/inquiries/" + inquiry["id"]
    _, run_id, job_id, work_id, _ = _start(client, path, "requirements", "整理背包需求")
    execute_agent_work(work_id, 1, model=model([
        call("update_requirements", {"fields": {"product": "backpack"}}, id="save"),
        call("request_info", {"fields": ["背包尺寸"], "reason": "尺寸未给"}, id="ask"),
    ]))
    paused = client.get(BASE + "/runs/" + run_id).json()
    assert paused["status"] == "needs_input"
    warning = client.get(path).json()["nodeWarnings"]["requirements"]
    assert warning[0]["skipped"] is False
    response = client.post(path + "/runs", json={"replyToRunId": run_id, "baseRevision": paused["baseRevision"], "skipMissing": True})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"
    assert response.json()["skippedQuestions"] == ["请补充背包尺寸。"]
    claim_resume(run_id, job_id, work_id)
    execute_agent_work(work_id, 2, model=model([
        # A model asking again must not trap the user in the same pause.
        call("request_info", {"fields": ["背包尺寸"]}, id="ask-again"),
        AIMessage(content="已保存可完成的规格草稿，尺寸仍待确认。"),
    ]))
    finished = client.get(BASE + "/runs/" + run_id).json()
    assert finished["status"] == "succeeded", finished
    view = client.get(path + "/workbench").json()
    assert view["case"].get("pendingRunId") is None and view["case"]["activeRunId"] is None
    assert view["case"]["nodeWarnings"]["requirements"][0]["skipped"] is True
    assert view["artifacts"]["spec"]["content"]["fields"]["dimensions"] is None
    assert not {"cost", "quotation"}.intersection(view["artifacts"])
    assert view["approvals"] == []

    # A later explicit check with actual information can clear the old skipped warning.
    _, _, _, next_work, _ = _start(client, path, "requirements", "客户补充尺寸30x45x15cm，请重新检查", view["case"]["currentRevision"])
    execute_agent_work(next_work, 1, model=model([
        call("update_requirements", {"fields": {"dimensions": "30x45x15cm"}}, id="fill"), AIMessage(content="尺寸已补齐。"),
    ]))
    remaining = client.get(path).json()["nodeWarnings"].get("requirements", [])
    assert not any(warning.get("field") == "dimensions" or warning["question"] == "请补充背包尺寸。" for warning in remaining)
    assert any(warning.get("field") == "fabric" for warning in remaining)


def test_skip_rejects_stale_revision_and_preserves_pending_run(client, monkeypatch, tmp_path):
    from app.agent_runtime import execute_agent_work
    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "stale.sqlite3"))
    path = BASE + "/inquiries/inq_demo_bag"
    _, run_id, _, work_id, _ = _start(client, path, "requirements", "整理需求")
    execute_agent_work(work_id, 1, model=model([call("request_info", {"fields": ["尺寸"]}, id="ask")]))
    response = client.post(path + "/runs", json={"replyToRunId": run_id, "baseRevision": 99, "skipMissing": True})
    assert response.status_code == 409
    assert client.get(path).json()["pendingRunId"] == run_id
    assert not client.get(BASE + "/runs/" + run_id).json()["skippedQuestions"]


def test_legacy_waiting_task_can_be_skipped_without_inventing_outputs(client):
    path = BASE + "/inquiries/inq_demo_bag"
    created = client.post(path + "/runs", json={"baseRevision": 0, "instruction": "整理需求"}).json()
    with SessionLocal() as db:
        run = db.get(Run, created["id"])
        run.status = "needs_input"
        run.payload = encode({"clarification": {"questions": [{"id": "size", "question": "请补充尺寸"}]}})
        case = db.get(Case, run.case_id)
        case.active_run_id = None
        case.payload = encode({**decode(case.payload), "pendingRunId": run.id})
        db.get(Job, run.job_id).status = "needs_input"
        db.query(WorkItem).filter(WorkItem.run_id == run.id).one().status = "waiting"
        db.commit()
    response = client.post(path + "/runs", json={"baseRevision": 0, "replyToRunId": created["id"], "skipMissing": True})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "succeeded"
    assert response.json().get("outputRevision") is None
    assert client.get(path).json().get("pendingRunId") is None
    assert client.get(path).json()["nodeWarnings"]["requirements"][0]["skipped"] is True


def test_generate_next_node_defers_waiting_task_and_persists_quote(client, monkeypatch, tmp_path):
    from app.agent_runtime import execute_agent_work
    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "next-node.sqlite3"))
    case = client.post(BASE + "/inquiries", json={"demoScenarioId": "us-tote"}).json()
    path = BASE + "/inquiries/" + case["id"]
    source = client.get(path + "/evidence").json()["items"]
    supplier = next(e for e in source if "工厂 A" in e["title"])
    offer = client.post(path + "/supplier-offers", json={"supplier": "Factory A", "evidenceSourceId": supplier["id"],
        "baseCny": "18", "packagingCny": "1", "localCny": "2", "moq": 500, "leadDays": 21}).json()
    _, waiting_id, _, work_id, _ = _start(client, path, "requirements", "整理需求")
    execute_agent_work(work_id, 1, model=model([
        call("update_requirements", {"fields": {"product": "cotton tote", "quantity": "5000"}}, id="spec"),
        call("request_info", {"fields": ["印刷位置"]}, id="ask"),
    ]))
    revision = client.get(path).json()["currentRevision"]
    body = {"node": "costing", "instruction": "生成报价", "baseRevision": revision, "skipPendingRunId": waiting_id}
    for invalid in ({"baseRevision": revision - 1}, {"skipPendingRunId": "another-run"}, {"node": "unknown"}):
        response = client.post(path + "/workbench/agent", json={**body, **invalid})
        assert response.status_code >= 400
        assert client.get(path).json()["pendingRunId"] == waiting_id
        assert client.get(BASE + "/runs/" + waiting_id).json()["status"] == "needs_input"

    created = client.post(path + "/workbench/agent", json=body)
    assert created.status_code == 200, created.text
    next_run = created.json()
    old = client.get(BASE + "/runs/" + waiting_id).json()
    assert old["status"] == "succeeded" and old["skippedQuestions"]
    assert client.get(path).json().get("pendingRunId") is None
    with SessionLocal() as db:
        run = db.get(Run, next_run["id"])
        work = db.query(WorkItem).filter(WorkItem.run_id == run.id).one()
        next_work, next_job = work.id, run.job_id
    claim_resume(next_run["id"], next_job, next_work)
    execute_agent_work(next_work, 2, model=model([
        call("request_info", {"fields": ["印刷位置"]}, id="repeat-upstream-gap"),
        call("calculate_cost", {"supplier_offer_id": offer["id"], "quantity": 5000, "exchange_rate": "7.2", "margin": "0.2"}, id="cost"),
        call("update_quotation", {"incoterm": "FOB", "named_place": "Ningbo", "payment_terms": "30/70", "valid_until": "2999-12-31", "moq": 500, "sample_time": "7 days", "production_time": "21 days", "exclusions": ["freight"]}, id="quote"),
        AIMessage(content="报价草稿已保存，印刷位置仍待确认。"),
    ]))
    finished = client.get(BASE + "/runs/" + next_run["id"]).json()
    assert finished["status"] == "succeeded", finished
    view = client.get(path + "/workbench").json()
    assert view["artifacts"]["quotation"]["content"]["unitPriceUsd"] == "3.65"
    assert view["case"]["nodeWarnings"]["requirements"][0]["skipped"] is True
    assert view["case"]["nodeWarnings"]["costing"][0]["skipped"] is True
    revisions = client.get(path + "/revisions").json()["items"]
    assert revisions[-1]["quote"]["unitPriceMinor"] == 365
    assert view["approvals"] == []
