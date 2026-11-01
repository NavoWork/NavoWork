from decimal import Decimal
import os

import pytest

from app.core import decode
from app.db import SessionLocal
from app.demo_scenarios import SCENARIOS, scenario_inputs
from app.models import Job, Run
from test_workbench_v2 import _finish, _start

BASE = "/api/v1/workspaces/ws_demo/inquiries"


def _create(client, scenario_id="de-backpack", key=None, scope="full"):
    result = client.post(BASE, json={"demoScenarioId": scenario_id, "demoDataScope": scope}, headers={"Idempotency-Key": key} if key else {})
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize("scenario_id", [s["id"] for s in SCENARIOS])
def test_default_demo_has_only_inputs_and_free_conversation(client, scenario_id):
    response = client.post(BASE, json={"demoScenarioId": scenario_id})
    assert response.status_code == 200, response.text
    case = response.json()
    path = BASE + '/' + case['id']
    view = client.get(path + '/workbench').json()
    assert case['demoDataScope'] == 'reference'
    assert view['artifacts'] == {}
    assert len(view['evidence']) == 4
    assert {e['sourceRole'] for e in view['evidence']} == {'customer_request', 'supplier_quote'}
    assert len([k for k in view['knowledge'] if k.get('caseId') == case['id']]) == 2
    assert client.get(path + '/demo-guide').json()['kind'] == 'chat'
    dispatched = client.post(path + '/workbench/agent', json={'instruction': '请按询盘生成产品设计图', 'baseRevision': 0})
    assert dispatched.status_code == 200, dispatched.text
    with SessionLocal() as db:
        run = db.get(Run, dispatched.json()['id'])
        job = db.get(Job, run.job_id)
        assert decode(job.payload)['agentNode'] is None
        assert job.graph_version == 'workbench-v2'


def test_demo_creation_is_fresh_idempotent_and_scoped(client, other_client):
    assert len(client.get(BASE + "/demo-scenarios").json()["items"]) == 5
    first = _create(client, key="demo-create")
    assert _create(client, key="demo-create")["id"] == first["id"]
    second = _create(client)
    assert first["id"] != second["id"]
    assert set(first["demoEvidence"].values()).isdisjoint(second["demoEvidence"].values())
    path = BASE + "/" + first["id"]
    view = client.get(path + "/workbench").json()
    assert view["artifacts"] == {}
    assert len(view["evidence"]) == 10
    assert len([k for k in view["knowledge"] if k.get("caseId") == first["id"]]) == 3
    assert first["customerContext"]["simulation"] is True
    assert client.get('/api/v1/workspaces/ws_demo/library/documents').status_code == 200
    assert client.get('/api/v1/workspaces/ws_demo/knowledge').status_code == 200
    assert client.get(path + "/demo-guide").json()["node"] == "inquiry"
    assert other_client.get(path + "/demo-guide").status_code in (403, 404)
    assert client.post(BASE, json={"demoScenarioId": "unknown"}).status_code == 400


def test_suggested_chat_prompt_dispatches_real_agent(client):
    case = _create(client)
    path = BASE + "/" + case["id"]
    guide = client.get(path + "/demo-guide").json()
    response = client.post(path + "/workbench/agent", json={"instruction": guide["prompt"], "baseRevision": 0})
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        run = db.get(Run, response.json()["id"])
        job = db.get(Job, run.job_id)
        assert job.graph_version == "workbench-v2"
        assert decode(job.payload)["agentNode"] == "inquiry"


@pytest.mark.parametrize("scenario_id", [s["id"] for s in SCENARIOS])
def test_all_demo_inputs_pass_full_business_gates(client, scenario_id):
    """Exercise real domain tools and all human gates; no model or canned outputs."""
    case = _create(client, scenario_id)
    path = BASE + "/" + case["id"]
    s = scenario_inputs(scenario_id)
    refs = case["demoEvidence"]
    visited = []
    for _ in range(16):
        guide = client.get(path + "/demo-guide").json()
        if guide["kind"] == "done":
            break
        if guide["kind"] == "approval":
            response = client.post(path + "/workbench/approvals", json={**guide, "verificationBasis": "人工核对模拟凭据", "note": "演示确认"})
            assert response.status_code == 200, response.text
            continue
        node = guide["node"]
        visited.append(node)
        view = client.get(path + "/workbench").json()
        toolbox, run_id, job_id, work_id, _ = _start(client, path, node, guide["prompt"], revision=view["case"]["currentRevision"])

        def call(name, args):
            result = toolbox.call(name, args)
            assert result["status"] == "success", (name, result)
            return result["data"]

        ctx = call("get_case_context", {})
        assert len(ctx["projectKnowledge"]) == 3
        if node == 'inquiry':
            assert toolbox.call('file_list_context', {})['status'] == 'success'
        if node == "inquiry":
            call("update_customer_profile", {"company": s["customer"], "country": s["country"], "channel": "email", "email": case["customerContext"]["email"], "summary": "模拟客户询盘"})
        elif node == "requirements":
            call("update_requirements", {"fields": s["fields"], "source_refs": [{"evidenceId": refs["spec"], "quote": s["fields"]["fabric"]}]})
            call("update_bom", {"rows": [{"category": "material", "item": s["fabric"], "quantityPerPiece": "1", "unit": "set"}]})
        elif node == "costing":
            offers = []
            for i, label in enumerate(("A", "B")):
                offers.append(call("record_supplier_quote", {"supplier": f"Demo Factory {label}", "evidence_id": refs[f"supplier{label}"], "base_cny": str(Decimal(s["base"]) + 3*i), "packaging_cny": s["packaging"], "local_cny": s["local"], "moq": 500, "lead_days": s["days"], "valid_until": s["validUntil"]}))
            cost = call("calculate_cost", {"supplier_offer_id": offers[0]["offerId"], "quantity": s["quantity"], "exchange_rate": "7.20", "margin": "0.20"})
            assert cost["unitPriceUsd"] == s["order"]["po"]["unitPriceUsd"]
            call("update_quotation", {"product": s["product"], "quantity": s["quantity"], "incoterm": "FOB", "incoterms_version": "2020", "named_place": "Ningbo", "payment_terms": s["fields"]["paymentTerms"], "valid_until": s["validUntil"], "moq": 500, "sample_time": "7 days", "production_time": s["fields"]["delivery"], "production_days": s["days"], "exclusions": ["freight", "insurance"]})
        elif node == "sample":
            call("record_sample", {"type": "pre_production", "sample_ref": s["sample"]["sampleRef"], "spec_version_id": view["artifacts"]["spec"]["itemId"], "checks": s["sample"]["checks"], "feedback": s["sample"]["feedback"]})
        elif node == "order":
            call("record_order", {"po": s["order"]["po"], "pi": s["order"]["pi"], "payment_schedule": s["order"]["paymentSchedule"]})
        elif node == "production":
            call("prepare_production", {"qc_standard": s["fields"]["inspection"]})
        _finish(run_id, job_id, work_id, node)
    assert guide["kind"] == "done", guide
    assert visited == ["inquiry", "requirements", "costing", "sample", "order", "production"]
    view = client.get(path + "/workbench").json()
    assert view["gate"]["status"] == "passed"
    assert view["case"]["currentRevision"] == 6
    assert view["artifacts"]["quotation"]["content"]["totalUsd"] == s["computed"]["totalUsd"]


@pytest.mark.skipif(os.getenv("NAVOWORK_LIVE_DEMO") != "1", reason="opt-in real provider acceptance")
def test_demo_with_live_model(client, tmp_path, monkeypatch):
    from app.agent_runtime import execute_agent_work
    monkeypatch.setenv("WORKBENCH_AGENT_CHECKPOINT_DB", str(tmp_path / "graph.sqlite3"))
    case = _create(client)
    path = BASE + "/" + case["id"]
    visited = []
    for _ in range(16):
        guide = client.get(path + "/demo-guide").json()
        if guide["kind"] == "done":
            break
        if guide["kind"] == "approval":
            response = client.post(path + "/workbench/approvals", json={**guide, "verificationBasis": "人工核对模拟凭据（验收测试）", "note": "演示验收"})
            assert response.status_code == 200, response.text
            print(f"Confirmed: {guide['scope']}", flush=True)
            continue
        node = guide["node"]
        assert node not in visited, f"Stage did not advance: {node}"
        visited.append(node)
        view = client.get(path + "/workbench").json()
        _, run_id, _, work_id, _ = _start(client, path, node, guide["prompt"], revision=view["case"]["currentRevision"])
        print(f"Real AI started: {node}", flush=True)
        execute_agent_work(work_id, 1)
        run = client.get(f"/api/v1/workspaces/ws_demo/runs/{run_id}").json()
        print(f"Real AI finished: {node} / {run['status']}", flush=True)
        assert run["status"] == "succeeded", {"status": run["status"], "error": run.get("error"), "questions": run.get("clarification")}
    assert guide["kind"] == "done"
    assert len(visited) == 6
    assert client.get(path + "/workbench/gate").json()["status"] == "passed"


@pytest.mark.skipif(os.getenv("NAVOWORK_LIVE_DEMO") != "1", reason="opt-in real provider acceptance")
def test_free_demo_chat_with_live_model(client, tmp_path, monkeypatch):
    from app.agent_runtime import execute_agent_work
    monkeypatch.setenv('WORKBENCH_AGENT_CHECKPOINT_DB', str(tmp_path / 'free-chat.sqlite3'))
    case = _create(client, scope='reference')
    path = BASE + '/' + case['id']
    prompts = [
        '请读取这条询盘的参考资料，整理需求规格和 BOM，再比较两家工厂的报价，按资料中的汇率、毛利率和数量核价，生成客户报价建议。只处理需求与报价。',
        '请把刚才的报价建议写成一封简短专业的英文客户回复，只输出邮件正文，不更新业务资料。',
    ]
    for index, prompt in enumerate(prompts):
        before = client.get(path).json()['currentRevision']
        _, run_id, _, work_id, _ = _start(client, path, None, prompt, revision=before)
        print(f'Live free conversation started: {index + 1}', flush=True)
        execute_agent_work(work_id, 1)
        run = client.get('/api/v1/workspaces/ws_demo/runs/' + run_id).json()
        assert run['status'] == 'succeeded', {'status': run['status'], 'error': run.get('error'), 'questions': run.get('clarification')}
        print(f'Live free conversation finished: {index + 1}', flush=True)
        if index == 0:
            view = client.get(path + '/workbench').json()
            assert {'spec', 'bom', 'cost', 'quotation'} <= set(view['artifacts'])
            assert view['artifacts']['quotation']['content']['unitPriceUsd'] == '8.69'
        else:
            assert client.get(path).json()['currentRevision'] == before
            messages = client.get(path + '/messages').json()['items']
            text = next(m['text'] for m in messages if m.get('runId') == run_id and m['role'] == 'assistant')
            assert '8.69' in text and len(text) > 80
