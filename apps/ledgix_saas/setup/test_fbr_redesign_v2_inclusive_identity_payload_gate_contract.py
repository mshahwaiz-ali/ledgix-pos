from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
GATE = APP_ROOT / "migration" / "fbr_redesign_v2_inclusive_identity_payload_gate.py"


class TestFBRV2InclusiveIdentityPayloadGateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GATE.read_text(encoding="utf-8")

    def test_gate_is_local_only_and_cutover_must_stay_false(self):
        self.assertIn("INTEGRATION_SITE", self.source)
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE", self.source)
        self.assertIn("must remain False", self.source)

    def test_gate_uses_real_inclusive_erpnext_fixture(self):
        self.assertIn("core._new_inclusive_template()", self.source)
        self.assertIn("core._direct_sales_invoice(", self.source)
        self.assertIn("EXPECTED_PRINTED_RATE = 1180.0", self.source)
        self.assertIn("EXPECTED_NET = 1000.0", self.source)
        self.assertIn("EXPECTED_GST = 180.0", self.source)

    def test_gate_requires_snapshot_v2_hash_evidence(self):
        self.assertIn("snapshots.SNAPSHOT_VERSION != 2", self.source)
        self.assertIn("read_persisted_v2_snapshot", self.source)
        self.assertIn('"snapshot_hash_verified"', self.source)

    def test_gate_proves_identity_survives_live_master_change(self):
        self.assertIn('"Company"', self.source)
        self.assertIn('"tax_id"', self.source)
        self.assertIn("erpnext_fbr_identity.resolve_invoice_identity(invoice)", self.source)
        self.assertIn(
            '"readiness_after_mutation_still_uses_frozen_identity"',
            self.source,
        )
        self.assertIn('"payload_uses_frozen_seller_identity"', self.source)

    def test_gate_proves_inclusive_tax_is_not_discount(self):
        self.assertIn('"snapshot_explicit_discount_zero"', self.source)
        self.assertIn('"snapshot_distributed_discount_zero"', self.source)
        self.assertIn('"payload_discount_zero"', self.source)
        self.assertIn('"payload_total_values_1180"', self.source)

    def test_readiness_mapping_override_is_in_memory_only(self):
        self.assertIn("mechanics_only_readiness_shim", self.source)
        self.assertIn("IN-MEMORY-INCLUSIVE-MECHANICS", self.source)
        self.assertNotIn("Ledgix FBR Reference Data", self.source)

    def test_no_real_transport_or_commit(self):
        self.assertIn("queue_native_for_fbr = _no_network_queue", self.source)
        self.assertIn("submit_hook_intercepts", self.source)
        self.assertIn('"no_real_fbr_network_calls": True', self.source)
        self.assertIn("frappe.db.commit = _no_commit", self.source)
        self.assertNotIn("fbr_v2_transport", self.source)
        self.assertNotIn("requests.", self.source)
        self.assertNotIn("network_attempts", self.source)

    def test_gate_rolls_back_master_and_fixture_changes(self):
        self.assertIn("frappe.db.rollback()", self.source)
        self.assertIn('"company_tax_id_restored"', self.source)
        self.assertIn('"item_disabled_restored"', self.source)
        self.assertIn('"rollback_clean"', self.source)
        self.assertIn('"gate_gl_rows_left"', self.source)


if __name__ == "__main__":
    unittest.main()
