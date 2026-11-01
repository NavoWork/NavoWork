"""Persist unfinished information independently of a running Agent task."""
from .core import decode, encode


def warning_node(job):
    payload = decode(job.payload)
    node = payload.get("agentNode") or payload.get("generationTarget")
    return {"customer": "inquiry", "quote": "costing"}.get(node, node) or {
        "qualify_inquiry": "inquiry", "confirm_requirements": "requirements",
        "prepare_quote": "costing", "manage_sample": "sample", "confirm_order": "order",
        "prepare_production": "production",
    }.get(job.kind, "requirements")


def record_missing(case, job, run, questions, *, skipped=False):
    data = decode(case.payload)
    warnings = data.get("nodeWarnings", {})
    node = warning_node(job)
    existing = {item["question"]: item for item in warnings.get(node, [])}
    for question in questions:
        label = str(question.get("question") or "").strip()[:500]
        if label:
            existing[label] = {"question": label, "runId": run.id, "skipped": skipped}
    warnings[node] = list(existing.values())
    data["nodeWarnings"] = warnings
    case.payload = encode(data)
    if skipped:
        value = decode(run.payload)
        value["skippedQuestions"] = list(dict.fromkeys([
            *value.get("skippedQuestions", []), *[q["question"] for q in questions if q.get("question")],
        ]))
        run.payload = encode(value)


def clear_checked_warnings(case, job, run):
    # Skipping never resolves a gap. A later successful check of the node may do so.
    if decode(run.payload).get("skippedQuestions"):
        return
    data = decode(case.payload)
    warnings = data.get("nodeWarnings", {})
    warnings.pop(warning_node(job), None)
    data["nodeWarnings"] = warnings
    case.payload = encode(data)


def record_spec_gaps(db, case, job, run):
    """A completed draft can still lack required fields even without request_info."""
    from .domain import SPEC_FIELDS, missing_spec_fields
    from .workbench import latest_artifact
    spec = latest_artifact(db, case, "spec")
    if not spec:
        return
    fields = spec.get("content", {}).get("fields", {})
    missing = set(missing_spec_fields(fields))
    data = decode(case.payload)
    warnings = data.get("nodeWarnings", {})
    # Validation warnings are recalculated; unanswered Agent questions stay intact.
    current = [w for w in warnings.get("requirements", []) if w.get("source") != "validation"]
    existing = {w["question"] for w in current}
    for field in SPEC_FIELDS:
        question = f"请补充{field['label']}。"
        if field["key"] in missing and question not in existing:
            current.append({"question": question, "runId": run.id, "skipped": False,
                            "source": "validation", "field": field["key"]})
    if current:
        warnings["requirements"] = current
    else:
        warnings.pop("requirements", None)
    data["nodeWarnings"] = warnings
    case.payload = encode(data)
