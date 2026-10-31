from __future__ import annotations

import hashlib
import json
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


def canonical(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


Status = Literal["success", "needs_info", "needs_review", "blocked", "conflict", "error"]


class ExecutionContext(Model):
    case_id: str = Field(min_length=1)
    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    can_read: bool = True
    can_write: bool = True
    generation: int = Field(default=0, ge=0)


class FileRef(Model):
    file_id: str
    case_id: str
    role: Literal["source", "output", "working"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str
    name: str
    byte_size: int = Field(ge=0)


class Citation(Model):
    file_id: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    locator: dict[str, Any]
    excerpt: str = Field(min_length=1, max_length=4000)


class Fact(Model):
    value: str | int | bool | None
    sources: list[Citation] = Field(default_factory=list)
    user_fact: str | None = None


class ArtifactRef(Model):
    artifact_id: str
    version: int = Field(ge=1)
    baseline: int = Field(ge=0)
    kind: str
    snapshot_hash: str
    files: list[FileRef] = Field(default_factory=list)
    inputs: list[Citation] = Field(default_factory=list)


class Question(Model):
    question_id: str
    missing_fields: list[str]
    affected_artifacts: list[str]
    prompt: str


class ToolCall(Model):
    tool_call_id: str = Field(min_length=1)
    name: str
    arguments: dict[str, Any]
    idempotency_key: str = Field(min_length=1, max_length=200)


class ToolResult(Model):
    status: Status
    outputs: list[FileRef] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    retryable: list[str] = Field(default_factory=list)
    code: str | None = None


class ExecutionEvent(Model):
    run_id: str
    seq: int = Field(ge=1)
    kind: str
    summary: str
    result_ref: str | None = None


class TaskSnapshot(Model):
    case_id: str
    job_id: str
    run_id: str
    generation: int
    status: Status
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    checkpoint_ref: str | None = None


class AgentError(Exception):
    def __init__(self, code: str, message: str, status: Status = "blocked"):
        super().__init__(message)
        self.code, self.status = code, status
