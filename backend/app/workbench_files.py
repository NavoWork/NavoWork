"""File tools composed into the workbench's existing business tool loop."""
from __future__ import annotations

from navowork_agent.contracts import AgentError, ExecutionContext, ToolCall, digest
from navowork_agent.tools.service import SCHEMAS, ToolService

from .agent_files import HostAdapter
from .core import decode, encode, items
from .db import SessionLocal
from .models import Run

FILE_TOOLS = {"list_context", "read_document", "list_artifacts", "create_working_copy", "edit_file", "validate_artifact"}
NODE_KINDS = {"inquiry": {"inquiry_assessment"}, "requirements": {"spec", "bom", "concept_image", "design_brief"},
              "costing": {"cost", "quotation", "comparison"}, "sample": {"sample"},
              "order": {"order", "payment", "pi"}, "production": {"production", "ta", "qc"}}


def schemas():
    return [{"type": "function", "function": {"name": "file_" + name, "description": description,
             "parameters": model.model_json_schema()}} for name, (model, description) in SCHEMAS.items() if name in FILE_TOOLS]


def call_file_tool(toolbox, name: str, arguments: dict):
    if not name.startswith("file_") or name[5:] not in FILE_TOOLS:
        return None
    tool = name[5:]
    adapter = HostAdapter(ExecutionContext(case_id=toolbox.case_id, job_id=toolbox.job_id,
        run_id=toolbox.run_id, generation=toolbox.generation), toolbox.user_id, toolbox.work_item_id)
    if tool == "edit_file":
        record = adapter.get_artifact(arguments.get("artifact_id"))
        kind = record["ref"]["kind"]
        if toolbox.node and not kind.startswith("working_file_") and kind not in NODE_KINDS.get(toolbox.node, set()):
            return {"status": "blocked", "summary": "当前节点不能修改其他业务节点的文件"}
    result = ToolService(adapter).call(ToolCall(tool_call_id=digest([name, arguments])[:24], name=tool,
        arguments=arguments, idempotency_key=digest([name, arguments])))
    value = result.model_dump(mode="json")
    value["summary"] = f"{name}: {result.status}" + (": " + "; ".join(result.warnings) if result.warnings else "")
    # File tools commit their immutable bytes before this presentation projection.
    # On replay the same export refs are reused; no parallel revision is created.
    with adapter.sessions() as db:
        adapter._authorize(db, True)
        run = db.get(Run, toolbox.run_id)
        payload = decode(run.payload)
        exports = {decode(row.payload).get("blobId"): decode(row.payload) for row in items(db, "export", case_id=toolbox.case_id)}
        outputs = {output["file_id"]: output for output in payload.get("fileOutputs", [])}
        for output in value["outputs"]:
            export = exports.get(output["file_id"])
            if export:
                outputs[output["file_id"]] = {**output, "downloadUrl": export["downloadUrl"]}
        payload["fileOutputs"] = list(outputs.values())
        run.payload = encode(payload)
        toolbox._log(db, name, arguments, value)
        db.commit()
    return value
