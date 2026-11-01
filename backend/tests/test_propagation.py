from copy import deepcopy
import pytest

from app.core import decode, encode, item_view, items
from app.db import SessionLocal
from app.domain import calculate_cost
from app.models import Case, Item
from app.propagation import add_edge, propagation_view, retry_node
from app.workbench import append_artifact, latest_artifacts

BASE = "/api/v1/workspaces/ws_demo/inquiries/inq_demo_bag/workbench"


def seed(db):
    case = db.get(Case, "inq_demo_bag")
    spec = append_artifact(db, case, "spec", {"fields": {"quantity": "100", "product": "Bag", "incoterm": "FOB",
        "incotermsVersion": "2020", "namedPlace": "Ningbo", "paymentTerms": "deposit"}}, propagate=False)
    result = calculate_cost([{"category": "material", "label": "Base", "amountCny": "72", "scope": "per_unit"},
                             {"category": "tooling", "label": "Setup", "amountCny": "720", "scope": "per_order"}],
                            exchange_rate="7.2", margin="0.2", quantity=100)
    cost = append_artifact(db, case, "cost", result)
    quote = append_artifact(db, case, "quotation", {"product": "Bag", "quantity": 100, "unitPriceUsd": result["unitPriceUsd"],
        "totalUsd": result["totalUsd"], "costVersionId": cost["itemId"], "incoterm": "FOB", "incotermsVersion": "2020",
        "namedPlace": "Ningbo", "paymentTerms": "deposit", "validUntil": "2999-12-31"})
    unrelated = append_artifact(db, case, "inquiry_assessment", {"summary": "Unrelated"})
    db.commit()
    return case, spec, cost, quote, unrelated


def change_quantity(db, case, spec, quantity):
    content = deepcopy(spec["content"])
    content["fields"]["quantity"] = str(quantity)
    return append_artifact(db, case, "spec", content)


def test_quantity_change_recalculates_only_mapped_drafts_and_invalidates_exports(client):
    from app.exports import export_artifact
    with SessionLocal() as db:
        case, spec, cost, quote, unrelated = seed(db)
        old = export_artifact(db, case, db.get(Item, quote["itemId"]), "xlsx")
        change_quantity(db, case, spec, 200)
        db.commit()
        latest = latest_artifacts(db, case)
        assert latest["cost"]["version"] == 2 and latest["quotation"]["version"] == 2
        assert latest["cost"]["content"]["unitPriceUsd"] == "13.13"
        assert latest["quotation"]["content"]["totalUsd"] == "2626.00"
        assert latest["inquiry_assessment"]["itemId"] == unrelated["itemId"]
        assert latest["cost"]["consistencyId"] == latest["quotation"]["consistencyId"]
        assert latest["cost"]["inputSnapshotHash"] == latest["quotation"]["inputSnapshotHash"]
        assert item_view(db.get(Item, old["exportId"]))["status"] == "stale"
        run = propagation_view(db, case)["runs"][-1]
        assert run["status"] == "synced" and run["coverageComplete"]
        output = run["nodes"]["quotation"]["exports"]["xlsx"]
        assert output["status"] == "ready" and output["exportId"] != old["exportId"]


def test_unmapped_file_change_is_review_and_does_not_guess_business_updates(client):
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        before = {kind: value["itemId"] for kind, value in latest_artifacts(db, case).items()}
        content = deepcopy(spec["content"])
        content["freeTextNotes"] = "New unstructured internal note"
        append_artifact(db, case, "spec", content)
        db.commit()
        latest = latest_artifacts(db, case)
        assert latest["cost"]["itemId"] == before["cost"]
        assert latest["quotation"]["itemId"] == before["quotation"]
        run = propagation_view(db, case)["runs"][-1]
        assert run["status"] == "needs_review" and not run["coverageComplete"]
        assert run["nodes"] == {}


def test_cycles_and_cross_case_edges_rejected(client):
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        with pytest.raises(ValueError, match="cycle"):
            add_edge(db, case, quote["itemId"], spec["itemId"])
        with pytest.raises(ValueError, match="endpoint"):
            add_edge(db, case, "missing_artifact", cost["itemId"])


def test_partial_export_failure_retries_only_failed_format_without_new_version(client, monkeypatch):
    import app.exports as exports
    original = exports.export_artifact
    failed = {"pdf"}

    def controlled(db, case, artifact, fmt, **kwargs):
        if artifact.version > 1 and fmt in failed:
            raise RuntimeError("Provider failure")
        return original(db, case, artifact, fmt, **kwargs)

    monkeypatch.setattr(exports, "export_artifact", controlled)
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        for fmt in ("xlsx", "pdf"):
            original(db, case, db.get(Item, quote["itemId"]), fmt)
        change_quantity(db, case, spec, 200)
        db.commit()
        run = propagation_view(db, case)["runs"][-1]
        assert run["status"] == "failed"
        node = run["nodes"]["quotation"]
        assert node["exports"]["pdf"]["status"] == "failed"
        successful_id = node["exports"]["xlsx"]["exportId"]
        artifact_id = node["outputId"]
        failed.clear()
        result = retry_node(db, case, run["id"], "quotation")
        db.commit()
        assert result["status"] == "synced"
        assert result["nodes"]["quotation"]["outputId"] == artifact_id
        assert result["nodes"]["quotation"]["exports"]["xlsx"]["exportId"] == successful_id
        assert item_view(db.get(Item, successful_id))["status"] == "ready"
        assert latest_artifacts(db, case)["quotation"]["version"] == 2


def test_late_retry_rejects_newer_source_and_approved_version_stays_immutable(client, monkeypatch):
    from app.core import create_item
    from app.exports import export_artifact
    import app.exports as exports
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        create_item(db, "approval", {"scope": "commercial_quotation_approval", "targetVersionId": quote["itemId"],
            "decision": "approved"}, case_id=case.id)
        original_content = deepcopy(quote["content"])
        export_artifact(db, case, db.get(Item, quote["itemId"]), "pdf")
        monkeypatch.setattr(exports, "export_artifact", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("failure")))
        new_spec = change_quantity(db, case, spec, 200)
        db.commit()
        run = propagation_view(db, case)["runs"][-1]
        latest = latest_artifacts(db, case)["quotation"]
        assert latest["requiresReconfirmation"] is True
        assert item_view(db.get(Item, quote["itemId"]))["content"] == original_content
        assert len(items(db, "approval", case_id=case.id)) == 1
        change_quantity(db, case, new_spec, 300)
        db.commit()
        with pytest.raises(ValueError, match="STALE_INPUT"):
            retry_node(db, case, run["id"], "quotation")
    response = client.get(BASE + "/dependencies")
    assert response.status_code == 200 and response.json()["edges"]


def test_explicit_bom_row_mapping_reprices_and_unknown_mapping_requires_review(client):
    from app.core import create_item
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        create_item(db, "evidence", {"text": "Canvas price CNY 36/m"}, case_id=case.id, item_id="supplier-price-source")
        bom = append_artifact(db, case, "bom", {"rows": [{"item": "Canvas", "unit": "m", "quantityPerPiece": "2",
            "unitPriceCny": "36", "wastage": "0", "sourceId": "supplier-price-source"}]})
        bound = deepcopy(cost["content"])
        bound.update(bomVersionId=bom["itemId"], bomBindings=[{"rowIndex": 0, "lineIndex": 0, "item": "Canvas", "unit": "m"}])
        append_artifact(db, case, "cost", bound)
        changed_bom = deepcopy(bom["content"])
        changed_bom["rows"][0]["quantityPerPiece"] = "3"
        append_artifact(db, case, "bom", changed_bom)
        db.commit()
        latest = latest_artifacts(db, case)
        assert latest["cost"]["content"]["lines"][0]["amountCny"] == "108"
        assert latest["quotation"]["content"]["unitPriceUsd"] == "20.00"
        run = propagation_view(db, case)["runs"][-1]
        assert run["status"] == "synced"
        assert run["nodes"]["cost"]["status"] == "synced"


def test_material_applicability_marks_existing_cost_and_exports_for_review(client):
    from app.exports import export_artifact
    from fastapi import HTTPException
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        # Canonical cost generation can explicitly bind existing manufacturing
        # fields; changing them invalidates applicability, never guesses a price.
        baseline_spec = deepcopy(spec["content"])
        baseline_spec["fields"]["fabric"] = "Canvas"
        spec = append_artifact(db, case, "spec", baseline_spec)
        cost = append_artifact(db, case, "cost", deepcopy(cost["content"]))
        quote_data = deepcopy(quote["content"])
        quote_data["costVersionId"] = cost["itemId"]
        quote = append_artifact(db, case, "quotation", quote_data)
        old_export = export_artifact(db, case, db.get(Item, quote["itemId"]), "pdf")
        changed = deepcopy(spec["content"])
        changed["fields"]["fabric"] = "Leather"
        append_artifact(db, case, "spec", changed)
        db.commit()
        latest = latest_artifacts(db, case)
        assert latest["cost"]["itemId"] == cost["itemId"]
        assert latest["cost"]["freshness"]["status"] == "needs_review"
        assert latest["quotation"]["freshness"]["status"] == "needs_review"
        assert item_view(db.get(Item, old_export["exportId"]))["status"] == "stale"
        with pytest.raises(HTTPException) as exc:
            export_artifact(db, case, db.get(Item, quote["itemId"]), "xlsx")
        assert exc.value.status_code == 409


def test_order_recomparison_preserves_customer_po_and_does_not_inherit_acceptance(client):
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        po = {"number": "PO-1", "quantity": 100, "unitPriceUsd": "13.75", "totalUsd": "1375.00"}
        order = append_artifact(db, case, "order", {"po": po, "pi": {"number": "PI-1", "seller": "Seller"},
            "quotationVersionId": quote["itemId"], "specVersionId": spec["itemId"],
            "confirmations": {"buyer": {"confirmed": True}, "seller": {"confirmed": True}}})
        change_quantity(db, case, spec, 200)
        db.commit()
        updated = latest_artifacts(db, case)["order"]
        assert updated["version"] == order["version"] + 1
        assert updated["content"]["po"] == po
        assert updated["content"]["confirmations"]["buyer"]["confirmed"] is False
        assert any(row["status"] == "conflict" for row in updated["content"]["diff"])


def test_native_docx_export_and_historical_freshness_header(client):
    from io import BytesIO
    from pathlib import Path
    from docx import Document
    from app.exports import export_artifact
    from app.models import Blob
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        result = export_artifact(db, case, db.get(Item, quote["itemId"]), "docx")
        blob = db.get(Blob, result["blobId"])
        document = Document(BytesIO(Path(blob.path).read_bytes()))
        assert any("13.75" in cell.text for table in document.tables for row in table.rows for cell in row.cells)
        change_quantity(db, case, spec, 200)
        db.commit()
        url = result["downloadUrl"]
    download = client.get(url)
    assert download.status_code == 200 and download.headers["x-artifact-freshness"] == "stale"


def test_failed_regeneration_rolls_back_candidate_then_recovery_unblocks_descendants(client, monkeypatch):
    import app.workbench as workbench
    original = workbench.append_artifact
    failure = {"enabled": True}

    def partial_failure(db, case, kind, content, **kwargs):
        result = original(db, case, kind, content, **kwargs)
        if kind == "cost" and failure["enabled"]:
            raise RuntimeError("Injected failure after candidate append")
        return result

    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        monkeypatch.setattr(workbench, "append_artifact", partial_failure)
        change_quantity(db, case, spec, 200)
        db.commit()
        run = propagation_view(db, case)["runs"][-1]
        assert run["nodes"]["cost"]["status"] == "failed"
        assert run["nodes"]["quotation"]["status"] == "needs_review"
        assert latest_artifacts(db, case)["cost"]["version"] == 1
        failure["enabled"] = False
        recovered = retry_node(db, case, run["id"], "cost")
        db.commit()
        assert recovered["status"] == "synced"
        assert recovered["nodes"]["quotation"]["status"] == "synced"
        assert latest_artifacts(db, case)["cost"]["version"] == 2
        assert latest_artifacts(db, case)["quotation"]["version"] == 2
        assert case.current_revision == 1 and recovered["expectedRevision"] == 1


def test_retry_rejects_changed_case_revision_even_if_artifact_ids_unchanged(client, monkeypatch):
    import app.exports as exports
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        exports.export_artifact(db, case, db.get(Item, quote["itemId"]), "pdf")
        monkeypatch.setattr(exports, "export_artifact", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("failure")))
        change_quantity(db, case, spec, 200)
        db.commit()
        run = propagation_view(db, case)["runs"][-1]
        case.current_revision += 1
        db.commit()
        with pytest.raises(ValueError, match="Case revision"):
            retry_node(db, case, run["id"], "quotation")


def test_manual_cost_recomputes_prices_and_rejects_unbound_or_retail_sources(client):
    source = client.post(BASE.removesuffix("/workbench") + "/evidence", json={"sourceRole": "supplier_quote",
        "title": "Factory cost", "text": "CNY 72 per piece"}).json()
    content = {"lines": [{"category": "material", "label": "Base", "amountCny": "72", "scope": "per_unit", "sourceId": source["id"]}],
        "exchangeRate": "7.2", "margin": "0.2", "quantity": 100, "unitPriceUsd": "0.01", "totalUsd": "0.01"}
    response = client.put(BASE + "/artifacts/cost", json={"baseVersion": 0, "content": content})
    assert response.status_code == 200, response.text
    assert response.json()["content"]["unitPriceUsd"] == "12.50"
    assert response.json()["content"]["totalUsd"] == "1250.00"
    content["lines"][0]["sourceId"] = "does-not-exist"
    response = client.put(BASE + "/artifacts/cost", json={"baseVersion": 1, "content": content})
    assert response.status_code == 422 and response.json()["error"]["code"] == "MISSING_COST_SOURCE"
    competitor = client.post(BASE.removesuffix("/workbench") + "/evidence", json={"sourceRole": "customer_request",
        "title": "Retail listing", "text": "Retail price USD 30"}).json()
    content["lines"][0]["sourceId"] = competitor["id"]
    response = client.put(BASE + "/artifacts/cost", json={"baseVersion": 1, "content": content})
    assert response.status_code == 422


def test_visual_dependencies_ignore_quantity_but_invalidate_images_on_logo_change(client):
    from app.core import create_item
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        image = append_artifact(db, case, "concept_image", {"specVersionId": spec["itemId"], "prompt": "Bag"})
        create_item(db, "export", {"artifactVersionId": image["itemId"], "format": "png", "status": "ready"},
                    case_id=case.id, item_id="image-export")
        spec = change_quantity(db, case, spec, 200)
        assert not (latest_artifacts(db, case)["concept_image"].get("freshness") or {}).get("status")
        # Image stays attached to the original visual specification. Its edge
        # must still be traversed when a newer visual field changes.
        content = deepcopy(spec["content"])
        content["fields"]["logo"] = "larger logo"
        append_artifact(db, case, "spec", content)
        db.commit()
        assert latest_artifacts(db, case)["concept_image"]["freshness"]["status"] == "needs_review"
        assert item_view(db.get(Item, "image-export"))["status"] == "stale"


def test_quantity_change_keeps_original_physical_sample_approval(client):
    from app.core import create_item
    from app.workbench import release_gate
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        sample = append_artifact(db, case, "sample", {"sampleRef": "S1", "specVersionId": spec["itemId"]})
        approval = create_item(db, "approval", {"scope": "sample_approval", "targetVersionId": sample["itemId"],
            "decision": "approved"}, case_id=case.id)
        original_approval = deepcopy(item_view(approval))
        changed_spec = change_quantity(db, case, spec, 200)
        db.commit()
        assert latest_artifacts(db, case)["sample"]["itemId"] == sample["itemId"]
        sample_gaps = [gap for gap in release_gate(db, case)["missing"] if gap["stage"] == "sample"]
        assert not sample_gaps
        changed_content = deepcopy(changed_spec["content"])
        changed_content["fields"]["logo"] = "New embroidered logo"
        append_artifact(db, case, "spec", changed_content)
        db.commit()
        assert latest_artifacts(db, case)["sample"]["freshness"]["status"] == "needs_review"
        assert item_view(approval) == original_approval
        assert any(gap["code"] == "SAMPLE_SPEC_STALE" for gap in release_gate(db, case)["missing"])


def test_source_spec_formats_refresh_in_same_snapshot_as_downstream_outputs(client):
    from io import BytesIO
    from pathlib import Path
    from docx import Document
    from app.exports import export_artifact
    from app.models import Blob
    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        old_source_export = export_artifact(db, case, db.get(Item, spec["itemId"]), "docx")
        old_quote_export = export_artifact(db, case, db.get(Item, quote["itemId"]), "xlsx")
        changed = change_quantity(db, case, spec, 200)
        db.commit()
        group = propagation_view(db, case)["runs"][-1]
        assert group["status"] == "synced"
        source_node = group["nodes"]["spec"]
        assert source_node["sourceExport"] and source_node["outputId"] == changed["itemId"]
        source_export = item_view(db.get(Item, source_node["exports"]["docx"]["exportId"]))
        quote_export = item_view(db.get(Item, group["nodes"]["quotation"]["exports"]["xlsx"]["exportId"]))
        assert source_export["artifactVersionId"] == changed["itemId"]
        assert source_export["consistencyId"] == quote_export["consistencyId"] == group["id"]
        assert source_export["inputSnapshotHash"] == quote_export["inputSnapshotHash"] == group["inputSnapshotHash"]
        assert item_view(db.get(Item, old_source_export["exportId"]))["status"] == "stale"
        assert item_view(db.get(Item, old_quote_export["exportId"]))["status"] == "stale"
        blob = db.get(Blob, source_export["blobId"])
        document = Document(BytesIO(Path(blob.path).read_bytes()))
        assert any("200" in cell.text for table in document.tables for row in table.rows for cell in row.cells)
        assert latest_artifacts(db, case)["spec"]["version"] == 2


def test_source_format_failure_retry_preserves_successful_downstream_versions(client, monkeypatch):
    import app.exports as exports
    original = exports.export_artifact
    failed = {"pdf"}

    def controlled(db, case, artifact, fmt, **kwargs):
        if item_view(artifact).get("kind") == "spec" and artifact.version > 1 and fmt in failed:
            raise RuntimeError("Injected source PDF failure")
        return original(db, case, artifact, fmt, **kwargs)

    with SessionLocal() as db:
        case, spec, cost, quote, _ = seed(db)
        for fmt in ("docx", "pdf"):
            original(db, case, db.get(Item, spec["itemId"]), fmt)
        original(db, case, db.get(Item, quote["itemId"]), "xlsx")
        monkeypatch.setattr(exports, "export_artifact", controlled)
        change_quantity(db, case, spec, 200)
        db.commit()
        group = propagation_view(db, case)["runs"][-1]
        assert group["status"] == "failed"
        assert group["nodes"]["spec"]["exports"]["pdf"]["status"] == "failed"
        assert group["nodes"]["quotation"]["status"] == "synced"
        successful_source_export = group["nodes"]["spec"]["exports"]["docx"]["exportId"]
        successful_quote_export = group["nodes"]["quotation"]["exports"]["xlsx"]["exportId"]
        output_ids = {key: value["itemId"] for key, value in latest_artifacts(db, case).items()}
        failed.clear()
        recovered = retry_node(db, case, group["id"], "spec")
        db.commit()
        assert recovered["status"] == "synced"
        assert recovered["nodes"]["spec"]["exports"]["docx"]["exportId"] == successful_source_export
        assert recovered["nodes"]["quotation"]["exports"]["xlsx"]["exportId"] == successful_quote_export
        assert output_ids == {key: value["itemId"] for key, value in latest_artifacts(db, case).items()}
        assert item_view(db.get(Item, successful_source_export))["status"] == "ready"
        assert item_view(db.get(Item, successful_quote_export))["status"] == "ready"


def test_source_bom_export_refresh_keeps_new_bom_version_without_duplicate(client):
    from app.exports import export_artifact
    with SessionLocal() as db:
        case, _, _, _, _ = seed(db)
        bom = append_artifact(db, case, "bom", {"rows": [{"item": "Canvas", "quantityPerPiece": "2"}]})
        old_export = export_artifact(db, case, db.get(Item, bom["itemId"]), "xlsx")
        changed = append_artifact(db, case, "bom", {"rows": [{"item": "Canvas", "quantityPerPiece": "3"}]})
        db.commit()
        group = propagation_view(db, case)["runs"][-1]
        node = group["nodes"]["bom"]
        assert node["status"] == "synced" and node["outputId"] == changed["itemId"]
        new_export = item_view(db.get(Item, node["exports"]["xlsx"]["exportId"]))
        assert new_export["status"] == "ready" and new_export["artifactVersionId"] == changed["itemId"]
        assert item_view(db.get(Item, old_export["exportId"]))["status"] == "stale"
        assert latest_artifacts(db, case)["bom"]["version"] == 2
