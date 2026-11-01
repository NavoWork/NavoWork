from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from navowork_agent.contracts import ExecutionContext, FileRef, canonical
from navowork_agent.adapters.local import LocalAdapter
from navowork_agent.tools.service import ToolService


def main():
    parser = argparse.ArgumentParser(description="Scoped file-agent local validation adapter")
    parser.add_argument("command", choices=["init", "import", "facts", "inspect", "run"])
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--case", default=None)
    parser.add_argument("--job", default="quotation")
    parser.add_argument("--files", nargs="*", type=Path, default=[])
    parser.add_argument("--facts-json", type=Path)
    parser.add_argument("--goal")
    parser.add_argument("--resume")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest = args.workspace / "manifest.json"
    state = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    case = args.case or state.get("case_id")
    if not case:
        parser.error("--case is required for a new workspace")
    adapter = LocalAdapter(args.workspace, ExecutionContext(case_id=case, job_id=args.job,
        run_id="run_" + uuid4().hex, generation=state.get("generation", 0)))
    if args.command == "init":
        result = {"case_id": case, "workspace": str(adapter.root)}
    elif args.command == "import":
        result = {"files": [adapter.import_source(p).model_dump() for p in args.files]}
    elif args.command == "facts":
        if not args.facts_json:
            parser.error("facts requires --facts-json containing an object of explicit user decisions")
        facts = json.loads(args.facts_json.read_text(encoding="utf-8"))
        if not isinstance(facts, dict):
            parser.error("Facts must be a JSON object")
        adapter.update_user_facts(facts)
        result = {"generation": adapter.context().generation, "facts": adapter.user_facts()}
    elif args.command == "inspect":
        result = {"files": [f.model_dump() for f in adapter.list_files()], "artifacts": adapter.list_artifacts(),
                  "events": adapter._load()["events"]}
    else:
        from navowork_agent.runtime.agent import agent_session
        with agent_session(ToolService(adapter)) as run:
            result = run(goal=args.goal, resume=args.resume)
        if args.output and result.get("outputs"):
            result["paths"] = adapter.export_files([FileRef.model_validate(f) for f in result["outputs"]], args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if result.get("status") in ("error", "blocked", "conflict") else 0


if __name__ == "__main__":
    raise SystemExit(main())
