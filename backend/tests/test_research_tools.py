"""Actual persisted research/artifact/export services; image and VLM providers are offline doubles."""
from io import BytesIO
from pathlib import Path
import base64
import json

import pytest

BASE = "/api/v1/workspaces/ws_demo"
CASE = BASE + "/inquiries/inq_demo_bag"


def revision(client):
    return client.get(CASE).json()["currentRevision"]


def evidence(client, text="Rival A uses recycled canvas and a front zip pocket. Retail price USD 49."):
    response = client.post(CASE + "/evidence", json={"title": "Archived rival catalogue", "sourceRole": "internal_note", "text": text})
    assert response.status_code == 200, response.text
    return response.json()


def compare_body(source, rev):
    return {"baseRevision": rev, "base_version": 0, "observations": [{"evidence_id": source["id"],
        "competitor": "Rival A", "attribute": "fabric", "excerpt": "recycled canvas",
        "locator": {"line": 1}, "observed_at": "2026-01-01", "applicable_scope": "archived European retail catalogue; not supplier cost"}],
        "suggestions": [{"text": "Explore a canvas option; feasibility and costing require factory review", "observation_indices": [0]}],
        "assumptions": ["A retail catalogue does not establish our material cost or manufacturing capability"]}


def test_competitor_observations_are_sourced_separate_from_design_and_cost(client, other_client):
    source = evidence(client)
    body = compare_body(source, revision(client))
    created = client.post(CASE + "/workbench/research/competitors", json=body)
    assert created.status_code == 200, created.text
    result = created.json()
    assert result["status"] == "needs_review"
    content = result["artifact"]["content"]
    assert content["sources"][0]["sha256"] == source["sha256"]
    assert content["observations"][0]["classification"] == "quoted_observation"
    assert content["suggestions"][0]["classification"] == "unverified_design_suggestion"
    assert content["ownCostBasis"] is False and content["supplierPriceApproved"] is False
    view = client.get(CASE + "/workbench").json()
    assert "competitor_analysis" in view["artifacts"] and "design_brief" in view["artifacts"]
    assert "cost" not in view["artifacts"] and "quotation" not in view["artifacts"]
    brief = result["designBrief"]
    assert brief["content"]["adoptedSuggestions"] == []
    adoption = client.post(CASE + f"/workbench/research/design-briefs/{brief['itemId']}/adopt",
        json={"baseRevision": revision(client), "indices": [0]})
    assert adoption.status_code == 200, adoption.text
    assert len(adoption.json()["artifact"]["content"]["adoptedSuggestions"]) == 1
    assert adoption.json()["artifact"]["content"]["customerAccepted"] is False
    assert client.post(CASE + f"/workbench/research/design-briefs/{brief['itemId']}/adopt",
        json={"baseRevision": revision(client), "indices": [0]}).status_code == 409
    assert "spec" not in client.get(CASE + "/workbench").json()["artifacts"]
    assert other_client.get(CASE + "/workbench/research").status_code == 404
    retrieved_source = client.get(CASE + "/workbench/research/sources/" + source["id"])
    assert retrieved_source.status_code == 200 and retrieved_source.json()["sections"][0]["locator"] == {"line": 1}
    assert other_client.get(CASE + "/workbench/research/sources/" + source["id"]).status_code == 404
    assert client.post(CASE + "/workbench/research/competitors", json=body).status_code == 409
    forged = compare_body(source, revision(client))
    forged["base_version"] = 1
    forged["observations"][0]["excerpt"] = "waterproof certified production fabric"
    assert client.post(CASE + "/workbench/research/competitors", json=forged).status_code == 422
    forged["observations"][0]["excerpt"] = "recycled canvas"
    forged["own_cost_cny"] = "1"
    assert client.post(CASE + "/workbench/research/competitors", json=forged).status_code == 422
    forged.pop("own_cost_cny")
    forged["observations"][0]["evidence_id"] = "another_case_evidence"
    assert client.post(CASE + "/workbench/research/competitors", json=forged).status_code == 422


def add_spec():
    from app.db import SessionLocal
    from app.models import Case
    from app.workbench import append_artifact
    with SessionLocal() as db:
        case = db.get(Case, "inq_demo_bag")
        spec = append_artifact(db, case, "spec", {"fields": {"product": "canvas tote", "logo": "small green logo"}}, title="Specification")
        db.commit()
        return spec


def png():
    from PIL import Image
    stream = BytesIO()
    Image.new("RGB", (48, 48), "green").save(stream, format="PNG")
    return stream.getvalue()


class ImageProvider:
    model = "offline-image-test"

    def generate(self, prompt):
        assert "Specification version" in prompt
        return {"data": [{"b64_json": base64.b64encode(png()).decode(), "output_format": "png"}]}


def test_concept_failure_retry_preserves_spec_binding_and_real_export(client, other_client, monkeypatch):
    from app import concept_images
    spec = add_spec()
    for key in ("IMAGE_API_KEY", "IMAGE_MODEL_API_KEY", "MODEL_API_KEY", "IMAGE_MODEL"):
        monkeypatch.delenv(key, raising=False)
    body = {"baseRevision": revision(client), "spec_version_id": spec["itemId"], "prompt": "Canvas tote with small green logo", "base_version": 0}
    failed = client.post(CASE + "/workbench/research/concepts", json=body)
    assert failed.status_code == 200, failed.text
    assert failed.json()["code"] == "IMAGE_MODEL_NOT_CONFIGURED"
    assert failed.json()["attempt"]["status"] == "failed"
    assert "concept_image" not in client.get(CASE + "/workbench").json()["artifacts"]
    actual_generate = concept_images.generate_image
    monkeypatch.setattr(concept_images, "generate_image", lambda prompt, **kwargs: actual_generate(prompt, provider=ImageProvider()))
    retried = client.post(CASE + f"/workbench/research/image-attempts/{failed.json()['attempt']['id']}/retry", json={"baseRevision": revision(client)})
    assert retried.status_code == 200, retried.text
    result = retried.json()
    assert result["status"] == "needs_review"
    content = result["artifact"]["content"]
    assert content["specVersionId"] == spec["itemId"] and content["conceptOnly"] is True
    assert content["accepted"] is False and content["sampleApproved"] is False
    url = result["export"]["downloadUrl"]
    assert client.get(url).content == png()
    assert other_client.get(url).status_code == 404
    assert result["proposalExport"]["snapshotHash"] == result["export"]["snapshotHash"]
    from docx import Document
    proposal = Document(BytesIO(client.get(result["proposalExport"]["downloadUrl"]).content))
    assert len(proposal.inline_shapes) == 1
    assert spec["itemId"] in " ".join(paragraph.text for paragraph in proposal.paragraphs)
    assert any("canvas tote" in cell.text for table in proposal.tables for row in table.rows for cell in row.cells)
    attempts = client.get(CASE + "/workbench/research").json()["imageAttempts"]
    assert {a["status"] for a in attempts} == {"failed", "succeeded"}


def test_late_concept_provider_cannot_commit_after_spec_changes(client):
    from app.concept_images import create_concept, ConceptImageError
    from app.db import SessionLocal
    from app.models import Case
    from app.workbench import append_artifact
    spec = add_spec()
    with SessionLocal() as db:
        case = db.get(Case, "inq_demo_bag")
        actor = case.owner_id

    class LateProvider(ImageProvider):
        def generate(self, prompt):
            with SessionLocal() as db:
                append_artifact(db, db.get(Case, "inq_demo_bag"), "spec", {"fields": {"product": "new design"}})
                db.commit()
            return super().generate(prompt)

    with pytest.raises(ConceptImageError) as rejected:
        create_concept(case_id="inq_demo_bag", user_id=actor, expected_revision=revision(client),
            spec_version_id=spec["itemId"], prompt="Canvas tote", base_version=0, provider=LateProvider())
    assert rejected.value.code == "SPEC_VERSION_UNAVAILABLE"
    assert "concept_image" not in client.get(CASE + "/workbench").json()["artifacts"]


def test_bom_recognition_candidate_dedup_and_human_correction_cas(client, monkeypatch):
    from app.bom_vision_service import _vision_package
    *_, adapter_class = _vision_package()
    samples = Path(__file__).resolve().parents[2] / "extensions/bom-vision/samples"

    class VisionProvider:
        name = "offline-vision-test"
        def extract(self, image, mime_type):
            return (samples / "clear.fake.json").read_text(encoding="utf-8")

    monkeypatch.setattr(adapter_class, "from_environment", classmethod(lambda cls: VisionProvider()))
    uploaded = client.post(CASE + "/evidence", data={"sourceRole": "supplier_quote"},
        files={"file": ("bom.jpg", (samples / "clear.jpg").read_bytes(), "image/jpeg")})
    assert uploaded.status_code == 200, uploaded.text
    body = {"baseRevision": revision(client), "evidenceId": uploaded.json()["id"]}
    created = client.post(CASE + "/workbench/research/bom-candidates", json=body)
    assert created.status_code == 200, created.text
    candidate = created.json()
    repeated = client.post(CASE + "/workbench/research/bom-candidates", json=body)
    assert repeated.status_code == 200 and repeated.json()["id"] == candidate["id"]
    assert candidate["validation"]["needs_review"] is True and candidate["validation"]["price_approved"] is False
    patch = {"baseRevision": revision(client), "expectedVersion": 1, "reason": "Checked against the image",
        "patches": [{"row_id": "row-1", "field": "quantity", "value": "2.60"}]}
    corrected = client.patch(CASE + "/workbench/research/bom-candidates/" + candidate["id"], json=patch)
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["revision"] == 2 and corrected.json()["rows"][0]["quantity"] == "2.60"
    assert client.patch(CASE + "/workbench/research/bom-candidates/" + candidate["id"], json=patch).status_code == 422
    assert "cost" not in client.get(CASE + "/workbench").json()["artifacts"]


def test_unconfigured_bom_provider_returns_failure_and_no_candidate(client, monkeypatch):
    from app.bom_vision_service import _vision_package
    _, _, _, AdapterError, adapter_class = _vision_package()
    def unconfigured(cls):
        raise AdapterError("vision_model_not_configured")
    monkeypatch.setattr(adapter_class, "from_environment", classmethod(unconfigured))
    uploaded = client.post(CASE + "/evidence", data={"sourceRole": "supplier_quote"},
        files={"file": ("bom.png", png(), "image/png")})
    assert uploaded.status_code == 200
    response = client.post(CASE + "/workbench/research/bom-candidates", json={"baseRevision": revision(client), "evidenceId": uploaded.json()["id"]})
    assert response.status_code == 422 and response.json()["error"]["code"] == "VISION_PROVIDER_UNAVAILABLE"
    assert client.get(CASE + "/workbench/research").json()["bomCandidates"] == []


def test_direct_bom_result_cannot_commit_after_case_changes(client, monkeypatch):
    from app.bom_vision_service import _vision_package
    from app.db import SessionLocal
    from app.models import Case
    _, _, _, _, adapter_class = _vision_package()
    samples = Path(__file__).resolve().parents[2] / "extensions/bom-vision/samples"

    class LateProvider:
        name = "offline-late-result-test"

        def extract(self, image, mime_type):
            with SessionLocal() as db:
                case = db.get(Case, "inq_demo_bag")
                case.current_revision += 1
                db.commit()
            return (samples / "clear.fake.json").read_text(encoding="utf-8")

    monkeypatch.setattr(adapter_class, "from_environment", classmethod(lambda cls: LateProvider()))
    uploaded = client.post(CASE + "/evidence", data={"sourceRole": "supplier_quote"},
        files={"file": ("late-bom.png", png(), "image/png")})
    response = client.post(CASE + "/workbench/research/bom-candidates", json={
        "baseRevision": revision(client), "evidenceId": uploaded.json()["id"]})
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "REVISION_CONFLICT"
    assert client.get(CASE + "/workbench/research").json()["bomCandidates"] == []


def test_research_tools_use_native_agent_scope_and_audited_results(client):
    from test_workbench_v2 import _start
    from app.agent_tools import tool_schemas
    source = evidence(client)
    toolbox, run_id, *_ = _start(client, CASE, "requirements", "Compare the attached catalogue", revision(client))
    toolbox.node = "requirements"
    body = compare_body(source, revision(client))
    body.pop("baseRevision")
    result = toolbox.call("create_competitor_analysis", body)
    assert result["status"] == "needs_review", result
    assert result["artifact"]["runId"] == run_id
    required = {schema["function"]["name"] for schema in tool_schemas("requirements")}
    costing = {schema["function"]["name"] for schema in tool_schemas("costing")}
    assert {"create_competitor_analysis", "generate_concept_image", "recognize_bom_image"} <= required
    assert "create_competitor_analysis" not in costing
    toolbox.node = "costing"
    denied = toolbox.call("create_competitor_analysis", {**body, "base_version": 1})
    assert denied["status"] == "blocked"


def test_late_image_and_bom_provider_cannot_write_after_lease_changes(client, monkeypatch):
    from test_workbench_v2 import _start
    from app.db import SessionLocal
    from app.models import WorkItem
    from app.concept_images import create_concept, ConceptImageError
    from app.bom_vision_service import _vision_package
    spec = add_spec()
    sample_path = Path(__file__).resolve().parents[2] / "extensions/bom-vision/samples"
    uploaded = client.post(CASE + "/evidence", data={"sourceRole": "supplier_quote"},
        files={"file": ("bom.jpg", (sample_path / "clear.jpg").read_bytes(), "image/jpeg")})
    assert uploaded.status_code == 200
    toolbox, run_id, job_id, work_id, _ = _start(client, CASE, "requirements", "Generate concept", revision(client))
    toolbox.node = "requirements"

    class FencedImageProvider(ImageProvider):
        def generate(self, prompt):
            with SessionLocal() as db:
                work = db.get(WorkItem, work_id)
                work.lease_generation += 1
                db.commit()
            return super().generate(prompt)

    with pytest.raises(ConceptImageError) as fenced:
        create_concept(case_id=toolbox.case_id, user_id=toolbox.user_id, expected_revision=revision(client),
            spec_version_id=spec["itemId"], prompt="Canvas tote", base_version=0,
            run_id=run_id, work_item_id=work_id, generation=1, provider=FencedImageProvider())
    assert fenced.value.code == "STALE_CONTEXT"
    assert "concept_image" not in client.get(CASE + "/workbench").json()["artifacts"]
    # Use the current lease and prove recognition also fences its final write.
    toolbox.generation = 2

    class FencedVisionProvider:
        name = "offline-fenced-vision"
        def extract(self, image, mime_type):
            with SessionLocal() as db:
                db.get(WorkItem, work_id).lease_generation += 1
                db.commit()
            return (sample_path / "clear.fake.json").read_text(encoding="utf-8")

    *_, adapter_class = _vision_package()
    monkeypatch.setattr(adapter_class, "from_environment", classmethod(lambda cls: FencedVisionProvider()))
    result = toolbox.call("recognize_bom_image", {"evidence_id": uploaded.json()["id"]})
    assert result["status"] != "needs_review", result
    assert client.get(CASE + "/workbench/research").json()["bomCandidates"] == []
