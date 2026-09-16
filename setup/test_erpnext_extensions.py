import unittest
from pathlib import Path

from ledgix_saas.setup import erpnext_extensions


class TestERPNextExtensionContract(unittest.TestCase):
    def test_phase3_targets_only_standard_erpnext_documents(self):
        self.assertEqual(
            set(erpnext_extensions.CUSTOM_FIELDS),
            {"Customer", "Sales Invoice", "POS Invoice", "Sales Invoice Item", "POS Invoice Item"},
        )

    def test_all_extension_fields_use_custom_namespace(self):
        for doctype, fields in erpnext_extensions.CUSTOM_FIELDS.items():
            with self.subTest(doctype=doctype):
                for field in fields:
                    self.assertTrue(field["fieldname"].startswith("custom_ledgix_"))
                    self.assertEqual(field.get("module"), "Ledgix")

    def test_line_legal_snapshots_are_immutable_contracts(self):
        for doctype in ("Sales Invoice Item", "POS Invoice Item"):
            legal_fields = [
                field
                for field in erpnext_extensions.CUSTOM_FIELDS[doctype]
                if field["fieldtype"] not in {"Section Break", "Column Break"}
            ]
            self.assertTrue(legal_fields)
            for field in legal_fields:
                self.assertEqual(field.get("read_only"), 1)
                self.assertEqual(field.get("no_copy"), 1)

    def test_business_profile_defaults_cover_product_modes(self):
        self.assertEqual(
            set(erpnext_extensions.PROFILE_DEFAULTS),
            {"Invoice + FBR Only", "Small Retail", "Full Retail", "B2B", "Mixed"},
        )
        invoice_only = erpnext_extensions.PROFILE_DEFAULTS["Invoice + FBR Only"]
        self.assertEqual(invoice_only["enable_inventory"], 0)
        self.assertEqual(invoice_only["enable_pos"], 0)
        self.assertEqual(invoice_only["enable_fbr"], 1)
        mixed = erpnext_extensions.PROFILE_DEFAULTS["Mixed"]
        self.assertTrue(all(mixed.values()))

    def test_role_matrix_keeps_cashier_out_of_purchase_writes(self):
        self.assertNotIn("Ledgix Cashier", erpnext_extensions.ERPNext_ROLE_PERMISSIONS["Purchase Invoice"])
        self.assertNotIn("Ledgix Cashier", erpnext_extensions.ERPNext_ROLE_PERMISSIONS["Purchase Receipt"])
        self.assertEqual(
            erpnext_extensions.ERPNext_ROLE_PERMISSIONS["POS Invoice"]["Ledgix Cashier"]["submit"],
            1,
        )

    def test_patch_and_after_migrate_are_registered(self):
        app_root = Path(__file__).resolve().parents[1]
        hooks_source = (app_root / "hooks.py").read_text(encoding="utf-8")
        patches_source = (app_root / "patches.txt").read_text(encoding="utf-8")
        self.assertIn("ledgix_saas.setup.erpnext_extensions.after_migrate", hooks_source)
        self.assertIn("ledgix_saas.patches.v1_0.sync_erpnext_extension_schema", patches_source)
