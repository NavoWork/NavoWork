"""OFFLINE protocol demonstrator, not an Agent or product implementation.

This adapter reads staged business files. It deliberately cannot import the suite/oracle.
Its narrow parsers are fixture helpers, not production extraction logic.
"""
from __future__ import annotations

import copy
import html
import io
import json
import re
import sys
import zipfile
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

from .inspection import canonical, confined, digest, pdf_pages, xlsx_cells


class OfflineAdapter:
    def __init__(self, request: dict):
        self.request = request
        self.root = Path(request["workspace"])
        self.events = []
        self.steps = []
        self.versions = []
        self.idempotency = {}

    def event(self, kind, step=None, **data):
        self.events.append({"seq": len(self.events) + 1, "type": kind, "run_id": self.request["run_id"],
                            "step": step, **data})

    def read(self, ref, step):
        source = next((s for s in self.request["inputs"] if s["id"] == ref["id"] and s["version"] == ref["version"]
                       and s["case_id"] == self.request["case_id"]), None)
        if source is None:
            return None, None
        data = confined(self.root, source["path"]).read_bytes()
        if digest(data) != source["sha256"]:
            raise ValueError("input hash mismatch")
        self.event("file_read", step, source=ref, sha256=digest(data), bytes=len(data))
        return source, data

    def cost(self, source, data):
        suffix = Path(source["name"]).suffix.lower()
        common = {"source": {"id": source["id"], "version": source["version"]}, "sha256": digest(data), "field": "cost_cny"}
        if suffix == ".xlsx":
            cells = xlsx_cells(data)
            value = cells["Factory A Quote", "B13"]
            return value, [{**common, "locator": {"type": "xlsx", "sheet": "Factory A Quote", "cell": "B13"}, "excerpt": value}]
        if suffix == ".pdf":
            for index, page in enumerate(pdf_pages(data), 1):
                match = re.search(r"Estimated cost basis\s+CNY ([0-9.]+) / piece", page)
                if match:
                    return match[1], [{**common, "locator": {"type": "pdf", "page": index, "quote": match[0]}, "excerpt": match[0]}]
            return None, []
        text = data.decode("utf-8-sig")
        match = re.search(r"(?:Confirmed supplier cost basis:|Revised estimated basis:) CNY ([0-9.]+) per piece", text)
        if not match:
            return None, []
        return match[1], [{**common, "locator": {"type": "text", "start": match.start(), "end": match.end()}, "excerpt": match[0]}]

    def file(self, relative, data):
        path = confined(self.root, relative)
        if not relative.startswith("outputs/"):
            raise ValueError("output must be under outputs/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return {"path": relative, "sha256": digest(data), "bytes": len(data)}

    def quotation(self, op, index):
        key = op["idempotency_key"]
        body_hash = digest(canonical(op))
        if key in self.idempotency:
            previous_hash, result = self.idempotency[key]
            if previous_hash != body_hash:
                return {"status": "conflict", "http_status": 409, "reason": "IDEMPOTENCY_CONFLICT"}
            self.event("idempotency_replay", index, artifact_id=result.get("artifact", {}).get("id"))
            return copy.deepcopy(result)
        source, data = self.read(op["source"], index)
        if source is None:
            return {"status": "denied", "http_status": 404}
        cost, citations = self.cost(source, data)
        if cost is None:
            result = {"status": "blocked", "quote": None, "reason": "MISSING_COST"}
            self.idempotency[key] = body_hash, copy.deepcopy(result)
            return result
        unit = (Decimal(cost) / Decimal(op["fx"]) / (1 - Decimal(op["margin"]))).quantize(Decimal(".01"), rounding=ROUND_CEILING)
        quote = {"unit_usd": format(unit, ".2f"), "total_usd": format(unit * op["quantity"], ".2f"), "quantity": op["quantity"]}
        version = len(self.versions) + 1
        prior = self.versions[-1] if self.versions else None
        content = {"case_id": self.request["case_id"], "version": version, "quote": quote, "status": "draft",
                   "base_id": prior["id"] if prior else None, "base_sha256": prior["sha256"] if prior else None,
                   "citations": citations, "cost_cny": cost}
        artifact = {"id": f"quotation-v{version}", "version": version,
                    **self.file(f"outputs/quotation-v{version}.json", canonical(content))}
        self.versions.append(artifact)
        self.event("artifact_written", index, artifact_id=artifact["id"], sha256=artifact["sha256"], path=artifact["path"], idempotency_key=key)
        result = {"status": "draft", "quote": quote, "artifact": artifact, "citations": citations}
        self.idempotency[key] = body_hash, copy.deepcopy(result)
        return result

    def export(self, op, index):
        previous = self.steps[op["step"]]
        quote = previous["quote"]
        # Explicit allowlist: no raw source excerpts, costs, or supplier offers.
        public = {"case_id": self.request["case_id"], "quote": quote, "status": "draft", "sent_at": None}
        body = ("<!doctype html><meta charset='utf-8'><h1>SIMULATED quotation draft</h1><pre>" + html.escape(json.dumps(public)) + "</pre>").encode()
        exports, errors = [], []
        for fmt in op["formats"]:
            if fmt in op.get("faults", {}).get("export_fail", []):
                errors.append({"format": fmt, "code": "EXPORT_FAILED"})
                self.event("export_failed", index, format=fmt, code="EXPORT_FAILED")
                continue
            if fmt == "html":
                data = body
            elif fmt == "zip":
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("quotation.html", body)
                    archive.writestr("manifest.json", canonical(public))
                data = buffer.getvalue()
            else:
                errors.append({"format": fmt, "code": "UNSUPPORTED_FORMAT"})
                self.event("export_failed", index, format=fmt, code="UNSUPPORTED_FORMAT")
                continue
            record = {"format": fmt, "audience": op["audience"], **self.file(f"outputs/customer-{index}.{fmt}", data)}
            exports.append(record)
            self.event("export_ready", index, **record)
        return {"status": "partial" if exports and errors else "failed" if errors else "ready", "exports": exports, "errors": errors}

    def operation(self, op, index):
        action = op["action"]
        if action in ("quote", "quote_change"):
            return self.quotation(op, index)
        if action == "export":
            return self.export(op, index)
        if action == "read_artifact":
            artifact = self.steps[op["step"]]["artifact"]
            data = confined(self.root, artifact["path"]).read_bytes()
            self.event("artifact_read", index, artifact_id=artifact["id"], sha256=digest(data))
            return {"status": "ready", "file": {**artifact, "sha256": digest(data)}}
        source, data = self.read(op["source"], index)
        if source is None:
            self.event("access_denied", index, source=op["source"], http_status=404)
            return {"status": "denied", "http_status": 404}
        if action == "inspect_requirements":
            self.read(op["image"], index)
            return {"status": "draft", "fields": {"dimensions": None, "material_grade": None, "arrival_guaranteed": False}}
        if action == "approve_sample":
            return {"status": "blocked", "sample_approved": False, "reason": "APPROVAL_REQUIRED"}
        if action == "send":
            return {"status": "blocked", "sent_at": None, "reason": "CONNECTOR_UNAVAILABLE"}
        if action == "inspect_untrusted":
            return {"status": "draft", "sent_at": None}
        if action == "read":
            return {"status": "ready", "text": data.decode()}
        raise ValueError(f"unsupported action {action}")

    def run(self):
        self.event("run_started", request_sha256=digest(canonical(self.request)))
        for index, op in enumerate(self.request["operations"]):
            self.event("operation_started", index, action=op["action"])
            result = self.operation(op, index)
            self.steps.append(result)
            self.event("operation_finished", index, status=result["status"])
        self.event("run_finished", status="completed")
        return {"protocol": "navowork-eval/1", "run_id": self.request["run_id"], "case_id": self.request["case_id"],
                "execution": {"kind": "offline", "adapter": "reference", "model": None}, "steps": self.steps, "events": self.events}


def run(request: dict) -> dict:
    return OfflineAdapter(request).run()


if __name__ == "__main__":
    # stdout is exclusively protocol JSON; parser warnings belong to stderr.
    print(json.dumps(run(json.load(sys.stdin)), ensure_ascii=False))
