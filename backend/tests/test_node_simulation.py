import pytest

from app.core import decode, items, item_view
from app.db import SessionLocal
from app.demo_scenarios import SCENARIOS
from app.models import Case, Job, Run
from app.node_simulation import PHASES
from app.worker import work_once

BASE = "/api/v1/workspaces/ws_demo"


@pytest.fixture
def no_provider(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Node simulation reached a real Agent executor")
    monkeypatch.setattr("app.agent_runtime.execute_agent_work", forbidden)
    monkeypatch.setattr("app.file_worker.execute_file_work", forbidden)
    monkeypatch.setattr("app.node_simulation.PHASE_SECONDS", 0)


@pytest.mark.parametrize("scenario", [s["id"] for s in SCENARIOS] + [None])
def test_mock_nodes_persist_complete_sequence_without_a_model(client, no_provider, scenario):
    body = {"demoScenarioId": scenario} if scenario else {"title": "Custom demo", "customer": "Buyer", "originalText": "Please quote bags."}
    case = client.post(BASE + "/inquiries", json=body).json()
    path = BASE + "/inquiries/" + case["id"]
    for number, node in enumerate(("inquiry", "requirements", "costing", "risks", "reply", "sample", "order", "production")):
        response = client.post(path + "/workbench/simulations", json={"node": node, "baseRevision": number, "instruction": "依据现有资料生成"})
        assert response.status_code == 200, response.text
        run_id = response.json()["id"]
        assert response.json()["executionMode"] == "simulation"
        assert work_once(None)
        run = client.get(BASE + "/runs/" + run_id).json()
        assert run["status"] == "succeeded", run
        assert run["completedPhases"] == list(PHASES)
        assert run["agentVerification"] == {"liveExecuted": False, "mode": "local_mock", "modelApiCalled": False}
        with SessionLocal() as db:
            events = sorted([item_view(row) for row in items(db, "run_event", case_id=case["id"]) if row.parent_id == run_id], key=lambda e: e["seq"])
            assert [e["payload"]["phase"] for e in events if e["type"] == "run.running"] == list(PHASES)
        revisions = client.get(path + "/revisions").json()["items"]
        assert revisions[-1]["number"] == number + 1
        if node == "costing":
            assert revisions[-1]["quote"]["unitPriceMinor"] > 0
        if node in ("reply", "sample", "order", "production"):
            assert "Thank you" in revisions[-1]["replies"]["en-US"]
    view = client.get(path + "/workbench").json()
    assert view["approvals"] == []
    assert view["case"].get("pendingRunId") is None
    assert all(a["content"]["simulation"] for a in view["artifacts"].values())


def test_chat_stays_live_and_cancelled_simulation_cannot_save(client, no_provider):
    case = client.post(BASE + "/inquiries", json={"demoScenarioId": "de-backpack"}).json()
    path = BASE + "/inquiries/" + case["id"]
    chat = client.post(path + "/workbench/agent", json={"instruction": "请分析客户需求", "baseRevision": 0}).json()
    assert chat["executionMode"] == "live"
    with SessionLocal() as db:
        job = db.get(Job, db.get(Run, chat["id"]).job_id)
        assert decode(job.payload)["agentMode"] is True
        assert not decode(job.payload).get("simulationNode")
    client.post(BASE + "/runs/" + chat["id"] + "/cancel")
    mock = client.post(path + "/workbench/simulations", json={"node": "requirements", "instruction": "生成", "baseRevision": 0}).json()
    client.post(BASE + "/runs/" + mock["id"] + "/cancel")
    assert not work_once(None)
    assert client.get(path).json()["currentRevision"] == 0


def test_cancelling_during_simulated_progress_keeps_outputs_empty(client, no_provider, monkeypatch):
    case = client.post(BASE + "/inquiries", json={"demoScenarioId": "us-tote"}).json()
    path = BASE + "/inquiries/" + case["id"]
    run = client.post(path + "/workbench/simulations", json={"node": "requirements", "instruction": "生成", "baseRevision": 0}).json()
    monkeypatch.setattr("app.node_simulation.time.sleep", lambda _: client.post(BASE + "/runs/" + run["id"] + "/cancel"))
    assert work_once(None)
    assert client.get(BASE + "/runs/" + run["id"]).json()["status"] == "cancelled"
    assert client.get(path + "/workbench").json()["artifacts"] == {}
    assert client.get(path).json()["currentRevision"] == 0
