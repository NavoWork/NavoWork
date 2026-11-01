"""Opt-in real image/VLM acceptance; see README.md next to this file.

No provider doubles or injected transports. Ordinary runs skip before fixtures
or provider requests. Configured provider failures are failures, never skips.
"""
from io import BytesIO
import hashlib
import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("NAVOWORK_LIVE_RESEARCH") != "1",
    reason="Live research acceptance not executed: NAVOWORK_LIVE_RESEARCH=1 required",
)

CASE = "/api/v1/workspaces/ws_demo/inquiries/inq_demo_bag"


def _require_configuration(names, *, image=False):
    missing = [name for name in names if not os.getenv(name)]
    if image and not any(os.getenv(name) for name in ("IMAGE_API_KEY", "IMAGE_MODEL_API_KEY", "MODEL_API_KEY")):
        missing.append("IMAGE_API_KEY (or IMAGE_MODEL_API_KEY / MODEL_API_KEY)")
    if missing:
        pytest.skip("Live research acceptance not executed: missing " + ", ".join(missing))


def _ok(response):
    # Only emit internal error codes/status, never provider bodies or credentials.
    if response.status_code != 200:
        try:
            payload = response.json()
            code = (payload.get("error") or {}).get("code", "unknown")
        except (ValueError, AttributeError, TypeError):
            code = "non-json-response"
        pytest.fail(f"Research API returned HTTP {response.status_code}; code={code}", pytrace=False)
    return response.json()


def _revision(client):
    return _ok(client.get(CASE))["currentRevision"]


def _synthetic_bom_png():
    from PIL import Image, ImageDraw, ImageFont

    for filename in ("C:/Windows/Fonts/arial.ttf", "DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(filename, 28)
            break
        except OSError:
            pass
    else:
        font = ImageFont.load_default(size=28)
    image = Image.new("RGB", (1700, 620), "white")
    draw = ImageDraw.Draw(image)
    draw.text((35, 30), "SIMULATED BOM - SYNTHETIC TEST INPUT", font=font, fill="black")
    draw.text((35, 80), "NOT A SUPPLIER QUOTE. All values are invented for software testing.", font=font, fill="black")
    columns = [35, 330, 590, 825, 1040, 1390]
    table = [
        ["Material", "Spec", "Quantity", "Unit", "Unit price CNY", "Subtotal CNY"],
        ["Canvas", "600D", "2.00", "m", "10.00", "20.00"],
        ["Zipper", "No.5", "1.00", "pc", "3.00", "3.00"],
    ]
    for index, row in enumerate(table):
        y = 170 + index * 85
        for x, value in zip(columns, row):
            draw.text((x, y), value, font=font, fill="black")
        draw.line((30, y + 55, 1665, y + 55), fill="gray", width=2)
    draw.text((1040, 460), "TOTAL CNY 23.00", font=font, fill="black")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_live_concept_image_and_editable_proposal(client, other_client):
    _require_configuration(["IMAGE_MODEL"], image=True)
    from PIL import Image
    from docx import Document
    from app.db import SessionLocal
    from app.models import Case
    from app.workbench import append_artifact

    with SessionLocal() as db:
        case = db.get(Case, "inq_demo_bag")
        spec = append_artifact(db, case, "spec", {"fields": {
            "product": "canvas tote", "logo": "neutral empty logo placeholder",
        }}, title="SIMULATED live acceptance specification")
        db.commit()
    result = _ok(client.post(CASE + "/workbench/research/concepts", json={
        "baseRevision": _revision(client), "spec_version_id": spec["itemId"], "base_version": 0,
        "prompt": "A simple canvas tote product concept illustration for a synthetic software acceptance test. Use a neutral empty logo placeholder.",
    }))
    assert result.get("status") == "needs_review", f"Concept generation failed; code={result.get('code', 'unknown')}"
    content = result["artifact"]["content"]
    assert content["specVersionId"] == spec["itemId"]
    assert content["conceptOnly"] is True and content["accepted"] is False
    assert content["sampleApproved"] is False and content["productionReleased"] is False
    downloaded = client.get(result["export"]["downloadUrl"])
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == content["sha256"]
    with Image.open(BytesIO(downloaded.content)) as image:
        assert image.format in ("PNG", "JPEG") and min(image.size) > 0
        image.verify()
    proposal_download = client.get(result["proposalExport"]["downloadUrl"])
    assert proposal_download.status_code == 200
    proposal = Document(BytesIO(proposal_download.content))
    assert len(proposal.inline_shapes) == 1
    text = " ".join(paragraph.text for paragraph in proposal.paragraphs)
    snapshot = result["export"]["snapshotHash"]
    assert result["proposalExport"]["snapshotHash"] == snapshot
    assert snapshot in text and spec["itemId"] in text
    assert any("canvas tote" in cell.text for table in proposal.tables for row in table.rows for cell in row.cells)
    for export in (result["export"], result["proposalExport"]):
        assert other_client.get(export["downloadUrl"]).status_code == 404
    saved = _ok(client.get(CASE + "/workbench/research"))
    assert any(attempt["status"] == "succeeded" for attempt in saved["imageAttempts"])


def test_live_bom_reads_uploaded_image_bytes_as_unapproved_candidate(client, other_client):
    _require_configuration(["MODEL_NAME", "MODEL_API_KEY"])
    image = _synthetic_bom_png()
    uploaded = _ok(client.post(CASE + "/evidence", data={"sourceRole": "internal_note"},
        files={"file": ("SIMULATED-BOM.png", image, "image/png")}))
    candidate = _ok(client.post(CASE + "/workbench/research/bom-candidates", json={
        "baseRevision": _revision(client), "evidenceId": uploaded["id"],
    }))
    assert candidate["source"]["sha256"] == hashlib.sha256(image).hexdigest()
    assert candidate["source"]["file_ref"]["file_id"] == uploaded["id"]
    assert candidate["raw_text"].strip() and candidate["rows"]
    # This is a provider integration check, not an OCR accuracy benchmark.
    for row in candidate["rows"]:
        assert row.get("material_name") and row["source"]["raw_text"].strip()
        assert row["source"]["kind"] == "visual_row_text"
    assert candidate["validation"]["needs_review"] is True
    assert candidate["validation"]["price_approved"] is False
    saved = _ok(client.get(CASE + "/workbench/research"))
    assert any(row["id"] == candidate["id"] for row in saved["bomCandidates"])
    artifacts = _ok(client.get(CASE + "/workbench"))["artifacts"]
    assert "cost" not in artifacts and "quotation" not in artifacts
    assert other_client.get(CASE + "/workbench/research").status_code == 404
