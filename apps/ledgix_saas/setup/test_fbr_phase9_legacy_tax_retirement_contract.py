from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

LEGACY_TAX_DOCTYPES = (
    "Ledgix Tax Profile",
    "Ledgix Tax Category",
    "Ledgix Tax Rate",
    "Ledgix Item Tax Profile",
    "Ledgix Tax Audit Log",
    "Ledgix Invoice Tax Detail",
    "Ledgix Return Tax Detail",
)

class TestFBRPhase9LegacyTaxRetirementContract(unittest.TestCase):
    def test_rpc_surfaces_fail_closed(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        guard = "ledgix_saas.api.legacy_tax_guard.reject_legacy_tax_action"
        for method in (
            "ledgix_saas.api.tax_center.get_tax_center_boot",
            "ledgix_saas.api.tax_center.save_tax_profile_settings",
            "ledgix_saas.api.tax_center.preview_tax_calculation",
            "ledgix_saas.api.tax_center.save_tax_category",
            "ledgix_saas.api.tax_center.toggle_tax_category",
            "ledgix_saas.api.tax_center.save_tax_rate",
            "ledgix_saas.api.tax_center.close_tax_rate",
            "ledgix_saas.api.tax_center.get_category_tax_mappings",
            "ledgix_saas.api.tax_center.save_category_tax_defaults",
            "ledgix_saas.api.tax_center.apply_category_tax_to_items",
            "ledgix_saas.api.tax_center.preview_item_effective_tax",
            "ledgix_saas.api.tax_center.save_item_tax_mapping",
            "ledgix_saas.api.tax_center.mark_item_tax_reviewed",
            "ledgix_saas.api.tax_center.toggle_item_tax_mapping",
            "ledgix_saas.api.taxation.preview_sale_tax_for_form",
        ):
            self.assertIn(f'"{method}": "{guard}"', hooks)

    def test_direct_tax_center_entry_points_guard_first(self):
        source = (APP_ROOT / "api" / "tax_center.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        targets = {
            "get_tax_center_boot","save_tax_profile_settings","preview_tax_calculation",
            "save_tax_category","toggle_tax_category","save_tax_rate","close_tax_rate",
            "get_category_tax_mappings","save_category_tax_defaults",
            "apply_category_tax_to_items","preview_item_effective_tax",
            "save_item_tax_mapping","mark_item_tax_reviewed","toggle_item_tax_mapping",
        }
        found = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in targets:
                found.add(node.name)
                self.assertIsInstance(node.body[0], ast.Return, node.name)
                self.assertIn(
                    "legacy_tax_guard.reject_legacy_tax_action",
                    ast.unparse(node.body[0].value),
                )
        self.assertEqual(found, targets)

    def test_archive_permissions_are_read_only(self):
        for doctype in LEGACY_TAX_DOCTYPES:
            slug = doctype.lower().replace(" ", "_")
            data = json.loads(
                (APP_ROOT / "ledgix" / "doctype" / slug / f"{slug}.json")
                .read_text(encoding="utf-8")
            )
            rows = data.get("permissions") or []
            self.assertTrue(rows, doctype)
            for row in rows:
                self.assertEqual(int(row.get("read") or 0), 1)
                for key in ("write","create","delete","submit","cancel","amend","share","email"):
                    self.assertEqual(int(row.get(key) or 0), 0, (doctype, row.get("role"), key))

    def test_v2_center_has_no_old_tax_master_dependency(self):
        source = (APP_ROOT / "api" / "fbr_v2_center.py").read_text(encoding="utf-8")
        for value in ("Ledgix Tax Profile","Ledgix Tax Category","Ledgix Tax Rate","Ledgix Item Tax Profile","_legacy_summary"):
            self.assertNotIn(value, source)

    def test_validation_requires_current_authorities(self):
        source = (APP_ROOT / "validation.py").read_text(encoding="utf-8")
        for value in ('"ledgix_saas.api.taxation"','"ledgix_saas.api.fbr_submission"','"ledgix_saas.api.fbr_client"'):
            self.assertNotIn(value, source)
        for value in (
            '"ledgix_saas.services.erpnext_tax_authority"',
            '"ledgix_saas.api.fbr_v2_center"',
            '"ledgix_saas.api.fbr_reference_v2"',
            '"ledgix_saas.services.fbr_v2_readiness"',
        ):
            self.assertIn(value, source)

    def test_frozen_archive_backfill_is_blocked(self):
        source = (APP_ROOT / "setup" / "erpnext_extensions.py").read_text(encoding="utf-8")
        self.assertIn('"Ledgix Legacy Retirement State"', source)
        self.assertIn('== "Frozen"', source)

    def test_legacy_item_group_fields_are_hidden_read_only(self):
        source = (APP_ROOT / "setup" / "erpnext_phase5_extensions.py").read_text(encoding="utf-8")
        for fieldname in (
            "custom_ledgix_tax_defaults_enabled",
            "custom_ledgix_default_tax_category",
            "custom_ledgix_default_taxable",
            "custom_ledgix_default_sales_type",
            "custom_ledgix_default_uom_for_fbr",
            "custom_ledgix_default_scenario_id",
        ):
            at = source.index(f'"{fieldname}"')
            tail = source[at:at+550]
            self.assertIn("hidden=1", tail)
            self.assertIn("read_only=1", tail)

if __name__ == "__main__":
    unittest.main()
