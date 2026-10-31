from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile
import pytest
from openpyxl import load_workbook
from pypdf import PdfReader
from docx import Document

from navowork_agent.contracts import Fact, ExecutionContext
from navowork_agent.adapters.local import LocalAdapter
from navowork_agent.tools.service import ToolService
from navowork_agent.tools.pricing import calculate_quote, PricingInput
from support import make_adapter, base_snapshot, change_snapshot, publish, invoke, baselines, REPO, INPUTS


def test_real_files_golden_and_resume(tmp_path):
    # The harness alone opens the oracle. No expected data enters the product tool context.
    expected = json.loads((REPO / "test/expected/quote-golden.json").read_text())["results"]
    a = make_adapter(tmp_path)
    svc = ToolService(a)
    snap = base_snapshot(a)
    initial_args = {"snapshot": snap.model_dump(mode="json"), "baselines": baselines(a), "intent": "initial"}
    first = invoke(svc, "publish_documents", initial_args, "initial")
    assert first.status == "needs_review", first
    assert len(first.outputs) == 4, first
    assert first.data["pricing"]["quote"]["unit_usd"] == expected["supplier_a_v1"]["unit_usd"]
    assert first.data["pricing"]["quote"]["total_usd"] == expected["supplier_a_v1"]["total_usd"]
    assert invoke(svc, "publish_documents", initial_args, "initial") == first
    original = {f.file_id: a.read_bytes(f.file_id) for f in first.outputs}
    missing = publish(svc, change_snapshot(a, snap), "confirmed_change")
    assert missing.status == "needs_info", missing
    assert missing.data["pricing"]["quote"] is None
    assert missing.questions
    assert len(missing.outputs) == 4
    # Restart adapter to verify durable versions/results; then supply the later email.
    a = LocalAdapter(tmp_path, a.context().model_copy(update={"run_id": "r_resumed"}))
    svc = ToolService(a)
    updated = publish(svc, change_snapshot(a, snap, priced=True), "confirmed_change")
    assert updated.status == "needs_review", updated
    assert updated.data["pricing"]["quote"]["unit_usd"] == expected["supplier_a_v2"]["unit_usd"]
    assert updated.data["pricing"]["quote"]["total_usd"] == expected["supplier_a_v2"]["total_usd"]
    assert all(a.read_bytes(fid) == data for fid, data in original.items())
    assert all(ref.version == 3 for ref in updated.artifacts)
    assert len({ref.snapshot_hash for ref in updated.artifacts}) == 1
    for art in updated.artifacts:
        validated = invoke(svc, "validate_artifact", {"artifact_id": art.artifact_id, "version": art.version})
        assert validated.status == "needs_review", validated
    quote_ref = next(a for a in updated.artifacts if a.kind == "quotation")
    package = invoke(svc, "package_customer_files", {"artifact_id": quote_ref.artifact_id, "version": quote_ref.version})
    assert len(package.outputs) == 1, package
    with ZipFile(BytesIO(a.read_bytes(package.outputs[0].file_id))) as archive:
        assert set(archive.namelist()) == {"quotation-v3.xlsx", "quotation-v3.pdf", "delivery-manifest.json"}
        manifest = json.loads(archive.read("delivery-manifest.json"))
        assert manifest["snapshot_hash"] == quote_ref.snapshot_hash
        assert "sources" not in manifest and "snapshot" not in manifest and "pricing" not in manifest
    # Check the actual cached workbook and actual PDF, not only tool result JSON.
    cost = next(f for f in updated.outputs if f.name.startswith("cost"))
    wb = load_workbook(BytesIO(a.read_bytes(cost.file_id)), data_only=True)
    values = {row[0].value: row[1].value for row in wb.active if len(row) >= 2}
    assert values["Unit quote USD"] == 9.21 and values["Goods subtotal USD"] == 27630
    for f in updated.outputs:
        if f.name.startswith("quotation"):
            raw = a.read_bytes(f.file_id)
            if f.name.endswith("pdf"):
                text = "".join(p.extract_text() for p in PdfReader(BytesIO(raw)).pages)
            else:
                w = load_workbook(BytesIO(raw), data_only=False)
                text = " ".join(str(c.value) for ws in w for row in ws for c in row)
            assert "9.21" in text and "27630.00" in text
            assert "INTERNAL_COST_MARGIN_DO_NOT_EXPORT" not in text
            assert "Factory A" not in text and "Gross margin" not in text


def test_supplier_b_and_same_filename_changed_values(tmp_path):
    a = make_adapter(tmp_path / "b")
    b = base_snapshot(a, "B")
    assert calculate_quote(b.pricing)["quote"]["unit_usd"] == "9.03"
    assert calculate_quote(b.pricing)["quote"]["total_usd"] == "27090.00"
    # Mutate only a temporary copy while preserving its filename.
    root = tmp_path / "inputs"
    root.mkdir()
    for name in ["inquiry.eml", "factory-A-quote.xlsx"]:
        (root / name).write_bytes((INPUTS / "BAG-2026-DE-001" / name).read_bytes())
    wb = load_workbook(root / "factory-A-quote.xlsx")
    wb.active["B10"] = 57
    wb.save(root / "factory-A-quote.xlsx")
    modified = base_snapshot(make_adapter(tmp_path / "changed"), input_root=root)
    assert calculate_quote(modified.pricing)["quote"]["unit_usd"] != "8.69"


def test_baseline_idempotency_scope_and_stale_results(tmp_path):
    a = make_adapter(tmp_path)
    svc = ToolService(a)
    snap = base_snapshot(a)
    first = publish(svc, snap, key="stable")
    assert len(first.outputs) == 4
    wrong = publish(svc, snap, key="stable")
    assert wrong.code == "IDEMPOTENCY_CONFLICT"
    conflict = publish(svc, snap, "confirmed_change", bases={"spec": 0, "cost": 0, "quotation": 0})
    assert conflict.code == "BASELINE_CONFLICT"
    assert invoke(svc, "read_document", {"file_id": "another-case-file"}).code == "FILE_UNAVAILABLE"
    stale = LocalAdapter(tmp_path, a.context())
    a.update_user_facts({"correction": "new"})
    delayed = publish(ToolService(stale), snap, "confirmed_change")
    assert delayed.code == "STALE_CONTEXT"
    first_file = first.outputs[0]
    source = next(f for f in a.list_files() if f.role == "source")
    denied = invoke(ToolService(a), "edit_file", {"artifact_id": first.artifacts[0].artifact_id, "baseline": 1,
        "file_id": source.file_id, "operations": [{"op": "append_paragraph", "text": "overwrite"}]})
    assert denied.code == "ORIGINAL_READ_ONLY"


def test_partial_failure_retry_and_manual_notes(tmp_path):
    a = make_adapter(tmp_path)
    snap = base_snapshot(a)
    svc = ToolService(a, fail_formats=["pdf"])
    partial = publish(svc, snap)
    assert partial.status == "error" and len(partial.outputs) == 3
    assert partial.retryable == ["quotation.pdf"]
    quote = next(x for x in partial.artifacts if x.kind == "quotation")
    retry = invoke(ToolService(a), "export_artifact", {"artifact_id": quote.artifact_id, "version": quote.version, "format": "pdf"}, "retry-pdf")
    assert len(retry.outputs) == 1
    assert baselines(a) == {"spec": 1, "cost": 1, "quotation": 1}
    spec = next(x for x in partial.artifacts if x.kind == "spec")
    edited = invoke(ToolService(a), "edit_file", {"artifact_id": spec.artifact_id, "baseline": 1,
        "file_id": spec.files[0].file_id, "operations": [{"op": "append_paragraph", "text": "Human note keep me"}]})
    assert edited.status == "needs_review", edited
    updated = publish(ToolService(a), change_snapshot(a, snap, priced=True), "confirmed_change")
    assert len(updated.outputs) == 4
    docx = next(f for f in updated.outputs if f.name.endswith("docx"))
    doc = Document(BytesIO(a.read_bytes(docx.file_id)))
    assert "Human note keep me" in " ".join(p.text for p in doc.paragraphs)
    field_edit = invoke(ToolService(a), "edit_file", {"artifact_id": spec.artifact_id, "baseline": 3,
        "file_id": docx.file_id, "operations": [{"op": "set_table_cell", "table": 0, "row": 1, "column": 1, "text": "Manual product"}]})
    assert field_edit.status == "needs_review"
    conflicting = publish(ToolService(a), change_snapshot(a, snap, priced=True), "confirmed_change")
    assert conflicting.code == "FIELD_RECONCILIATION_REQUIRED"


def test_unknown_moq_missing_cost_and_invalid_numbers(tmp_path):
    a = make_adapter(tmp_path)
    snap = base_snapshot(a)
    unknown = snap.pricing.model_copy(update={"costs": [c.model_copy(update={"amount": Fact(value=None)}) if c.category == "local" else c for c in snap.pricing.costs]})
    assert calculate_quote(unknown)["status"] == "needs_info"
    below = snap.pricing.model_copy(update={"quantity": 10})
    assert calculate_quote(below)["reason"] == "QUANTITY_BELOW_MOQ"
    for quantity in [0, -1, 2.5, True, "3000"]:
        raw = snap.pricing.model_dump()
        raw["quantity"] = quantity
        with pytest.raises(ValueError): PricingInput.model_validate(raw)
    raw = snap.pricing.model_dump()
    raw["fx_cny_per_usd"]["value"] = "NaN"
    with pytest.raises(ValueError): calculate_quote(PricingInput.model_validate(raw))
    # Actual incomplete/independent Case sources are readable but never grant absent prices.
    for case in ("BAG-2026-DE-002", "BAG-2026-DE-003"):
        other = make_adapter(tmp_path / case, case)
        for path in (INPUTS / case).iterdir():
            ref = other.import_source(path)
            assert other.read_document(ref.file_id)["sections"]
        assert invoke(ToolService(other), "read_document", {"file_id": a.list_files()[0].file_id}).code == "FILE_UNAVAILABLE"


def test_source_docx_is_copied_before_agent_edits(tmp_path):
    source_path = tmp_path / "customer-spec.docx"
    original = Document()
    original.add_paragraph("Requested material: canvas")
    original.save(source_path)
    adapter = make_adapter(tmp_path / "case")
    source = adapter.import_source(source_path)
    source_bytes = adapter.read_bytes(source.file_id)
    service = ToolService(adapter)

    copied = invoke(service, "create_working_copy", {"file_id": source.file_id}, "copy-source-docx")
    assert copied.status == "needs_review" and len(copied.artifacts) == 1
    assert copied.outputs[0].role == "working"
    artifact = copied.artifacts[0]
    edited = invoke(service, "edit_file", {"artifact_id": artifact.artifact_id, "baseline": artifact.version,
        "file_id": copied.outputs[0].file_id, "operations": [{"op": "append_paragraph", "text": "Reviewed by agent"}]}, "edit-working-docx")
    assert edited.status == "needs_review" and edited.outputs[0].role == "working"
    validated = invoke(service, "validate_artifact", {"artifact_id": artifact.artifact_id, "version": edited.artifacts[0].version})
    assert validated.status == "needs_review"
    result_doc = Document(BytesIO(adapter.read_bytes(edited.outputs[0].file_id)))
    assert "Reviewed by agent" in " ".join(p.text for p in result_doc.paragraphs)
    assert adapter.read_bytes(source.file_id) == source_bytes


def test_forged_confirmation_citations_and_prompt_injection(tmp_path):
    a = make_adapter(tmp_path)
    snap = base_snapshot(a)
    bad = snap.model_copy(update={"fields": {**snap.fields, "material": Fact(value="silk", user_fact="made_up")}})
    assert publish(ToolService(a), bad).code == "UNCONFIRMED_USER_FACT"
    ref = a.import_source(INPUTS / "adversarial/prompt-injection.eml")
    read = invoke(ToolService(a), "read_document", {"file_id": ref.file_id})
    assert read.status == "success"
    assert not a.list_artifacts()
    assert "send_email" not in [s["function"]["name"] for s in ToolService(a).schemas()]
    forged = snap.model_dump()
    forged["fields"]["product"]["sources"][0]["excerpt"] = "not a real excerpt"
    assert publish(ToolService(a), type(snap).model_validate(forged)).code == "SOURCE_LOCATION"
