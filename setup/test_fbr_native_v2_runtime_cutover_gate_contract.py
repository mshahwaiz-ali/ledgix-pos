from pathlib import Path
import unittest


APP = Path(__file__).resolve().parents[1]
GATE = APP / "migration" / "fbr_native_v2_runtime_cutover_gate.py"


class TestFBRNativeV2RuntimeCutoverGateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = GATE.read_text(encoding="utf-8")

    def test_gate_is_local_site_restricted(self):
        self.assertIn("INTEGRATION_SITE", self.gate)
        self.assertIn("Refusing FBR native V2 runtime cutover gate", self.gate)

    def test_gate_covers_sales_and_pos_invoices(self):
        self.assertIn("erpnext_selling.build_sales_invoice(", self.gate)
        self.assertIn("erpnext_pos.build_pos_invoice(", self.gate)
        self.assertIn("sale.submit()", self.gate)
        self.assertIn("pos.submit()", self.gate)

    def test_gate_uses_real_native_submit_hook(self):
        self.assertNotIn(
            "fbr_native.queue_native_for_fbr =",
            self.gate,
        )
        self.assertIn(
            "fbr_v2_snapshot_persistence._profile_active = _force_snapshot_profile",
            self.gate,
        )

    def test_gate_proves_v2_preview_contract(self):
        self.assertIn("fbr_native.validate_native_readiness_internal(", self.gate)
        self.assertIn("fbr_native.build_native_payload_internal(", self.gate)
        self.assertIn('"preview_builder_v2"', self.gate)
        self.assertIn('"readiness_snapshot_source_persisted_v2"', self.gate)

    def test_gate_proves_validate_and_submit_fail_closed(self):
        self.assertIn("fbr_native.validate_native_with_fbr_internal(", self.gate)
        self.assertIn("fbr_native.submit_native_to_fbr_internal(", self.gate)
        self.assertIn("V2_NETWORK_CUTOVER_MESSAGE", self.gate)
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE is False", self.gate)

    def test_gate_forbids_actual_fbr_transport(self):
        self.assertIn("fbr_v2_transport.validate_invoice = _forbid_validate", self.gate)
        self.assertIn("fbr_v2_transport.post_invoice = _forbid_post", self.gate)
        self.assertIn('"no_fbr_network_attempts"', self.gate)

    def test_gate_does_not_fabricate_compliance_evidence(self):
        for forbidden in (
            '"Ledgix FBR Reference Data"',
            '"needs_review", 0',
            "sandbox_token",
            "production_token",
            "production_post_armed = 1",
        ):
            self.assertNotIn(forbidden, self.gate)

    def test_gate_rolls_back_and_checks_pos_restoration(self):
        self.assertIn("frappe.db.rollback()", self.gate)
        self.assertIn('"ROLLBACK_CONFIRMED"', self.gate)
        self.assertIn('"persisted_gate_invoices"', self.gate)
        self.assertIn('"main_counter_pos_taxes_and_charges"', self.gate)


if __name__ == "__main__":
    unittest.main()
