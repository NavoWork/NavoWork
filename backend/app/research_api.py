"""Authenticated Case research, image retry and human BOM correction endpoints."""
from __future__ import annotations

from pydantic import ValidationError

from .core import decode, fail, item_view, items
from .models import Item
from .research_tools import CompareArgs, ConceptArgs, create_analysis, source_sections


def _editable(case, body):
    if case.active_run_id or decode(case.payload).get("pendingRunId"):
        fail("RUN_IN_PROGRESS", "请先完成当前任务。", 409)
    if type(body.get("baseRevision")) is not int or body.get("baseRevision") != case.current_revision:
        fail("REVISION_CONFLICT", "项目版本已变化。", 409)


def research_routes(request, db, user, case, tail, body, form=None):
    if not tail or tail[0] != "research":
        return None
    path, method = tail[1:], request.method
    if len(path) == 2 and path[0] == "sources" and method == "GET":
        try:
            row, value, source_hash, sections = source_sections(db, case, path[1])
        except ValueError as exc:
            fail("RESEARCH_SOURCE_UNAVAILABLE", str(exc), 404)
        except Exception:
            fail("RESEARCH_SOURCE_UNREADABLE", "该来源无法提供文字定位，请选择可读文档；表格图片请使用 BOM 识别。", 422)
        return {"id": row.id, "version": row.version, "sha256": source_hash,
                "title": value.get("title"), "sections": sections}
    if not path and method == "GET":
        kinds = {"competitor_analysis", "design_brief", "concept_image"}
        return {"artifacts": [item_view(row) for row in items(db, "artifact", case_id=case.id)
                if decode(row.payload).get("kind") in kinds],
            "imageAttempts": [item_view(row) for row in items(db, "image_attempt", case_id=case.id)],
            "bomCandidates": [item_view(row) for row in items(db, "bom_candidate", case_id=case.id)]}
    try:
        if len(path) == 3 and path[0] == "design-briefs" and path[2] == "adopt" and method == "POST":
            from sqlalchemy import text
            db.execute(text("BEGIN IMMEDIATE"))
            db.refresh(case)
            _editable(case, body)
            from .workbench import append_artifact, latest_artifact, commit_revision
            brief = latest_artifact(db, case, "design_brief")
            if not brief or brief["itemId"] != path[1]:
                fail("ARTIFACT_CONFLICT", "设计简报版本已变化。", 409)
            indices = body.get("indices")
            suggestions = brief["content"].get("competitorSuggestions", [])
            if (not isinstance(indices, list) or not 1 <= len(indices) <= len(suggestions)
                or any(type(index) is not int or index < 0 or index >= len(suggestions) for index in indices)
                or len(indices) != len(set(indices))):
                fail("INVALID_INPUT", "请选择当前简报中的候选建议。", 422)
            content = {**brief["content"], "adoptedSuggestions": [suggestions[index] for index in indices],
                "adoptedBy": user.id, "adoptedIndices": indices,
                "customerAccepted": False, "manufacturingFeasibility": "unverified",
                "pending": ["User selected design direction; specification/BOM changes require explicit mapped fields and factory confirmation"]}
            artifact = append_artifact(db, case, "design_brief", content, title="已采纳方向的设计简报草稿")
            commit_revision(db, case, "用户采纳候选设计方向；未推测修改规格、BOM 或工厂成本", node="requirements")
            db.commit()
            return {"status": "needs_review", "artifact": artifact,
                "summary": "已记录用户采纳项；制造可行性、规格映射与成本仍待核对。"}
        if path == ["competitors"] and method == "POST":
            from sqlalchemy import text
            db.execute(text("BEGIN IMMEDIATE"))
            db.refresh(case)
            _editable(case, body)
            args = CompareArgs.model_validate({key: value for key, value in body.items() if key != "baseRevision"})
            result = create_analysis(db, case, args)
            from .workbench import commit_revision
            commit_revision(db, case, result["summary"], node="requirements")
            db.commit()
            return result
        if path == ["concepts"] and method == "POST":
            _editable(case, body)
            args = ConceptArgs.model_validate({key: value for key, value in body.items() if key != "baseRevision"})
            case_id, user_id, revision = case.id, user.id, case.current_revision
            db.rollback()
            from .concept_images import create_concept
            return create_concept(case_id=case_id, user_id=user_id, expected_revision=revision,
                spec_version_id=args.spec_version_id, prompt=args.prompt, base_version=args.base_version)
        if len(path) == 3 and path[0] == "image-attempts" and path[2] == "retry" and method == "POST":
            _editable(case, body)
            row = db.get(Item, path[1])
            if not row or row.kind != "image_attempt" or row.case_id != case.id:
                fail("NOT_FOUND", "图像尝试不存在。", 404)
            attempt = item_view(row)
            if attempt.get("status") != "failed" or not attempt.get("retryable"):
                fail("NOT_RETRYABLE", "该图像尝试不可重试。", 409)
            case_id, user_id, revision = case.id, user.id, case.current_revision
            db.rollback()
            from .concept_images import create_concept
            return create_concept(case_id=case_id, user_id=user_id, expected_revision=revision,
                spec_version_id=attempt["specVersionId"], prompt=attempt["prompt"],
                base_version=attempt["baseVersion"], retry_of=row.id)
        if path == ["bom-candidates"] and method == "POST":
            _editable(case, body)
            row = db.get(Item, str(body.get("evidenceId") or ""))
            if not row or row.kind != "evidence" or row.case_id != case.id:
                fail("NOT_FOUND", "BOM 原件不存在。", 404)
            from .bom_vision_service import recognize_case_evidence, save_case_candidate
            # Provider work cannot authorize a late write into a newer Case.
            source_id, source_payload = row.id, row.payload
            result = recognize_case_evidence(db, case, row, actor=user.id, persist=False)
            db.rollback()
            from sqlalchemy import text
            db.execute(text("BEGIN IMMEDIATE"))
            db.refresh(case)
            _editable(case, body)
            current_source = db.get(Item, source_id)
            if not current_source or current_source.payload != source_payload:
                fail("SOURCE_VERSION", "识别期间原件版本已变化，请重新识别。", 409)
            result = save_case_candidate(db, case, result)
            db.commit()
            return result
        if len(path) == 2 and path[0] == "bom-candidates" and method == "PATCH":
            from sqlalchemy import text
            db.execute(text("BEGIN IMMEDIATE"))
            db.refresh(case)
            _editable(case, body)
            row = db.get(Item, path[1])
            if not row or row.kind != "bom_candidate" or row.case_id != case.id:
                fail("NOT_FOUND", "BOM 候选不存在。", 404)
            from .bom_vision_service import correct_case_candidate
            result = correct_case_candidate(db, case, row, expected_revision=body.get("expectedVersion"),
                patches=body.get("patches"), reason=body.get("reason"), actor=user.id)
            db.commit()
            return result
    except (ValueError, ValidationError) as exc:
        db.rollback()
        fail(getattr(exc, "code", "RESEARCH_VALIDATION_FAILED"), str(exc)[:500],
             409 if getattr(exc, "status", None) == "conflict" else 422)
    except Exception as exc:
        db.rollback()
        if type(exc).__name__ == "AdapterError":
            fail("VISION_PROVIDER_UNAVAILABLE", str(exc), 422)
        raise
    fail("NOT_FOUND", "研究接口不存在。", 404)
