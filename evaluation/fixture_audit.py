"""Audit declared fixture hashes without rewriting/resealing original inputs."""
from __future__ import annotations

import json

from .inspection import digest
from .suite import REPO


def audit_fixtures():
    entries = []
    for case_file in sorted((REPO / "test/cases").glob("*.json")):
        case = json.loads(case_file.read_text(encoding="utf-8-sig"))
        for source in case["sources"]:
            entries.append((f"test/inputs/{case['case']['id']}/{source['name']}", source["sha256"]))
    manifest = json.loads((REPO / "test/core15/manifest.json").read_text(encoding="utf-8-sig"))
    entries.extend(("test/core15/" + item["path"], item["sha256"]) for item in manifest["evidence"])
    entries.extend(("test/core15/" + path, sha) for path, sha in manifest["artifact_hashes"].items())
    mismatches = []
    for path, declared in entries:
        target = REPO / path
        actual = digest(target.read_bytes()) if target.is_file() else None
        if actual != declared:
            data = target.read_bytes() if target.is_file() else b""
            mismatches.append({"path": path, "declared_sha256": declared, "actual_sha256": actual,
                               "lf_normalized_matches_declared": actual is not None and digest(data.replace(b"\r\n", b"\n")) == declared})
    return {"status": "failed" if mismatches else "passed", "files_checked": len(entries), "mismatches": mismatches,
            "policy": "Never normalize, repair or reseal test/ in this harness. Scenario checks bind actual raw bytes; declared-fixture integrity is a separate acceptance precondition.",
            "core15_evidence_used_as_agent_input": False}
