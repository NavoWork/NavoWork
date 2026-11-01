from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}\Z", re.ASCII)


class MockError(ValueError):
    """Stable diagnostic code without input content or filesystem paths."""


def _identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise MockError("mock_identifier_invalid")
    return value


def _json_value(value, depth=0):
    if depth > 50:
        raise MockError("mock_json_too_deep")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item, depth + 1)
        return
    raise MockError("mock_json_value_invalid")


def fingerprint(value: Any) -> dict:
    """bytes → exact SHA-256; JSON → sorted compact UTF-8 JSON v1 → SHA-256."""
    if type(value) is bytes:
        if len(value) > MAX_FILE_BYTES:
            raise MockError("mock_input_too_large")
        kind, encoded = "bytes", value
    else:
        _json_value(value)
        try:
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
        except (ValueError, TypeError, UnicodeError):
            raise MockError("mock_json_value_invalid") from None
        if len(encoded) > MAX_JSON_BYTES:
            raise MockError("mock_input_too_large")
        kind = "json-v1"
    return {"kind": kind, "sha256": hashlib.sha256(encoded).hexdigest()}


def read_bytes(path: Path, limit: int = MAX_FILE_BYTES) -> bytes:
    try:
        with Path(path).open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError:
        raise MockError("mock_file_unavailable") from None
    if len(data) > limit:
        raise MockError("mock_file_too_large")
    return data


def decode_json(data: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise MockError("mock_json_duplicate_key")
            result[key] = value
        return result
    try:
        value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs)
        _json_value(value)
        return value
    except MockError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise MockError("mock_json_invalid") from None


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value, re.ASCII):
        raise MockError("mock_digest_invalid")
    return value


def _input_key(inputs: dict):
    if not isinstance(inputs, dict) or not inputs or len(inputs) > 32:
        raise MockError("mock_inputs_invalid")
    parts = []
    for name, item in inputs.items():
        _identifier(name)
        if not isinstance(item, dict) or set(item) != {"kind", "sha256"} or item["kind"] not in ("bytes", "json-v1"):
            raise MockError("mock_input_fingerprint_invalid")
        parts.append((name, item["kind"], _digest(item["sha256"])))
    return tuple(sorted(parts))


class Catalog:
    """Immutable catalog snapshot with exact workflow/operation/input matching.

    Output fixtures remain external assets. Their pinned JSON digest is checked
    before every replay, so editing a fixture requires explicitly updating it.
    """

    def __init__(self, document: dict, root: Path):
        if not isinstance(document, dict) or set(document) != {"schema_version", "catalog_id", "scenarios"}:
            raise MockError("mock_catalog_schema_invalid")
        if type(document["schema_version"]) is not int or document["schema_version"] != 1:
            raise MockError("mock_catalog_version_unsupported")
        self.catalog_id = _identifier(document["catalog_id"])
        self._root = Path(root).resolve()
        self._document = copy.deepcopy(document)
        self._index = {}
        ids = set()
        scenarios = self._document["scenarios"]
        if not isinstance(scenarios, list) or len(scenarios) > 1000:
            raise MockError("mock_scenarios_invalid")
        for scenario in scenarios:
            if not isinstance(scenario, dict) or set(scenario) != {"id", "workflow", "operation", "inputs", "output"}:
                raise MockError("mock_scenario_schema_invalid")
            sid = _identifier(scenario["id"])
            if sid in ids:
                raise MockError("mock_scenario_id_duplicate")
            ids.add(sid)
            key = (_identifier(scenario["workflow"]), _identifier(scenario["operation"]), _input_key(scenario["inputs"]))
            if key in self._index:
                raise MockError("mock_match_ambiguous")
            output = scenario["output"]
            if not isinstance(output, dict) or set(output) != {"path", "sha256"}:
                raise MockError("mock_output_invalid")
            self._output_path(output["path"])
            _digest(output["sha256"])
            self._index[key] = scenario

    @classmethod
    def load(cls, path: Path | str):
        path = Path(path)
        return cls(decode_json(read_bytes(path, MAX_JSON_BYTES)), path.resolve().parent)

    def _output_path(self, relative):
        if not isinstance(relative, str) or not relative:
            raise MockError("mock_output_path_invalid")
        path = Path(relative)
        try:
            resolved = (self._root / path).resolve()
            if path.is_absolute() or not resolved.is_relative_to(self._root) or resolved == self._root:
                raise MockError("mock_output_path_outside_catalog")
            return resolved
        except MockError:
            raise
        except (OSError, ValueError):
            raise MockError("mock_output_path_invalid") from None

    def _read_output(self, scenario):
        # Resolve again to catch a symlink redirected after catalog construction.
        data = decode_json(read_bytes(self._output_path(scenario["output"]["path"]), MAX_JSON_BYTES))
        if fingerprint(data)["sha256"] != scenario["output"]["sha256"]:
            raise MockError("mock_output_hash_mismatch")
        return data

    def replay(self, workflow: str, operation: str, inputs: dict) -> dict:
        if not isinstance(inputs, dict) or not 1 <= len(inputs) <= 32:
            raise MockError("mock_inputs_invalid")
        fingerprints = {name: fingerprint(value) for name, value in inputs.items()}
        key = (_identifier(workflow), _identifier(operation), _input_key(fingerprints))
        scenario = self._index.get(key)
        if scenario is None:
            raise MockError("mock_sample_not_found")
        return {"mode": "mock", "mock": {"catalog_id": self.catalog_id, "schema_version": 1,
                "scenario_id": scenario["id"], "workflow": workflow, "operation": operation,
                "inputs": fingerprints, "output_json_sha256": scenario["output"]["sha256"]},
                "data": self._read_output(scenario)}

    def check(self) -> dict:
        """Validate all output hashes and JSON, including scenarios not replayed yet."""
        for scenario in self._index.values():
            self._read_output(scenario)
        return {"mode": "mock", "catalog_id": self.catalog_id, "scenario_count": len(self._index), "valid": True}
