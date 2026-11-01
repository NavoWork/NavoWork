"""Customer PO immutability and server-projected PI across every writer."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from app.core import create_item, item_view, items
from app.db import SessionLocal
from app.exports import export_artifact
from app.models import Blob, Case, Item
from app.propagation import propagation_view
from app.workbench import append_artifact, latest_artifacts
from test_propagation import seed, change_quantity


CASE = "/api/v1/workspaces/ws_demo/inquiries/inq_demo_bag"


def _order_inputs(quote):
    po = {key: deepcopy(quote["content"].get(key)) for key in (
        "quantity", "unitPriceUsd", "totalUsd", "incoterm", "namedPlace", "paymentTerms")}
    po.update(number="PO-ORIGINAL", originalText="PRIVATE_CUSTOMER_PO_100_PIECES")
    pi = {"number": "PI-001", "seller": {"name": "Seller", "address": "Office 1"},
          "buyer": {"name": "Buyer"}, "bank": "Preserve bank instructions",
          "quantity": 999, "unitPriceUsd": "999.99", "totalUsd": "999990.00",
          "margin": "PRIVATE_MARGIN", "supplier": "PRIVATE_FACTORY"}
    return {"po": po, "pi": pi,
            "confirmations": {"buyer": {"confirmed": True}, "seller": {"confirmed": True}}}


def _export_text(db, exported):
    data = Path(db.get(Blob, exported["blobId"]).path).read_bytes()
    if exported["format"] == "pdf":
        from pypdf import PdfReader
        return "\n".join(page.extract_text() for page in PdfReader(BytesIO(data)).pages)
    with ZipFile(BytesIO(data)) as archive:
        return "\n".join(archive.read(name).decode("utf-8") for name in archive.namelist() if name.endswith(".xml"))


def test_manual_order_server_projects_pi_and_propagates_new_amount_without_po_or_approval_rewrite(client):
    with SessionLocal() as db:
        case, spec, _, quote, _ = seed(db)
    inputs = _order_inputs(quote)
    original = deepcopy(inputs)
    response = client.put(CASE + "/workbench/artifacts/order", json={"baseVersion": 0, "content": inputs})
    assert response.status_code == 200, response.text
    order = response.json()
    assert order["content"]["po"] == original["po"]
    assert order["content"]["pi"]["quantity"] == 100
    assert order["content"]["pi"]["totalUsd"] == quote["content"]["totalUsd"]
    assert order["content"]["pi"]["bank"] == original["pi"]["bank"]
    assert not order["content"]["confirmations"]["buyer"]["confirmed"]
    assert not order["content"]["confirmations"]["seller"]["confirmed"]
    assert order["content"]["quotationVersionId"] == quote["itemId"]
    with SessionLocal() as db:
        case = db.get(Case, "inq_demo_bag")
        approval = create_item(db, "approval", {"scope": "order_buyer_confirmation",
            "targetVersionId": order["itemId"], "decision": "approved"}, case_id=case.id)
        approval_id, approval_payload = approval.id, approval.payload
        payment = append_artifact(db, case, "payment", {"schedule": [
            {"milestone": "deposit", "amountUsd": "412.50", "ratio": "0.30", "status": "pending"}]})
        original_payment = deepcopy(payment["content"])
        original_order_content = deepcopy(order["content"])
        old_exports = {fmt: export_artifact(db, case, db.get(Item, order["itemId"]), fmt)
                       for fmt in ("docx", "pdf")}
        change_quantity(db, case, spec, 200)
        db.commit()
        latest = latest_artifacts(db, case)
        updated = latest["order"]
        assert updated["version"] == 2
        assert updated["content"]["po"] == original["po"]
        assert updated["content"]["pi"]["quantity"] == 200
        assert updated["content"]["pi"]["unitPriceUsd"] == "13.13"
        assert updated["content"]["pi"]["totalUsd"] == "2626.00"
        assert updated["content"]["pi"]["currency"] == "USD"
        for key in ("number", "seller", "buyer", "bank"):
            assert updated["content"]["pi"][key] == original["pi"][key]
        assert updated["content"]["quotationVersionId"] == latest["quotation"]["itemId"]
        assert updated["requiresReconfirmation"] is True
        assert not updated["content"]["confirmations"]["buyer"]["confirmed"]
        assert any(row["field"] == "quantity" and row["status"] == "conflict" for row in updated["content"]["diff"])
        assert item_view(db.get(Item, order["itemId"]))["content"] == original_order_content
        assert db.get(Item, approval_id).payload == approval_payload
        assert len(items(db, "approval", case_id=case.id)) == 1
        assert latest["payment"]["itemId"] == payment["itemId"]
        assert latest["payment"]["content"] == original_payment
        assert latest["payment"]["freshness"]["status"] == "needs_review"
        run = propagation_view(db, case)["runs"][-1]
        assert run["nodes"]["order"]["status"] == "synced"
        assert run["nodes"]["payment"]["status"] == "needs_review"
        assert updated["consistencyId"] == latest["quotation"]["consistencyId"]
        for fmt, old in old_exports.items():
            assert item_view(db.get(Item, old["exportId"]))["status"] == "stale"
            branch = run["nodes"]["order"]["exports"][fmt]
            assert branch["status"] == "ready"
            exported = item_view(db.get(Item, branch["exportId"]))
            assert exported["artifactVersionId"] == updated["itemId"]
            text = _export_text(db, exported)
            assert "2626.00" in text and "13.13" in text
            assert "PRIVATE_" not in text and "costVersionId" not in text and "margin" not in text


def test_native_record_order_uses_same_pi_projection(client):
    from test_workbench_v2 import _start

    with SessionLocal() as db:
        _, _, _, quote, _ = seed(db)
    inputs = _order_inputs(quote)
    toolbox, *_ = _start(client, CASE, "order", "Prepare a PI draft")
    result = toolbox.call("record_order", {"po": inputs["po"], "pi": inputs["pi"]})
    assert result["status"] == "success", result
    with SessionLocal() as db:
        case = db.get(Case, "inq_demo_bag")
        content = latest_artifacts(db, case)["order"]["content"]
        assert content["po"] == inputs["po"]
        assert content["pi"]["quantity"] == 100
        assert content["pi"]["unitPriceUsd"] == quote["content"]["unitPriceUsd"]
        assert content["pi"]["totalUsd"] == quote["content"]["totalUsd"]
        assert content["pi"]["number"] == "PI-001"
        assert content["confirmations"]["seller"]["confirmed"] is False


def test_pi_total_is_computed_from_quote_and_removed_terms_do_not_survive(client):
    with SessionLocal() as db:
        case, _, _, quote, _ = seed(db)
        quoted = deepcopy(quote["content"])
        quoted.update(totalUsd="WRONG_TOTAL", product="Updated bag", paymentTerms=None)
        append_artifact(db, case, "quotation", quoted)
        inputs = _order_inputs(quote)
        inputs["pi"].update(paymentTerms="Old terms", product="Old product")
        order = append_artifact(db, case, "order", inputs)
        assert order["content"]["pi"]["totalUsd"] == "1375.00"
        assert order["content"]["pi"]["paymentTerms"] is None
        assert order["content"]["pi"]["product"] == "Updated bag"
        assert order["content"]["po"] == inputs["po"]


def test_incomplete_quote_preserves_reviewable_legacy_draft_without_invented_pi_money(client):
    with SessionLocal() as db:
        case = db.get(Case, "inq_demo_bag")
        append_artifact(db, case, "quotation", {"unitPriceUsd": "8.69"})
        order = append_artifact(db, case, "order", {
            "quotationVersionId": "legacy-quote", "specVersionId": "legacy-spec",
            "po": {"number": "CUSTOMER-ORIGINAL"},
            "pi": {"number": "PI-DRAFT", "totalUsd": "FABRICATED"},
        })
        assert order["content"]["pi"]["totalUsd"] is None
        assert order["content"]["pi"]["quantity"] is None
        assert order["content"]["piProjection"]["status"] == "needs_review"
        assert order["content"]["quotationVersionId"] == "legacy-quote"
        assert order["content"]["po"] == {"number": "CUSTOMER-ORIGINAL"}
