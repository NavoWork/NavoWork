"""Deterministic checks of supplied, located candidates; never an approval service."""

from copy import deepcopy
from decimal import Decimal, localcontext
import re


class InvalidInput(ValueError):
    """Malformed input, distinct from a valid request with missing information."""


DECISIONS = {"full", "partial", "conditional", "rejected"}
HEADERS = ("buyer", "seller", "total_quantity", "total_amount", "currency",
           "incoterm", "named_place", "incoterms_edition", "payment_terms",
           "spec_version_id", "delivery_terms")
LINE_FIELDS = ("sku", "quantity", "unit", "unit_price", "amount")
NUMBERS = {"quantity", "unit_price", "amount", "total_quantity", "total_amount"}
CONDITIONAL = re.compile(r"\b(?:conditional|subject to|provided that|before final approval|but|unless)\b|有条件|但是|但请|待.{0,12}批准|批准前", re.I)
SAMPLE_PENDING = re.compile(r"(?:does not|do not|not) approve.{0,40}(?:sample|specification)|sample approval.{0,30}(?:will follow|pending)|尚未批准|样品.{0,8}待批准", re.I | re.S)
SAMPLE_REJECTED = re.compile(r"\b(?:reject|decline)(?:d)?\b.{0,60}\bsample\b|\b(?:do not|cannot|will not) approve\b.{0,40}\bsample\b|拒绝批准|不批准此样|不接受样品", re.I | re.S)


def text(value, path):
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput(f"{path}: expected nonempty string")
    return value


def obj(value, path):
    if not isinstance(value, dict):
        raise InvalidInput(f"{path}: expected object")
    return value


def rows(value, path):
    if not isinstance(value, list):
        raise InvalidInput(f"{path}: expected array")
    return value


def keys(value, allowed, path):
    unknown = value.keys() - set(allowed)
    if unknown:
        raise InvalidInput(f"{path}: unsupported fields {', '.join(sorted(unknown))}")


def validate_statement(statement, path):
    obj(statement, path)
    keys(statement, ("decision", "conditions", "scope", "version_id", "sample_id", "evidence"), path)
    if statement.get("decision") is not None and (not isinstance(statement["decision"], str) or statement["decision"] not in DECISIONS):
        raise InvalidInput(f"{path}.decision: full/partial/conditional/rejected required")
    for i, condition in enumerate(rows(statement.get("conditions", []), f"{path}.conditions")):
        text(condition, f"{path}.conditions[{i}]")
    if statement.get("evidence") is not None:
        obj(statement["evidence"], f"{path}.evidence")


def finding(code, path, message, severity="review", **details):
    return {"code": code, "path": path, "message": message,
            "severity": severity, **deepcopy(details)}


def located(evidence, case_id):
    if not isinstance(evidence, dict):
        return False
    locator = evidence.get("locator")
    locator_ok = (isinstance(locator, str) and bool(locator.strip())) or (isinstance(locator, dict) and bool(locator))
    return locator_ok and evidence.get("case_id") == case_id and all(
        isinstance(evidence.get(k), str) and evidence[k].strip()
        for k in ("source_id", "quote", "role"))


def decimal(value, path):
    # Bound precision and magnitude so an untrusted document cannot exhaust arithmetic.
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,12}(?:\.\d{1,6})?", value):
        raise InvalidInput(f"{path}: expected nonnegative decimal string (12+6 digits max)")
    return Decimal(value)


def normalize(value, field):
    if field in NUMBERS:
        return decimal(value, field)
    if value is None:
        return None
    if field == "spec_version_id":
        return text(value, field)  # Immutable version identifiers are case-sensitive.
    return " ".join(text(value, field).split()).casefold()


def field_value(field):
    return field.get("value") if isinstance(field, dict) else None


def statement_valid(statement, case_id, version_id, scope, *, sample_id=None):
    if not isinstance(statement, dict):
        return False
    evidence = statement.get("evidence")
    return (statement.get("decision") == "full" and not statement.get("conditions")
            and statement.get("scope") == scope
            and statement.get("version_id") == version_id
            and (sample_id is None or statement.get("sample_id") == sample_id)
            and located(evidence, case_id) and evidence["role"] == "customer_approval"
            and not CONDITIONAL.search(evidence["quote"])
            and (sample_id is None or not SAMPLE_PENDING.search(evidence["quote"])))


def review_sample(request):
    request = obj(request, "request")
    keys(request, ("case_id", "sample_id", "spec_version_id", "response", "feedback"), "request")
    case_id = text(request.get("case_id"), "case_id")
    sample_id = text(request.get("sample_id"), "sample_id")
    spec = text(request.get("spec_version_id"), "spec_version_id")
    statement = obj(request.get("response", {}), "response")
    validate_statement(statement, "response")
    decision = statement.get("decision")
    conditions = rows(statement.get("conditions", []), "response.conditions")
    for i, condition in enumerate(conditions):
        text(condition, f"response.conditions[{i}]")
    feedback = rows(request.get("feedback", []), "feedback")
    findings, modifications = [], []
    if not located(statement.get("evidence"), case_id):
        findings.append(finding("RESPONSE_EVIDENCE_MISSING", "response.evidence", "Customer reply needs same-Case source and locator."))
    for i, item in enumerate(feedback):
        obj(item, f"feedback[{i}]")
        keys(item, ("field", "observation", "requested_change", "evidence"), f"feedback[{i}]")
        text(item.get("field"), f"feedback[{i}].field")
        text(item.get("observation"), f"feedback[{i}].observation")
        if not located(item.get("evidence"), case_id):
            findings.append(finding("FEEDBACK_EVIDENCE_MISSING", f"feedback[{i}]", "Feedback needs same-Case source and locator."))
        if item.get("requested_change"):
            text(item["requested_change"], f"feedback[{i}].requested_change")
            modifications.append({"sample_id": sample_id, "spec_version_id": spec,
                                  "field": item["field"], "observation": item["observation"],
                                  "requested_change": item["requested_change"],
                                  "evidence": deepcopy(item.get("evidence")),
                                  "status": "proposed_requires_review"})
    if SAMPLE_REJECTED.search(str((statement.get("evidence") or {}).get("quote", ""))):
        decision = "rejected"
    elif conditions or CONDITIONAL.search(str((statement.get("evidence") or {}).get("quote", ""))):
        if decision != "rejected":
            decision = "conditional"
    elif decision == "full" and SAMPLE_PENDING.search(str((statement.get("evidence") or {}).get("quote", ""))):
        decision = "partial"
    valid = statement_valid(statement, case_id, spec, "sample", sample_id=sample_id)
    # A proposed modification requires another sample/version review even with a full reply.
    approved = valid and decision == "full" and not modifications and not findings
    if not approved:
        findings.append(finding("SAMPLE_NOT_APPROVED", "response", "No complete, unconditional, located sample approval for this sample/specification.", "block"))
    return {"case_id": case_id, "sample_id": sample_id, "spec_version_id": spec,
            "response_kind": decision or "unknown", "sample_approval_supported": approved,
            "approval_scope": "sample_review_only", "feedback": deepcopy(feedback),
            "modifications": modifications, "conditions": deepcopy(conditions),
            "response": deepcopy(statement), "findings": findings,
            "production_release": "not_evaluated"}


def check_document(document, case_id, path):
    obj(document, path)
    keys(document, (*HEADERS, "lines"), path)
    findings = []
    for name in HEADERS:
        field = document.get(name)
        findings.extend(check_field(field, case_id, f"{path}.{name}", name))
    lines = rows(document.get("lines", []), f"{path}.lines")
    if not lines:
        findings.append(finding("LINES_MISSING", f"{path}.lines", "At least one product line is required."))
    ids = set()
    for i, line in enumerate(lines):
        obj(line, f"{path}.lines[{i}]")
        keys(line, (*LINE_FIELDS, "line_id"), f"{path}.lines[{i}]")
        key = text(line.get("line_id"), f"{path}.lines[{i}].line_id")
        if key in ids:
            raise InvalidInput(f"{path}.lines: duplicate line_id {key}")
        ids.add(key)
        for name in LINE_FIELDS:
            findings.extend(check_field(line.get(name), case_id, f"{path}.lines[{i}].{name}", name))
    with localcontext() as context:
        context.prec = 60
        for i, line in enumerate(lines):
            values = [field_value(line.get(k)) for k in ("quantity", "unit_price", "amount")]
            if all(v is not None for v in values):
                q, p, a = [decimal(v, path) for v in values]
                if q * p != a:
                    findings.append(finding("LINE_AMOUNT_MISMATCH", f"{path}.lines[{i}].amount", "Quantity times supplied unit price differs from supplied line amount.", "block"))
        for total, column in (("total_quantity", "quantity"), ("total_amount", "amount")):
            values = [field_value(line.get(column)) for line in lines]
            if lines and field_value(document.get(total)) is not None and all(v is not None for v in values):
                # Do not sum pieces and cartons without a conversion supplied by another tool.
                units = {normalize(field_value(line.get("unit")), "unit") for line in lines}
                if total == "total_quantity" and (None in units or len(units) != 1):
                    findings.append(finding("MIXED_UNITS", f"{path}.{total}", "Quantity units cannot be summed without a verified conversion.", "block"))
                elif sum((decimal(v, path) for v in values), Decimal(0)) != decimal(field_value(document.get(total)), path):
                    findings.append(finding("TOTAL_MISMATCH", f"{path}.{total}", "Supplied total differs from sum of supplied lines.", "block"))
    return findings


def check_field(field, case_id, path, name):
    if field is None or (isinstance(field, dict) and field.get("value") is None):
        return [finding("FIELD_MISSING", path, "Unknown; do not default or infer.")]
    obj(field, path)
    keys(field, ("value", "raw", "evidence"), path)
    value = field.get("value")
    normalize(value, name)
    if name in ("quantity", "total_quantity") and decimal(value, path) <= 0:
        raise InvalidInput(f"{path}: quantity must be positive")
    if not isinstance(field.get("raw"), str) or not field["raw"].strip() or not located(field.get("evidence"), case_id):
        return [finding("FIELD_EVIDENCE_MISSING", path, "Preserve original wording and same-Case source/field locator.")]
    return []


def compare_po(request):
    request = obj(request, "request")
    keys(request, ("case_id", "po", "baseline"), "request")
    case_id = text(request.get("case_id"), "case_id")
    po = obj(request.get("po"), "po")
    baseline = obj(request.get("baseline"), "baseline")
    keys(baseline, ("version_id", "status", "customer_acceptance", "document"), "baseline")
    version_id = text(baseline.get("version_id"), "baseline.version_id")
    state = baseline.get("status")
    if state not in ("draft", "reviewed", "released", "superseded"):
        raise InvalidInput("baseline.status: draft/reviewed/released/superseded required")
    document = obj(baseline.get("document"), "baseline.document")
    findings = check_document(po, case_id, "po") + check_document(document, case_id, "baseline.document")
    differences = []

    def compare(left, right, name, path):
        lv, rv = field_value(left), field_value(right)
        if lv is not None and rv is not None and normalize(lv, name) != normalize(rv, name):
            differences.append({"path": path, "po": deepcopy(left), "baseline": deepcopy(right)})
            findings.append(finding("PO_BASELINE_CONFLICT", path, "Buyer wording differs from the stated comparison basis.", "block"))

    for name in HEADERS:
        compare(po.get(name), document.get(name), name, f"po.{name}")
    left = {line["line_id"]: line for line in po.get("lines", [])}
    right = {line["line_id"]: line for line in document.get("lines", [])}
    for key in sorted(left.keys() | right.keys()):
        if key not in left or key not in right:
            differences.append({"path": f"po.lines[{key}]", "po": deepcopy(left.get(key)), "baseline": deepcopy(right.get(key))})
            findings.append(finding("LINE_SET_CONFLICT", f"po.lines[{key}]", "Added or missing line; explicit line mapping is required.", "block"))
        else:
            for name in LINE_FIELDS:
                compare(left[key].get(name), right[key].get(name), name, f"po.lines[{key}].{name}")
    acceptance = baseline.get("customer_acceptance")
    if acceptance is not None:
        validate_statement(acceptance, "baseline.customer_acceptance")
    accepted = statement_valid(acceptance, case_id, version_id, "commercial")
    if not accepted:
        findings.append(finding("CUSTOMER_ACCEPTANCE_UNPROVEN", "baseline.customer_acceptance", "Comparison uses the stated candidate baseline; customer acceptance is not established."))
    if state != "released":
        findings.append(finding("BASELINE_NOT_RELEASED", "baseline.status", "Comparison basis is not a currently released quotation."))
    return {"case_id": case_id, "basis": {"version_id": version_id, "status": state,
            "customer_acceptance_supported": accepted, "customer_acceptance": deepcopy(acceptance)},
            "differences": differences, "findings": findings,
            "po": deepcopy(po), "baseline_document": deepcopy(document),
            "comparison_complete": not any(f["code"] in {"FIELD_MISSING", "FIELD_EVIDENCE_MISSING", "LINES_MISSING"} for f in findings),
            "order_execution_authorized": False}


def prepare_pi(request):
    request = obj(request, "request")
    keys(request, ("case_id", "po", "baseline", "sample", "pi_number", "issue_date"), "request")
    for name in ("pi_number", "issue_date"):
        if request.get(name) is not None:
            text(request[name], name)
    comparison = compare_po({k: request.get(k) for k in ("case_id", "po", "baseline")})
    # Always recompute; never trust a caller's 'passed' report.
    case_id = comparison["case_id"]
    spec = field_value(comparison["po"].get("spec_version_id"))
    sample_request = request.get("sample")
    sample = review_sample(sample_request) if sample_request is not None else None
    sample_ok = bool(sample and sample["case_id"] == case_id and
                     sample["spec_version_id"] == spec and sample["sample_approval_supported"])
    findings = deepcopy(comparison["findings"])
    if sample is not None and (sample["case_id"] != case_id or sample["spec_version_id"] != spec):
        findings.append(finding("SAMPLE_SCOPE_MISMATCH", "sample", "Sample must belong to this Case and PI specification.", "block"))
    prerequisites = [
        {"key": "physical_sample_approval", "state": "evidence_supported" if sample_ok else "pending", "sample_id": sample["sample_id"] if sample else None, "spec_version_id": spec},
        {"key": "commercial_terms_review", "state": "pending" if findings else "evidence_supported"},
        {"key": "signed_order_confirmation", "state": "pending"},
        {"key": "deposit_receipt", "state": "pending"},
        {"key": "supplier_schedule_confirmation", "state": "pending"},
        {"key": "internal_production_release", "state": "pending"},
    ]
    pending = [{"key": p["key"], "reason": "Host verification/approval required before order execution."}
               for p in prerequisites if p["state"] == "pending"]
    pending.extend({"key": f["path"], "reason": f["message"], "code": f["code"]} for f in findings)
    for name in ("pi_number", "issue_date"):
        if request.get(name) is None:
            pending.append({"key": name, "reason": "PI header field is unknown."})
    return {"case_id": case_id, "document_kind": "proforma_invoice", "status": "draft",
            "title": "PROFORMA INVOICE — DRAFT / 待确认",
            "content": {"pi_number": request.get("pi_number"), "issue_date": request.get("issue_date"),
                        "commercial_terms": deepcopy(comparison["po"]),
                        "comparison_basis": deepcopy(comparison["basis"])},
            "sample_review": sample, "po_review": comparison,
            "execution_prerequisites": prerequisites, "pending_confirmations": pending,
            "findings": findings, "signed": False, "payment_received": False,
            "production_released": False, "file_generation": "host_tool_required",
            "notice": "Draft only. Does not establish contract signature, payment receipt or production release. Unknowns and conflicts require review."}
