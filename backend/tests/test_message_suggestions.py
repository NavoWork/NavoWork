BASE = "/api/v1/workspaces/ws_demo"
CASE = BASE + "/inquiries/inq_demo_bag"


def test_suggestions_follow_actual_artifacts_and_do_not_skip_to_orders(client):
    response = client.get(CASE + "/message-suggestions")
    assert response.status_code == 200
    fresh = response.json()
    assert fresh["items"][0]["intent"] == "requirements"
    assert not ({s["intent"] for s in fresh["items"]} & {"cost", "quotation", "order", "production"})
    client.post(CASE + "/artifacts", json={"kind": "spec", "content": {"product": "backpack", "quantity": 3000}})
    spec = client.get(CASE + "/message-suggestions").json()
    assert spec["items"][0]["intent"] == "rfq"
    client.post(CASE + "/artifacts", json={"kind": "cost", "content": {"result": {"unitPriceUsd": "8.69"}}})
    assert client.get(CASE + "/message-suggestions").json()["items"][0]["intent"] == "quotation"


def test_pending_questions_have_editable_placeholders_not_invented_answers(client, monkeypatch):
    from test_business_agent import start, tc
    run = start(client, monkeypatch, [[tc("ask_user", {"questions": ["客户希望使用普通纸盒还是定制彩盒？"]}, "question")]])
    assert run["status"] == "needs_input"
    result = client.get(CASE + "/message-suggestions").json()
    assert result["context"] == "回应刚才的问题"
    assert "普通纸盒还是定制彩盒" in result["items"][0]["message"]
    assert "【请补充】" in result["items"][0]["message"]
    assert all(item["intent"] in ("clarify", "knowledge") for item in result["items"])


def test_model_suggestions_persist_but_expire_when_case_changes(client, monkeypatch, other_client):
    from test_business_agent import start, tc
    message = "请针对刚才背包包装方式的缺项，起草一条给客户的确认消息，并保留其他尚未明确的条件。"
    run = start(client, monkeypatch, [
        [tc("update_requirements", {"fields": {"product": "backpack", "quantity": 3000, "missing_fields": ["packaging"]}}, "requirements")],
        [tc("suggest_next_messages", {"suggestions": [{"intent": "reply", "title": "确认背包包装方式", "message": message}, {"intent": "production", "title": "提前安排生产", "message": "请准备生产资料。"}]}, "suggestions")],
    ])
    assert run["status"] == "succeeded", run
    result = client.get(CASE + "/message-suggestions").json()
    assert result["items"][0]["message"] == message
    assert all(s["intent"] != "production" for s in result["items"])
    assert other_client.get(CASE + "/message-suggestions").status_code == 404
    client.post(CASE + "/evidence", json={"sourceRole": "customer_change", "text": "客户补充：使用普通纸盒。"})
    refreshed = client.get(CASE + "/message-suggestions").json()
    assert all(s["message"] != message for s in refreshed["items"])
    client.patch(BASE + "/settings", json={"skills": [{"id": "requirements", "enabled": False}]})
    assert all(s["intent"] not in ("requirements", "clarify", "reply") for s in client.get(CASE + "/message-suggestions").json()["items"])
