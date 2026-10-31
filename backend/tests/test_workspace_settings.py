from app.core import WORKSPACE_ID


def test_settings_persist_business_defaults_and_skill_switches(client):
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/settings"
    initial = client.get(path).json()
    assert initial["agent"]["stepwise"] is True
    response = client.patch(path, json={"editVersion": initial["editVersion"], "company": {"name": "Harbor Trading", "defaultPort": "Shanghai"}, "pricing": {"exchangeRate": "7.15", "targetMargin": "25"}, "skills": [{"id": "quotation", "enabled": False}]})
    assert response.status_code == 200
    saved = client.get(path).json()
    assert saved["company"]["name"] == "Harbor Trading"
    assert saved["pricing"]["exchangeRate"] == "7.15"
    assert not next(s for s in saved["skills"] if s["id"] == "quotation")["enabled"]
    assert client.patch(path, json={"editVersion": initial["editVersion"], "pricing": {"targetMargin": "10"}}).status_code == 409


def test_settings_reject_invalid_pricing_and_client_credentials(client, other_client):
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/settings"
    for pricing in ({"exchangeRate": "0"}, {"targetMargin": "100"}, {"exchangeRate": "NaN"}, {"quotationValidityDays": 1.5}):
        assert client.patch(path, json={"pricing": pricing}).status_code == 400
    assert client.patch(path, json={"agent": {"apiKey": "no-client-keys"}}).status_code == 400
    assert other_client.patch(path, json={"company": {"name": "Other"}}).status_code == 403
    assert other_client.get(path).status_code == 200


def test_settings_redact_endpoint_credentials(client, monkeypatch):
    monkeypatch.setenv("MODEL_BASE_URL", "https://user:secret@example.test/v1?api_key=hidden")
    response = client.get(f"/api/v1/workspaces/{WORKSPACE_ID}/settings")
    assert response.json()["agent"]["baseUrl"] == "https://example.test/v1"
    assert "secret" not in response.text and "hidden" not in response.text
