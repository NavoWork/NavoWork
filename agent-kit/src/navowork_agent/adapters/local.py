"""Disposable filesystem adapter, not a replacement for the host business database."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import mimetypes
import os
from pathlib import Path
import time
from uuid import uuid4
import json

from navowork_agent.contracts import (
    AgentError, ExecutionContext, FileRef, ToolResult, ExecutionEvent, canonical, digest,
)
from navowork_agent.tools.readers import read_file


class LocalTransaction:
    def __init__(self, adapter, state):
        self.adapter, self.state = adapter, state

    def current(self, artifact_id):
        history = self.state["artifacts"].get(artifact_id, [])
        return deepcopy(history[-1]) if history else None

    def put_file(self, data, name, role="output"):
        return self.adapter._put(self.state, data, name, role)

    def append_artifact(self, record):
        aid = record["ref"]["artifact_id"]
        history = self.state["artifacts"].setdefault(aid, [])
        current = history[-1]["ref"]["version"] if history else 0
        if record["ref"]["baseline"] != current or record["ref"]["version"] != current + 1:
            raise AgentError("BASELINE_CONFLICT", "Artifact baseline changed at commit", "conflict")
        history.append(deepcopy(record))

    def register_export(self, artifact, file):
        self.state["exports"].append({"artifact": deepcopy(artifact), "file": file.model_dump()})


class LocalAdapter:
    def __init__(self, root: Path, context: ExecutionContext):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._context = context
        self.manifest = self.root / "manifest.json"
        with self.transaction() as state:
            if state.get("case_id") not in (None, context.case_id):
                raise AgentError("CASE_SCOPE", "Workspace belongs to another Case")
            state.setdefault("case_id", context.case_id)
            state.setdefault("generation", 0)

    def context(self):
        return self._context

    def _load(self):
        if not self.manifest.exists():
            return {"files": {}, "artifacts": {}, "idempotency": {}, "events": [], "results": {}, "facts": {}, "exports": []}
        return json.loads(self.manifest.read_text(encoding="utf-8"))

    def _save(self, state):
        temp = self.root / f"manifest-{uuid4().hex}.tmp"
        with temp.open("w", encoding="utf-8") as stream:
            stream.write(canonical(state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self.manifest)

    @contextmanager
    def transaction(self):
        lock = self.root / ".manifest.lock"
        for attempt in range(100):
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                if attempt == 99:
                    raise AgentError("WORKSPACE_BUSY", "Workspace is locked; retry after active process exits", "conflict")
                time.sleep(.02)
        try:
            os.close(fd)
            state = self._load()
            yield state
            self._save(state)
        finally:
            lock.unlink(missing_ok=True)

    def _check(self, state, write=False):
        c = self._context
        if state.get("case_id") != c.case_id or not c.can_read:
            raise AgentError("CASE_SCOPE", "File or task is unavailable in this Case")
        if write and not c.can_write:
            raise AgentError("WRITE_DENIED", "Host did not grant write access")
        if write and state["generation"] != c.generation:
            raise AgentError("STALE_CONTEXT", "A newer user input superseded this execution", "conflict")

    def assert_current(self):
        self._check(self._load(), write=True)

    def user_facts(self):
        state = self._load()
        self._check(state)
        return deepcopy(state["facts"])

    def update_user_facts(self, facts: dict, *, supersede=True):
        """Host-only API. Never registered as a model tool."""
        with self.transaction() as state:
            self._check(state, write=True)
            state["facts"].update(facts)
            if supersede:
                state["generation"] += 1
        self._context = self._context.model_copy(update={"generation": state["generation"]})

    def _put(self, state, data: bytes, name: str, role="output", media_type=None):
        if len(data) > 20 * 1024 * 1024:
            raise AgentError("FILE_TOO_LARGE", "File exceeds 20 MiB")
        sha = hashlib.sha256(data).hexdigest()
        blob_dir = self.root / "blobs"
        blob_dir.mkdir(exist_ok=True)
        target = blob_dir / sha
        if not target.exists():
            temp = blob_dir / f"{uuid4().hex}.tmp"
            temp.write_bytes(data)
            os.replace(temp, target)
        name = Path(name).name
        mt = media_type or mimetypes.guess_type(name)[0] or "application/octet-stream"
        identity = "f_" + digest([self._context.case_id, sha, role, name])[:32]
        ref = FileRef(file_id=identity, case_id=self._context.case_id, role=role, sha256=sha,
                      media_type=mt, name=name, byte_size=len(data))
        state["files"][identity] = ref.model_dump()
        return ref

    def import_source(self, path: Path):
        """Trusted host import; a model cannot import arbitrary physical paths."""
        path = Path(path)
        if path.stat().st_size > 20 * 1024 * 1024:
            raise AgentError("FILE_TOO_LARGE", "File exceeds 20 MiB")
        with self.transaction() as state:
            self._check(state, write=True)
            return self._put(state, path.read_bytes(), path.name, "source")

    def list_files(self):
        state = self._load()
        self._check(state)
        return [FileRef.model_validate(f) for f in state["files"].values()]

    def _ref(self, state, file_id):
        self._check(state)
        value = state["files"].get(file_id)
        if not value or value["case_id"] != self._context.case_id:
            raise AgentError("FILE_UNAVAILABLE", "File is unavailable in this Case")
        return FileRef.model_validate(value)

    def read_bytes(self, file_id):
        ref = self._ref(self._load(), file_id)
        data = (self.root / "blobs" / ref.sha256).read_bytes()
        if hashlib.sha256(data).hexdigest() != ref.sha256:
            raise AgentError("HASH_MISMATCH", "Stored file failed integrity verification")
        return data

    def read_document(self, file_id):
        ref = self._ref(self._load(), file_id)
        self.read_bytes(file_id)
        return read_file(self.root / "blobs" / ref.sha256, ref.media_type)

    def list_artifacts(self):
        state = self._load()
        self._check(state)
        return [deepcopy(versions[-1]) for versions in state["artifacts"].values() if versions]

    def get_artifact(self, artifact_id, version=None):
        state = self._load()
        self._check(state)
        versions = state["artifacts"].get(artifact_id, [])
        match = next((x for x in versions if x["ref"]["version"] == version), None) if version else (versions[-1] if versions else None)
        if match is None:
            raise AgentError("ARTIFACT_UNAVAILABLE", "Artifact version is unavailable in this Case")
        return deepcopy(match)

    def list_exports(self, artifact_id, version):
        self.get_artifact(artifact_id, version)  # Verify scoped identity before returning export refs.
        state = self._load()
        return [FileRef.model_validate(x["file"]) for x in state["exports"]
                if x["artifact"]["artifact_id"] == artifact_id and x["artifact"]["version"] == version]

    def _event(self, state, kind, summary, result_ref=None):
        seq = 1 + sum(e["run_id"] == self._context.run_id for e in state["events"])
        event = ExecutionEvent(run_id=self._context.run_id, seq=seq, kind=kind, summary=summary, result_ref=result_ref)
        state["events"].append(event.model_dump())
        return event

    def emit(self, kind, summary, result_ref=None):
        with self.transaction() as state:
            self._check(state)
            return self._event(state, kind, summary, result_ref)

    def execute_once(self, key, payload, operation, *, write=True):
        """CAS, output refs, tool result and idempotency record share one manifest commit.

        Blobs written before a failed commit may be orphaned, never visible as results.
        Process termination during commit requires manual lock removal after confirming no writer lives.
        """
        with self.transaction() as state:
            self._check(state, write=write)
            scope = digest([self._context.case_id, self._context.job_id, key])
            fingerprint = digest(payload)
            prior = state["idempotency"].get(scope)
            if prior:
                if prior["fingerprint"] != fingerprint:
                    raise AgentError("IDEMPOTENCY_CONFLICT", "Key was already used with different input", "conflict")
                return ToolResult.model_validate(state["results"][prior["result_ref"]])
            result = operation(LocalTransaction(self, state))
            rid = "r_" + digest([scope, fingerprint])
            state["results"][rid] = result.model_dump(mode="json")
            state["idempotency"][scope] = {"fingerprint": fingerprint, "result_ref": rid}
            self._event(state, "tool_result", f"{payload.get('name', 'tool')}: {result.status}; outputs={len(result.outputs)}", rid)
            return result

    def export_files(self, refs: list[FileRef], directory: Path):
        """Trusted presentation API; model never chooses a physical output directory."""
        directory = Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        paths = []
        for ref in refs:
            actual = self._ref(self._load(), ref.file_id)
            if actual != ref:
                raise AgentError("REFERENCE_MISMATCH", "Output reference differs from registered file")
            path = directory / f"{ref.file_id[:10]}-{Path(ref.name).name}"
            data = self.read_bytes(ref.file_id)
            if path.exists() and path.read_bytes() != data:
                raise AgentError("EXPORT_EXISTS", "Refusing to overwrite a different exported file", "conflict")
            path.write_bytes(data)
            paths.append(str(path))
        return paths
