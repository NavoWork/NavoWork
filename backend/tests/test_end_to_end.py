from __future__ import annotations

import os


def test_real_case_run_change_and_export(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("GRAPH_CHECKPOINT_DB", str(tmp_path / "graph.sqlite3"))
    monkeypatch.setenv("APP_ENV", "demo")
    from fastapi.testclient import TestClient
    from langgraph.checkpoint.sqlite import SqliteSaver
    from app.agent import build_graph, price_quote
    from app.main import app
    from app.worker import work_once

    assert price_quote({"base": "44", "packaging": "2", "local": "4", "exchangeRate": "7.2", "margin": "20", "quantity": 3000})["unitPriceUsd"] == "8.69"
    assert price_quote({"base": "44", "packaging": "5", "local": "4", "exchangeRate": "7.2", "margin": "20", "quantity": 3000})["unitPriceUsd"] == "9.21"
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/session", json={"email": "demo@navowork.local", "password": "ChangeMe123!"})
        assert response.status_code == 200, response.text
        base = "/api/v1/workspaces/ws_demo"
        created = client.post(base + "/inquiries", json={"title": "德国背包项目", "customer": "Michael", "originalText": "Please quote 3,000 custom backpacks with our logo, FOB Ningbo."}, headers={"Idempotency-Key": "case-test"})
        assert created.status_code == 200, created.text
        case = created.json()
        repeated = client.post(base + "/inquiries", json={"title": "德国背包项目", "customer": "Michael", "originalText": "Please quote 3,000 custom backpacks with our logo, FOB Ningbo."}, headers={"Idempotency-Key": "case-test"})
        assert repeated.json()["id"] == case["id"]
        path = base + "/inquiries/" + case["id"]
        supplier_source = client.post(path + "/evidence", json={"sourceRole": "supplier_quote", "title": "工厂 A 报价", "text": "Backpack RMB44; packaging RMB2"}).json()
        initial_offer = client.post(path + "/supplier-offers", json={"supplier": "Factory A", "evidenceSourceId": supplier_source["id"], "baseCny": "44", "packagingCny": "2", "localCny": "4", "moq": 1000, "leadDays": 28}).json()
        run = client.post(path + "/jobs", json={"kind": "prepare_quote", "goal": "请核算背包报价", "costInputs": {"base": "44", "packaging": "2", "local": "4", "exchangeRate": "7.2", "margin": "20", "quantity": 3000}})
        assert run.status_code == 422, run.text
        run = client.post(path + "/jobs", json={"kind": "prepare_quote", "goal": "请核算背包报价", "selectedSupplierOfferId": initial_offer["id"], "costInputs": {"exchangeRate": "7.2", "margin": "20", "quantity": 3000}})
        assert run.status_code == 200, run.text
        with SqliteSaver.from_conn_string(str(tmp_path / "graph.sqlite3")) as saver:
            saver.setup()
            assert work_once(build_graph(saver))
        finished = client.get(base + "/runs/" + run.json()["id"])
        assert finished.json()["status"] == "succeeded", finished.text
        revision = client.get(path + "/revisions").json()["items"][-1]
        assert revision["quote"]["unitPriceMinor"] == 869
        drafts = client.get(path + "/revisions/1/reply-drafts").json()["items"]
        result = client.post(path + "/exports", json={"revision": 1, "draftVersions": {d["locale"]: d["draftVersion"] for d in drafts}, "format": "pdf"})
        assert result.status_code == 200, result.text
        downloaded = client.get(result.json()["downloadUrl"])
        assert downloaded.content.startswith(b"%PDF")
        impact = client.post(path + "/change-sets", json={"instruction": "供应商将包装改为定制彩盒，成本和交期需更新"})
        assert impact.status_code == 200, impact.text
        assert any(i["nodeKey"] == "calculate_cost" for i in impact.json()["nodeImpacts"])
        assert client.get(path + "/change-sets/" + impact.json()["id"] + "/node-impacts").json()["items"]
        pack = client.post(path + "/production-packs", json={"revision": 1}).json()
        check = client.post(path + "/production-packs/" + pack["id"] + "/validate", json={}).json()
        assert check["status"] == "blocked"
        denied = client.post(path + "/production-packs/" + pack["id"] + "/release", json={})
        assert denied.status_code == 422

        artifacts = client.get(path + "/artifacts").json()["items"]
        assert {"spec", "rfq", "comparison", "cost", "quotation"} <= {a["kind"] for a in artifacts}
        for kind in ("spec", "rfq", "comparison", "cost", "quotation"):
            artifact = next(a for a in artifacts if a["kind"] == kind)
            exported = client.post(path + f"/artifacts/{artifact['id']}/exports", json={"format": "xlsx"})
            assert exported.status_code == 200, exported.text
            assert client.get(exported.json()["downloadUrl"]).content.startswith(b"PK")
        spec = next(a for a in artifacts if a["kind"] == "spec")
        next_spec = client.post(path + f"/artifacts/{spec['id']}/versions", json={"baseVersion": 1, "content": {"product": "backpack", "packaging": "custom box"}})
        assert next_spec.status_code == 200, next_spec.text
        assert client.post(path + f"/artifacts/{spec['id']}/versions", json={"baseVersion": 1, "content": {}}).status_code == 409
        assert client.get(path + f"/artifacts/{next_spec.json()['id']}/diff?from=1").json()["changedFields"]

        customer = client.post(path + "/evidence", json={"sourceRole": "customer_approval", "title": "客户规格确认邮件", "text": "We approve spec V1"}).json()
        internal = client.post(path + "/evidence", json={"sourceRole": "internal_note", "title": "卖方 PI 确认", "text": "Seller confirms PI V1"}).json()
        po = client.post(path + "/evidence", json={"sourceRole": "customer_po", "title": "PO", "text": "Order for 3000 backpacks"}).json()
        parsed = client.post(path + f"/evidence/{po['id']}/parse", json={})
        assert parsed.status_code == 200, parsed.text
        assert client.post(path + "/approvals", json={"scope": "customer_spec_approval", "targetVersionId": "1", "decision": "approved", "evidenceRefs": [internal["id"]]}).status_code == 400
        assert client.post(path + "/samples", json={"customerApproved": True, "evidenceSourceId": internal["id"]}).status_code == 400
        assert client.post(path + "/order-confirmations", json={"documentVersionId": po["id"], "buyerConfirmed": True, "sellerConfirmed": True, "buyerEvidenceSourceId": customer["id"], "sellerEvidenceSourceId": customer["id"]}).status_code == 400
        assert client.post(path + "/payment-assurance-checks", json={"decision": "verified", "evidenceSourceId": po["id"]}).status_code == 400
        assert client.post(path + f"/change-sets/{impact.json()['id']}/activate", json={}).status_code == 422

        change_source = client.post(path + "/evidence", json={"sourceRole": "supplier_quote", "title": "包装变更", "text": "Packaging custom box costs more"}).json()
        change = client.post(path + "/change-sets", json={"instruction": "包装从纸盒改为彩盒", "sourceId": change_source["id"]}).json()
        regenerated = client.post(path + f"/change-sets/{change['id']}/regenerate", json={})
        assert regenerated.status_code == 200, regenerated.text
        with SqliteSaver.from_conn_string(str(tmp_path / "graph.sqlite3")) as saver:
            saver.setup()
            assert work_once(build_graph(saver))
        refreshed = client.get(path + f"/change-sets/{change['id']}").json()
        assert refreshed["status"] == "awaiting_confirmation"
        assert len(refreshed["candidateArtifactIds"]) >= 3
        assert client.post(path + f"/change-sets/{change['id']}/activate", json={}).status_code == 422

        supplier_source = client.post(path + "/evidence", json={"sourceRole": "supplier_quote", "title": "工厂 A 报价", "text": "Backpack RMB44; packaging RMB2"}).json()
        offer = client.post(path + "/supplier-offers", json={"supplier": "Factory A", "evidenceSourceId": supplier_source["id"], "baseCny": "44", "packagingCny": "2", "localCny": "4", "moq": 1000, "leadDays": 28})
        assert offer.status_code == 200, offer.text
        assert client.post(path + "/jobs", json={"kind": "prepare_quote", "selectedSupplierOfferId": offer.json()["id"], "costInputs": {"exchangeRate": "7.2", "margin": "20", "quantity": 500}}).status_code == 400
        supplier_run = client.post(path + "/jobs", json={"kind": "prepare_quote", "selectedSupplierOfferId": offer.json()["id"], "costInputs": {"exchangeRate": "7.2", "margin": "20", "quantity": 3000}})
        assert supplier_run.status_code == 200, supplier_run.text
        with SqliteSaver.from_conn_string(str(tmp_path / "graph.sqlite3")) as saver:
            saver.setup()
            assert work_once(build_graph(saver))
        comparison = [a for a in client.get(path + "/artifacts").json()["items"] if a["kind"] == "comparison"][-1]
        assert comparison["content"]["selectedSupplierOfferId"] == offer.json()["id"]
        assert comparison["content"]["supplierOffers"][0]["supplier"] == "Factory A"

        second_path = base + "/inquiries/" + client.post(base + "/inquiries", json={"title": "另一个项目", "customer": "Other", "originalText": "Quote bags"}).json()["id"]
        assert client.get(second_path + f"/evidence/{supplier_source['id']}").status_code == 404
        assert client.get(second_path + f"/artifacts/{spec['id']}").status_code == 404
        assert client.post(second_path + "/supplier-offers", json={"supplier": "Cross", "evidenceSourceId": supplier_source["id"], "baseCny": "1", "packagingCny": "1"}).status_code == 404

        release_case = client.post(base + "/inquiries", json={"title": "生产放行项目", "customer": "Buyer", "originalText": "Please quote 3000 backpacks."}).json()
        release_path = base + "/inquiries/" + release_case["id"]
        assert client.post(release_path + "/jobs", json={"kind": "qualify_inquiry", "goal": "建立规格草稿"}).status_code == 200
        with SqliteSaver.from_conn_string(str(tmp_path / "graph.sqlite3")) as saver:
            saver.setup()
            assert work_once(build_graph(saver))
        factory_evidence = client.post(release_path + "/evidence", json={"sourceRole": "supplier_quote", "text": "Base CNY44 packaging CNY2", "title": "生产报价"}).json()["id"]
        factory_offer = client.post(release_path + "/supplier-offers", json={"supplier": "Factory B", "evidenceSourceId": factory_evidence, "baseCny": "44", "packagingCny": "2", "localCny": "4", "moq": 1000, "leadDays": 28}).json()["id"]
        quote_run = client.post(release_path + "/jobs", json={"kind": "prepare_quote", "selectedSupplierOfferId": factory_offer, "costInputs": {"exchangeRate": "7.2", "margin": "20", "quantity": 3000}})
        assert quote_run.status_code == 200, quote_run.text
        with SqliteSaver.from_conn_string(str(tmp_path / "graph.sqlite3")) as saver:
            saver.setup()
            assert work_once(build_graph(saver))
        release_artifacts = client.get(release_path + "/artifacts").json()["items"]
        spec_id = [a for a in release_artifacts if a["kind"] == "spec"][-1]["id"]
        quote = [a for a in release_artifacts if a["kind"] == "quotation"][-1]
        quote_content = {**quote["content"], "incoterm": "FOB", "namedPlace": "Ningbo", "paymentTerms": "30% deposit, 70% before shipment", "validUntil": "2026-12-31"}
        quote_edit = client.post(release_path + f"/artifacts/{quote['id']}/versions", json={"baseVersion": quote["version"], "content": quote_content})
        assert quote_edit.status_code == 200, quote_edit.text
        quote_id = quote_edit.json()["id"]
        customer_ok = client.post(release_path + "/evidence", json={"sourceRole": "customer_approval", "text": "I approve the final sample and spec.", "title": "客户确认"}).json()["id"]
        supplier_ok = client.post(release_path + "/evidence", json={"sourceRole": "supplier_confirmation", "text": "We accept production.", "title": "工厂确认"}).json()["id"]
        po_id = client.post(release_path + "/evidence", json={"sourceRole": "customer_po", "text": "PO version 1", "title": "订单"}).json()["id"]
        seller_ok = client.post(release_path + "/evidence", json={"sourceRole": "internal_note", "text": "Seller confirms PO version 1", "title": "卖方确认"}).json()["id"]
        payment_id = client.post(release_path + "/evidence", json={"sourceRole": "payment_receipt", "text": "Bank receipt reference 123", "title": "入账凭据"}).json()["id"]
        for scope, target, refs in (("customer_spec_approval", spec_id, [customer_ok]), ("commercial_quotation_approval", quote_id, []), ("supplier_production_confirmation", "2", [supplier_ok])):
            response = client.post(release_path + "/approvals", json={"scope": scope, "targetVersionId": target, "decision": "approved", "evidenceRefs": refs})
            assert response.status_code == 200, response.text
        assert client.post(release_path + "/samples", json={"specVersionId": spec_id, "customerApproved": True, "evidenceSourceId": customer_ok}).status_code == 200
        assert client.post(release_path + "/order-confirmations", json={"documentVersionId": po_id, "buyerConfirmed": True, "sellerConfirmed": True, "buyerEvidenceSourceId": customer_ok, "sellerEvidenceSourceId": seller_ok}).status_code == 200
        assert client.post(release_path + "/payment-assurance-checks", json={"decision": "verified", "evidenceSourceId": payment_id, "verificationBasis": "已由负责人核对银行流水 123"}).status_code == 200
        release_pack = client.post(release_path + "/production-packs", json={"revision": 2}).json()
        assert client.post(release_path + f"/production-packs/{release_pack['id']}/validate", json={}).json()["status"] == "passed"
        released = client.post(release_path + f"/production-packs/{release_pack['id']}/release", json={})
        assert released.status_code == 200, released.text
        assert released.json()["released"] is True
