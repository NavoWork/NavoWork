from langchain_core.messages import AIMessage

BASE = "/api/v1/workspaces/ws_demo"
CASE = BASE + "/inquiries/inq_demo_bag"


class ScriptedModel:
    def __init__(self, batches):
        self.batches = iter(batches)

    def bind_tools(self, tools):
        assert any(t["function"]["name"] == "calculate_quote" for t in tools)
        return self

    def invoke(self, messages):
        calls = next(self.batches, None)
        return AIMessage(content="已完成当前节点。" if calls is None else "", tool_calls=calls or [])


def tc(name, args, ident):
    return {"name": name, "args": args, "id": ident, "type": "tool_call"}


def start(client, monkeypatch, batches, instruction="整理需求，不生成后续节点", revision=0):
    import app.business_agent as module
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "test-model")
    monkeypatch.setenv("AGENT_FILE_TOOLS", "0")
    original = getattr(module, "_test_original_execute", module.execute_business_work)
    monkeypatch.setattr(module, "_test_original_execute", original, raising=False)
    monkeypatch.setattr(module, "execute_business_work", lambda work, gen: original(work, gen, ScriptedModel(batches)))
    response = client.post(CASE + "/runs", json={"action": "analyze", "instruction": instruction, "baseRevision": revision})
    assert response.status_code == 200, response.text
    from app.worker import work_once
    assert work_once(None)
    return client.get(BASE + "/runs/" + response.json()["id"]).json()


def test_stage_writes_are_real_and_later_stages_stay_empty(client, monkeypatch):
    run = start(client, monkeypatch, [[tc("get_case_context", {}, "context")], [tc("update_requirements", {"fields": {"product": "backpack", "quantity": 3000, "packaging": None, "missing_fields": ["packaging"]}}, "requirements")]])
    assert run["status"] == "succeeded", run
    assert run["outputRevision"] == 1
    assert [t["name"] for t in run["toolCalls"]] == ["get_case_context", "update_requirements"]
    artifacts = client.get(CASE + "/artifacts").json()["items"]
    assert [a["kind"] for a in artifacts] == ["spec"]
    revision = client.get(CASE + "/revisions/1").json()
    assert revision["requirements"]["quantity"] == 3000
    assert revision["quote"] is None
    assert revision["replies"] == {"en-US": "", "es-MX": ""}


def test_disabled_skill_is_enforced_and_questions_persist(client, monkeypatch):
    response = client.patch(BASE + "/settings", json={"skills": [{"id": "specification", "enabled": False}]})
    assert response.status_code == 200, response.text
    run = start(client, monkeypatch, [[tc("save_artifact_draft", {"kind": "spec", "title": "规格", "content": {"product": "backpack"}, "base_version": 0}, "disabled")], [tc("ask_user", {"questions": ["请启用规格技能后继续。"]}, "question")]])
    assert run["status"] == "needs_input", run
    assert run["toolCalls"][0]["status"] == "failed"
    assert run["clarification"]["questions"][0]["question"] == "请启用规格技能后继续。"
    assert client.get(CASE + "/artifacts").json()["items"] == []


def test_costing_uses_decimal_and_does_not_generate_quotation(client, monkeypatch):
    evidence = client.post(CASE + "/evidence", json={"title": "工厂原件", "sourceRole": "supplier_quote", "text": "工厂A，base 44, packaging 2, local 4, MOQ1000, 28 days"}).json()
    offer = client.post(CASE + "/supplier-offers", json={"supplier": "A", "evidenceSourceId": evidence["id"], "baseCny": "44", "packagingCny": "2", "localCny": "4", "moq": 1000, "leadDays": 28}).json()
    run = start(client, monkeypatch, [[tc("calculate_quote", {"offer_id": offer["id"], "quantity": 3000}, "calculate")]], "核算成本")
    assert run["status"] == "succeeded", run
    artifacts = client.get(CASE + "/artifacts").json()["items"]
    assert [a["kind"] for a in artifacts] == ["cost"]
    assert artifacts[0]["content"]["result"]["unitPriceUsd"] == "8.69"
    assert client.get(CASE + "/revisions/1").json()["quote"] is None


def test_private_asset_and_approval_fields_cannot_escape_scope(client, monkeypatch):
    from app.core import create_item
    from app.db import SessionLocal
    with SessionLocal() as db:
        create_item(db, "asset", {"id": "private", "space": "personal", "ownerId": "other", "name": "private.txt", "textContent": "private"}, item_id="private:v1")
        db.commit()
    run = start(client, monkeypatch, [[tc("read_asset", {"version_id": "private:v1"}, "private")], [tc("save_artifact_draft", {"kind": "sample", "title": "样品反馈", "base_version": 0, "content": {"customerApproved": True, "approval": "approved", "released": True}}, "draft")]])
    assert run["status"] == "succeeded"
    assert run["toolCalls"][0]["status"] == "failed"
    artifact = client.get(CASE + "/artifacts").json()["items"][0]
    assert artifact["content"]["customerApproved"] is False
    assert artifact["content"]["approval"] is None
    assert artifact["content"]["released"] is False
    assert client.get(CASE + "/approvals").json()["items"] == []


def test_packaging_change_invalidates_quote_and_produces_editable_candidates(client, monkeypatch):
    first = start(client, monkeypatch, [[tc("update_requirements", {"fields": {"product": "backpack", "quantity": 3000, "packaging": "plain box"}}, "spec")]])
    assert first["status"] == "succeeded"
    evidence = client.post(CASE + "/evidence", json={"title": "Supplier", "sourceRole": "supplier_quote", "text": "44 + 2 + 4 CNY, MOQ1000, 28 days"}).json()
    offer = client.post(CASE + "/supplier-offers", json={"supplier": "A", "evidenceSourceId": evidence["id"], "baseCny": "44", "packagingCny": "2", "localCny": "4", "moq": 1000, "leadDays": 28}).json()
    second = start(client, monkeypatch, [[tc("calculate_quote", {"offer_id": offer["id"], "quantity": 3000}, "cost")], [tc("save_artifact_draft", {"kind": "quotation", "title": "客户报价", "content": {}, "base_version": 0}, "quote")]], "核价并生成报价", 1)
    assert second["status"] == "succeeded", second
    quotation = next(a for a in client.get(CASE + "/artifacts").json()["items"] if a["kind"] == "quotation")
    assert quotation["content"]["incoterm"] == "FOB"
    assert quotation["content"]["namedPlace"] == "Ningbo"
    third = start(client, monkeypatch, [[tc("analyze_change", {"instruction": "包装改为彩盒，新成本待供应商确认"}, "change")], [tc("update_requirements", {"fields": {"packaging": "color box"}}, "spec2")]], "包装改为彩盒", 2)
    assert third["status"] == "succeeded", third
    revision = client.get(CASE + "/revisions/3").json()
    assert revision["quote"] is None
    change = client.get(CASE + "/change-sets").json()["items"][0]
    assert change["status"] == "awaiting_confirmation"
    assert change["sourceId"] and change["candidateArtifactIds"]
    assert change["regeneratedByRunId"] == third["id"]
    assert all(i["editTarget"]["caseId"] == "inq_demo_bag" for i in change["nodeImpacts"])
    quote2 = client.get(CASE + "/artifacts/" + revision["artifactVersionIds"]["quotation"]).json()
    assert quote2["version"] == 2 and quote2["content"]["quote"] is None
    assert quote2["content"]["pendingReconfirmation"] is True


def test_negative_stage_constraints_do_not_route_to_quotation():
    from app.run_context import route_intent
    assert route_intent("analyze", "请整理需求，不要生成报价") == "confirm_requirements"
    assert route_intent("analyze", "只完成需求节点，不生成回复或报价") == "confirm_requirements"
