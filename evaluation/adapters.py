"""Trusted transport shims. Business expectations are never sent over the boundary."""
from __future__ import annotations

import base64
import importlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path

from .inspection import canonical, confined

MAX_RESPONSE = 20_000_000


class Unavailable(RuntimeError):
    pass


def invoke(request, *, adapter="unavailable", module=None, command=None, endpoint=None,
           token_env=None, timeout=30, mutation=None):
    if adapter == "unavailable":
        raise Unavailable("No tested runtime/interface configured. Product acceptance is blocked.")
    if adapter == "reference":
        from .reference_adapter import run
        return run(request), request
    if adapter == "mutant":
        from .mutants import run
        return run(request, mutation), request
    if adapter == "module":
        name, function = module.split(":", 1)
        return getattr(importlib.import_module(name), function)(json.loads(canonical(request))), request
    if adapter == "command":
        if not isinstance(command, list) or not command or any(not isinstance(v, str) for v in command):
            raise ValueError("command must be a JSON array of strings")
        # No shell, no implicit repo cwd. This is hygiene, not OS-level isolation.
        result = subprocess.run(command, input=canonical(request), capture_output=True,
                                cwd=request["workspace"], timeout=timeout, check=False)
        if result.returncode:
            raise RuntimeError(f"tested command exited {result.returncode}; no success inferred")
        if len(result.stdout) > MAX_RESPONSE:
            raise ValueError("response size limit exceeded")
        return json.loads(result.stdout), request
    if adapter == "http":
        if not endpoint or not endpoint.startswith(("http://", "https://")):
            raise ValueError("HTTP(S) evaluation endpoint required")
        # A server shim receives bytes, never local filesystem paths to the repository/oracle.
        wire = json.loads(canonical(request))
        wire["workspace"] = "."
        for item in wire["inputs"]:
            item["data_base64"] = base64.b64encode(confined(Path(request["workspace"]), item["path"]).read_bytes()).decode("ascii")
        headers = {"Content-Type": "application/json"}
        if token_env:
            headers["Authorization"] = "Bearer " + os.environ[token_env]
        payload = urllib.request.Request(endpoint, data=canonical(wire), headers=headers, method="POST")
        with urllib.request.urlopen(payload, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("response size limit exceeded")
        result = json.loads(raw)
        for output in result.pop("output_files", []):
            relative = output["path"]
            if not relative.startswith("outputs/"):
                raise ValueError("remote output outside outputs/")
            target = confined(Path(request["workspace"]), relative)
            if target.exists():
                raise ValueError("duplicate remote output path")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(output["data_base64"], validate=True))
        return result, wire
    raise ValueError("unknown adapter")
