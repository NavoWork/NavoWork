"""Read-only source projections. No later core15 evidence enters early tests."""

from email import policy
from email.parser import BytesParser
from pathlib import Path
import unittest

from order_skills.domain import compare_po, prepare_pi, review_sample
from support import CASE, evidence, field, order, sample

ROOT = Path(__file__).resolve().parents[3]
EARLY = ROOT / "test" / "inputs" / CASE
LATE = ROOT / "test" / "core15"


def body(path):
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    return message.get_body(preferencelist=("plain",)).get_content().strip()


class RepositorySourceTests(unittest.TestCase):
    def test_early_conditional_customer_reply(self):
        request = sample("conditional")
        quote = body(EARLY / "customer-conditional-confirmation.eml")
        request["response"]["evidence"] = evidence(quote, "early-conditional", locator="email:body")
        request["response"]["conditions"] = ["Widen logo to 60 mm", "Review physical color-box sample"]
        request["feedback"] = [{"field": "logo.width_mm", "observation": "Customer requests 60 mm",
                                "requested_change": "Propose 60 mm; obtain new specification and sample review",
                                "evidence": request["response"]["evidence"]}]
        result = review_sample(request)
        self.assertFalse(result["sample_approval_supported"])
        self.assertEqual(result["response_kind"], "conditional")
        self.assertEqual(len(result["modifications"]), 1)

    def test_early_commercial_acceptance_is_not_sample_approval(self):
        request = sample()
        quote = body(EARLY / "customer-unconditional-confirmation.eml")
        request["response"]["evidence"] = evidence(quote, "early-commercial", locator="email:body")
        request["response"]["scope"] = "commercial"
        result = review_sample(request)
        self.assertFalse(result["sample_approval_supported"])
        self.assertEqual(result["response_kind"], "partial")

    def test_early_pi_keeps_physical_sample_pending(self):
        request = order()
        request["baseline"]["version_id"] = "quote-v2-candidate"
        request["baseline"]["status"] = "draft"
        del request["baseline"]["customer_acceptance"]
        result = prepare_pi(request)
        self.assertEqual(result["status"], "draft")
        self.assertFalse(result["po_review"]["basis"]["customer_acceptance_supported"])
        self.assertEqual(result["execution_prerequisites"][0]["state"], "pending")

    def test_late_core15_sample_only_approves_its_sample_scope(self):
        request = order()
        request["sample"] = sample()
        quote = body(LATE / "evidence" / "closeout-customer-sample-approval-s03.eml")
        self.assertIn("sample S03", quote)
        self.assertIn("TechPack V3", quote)
        request["sample"]["response"]["evidence"] = evidence(quote, "core15-E04", locator="email:body")
        result = prepare_pi(request)
        self.assertTrue(result["sample_review"]["sample_approval_supported"])
        self.assertEqual(result["execution_prerequisites"][0]["state"], "evidence_supported")
        self.assertFalse(result["payment_received"])
        self.assertFalse(result["signed"])
        self.assertFalse(result["production_released"])

    def test_real_po_pdf_port_conflict_is_located(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("Optional repository-PDF replay needs pypdf; domain suite needs stdlib only")
        quote = PdfReader(EARLY / "po-conflict.pdf").pages[0].extract_text()
        self.assertIn("FOB Shanghai, Incoterms 2020", quote)
        request = order()
        # Explicit manually reviewed projection, not a claim of model extraction.
        port = field("Shanghai", "Trade term", "test/inputs/BAG-2026-DE-001/po-conflict.pdf")
        port["raw"] = "FOB Shanghai, Incoterms 2020"
        port["evidence"]["quote"] = port["raw"]
        request["po"]["named_place"] = port
        result = compare_po(request)
        difference = next(d for d in result["differences"] if d["path"] == "po.named_place")
        self.assertIn(difference["po"]["evidence"]["quote"], quote)
        self.assertEqual(difference["po"]["evidence"]["locator"], "page:1;field:Trade term")


if __name__ == "__main__":
    unittest.main()
