"""Sourced competitor observations and optional concept/BOM tools for the native workbench."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .core import decode, item_view, items
from .models import Blob, Item, now


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Observation(StrictModel):
    evidence_id: str
    competitor: str = Field(min_length=1, max_length=120)
    attribute: str = Field(min_length=1, max_length=120)
    excerpt: str = Field(min_length=1, max_length=2000)
    locator: dict = Field(default_factory=dict)
    observed_at: str = Field(description="ISO date/time of the source observation")
    applicable_scope: str = Field(min_length=1, max_length=500)


class Suggestion(StrictModel):
    text: str = Field(min_length=1, max_length=1000)
    observation_indices: list[int] = Field(min_length=1, max_length=20)


class CompareArgs(StrictModel):
    observations: list[Observation] = Field(min_length=1, max_length=50)
    suggestions: list[Suggestion] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    base_version: int = Field(default=0, ge=0)


class ConceptArgs(StrictModel):
    spec_version_id: str
    prompt: str = Field(min_length=1, max_length=6000)
    base_version: int = Field(default=0, ge=0)


class BomArgs(StrictModel):
    evidence_id: str


MODELS = {"create_competitor_analysis": CompareArgs, "generate_concept_image": ConceptArgs,
          "recognize_bom_image": BomArgs}
DESCRIPTIONS = {
    "create_competitor_analysis": "Compare curated Case competitor sources. Every observation requires a verbatim excerpt, exact locator, observation date and scope. Suggestions are explicitly unverified design ideas, never supplier cost, confirmation, or source facts.",
    "generate_concept_image": "Prepare a PNG/JPEG product concept draft bound to the current specification. For demo cases with imageCapability.mode=preset, load bundled demo artwork without an image API; cannot redraw or revise its pixels. Other cases require an image provider. Never constitutes engineering or physical sample approval.",
    "recognize_bom_image": "Read a Case supplier/internal PNG/JPEG BOM as candidate rows with uncertainty and totals checks. Human review is required; this does not approve price or set verified business costs.",
}
TOOL_SCHEMAS = [{"type": "function", "function": {"name": name, "description": DESCRIPTIONS[name],
                 "parameters": model.model_json_schema()}} for name, model in MODELS.items()]


def frozen_sources(db, job, evidence_ids):
    manifest = {entry["id"]: entry for entry in decode(job.payload).get("evidence", [])}
    for source_id in evidence_ids:
        frozen = manifest.get(source_id)
        row = db.get(Item, source_id)
        current = decode(row.payload) if row else {}
        if (not frozen or not row or current.get("sha256") != frozen.get("sha256")
            or current.get("blobId") != frozen.get("blobId")):
            raise ValueError("Source is unavailable in this run's frozen input manifest")


def source_sections(db, case, evidence_id):
    row = db.get(Item, evidence_id)
    if not row or row.kind != "evidence" or row.case_id != case.id:
        raise ValueError("Source evidence is unavailable in this Case")
    value = item_view(row)
    if value.get("blobId"):
        blob = db.get(Blob, value["blobId"])
        if not blob or blob.case_id != case.id:
            raise ValueError("Source blob is unavailable")
        data = Path(blob.path).read_bytes()
        if hashlib.sha256(data).hexdigest() != blob.sha256 or value.get("sha256") != blob.sha256:
            raise ValueError("Source integrity check failed")
        from navowork_agent.tools.readers import read_file
        sections = read_file(Path(blob.path), blob.media_type)["sections"]
        source_hash = blob.sha256
    else:
        text = value.get("text", "")
        source_hash = hashlib.sha256(text.encode()).hexdigest()
        if value.get("sha256") != source_hash:
            raise ValueError("Source integrity check failed")
        sections = [{"locator": {"line": i}, "text": line} for i, line in enumerate(text.splitlines(), 1)]
    return row, value, source_hash, sections


def create_analysis(db, case, args, *, run_id=None):
    from .workbench import append_artifact, latest_artifact
    latest = latest_artifact(db, case, "competitor_analysis")
    if (latest or {}).get("version", 0) != args.base_version:
        raise ValueError("Competitor analysis baseline changed")
    observations, sources = [], {}
    for obs in args.observations:
        row, value, source_hash, sections = source_sections(db, case, obs.evidence_id)
        if not any(section["locator"] == obs.locator and obs.excerpt in section["text"] for section in sections):
            raise ValueError("Observation excerpt does not occur at the declared source locator")
        try:
            observed = datetime.fromisoformat(obs.observed_at.replace("Z", "+00:00"))
            observed = observed.replace(tzinfo=timezone.utc) if observed.tzinfo is None else observed
            if observed > datetime.now(timezone.utc):
                raise ValueError()
        except ValueError:
            raise ValueError("Observation date must be a valid non-future ISO date") from None
        sources[row.id] = {"evidenceId": row.id, "version": row.version, "sha256": source_hash,
            "title": value.get("title"), "capturedAt": value.get("createdAt") or row.created_at,
            "observedAt": obs.observed_at, "applicableScope": obs.applicable_scope}
        observations.append({**obs.model_dump(mode="json"), "sourceVersion": row.version,
            "sha256": source_hash, "classification": "quoted_observation", "independentlyVerified": False})
    for suggestion in args.suggestions:
        if any(index < 0 or index >= len(observations) for index in suggestion.observation_indices):
            raise ValueError("Suggestion references an unavailable observation")
    content = {"sources": list(sources.values()), "observations": observations,
        "suggestions": [{**idea.model_dump(), "classification": "unverified_design_suggestion"} for idea in args.suggestions],
        "assumptions": args.assumptions, "ownCostBasis": False, "supplierPriceApproved": False,
        "scope": "curated_sources_only", "coverage": "No claim of exhaustive or live market research",
        "status": "needs_review"}
    content["snapshotHash"] = hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    artifact = append_artifact(db, case, "competitor_analysis", content, title="有来源的竞品比较", run_id=run_id)
    spec = latest_artifact(db, case, "spec") or {}
    brief = append_artifact(db, case, "design_brief", {"analysisVersionId": artifact["itemId"],
        "specVersionId": spec.get("itemId"), "customerRequirements": (spec.get("content") or {}).get("fields") or {},
        "competitorSuggestions": content["suggestions"], "adoptedSuggestions": [],
        "immutableRequirements": [], "pending": ["Factory feasibility and material/cost basis remain unverified"],
        "assumptions": args.assumptions, "manufacturingFeasibility": "unverified", "customerAccepted": False},
        title="候选设计简报", run_id=run_id)
    return {"status": "needs_review", "summary": "已保存带来源、日期与适用范围的竞品比较和候选设计简报；不作为自家成本或制造承诺。",
            "artifact": artifact, "designBrief": brief}


def call_research_tool(toolbox, name, arguments):
    if name not in MODELS:
        return None
    if toolbox.node not in (None, "requirements"):
        return {"status": "blocked", "summary": "竞品、设计与 BOM 识别仅在需求阶段可写入。"}
    try:
        args = MODELS[name].model_validate(arguments)
        if name == "generate_concept_image":
            from .concept_images import create_concept
            with toolbox._tx() as (db, case, user, run, job):
                expected_revision = case.current_revision
            result = create_concept(case_id=toolbox.case_id, user_id=toolbox.user_id,
                expected_revision=expected_revision, run_id=toolbox.run_id,
                work_item_id=toolbox.work_item_id, generation=toolbox.generation,
                spec_version_id=args.spec_version_id, prompt=args.prompt, base_version=args.base_version)
            with toolbox._tx(write=True) as (db, case, user, run, job):
                toolbox._log(db, name, args.model_dump(), result)
            return result
        if name == "recognize_bom_image":
            from .bom_vision_service import recognize_case_evidence, save_case_candidate
            with toolbox._tx() as (db, case, user, run, job):
                frozen_sources(db, job, [args.evidence_id])
                evidence = db.get(Item, args.evidence_id)
                if not evidence:
                    raise ValueError("BOM evidence is unavailable")
                candidate = recognize_case_evidence(db, case, evidence, actor=user.id, persist=False)
            with toolbox._tx(write=True) as (db, case, user, run, job):
                candidate = save_case_candidate(db, case, candidate)
                result = {"status": "needs_review", "summary": candidate["summary"], "candidate": candidate}
                toolbox._log(db, name, args.model_dump(), result)
            return result
        with toolbox._tx(write=True) as (db, case, user, run, job):
            if name == "create_competitor_analysis":
                frozen_sources(db, job, [obs.evidence_id for obs in args.observations])
                result = create_analysis(db, case, args, run_id=run.id)
            toolbox._log(db, name, args.model_dump(), result)
            return result
    except (ValidationError, ValueError) as exc:
        return {"status": getattr(exc, "status", "error"), "code": getattr(exc, "code", "RESEARCH_VALIDATION_FAILED"), "summary": str(exc)[:500]}
    except Exception as exc:
        code = getattr(exc, "code", str(exc) if type(exc).__name__ == "AdapterError" else "RESEARCH_TOOL_FAILED")
        return {"status": getattr(exc, "status", "error"), "code": code,
                "summary": "研究或视觉工具未完成，请核对输入和 provider 配置后重试。"}
