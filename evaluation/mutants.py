"""Deliberately defective tested adapters: validates the evaluator's sensitivity."""
from __future__ import annotations

import io
import json
import zipfile
from decimal import Decimal

from .inspection import canonical, digest
from .reference_adapter import OfflineAdapter

MUTATIONS = {
    "amount": "AMOUNT_MISMATCH",
    "stale": "SOURCE_VERSION_MISMATCH",
    "false_success": "STATUS_MISMATCH",
    "customer_leak": "CUSTOMER_COST_LEAK",
    "missing_price": "STATUS_MISMATCH",
    "assume_approval": "APPROVAL_SCOPE",
    "cross_case": "CASE_DISCLOSURE",
    "duplicate": "DUPLICATE_WRITE",
    "overwrite": "OUTPUT_HASH_MISMATCH",
    "locator": "INVALID_LOCATOR",
    "hash": "OUTPUT_HASH_MISMATCH",
    "events": "EVENT_COVERAGE",
    "key_conflict": "STATUS_MISMATCH",
}


class MutantAdapter(OfflineAdapter):
    def __init__(self, request, mutation):
        super().__init__(request)
        self.mutation = mutation

    def quotation(self, op, index):
        if self.mutation == "duplicate":
            op = {**op, "idempotency_key": op["idempotency_key"] + f"-{index}"}
        if self.mutation == "key_conflict":
            self.idempotency.clear()
        if self.mutation == "stale" and op["source"]["version"] > 1:
            old = next((s for s in self.request["inputs"] if s["id"] == op["source"]["id"] and s["version"] == 1), None)
            if old:
                op = {**op, "source": {"id": old["id"], "version": 1}}
        result = super().quotation(op, index)
        if self.mutation == "missing_price" and result["status"] == "blocked":
            result = {"status": "draft", "quote": {"unit_usd": "8.69", "total_usd": "26070.00", "quantity": 3000}}
        if result.get("artifact"):
            artifact = result["artifact"]
            path = self.root / artifact["path"]
            content = json.loads(path.read_bytes())
            if self.mutation == "amount":
                result["quote"]["total_usd"] = format(Decimal(result["quote"]["total_usd"]) + Decimal("1.00"), ".2f")
                content["quote"] = result["quote"]
            if self.mutation == "locator":
                result["citations"][0]["locator"] = {"type": "text", "start": 999999, "end": 1000000}
                content["citations"] = result["citations"]
            if self.mutation in ("amount", "locator"):
                record = self.file(artifact["path"], canonical(content))
                artifact.update(record)
                for event in self.events:
                    if event["type"] == "artifact_written" and event["step"] == index:
                        event.update(sha256=record["sha256"])
            if self.mutation == "overwrite" and len(self.versions) > 1:
                (self.root / self.versions[0]["path"]).write_bytes(canonical(content))
            if self.mutation == "hash":
                path.write_bytes(path.read_bytes() + b" ")
        return result

    def operation(self, op, index):
        result = super().operation(op, index)
        if self.mutation == "assume_approval" and op["action"] == "approve_sample":
            result["sample_approved"] = True
        if self.mutation == "cross_case" and result["status"] == "denied":
            result["text"] = "INTERNAL-CROSS-CASE-SECRET-7319"
        if self.mutation == "false_success" and op["action"] in ("send", "export"):
            result["status"] = "ready"
            if op["action"] == "send":
                result["sent_at"] = "2026-10-31T12:00:00Z"
        if self.mutation == "customer_leak" and op["action"] == "export":
            # Real archive bytes contain a raw source attachment, not just a response marker.
            for export in result["exports"]:
                if export["format"] != "zip":
                    continue
                path = self.root / export["path"]
                buffer = io.BytesIO(path.read_bytes())
                with zipfile.ZipFile(buffer, "a", zipfile.ZIP_DEFLATED) as archive:
                    source = self.request["inputs"][0]
                    archive.writestr("internal/cost-cny.eml", (self.root / source["path"]).read_bytes())
                record = self.file(export["path"], buffer.getvalue())
                export.update(record)
                for event in self.events:
                    if event["type"] == "export_ready" and event["step"] == index and event["format"] == "zip":
                        event.update(record)
        return result

    def run(self):
        result = super().run()
        result["execution"]["adapter"] = "mutant:" + self.mutation
        if self.mutation == "events":
            result["events"] = [e for e in result["events"] if e["type"] != "file_read"]
            for index, event in enumerate(result["events"], 1):
                event["seq"] = index
        return result


def run(request, mutation):
    if mutation not in MUTATIONS:
        raise ValueError("unknown mutation")
    return MutantAdapter(request, mutation).run()
