"""Host-side scenario runner and machine-readable reporting."""
from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .adapters import Unavailable, invoke
from .checker import evaluate
from .fixture_audit import audit_fixtures
from .inspection import canonical, digest
from .suite import REPO, build_suite, stage


def git_head():
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def implementation_manifest():
    paths = sorted((REPO / "evaluation").glob("*.py")) + sorted((REPO / "evaluation/tests").glob("*.py"))
    return {path.relative_to(REPO).as_posix(): digest(path.read_bytes()) for path in paths}


def run_suite(output: Path, *, seed=7319, selected=None, mode="offline", **adapter_config) -> dict:
    output = output.resolve()
    if not output.is_relative_to(REPO / "evaluation"):
        raise ValueError("all evaluation outputs must stay under evaluation/")
    output.mkdir(parents=True, exist_ok=False)
    scenario_results, inventory = [], []
    adapter = adapter_config.get("adapter", "unavailable")
    suite = build_suite(seed)
    if selected:
        unknown = set(selected) - {s.id for s in suite}
        if unknown:
            raise ValueError("unknown scenarios: " + ", ".join(sorted(unknown)))
        suite = [s for s in suite if s.id in selected]
    for scenario in suite:
        root = output / scenario.id
        request, sources = stage(scenario, root, str(uuid.uuid4()))
        inventory.extend({"scenario": scenario.id, **s} for s in sources)
        write_json(root / "request.json", request)
        try:
            response, wire = invoke(request, **adapter_config)
            write_json(root / "response.json", response)
            # Audit the exact public payload separately from evaluator-only expectations.
            write_json(root / "wire-request.json", wire)
            result = evaluate(scenario, wire, response, root, require_model=mode == "real-model")
            result.update(request_sha256=digest(canonical(wire)), response_sha256=digest(canonical(response)))
        except (Unavailable, ImportError) as exc:
            result = {"id": scenario.id, "title": scenario.title, "coverage": scenario.coverage, "status": "blocked",
                      "findings": [{"code": "RUNTIME_UNAVAILABLE", "step": None, "message": str(exc)}]}
        except Exception as exc:
            # Malformed output, timeout and transport errors are failures, never a passed skip.
            result = {"id": scenario.id, "title": scenario.title, "coverage": scenario.coverage, "status": "failed",
                      "findings": [{"code": "ADAPTER_OR_PROTOCOL_ERROR", "step": None,
                                    "message": type(exc).__name__ + ": " + str(exc)[:400]}]}
        scenario_results.append(result)
    counts = {status: sum(r["status"] == status for r in scenario_results) for status in ("passed", "failed", "blocked")}
    report = {
        "schema": "navowork-eval-report/1", "created_at": datetime.now(timezone.utc).isoformat(),
        "repository_head": git_head(), "seed": seed, "data": "SIMULATED", "adapter": adapter,
        "implementation_files": implementation_manifest(),
        "evidence_directory": output.relative_to(REPO).as_posix(),
        "requested_mode": mode, "status": "failed" if counts["failed"] else "blocked" if counts["blocked"] else "passed",
        "status_scope": "scenario_checks_only",
        "summary": {"scenarios": len(scenario_results), **counts},
        "layers": {
            "offline": {"status": "executed" if adapter in ("reference", "mutant") else "not_classified_as_offline"},
            "real_model": {"status": "not_executed" if adapter in ("reference", "mutant", "unavailable") else "reported_unverified" if any(r.get("model_calls_reported") for r in scenario_results) else "not_verified",
                           "reported_calls": sum(r.get("model_calls_reported", 0) for r in scenario_results)},
            "file_content": {"status": "inspected" if any(r.get("output_evidence") for r in scenario_results) else "not_inspected"},
            "file_visual": {"status": "not_performed", "reason": "No rendering or human visual review was performed by this harness."},
        },
        "phases": {
            "independent_harness": {"status": "executed" if adapter != "unavailable" else "ready_runtime_blocked"},
            "main_chain_integration": {"status": "blocked", "reason": "Authenticated backend/Worker end-to-end evidence is pending; committed protocol checks are recorded separately."},
        },
        "product_acceptance": {"status": "not_accepted", "reason": "Offline fixtures/adapter reports do not establish real Agent, backend integration, authorization enforcement or UI/visual acceptance."},
        "trust_boundary": "Adapter events and model receipts are self-reported unless independently reconciled with authenticated host/service logs. Local module/command transports are not an OS sandbox.",
        "declared_fixture_integrity": audit_fixtures(), "input_inventory": inventory, "scenarios": scenario_results,
    }
    write_json(output / "report.json", report)
    failures = [f"{r['id']} step={f.get('step')} [{f['code']}] {f['message']}" for r in scenario_results for f in r["findings"]]
    if not failures:
        failures.append("No scenario check failures; this does not establish product acceptance.")
    failures.extend("PRECONDITION [FIXTURE_HASH_MISMATCH] " + m["path"] for m in report["declared_fixture_integrity"]["mismatches"])
    failures.append("NOT_ACCEPTED [MAIN_CHAIN_BLOCKED] Real Agent/Worker integration and independent model/visual evidence are pending.")
    (output / "failures.txt").write_text("\n".join(failures) + "\n", encoding="utf-8")
    return report
