"""Explicit version dependencies and deterministic, resumable draft propagation.

Only registered template mappings are executable. Unknown free-text or file
changes remain visible as review work; they never authorize inferred updates.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json

from .core import create_item, decode, encode, item_view, items, uid
from .models import Item, now
from .domain import calculate_cost, missing_quote_fields, order_diff

RULE_VERSION = "workbench-dependencies-v1"
REFERENCE_FIELDS = {"specVersionId": "spec", "bomVersionId": "bom", "costVersionId": "cost",
                    "quotationVersionId": "quotation", "orderVersionId": "order", "analysisVersionId": "competitor_analysis"}
SPEC_QUOTE_FIELDS = {"product", "quantity", "incoterm", "incotermsVersion", "namedPlace", "paymentTerms"}
PHYSICAL_SPEC_KEYS = ("product", "style", "dimensions", "color", "structure", "laptopSleeve", "straps", "fabric", "lining",
                      "filling", "materialFinish", "zipper", "buckle", "webbing", "logo", "label", "packaging", "cartonQty",
                      "cartonSize", "cartonWeight", "shippingMarks", "tests", "inspection", "sampleRequirement")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str,
                                    separators=(",", ":")).encode()).hexdigest()


def _latest(db, case):
    from .workbench import latest_artifacts
    return latest_artifacts(db, case)


def _write(row, value):
    row.payload = encode(value)


def add_edge(db, case, source, target, *, locators=None, rule="review", provenance="template_mapping"):
    """Register exact immutable endpoints; reject cycles across artifact kinds."""
    for value in (source, target):
        row = db.get(Item, value)
        if not row or row.case_id != case.id or row.kind != "artifact":
            raise ValueError("Dependency endpoint is not a Case artifact version")
    src, dst = db.get(Item, source), db.get(Item, target)
    source_kind, target_kind = decode(src.payload)["kind"], decode(dst.payload)["kind"]
    edges = [item_view(row) for row in items(db, "dependency_edge", case_id=case.id)]
    graph = {}
    for edge in edges:
        graph.setdefault(edge["sourceKind"], set()).add(edge["targetKind"])
    queue, seen = [target_kind], set()
    while queue:
        current = queue.pop()
        if current == source_kind:
            raise ValueError("Dependency cycle")
        if current not in seen:
            seen.add(current)
            queue.extend(graph.get(current, ()))
    payload = {"sourceId": source, "sourceVersion": src.version, "sourceKind": source_kind,
               "targetId": target, "targetVersion": dst.version, "targetKind": target_kind,
               "locators": sorted(locators or ["*"]), "rule": rule, "ruleVersion": RULE_VERSION,
               "provenance": provenance}
    edge_id = "edge_" + digest([case.id, payload])[:28]
    if not db.get(Item, edge_id):
        create_item(db, "dependency_edge", payload, case_id=case.id, parent_id=source, item_id=edge_id)
    return payload


def register_inputs(db, case, artifact):
    """Bindings are explicit references or canonical server template fields."""
    current = _latest(db, case)
    kind, content, target = artifact["kind"], artifact.get("content") or {}, artifact["itemId"]
    for key, source_kind in REFERENCE_FIELDS.items():
        source_id = content.get(key)
        if source_id and source_id != target:
            source_row = db.get(Item, source_id)
            if not source_row or source_row.case_id != case.id or source_row.kind != "artifact":
                row = db.get(Item, target)
                value = decode(row.payload)
                value.setdefault("invalidReferences", []).append({"field": key, "id": source_id})
                _write(row, value)
                continue
            rule = "cost_to_quote" if kind == "quotation" and source_kind == "cost" else "order_compare" if kind == "order" else "review"
            if kind == "cost" and source_kind == "bom" and content.get("bomBindings"):
                rule = "bom_cost"
            visual = ["fields." + key for key in ("product", "style", "dimensions", "color", "structure", "fabric", "lining", "logo", "packaging")]
            locators = visual if source_kind == "spec" and kind in ("concept_image", "design_brief") else None
            if source_kind == "spec" and kind == "sample":
                locators = ["fields." + key for key in PHYSICAL_SPEC_KEYS]
            add_edge(db, case, source_id, target, rule=rule, locators=locators)
    spec = current.get("spec")
    if spec and kind in ("cost", "quotation"):
        fields = spec.get("content", {}).get("fields", {})
        # Quantity feeds server calculation. Matching values are a documented
        # canonical template mapping, never a guessed text association.
        if kind == "cost" and str(fields.get("quantity")) == str(content.get("quantity")):
            add_edge(db, case, spec["itemId"], target, locators=["fields.quantity"], rule="quantity_cost")
            manufacturing = ["fields." + key for key in ("fabric", "lining", "dimensions", "structure", "logo", "packaging", "inspection")]
            if manufacturing:
                add_edge(db, case, spec["itemId"], target, locators=manufacturing, rule="review", provenance="cost_applicability_mapping")
        if kind == "quotation":
            mapped = ["fields." + key for key in SPEC_QUOTE_FIELDS if fields.get(key) is not None
                      and str(fields[key]) == str(content.get(key))]
            if mapped:
                add_edge(db, case, spec["itemId"], target, locators=mapped, rule="spec_to_quote")
    if kind == "cost" and current.get("bom") and not content.get("bomVersionId"):
        add_edge(db, case, current["bom"]["itemId"], target, rule="review", provenance="supplier_cost_scope_review")
    # Existing payment amounts/ratios are human evidence, not an executable
    # formula. Track their order scope without changing receipts or schedules.
    if kind == "payment" and current.get("order") and not content.get("orderVersionId"):
        add_edge(db, case, current["order"]["itemId"], target, rule="review", provenance="payment_scope_review")
    if kind == "order" and current.get("payment"):
        add_edge(db, case, target, current["payment"]["itemId"], rule="review", provenance="payment_scope_review")


def _diff(before, after, path=""):
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(set(before) | set(after)):
            result.extend(_diff(before.get(key), after.get(key), f"{path}.{key}".strip(".")))
        return result
    return [{"field": path, "before": before, "after": after}] if before != after else []


def _matches(edge, changes):
    return "*" in edge["locators"] or any(change["field"] == locator or change["field"].startswith(locator + ".")
        for change in changes for locator in edge["locators"])


def _freshness(db, row_id, status, group_id, reason):
    row = db.get(Item, row_id)
    case_id = row.case_id if row else None
    if row:
        value = decode(row.payload)
        value["freshness"] = {"status": status, "consistencyId": group_id, "reason": reason, "updatedAt": now()}
        _write(row, value)
    for row in items(db, "export", case_id=case_id):
        value = decode(row.payload)
        bound = value.get("artifactVersionId") == row_id
        if not bound and value.get("revision") is not None:
            revisions = [revision for revision in items(db, "revision", case_id=case_id) if revision.version == value["revision"]]
            bound = any(row_id in (decode(revision.payload).get("artifactVersionIds") or {}).values() for revision in revisions)
        if bound and status in ("stale", "superseded", "needs_review"):
            value.update(status="stale", freshness={"status": "stale", "consistencyId": group_id, "reason": reason})
            _write(row, value)


def _status(group):
    statuses = [node["status"] for node in group["nodes"].values()]
    return "failed" if "failed" in statuses else "needs_review" if not group.get("coverageComplete", True) or any(s in ("needs_review", "blocked") for s in statuses) else "synced"


def _export_formats(db, case, artifact_id):
    return sorted({decode(row.payload).get("format") for row in items(db, "export", case_id=case.id)
                   if decode(row.payload).get("artifactVersionId") == artifact_id} - {None})


def artifact_changed(db, case, previous, artifact):
    register_inputs(db, case, artifact)
    if not previous:
        return None
    changes = _diff(previous.get("content") or {}, artifact.get("content") or {})
    if not changes:
        return None
    latest = _latest(db, case)
    edges = [item_view(row) for row in items(db, "dependency_edge", case_id=case.id)]
    current_ids = {value["itemId"] for value in latest.values()}
    queue = [(previous["itemId"], previous["kind"])]
    affected, active_edges = {}, []
    while queue:
        source_id, source_kind = queue.pop(0)
        for edge in edges:
            # A field binding survives intervening versions that did not touch
            # that field (e.g. quantity changes must not detach a logo/image
            # dependency). The persisted edge still cites its exact baseline;
            # this propagation records the replacement version separately.
            if edge["sourceKind"] != source_kind or edge["targetId"] not in current_ids:
                continue
            if source_id == previous["itemId"] and not _matches(edge, changes):
                continue
            active_edges.append({**edge, "changedSourceId": source_id})
            if edge["targetKind"] not in affected:
                affected[edge["targetKind"]] = edge["targetId"]
                queue.append((edge["targetId"], edge["targetKind"]))
    group_id = uid("sync")
    # Source version's old exports are stale even if no downstream mapping exists.
    _freshness(db, previous["itemId"], "superseded", group_id, "Source content changed")
    nodes = {}
    source_formats = _export_formats(db, case, previous["itemId"]) if artifact["kind"] in ("spec", "bom") else []
    if source_formats:
        # The newly saved source content is already authoritative. Refresh its
        # existing business export formats without re-editing the user's
        # separate Office working-copy bytes or creating another source version.
        nodes[artifact["kind"]] = {"kind": artifact["kind"], "baselineId": previous["itemId"],
            "status": "updating", "outputId": artifact["itemId"], "contentValid": True,
            "sourceExport": True, "exports": {fmt: {"status": "pending"} for fmt in source_formats}, "attempts": 0}
    for kind, target_id in affected.items():
        _freshness(db, target_id, "stale", group_id, "Upstream version changed")
        formats = _export_formats(db, case, target_id)
        nodes[kind] = {"kind": kind, "baselineId": target_id, "status": "updating", "outputId": None,
                       "exports": {fmt: {"status": "pending"} for fmt in formats}, "attempts": 0}
    mapped = {locator for edge in active_edges if edge["sourceKind"] == previous["kind"] for locator in edge["locators"]}
    complete = bool(active_edges) and all("*" in mapped or any(change["field"] == loc or change["field"].startswith(loc + ".") for loc in mapped)
                                                for change in changes)
    snapshot = {kind: {"id": value["itemId"], "version": value["version"], "hash": digest(value.get("content"))}
                for kind, value in latest.items()}
    sequence = max((row.version for row in items(db, "propagation", case_id=case.id)), default=0) + 1
    group = {"id": group_id, "sequence": sequence, "caseId": case.id, "sourceId": artifact["itemId"], "previousId": previous["itemId"],
             "baseRevision": case.current_revision, "inputSnapshot": snapshot, "inputSnapshotHash": digest(snapshot),
             "ruleVersion": RULE_VERSION, "changes": changes, "coverageComplete": complete,
             "nodes": nodes, "edges": active_edges, "status": "updating", "createdAt": now()}
    row = create_item(db, "propagation", group, case_id=case.id, item_id=group_id, version=sequence)
    db.flush()
    source_row = db.get(Item, artifact["itemId"])
    source_value = decode(source_row.payload)
    source_value.update(consistencyId=group_id, inputSnapshotHash=group["inputSnapshotHash"])
    _write(source_row, source_value)
    for kind in _ordered(group):
        _execute(db, case, group, kind)
    group["status"] = _status(group)
    if not complete:
        value = decode(db.get(Item, artifact["itemId"]).payload)
        value["impactCoverage"] = {"complete": False, "status": "needs_review", "consistencyId": group_id,
                                   "reason": "Some changed fields have no explicit downstream mapping"}
        _write(db.get(Item, artifact["itemId"]), value)
    group["expectedVersions"] = {kind: value["itemId"] for kind, value in _latest(db, case).items()}
    group["expectedRevision"] = case.current_revision
    group["pendingRevision"] = True
    _write(row, group)
    return group


def _ordered(group):
    pending, result = set(group["nodes"]), []
    while pending:
        ready = sorted(kind for kind in pending if not any(edge["targetKind"] == kind and edge["sourceKind"] in pending for edge in group["edges"]))
        if not ready:
            raise ValueError("Dependency cycle")
        result.extend(ready)
        pending -= set(ready)
    return result


def _rebuild(db, case, group, kind, node):
    from .workbench import append_artifact
    current = _latest(db, case)
    old = item_view(db.get(Item, node["baselineId"]))
    content = deepcopy(old.get("content") or {})
    incoming = [edge for edge in group["edges"] if edge["targetKind"] == kind]
    for edge in incoming:
        parent = group["nodes"].get(edge["sourceKind"])
        if parent and not parent.get("contentValid"):
            raise ReviewRequired("A required upstream branch needs review or failed")
    rules = {edge["rule"] for edge in incoming}
    if "review" in rules:
        raise ReviewRequired("No deterministic rule for this dependency; inspect the affected version")
    if kind == "cost" and rules <= {"quantity_cost", "bom_cost"}:
        raw = Decimal(str(current["spec"]["content"]["fields"]["quantity"])) if "quantity_cost" in rules else Decimal(str(content["quantity"]))
        if raw != raw.to_integral_value():
            raise ReviewRequired("Quantity must be an integer")
        quantity = int(raw)
        offer = db.get(Item, content.get("supplierOfferId")) if content.get("supplierOfferId") else None
        if offer and quantity < int(item_view(offer).get("moq", 1)):
            raise ReviewRequired("New quantity is below the sourced supplier MOQ")
        if "bom_cost" in rules:
            bom = current.get("bom")
            if not bom:
                raise ReviewRequired("Bound BOM is unavailable")
            rows, lines = bom["content"].get("rows") or [], content.get("lines") or []
            bindings = content.get("bomBindings") or []
            if len({binding["lineIndex"] for binding in bindings}) != len(bindings):
                raise ReviewRequired("BOM cost bindings must identify unique cost lines")
            for binding in bindings:
                row_index, line_index = binding["rowIndex"], binding["lineIndex"]
                if not isinstance(row_index, int) or not isinstance(line_index, int) or row_index < 0 or line_index < 0:
                    raise ReviewRequired("Invalid explicit BOM row binding")
                if row_index >= len(rows) or line_index >= len(lines):
                    raise ReviewRequired("Bound BOM row or cost line is unavailable")
                row = rows[row_index]
                if row.get("item") != binding.get("item") or row.get("unit") != binding.get("unit"):
                    raise ReviewRequired("Bound BOM item/unit changed; inspect row mapping")
                if not row.get("sourceId"):
                    raise ReviewRequired("BOM unit price needs an explicit source")
                source = db.get(Item, row["sourceId"])
                if not source or source.case_id != case.id or source.kind not in ("evidence", "supplier_offer"):
                    raise ReviewRequired("BOM price source does not belong to this Case")
                values = [Decimal(str(row.get(key))) for key in ("quantityPerPiece", "unitPriceCny")]
                wastage = Decimal(str(row.get("wastage") or "0"))
                if any(not value.is_finite() or value < 0 for value in [*values, wastage]) or wastage >= 1:
                    raise ReviewRequired("BOM quantities/prices must be nonnegative; loss must be a ratio below one")
                if lines[line_index].get("scope", "per_unit") != "per_unit":
                    raise ReviewRequired("BOM row mappings support per-unit cost only")
                lines[line_index].update(amountCny=str(values[0] * values[1] * (1 + wastage)), sourceId=row["sourceId"])
            content["bomVersionId"] = bom["itemId"]
        content.update(calculate_cost(content.get("lines"), exchange_rate=content.get("exchangeRate"),
                                      margin=content.get("margin"), quantity=quantity))
    elif kind == "quotation" and rules <= {"cost_to_quote", "spec_to_quote"}:
        if "cost_to_quote" in rules:
            cost = current.get("cost")
            if not cost or (cost.get("freshness") or {}).get("status") in ("stale", "needs_review"):
                raise ReviewRequired("Cost is not synchronized")
            for key in ("quantity", "unitPriceUsd", "totalUsd"):
                content[key] = cost["content"].get(key)
            content["costVersionId"] = cost["itemId"]
        for edge in incoming:
            if edge["rule"] == "spec_to_quote":
                for locator in edge["locators"]:
                    key = locator.removeprefix("fields.")
                    content[key] = current["spec"]["content"]["fields"].get(key)
        if missing_quote_fields(content):
            raise ReviewRequired("Quotation still has required missing fields")
    elif kind == "order" and rules == {"order_compare"}:
        quotation, spec = current.get("quotation"), current.get("spec")
        content.update(quotationVersionId=quotation["itemId"] if quotation else None,
                       specVersionId=spec["itemId"] if spec else None,
                       confirmations={"buyer": {"confirmed": False}, "seller": {"confirmed": False}})
        # append_artifact projects the new quote into PI using the same shared
        # server mapping as manual/Agent saves. Customer PO stays immutable.
        content["diff"] = order_diff(content, (quotation or {}).get("content"), (spec or {}).get("content"))
    else:
        raise ReviewRequired("No deterministic regeneration rule is registered")
    artifact = append_artifact(db, case, kind, content, title=old.get("title"), propagate=False)
    row = db.get(Item, artifact["itemId"])
    value = decode(row.payload)
    value.update(consistencyId=group["id"], inputSnapshotHash=group["inputSnapshotHash"], basedOnId=node["baselineId"],
                 requiresReconfirmation=bool([a for a in items(db, "approval", case_id=case.id)
                     if item_view(a).get("targetVersionId") == node["baselineId"]]))
    _write(row, value)
    register_inputs(db, case, artifact)
    return artifact


class ReviewRequired(ValueError):
    pass


def _execute(db, case, group, kind):
    node = group["nodes"][kind]
    node["attempts"] += 1
    try:
        if node.get("outputId"):
            output = db.get(Item, node["outputId"])
        else:
            with db.begin_nested():
                artifact = _rebuild(db, case, group, kind, node)
            node["outputId"] = artifact["itemId"]
            output = db.get(Item, artifact["itemId"])
        node["status"] = "synced"
        node["contentValid"] = True
        node.pop("error", None)
        _freshness(db, output.id, "synced", group["id"], "Validated against controlled input snapshot")
        for fmt, branch in node["exports"].items():
            if branch.get("status") == "ready":
                continue
            try:
                from .exports import export_artifact
                with db.begin_nested():
                    exported = export_artifact(db, case, output, fmt, commit=False)
                branch.update(status="ready", exportId=exported["exportId"])
                branch.pop("error", None)
            except Exception:
                branch.update(status="failed", error="Export failed; retry this branch")
                node["status"] = "exports_failed"
        if node["status"] == "exports_failed":
            node["status"] = "failed"
            node["error"] = "One export format failed; successful outputs are retained"
    except ReviewRequired as exc:
        node.update(status="needs_review", error=str(exc))
        _freshness(db, node["baselineId"], "needs_review", group["id"], str(exc))
    except Exception:
        node.update(status="failed", error="Regeneration failed; retry this node")


def retry_node(db, case, group_id, kind):
    row = db.get(Item, group_id)
    if not row or row.case_id != case.id or row.kind != "propagation":
        raise ValueError("Propagation not found")
    group = item_view(row)
    if kind not in group["nodes"]:
        raise ValueError("Propagation node not found")
    if case.active_run_id:
        raise ValueError("An Agent run is active")
    if decode(case.payload).get("pendingRunId"):
        raise ValueError("An Agent run is waiting for input")
    if group.get("expectedRevision", case.current_revision) != case.current_revision:
        raise ValueError("STALE_INPUT: Case revision has changed")
    expected = group.get("expectedVersions", {})
    current = {key: value["itemId"] for key, value in _latest(db, case).items()}
    if any(current.get(key) != value for key, value in expected.items()):
        raise ValueError("STALE_INPUT: source or artifact version has changed")
    node = group["nodes"][kind]
    if node["status"] == "synced":
        return group
    before_versions = {key: value["itemId"] for key, value in _latest(db, case).items()}
    _execute(db, case, group, kind)
    # A recovered source makes only its blocked descendants eligible. Completed
    # sibling outputs and successful export formats remain untouched.
    eligible = {kind}
    for target in _ordered(group):
        candidate = group["nodes"][target]
        if target == kind or candidate["status"] not in ("needs_review", "blocked"):
            continue
        if any(edge["sourceKind"] in eligible and edge["targetKind"] == target for edge in group["edges"]):
            _execute(db, case, group, target)
            if candidate.get("contentValid"):
                eligible.add(target)
    if before_versions != {key: value["itemId"] for key, value in _latest(db, case).items()}:
        from .workbench import commit_revision
        commit_revision(db, case, "Dependency branch regenerated", node=kind)
    group["expectedVersions"] = {key: value["itemId"] for key, value in _latest(db, case).items()}
    group["expectedRevision"] = case.current_revision
    group["pendingRevision"] = False
    group["status"] = _status(group)
    group["updatedAt"] = now()
    _write(row, group)
    return group


def propagation_view(db, case):
    return {"edges": [item_view(row) for row in items(db, "dependency_edge", case_id=case.id)],
            "runs": [item_view(row) for row in sorted(items(db, "propagation", case_id=case.id), key=lambda row: row.version)], "ruleVersion": RULE_VERSION}


def sample_spec_applicable(db, case, sample, spec):
    """Keep the sample approval on its original version; compare physical scope.

    A new order quantity/payment clause does not assert a new physical sample.
    Unknown-to-known physical changes do require a fresh review.
    """
    if not sample or not spec:
        return False
    source = db.get(Item, sample.get("content", {}).get("specVersionId"))
    if not source or source.case_id != case.id or source.kind != "artifact" or item_view(source).get("kind") != "spec":
        return False
    before = item_view(source).get("content", {}).get("fields") or {}
    after = spec.get("content", {}).get("fields") or {}
    return all(before.get(key) == after.get(key) for key in PHYSICAL_SPEC_KEYS)


def finalize_revision(db, case):
    """Bind a just-created propagation to the host revision that commits it."""
    versions = {key: value["itemId"] for key, value in _latest(db, case).items()}
    for row in items(db, "propagation", case_id=case.id):
        group = decode(row.payload)
        if group.get("pendingRevision") and group.get("expectedVersions") == versions:
            group.update(expectedRevision=case.current_revision, pendingRevision=False)
            _write(row, group)
