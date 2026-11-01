"""Real Office bytes through authenticated human editing routes; no model substitute."""
from io import BytesIO

from docx import Document
from openpyxl import Workbook, load_workbook
import pytest

BASE = "/api/v1/workspaces/ws_demo/inquiries/inq_demo_bag"
OFFICE = BASE + "/workbench/office"


def upload(client, name, data):
    import mimetypes
    result = client.post(BASE + "/evidence", files={"file": (name, data, mimetypes.guess_type(name)[0] or "application/octet-stream")})
    assert result.status_code == 200, result.text
    return result.json()["id"]


def docx_bytes():
    document = Document()
    document.add_paragraph("Original specification")
    document.add_table(rows=1, cols=2).cell(0, 0).text = "Canvas"
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def xlsx_bytes():
    book = Workbook()
    book.active.title = "BOM"
    book.active.append([2, 3, "=A1*B1"])
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def copy(client, name="spec.docx", data=None):
    source_id = upload(client, name, data or docx_bytes())
    result = client.post(OFFICE, json={"fileId": source_id})
    assert result.status_code == 200, result.text
    return source_id, result.json()


def test_docx_preview_edit_history_and_access(client, other_client):
    source_id, copied = copy(client)
    document_id = copied["documentId"]
    view = client.get(OFFICE + "/" + document_id).json()
    assert view["preview"]["paragraphs"][0]["text"] == "Original specification"
    assert view["preview"]["tables"][0]["rows"][0][0] == "Canvas"
    original_copy = client.get(copied["downloadUrl"]).content
    changed = client.put(OFFICE + "/" + document_id, json={"baseVersion": 1, "baseHash": copied["sha256"],
        "operations": [{"op": "set_paragraph", "index": 0, "text": "Reviewed canvas specification", "bold": True},
                       {"op": "set_table_cell", "table": 0, "row": 0, "column": 0, "text": "Recycled canvas"}]})
    assert changed.status_code == 200, changed.text
    changed = changed.json()
    assert changed["version"] == 2 and changed["impactCoverage"] == "review_required"
    assert changed.get("consistencyId")
    downloaded = Document(BytesIO(client.get(changed["downloadUrl"]).content))
    assert downloaded.paragraphs[0].text == "Reviewed canvas specification"
    assert downloaded.paragraphs[0].runs[0].bold
    assert downloaded.tables[0].cell(0, 0).text == "Recycled canvas"
    preview = client.get(OFFICE + "/" + document_id).json()["preview"]
    assert preview["paragraphs"][0]["text"] == downloaded.paragraphs[0].text
    assert client.get(copied["downloadUrl"]).content == original_copy
    pdf = client.get(changed["downloadUrl"].replace("/download", "/pdf"))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    from app.core import decode
    from app.db import SessionLocal
    from app.models import Item, Blob
    from pathlib import Path
    with SessionLocal() as db:
        source = db.get(Item, source_id)
        assert Path(db.get(Blob, decode(source.payload)["blobId"]).path).read_bytes() == original_copy
    stale = client.put(OFFICE + "/" + document_id, json={"baseVersion": 1, "baseHash": copied["sha256"],
        "operations": [{"op": "append_paragraph", "text": "stale"}]})
    assert stale.status_code == 409
    assert other_client.get(OFFICE + "/" + document_id).status_code == 404
    assert other_client.get(changed["downloadUrl"]).status_code == 404
    assert other_client.post(OFFICE, json={"fileId": source_id}).status_code == 404


def test_xlsx_formula_preview_and_export_share_cached_values(client):
    _, copied = copy(client, "cost.xlsx", xlsx_bytes())
    path = OFFICE + "/" + copied["documentId"]
    view = client.get(path).json()
    assert view["preview"]["sheets"][0]["rows"][0][2]["display"] == 6
    updated = client.put(path, json={"baseVersion": 1, "baseHash": copied["sha256"],
        "operations": [{"op": "set_cell", "sheet": "BOM", "cell": "A1", "value": 5}]})
    assert updated.status_code == 200, updated.text
    download = client.get(updated.json()["downloadUrl"]).content
    book = load_workbook(BytesIO(download), data_only=True)
    assert book["BOM"]["C1"].value == 15
    view = client.get(path).json()
    assert view["preview"]["sheets"][0]["rows"][0][2]["display"] == 15
    rejected = client.put(path, json={"baseVersion": 2, "baseHash": updated.json()["sha256"],
        "operations": [{"op": "set_cell", "sheet": "BOM", "cell": "C1", "value": "=WEBSERVICE(A1)", "formula": True}]})
    assert rejected.status_code == 422
    assert client.get(path).json()["version"] == 2
    structural = client.put(path, json={"baseVersion": 2, "baseHash": updated.json()["sha256"],
        "operations": [{"op": "delete_rows", "sheet": "BOM", "index": 1}]})
    assert structural.status_code == 422
    copied_range = client.put(path, json={"baseVersion": 2, "baseHash": updated.json()["sha256"],
        "operations": [{"op": "copy_range", "sheet": "BOM", "sourceRange": "A1:C1", "cell": "A2"}]})
    assert copied_range.status_code == 200, copied_range.text
    ranged_book = load_workbook(BytesIO(client.get(copied_range.json()["downloadUrl"]).content), data_only=True)
    assert ranged_book["BOM"]["C2"].value == 15


def test_docx_images_are_case_scoped_and_preserved_in_output(client):
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", (10, 12), "red").save(buffer, "PNG")
    image_id = upload(client, "logo.png", buffer.getvalue())
    _, copied = copy(client)
    path = OFFICE + "/" + copied["documentId"]
    result = client.put(path, json={"baseVersion": 1, "baseHash": copied["sha256"],
        "operations": [{"op": "add_picture", "fileId": image_id, "width": 2}]})
    assert result.status_code == 200, result.text
    view = client.get(path).json()
    assert len(view["preview"]["images"]) == 1
    assert view["preview"]["images"][0]["url"].startswith("data:image/png;base64,")
    image_doc = Document(BytesIO(client.get(result.json()["downloadUrl"]).content))
    assert len(image_doc.inline_shapes) == 1
    rejected = client.put(path, json={"baseVersion": 2, "baseHash": result.json()["sha256"],
        "operations": [{"op": "replace_picture", "index": 0, "fileId": "foreign-image"}]})
    assert rejected.status_code == 422


def test_office_can_edit_real_generated_proposal_export(client):
    # Generated proposal files enter the editor through their authorized export row,
    # never by accepting a caller-supplied physical path or arbitrary Blob ID.
    from app.core import create_item, store_blob
    from app.db import SessionLocal
    from app.models import Case
    with SessionLocal() as db:
        case = db.get(Case, "inq_demo_bag")
        blob = store_blob(db, docx_bytes(), "design-proposal-v1.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", case.id)
        create_item(db, "export", {"blobId": blob.id, "format": "docx", "status": "ready",
            "artifactVersionId": "concept_image_v1"}, case_id=case.id, item_id="proposal_export")
        blob_id = blob.id
        db.commit()
    listing = client.get(OFFICE).json()
    assert any(source["fileId"] == "proposal_export" for source in listing["sources"])
    result = client.post(OFFICE, json={"fileId": "proposal_export"})
    assert result.status_code == 200, result.text
    assert client.post(OFFICE, json={"fileId": blob_id}).status_code == 404
    assert client.post(OFFICE, json={"fileId": "C:/private/secret.docx"}).status_code == 404


@pytest.mark.parametrize("fmt", ["docx", "xlsx"])
def test_generated_spec_numeric_edit_automatically_updates_cost_quote_and_exports(client, fmt):
    from app.core import items, item_view
    from app.db import SessionLocal
    from app.exports import export_artifact
    from app.models import Case, Item
    from app.workbench import latest_artifacts
    from test_propagation import seed
    with SessionLocal() as db:
        case, spec, _, quote, _ = seed(db)
        old_quote_export = export_artifact(db, case, db.get(Item, quote["itemId"]), "xlsx")
        spec_export = export_artifact(db, case, db.get(Item, spec["itemId"]), fmt)
    copied = client.post(OFFICE, json={"fileId": spec_export["exportId"]})
    assert copied.status_code == 200, copied.text
    copied = copied.json()
    mapping = copied["source"].get("templateMapping")
    assert mapping and "fields.quantity" in mapping["fields"]
    locator = mapping["fields"]["fields.quantity"]
    operation = {"op": "set_table_cell", **locator, "text": "200"} if fmt == "docx" else {"op": "set_cell", **locator, "value": 200}
    updated = client.put(OFFICE + "/" + copied["documentId"], json={"baseVersion": 1, "baseHash": copied["sha256"], "operations": [operation]})
    assert updated.status_code == 200, updated.text
    result = updated.json()
    assert result["fieldMapping"]["coverageComplete"]
    assert result["fieldMapping"]["status"] == "mapped"
    with SessionLocal() as db:
        case = db.get(Case, "inq_demo_bag")
        latest = latest_artifacts(db, case)
        assert latest["spec"]["content"]["fields"]["quantity"] == "200"
        assert latest["cost"]["version"] == 2
        assert latest["quotation"]["version"] == 2
        assert latest["quotation"]["content"]["totalUsd"] == "2626.00"
        assert item_view(db.get(Item, old_quote_export["exportId"]))["status"] == "stale"
        exports = [item_view(row) for row in items(db, "export", case_id=case.id)]
        assert any(row.get("artifactVersionId") == latest["quotation"]["itemId"] and row["status"] == "ready" for row in exports)
    view = client.get(OFFICE + "/" + copied["documentId"]).json()
    if fmt == "docx":
        assert view["preview"]["tables"][0]["rows"][locator["row"]][1] == "200"
    else:
        assert any(cell["address"] == locator["cell"] and cell["display"] == 200 for row in view["preview"]["sheets"][0]["rows"] for cell in row)


def test_stale_or_broken_template_mapping_preserves_file_without_overwriting_business(client):
    from app.db import SessionLocal
    from app.exports import export_artifact
    from app.models import Item
    from app.workbench import append_artifact, latest_artifacts
    from test_propagation import seed
    with SessionLocal() as db:
        case, spec, *_ = seed(db)
        exported = export_artifact(db, case, db.get(Item, spec["itemId"]), "docx")
    first = client.post(OFFICE, json={"fileId": exported["exportId"]}).json()
    second = client.post(OFFICE, json={"fileId": exported["exportId"]}).json()
    locator = first["source"]["templateMapping"]["fields"]["fields.quantity"]
    broken = client.put(OFFICE + "/" + first["documentId"], json={"baseVersion": 1, "baseHash": first["sha256"],
        "operations": [{"op": "set_table_cell", "table": 0, "row": locator["row"], "column": 0, "text": "unknown.quantity"}]})
    assert broken.status_code == 200, broken.text
    assert broken.json()["fieldMapping"]["status"] == "mapping_conflict"
    with SessionLocal() as db:
        assert latest_artifacts(db, case)["spec"]["version"] == 1
        changed = {**spec["content"], "fields": {**spec["content"]["fields"], "quantity": "300"}}
        append_artifact(db, case, "spec", changed)
        db.commit()
    stale = client.put(OFFICE + "/" + second["documentId"], json={"baseVersion": 1, "baseHash": second["sha256"],
        "operations": [{"op": "set_table_cell", **locator, "text": "999"}]})
    assert stale.status_code == 200, stale.text
    assert stale.json()["version"] == 2 and stale.json()["fieldMapping"]["status"] == "mapping_conflict"
    with SessionLocal() as db:
        assert latest_artifacts(db, case)["spec"]["content"]["fields"]["quantity"] == "300"


def test_generated_bom_numeric_cell_edit_reprices_bound_cost_without_chat(client):
    from copy import deepcopy
    from app.core import create_item
    from app.db import SessionLocal
    from app.domain import normalize_bom
    from app.exports import export_artifact
    from app.models import Item
    from app.workbench import append_artifact, latest_artifacts
    from test_propagation import seed
    with SessionLocal() as db:
        case, _, cost, *_ = seed(db)
        create_item(db, "evidence", {"text": "Canvas price CNY 36/m", "sourceRole": "supplier_quote"},
                    case_id=case.id, item_id="office-bom-price-source")
        bom = append_artifact(db, case, "bom", {"rows": normalize_bom([{"item": "Canvas", "unit": "m", "quantityPerPiece": "2",
            "unitPriceCny": "36", "wastage": "0", "sourceId": "office-bom-price-source"}])})
        bound = deepcopy(cost["content"])
        bound["lines"][0]["sourceId"] = "office-bom-price-source"
        bound.update(bomVersionId=bom["itemId"], bomBindings=[{"rowIndex": 0, "lineIndex": 0, "item": "Canvas", "unit": "m"}])
        append_artifact(db, case, "cost", bound)
        db.commit()
        baseline = latest_artifacts(db, case)
        exported = export_artifact(db, case, db.get(Item, bom["itemId"]), "xlsx")
    copied = client.post(OFFICE, json={"fileId": exported["exportId"]})
    assert copied.status_code == 200, copied.text
    copied = copied.json()
    mapping = copied["source"].get("templateMapping")
    assert mapping and mapping["kind"] == "bom"
    locator = mapping["fields"]["rows.0.quantityPerPiece"]
    updated = client.put(OFFICE + "/" + copied["documentId"], json={"baseVersion": 1, "baseHash": copied["sha256"],
        "operations": [{"op": "set_cell", **locator, "value": 3}]})
    assert updated.status_code == 200, updated.text
    assert updated.json()["fieldMapping"]["status"] == "mapped"
    with SessionLocal() as db:
        latest = latest_artifacts(db, case)
        assert latest["bom"]["content"]["rows"][0]["quantityPerPiece"] == "3"
        assert latest["cost"]["version"] == baseline["cost"]["version"] + 1
        assert latest["quotation"]["version"] == baseline["quotation"]["version"] + 1
        assert latest["cost"]["content"]["lines"][0]["amountCny"] == "108"
        assert latest["quotation"]["content"]["unitPriceUsd"] == "20.00"
        assert latest["bom"]["content"]["rows"][0]["sourceId"] == "office-bom-price-source"
    tampered = client.put(OFFICE + "/" + copied["documentId"], json={"baseVersion": 2, "baseHash": updated.json()["sha256"],
        "operations": [{"op": "set_cell", "sheet": "BOM", "cell": "I2", "value": "invented-source"}]})
    assert tampered.status_code == 200
    assert tampered.json()["fieldMapping"]["status"] == "mapping_conflict"
    with SessionLocal() as db:
        assert latest_artifacts(db, case)["bom"]["content"]["rows"][0]["sourceId"] == "office-bom-price-source"
