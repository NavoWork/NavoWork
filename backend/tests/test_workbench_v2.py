from __future__ import annotations

from app.agent_tools import WorkbenchToolbox
from app.db import SessionLocal
from app.models import Case, Job, Run, WorkItem
from app.workbench import finalize_agent_run


def _start(client, path, node, instruction, revision=0):
    response = client.post(path + "/workbench/agent", json={"node": node, "instruction": instruction, "baseRevision": revision})
    assert response.status_code == 200, response.text
    run_id = response.json()["id"]
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        job = db.get(Job, run.job_id)
        work = db.query(WorkItem).filter(WorkItem.run_id == run.id).one()
        case = db.get(Case, run.case_id)
        run.status = "running"
        job.status = "running"
        work.status = "running"
        work.lease_generation = 1
        work.lease_expires_at = "2999-01-01T00:00:00Z"
        case.active_run_id = run.id
        db.commit()
        return WorkbenchToolbox(case_id=case.id, user_id=job.payload and __import__("app.core", fromlist=["decode"]).decode(job.payload)["createdBy"], run_id=run.id, job_id=job.id, work_item_id=work.id, generation=1), run.id, job.id, work.id, case.id


def _finish(run_id, job_id, work_id, node):
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        job = db.get(Job, job_id)
        case = db.get(Case, run.case_id)
        finalize_agent_run(db, case, run, job, "本轮已完成", node=node, artifacts_changed=True)
        db.get(WorkItem, work_id).status = "done"
        db.commit()


def test_new_inquiry_advances_node_by_node(client):
    base = "/api/v1/workspaces/ws_demo"
    created = client.post(base + "/inquiries", json={"title": "德国背包项目", "customer": "Nordlicht Outdoor", "originalText": "Please quote 3,000 custom backpacks, FOB Ningbo, delivery to Hamburg."})
    assert created.status_code == 200, created.text
    case = created.json()
    path = base + "/inquiries/" + case["id"]

    empty = client.get(path + "/workbench").json()
    assert empty["case"]["currentRevision"] == 0
    assert empty["artifacts"] == {}
    assert empty["stages"][1]["status"] == "empty"

    inquiry = client.post(path + "/evidence", json={"sourceRole": "customer_request", "title": "客户询盘", "text": "3,000 custom backpacks, FOB Ningbo, Hamburg."}).json()
    spec_source = client.post(path + "/evidence", json={"sourceRole": "internal_note", "title": "规格确认", "text": "600D recycled polyester, 30x45x15cm, YKK zipper, 20 pcs per carton."}).json()
    supplier = client.post(path + "/evidence", json={"sourceRole": "supplier_quote", "title": "工厂 A 报价", "text": "Base CNY 44, packaging CNY 2, local CNY 4, MOQ 1000, lead 28 days."}).json()

    toolbox, run_id, job_id, work_id, case_id = _start(client, path, "requirements", "整理客户需求与箱包规格")
    context = toolbox.call("get_case_context", {})
    assert context["status"] == "success"
    assert context["data"]["stages"][1]["status"] == "empty"
    result = toolbox.call("update_requirements", {"fields": {
        "product": "custom backpack", "quantity": "3000", "dimensions": "30 x 45 x 15 cm",
        "fabric": "600D recycled polyester, 300 gsm", "logo": "embroidered logo 60 x 25 mm",
        "packaging": "recycled polybag + hangtag", "inspection": "AQL 2.5 pre-shipment",
        "destination": "Hamburg, Germany", "incoterm": "FOB", "incotermsVersion": "2020",
        "namedPlace": "Ningbo", "paymentTerms": "30% deposit, 70% before shipment", "delivery": "45 days after sample approval",
    }, "source_refs": [{"evidenceId": inquiry["id"], "quote": "3,000 custom backpacks"}, {"evidenceId": spec_source["id"], "quote": "600D recycled polyester"}]})
    assert result["status"] == "success", result
    assert result["data"]["ready"] is True
    bom = toolbox.call("update_bom", {"rows": [{"category": "material", "item": "600D recycled polyester", "spec": "300 gsm", "quantityPerPiece": "1.2", "unit": "m", "supplier": "Factory A"}]})
    assert bom["status"] == "success"
    _finish(run_id, job_id, work_id, "requirements")

    view = client.get(path + "/workbench").json()
    assert view["case"]["currentRevision"] == 1
    assert view["artifacts"]["spec"]["content"]["fields"]["product"] == "custom backpack"
    assert view["artifacts"]["bom"]["content"]["rows"][0]["item"] == "600D recycled polyester"
    assert "quotation" not in view["artifacts"]
    assert view["stages"][2]["status"] == "empty"

    toolbox, run_id, job_id, work_id, _ = _start(client, path, "costing", "登记供应商报价并报价", revision=1)
    offer = toolbox.call("record_supplier_quote", {"supplier": "Factory A", "evidence_id": supplier["id"], "base_cny": "44", "packaging_cny": "2", "local_cny": "4", "moq": 1000, "lead_days": 28})
    assert offer["status"] == "success", offer
    offer_id = offer["data"]["offerId"]
    cost = toolbox.call("calculate_cost", {"supplier_offer_id": offer_id, "quantity": 3000, "exchange_rate": "7.2", "margin": "0.2"})
    assert cost["data"]["unitPriceUsd"] == "8.69", cost
    quote = toolbox.call("update_quotation", {"incoterm": "FOB", "incoterms_version": "2020", "named_place": "Ningbo", "payment_terms": "30% deposit, 70% before shipment", "valid_until": "2999-12-31", "moq": 1000, "sample_time": "7 days", "production_time": "28 days", "exclusions": ["freight", "insurance"]})
    assert quote["status"] == "success", quote
    _finish(run_id, job_id, work_id, "costing")

    view = client.get(path + "/workbench").json()
    assert view["artifacts"]["quotation"]["content"]["unitPriceUsd"] == "8.69"
    assert view["stages"][2]["status"] == "ready"
    assert view["gate"]["status"] == "blocked"

    spec_id = view["artifacts"]["spec"]["itemId"]
    quotation_id = view["artifacts"]["quotation"]["itemId"]
    customer_ok = client.post(path + "/evidence", json={"sourceRole": "customer_approval", "title": "客户确认", "text": "We approve the spec and sample."}).json()
    seller_ok = client.post(path + "/evidence", json={"sourceRole": "internal_note", "title": "卖方确认", "text": "Seller accepts the PI."}).json()
    payment_ok = client.post(path + "/evidence", json={"sourceRole": "payment_receipt", "title": "付款凭据", "text": "Deposit received."}).json()
    supplier_ok = client.post(path + "/evidence", json={"sourceRole": "supplier_confirmation", "title": "工厂确认", "text": "Factory accepts the production conditions."}).json()

    toolbox, run_id, job_id, work_id, _ = _start(client, path, "sample", "记录样品", revision=2)
    sample = toolbox.call("record_sample", {"type": "pre_production", "round": 1, "sample_ref": "SMP-DE-001", "spec_version_id": spec_id, "checks": {"appearance": "passed", "dimensions": "passed"}})
    assert sample["status"] == "success", sample
    _finish(run_id, job_id, work_id, "sample")

    toolbox, run_id, job_id, work_id, _ = _start(client, path, "order", "登记 PO 与付款计划", revision=3)
    order = toolbox.call("record_order", {"po": {"number": "PO-DE-001", "buyer": "Nordlicht Outdoor", "quantity": 3000, "unitPriceUsd": "8.69", "totalUsd": "26070.00", "incoterm": "FOB", "namedPlace": "Ningbo", "paymentTerms": "30% deposit, 70% before shipment"}, "pi": {"number": "PI-DE-001", "seller": "NavoWork Trading", "bank": "Demo Bank"}, "payment_schedule": [{"milestone": "deposit", "ratio": "0.30", "amountUsd": "7821.00", "due": "2026-11-10"}]})
    assert order["status"] == "success", order
    assert order["data"]["conflicts"] == []
    _finish(run_id, job_id, work_id, "order")

    view = client.get(path + "/workbench").json()
    sample_id = view["artifacts"]["sample"]["itemId"]
    order_id = view["artifacts"]["order"]["itemId"]
    payment_id = view["artifacts"]["payment"]["itemId"]
    for scope, target, refs in (
        ("customer_spec_approval", spec_id, [customer_ok["id"]]),
        ("commercial_quotation_approval", quotation_id, []),
        ("sample_approval", sample_id, [customer_ok["id"]]),
        ("order_buyer_confirmation", order_id, [customer_ok["id"]]),
        ("order_seller_confirmation", order_id, [seller_ok["id"]]),
        ("payment_verification", payment_id, [payment_ok["id"]]),
    ):
        body = {"scope": scope, "targetVersionId": target, "evidenceRefs": refs}
        if scope == "payment_verification":
            body["verificationBasis"] = "财务核对定金凭据"
        response = client.post(path + "/workbench/approvals", json=body)
        assert response.status_code == 200, (scope, response.text)

    toolbox, run_id, job_id, work_id, _ = _start(client, path, "production", "准备生产资料", revision=4)
    production = toolbox.call("prepare_production", {"qc_standard": "AQL 2.5"})
    assert production["status"] == "success", production
    _finish(run_id, job_id, work_id, "production")
    view = client.get(path + "/workbench").json()
    production_id = view["artifacts"]["production"]["itemId"]
    blocked = client.post(path + "/workbench/release", json={"targetVersionId": production_id, "evidenceRefs": []})
    assert blocked.status_code == 422
    confirm = client.post(path + "/workbench/approvals", json={"scope": "supplier_production_confirmation", "targetVersionId": production_id, "evidenceRefs": [supplier_ok["id"]]})
    assert confirm.status_code == 200, confirm.text
    released = client.post(path + "/workbench/release", json={"targetVersionId": production_id, "evidenceRefs": []})
    assert released.status_code == 200, released.text
    final = client.get(path + "/workbench").json()
    assert final["gate"]["status"] == "passed", final["gate"]
    assert final["stages"][5]["status"] == "confirmed"
