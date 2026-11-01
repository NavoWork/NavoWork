"""Exercise ONLY committed agent-kit objects, without touching another checkout."""
from __future__ import annotations

import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

from .inspection import digest, text_content
from .runner import implementation_manifest, write_json
from .suite import CASE, REPO, money


def check_committed_protocol(revision: str, output: Path) -> dict:
    output = output.resolve()
    if not output.is_relative_to(REPO / "evaluation/runs"):
        raise ValueError("committed snapshots must stay in ignored evaluation/runs/")
    output.mkdir(parents=True, exist_ok=False)
    commit = subprocess.run(["git", "rev-parse", "--verify", revision + "^{commit}"], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout.strip()
    prefix = "agent-kit/src/"
    paths = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit, prefix], cwd=REPO,
                           capture_output=True, text=True, check=True).stdout.splitlines()
    if not paths:
        raise ValueError("revision contains no committed agent-kit package")
    snapshot = output / "committed-snapshot"
    inventory = {}
    for relative in paths:
        if not relative.startswith(prefix) or ".." in Path(relative).parts:
            raise ValueError("unexpected committed path")
        data = subprocess.run(["git", "show", commit + ":" + relative], cwd=REPO, capture_output=True, check=True).stdout
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        inventory[relative] = digest(data)
    existing = {name: module for name, module in sys.modules.items() if name == "navowork_agent" or name.startswith("navowork_agent.")}
    for name in existing:
        del sys.modules[name]
    sys.path.insert(0, str(snapshot / prefix))
    checks = []

    def check(name, function):
        try:
            details = function()
            checks.append({"name": name, "status": "passed", "evidence": details})
        except Exception as exc:
            checks.append({"name": name, "status": "failed", "error": type(exc).__name__ + ": " + str(exc)[:800]})

    def must(condition, message):
        if not condition:
            raise AssertionError(message)

    try:
        contracts = importlib.import_module("navowork_agent.contracts")
        ports = importlib.import_module("navowork_agent.ports")
        LocalAdapter = importlib.import_module("navowork_agent.adapters.local").LocalAdapter
        ToolService = importlib.import_module("navowork_agent.tools.service").ToolService
        pricing_types = importlib.import_module("navowork_agent.tools.pricing")
        from pydantic import ValidationError
        context = contracts.ExecutionContext(case_id=CASE, job_id="eval-compat-job", run_id="eval-compat-run")
        adapter = LocalAdapter(output / "host", context)
        adapter.update_user_facts({"fx": "7.20", "margin": "0.20"}, supersede=False)
        service = ToolService(adapter)
        inputs = REPO / "test/inputs" / CASE
        inquiry = adapter.import_source(inputs / "inquiry.eml")
        supplier = adapter.import_source(inputs / "factory-A-quote.xlsx")
        pdf = adapter.import_source(inputs / "factory-B-quote.pdf")

        def invoke(name, arguments=None, key=None, selected_service=None):
            arguments = arguments or {}
            return (selected_service or service).call(contracts.ToolCall(tool_call_id="eval-call", name=name,
                arguments=arguments, idempotency_key=key or contracts.digest([name, arguments])))

        def cite(ref, **locator):
            section = next(s for s in adapter.read_document(ref.file_id)["sections"]
                           if all(s["locator"].get(k) == v for k, v in locator.items()))
            return contracts.Citation(file_id=ref.file_id, sha256=ref.sha256, locator=section["locator"], excerpt=section["text"][:3000])

        def strict_dtos():
            rejected = []
            for cls, valid, extra in (
                (contracts.ExecutionContext, context.model_dump(), {"actor_id": "manager"}),
                (contracts.FileRef, supplier.model_dump(), {"path": "C:/private"}),
                (contracts.Citation, cite(supplier, cell="B10").model_dump(), {"case_id": CASE}),
                (contracts.ToolResult, {"status": "success"}, {"quote": {}})):
                try:
                    cls.model_validate({**valid, **extra})
                except ValidationError:
                    rejected.append(cls.__name__)
            must(len(rejected) == 4, "extra fields unexpectedly accepted")
            statuses = ["success", "needs_info", "needs_review", "blocked", "conflict", "error"]
            must(all(contracts.ToolResult(status=s, data={"evaluation": True}).status == s for s in statuses), "status roundtrip lost")
            return {"extra_field_rejection": rejected, "native_statuses_preserved": statuses,
                    "mapping": "Evaluation step status is contextual; never collapse needs_review or partial failures into approved/sent."}

        check("strict_dtos_and_status_roundtrip", strict_dtos)

        def port_and_reads():
            must(all(isinstance(adapter, cls) for cls in (ports.CaseContextPort, ports.FileStorePort, ports.ArtifactPort, ports.EventSink)), "port mismatch")
            actual = invoke("read_document", {"file_id": supplier.file_id})
            must(actual.status == "success", "actual reader failed")
            sections = actual.data["sections"]
            values = {s["locator"].get("cell"): s.get("value") for s in sections}
            must([str(values[c]) for c in ("B10", "B11", "B12")] == ["44", "2", "4"], "actual XLSX values differ")
            page = cite(pdf, page=1)
            must("52.00" in page.excerpt and page.sha256 == digest(adapter.read_bytes(pdf.file_id)), "PDF source mismatch")
            return {"xlsx_sha256": supplier.sha256, "pdf_sha256": pdf.sha256, "pdf_locator": page.locator}

        check("actual_ports_xlsx_pdf_and_citations", port_and_reads)
        sections = adapter.read_document(supplier.file_id)["sections"]
        costs = []
        for category, cell in (("base", "B10"), ("packaging", "B11"), ("local", "B12")):
            value = next(s["value"] for s in sections if s["locator"].get("cell") == cell)
            costs.append(pricing_types.CostLine(category=category, amount=contracts.Fact(value=str(value), sources=[cite(supplier, cell=cell)]), scope="per_unit"))
        pricing = pricing_types.PricingInput(quantity=3000, costs=costs,
            fx_cny_per_usd=contracts.Fact(value="7.20", user_fact="fx"), target_gross_margin=contracts.Fact(value="0.20", user_fact="margin"))
        inquiry_cite = cite(inquiry, part="body")
        snapshot_data = pricing_types.ContentSnapshot(fields={
            "product": contracts.Fact(value="custom backpacks", sources=[inquiry_cite]),
            "quantity": contracts.Fact(value=3000, sources=[inquiry_cite]),
            "packaging": contracts.Fact(value="ordinary paper box", sources=[cite(supplier, cell="C11")]),
            "dimensions": contracts.Fact(value=None), "material": contracts.Fact(value=None)}, pricing=pricing,
            internal_notes={"private": "INTERNAL-COMPAT-COST-DO-NOT-EXPORT"}, supplier="Factory A")

        def numeric_missing():
            result = invoke("calculate_quote", {"pricing": pricing.model_dump(mode="json")})
            expected = money("50", "7.20", "0.20", 3000)
            must(result.status == "success" and all(result.data["quote"][k] == v for k, v in expected.items()), "independent oracle mismatch")
            unknown = pricing.model_copy(update={"costs": [c.model_copy(update={"amount": contracts.Fact(value=None)}) if c.category == "packaging" else c for c in costs]})
            missing = invoke("calculate_quote", {"pricing": unknown.model_dump(mode="json")})
            must(missing.status == "needs_info" and missing.data["quote"] is None and bool(missing.questions), "missing cost not blocked")
            return {"actual_quote": result.data["quote"], "missing_status": missing.status}

        check("sourced_numeric_oracle_and_missing_cost", numeric_missing)
        args = {"snapshot": snapshot_data.model_dump(mode="json"), "baselines": {"spec": 0, "cost": 0, "quotation": 0}, "intent": "initial"}
        published = invoke("publish_documents", args, "publish-once")

        def publish_files():
            must(published.status == "needs_review" and len(published.outputs) == 4, "publish incomplete: " + str(published))
            verified = []
            for ref in published.outputs:
                data = adapter.read_bytes(ref.file_id)
                must(digest(data) == ref.sha256 and len(data) == ref.byte_size, "physical output digest/size mismatch")
                if ref.name.startswith("quotation-"):
                    text = text_content(data, Path(ref.name).suffix)
                    must("8.69" in text and "26070" in text.replace(",", ""), "quotation file amounts differ")
                verified.append({"name": ref.name, "sha256": ref.sha256, "bytes": ref.byte_size})
            return {"outputs": verified, "status": published.status, "visual_review": "not_performed"}

        check("actual_publish_files_and_amounts", publish_files)

        def idempotency():
            before = len(adapter._load()["events"])
            must(invoke("publish_documents", args, "publish-once") == published, "retry changed result")
            must(invoke("publish_documents", args, "publish-once") == published, "third execution changed result")
            must(len(adapter._load()["events"]) == before and all(a["ref"]["version"] == 1 for a in adapter.list_artifacts()), "retry duplicated business writes")
            conflict = invoke("publish_documents", {**args, "intent": "confirmed_change"}, "publish-once")
            must(conflict.status == "conflict" and conflict.code == "IDEMPOTENCY_CONFLICT", "changed body reused key")
            return {"retries": 3, "artifact_versions": [a["ref"]["version"] for a in adapter.list_artifacts()], "conflict_code": conflict.code}

        check("idempotency_and_conflicting_key", idempotency)
        quotation = next(a for a in published.artifacts if a.kind == "quotation")

        def customer_package():
            result = invoke("package_customer_files", {"artifact_id": quotation.artifact_id, "version": 1})
            must(result.status == "needs_review" and len(result.outputs) == 1, "package not generated")
            data = adapter.read_bytes(result.outputs[0].file_id)
            text = text_content(data, ".zip")
            must("INTERNAL-COMPAT-COST-DO-NOT-EXPORT" not in text and "cost-v1" not in text and "gross_margin" not in text, "customer package contains internal costing")
            return {"zip_sha256": digest(data), "bytes": len(data), "audience": "customer", "status": result.status}

        check("actual_customer_zip_cost_exclusion", customer_package)

        def partial_exports():
            partial_adapter = LocalAdapter(output / "partial-host", context.model_copy(update={"job_id": "partial-job"}))
            # Host-only seed: import the same authorized sources and host facts, never elevate through tool arguments.
            partial_adapter.update_user_facts({"fx": "7.20", "margin": "0.20"}, supersede=False)
            for path in (inputs / "inquiry.eml", inputs / "factory-A-quote.xlsx"):
                partial_adapter.import_source(path)
            partial_service = ToolService(partial_adapter, fail_formats=("pdf",))
            result = invoke("publish_documents", args, "partial-publish", partial_service)
            must(result.status == "error" and "quotation.pdf" in result.retryable and len(result.outputs) == 3, "partial failure falsified/lost outputs")
            quote_ref = next(a for a in result.artifacts if a.kind == "quotation")
            package = invoke("package_customer_files", {"artifact_id": quote_ref.artifact_id, "version": 1}, "partial-package", partial_service)
            must(package.code == "EXPORT_INCOMPLETE" and not package.outputs, "incomplete customer package released")
            retry = invoke("export_artifact", {"artifact_id": quote_ref.artifact_id, "version": 1, "format": "pdf"}, "retry-pdf", ToolService(partial_adapter))
            must(retry.status == "needs_review" and len(retry.outputs) == 1, "single branch retry failed")
            return {"native_status": result.status, "completed_files": len(result.outputs), "retryable": result.retryable,
                    "incomplete_package_code": package.code, "recovered_pdf_sha256": retry.outputs[0].sha256,
                    "mapping": "Preserve native error plus completed outputs and retryable branches; evaluation UI may describe partial completion."}

        check("actual_partial_export_and_branch_retry", partial_exports)

        def opaque_versions():
            one, two = output / "v1/same.eml", output / "v2/same.eml"
            one.parent.mkdir(); two.parent.mkdir()
            one.write_text("SIMULATED first content", encoding="utf-8")
            two.write_text("SIMULATED different content", encoding="utf-8")
            first, second = adapter.import_source(one), adapter.import_source(two)
            one.write_text("changed outside managed store", encoding="utf-8")
            must(first.name == second.name and first.file_id != second.file_id and first.sha256 != second.sha256, "same-name identity collapsed")
            must(adapter.read_bytes(first.file_id) == b"SIMULATED first content", "imported old bytes changed")
            return {"version_1_id": first.file_id, "version_2_id": second.file_id, "version_field_policy": "FileRef has no version; host retains source-version-to-opaque-ID registry."}

        check("same_name_opaque_identity_and_old_bytes", opaque_versions)

        def scope_and_generation():
            foreign_adapter = LocalAdapter(output / "foreign-host", context.model_copy(update={"case_id": "BAG-2026-DE-003"}))
            foreign_path = output / "foreign-secret.txt"
            foreign_path.write_text("FOREIGN-COMPAT-SECRET", encoding="utf-8")
            foreign = foreign_adapter.import_source(foreign_path)
            denied = invoke("read_document", {"file_id": foreign.file_id})
            must(denied.status == "blocked" and denied.code == "FILE_UNAVAILABLE" and "FOREIGN-COMPAT-SECRET" not in denied.model_dump_json(), "real existing foreign ID disclosed")
            read_only = LocalAdapter(adapter.root, context.model_copy(update={"can_write": False}))
            refusal = invoke("request_info", {"fields": ["x"]}, "no-write", ToolService(read_only))
            must(refusal.code == "WRITE_DENIED", "read-only context wrote state")
            old_context = LocalAdapter(adapter.root, context)
            adapter.update_user_facts({"new_host_input": "confirmed"})
            stale = invoke("request_info", {"fields": ["x"]}, "stale-generation", ToolService(old_context))
            must(stale.status == "conflict" and stale.code == "STALE_CONTEXT", "stale generation wrote state")
            return {"foreign_code": denied.code, "read_only_code": refusal.code, "stale_code": stale.code}

        # Keep generation fencing last, after write-dependent checks.
        def version_history():
            changed = snapshot_data.model_copy(update={"internal_notes": {"private": "INTERNAL-COMPAT-COST-DO-NOT-EXPORT", "revision": "new draft"}})
            updated = invoke("publish_documents", {"snapshot": changed.model_dump(mode="json"), "baselines": {"spec": 1, "cost": 1, "quotation": 1}, "intent": "confirmed_change"})
            must(updated.status == "needs_review" and all(a.version == 2 and a.baseline == 1 for a in updated.artifacts), "new version relationship failed")
            old = adapter.get_artifact(quotation.artifact_id, 1)
            must(old["ref"] == quotation.model_dump(mode="json"), "old artifact metadata changed")
            must(all(digest(adapter.read_bytes(f.file_id)) == f.sha256 for f in quotation.files), "old physical outputs overwritten")
            stale = invoke("publish_documents", args, "stale-baseline")
            must(stale.status == "conflict" and stale.code == "BASELINE_CONFLICT", "stale baseline wrote artifact")
            return {"old_version": 1, "new_version": 2, "old_snapshot_hash": quotation.snapshot_hash, "stale_code": stale.code}

        check("actual_immutable_history_and_baseline_CAS", version_history)

        def no_authority_tools():
            names = {s["function"]["name"] for s in service.schemas()}
            forbidden = {"shell", "send_email", "approve", "release_production", "import_source"}
            must(not names & forbidden, "authority tool unexpectedly exposed")
            result = invoke("send_email", {"to": "attacker@evaluation.invalid"})
            must(result.status == "blocked" and result.code == "UNKNOWN_TOOL" and not result.outputs, "unregistered send forged success")
            return {"registered_tools": sorted(names), "send_rejection": result.code}

        check("no_shell_external_send_or_approval_tools", no_authority_tools)
        check("actual_foreign_case_readonly_and_generation_fence", scope_and_generation)
    except Exception as exc:
        checks.append({"name": "package_setup_or_dependency", "status": "blocked" if isinstance(exc, ImportError) else "failed", "error": type(exc).__name__ + ": " + str(exc)[:800]})
    finally:
        sys.path.pop(0)
        for name in list(sys.modules):
            if name == "navowork_agent" or name.startswith("navowork_agent."):
                del sys.modules[name]
        sys.modules.update(existing)
    counts = {s: sum(c["status"] == s for c in checks) for s in ("passed", "failed", "blocked")}
    report = {"schema": "navowork-committed-protocol-compatibility/1", "revision": commit,
              "status": "failed" if counts["failed"] else "blocked" if counts["blocked"] else "passed",
              "summary": {"checks": len(checks), **counts}, "implementation_files": implementation_manifest(),
              "committed_source_sha256": inventory, "checks": checks,
              "execution_layer": "offline_actual_committed_agentkit_tools", "backend_worker_integration": "blocked",
              "real_model_executed": False, "file_visual_review": "not_performed", "product_acceptance": "not_accepted",
              "evidence_directory": output.relative_to(REPO).as_posix()}
    write_json(output / "report.json", report)
    (output / "failures.txt").write_text("\n".join(c["name"] + ": " + c.get("error", "") for c in checks if c["status"] != "passed")
        + "\nWorker/backend integration, real model and visual review remain unaccepted.\n", encoding="utf-8")
    return report
