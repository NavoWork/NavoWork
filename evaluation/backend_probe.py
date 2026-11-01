"""Read-only pure-function observations from the committed backend.

Execute selected ASTs with explicit in-memory collaborators. Never import/start the
service, open its database, send model requests or write to backend storage.
"""
from __future__ import annotations

import ast
import html
import json
import re
from decimal import Decimal, ROUND_CEILING
from types import SimpleNamespace

from .inspection import digest
from .runner import git_head
from .suite import REPO


def load_functions(relative, names, namespace):
    path = REPO / relative
    data = path.read_bytes()
    tree = ast.parse(data, filename=str(path))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {n.name for n in nodes} != set(names):
        raise ValueError("checked-in backend function signature changed")
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return [{"file": relative, "function": n.name, "line": n.lineno, "sha256": digest(data)} for n in nodes]


class ExtractedProxy:
    def __init__(self, **values):
        self.values = {"product": None, "quantity": None, "destination": None, "requested_arrival": None,
                       "customization": None, "specification": None, "missing_fields": [], **values}
        self.__dict__.update(self.values)

    def model_dump(self):
        return dict(self.values)

    @classmethod
    def model_validate(cls, values):
        return cls(**values)


def probe_backend():
    observations, references = [], []
    namespace = {"Decimal": Decimal, "ROUND_CEILING": ROUND_CEILING, "re": re, "Extracted": ExtractedProxy,
                 "extract_with_model": lambda text: None, "decode": json.loads, "uid": lambda prefix: "probe_" + prefix,
                 "now": lambda: "2026-10-31T00:00:00Z"}
    try:
        references += load_functions("backend/app/agent.py", ["price_quote", "extract_without_model", "understand_node", "draft_node"], namespace)
        references += load_functions("backend/app/worker.py", ["build_revision"], namespace)
        quote = namespace["price_quote"]({"base": "44", "packaging": "2", "local": "4", "exchangeRate": "7.20", "margin": "20", "quantity": 3000})
        case = SimpleNamespace(id="probe-case", current_revision=0, payload=json.dumps({"destination": "Hamburg"}))
        run = SimpleNamespace(id="probe-run", job_id="probe-job", payload="{}")
        state = {"extracted": {"product": "backpack", "quantity": 3200, "missing_fields": []}, "quote": quote, "selectedSupplierOfferId": "probe-offer"}
        revision = namespace["build_revision"](case, run, state)
        mismatch = revision["requirements"]["quantity"] != revision["quote"]["quantity"]
        observations.append({"id": "BACKEND-AMOUNT", "status": "observed" if mismatch else "not_observed",
                             "scope": "build_revision pure function with inconsistent input state",
                             "actual": {"requirements_quantity": revision["requirements"]["quantity"], "quote_quantity": revision["quote"]["quantity"],
                                        "subtotal_minor": revision["quote"]["goodsSubtotalMinor"]},
                             "limit": "No API or Worker end-to-end path was run; this proves the function does not reconcile these quantities, not that a live request reaches this state."})
        changed = namespace["understand_node"]({"text": "Please quote 4,800 custom backpacks. New supplier evidence attached.",
                                                "prior_extracted": {"product": "backpack", "quantity": 3000},
                                                "instruction": "Analyze the updated business evidence."})
        observations.append({"id": "BACKEND-STALE", "status": "observed" if changed["extracted"]["quantity"] == 3000 else "not_observed",
                             "scope": "understand_node pure function, model extraction disabled",
                             "actual": {"updated_source_quantity": 4800, "prior_quantity": 3000, "result_quantity": changed["extracted"]["quantity"]},
                             "limit": "Function-level stale field retention; file/version tool integration was not exercised."})
        captured = {}

        def store_blob(db, data, filename, media, case_id):
            captured.update(data=data, filename=filename, media=media)
            return SimpleNamespace(id="probe-blob")

        namespace.update(html=html, json=json, item_view=lambda item: item.value, store_blob=store_blob,
                         create_item=lambda *args, **kwargs: None)
        references += load_functions("backend/app/exports.py", ["export_artifact"], namespace)
        memo = "INTERNAL-PROBE-COST-53.00-MARGIN-20PCT"
        artifacts = namespace["draft_node"]({"kind": "prepare_quote", "extracted": {"product": "backpack"},
                                             "source_texts": [{"id": "internal-note", "content": memo}]} )["artifacts"]
        artifact = SimpleNamespace(id="probe-spec-v1", version=1, value=artifacts[0])
        namespace["export_artifact"](SimpleNamespace(commit=lambda: None), SimpleNamespace(id="probe-case", workspace_id="probe-ws"), artifact, "html")
        retained = memo.encode() in captured["data"]
        observations.append({"id": "BACKEND-RAW-EXPORT", "status": "observed" if retained else "not_observed",
                             "scope": "draft_node spec referenceExcerpts → export_artifact HTML, in-memory store_blob",
                             "actual": {"internal_source_excerpt_retained": retained, "rendered_sha256": digest(captured["data"]), "format": "html"},
                             "limit": "Generic artifact export retains internal excerpts. No customer audience/package route was exercised; do not label this a reproduced customer package leak."})
        observations.extend([
            {"id": "BACKEND-FALSE-SUCCESS", "status": "not_tested", "limit": "No live tool/runtime supplied. Only the intentionally defective adapter demonstrates evaluator detection."},
            {"id": "BACKEND-CUSTOMER-PACKAGE", "status": "not_tested", "limit": "Actual audience-controlled customer package endpoint not provided; mutation test is not a backend reproduction."},
        ])
        status = "completed"
    except Exception as exc:
        status = "blocked"
        observations.append({"id": "PROBE-ERROR", "status": "blocked", "error": type(exc).__name__ + ": " + str(exc)})
    return {"schema": "navowork-backend-observations/1", "status": status, "repository_head": git_head(),
            "execution_layer": "offline_backend_function_probe", "simulated_inputs": True, "model_executed": False,
            "backend_service_executed": False, "file_visual_review": "not_performed", "product_acceptance": "not_accepted",
            "source_references": references, "observations": observations}
