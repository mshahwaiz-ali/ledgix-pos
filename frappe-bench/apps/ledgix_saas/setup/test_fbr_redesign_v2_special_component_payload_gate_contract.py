from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]
GATE = APP_ROOT / "migration" / "fbr_redesign_v2_special_component_payload_gate.py"


class TestFBRV2SpecialComponentPayloadGateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GATE.read_text()

    def test_gate_is_local_only_and_keeps_cutover_disabled(self):
        self.assertIn('SAFE_SITE = "ledgix-erpnext.local"', self.source)
        self.assertIn("frappe.local.site != SAFE_SITE", self.source)
        self.assertIn('"V2_NETWORK_CUTOVER_ACTIVE"', self.source)
        self.assertIn("must remain False", self.source)
        self.assertIn("v2_network_cutover_still_false", self.source)

    def test_reuses_all_proven_phase1_special_component_fixtures(self):
        for module in (
            "fbr_redesign_phase1_third_schedule_parity_gate",
            "fbr_redesign_phase1_extra_tax_parity_gate",
            "fbr_redesign_phase1_further_tax_parity_gate",
            "fbr_redesign_phase1_fed_parity_gate",
            "fbr_redesign_phase1_withheld_parity_gate",
        ):
            self.assertIn(module, self.source)

    def test_real_persisted_snapshot_and_hash_verification_are_required(self):
        self.assertIn("snapshots.read_persisted_v2_snapshot", self.source)
        self.assertIn('persisted.get("hash_verified")', self.source)
        self.assertIn('persisted.get("snapshot_hash")', self.source)
        self.assertIn('"snapshot_source": "persisted_v2"', self.source)

    def test_in_memory_readiness_shim_is_explicit_and_non_certifying(self):
        self.assertIn("def _mechanics_readiness", self.source)
        self.assertIn("IN_MEMORY_LOCAL_PAYLOAD_MECHANICS_ONLY", self.source)
        self.assertIn("does not prove FBR", self.source)
        self.assertIn(
            "fbr_v2_payload_builder.fbr_v2_readiness.evaluate_invoice_readiness",
            self.source,
        )
        self.assertNotIn('frappe.new_doc("Ledgix FBR Reference Data")', self.source)

    def test_canonical_builder_is_used_for_payload_mechanics(self):
        self.assertIn(
            "fbr_v2_payload_builder.build_payload_candidate(doc.doctype, doc.name)",
            self.source,
        )
        for field in (
            "fixedNotifiedValueOrRetailPrice",
            "salesTaxApplicable",
            "extraTax",
            "furtherTax",
            "fedPayable",
            "salesTaxWithheldAtSource",
            "totalValues",
        ):
            self.assertIn(field, self.source)

    def test_third_schedule_and_withheld_numeric_contracts_are_explicit(self):
        for needle in (
            '"notified": 1200.0',
            '"gst": 216.0',
            '"grand_total": 1216.0',
            '"withheld": withheld.WITHHELD_PER_UNIT',
            '"grand_total": 1180.0',
            '"withheld_payload_total_not_1220"',
            '"withheld_not_posted_to_gl"',
        ):
            self.assertIn(needle, self.source)

    def test_return_payload_remains_fail_closed(self):
        self.assertIn("Debit/Credit Note semantics", self.source)
        self.assertIn("are proven in Sandbox", self.source)
        self.assertIn('"return_payload_still_fail_closed"', self.source)

    def test_queue_transport_and_commit_are_intercepted_and_restored(self):
        for needle in (
            "original_queue = fbr_native.queue_native_for_fbr",
            "fbr_native.queue_native_for_fbr = _no_network_queue",
            "fbr_native.queue_native_for_fbr = original_queue",
            "original_validate = fbr_v2_transport.validate_invoice",
            "original_post = fbr_v2_transport.post_invoice",
            "fbr_v2_transport.validate_invoice = _block_transport",
            "fbr_v2_transport.post_invoice = _block_transport",
            "fbr_v2_transport.validate_invoice = original_validate",
            "fbr_v2_transport.post_invoice = original_post",
            "original_commit = frappe.db.commit",
            "frappe.db.commit = _no_commit",
            "frappe.db.commit = original_commit",
        ):
            self.assertIn(needle, self.source)
        self.assertNotIn("frappe.db.commit()", self.source)

    def test_each_component_case_is_rollback_isolated(self):
        for needle in (
            "for index, spec in enumerate(CASE_SPECS, start=1):",
            "frappe.db.savepoint(savepoint)",
            "frappe.db.rollback(save_point=savepoint)",
            "frappe.db.release_savepoint(savepoint)",
            '"per_case_rollback_clean"',
            '"post_case_rollback"',
            '"case_isolation"',
        ):
            self.assertIn(needle, self.source)

    def test_profile_override_is_temporary_and_everything_rolls_back(self):
        for needle in (
            "original_profile_active = snapshots._profile_active",
            "snapshots._profile_active = _force_profile_active",
            "snapshots._profile_active = original_profile_active",
            "frappe.db.rollback()",
            "before_states = _record_fixture_states()",
            "after_states = _record_fixture_states()",
            '"persisted_gate_records"',
            '"rollback_clean"',
        ):
            self.assertIn(needle, self.source)


if __name__ == "__main__":
    unittest.main()
