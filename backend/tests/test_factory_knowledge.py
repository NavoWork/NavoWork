import json
from langchain_core.messages import AIMessage, ToolMessage

BASE = "/api/v1/workspaces/ws_demo"
CASE = BASE + "/inquiries/inq_demo_bag"


def checked(response):
    assert response.status_code == 200, response.text
    return response.json()


def factory(client, base="44", previous=None):
    body = {"title": "背包工厂 A · 核价资料", "content": f"工厂 A；适用产品：定制背包；基础单价 CNY {base}/件；包装 CNY 2/件；本地费用 CNY 4/件；MOQ 1000；交期 28 天。"}
    return checked(client.post(BASE + (f"/knowledge/{previous['sourceId']}/versions" if previous else "/knowledge"), json=body))


class FactoryModel:
    def __init__(self, source, base="44", quote_version=0):
        self.source, self.base, self.quote_version, self.step = source, base, quote_version, 0

    def bind_tools(self, tools):
        assert any(t["function"]["name"] == "register_knowledge_offer" for t in tools)
        return self

    def invoke(self, messages):
        self.step += 1
        calls = [
            ("get_case_context", {}),
            ("search_knowledge", {"query": "背包"}),
            ("read_knowledge", {"version_id": f"{self.source['sourceId']}:v{self.source['version']}"}),
            ("register_knowledge_offer", {"version_id": f"{self.source['sourceId']}:v{self.source['version']}", "offer": {"supplier": "工厂 A", "baseCny": self.base, "packagingCny": "2", "localCny": "4", "moq": 1000, "leadDays": 28}}),
        ]
        if self.step <= len(calls):
            name, args = calls[self.step - 1]
        elif self.step == 5:
            offer = json.loads(next(m.content for m in reversed(messages) if isinstance(m, ToolMessage)))
            name, args = "calculate_quote", {"offer_id": offer["id"], "quantity": 3000}
        elif self.step == 6:
            name, args = "save_artifact_draft", {"kind": "quotation", "title": "客户报价草稿", "content": {}, "base_version": self.quote_version}
        else:
            return AIMessage(content="已按工厂知识生成成本与报价草稿，请审查。")
        return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{self.step}", "type": "tool_call"}])


def run_quote(client, monkeypatch, model, revision=0):
    import app.business_agent as module
    from app.worker import work_once
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_NAME", "test-model")
    # Knowledge-first quotation must remain on the business agent even when file tools are enabled.
    monkeypatch.setenv("AGENT_FILE_TOOLS", "1")
    original = getattr(module, "_test_original_execute", module.execute_business_work)
    monkeypatch.setattr(module, "_test_original_execute", original, raising=False)
    monkeypatch.setattr(module, "execute_business_work", lambda work, gen: original(work, gen, model))
    dispatched = checked(client.post(CASE + "/runs", json={"action": "prepare_quote", "knowledgeQuote": True, "baseRevision": revision, "instruction": "从知识库自动核价并生成待审查报价"}))
    assert work_once(None)
    return checked(client.get(BASE + "/runs/" + dispatched["id"]))


def test_knowledge_quote_and_version_change_preserve_previous_basis(client, monkeypatch):
    first = factory(client)
    result = run_quote(client, monkeypatch, FactoryModel(first))
    assert result["status"] == "succeeded", result
    assert all(t["status"] == "succeeded" for t in result["toolCalls"]), result
    first_artifacts = checked(client.get(CASE + "/artifacts"))["items"]
    assert {a["kind"] for a in first_artifacts} == {"cost", "quotation"}
    cost = next(a for a in first_artifacts if a["kind"] == "cost")
    assert cost["content"]["result"]["unitPriceMinor"] == 869
    assert cost["content"]["factorySource"]["sourceVersionId"] == f"{first['sourceId']}:v1"
    assert checked(client.get(CASE + "/sop-status"))["factorySource"]["outdated"] is False
    old_evidence = checked(client.get(CASE + "/evidence"))["items"][0]
    assert old_evidence["text"] == first["content"]
    assert checked(client.get(CASE + "/approvals"))["items"] == []

    second = factory(client, "52", first)
    status = checked(client.get(CASE + "/sop-status"))
    assert status["factorySource"]["outdated"] is True
    assert next(s for s in status["stages"] if s["kind"] == "prepare_quote")["status"] == "needs_update"
    old_quote = next(a for a in first_artifacts if a["kind"] == "quotation")
    approval = client.post(CASE + "/approvals", json={"scope": "commercial_quotation_approval", "decision": "approved", "targetVersionId": old_quote["id"]})
    assert approval.status_code == 422
    assert approval.json()["error"]["code"] == "FACTORY_KNOWLEDGE_CHANGED"
    updated = run_quote(client, monkeypatch, FactoryModel(second, "52", 1), revision=1)
    assert updated["status"] == "succeeded", updated
    artifacts = checked(client.get(CASE + "/artifacts"))["items"]
    new_cost = next(a for a in artifacts if a["kind"] == "cost" and a["version"] == 2)
    assert new_cost["content"]["result"]["unitPriceMinor"] == 1007
    assert new_cost["content"]["factorySource"]["version"] == 2
    assert checked(client.get(CASE + "/artifacts/" + cost["id"]))["content"] == cost["content"]
    assert checked(client.get(CASE + "/evidence/" + old_evidence["id"]))["text"] == first["content"]
    assert checked(client.get(CASE + "/sop-status"))["factorySource"]["outdated"] is False
    revision = checked(client.get(CASE + "/revisions/2"))
    assert any(ref["sourceVersionId"] == f"{second['sourceId']}:v2" for ref in revision["sourceRefs"])


def test_referenced_knowledge_cannot_be_overwritten(client, monkeypatch):
    source = factory(client)
    assert run_quote(client, monkeypatch, FactoryModel(source))["status"] == "succeeded"
    response = client.patch(BASE + f"/knowledge/{source['sourceId']}/versions/1", json={"editVersion": source["editVersion"], "content": "价格调整，包装费用待确认"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SOURCE_VERSION_FROZEN"
    assert checked(client.get(CASE + "/sop-status"))["factorySource"]["outdated"] is False


def test_knowledge_quotation_requires_actual_model_not_manual_import(client):
    response = client.post(CASE + "/runs", json={"action": "prepare_quote", "knowledgeQuote": True, "baseRevision": 0})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "AGENT_NOT_CONFIGURED"
    assert checked(client.get(CASE + "/evidence"))["items"] == []


def test_latest_revoked_source_is_not_replaced_by_old_version(client, monkeypatch):
    from test_business_agent import start, tc
    from app.db import SessionLocal
    from app.core import encode
    from app.models import Item
    first = factory(client)
    second = factory(client, "52", first)
    with SessionLocal() as db:
        row = db.get(Item, f"{second['sourceId']}:v2")
        row.payload = encode({**second, "status": "revoked"})
        db.commit()
    result = start(client, monkeypatch, [[tc("search_knowledge", {"query": "背包工厂 A"}, "search")]])
    with SessionLocal() as db:
        from app.models import Run
        from app.core import decode
        payload = decode(db.get(Run, result["id"]).payload)
        assert payload["toolResults"]["search"]["items"] == []


def test_old_version_and_missing_costs_cannot_be_registered(client, monkeypatch):
    from test_business_agent import start, tc
    first = factory(client)
    second = factory(client, "52", first)
    version = f"{first['sourceId']}:v1"
    latest = f"{second['sourceId']}:v2"
    result = start(client, monkeypatch, [
        [tc("read_knowledge", {"version_id": version}, "read-old")],
        [tc("register_knowledge_offer", {"version_id": version, "offer": {}}, "old")],
        [tc("read_knowledge", {"version_id": latest}, "read-new")],
        [tc("register_knowledge_offer", {"version_id": latest, "offer": {"supplier": "工厂 A", "baseCny": "52"}}, "missing")],
    ], "核价")
    assert next(t for t in result["toolCalls"] if t["id"] == "old")["status"] == "failed"
    assert next(t for t in result["toolCalls"] if t["id"] == "missing")["status"] == "failed"
    assert checked(client.get(CASE + "/supplier-offers"))["items"] == []
    assert checked(client.get(CASE + "/evidence"))["items"] == []
