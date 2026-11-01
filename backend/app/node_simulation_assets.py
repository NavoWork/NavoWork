"""Local roadshow research and artwork, sourced from the repository test pack."""
import hashlib
import json
from pathlib import Path

from .core import create_item, decode, encode, now, store_blob, uid
from .demo_images import preset_path
from .models import Item
from .research_tools import CompareArgs, create_analysis, source_sections
from .workbench import append_artifact

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "test" / "workbench_demo"


def demo_node_data(scenario_id):
    data = json.loads((PACK / "node-simulations.json").read_text())
    return data["scenarios"][scenario_id], data["productionTasks"]


def save_competitors(db, case, run, current, scenario_id):
    data, _ = demo_node_data(scenario_id)
    manifest = {entry["key"]: entry for entry in json.loads((PACK / "manifest.json").read_text())["entries"]}
    observations, cards = [], []
    for index, competitor in enumerate(data["competitors"]):
        key = competitor.get("fixtureKey") or f"{scenario_id}-competitor-{index}"
        evidence_id = f"ev_{case.id}_{key}"
        row = db.get(Item, evidence_id)
        if not row:
            blob = None
            if competitor.get("fixtureKey"):
                entry = manifest[key]
                path = (ROOT / entry["path"]).resolve()
                if not path.is_relative_to(PACK):
                    raise ValueError("Demo fixture path outside test pack")
                raw = path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                    raise ValueError("Demo fixture checksum mismatch")
                from .sop_api import _extract_file
                text = _extract_file(raw, path.name)
                blob = store_blob(db, raw, path.name, entry["mime"], case.id)
            else:
                text = "路演虚构竞品；非真实市场调查。\n" + "\n".join(f"{k}: {v}" for k, v in competitor.items())
            row = create_item(db, "evidence", {"title": f"[演示] {competitor['name']} 竞品快照", "sourceRole": "internal_note",
                "text": text, "blobId": blob.id if blob else None, "sha256": blob.sha256 if blob else hashlib.sha256(text.encode()).hexdigest(),
                "parseStatus": "parsed", "simulation": True, "node": "competitor", "fixtureKey": key,
                "fixturePath": manifest[key]["path"] if key in manifest else "test/workbench_demo/node-simulations.json", "createdAt": now()},
                case_id=case.id, item_id=evidence_id, status="observed")
            db.flush()
        _, _, _, sections = source_sections(db, case, row.id)
        # Quote the original section, including the PDF page/table locator.
        section = next(section for section in sections if competitor["name"] in section["text"])
        observations.append({"evidence_id": row.id, "competitor": competitor["name"], "attribute": "产品、材质、功能与零售价",
            "excerpt": section["text"][:2000], "locator": section["locator"], "observed_at": "2026-11-01",
            "applicable_scope": "路演虚构零售快照，仅作设计比较，不作为供应商成本或认证依据"})
        cards.append({**competitor, "evidenceId": row.id})
    result = create_analysis(db, case, CompareArgs.model_validate({"base_version": current.get("competitor_analysis", {}).get("version", 0),
        "observations": observations, "suggestions": [{"text": idea, "observation_indices": list(range(len(observations)))} for idea in data["suggestions"]],
        "assumptions": ["虚构竞品资料；零售价与当前 FOB 报价口径不同。"]}), run_id=run.id)
    for artifact in (result["artifact"], result["designBrief"]):
        row = db.get(Item, artifact["itemId"])
        value = decode(row.payload)
        value["content"].update(simulation=True, generationMode="local_mock")
        if artifact["kind"] == "competitor_analysis":
            value["content"]["comparisons"] = cards
        row.payload = encode(value)
    return result


def save_design_image(db, case, run, job, spec, scenario_id):
    data, _ = demo_node_data(scenario_id)
    raw = preset_path(scenario_id).read_bytes()  # No provider path or network fallback.
    blob = store_blob(db, raw, f"{scenario_id}-concept.png", "image/png", case.id)
    export_id = uid("export")
    content = {"prompt": data["designDirection"], "specVersionId": spec["itemId"],
        "specHash": hashlib.sha256(encode(spec["content"]).encode()).hexdigest(),
        "simulation": True, "generationMode": "preset", "presetId": scenario_id, "imageApiCalled": False,
        "model": f"demo-preset:{scenario_id}", "imageFileId": blob.id, "sha256": blob.sha256,
        "conceptOnly": True, "accepted": False, "sampleApproved": False, "productionReleased": False,
        "status": "needs_review", "visualAlignment": "needs_human_review",
        "downloadUrl": f"/api/v1/workspaces/{case.workspace_id}/exports/{export_id}/download"}
    artifact = append_artifact(db, case, "concept_image", content, title="产品设计图", run_id=run.id, job_id=job.id)
    create_item(db, "export", {"exportId": export_id, "status": "ready", "caseId": case.id, "artifactVersionId": artifact["itemId"],
        "format": "png", "mode": "concept_draft", "blobId": blob.id, "snapshotHash": blob.sha256,
        "downloadUrl": content["downloadUrl"], "createdAt": now()}, case_id=case.id, item_id=export_id)
    return artifact
