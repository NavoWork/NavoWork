"""Versioned, review-only concept image generation for an authorized Case."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from .core import create_item, decode, item_view, items, require_case, store_blob, uid
from .db import SessionLocal
from .models import Case, Item, Run, User, WorkItem, now
from .demo_images import preset_id, preset_path


MAX_PROMPT_CHARS = 8000
MAX_IMAGE_BYTES = 20 * 1024 * 1024
SUPPORTED_MIME = {"image/png": ("png", b"\x89PNG\r\n\x1a\n"),
                  "image/jpeg": ("jpg", b"\xff\xd8\xff")}


class ConceptImageError(ValueError):
    def __init__(self, code: str, message: str, status: str = "error"):
        super().__init__(message)
        self.code, self.status = code, status


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def image_settings() -> dict:
    key = os.getenv("IMAGE_API_KEY") or os.getenv("IMAGE_MODEL_API_KEY")
    base = (os.getenv("IMAGE_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    if not key:
        raise ConceptImageError("IMAGE_MODEL_NOT_CONFIGURED", "概念图生成未配置模型密钥。", "blocked")
    if not os.getenv("IMAGE_MODEL"):
        raise ConceptImageError("IMAGE_MODEL_NOT_CONFIGURED", "概念图生成未配置图像模型名称。", "blocked")
    parsed = urlsplit(base)
    if (parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password
        or parsed.query or parsed.fragment or (parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"))):
        raise ConceptImageError("IMAGE_ENDPOINT_INVALID", "图像服务端点必须使用 HTTPS。", "blocked")
    return {"api_key": key, "base_url": base,
            "model": os.environ["IMAGE_MODEL"]}


def image_capability(case) -> dict:
    preset = preset_id(case)
    if preset:
        ready = preset_path(preset).is_file()
        return {"configured": ready, "mode": "preset", "presetId": preset,
                "message": "预置演示图；不调用生图 API，不随提示词重新绘制。" if ready else "演示图片文件缺失"}
    try:
        config = image_settings()
        return {"configured": True, "mode": "provider", "model": config["model"]}
    except ConceptImageError:
        return {"configured": False, "mode": "provider", "message": "生图服务待接入"}


def generate_image(prompt: str, *, provider=None) -> tuple[bytes, str, str]:
    """Return (image bytes, media type, provider model) without fetching remote URLs."""
    prompt = str(prompt).strip()
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise ConceptImageError("IMAGE_PROMPT_INVALID", "设计说明不能为空且不能超过 8000 个字符。")
    full_prompt = ("Create a product concept illustration for visual discussion only. "
                   "Do not present it as a real photograph, engineering drawing, verified material, "
                   "manufacturing feasibility, or approved physical sample. Preserve the described "
                   "bag structure and branding placement. Use a neutral empty placeholder for logos; "
                   "do not invent brand text or present generated typography as original artwork. Design brief: " + prompt)
    if provider is None:
        config = image_settings()
        endpoint = config["base_url"] + "/images/generations"
        body = json.dumps({"model": config["model"], "prompt": full_prompt,
                           "size": os.getenv("IMAGE_SIZE", "1024x1024"),
                           "n": 1, "output_format": "png"}).encode("utf-8")
        request = Request(endpoint, data=body, headers={
            "Authorization": "Bearer " + config["api_key"],
            "Content-Type": "application/json", "Accept": "application/json"}, method="POST")
        try:
            with build_opener(_NoRedirect()).open(request, timeout=120) as response:
                if response.status != 200:
                    raise ConceptImageError("IMAGE_PROVIDER_FAILED", "图像服务未能生成概念图。")
                payload = json.loads(response.read(30 * 1024 * 1024))
        except HTTPError as exc:
            raise ConceptImageError("IMAGE_PROVIDER_FAILED", f"图像服务请求失败（HTTP {exc.code}）。") from None
        except (URLError, TimeoutError, OSError, json.JSONDecodeError):
            raise ConceptImageError("IMAGE_PROVIDER_FAILED", "图像服务连接失败或响应无效。") from None
        model = config["model"]
    else:
        try:
            payload = provider.generate(full_prompt)
            model = getattr(provider, "model", "injected-provider")
        except ConceptImageError:
            raise
        except Exception:
            raise ConceptImageError("IMAGE_PROVIDER_FAILED", "图像服务未能生成概念图。") from None
    try:
        entry = payload["data"][0]
        raw = entry.get("b64_json")
        if not isinstance(raw, str):
            raise ValueError
        image = base64.b64decode(raw, validate=True)
        if not image or len(image) > MAX_IMAGE_BYTES:
            raise ValueError
        fmt = entry.get("output_format", "png").lower()
        mime = "image/jpeg" if fmt in ("jpeg", "jpg") else "image/png" if fmt == "png" else None
        if not mime or not image.startswith(SUPPORTED_MIME[mime][1]):
            raise ValueError
    except (KeyError, IndexError, TypeError, ValueError):
        raise ConceptImageError("IMAGE_RESPONSE_INVALID", "图像服务返回的图片数据格式无效。") from None
    return image, mime, model


def _binding(db, case_id, user_id, expected_revision, spec_version_id, base_version, run_id=None, work_item_id=None, generation=None):
    user = db.get(User, user_id)
    if not user:
        raise ConceptImageError("CASE_SCOPE", "无权访问项目。", "blocked")
    case = require_case(db, user, case_id)
    if case.current_revision != expected_revision:
        raise ConceptImageError("STALE_CONTEXT", "项目已变化，请基于新版重新生成。", "conflict")
    if run_id:
        run, work = db.get(Run, run_id), db.get(WorkItem, work_item_id)
        if (not run or run.case_id != case.id or run.status != "running" or case.active_run_id != run.id
            or run.base_revision != expected_revision or not work or work.run_id != run.id
            or work.status != "running" or work.lease_generation != generation
            or (work.lease_expires_at and work.lease_expires_at < now())):
            raise ConceptImageError("STALE_CONTEXT", "任务或执行租约已变化。", "conflict")
    elif case.active_run_id or decode(case.payload).get("pendingRunId"):
        raise ConceptImageError("RUN_IN_PROGRESS", "请先完成当前任务。", "conflict")
    specs = [row for row in items(db, "artifact", case_id=case.id) if decode(row.payload).get("kind") == "spec"]
    spec = max(specs, key=lambda row: row.version, default=None)
    if not spec or spec.id != spec_version_id:
        raise ConceptImageError("SPEC_VERSION_UNAVAILABLE", "请选择本项目当前规格版本。", "conflict")
    versions = [row for row in items(db, "artifact", case_id=case.id) if decode(row.payload).get("kind") == "concept_image"]
    current = max((row.version for row in versions), default=0)
    if current != base_version:
        raise ConceptImageError("BASELINE_CONFLICT", "概念图版本已变化。", "conflict")
    return case, spec


def create_concept(*, case_id, user_id, expected_revision, spec_version_id, prompt, base_version=0,
                   run_id=None, work_item_id=None, generation=None, provider=None, retry_of=None):
    """Provider work is outside the write lock; CAS and lease fencing run again on commit."""
    binding = dict(case_id=case_id, user_id=user_id, expected_revision=expected_revision,
                   spec_version_id=spec_version_id, base_version=base_version, run_id=run_id,
                   work_item_id=work_item_id, generation=generation)
    prompt = str(prompt).strip()
    if not prompt or len(prompt) > MAX_PROMPT_CHARS:
        raise ConceptImageError("IMAGE_PROMPT_INVALID", "设计说明不能为空且不能超过 8000 个字符。")
    with SessionLocal() as db:
        case, spec = _binding(db, **binding)
        preset = preset_id(case)
        spec_hash = hashlib.sha256(json.dumps(decode(spec.payload).get("content", {}), sort_keys=True).encode()).hexdigest()
        # Freeze the exact input; the image service sees the controlled specification too.
        description = json.dumps(decode(spec.payload).get("content", {}), ensure_ascii=False, sort_keys=True)
        provider_prompt = f"Specification version {spec.id}: {description}\nUser design brief: {prompt}"
        request_hash = hashlib.sha256(json.dumps([spec.id, spec_hash, prompt], ensure_ascii=False).encode()).hexdigest()
    attempt_id = uid("image_attempt")
    try:
        if preset:
            try:
                image = preset_path(preset).read_bytes()
            except OSError:
                raise ConceptImageError("DEMO_IMAGE_UNAVAILABLE", "演示图片文件缺失，请恢复本地素材后重试。", "blocked") from None
            mime, model = "image/png", f"demo-preset:{preset}"
        else:
            image, mime, model = generate_image(provider_prompt, provider=provider)
        from PIL import Image
        with Image.open(BytesIO(image)) as parsed:
            if parsed.width * parsed.height > 25_000_000 or parsed.format not in ("PNG", "JPEG"):
                raise ConceptImageError("IMAGE_RESPONSE_INVALID", "图片尺寸或格式超出支持范围。")
            parsed.verify()
        with Image.open(BytesIO(image)) as parsed:
            parsed.load()
    except Exception as exc:
        error = exc if isinstance(exc, ConceptImageError) else ConceptImageError("IMAGE_RESPONSE_INVALID", "图像服务返回了无效图片。")
        with SessionLocal() as db:
            case, _ = _binding(db, **binding)
            attempt = {"id": attempt_id, "status": "failed", "code": error.code, "message": str(error),
                "prompt": prompt, "specVersionId": spec_version_id, "specHash": spec_hash,
                "baseVersion": base_version, "baseRevision": expected_revision, "inputHash": request_hash,
                "retryable": error.code != "IMAGE_PROMPT_INVALID", "retryOf": retry_of, "createdAt": now()}
            create_item(db, "image_attempt", attempt, case_id=case.id, item_id=attempt_id)
            db.commit()
        return {"status": error.status, "code": error.code, "summary": str(error), "attempt": attempt}
    with SessionLocal() as db:
        from sqlalchemy import text
        db.execute(text("BEGIN IMMEDIATE"))
        case, spec = _binding(db, **binding)
        current_hash = hashlib.sha256(json.dumps(decode(spec.payload).get("content", {}), sort_keys=True).encode()).hexdigest()
        if current_hash != spec_hash:
            raise ConceptImageError("SPEC_VERSION_UNAVAILABLE", "规格内容在图像生成期间发生变化。", "conflict")
        from .workbench import append_artifact, commit_revision
        extension = SUPPORTED_MIME[mime][0]
        blob = store_blob(db, image, f"concept-image-v{base_version + 1}.{extension}", mime, case.id)
        export_id = uid("export")
        proposal_id = uid("export")
        content = {"prompt": prompt, "model": model, "specVersionId": spec.id, "specHash": spec_hash,
            "generationMode": "preset" if preset else "provider", "presetId": preset,
            "simulation": bool(preset), "imageApiCalled": not bool(preset),
            "inputHash": request_hash, "imageFileId": blob.id, "sha256": blob.sha256,
            "conceptOnly": True, "accepted": False, "sampleApproved": False, "productionReleased": False,
            "visualAlignment": "needs_human_review", "logoHandling": "neutral_placeholder; replace with original artwork in the document editor",
            "status": "needs_review", "downloadUrl": f"/api/v1/workspaces/{case.workspace_id}/exports/{export_id}/download",
            "proposalDownloadUrl": f"/api/v1/workspaces/{case.workspace_id}/exports/{proposal_id}/download"}
        artifact = append_artifact(db, case, "concept_image", content, title="产品概念图", run_id=run_id, status="draft")
        export = {"exportId": export_id, "status": "ready", "caseId": case.id,
            "artifactVersionId": artifact["itemId"], "format": extension, "mode": "concept_draft", "blobId": blob.id,
            "snapshotHash": request_hash, "downloadUrl": content["downloadUrl"], "createdAt": now()}
        create_item(db, "export", export, case_id=case.id, item_id=export_id)
        # A native, editable proposal binds the image, specification and uncertainties
        # to this same immutable input hash. OfficeFiles can import this export.
        from docx import Document
        from docx.shared import Inches
        document = Document()
        document.add_heading("Product concept proposal", 0)
        document.add_paragraph("Prepared demo concept image: loaded from a local preset; no image API was called and the image was not redrawn from this request." if preset else "AI product concept illustration: visual communication only. Not an engineering drawing, real photograph, or approved physical sample.")
        document.add_paragraph(f"Specification: {spec.id}; input snapshot: {request_hash}")
        document.add_paragraph(prompt)
        document.add_picture(BytesIO(image), width=Inches(4.5))
        fields = (decode(spec.payload).get("content") or {}).get("fields") or {}
        table = document.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        table.rows[0].cells[0].text, table.rows[0].cells[1].text = "Specification field", "Controlled value"
        for key, value in fields.items():
            cells = table.add_row().cells
            cells[0].text, cells[1].text = str(key), "Unknown" if value is None else str(value)
        document.add_paragraph("Pending: visual/spec alignment review, material properties, manufacturability, BOM quantities, supplier prices and physical sample approval. Generated text or pixels do not verify these facts.")
        stream = BytesIO()
        document.save(stream)
        proposal_blob = store_blob(db, stream.getvalue(), f"design-proposal-v{base_version + 1}.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document", case.id)
        proposal_export = {**export, "exportId": proposal_id, "blobId": proposal_blob.id, "format": "docx",
            "downloadUrl": f"/api/v1/workspaces/{case.workspace_id}/exports/{proposal_id}/download"}
        create_item(db, "export", proposal_export, case_id=case.id, item_id=proposal_id)
        create_item(db, "image_attempt", {"id": attempt_id, "status": "succeeded", "retryOf": retry_of,
            "inputHash": request_hash, "artifactVersionId": artifact["itemId"], "createdAt": now()}, case_id=case.id, item_id=attempt_id)
        if not run_id:
            commit_revision(db, case, "载入产品演示图" if preset else "生成规格绑定的概念图草稿", node="requirements")
        db.commit()
        return {"status": "needs_review", "summary": "已载入本询盘的预置产品演示图并保存设计方案；未调用生图 API，图片不会随提示词重新绘制。" if preset else "已生成概念图草稿；不代表工程可行性或实物样品批准。",
                "artifact": artifact, "export": export, "proposalExport": proposal_export, "attemptId": attempt_id}
