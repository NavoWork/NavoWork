WORKSPACE_ID = "ws_demo"


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


def test_sop_progress_reflects_only_created_drafts_without_granting_release(client):
    from app.core import create_item
    from app.db import SessionLocal
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/inquiries/inq_demo_bag/sop-status"
    initial = client.get(path).json()
    assert all(stage["status"] == "not_started" for stage in initial["stages"])
    with SessionLocal() as db:
        create_item(db, "artifact", {"kind": "sample_feedback", "title": "样品整改记录", "content": {"status": "draft"}}, case_id="inq_demo_bag")
        create_item(db, "artifact", {"kind": "qc", "title": "验货清单", "content": {"status": "draft"}}, case_id="inq_demo_bag")
        db.commit()
    result = client.get(path).json()
    assert {stage["kind"] for stage in result["stages"] if stage["status"] == "needs_review"} == {"manage_sample", "inspect_quality"}
    assert result["productionRelease"]["status"] == "blocked"


def test_customer_quotation_export_omits_internal_pricing(client):
    path = f"/api/v1/workspaces/{WORKSPACE_ID}/inquiries/inq_demo_bag"
    artifact = client.post(path + "/artifacts", json={"kind": "quotation", "title": "客户报价单", "content": {
        "product": "Backpack", "quote": {"unitPriceUsd": "8.69", "goodsSubtotalUsd": "26070.00", "unitCostCny": "50.00"},
        "margin": "20", "selectedSupplierOfferId": "internal-supplier-reference", "paymentTerms": "30% deposit"}}).json()
    exported = client.post(path + f"/artifacts/{artifact['id']}/exports", json={"format": "html"}).json()
    document = client.get(exported["downloadUrl"]).text
    assert "8.69" in document and "26070.00" in document
    assert "unitCostCny" not in document and "internal-supplier-reference" not in document and "<th>margin</th>" not in document
