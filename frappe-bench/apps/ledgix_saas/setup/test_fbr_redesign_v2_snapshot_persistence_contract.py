from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignV2SnapshotPersistenceContract(unittest.TestCase):
    def setUp(self):
        self.extensions = (
            APP_ROOT.parent / "fbr_v1/fbr_v1/setup/erpnext_fbr_schema.py"
        ).read_text(encoding="utf-8")
        self.service = (
            APP_ROOT / "services" / "fbr_v2_snapshot_persistence.py"
        ).read_text(encoding="utf-8")
        self.hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.gate = (
            APP_ROOT / "migration" / "fbr_redesign_v2_snapshot_persistence_gate.py"
        ).read_text(encoding="utf-8")

    def test_fresh_v1_schema_does_not_provision_historical_v2_snapshots(self):
        from fbr_v1.setup.erpnext_fbr_schema import CUSTOM_FIELDS, LEGACY_FISCAL_FIELDS
        for dt in ('Sales Invoice', 'POS Invoice', 'Sales Invoice Item', 'POS Invoice Item'):
            fields = {row['fieldname'] for row in CUSTOM_FIELDS[dt]}
            self.assertFalse(any('fbr_v2_snapshot' in name for name in fields))
        self.assertIn('custom_ledgix_fbr_v2_snapshot_json', LEGACY_FISCAL_FIELDS)
        self.assertIn('harden_existing_legacy_fields', self.extensions)

    def test_snapshot_service_uses_native_collector_only(self):
        self.assertIn("collect_native_tax_breakdown", self.service)
        self.assertIn('"authority": "ERPNext Native"', self.service)

        for forbidden in (
            "erpnext_tax_foundation",
            "Ledgix Item Tax Profile",
            "Ledgix Tax Category",
            "scenario_id",
            "extra_tax_per_unit",
            "further_tax_per_unit",
            "fed_payable_per_unit",
            "default_tax_rate",
        ):
            self.assertNotIn(forbidden, self.service)

    def test_snapshot_capture_is_before_submit_for_both_native_invoice_types(self):
        hook = (
            '"before_submit": '
            '"ledgix_saas.services.fbr_v2_snapshot_persistence.before_submit_capture"'
        )
        self.assertNotIn(hook, self.hooks)
        current_hooks = (APP_ROOT.parent / 'fbr_v1/fbr_v1/hooks.py').read_text()
        self.assertEqual(current_hooks.count('fbr_v1.services.fbr_v1_snapshot_persistence.before_submit_capture'), 2)

    def test_disabled_v2_profile_keeps_hook_dormant(self):
        self.assertIn("def _profile_active(company: str) -> bool:", self.service)
        self.assertIn('mode != "Disabled"', self.service)
        self.assertIn("if not force and not _profile_active(doc.company):", self.service)
        self.assertIn('"captured": False', self.service)

    def test_capture_guard_matches_frappe_before_submit_state(self):
        self.assertIn("cint(doc.docstatus) != 1", self.service)
        self.assertIn('getattr(doc, "_action", "")', self.service)
        self.assertIn('!= "submit"', self.service)
        self.assertIn(
            "FBR V2 immutable snapshot may only be captured during the native ",
            self.service,
        )
        self.assertIn(
            "before_submit transition.",
            self.service,
        )

    def test_snapshot_is_hash_verified_and_refuses_overwrite(self):
        self.assertIn("hashlib.sha256", self.service)
        self.assertIn("Refusing to overwrite legal evidence", self.service)
        self.assertIn("snapshot hash verification failed", self.service)
        self.assertIn("header/line snapshot hash manifest does not match", self.service)

    def test_snapshot_v2_freezes_identity_and_explicit_discount_evidence(self):
        native_snapshot = (
            APP_ROOT / "services" / "erpnext_fbr_snapshot.py"
        ).read_text(encoding="utf-8")

        self.assertIn("SNAPSHOT_VERSION = 2", self.service)
        self.assertIn("erpnext_fbr_identity.resolve_invoice_identity(doc)", self.service)
        self.assertIn('"identity": identity', self.service)

        for fieldname in (
            "price_list_rate",
            "rate_with_margin",
            "discount_percentage",
            "discount_amount",
            "distributed_discount_amount",
        ):
            self.assertIn(f'"{fieldname}"', native_snapshot)

    def test_snapshot_service_does_not_write_database_or_call_fbr(self):
        for forbidden in (
            "frappe.db.set_value(",
            ".db_set(",
            ".insert(",
            ".save(",
            ".submit(",
            "requests.",
            "fbr_client",
            "fbr_transport",
            "post_invoice(",
            "validate_invoice(",
        ):
            self.assertNotIn(forbidden, self.service)

        self.assertIn('"fbr_network_call": False', self.service)

    def test_service_does_not_populate_legacy_snapshot_fields(self):
        for forbidden_assignment in (
            'doc.set("custom_ledgix_fbr_snapshot_version"',
            'doc.set("custom_ledgix_fbr_snapshot_json"',
            'item.set("custom_ledgix_fbr_snapshot_version"',
            'item.set("custom_ledgix_fbr_snapshot_json"',
        ):
            self.assertNotIn(forbidden_assignment, self.service)

    def test_runtime_gate_covers_sale_pos_and_both_return_types(self):
        self.assertIn("build_sales_invoice(", self.gate)
        self.assertIn("create_sales_return(", self.gate)
        self.assertIn("core._new_pos_template()", self.gate)
        self.assertIn(
            'pos_profile.db_set(\n            "taxes_and_charges",',
            self.gate,
        )
        self.assertIn('frappe.clear_cache(doctype="POS Profile")', self.gate)
        self.assertIn("build_pos_invoice(", self.gate)
        self.assertIn(
            'cart_items=[{"item": core.ITEMS["ordinary"], "qty": 1}]',
            self.gate,
        )
        self.assertIn("price_list=price_list", self.gate)
        self.assertIn("client_sale_id=f\"V2-SNAPSHOT-POS-", self.gate)
        self.assertIn(
            'source="FBR V2 Snapshot Persistence Gate"',
            self.gate,
        )
        self.assertIn("make_sales_return(", self.gate)
        self.assertIn("read_persisted_v2_snapshot", self.gate)
        self.assertIn("frappe.db.rollback()", self.gate)
        self.assertIn('"fbr_network_calls": 0', self.gate)


if __name__ == "__main__":
    unittest.main()
