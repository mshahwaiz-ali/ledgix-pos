from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

RETIRED_CONFIG_MASTER_DOCTYPES = (
    "Ledgix Tax Profile",
    "Ledgix Tax Category",
    "Ledgix Tax Rate",
    "Ledgix Item Tax Profile",
)

HISTORICAL_TAX_EVIDENCE_DOCTYPES = (
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
        for doctype in HISTORICAL_TAX_EVIDENCE_DOCTYPES:
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

    def test_frozen_archive_backfill_is_physically_retired(self):
        source = (
            APP_ROOT / "setup" / "erpnext_extensions.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("backfill_erpnext_item_profile_links", source)
        self.assertNotIn('"Ledgix Item Tax Profile"', source)

    def test_external_legacy_tax_links_are_replaced_by_data_snapshots(self):
        extensions = (
            APP_ROOT / "setup" / "erpnext_extensions.py"
        ).read_text(encoding="utf-8")
        phase5 = (
            APP_ROOT / "setup" / "erpnext_phase5_extensions.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn(
            '_cf(\n            "custom_ledgix_fbr_item_profile",',
            extensions,
        )
        self.assertIn(
            '"custom_ledgix_legacy_fbr_item_profile_snapshot"',
            extensions,
        )

        self.assertNotIn(
            '_cf(\n            "custom_ledgix_default_tax_category",',
            phase5,
        )
        self.assertIn(
            '"custom_ledgix_legacy_default_tax_category_snapshot"',
            phase5,
        )

        category = json.loads(
            (
                APP_ROOT / "ledgix" / "doctype" / "ledgix_category"
                / "ledgix_category.json"
            ).read_text(encoding="utf-8")
        )
        row = next(
            x for x in category["fields"]
            if x.get("fieldname") == "default_tax_category"
        )
        self.assertEqual(row.get("fieldtype"), "Data")
        self.assertNotIn("options", row)

        sale_item = json.loads(
            (
                APP_ROOT / "ledgix" / "doctype" / "ledgix_sale_item"
                / "ledgix_sale_item.json"
            ).read_text(encoding="utf-8")
        )
        row = next(
            x for x in sale_item["fields"]
            if x.get("fieldname") == "item_tax_profile_snapshot"
        )
        self.assertEqual(row.get("fieldtype"), "Data")
        self.assertNotIn("options", row)

        migration = (
            APP_ROOT / "migration" / "fbr_phase9_snapshot_link_detachment.py"
        ).read_text(encoding="utf-8")
        self.assertIn("copied_values_preserved", migration)
        self.assertIn("external_legacy_links", migration)
        self.assertNotIn("requests.", migration)
        self.assertNotIn("fbr.gov.pk", migration)

    def test_operational_paths_do_not_call_legacy_tax_engine(self):
        for relative in (
            "api/v2_pos.py",
            "ledgix/doctype/ledgix_sale/ledgix_sale.py",
            "api/fbr_payload.py",
        ):
            source = (APP_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("apply_sale_tax_snapshot", source)

        payload = (APP_ROOT / "api" / "fbr_payload.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("prepare_sale_tax_snapshot_for_doc", payload)
        self.assertNotIn("from ledgix_saas.api.taxation", payload)

    def test_historical_identity_helpers_do_not_read_legacy_tax_profile(self):
        for relative in (
            "services/sales.py",
            "api/fbr_payload.py",
        ):
            source = (APP_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn('"Ledgix Tax Profile"', source)

    def test_demo_seed_uses_v2_mapping_and_keeps_review_required(self):
        demo = (APP_ROOT / "setup" / "erpnext_demo_data.py").read_text(
            encoding="utf-8"
        )
        retail = (
            APP_ROOT / "setup" / "retail_operating_profile.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'FBR_ITEM_MAPPING_DOCTYPE = "Ledgix FBR Item Mapping"',
            demo,
        )
        self.assertIn("doc.needs_review = 1", demo)
        self.assertNotIn('frappe.new_doc("Ledgix Tax Category")', demo)
        self.assertNotIn('frappe.new_doc("Ledgix Item Tax Profile")', demo)
        self.assertNotIn("erpnext_tax_foundation.apply_tax_plan", demo)

        self.assertNotIn('frappe.new_doc("Ledgix Tax Category")', retail)
        self.assertNotIn('frappe.new_doc("Ledgix Item Tax Profile")', retail)
        self.assertIn("_ORIGINAL_ENSURE_TAX_MAPPING", retail)

    def test_config_master_execution_modules_are_tombstones(self):
        forbidden = (
            "Ledgix Tax Profile",
            "Ledgix Tax Category",
            "Ledgix Tax Rate",
            "Ledgix Item Tax Profile",
        )
        for relative in (
            "api/tax_center.py",
            "api/taxation.py",
            "services/tax.py",
            "setup/erpnext_tax_foundation.py",
        ):
            source = (APP_ROOT / relative).read_text(encoding="utf-8")
            for value in forbidden:
                self.assertNotIn(value, source, (relative, value))

        tax_center = (APP_ROOT / "api" / "tax_center.py").read_text(
            encoding="utf-8"
        )
        for method in (
            "get_invoice_tax_snapshots",
            "get_return_tax_snapshots",
            "get_fbr_submission_logs",
            "get_fbr_readiness",
        ):
            self.assertIn(f"def {method}(", tax_center)

        foundation = (
            APP_ROOT / "setup" / "erpnext_tax_foundation.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def sync_custom_fields()", foundation)
        self.assertIn("def get_company_tax_accounts(", foundation)
        self.assertIn("legacy_tax_guard.reject_legacy_tax_action", foundation)

    def test_historical_tax_category_fields_are_data_snapshots(self):
        for slug in (
            "ledgix_invoice_tax_detail",
            "ledgix_return_tax_detail",
        ):
            data = json.loads(
                (
                    APP_ROOT
                    / "ledgix"
                    / "doctype"
                    / slug
                    / f"{slug}.json"
                ).read_text(encoding="utf-8")
            )
            row = next(
                x
                for x in data["fields"]
                if x.get("fieldname") == "tax_category"
            )
            self.assertEqual(row.get("fieldtype"), "Data")
            self.assertEqual(int(row.get("read_only") or 0), 1)
            self.assertNotIn("options", row)

    def test_setup_helpers_cannot_recreate_config_masters(self):
        for relative in (
            "setup/erpnext_extensions.py",
            "setup/retail_cleanup_safe.py",
            "setup/retail_local_hygiene.py",
            "ledgix/doctype/v2_test_utils.py",
            "ledgix/doctype/ledgix_sale/ledgix_sale.js",
        ):
            source = (APP_ROOT / relative).read_text(encoding="utf-8")
            for value in (
                "Ledgix Tax Profile",
                "Ledgix Tax Category",
                "Ledgix Tax Rate",
                "Ledgix Item Tax Profile",
                "ledgix_saas.api.taxation.preview_sale_tax_for_form",
            ):
                self.assertNotIn(value, source, (relative, value))

        extensions = (
            APP_ROOT / "setup" / "erpnext_extensions.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("backfill_erpnext_item_profile_links", extensions)

    def test_legacy_item_group_fields_are_hidden_read_only(self):
        source = (APP_ROOT / "setup" / "erpnext_phase5_extensions.py").read_text(encoding="utf-8")
        for fieldname in (
            "custom_ledgix_tax_defaults_enabled",
            "custom_ledgix_legacy_default_tax_category_snapshot",
            "custom_ledgix_default_taxable",
            "custom_ledgix_default_sales_type",
            "custom_ledgix_default_uom_for_fbr",
            "custom_ledgix_default_scenario_id",
        ):
            at = source.index(f'"{fieldname}"')
            tail = source[at:at+550]
            self.assertIn("hidden=1", tail)
            self.assertIn("read_only=1", tail)


    def test_config_master_packages_are_physically_absent_from_source(self):
        for doctype in RETIRED_CONFIG_MASTER_DOCTYPES:
            slug = doctype.lower().replace(" ", "_")
            self.assertFalse(
                (APP_ROOT / "ledgix" / "doctype" / slug).exists(),
                doctype,
            )

    def test_config_masters_are_removed_from_runtime_registrations(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        permissions = (
            APP_ROOT / "setup" / "permissions.py"
        ).read_text(encoding="utf-8")

        for doctype in RETIRED_CONFIG_MASTER_DOCTYPES:
            self.assertNotIn(f'"{doctype}"', hooks)
            self.assertNotIn(f'"{doctype}":', permissions)

        for doctype in HISTORICAL_TAX_EVIDENCE_DOCTYPES:
            self.assertIn(f'"{doctype}"', hooks)
            self.assertIn(f'"{doctype}":', permissions)

    def test_tax_audit_reference_identity_is_detached_data(self):
        data = json.loads(
            (
                APP_ROOT
                / "ledgix"
                / "doctype"
                / "ledgix_tax_audit_log"
                / "ledgix_tax_audit_log.json"
            ).read_text(encoding="utf-8")
        )
        by_name = {
            row.get("fieldname"): row
            for row in data.get("fields", [])
        }
        for fieldname in ("reference_doctype", "reference_name"):
            row = by_name[fieldname]
            self.assertEqual(row.get("fieldtype"), "Data")
            self.assertEqual(int(row.get("read_only") or 0), 1)
            self.assertNotIn("options", row)

    def test_physical_cleanup_patch_is_registered_last_and_guarded(self):
        patches = [
            line.strip()
            for line in (APP_ROOT / "patches.txt").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
            and not line.lstrip().startswith("[")
            and not line.lstrip().startswith("#")
        ]
        expected = (
            "ledgix_saas.patches.v1_0."
            "cleanup_retired_legacy_tax_config_masters"
        )
        self.assertEqual(patches[-1], expected)

        source = (
            APP_ROOT
            / "patches"
            / "v1_0"
            / "cleanup_retired_legacy_tax_config_masters.py"
        ).read_text(encoding="utf-8")

        for value in (
            "VERIFIED_BACKUP_AND_APPROVED_LEGACY_TAX_CONFIG_CLEANUP",
            "Legacy Retirement State",
            "Disabled",
            "Manual",
            "__frappe_version_snapshot__",
            "Ledgix Tax Audit Log",
            "DROP TABLE IF EXISTS",
            "delete_permanently=True",
            "_assert_mapping_parity",
            "_assert_no_external_references",
        ):
            self.assertIn(value, source)

        self.assertNotIn("requests.", source)
        self.assertNotIn("fbr.gov.pk", source)

        tree = ast.parse(source)
        execute_fn = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "execute"
        )
        no_op_guard = next(
            node
            for node in execute_fn.body
            if isinstance(node, ast.If)
            and "_anything_remaining()" in ast.unparse(node.test)
        )
        no_op_body = [ast.unparse(node) for node in no_op_guard.body]
        self.assertIn("_assert_no_customizations_on_targets()", no_op_body)
        self.assertIn("_assert_retired()", no_op_body)

if __name__ == "__main__":
    unittest.main()
