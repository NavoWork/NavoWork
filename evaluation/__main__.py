"""python -m evaluation: independent CLI, without touching repository root configuration."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .runner import run_suite, write_json
from .suite import REPO, build_suite


def default_output(prefix):
    return REPO / "evaluation/runs" / (prefix + "-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("list", help="list scenario IDs and coverage; never send this output to the Agent")
    run = sub.add_parser("run")
    run.add_argument("--adapter", choices=["unavailable", "reference", "module", "command", "http"], default="unavailable")
    run.add_argument("--module", help="trusted Python module:function")
    run.add_argument("--command-json", help="JSON argv array; shell is never used")
    run.add_argument("--endpoint", help="server-side evaluation shim HTTP(S) endpoint")
    run.add_argument("--token-env", help="environment variable containing endpoint bearer token; value is not recorded")
    run.add_argument("--timeout", type=float, default=30)
    run.add_argument("--mode", choices=["offline", "real-model"], default="offline")
    run.add_argument("--scenario", action="append")
    run.add_argument("--seed", type=int, default=7319)
    run.add_argument("--output", type=Path)
    selftest = sub.add_parser("self-test", help="positive control plus defective adapter mutation validation")
    selftest.add_argument("--output", type=Path)
    selftest.add_argument("--seed", type=int, default=7319)
    probe = sub.add_parser("backend-probe", help="execute selected checked-in pure function ASTs, not the backend service")
    probe.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.operation == "list":
        print(json.dumps([{"id": s.id, "title": s.title, "coverage": s.coverage} for s in build_suite()], ensure_ascii=False, indent=2))
        return 0
    if args.operation == "backend-probe":
        from .backend_probe import probe_backend
        output = args.output or default_output("backend-probe")
        output = output.resolve()
        if not output.is_relative_to(REPO / "evaluation"):
            parser.error("output must stay under evaluation/")
        output.mkdir(parents=True, exist_ok=False)
        result = probe_backend()
        write_json(output / "report.json", result)
        print(f"Backend function observations: {output / 'report.json'}; product NOT ACCEPTED")
        return 0 if result["status"] == "completed" else 2
    if args.operation == "self-test":
        from .selftest import self_test
        output = args.output or default_output("self-test")
        result = self_test(output, args.seed)
        print(json.dumps(result["summary"], ensure_ascii=False))
        print(f"Report: {output.resolve() / 'report.json'}; product NOT ACCEPTED")
        return 0 if result["status"] == "passed" else 1
    if not 0 < args.timeout <= 55:
        parser.error("timeout must be > 0 and <= 55 seconds")
    for adapter, required in (("module", args.module), ("command", args.command_json), ("http", args.endpoint)):
        if args.adapter == adapter and not required:
            parser.error(f"{adapter} adapter requires its configuration argument")
    output = args.output or default_output("run")
    result = run_suite(output, seed=args.seed, selected=args.scenario, mode=args.mode, adapter=args.adapter,
                       module=args.module, command=json.loads(args.command_json) if args.command_json else None,
                       endpoint=args.endpoint, token_env=args.token_env, timeout=args.timeout)
    print(json.dumps(result["summary"]))
    if result["declared_fixture_integrity"]["status"] != "passed":
        print(f"Declared fixture integrity FAILED: {len(result['declared_fixture_integrity']['mismatches'])} hash mismatches; see report.json")
    print(f"Report: {output.resolve() / 'report.json'}; product NOT ACCEPTED")
    return 1 if result["summary"]["failed"] else 2 if result["summary"]["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
