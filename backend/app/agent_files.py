"""Agent Kit ports over existing Case/Item/Blob services; no parallel business DB."""
from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
import re

from sqlalchemy import text
from fastapi import HTTPException
from navowork_agent.contracts import ExecutionContext, AgentError, FileRef, ToolResult, ExecutionEvent, digest
from navowork_agent.tools.readers import read_file
from .core import create_item, decode, encode, items, require_case, store_blob, uid
from .db import SessionLocal
from .models import Case, Item, Blob, Job, Run, WorkItem, User, Idempotency, now


def enabled():
    import os
    return os.getenv("AGENT_FILE_TOOLS", "0") == "1"


def confirmed_facts(text_value):
    """Conservative host extraction of explicitly named user decisions, no defaults."""
    if re.search(r"如果|假设|不要|是否|\bif\b|would", text_value, re.I):
        return {}
    facts = {}
    for key, pattern in [("fx", r"(?:汇率|exchange\s*rate|FX)\s*(?:为|是|采用|[:=：])?\s*(\d+(?:\.\d+)?)"),
                         ("quantity", r"(?:数量|quantity)\s*(?:改为|为|是|[:=：])?\s*(\d+)")]:
        values = re.findall(pattern, text_value, re.I)
        if len(set(values)) == 1:
            facts[key] = int(values[0]) if key == "quantity" else values[0]
    margins = re.findall(r"(?:毛利(?:率)?|gross\s*margin)\s*(?:为|是|采用|[:=：])?\s*(\d+(?:\.\d+)?)\s*(%)?", text_value, re.I)
    if len(set(margins)) == 1:
        from decimal import Decimal
        value, percent = margins[0]
        ratio = Decimal(value) / 100 if percent else Decimal(value)
        if 0 <= ratio < 1:
            facts["margin"] = str(ratio)
    packaging = re.search(r"(?:包装|packaging)\s*(?:改为|改成|[:=：])\s*([^，。；;\n]+)", text_value, re.I)
    if packaging:
        facts["packaging"] = packaging.group(1).strip()
    return facts


class HostTransaction:
    def __init__(self, adapter, db): self.adapter, self.db = adapter, db
    def current(self, artifact_id): return self.adapter._artifact(self.db, artifact_id, None, missing_ok=True)
    def put_file(self, data, name, role="output"):
        c = self.adapter.context()
        blob = store_blob(self.db, data, name, mimetypes.guess_type(name)[0] or "application/octet-stream", c.case_id)
        ref = FileRef(file_id=blob.id, case_id=c.case_id, role=role, sha256=blob.sha256,
                      media_type=blob.media_type, name=blob.filename, byte_size=blob.byte_size)
        create_item(self.db, "agent_file", {"ref": ref.model_dump(), "blobId": blob.id, "runId": c.run_id}, case_id=c.case_id, item_id="af_" + blob.id)
        return ref
    def append_artifact(self, record):
        ref = record["ref"]
        history = [i for i in items(self.db, "artifact", case_id=self.adapter.context().case_id) if decode(i.payload).get("kind") == ref["kind"]]
        latest = max(history, key=lambda i: i.version) if history else None
        current = latest.version if latest else 0
        if current != ref["baseline"] or ref["version"] != current+1:
            raise AgentError("BASELINE_CONFLICT", "Host artifact version changed", "conflict")
        c = self.adapter.context()
        row_id = f"artifact_{c.case_id}_{ref['kind']}_v{ref['version']}"
        snap = record["snapshot"]
        # Existing UI consumes content; complete controlled record stays attached to this immutable version.
        content = {k: v.get("value") for k, v in snap.get("fields", {}).items()}
        if ref["kind"] == "cost": content = {"input": snap.get("pricing"), "result": record.get("pricing", {}).get("quote")}
        if ref["kind"] == "quotation":
            q = record.get("pricing", {}).get("quote")
            content["quote"] = {k: q[k] for k in ("unit_usd", "total_usd", "quantity")} if q else None
        export_refs = []
        for file in ref["files"]:
            export_refs.append(self._export(ref, FileRef.model_validate(file), row_id))
        create_item(self.db, "artifact", {"caseId": c.case_id, "kind": ref["kind"], "title": ref["kind"],
            "version": ref["version"], "content": content, "agentRecord": record, "exports": export_refs,
            "basedOnId": latest.id if latest else None, "status": "draft", "runId": c.run_id, "jobId": c.job_id,
            "createdAt": now()}, case_id=c.case_id, parent_id=ref["kind"], version=ref["version"], item_id=row_id)
    def _export(self, artifact, file, row_id):
        c = self.adapter.context()
        export_id = uid("export")
        value = {"exportId": export_id, "status": "ready", "downloadUrl": f"/api/v1/workspaces/{self.adapter.workspace_id}/exports/{export_id}/download",
                 "caseId": c.case_id, "artifactVersionId": row_id, "agentArtifactId": artifact["artifact_id"], "agentArtifactVersion": artifact["version"],
                 "snapshotHash": artifact["snapshot_hash"], "fileRef": file.model_dump(), "format": file.name.rsplit(".", 1)[-1],
                 "mode": "draft", "blobId": file.file_id, "createdAt": now()}
        create_item(self.db, "export", value, case_id=c.case_id, item_id=export_id)
        return value
    def register_export(self, artifact, file):
        self._export(artifact, file, f"artifact_{self.adapter.context().case_id}_{artifact['kind']}_v{artifact['version']}")


class HostAdapter:
    def __init__(self, context: ExecutionContext, user_id: str, work_item_id: str, *, session_factory=SessionLocal):
        self._context, self.user_id, self.work_item_id = context, user_id, work_item_id
        self.sessions = session_factory
        with self.sessions() as db:
            case = self._authorize(db)
            self.workspace_id = case.workspace_id

    def context(self): return self._context

    def _authorize(self, db, write=False):
        c = self._context
        user = db.get(User, self.user_id)
        if not user or not c.can_read or (write and not c.can_write):
            raise AgentError("CASE_SCOPE", "Host access denied")
        try: case = require_case(db, user, c.case_id)
        except HTTPException: raise AgentError("CASE_SCOPE", "Host access denied") from None
        run, work = db.get(Run, c.run_id), db.get(WorkItem, self.work_item_id)
        if (not run or run.case_id != c.case_id or run.job_id != c.job_id or not work or work.run_id != c.run_id
            or work.lease_generation != c.generation or work.status != "running" or run.status != "running"
            or case.active_run_id != run.id or case.current_revision != run.base_revision
            or (work.lease_expires_at and work.lease_expires_at < now())):
            raise AgentError("STALE_CONTEXT", "Host revision, active run or lease has changed", "conflict")
        return case

    def assert_current(self):
        with self.sessions() as db: self._authorize(db, True)

    def user_facts(self):
        with self.sessions() as db:
            self._authorize(db)
            return decode(db.get(Job, self._context.job_id).payload).get("agentFacts", {})

    def _files(self, db):
        c = self._context
        payload = decode(db.get(Job, c.job_id).payload)
        frozen = {e["id"]: e for e in payload.get("evidence", [])}
        result = {}
        original = payload.get("originalText", "")
        if original:
            data = original.encode("utf-8")
            fid = "case_text:" + c.case_id
            result[fid] = FileRef(file_id=fid, case_id=c.case_id, role="source", sha256=hashlib.sha256(data).hexdigest(),
                                  media_type="text/plain", name="original-inquiry.txt", byte_size=len(data))
        for index, message in enumerate(payload.get("agentMessages", [])):
            data = message.encode("utf-8")
            fid = f"job_message:{c.job_id}:{index}"
            result[fid] = FileRef(file_id=fid, case_id=c.case_id, role="source", sha256=hashlib.sha256(data).hexdigest(),
                                  media_type="text/plain", name=f"user-input-{index + 1}.txt", byte_size=len(data))
        for row in items(db, "evidence", case_id=c.case_id):
            if row.id not in frozen: continue
            value = decode(row.payload)
            if value.get("sha256") != frozen[row.id].get("sha256") or value.get("blobId") != frozen[row.id].get("blobId"):
                raise AgentError("SOURCE_VERSION", "Evidence changed after dispatch")
            blob = db.get(Blob, value.get("blobId")) if value.get("blobId") else None
            if blob and blob.case_id == c.case_id:
                if blob.sha256 != value["sha256"]:
                    raise AgentError("SOURCE_VERSION", "Evidence blob no longer matches its source")
                result[row.id] = FileRef(file_id=row.id, case_id=c.case_id, role="source", sha256=blob.sha256,
                    media_type=blob.media_type, name=blob.filename, byte_size=blob.byte_size)
            elif not value.get("blobId"):
                data = value.get("text", "").encode("utf-8")
                if hashlib.sha256(data).hexdigest() != value["sha256"]:
                    raise AgentError("SOURCE_VERSION", "Pasted evidence integrity check failed")
                result[row.id] = FileRef(file_id=row.id, case_id=c.case_id, role="source", sha256=value["sha256"],
                    media_type="text/plain", name=value.get("title", "pasted-evidence") + ".txt", byte_size=len(data))
            else:
                raise AgentError("FILE_UNAVAILABLE", "Frozen evidence blob is unavailable")
        for entry in payload.get("assetManifest", []):
            blob = self._asset_blob(db, entry)
            result[entry["id"]] = FileRef(file_id=entry["id"], case_id=c.case_id, role="source", sha256=blob.sha256,
                media_type=blob.media_type, name=blob.filename, byte_size=blob.byte_size)
        for entry in payload.get("sourceRefs", []):
            data = self._resource_bytes(db, entry)
            result[entry["sourceVersionId"]] = FileRef(file_id=entry["sourceVersionId"], case_id=c.case_id, role="source",
                sha256=hashlib.sha256(data).hexdigest(), media_type="text/plain", name=entry["title"] + ".txt", byte_size=len(data))
        for entry in payload.get("canvasManifest", []):
            row = db.get(Item, entry["id"])
            if not row or row.kind != "canvas_file" or row.case_id != c.case_id or row.parent_id != self.user_id:
                raise AgentError("CASE_SCOPE", "Canvas attachment access changed")
            blob = db.get(Blob, decode(row.payload)["blobId"])
            if not blob or blob.case_id != c.case_id or blob.sha256 != entry["sha256"]:
                raise AgentError("SOURCE_VERSION", "Canvas attachment version changed")
            result[row.id] = FileRef(file_id=row.id, case_id=c.case_id, role="source", sha256=blob.sha256,
                media_type=blob.media_type, name=blob.filename, byte_size=blob.byte_size)
        for row in items(db, "agent_file", case_id=c.case_id):
            ref = FileRef.model_validate(decode(row.payload)["ref"])
            result[ref.file_id] = ref
        return result

    def _asset_blob(self, db, entry):
        from .workspace_api import asset_version
        match = re.fullmatch(r"(.+):v(\d+)", entry["id"])
        if not match:
            raise AgentError("CASE_SCOPE", "Invalid authorized asset version")
        try:
            row = asset_version(db, db.get(User, self.user_id), match[1], int(match[2]))
        except HTTPException:
            raise AgentError("CASE_SCOPE", "Asset access changed") from None
        value = decode(row.payload)
        blob = db.get(Blob, value.get("blobId"))
        if value.get("space") == "personal":
            raise AgentError("CASE_SCOPE", "Personal assets cannot enter shared Case execution")
        if not blob or blob.id != entry["blobId"] or blob.sha256 != entry["sha256"]:
            raise AgentError("SOURCE_VERSION", "Asset version changed")
        return blob

    def _resource_bytes(self, db, entry):
        row = db.get(Item, entry["sourceVersionId"])
        if not row or row.kind != "resource" or row.workspace_id != self.workspace_id:
            raise AgentError("CASE_SCOPE", "Resource access changed")
        value = decode(row.payload)
        data = value.get("content", "").encode("utf-8")
        if value.get("status") == "revoked" or hashlib.sha256(data).hexdigest() != entry["contentHash"]:
            raise AgentError("SOURCE_VERSION", "Resource revoked or version changed")
        return data

    def list_files(self):
        with self.sessions() as db:
            self._authorize(db)
            return list(self._files(db).values())

    def _blob(self, db, file_id):
        refs = self._files(db)
        if file_id not in refs: raise AgentError("FILE_UNAVAILABLE", "File is unavailable in this Case")
        ref = refs[file_id]
        entry = next((v for v in decode(db.get(Job, self._context.job_id).payload).get("assetManifest", []) if v["id"] == file_id), None)
        if entry:
            return ref, self._asset_blob(db, entry)
        row = db.get(Item, file_id) if ref.role == "source" else db.get(Item, "af_" + file_id)
        blob = db.get(Blob, decode(row.payload)["blobId"])
        if not blob or blob.case_id != self._context.case_id or blob.sha256 != ref.sha256:
            raise AgentError("SOURCE_VERSION", "File reference no longer matches the host")
        return ref, blob

    def read_bytes(self, file_id):
        with self.sessions() as db:
            self._authorize(db)
            payload = decode(db.get(Job, self._context.job_id).payload)
            refs = self._files(db)
            if file_id not in refs:
                raise AgentError("FILE_UNAVAILABLE", "File is unavailable in this Case")
            for index, message in enumerate(payload.get("agentMessages", [])):
                if file_id == f"job_message:{self._context.job_id}:{index}":
                    return message.encode("utf-8")
            pasted = next((v for v in payload.get("evidence", []) if v["id"] == file_id and not v.get("blobId")), None)
            if pasted:
                return pasted["text"].encode("utf-8")
            source = next((v for v in payload.get("sourceRefs", []) if v["sourceVersionId"] == file_id), None)
            if source:
                return self._resource_bytes(db, source)
            if file_id == "case_text:" + self._context.case_id:
                return decode(db.get(Job, self._context.job_id).payload)["originalText"].encode("utf-8")
            ref, blob = self._blob(db, file_id)
            data = Path(blob.path).read_bytes()
            if hashlib.sha256(data).hexdigest() != ref.sha256:
                raise AgentError("HASH_MISMATCH", "Host file integrity check failed")
            return data

    def read_document(self, file_id):
        data = self.read_bytes(file_id)
        with self.sessions() as db:
            self._authorize(db)
            payload = decode(db.get(Job, self._context.job_id).payload)
            if (file_id == "case_text:" + self._context.case_id or file_id.startswith(f"job_message:{self._context.job_id}:")
                or any(v["sourceVersionId"] == file_id for v in payload.get("sourceRefs", []))
                or any(v["id"] == file_id and not v.get("blobId") for v in payload.get("evidence", []))):
                return {"format": "txt", "sections": [{"locator": {"line": i}, "text": line[:10000]}
                    for i, line in enumerate(data.decode("utf-8").splitlines()[:10000], 1)], "warnings": []}
            ref, blob = self._blob(db, file_id)
            return read_file(Path(blob.path), ref.media_type)

    def _artifact(self, db, aid, version=None, missing_ok=False):
        for row in sorted(items(db, "artifact", case_id=self._context.case_id), key=lambda i: i.version, reverse=True):
            value = decode(row.payload)
            record = value.get("agentRecord")
            stable = "a_" + digest([self._context.case_id, value.get("kind")])[:24]
            if stable != aid: continue
            if version is not None and row.version != version: continue
            if record is None:
                if missing_ok:
                    return {"ref": {"version": row.version}, "content_matches_snapshot": False, "manual_operations": [{"legacy_host_version": row.id}]}
                raise AgentError("HOST_BASELINE_REQUIRES_RECONCILIATION", "Host artifact has no reconciled file snapshot", "conflict")
            return record
        if missing_ok: return None
        raise AgentError("ARTIFACT_UNAVAILABLE", "Artifact version is unavailable in this Case")

    def list_artifacts(self):
        with self.sessions() as db:
            self._authorize(db)
            latest = {}
            for row in items(db, "artifact", case_id=self._context.case_id):
                value = decode(row.payload)
                record = value.get("agentRecord")
                if record and (value["kind"] not in latest or record["ref"]["version"] > latest[value["kind"]]["ref"]["version"]):
                    latest[value["kind"]] = record
            return list(latest.values())

    def get_artifact(self, aid, version=None):
        with self.sessions() as db:
            self._authorize(db)
            return self._artifact(db, aid, version)

    def list_exports(self, aid, version):
        with self.sessions() as db:
            self._authorize(db)
            self._artifact(db, aid, version)
            return [FileRef.model_validate(v["fileRef"]) for row in items(db, "export", case_id=self._context.case_id)
                    if (v := decode(row.payload)).get("agentArtifactId") == aid and v.get("agentArtifactVersion") == version]

    def _event(self, db, kind, summary, result_ref=None):
        c = self._context
        run = db.get(Run, c.run_id)
        run.last_seq += 1
        event = ExecutionEvent(run_id=c.run_id, seq=run.last_seq, kind=kind, summary=summary, result_ref=result_ref)
        create_item(db, "run_event", {"runId": c.run_id, "inquiryId": c.case_id, "seq": run.last_seq,
            "type": "agent." + kind, "payload": {"summary": summary, "resultRef": result_ref}, "createdAt": now()}, case_id=c.case_id, parent_id=c.run_id)
        return event

    def emit(self, kind, summary, result_ref=None):
        with self.sessions() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            self._authorize(db)
            result = self._event(db, kind, summary, result_ref)
            db.commit()
            return result

    def execute_once(self, key, payload, operation, *, write=True):
        with self.sessions() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            self._authorize(db, write)
            if payload["name"] in ("calculate_quote", "publish_documents"):
                from .run_context import require_capability
                try:
                    require_capability(db, "costing")
                except HTTPException:
                    raise AgentError("CAPABILITY_DISABLED", "Host costing capability is disabled", "blocked") from None
            c = self._context
            scope, fingerprint = "agent:" + digest([c.case_id, c.job_id, key]), digest(payload)
            old = db.get(Idempotency, scope)
            if old:
                if old.body_hash != fingerprint:
                    raise AgentError("IDEMPOTENCY_CONFLICT", "Host tool key was used with different inputs", "conflict")
                return ToolResult.model_validate(decode(old.response))
            result = operation(HostTransaction(self, db))
            result_id = "agent_result_" + digest([scope, fingerprint])
            db.add(Idempotency(key=scope, body_hash=fingerprint, response=encode(result.model_dump(mode="json"))))
            create_item(db, "agent_result", {"result": result.model_dump(mode="json"), "tool": payload["name"], "runId": c.run_id},
                        case_id=c.case_id, parent_id=c.run_id, item_id=result_id)
            self._event(db, "tool_result", f"{payload['name']}: {result.status}; outputs={len(result.outputs)}", result_id)
            db.commit()
            return result
