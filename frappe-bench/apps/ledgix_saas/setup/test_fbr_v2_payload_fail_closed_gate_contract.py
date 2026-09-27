from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]
GATE = APP / "migration" / "fbr_v2_payload_fail_closed_gate.py"


class TestFBRV2PayloadFailClosedGateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = GATE.read_text(encoding="utf-8")

    def test_gate_is_local_site_restricted(self):
        self.assertIn("INTEGRATION_SITE", self.gate)
        self.assertIn("Refusing FBR V2 payload fail-closed gate", self.gate)

    def test_gate_uses_real_v2_builder_and_persisted_snapshot(self):
        self.assertIn("fbr_v2_payload_builder.build_payload_candidate(", self.gate)
        self.assertIn("read_persisted_v2_snapshot(", self.gate)
        self.assertIn("evaluate_invoice_readiness(", self.gate)

    def test_gate_creates_real_native_erpnext_invoice(self):
        self.assertIn("erpnext_selling.build_sales_invoice(", self.gate)
        self.assertIn('items=[{"item": core.ITEMS["ordinary"], "qty": 1}]', self.gate)
        self.assertIn("invoice.submit()", self.gate)

    def test_gate_does_not_fabricate_fbr_readiness_evidence(self):
        forbidden = (
            "Ledgix FBR Reference Data",
            "needs_review = 0",
            '"needs_review", 0',
            "sandbox_token",
            "production_token",
            "production_post_armed = 1",
        )
        for token in forbidden:
            self.assertNotIn(token, self.gate)

    def test_gate_requires_real_identity_mapping_and_reference_blockers(self):
        self.assertIn("seller_tax_id_blocker_present", self.gate)
        self.assertIn("seller_address_blocker_present", self.gate)
        self.assertIn("buyer_address_blocker_present", self.gate)
        self.assertIn("mapping_review_blocker_present", self.gate)
        self.assertIn("official_reference_blocker_present", self.gate)

    def test_gate_intercepts_fbr_submit_hook_and_commit(self):
        self.assertIn("fbr_native.queue_native_for_fbr = _no_network_queue", self.gate)
        self.assertIn("frappe.db.commit = _no_commit", self.gate)
        self.assertIn('"fbr_network_calls": 0', self.gate)

    def test_gate_rolls_everything_back(self):
        self.assertIn("frappe.db.rollback()", self.gate)
        self.assertIn('"ROLLBACK_CONFIRMED"', self.gate)
        self.assertIn('"persisted_gate_invoices"', self.gate)


if __name__ == "__main__":
    unittest.main()
