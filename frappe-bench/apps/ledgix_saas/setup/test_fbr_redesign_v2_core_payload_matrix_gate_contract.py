from __future__ import annotations

import unittest
from pathlib import Path


APP = Path(__file__).resolve().parents[1]
GATE = APP / "migration" / "fbr_redesign_v2_core_payload_matrix_gate.py"


class TestFBRV2CorePayloadMatrixGateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GATE.read_text(encoding="utf-8")

    def test_gate_is_local_and_cutover_fail_closed(self):
        self.assertIn("INTEGRATION_SITE", self.source)
        self.assertIn("V2_NETWORK_CUTOVER_ACTIVE must remain False", self.source)
        self.assertIn("snapshots.SNAPSHOT_VERSION != 2", self.source)

    def test_gate_covers_complete_ordinary_matrix(self):
        for case in (
            '"standard_18"',
            '"inclusive_18"',
            '"zero_rated"',
            '"exempt"',
            '"mixed_standard_zero_exempt"',
        ):
            self.assertIn(case, self.source)

    def test_gate_reuses_phase1_erpnext_native_fixtures(self):
        self.assertIn("fbr_redesign_phase1_native_core_parity_gate as core", self.source)
        self.assertIn("core._direct_sales_invoice(", self.source)
        self.assertIn("core._new_inclusive_template()", self.source)
        self.assertIn("erpnext_tax_authority.current_tax_authority()", self.source)

    def test_gate_consumes_real_persisted_v2_snapshots(self):
        self.assertIn("read_persisted_v2_snapshot", self.source)
        self.assertIn('"snapshot_hash_verified"', self.source)
        self.assertIn('"payload_snapshot_version_2"', self.source)

    def test_gate_proves_numeric_payload_mechanics(self):
        for marker in (
            '"valueSalesExcludingST": 1000',
            '"salesTaxApplicable": 180',
            '"totalValues": 1180',
            '"totalValues": 1000',
            '"expected_grand": 3180',
            '"payload_total_matches_erpnext"',
        ):
            self.assertIn(marker, self.source)

    def test_gate_proves_inclusive_tax_does_not_become_discount(self):
        self.assertIn('"discount": 0', self.source)
        self.assertIn('"all_payload_discounts_zero"', self.source)

    def test_mapping_and_readiness_bypass_is_in_memory_only(self):
        self.assertIn("IN-MEMORY-CORE-", self.source)
        self.assertIn("mechanics_only_readiness_shim", self.source)
        self.assertNotIn("Ledgix FBR Reference Data", self.source)
        self.assertNotIn("provision_component_mappings", self.source)

    def test_gate_has_per_case_and_final_rollback(self):
        self.assertIn("frappe.db.savepoint(savepoint)", self.source)
        self.assertIn("frappe.db.rollback(save_point=savepoint)", self.source)
        self.assertIn("frappe.db.release_savepoint(savepoint)", self.source)
        self.assertIn('"post_case_rollback"', self.source)
        self.assertIn('"rollback_clean"', self.source)

    def test_gate_blocks_real_network_and_commit(self):
        self.assertIn("queue_native_for_fbr = _no_network_queue", self.source)
        self.assertIn("frappe.db.commit = _no_commit", self.source)
        self.assertIn('"real_fbr_network_calls": 0', self.source)
        self.assertNotIn("fbr_v2_transport", self.source)
        self.assertNotIn("requests.", self.source)


if __name__ == "__main__":
    unittest.main()
