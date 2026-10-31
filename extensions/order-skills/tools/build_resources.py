"""Regenerate self-contained JSON Schemas and explicitly synthetic CLI examples."""

from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from support import order, sample, field  # noqa: E402 -- synthetic fixture builder only


def object_schema(properties, required=()):
    return {"type": "object", "properties": properties,
            "required": list(required), "additionalProperties": False}


def ref(name):
    return {"$ref": f"#/$defs/{name}"}


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


def schemas():
    string = {"type": "string", "minLength": 1}
    boolean = {"type": "boolean"}
    evidence = object_schema({name: string for name in ("case_id", "source_id", "locator", "quote", "role")})
    located_field = object_schema({"value": nullable(string), "raw": nullable(string), "evidence": nullable(ref("evidence"))})
    statement = object_schema({"decision": {"enum": ["full", "partial", "conditional", "rejected", None]},
                               "conditions": {"type": "array", "items": string},
                               "scope": string, "version_id": string, "sample_id": string,
                               "evidence": nullable(ref("evidence"))})
    feedback = object_schema({"field": string, "observation": string, "requested_change": string,
                              "evidence": nullable(ref("evidence"))}, ("field", "observation"))
    headers = ("buyer", "seller", "total_quantity", "total_amount", "currency", "incoterm",
               "named_place", "incoterms_edition", "payment_terms", "spec_version_id", "delivery_terms")
    line = object_schema({"line_id": string, **{key: nullable(ref("field")) for key in ("sku", "quantity", "unit", "unit_price", "amount")}}, ("line_id",))
    document = object_schema({**{key: nullable(ref("field")) for key in headers}, "lines": {"type": "array", "items": ref("line")}})
    baseline = object_schema({"version_id": string, "status": {"enum": ["draft", "reviewed", "released", "superseded"]},
                              "document": ref("document"), "customer_acceptance": nullable(ref("statement"))}, ("version_id", "status", "document"))
    sample_input = object_schema({"case_id": string, "sample_id": string, "spec_version_id": string,
                                  "response": ref("statement"), "feedback": {"type": "array", "items": ref("feedback")}}, ("case_id", "sample_id", "spec_version_id"))
    order_props = {"case_id": string, "po": ref("document"), "baseline": ref("baseline")}
    order_input = object_schema(order_props, order_props)
    pi_input = object_schema({**order_props, "sample": nullable(ref("sampleRequest")),
                             "pi_number": nullable(string), "issue_date": nullable(string)}, order_props)
    finding = object_schema({"code": string, "path": string, "message": string,
                             "severity": {"enum": ["review", "block", "info"]}}, ("code", "path", "message", "severity"))
    findings = {"type": "array", "items": ref("finding")}
    modification = object_schema({**feedback["properties"], "sample_id": string, "spec_version_id": string,
                                   "status": {"const": "proposed_requires_review"}},
                                  ("sample_id", "spec_version_id", "field", "observation", "requested_change", "evidence", "status"))
    sample_props = {"case_id": string, "sample_id": string, "spec_version_id": string,
                    "response_kind": {"enum": ["full", "partial", "conditional", "rejected", "unknown"]},
                    "sample_approval_supported": boolean, "approval_scope": {"const": "sample_review_only"},
                    "feedback": {"type": "array", "items": ref("feedback")},
                    "modifications": {"type": "array", "items": ref("modification")},
                    "conditions": {"type": "array", "items": string}, "response": ref("statement"),
                    "findings": findings, "production_release": {"const": "not_evaluated"}}
    basis = object_schema({"version_id": string, "status": baseline["properties"]["status"],
                           "customer_acceptance_supported": boolean, "customer_acceptance": nullable(ref("statement"))},
                          ("version_id", "status", "customer_acceptance_supported", "customer_acceptance"))
    difference = object_schema({"path": string, "po": nullable({"type": "object"}), "baseline": nullable({"type": "object"})}, ("path", "po", "baseline"))
    po_props = {"case_id": string, "basis": ref("basis"), "differences": {"type": "array", "items": ref("difference")},
                "findings": findings, "po": ref("document"), "baseline_document": ref("document"),
                "comparison_complete": boolean, "order_execution_authorized": {"const": False}}
    prerequisite = object_schema({"key": string, "state": {"enum": ["pending", "evidence_supported"]},
                                  "sample_id": nullable(string), "spec_version_id": nullable(string)}, ("key", "state"))
    pending = object_schema({"key": string, "reason": string, "code": string}, ("key", "reason"))
    content = object_schema({"pi_number": nullable(string), "issue_date": nullable(string),
                             "commercial_terms": ref("document"), "comparison_basis": ref("basis")},
                            ("pi_number", "issue_date", "commercial_terms", "comparison_basis"))
    pi_props = {"case_id": string, "document_kind": {"const": "proforma_invoice"}, "status": {"const": "draft"},
                "title": string, "content": content, "sample_review": nullable(ref("sampleResult")), "po_review": ref("poResult"),
                "execution_prerequisites": {"type": "array", "items": prerequisite},
                "pending_confirmations": {"type": "array", "items": pending}, "findings": findings,
                "signed": {"const": False}, "payment_received": {"const": False}, "production_released": {"const": False},
                "file_generation": {"const": "host_tool_required"}, "notice": string}
    return {"evidence": evidence, "field": located_field, "statement": statement,
            "feedback": feedback, "line": line, "document": document, "baseline": baseline,
            "finding": finding, "modification": modification, "basis": basis, "difference": difference,
            "sampleRequest": sample_input, "orderRequest": order_input, "piRequest": pi_input,
            "sampleResult": object_schema(sample_props, sample_props),
            "poResult": object_schema(po_props, po_props), "piResult": object_schema(pi_props, pi_props)}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reachable(definitions, name):
    selected = {}

    def visit(value):
        if isinstance(value, dict):
            target = value.get("$ref", "").removeprefix("#/$defs/")
            if target in definitions and target not in selected:
                selected[target] = definitions[target]
                visit(definitions[target])
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(ref(name))
    return selected


def main():
    definitions = schemas()
    for skill, request, result in (("sample-feedback", "sampleRequest", "sampleResult"),
                                    ("po-check", "orderRequest", "poResult"), ("pi-prepare", "piRequest", "piResult")):
        for direction, name in (("input", request), ("output", result)):
            # Each schema is self-contained; no runtime registry or remote fetch needed.
            dump(ROOT / "skills" / skill / f"{direction}.schema.json", {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": f"order-skills/{skill}/{direction} (domain data only)",
                **ref(name), "$defs": deepcopy(reachable(definitions, name))})
    conditional = sample("conditional")
    conditional["response"]["conditions"] = ["Review revised 60 mm logo and physical color-box sample"]
    conditional["feedback"] = [{"field": "logo.width_mm", "observation": "SIMULATED: 50 mm on submitted sample",
                                 "requested_change": "Propose 60 mm and obtain new sample review",
                                 "evidence": deepcopy(conditional["response"]["evidence"])}]
    draft_basis = order()
    draft_basis["baseline"]["status"] = "draft"
    del draft_basis["baseline"]["customer_acceptance"]
    conflicting = deepcopy(draft_basis)
    conflicting["po"]["named_place"] = field("Shanghai", "Trade term", "synthetic-conflicting-po")
    conflicting["po"]["named_place"]["raw"] = "FOB Shanghai, Incoterms 2020"
    conflicting["po"]["named_place"]["evidence"]["quote"] = conflicting["po"]["named_place"]["raw"]
    pi = deepcopy(draft_basis)
    pi["pi_number"] = "SIMULATED-PI-DRAFT-001"
    pi["issue_date"] = "2026-10-31"
    for name, value in (("sample-conditional", conditional), ("po-missing-acceptance", draft_basis),
                         ("po-port-conflict", conflicting), ("pi-without-approved-sample", pi)):
        dump(ROOT / "examples" / f"{name}.json", value)


if __name__ == "__main__":
    main()
