from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from .catalog import Catalog, MAX_JSON_BYTES, MockError, _identifier, decode_json, fingerprint, read_bytes


def _inputs(args):
    result = {}
    for kind, items in (("file", args.file), ("json", args.json)):
        for item in items:
            name, separator, path = item.partition("=")
            if not separator or not path or name in result:
                raise MockError("mock_input_argument_invalid")
            _identifier(name)
            data = read_bytes(Path(path), MAX_JSON_BYTES) if kind == "json" else read_bytes(Path(path))
            result[name] = decode_json(data) if kind == "json" else data
    if not 1 <= len(result) <= 32:
        raise MockError("mock_inputs_invalid")
    return result


def _add(args, inputs):
    path = args.catalog.resolve()
    if path.exists():
        document = decode_json(read_bytes(path, MAX_JSON_BYTES))
        Catalog(document, path.parent).check()
        if args.catalog_id and args.catalog_id != document["catalog_id"]:
            raise MockError("mock_catalog_id_conflict")
    else:
        if not args.catalog_id:
            raise MockError("mock_catalog_id_required")
        document = {"schema_version": 1, "catalog_id": args.catalog_id, "scenarios": []}
    try:
        relative = args.output.resolve().relative_to(path.parent).as_posix()
    except ValueError:
        raise MockError("mock_output_path_outside_catalog") from None
    if args.output.resolve() == path:
        raise MockError("mock_output_is_catalog")
    output = read_bytes(args.output, MAX_JSON_BYTES)
    output_data = decode_json(output)
    document["scenarios"].append({"id": args.scenario, "workflow": args.workflow, "operation": args.operation,
                                  "inputs": {name: fingerprint(value) for name, value in inputs.items()},
                                  "output": {"path": relative, "sha256": fingerprint(output_data)["sha256"]}})
    catalog = Catalog(document, path.parent)
    catalog.check()
    # Authoring command only; replay never modifies catalogs or fixture files.
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return catalog.check()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Deterministic demo fixtures; no models or agents")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("fingerprint", "add", "run", "check"):
        child = sub.add_parser(command)
        if command != "fingerprint":
            child.add_argument("--catalog", type=Path, required=True)
        if command in ("add", "run"):
            child.add_argument("--workflow", required=True)
            child.add_argument("--operation", required=True)
        if command != "check":
            child.add_argument("--file", action="append", default=[], metavar="NAME=PATH")
            child.add_argument("--json", action="append", default=[], metavar="NAME=PATH")
        if command == "add":
            child.add_argument("--catalog-id", help="required when creating a catalog")
            child.add_argument("--scenario", required=True)
            child.add_argument("--output", type=Path, required=True, help="existing JSON fixture inside catalog directory")
        if command == "run":
            child.add_argument("--out", type=Path, help="new result file; refuses overwrite")
    args = parser.parse_args(argv)
    try:
        inputs = _inputs(args) if args.command != "check" else None
        if args.command == "check":
            result = Catalog.load(args.catalog).check()
        elif args.command == "fingerprint":
            if not inputs:
                raise MockError("mock_inputs_invalid")
            result = {name: fingerprint(value) for name, value in inputs.items()}
        elif args.command == "add":
            result = _add(args, inputs)
        else:
            result = Catalog.load(args.catalog).replay(args.workflow, args.operation, inputs)
        output = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if getattr(args, "out", None):
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(output)
        else:
            sys.stdout.write(output)
        return 0
    except MockError as exc:
        sys.stderr.write(json.dumps({"status": "blocked", "mode": "mock", "code": str(exc)}) + "\n")
        return 2
    except (OSError, ValueError, TypeError):
        sys.stderr.write('{"status":"blocked","mode":"mock","code":"mock_local_io_failed"}\n')
        return 2
