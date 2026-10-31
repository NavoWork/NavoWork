from __future__ import annotations

import base64
import copy
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from evaluation.adapters import invoke
from evaluation.backend_probe import probe_backend
from evaluation.checker import evaluate
from evaluation.fixture_audit import audit_fixtures
from evaluation.inspection import canonical, confined, digest, text_content
from evaluation.mutants import MUTATIONS, run as mutant_run
from evaluation.reference_adapter import run
from evaluation.runner import run_suite
from evaluation.suite import REPO, build_suite, money, stage


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        (REPO / "evaluation/runs").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=REPO / "evaluation/runs")
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def staged(self, sid="E03", seed=7319):
        scenario = next(s for s in build_suite(seed) if s.id == sid)
        root = self.root / (sid + "-" + str(seed))
        request, _ = stage(scenario, root, "test-" + sid)
        return scenario, request, root

    def codes(self, result):
        return {f["code"] for f in result["findings"]}

    def test_independent_money_oracle(self):
        self.assertEqual(money("50", "7.20", "0.20", 3000), {"unit_usd": "8.69", "total_usd": "26070.00", "quantity": 3000})
        self.assertEqual(money("53", "7.20", "0.20", 3000)["total_usd"], "27630.00")
        self.assertEqual(money("0.01", "7.31", "0.29", 2103)["unit_usd"], "0.01")

    def test_all_scenarios_positive_and_generated_variants(self):
        for seed in (7319, 91999):
            for scenario in build_suite(seed):
                with self.subTest(seed=seed, scenario=scenario.id):
                    root = self.root / f"{seed}-{scenario.id}"
                    request, _ = stage(scenario, root, "control-" + scenario.id)
                    result = evaluate(scenario, request, run(request), root)
                    self.assertEqual(result["status"], "passed", result["findings"])

    def test_each_mutant_hits_designated_invariant(self):
        for name, target in MUTATIONS.items():
            hits = []
            for scenario in build_suite():
                root = self.root / name / scenario.id
                request, _ = stage(scenario, root, "mutant-" + scenario.id)
                result = evaluate(scenario, request, mutant_run(request, name), root)
                hits.extend(f for f in result["findings"] if f["code"] == target)
            self.assertTrue(hits, f"mutant {name} did not hit {target}")

    def test_no_oracle_or_future_evidence_in_request(self):
        scenario, request, root = self.staged("E02a")
        payload = canonical(request).decode()
        for forbidden in ("expected", "quote-golden", "core15", "factory-A-color-box-update", "53.00", "9.21", "27630"):
            self.assertNotIn(forbidden, payload)
        self.assertEqual(len(request["inputs"]), 2)
        self.assertEqual({p.suffix for p in (root / "inputs").rglob("*") if p.is_file()}, {".eml", ".xlsx"})
        self.assertFalse((root / "expected").exists())

    def test_foreign_source_bytes_never_staged(self):
        scenario, request, root = self.staged("E05")
        self.assertFalse(request["inputs"])
        self.assertNotIn("INTERNAL-CROSS-CASE-SECRET", canonical(request).decode())
        self.assertEqual(list(root.rglob("*.eml")), [])

    def test_content_tampering_even_with_recomputed_hash(self):
        scenario, request, root = self.staged()
        response = run(request)
        artifact = response["steps"][0]["artifact"]
        path = root / artifact["path"]
        content = json.loads(path.read_bytes())
        content["quote"]["total_usd"] = "1.00"
        data = canonical(content)
        path.write_bytes(data)
        artifact.update(sha256=digest(data), bytes=len(data))
        codes = self.codes(evaluate(scenario, request, response, root))
        self.assertIn("FILE_CONTENT_MISMATCH", codes)

    def test_input_tampering_is_detected(self):
        scenario, request, root = self.staged()
        response = run(request)
        (root / request["inputs"][0]["path"]).write_bytes(b"replaced input")
        self.assertIn("INPUT_MUTATED", self.codes(evaluate(scenario, request, response, root)))

    def test_output_path_escape_and_missing_file(self):
        for path in ("../outside.json", "outputs/../../outside.json", "C:/outside.json", "outputs/missing.json"):
            scenario, request, root = self.staged(seed=hash(path))
            response = run(request)
            response["steps"][0]["artifact"]["path"] = path
            self.assertIn("MISSING_OUTPUT_FILE", self.codes(evaluate(scenario, request, response, root)))

    def test_bad_citation_excerpt(self):
        scenario, request, root = self.staged()
        response = run(request)
        response["steps"][0]["citations"][0]["excerpt"] = "made up source text"
        self.assertIn("CITATION_EXCERPT_MISMATCH", self.codes(evaluate(scenario, request, response, root)))

    def test_real_model_request_does_not_promote_offline_results(self):
        scenario, request, root = self.staged()
        result = evaluate(scenario, request, run(request), root, require_model=True)
        self.assertIn("MODEL_EVIDENCE_MISSING", self.codes(result))

    def test_missing_execution_classification_fails_protocol(self):
        scenario, request, root = self.staged()
        response = run(request)
        del response["execution"]
        self.assertIn("INVALID_PROTOCOL", self.codes(evaluate(scenario, request, response, root)))

    def test_declared_fixture_hashes_audited_without_normalizing(self):
        result = audit_fixtures()
        self.assertEqual(result["files_checked"], 43)
        self.assertFalse(result["core15_evidence_used_as_agent_input"])
        for mismatch in result["mismatches"]:
            self.assertNotEqual(mismatch["actual_sha256"], mismatch["declared_sha256"])

    def test_artifact_cost_and_version_are_checked(self):
        scenario, request, root = self.staged()
        response = run(request)
        artifact = response["steps"][0]["artifact"]
        path = root / artifact["path"]
        content = json.loads(path.read_bytes())
        content.update(cost_cny="4", version=900)
        data = canonical(content)
        path.write_bytes(data)
        artifact.update(sha256=digest(data), bytes=len(data))
        codes = self.codes(evaluate(scenario, request, response, root))
        self.assertIn("CITATION_FIELD_MISMATCH", codes)
        self.assertIn("FILE_PROVENANCE_MISMATCH", codes)

    def test_event_reordering_and_request_binding(self):
        scenario, request, root = self.staged()
        response = run(request)
        response["events"][0]["request_sha256"] = "0" * 64
        response["events"][2], response["events"][3] = response["events"][3], response["events"][2]
        codes = self.codes(evaluate(scenario, request, response, root))
        self.assertIn("EVENT_SEQUENCE", codes)
        self.assertIn("EVENT_COVERAGE", codes)

    def test_zip_scanner_reads_nested_members(self):
        inner = io.BytesIO()
        with zipfile.ZipFile(inner, "w") as archive:
            archive.writestr("cost.txt", "INTERNAL-COST-NESTED")
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as archive:
            archive.writestr("attachments/nested.zip", inner.getvalue())
        self.assertIn("INTERNAL-COST-NESTED", text_content(outer.getvalue(), ".zip"))

    def test_unavailable_runtime_reports_blocked_and_not_accepted(self):
        report = run_suite(self.root / "unavailable", selected=["E03"])
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["summary"], {"scenarios": 1, "passed": 0, "failed": 0, "blocked": 1})
        self.assertEqual(report["product_acceptance"]["status"], "not_accepted")
        self.assertEqual(report["layers"]["file_visual"]["status"], "not_performed")

    def test_module_adapter_compatibility(self):
        report = run_suite(self.root / "module", adapter="module", module="evaluation.reference_adapter:run", selected=["E03", "E09"])
        self.assertEqual(report["status"], "passed")

    def test_stdio_cli_compatibility(self):
        report = run_suite(self.root / "command", adapter="command", command=[sys.executable, str(REPO / "evaluation/stdio_adapter.py")], selected=["E03", "E09"])
        self.assertEqual(report["status"], "passed")

    def test_timeout_and_malformed_protocol_fail_closed(self):
        for name, command in (("timeout", [sys.executable, "-c", "import time; time.sleep(3)"]),
                              ("invalid", [sys.executable, "-c", "print('{}')"]),
                              ("nonzero", [sys.executable, "-c", "raise SystemExit(4)"])):
            report = run_suite(self.root / name, adapter="command", command=command, timeout=0.1 if name == "timeout" else 3, selected=["E03"])
            self.assertEqual(report["status"], "failed")

    def test_http_transport_materializes_bytes_and_binds_wire_hash(self):
        server_root = self.root / "server"
        server_root.mkdir()
        captured = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                wire = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                captured.append(wire)
                local = copy.deepcopy(wire)
                local["workspace"] = str(server_root)
                for item in local["inputs"]:
                    path = confined(server_root, item["path"])
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(base64.b64decode(item.pop("data_base64")))
                result = run(local)
                result["events"][0]["request_sha256"] = digest(canonical(wire))
                result["output_files"] = [{"path": p.relative_to(server_root).as_posix(), "data_base64": base64.b64encode(p.read_bytes()).decode()}
                                          for p in (server_root / "outputs").rglob("*") if p.is_file()]
                data = canonical(result)
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            report = run_suite(self.root / "http", adapter="http", endpoint=f"http://127.0.0.1:{server.server_port}/evaluate", selected=["E03"])
            self.assertEqual(report["status"], "passed", report["scenarios"])
            self.assertEqual(captured[0]["workspace"], ".")
            self.assertNotIn("expected", canonical(captured[0]).decode())
            self.assertTrue(captured[0]["inputs"][0]["data_base64"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_read_only_backend_function_observations(self):
        report = probe_backend()
        self.assertEqual(report["status"], "completed")
        self.assertFalse(report["backend_service_executed"])
        self.assertFalse(report["model_executed"])
        observations = {o["id"]: o for o in report["observations"]}
        self.assertEqual(observations["BACKEND-CUSTOMER-PACKAGE"]["status"], "not_tested")


if __name__ == "__main__":
    unittest.main()
