"""External OFFLINE acceptance harness; not a substitute for real model execution."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "tests"))
from support import make_adapter, base_snapshot, change_snapshot, publish, invoke, REPO, INPUTS
from navowork_agent.tools.service import ToolService
from navowork_agent.tools.pricing import calculate_quote
from navowork_agent.contracts import canonical


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, help="Explicit retained demo directory; default is a fresh temporary directory")
    args = p.parse_args()
    root = args.output.resolve() if args.output else Path(tempfile.mkdtemp(prefix="navowork-replay-"))
    root.mkdir(parents=True, exist_ok=True)
    if (root / "case-a/manifest.json").exists():
        p.error("Use a fresh output directory to preserve prior replay evidence")
    # Only this external evaluator reads expectations. Neither product tools nor the Agent receive them.
    expected = json.loads((REPO / "test/expected/quote-golden.json").read_text())["results"]
    adapter = make_adapter(root / "case-a")
    service = ToolService(adapter)
    stages, files = [], []
    snap = base_snapshot(adapter)
    stage = publish(service, snap)
    assert stage.status == "needs_review", stage
    assert stage.data["pricing"]["quote"]["unit_usd"] == expected["supplier_a_v1"]["unit_usd"]
    assert stage.data["pricing"]["quote"]["total_usd"] == expected["supplier_a_v1"]["total_usd"]
    stages.append({"stage": "initial", "inputs": [f.model_dump() for f in adapter.list_files() if f.role == "source"], "result": stage.model_dump(mode="json")})
    files.extend(stage.outputs)
    old = {f.file_id: adapter.read_bytes(f.file_id) for f in stage.outputs}
    stage = publish(service, change_snapshot(adapter, snap), "confirmed_change")
    assert stage.status == "needs_info" and stage.data["pricing"]["quote"] is None
    stages.append({"stage": "packaging_missing_price", "inputs": [f.model_dump() for f in adapter.list_files() if f.role == "source"], "result": stage.model_dump(mode="json")})
    files.extend(stage.outputs)
    stage = publish(service, change_snapshot(adapter, snap, priced=True), "confirmed_change")
    assert stage.status == "needs_review"
    assert stage.data["pricing"]["quote"]["unit_usd"] == expected["supplier_a_v2"]["unit_usd"]
    assert stage.data["pricing"]["quote"]["total_usd"] == expected["supplier_a_v2"]["total_usd"]
    for fid, data in old.items(): assert adapter.read_bytes(fid) == data
    stages.append({"stage": "price_supplement", "inputs": [f.model_dump() for f in adapter.list_files() if f.role == "source"], "result": stage.model_dump(mode="json")})
    files.extend(stage.outputs)
    checks = []
    for artifact in stage.artifacts:
        check = invoke(service, "validate_artifact", {"artifact_id": artifact.artifact_id, "version": artifact.version})
        assert check.status == "needs_review"
        checks.append(check.model_dump(mode="json"))
    b = make_adapter(root / "case-b")
    b_snap = base_snapshot(b, "B")
    b_quote = calculate_quote(b_snap.pricing)["quote"]
    assert b_quote["unit_usd"] == expected["supplier_b"]["unit_usd"]
    paths = adapter.export_files(files, root / "files")
    record = {"verification_mode": "offline_tool_replay", "live_model": "not_run", "pdf_visual": "not_run",
              "docx_visual": "not_run", "old_versions_unchanged": True, "supplier_b": b_quote,
              "versions": {n: importlib.metadata.version(n) for n in ["langgraph", "langchain", "langchain-openai", "openpyxl", "pypdf", "reportlab"]},
              "stages": stages, "checks": checks, "paths": paths, "events": adapter._load()["events"]}
    (root / "replay-report.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(root / "replay-report.json"), "outputs": len(paths), "live_model": "not_run", "old_versions_unchanged": True}, indent=2))


if __name__ == "__main__":
    main()
