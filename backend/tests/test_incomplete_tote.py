from langchain_core.messages import AIMessage

from app.agent_runtime import execute_agent_work
from test_skip_missing import model, call
from test_node_simulation import no_provider
from test_inquiry_assets import library
from app.worker import work_once
from test_workbench_v2 import _start

BASE = "/api/v1/workspaces/ws_demo"


def create_incomplete(client):
    result = client.post(BASE + "/inquiries", json={
        "demoScenarioId": "us-tote", "demoDataScope": "incomplete"
    })
    assert result.status_code == 200, result.text
    case = result.json()
    return case, BASE + "/inquiries/" + case["id"]


def test_incomplete_tote_has_no_hidden_specs_or_prices(client):
    catalog = client.get(BASE + "/inquiries/demo-scenarios").json()["items"]
    assert next(row for row in catalog if row["id"] == "us-tote")["dataScope"] == "incomplete"
    case, path = create_incomplete(client)
    view = client.get(path + "/workbench").json()
    assert case["demoDataScope"] == "incomplete"
    assert not case.get("nodeWarnings")
    assert view["artifacts"] == {}
    assert len(view["evidence"]) == 2
    assert not [row for row in view["knowledge"] if row.get("caseId") == case["id"]]
    for row in view["evidence"]:
        assert row["sourceRole"] == "customer_request"
        assert all(value not in row["text"] for value in ("12 oz", "38 x 42", "120 x 80", "baseCny"))


def test_incomplete_mock_nodes_finish_without_provider_and_keep_warnings(client, no_provider, monkeypatch):
    # A configured provider must not change this scenario's local-only behavior.
    monkeypatch.setenv("MODEL_API_KEY", "test-do-not-use")
    case, path = create_incomplete(client)
    nodes = ("inquiry", "requirements", "competitor", "design", "costing", "risks", "reply", "sample", "order", "production")
    for revision, node in enumerate(nodes):
        response = client.post(path + "/workbench/simulations", json={
            "node": node, "baseRevision": revision, "instruction": "生成缺项演示草稿"
        })
        assert response.status_code == 200, response.text
        run_id = response.json()["id"]
        assert response.json()["executionMode"] == "simulation"
        assert work_once(None)
        run = client.get(BASE + "/runs/" + run_id).json()
        assert run["status"] == "succeeded", run
        assert run["agentVerification"] == {"liveExecuted": False, "mode": "local_mock", "modelApiCalled": False}
        view = client.get(path + "/workbench").json()
        warnings = view["case"]["nodeWarnings"][node]
        assert len(warnings) == 5
        assert all(w["source"] == "local_mock" and w["runId"] == run_id for w in warnings)
        fields = view["artifacts"]["spec"]["content"]["fields"]
        assert fields["quantity"] == "5000"
        assert all(fields[key] is None for key in ("dimensions", "fabric", "logo", "structure", "delivery", "incoterm"))
        assert not view["approvals"]
        assert not view["case"].get("pendingRunId")
    assert not view["artifacts"]["quotation"]["content"].get("unitPriceUsd")
    assert not view["artifacts"]["production"]["content"].get("productionDays")
    assert view["artifacts"]["concept_image"]["content"]["imageApiCalled"] is False
    assert "21 days" not in view["artifacts"]["customer_reply"]["content"]["replies"]["en-US"]
    own_assets = library(client, case["id"])
    assert any(a["sourceKind"] == "original" for a in own_assets)
    assert {view["artifacts"][kind]["itemId"] for kind in ("spec", "bom")}.issubset({a["sourceId"] for a in own_assets})


def test_repeated_mock_does_not_duplicate_warnings_and_chat_stays_live(client, no_provider):
    _, path = create_incomplete(client)
    for revision in range(2):
        response = client.post(path + "/workbench/simulations", json={
            "node": "requirements", "baseRevision": revision, "instruction": "分析这个询盘的信息缺口"
        })
        assert response.status_code == 200, response.text
        assert response.json()["executionMode"] == "simulation"
        assert work_once(None)
        view = client.get(path + "/workbench").json()
        assert len(view["case"]["nodeWarnings"]["requirements"]) == 5
        assert view["case"]["currentRevision"] == revision + 1

    chat = client.post(path + "/workbench/agent", json={"baseRevision": 2, "instruction": "分析这个询盘"}).json()
    assert chat["executionMode"] == "live"
    assert client.post(BASE + "/runs/" + chat["id"] + "/cancel").status_code == 200


def test_completed_draft_keeps_validation_warnings_without_agent_question(client, monkeypatch, tmp_path):
    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "no-question.sqlite3"))
    case = client.post(BASE + "/inquiries", json={"title": "Partial draft", "customer": "Buyer", "originalText": "Please quote canvas bags."}).json()
    path = BASE + "/inquiries/" + case["id"]
    _, run_id, _, work_id, _ = _start(client, path, "requirements", "整理已知内容")
    execute_agent_work(work_id, 1, model=model([
        call("update_requirements", {"fields": {"product": "canvas tote bag", "quantity": "5000"}}, id="save"),
        AIMessage(content="草稿已保存。"),
    ]))
    assert client.get(BASE + "/runs/" + run_id).json()["status"] == "succeeded"
    assert {w["field"] for w in client.get(path).json()["nodeWarnings"]["requirements"]} >= {"dimensions", "fabric", "logo"}
