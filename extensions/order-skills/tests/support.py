"""Explicit synthetic domain fixtures; not commercial records or host contracts."""

from copy import deepcopy

CASE = "BAG-2026-DE-001"


def evidence(quote="SIMULATED located statement", source="synthetic-source", role="customer_approval", locator="body:paragraph-1"):
    return {"case_id": CASE, "source_id": source, "locator": locator, "quote": quote, "role": role}


def field(value, name, source="synthetic-po"):
    return {"value": value, "raw": value,
            "evidence": evidence(value, source, "customer_po", f"page:1;field:{name}")}


def sample(decision="full"):
    return {"case_id": CASE, "sample_id": "S03", "spec_version_id": "spec-v3",
            "response": {"decision": decision, "conditions": [], "scope": "sample",
                         "version_id": "spec-v3", "sample_id": "S03",
                         "evidence": evidence("SIMULATED: We approve sample S03 against spec-v3.")},
            "feedback": []}


def document():
    values = {"buyer": "Weber Outdoor", "seller": "Navo Demo", "total_quantity": "3000",
              "total_amount": "27630.00", "currency": "USD", "incoterm": "FOB",
              "named_place": "Ningbo", "incoterms_edition": "2020",
              "payment_terms": "30% deposit, 70% against copy of shipping documents",
              "spec_version_id": "spec-v3", "delivery_terms": "Arrival requested; no guarantee"}
    doc = {name: field(value, name) for name, value in values.items()}
    doc["lines"] = [{"line_id": "1", **{name: field(value, name) for name, value in
                    {"sku": "WB-26/navy", "quantity": "3000", "unit": "piece",
                     "unit_price": "9.21", "amount": "27630.00"}.items()}}]
    return doc


def order():
    doc = document()
    return {"case_id": CASE, "po": doc,
            "baseline": {"version_id": "quote-v3", "status": "released",
                         "document": deepcopy(doc), "customer_acceptance": {
                             "decision": "full", "scope": "commercial", "version_id": "quote-v3",
                             "conditions": [], "evidence": evidence("SIMULATED: We accept quotation quote-v3.")}}}
