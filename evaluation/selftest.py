"""Mutation testing: a nonzero failure count alone is insufficient to kill a mutant."""
from __future__ import annotations

from pathlib import Path

from .mutants import MUTATIONS
from .runner import run_suite, write_json
from .suite import REPO


def self_test(output: Path, seed=7319):
    output = output.resolve()
    if not output.is_relative_to(REPO / "evaluation"):
        raise ValueError("output must stay under evaluation/")
    output.mkdir(parents=True, exist_ok=False)
    control = run_suite(output / "control", adapter="reference", seed=seed)
    mutations = []
    for mutation, target_code in MUTATIONS.items():
        report = run_suite(output / mutation, adapter="mutant", mutation=mutation, seed=seed)
        hits = [{"scenario": r["id"], "step": f["step"], "code": f["code"]}
                for r in report["scenarios"] for f in r["findings"] if f["code"] == target_code]
        mutations.append({"mutation": mutation, "target_code": target_code, "status": "killed" if hits else "survived", "hits": hits,
                          "report": f"{mutation}/report.json"})
    killed = sum(m["status"] == "killed" for m in mutations)
    passed = control["status"] == "passed" and killed == len(MUTATIONS)
    result = {"schema": "navowork-evaluator-selftest/1", "status": "passed" if passed else "failed", "seed": seed,
              "implementation_files": control["implementation_files"],
              "summary": {"control": control["summary"], "mutations": len(MUTATIONS), "killed": killed, "survived": len(MUTATIONS) - killed},
              "mutations": mutations, "declared_fixture_integrity": control["declared_fixture_integrity"],
              "layers": {"offline": "executed", "real_model": "not_executed", "file_visual": "not_performed"},
              "product_acceptance": "not_accepted", "main_chain_integration": "blocked"}
    write_json(output / "report.json", result)
    lines = (["Positive control failed; inspect control/failures.txt"] if control["status"] != "passed" else [])
    lines.extend(m["mutation"] + ": target invariant not detected (" + m["target_code"] + ")" for m in mutations if m["status"] == "survived")
    (output / "failures.txt").write_text("\n".join(lines) + ("\n" if lines else "No evaluator self-test failures. Product remains not accepted.\n"), encoding="utf-8")
    return result
