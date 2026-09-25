from pathlib import Path
import ast
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_COMMIT = "808f384311b0545e1d3e39791f085db5678832bb"

FULLY_RETIRED_TEST_FILES = (
    "ledgix/doctype/ledgix_item_price/test_ledgix_item_price.py",
    "ledgix/doctype/ledgix_payment/test_ledgix_payment.py",
    "ledgix/doctype/ledgix_payment/test_v2_return_credit_balance.py",
    "ledgix/doctype/ledgix_pos_hold/test_ledgix_pos_hold.py",
    "ledgix/doctype/ledgix_pos_shift/test_ledgix_pos_shift.py",
    "ledgix/doctype/ledgix_purchase/test_ledgix_purchase.py",
    "ledgix/doctype/ledgix_sale/test_ledgix_sale.py",
    "ledgix/doctype/ledgix_sale/test_v2_print_formats.py",
    "ledgix/doctype/ledgix_sales_return/test_ledgix_sales_return.py",
    "ledgix/doctype/ledgix_stock_movement/test_ledgix_stock_movement.py",
    "ledgix/doctype/ledgix_stock_serial/test_v2_serial_pos.py",
    "ledgix/doctype/ledgix_stock_serial/test_v2_serial_return.py",
    "ledgix/doctype/ledgix_fbr_correction_request/test_ledgix_fbr_correction_request.py",
)

MIXED_ACTIVE_TEST_FILE = "ledgix/doctype/ledgix_user_profile/test_ledgix_user_profile.py"

LEGACY_FIXTURE_HELPERS = (
    "make_price_list",
    "make_item",
    "make_item_price",
    "make_customer",
    "make_supplier",
    "ensure_cash_payment_method",
    "make_sale",
    "make_purchase",
    "make_sales_return",
)

NATIVE_COVERAGE = {
    "selling": (
        "setup/test_erpnext_phase6_extensions.py",
        "migration/erpnext_phase6_selling_gate.py",
    ),
    "inventory": (
        "setup/test_erpnext_phase7_contract.py",
        "migration/erpnext_phase7_buying_inventory_gate.py",
    ),
    "pos_returns": (
        "setup/test_erpnext_phase8_contract.py",
        "migration/erpnext_phase8_pos_gate.py",
    ),
    "fbr_native": (
        "setup/test_erpnext_phase9_contract.py",
        "migration/erpnext_phase9_fbr_gate.py",
    ),
    "printing_reporting": (
        "setup/test_erpnext_phase10_contract.py",
        "migration/erpnext_phase10_reporting_print_gate.py",
    ),
    "legacy_freeze": (
        "setup/test_erpnext_phase12_contract.py",
        "migration/erpnext_phase12_legacy_retirement_gate.py",
    ),
    "fbr_v2": (
        "setup/test_fbr_v2_payload_builder_contract.py",
        "migration/fbr_redesign_v2_core_payload_matrix_gate.py",
    ),
}


class TestPhase12LegacyBusinessTestRetirement(unittest.TestCase):
    def test_fully_retired_modules_are_import_safe_stubs(self):
        for rel in FULLY_RETIRED_TEST_FILES:
            text = (APP_ROOT / rel).read_text(encoding="utf-8")
            ast.parse(text)
            self.assertIn("LEGACY_BUSINESS_TEST_RETIRED = True", text, rel)
            self.assertIn(
                f'LEGACY_HISTORICAL_SOURCE_COMMIT = "{HISTORICAL_COMMIT}"',
                text,
                rel,
            )
            self.assertIn("@unittest.skip(LEGACY_BUSINESS_TEST_RETIREMENT_REASON)", text, rel)
            self.assertNotIn("import frappe", text, rel)
            self.assertNotIn("from frappe", text, rel)
            self.assertNotIn("from ledgix", text, rel)
            self.assertNotIn("from ledgix_saas", text, rel)

    def test_user_profile_suite_remains_active_except_two_legacy_customer_tests(self):
        text = (APP_ROOT / MIXED_ACTIVE_TEST_FILE).read_text(encoding="utf-8")
        self.assertIn("LEGACY_BUSINESS_TEST_RETIRED = False", text)
        self.assertIn("LEGACY_PARTIAL_TEST_RETIREMENT = True", text)
        self.assertNotIn(
            "@unittest.skip(LEGACY_BUSINESS_TEST_RETIREMENT_REASON)\nclass TestLedgixUserProfile",
            text,
        )
        self.assertEqual(
            text.count("@unittest.skip(LEGACY_BUSINESS_TEST_RETIREMENT_REASON)"),
            2,
        )
        for active in (
            "test_v2_pricing_and_payment_permissions_share_main_role_contract",
            "test_page_and_workspace_roles_match_v2_navigation_contract",
            "test_only_four_custom_ledgix_pages_remain",
            "test_workspace_shortcuts_resolve_to_real_frappe_targets",
            "test_role_home_pages_route_cashier_to_pos_and_management_to_workspace",
            "test_retired_product_settings_maintenance_and_role_are_absent",
            "test_stock_movement_is_a_read_only_business_ledger",
        ):
            self.assertIn(f"def {active}(", text)

    def test_physically_retired_config_test_packages_remain_absent(self):
        for name in ("ledgix_fbr_settings", "ledgix_item_tax_profile"):
            self.assertFalse((APP_ROOT / "ledgix" / "doctype" / name).exists())
        for name in ("test_fbr_v2_old_settings_source_deregistration_contract.py",
                     "test_fbr_phase9_legacy_tax_retirement_contract.py"):
            self.assertTrue((APP_ROOT / "setup" / name).is_file())

    def test_shared_legacy_business_fixture_helpers_fail_closed(self):
        text = (APP_ROOT / "ledgix/doctype/v2_test_utils.py").read_text(encoding="utf-8")
        self.assertIn("_retired_legacy_business_fixture", text)
        for helper in LEGACY_FIXTURE_HELPERS:
            self.assertIn(
                f'return _retired_legacy_business_fixture("{helper}")',
                text,
                helper,
            )
        self.assertIn("make_user_with_roles", text)
        self.assertIn("configure_v2_test_environment", text)

    def test_native_replacement_coverage_files_exist(self):
        for domain, paths in NATIVE_COVERAGE.items():
            for rel in paths:
                self.assertTrue((APP_ROOT / rel).exists(), f"{domain}: {rel}")

    def test_phase12_freeze_contract_remains_authoritative(self):
        text = (APP_ROOT / "setup/test_erpnext_phase12_contract.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("test_hooks_freeze_all_legacy_top_level_business_doctypes", text)
        self.assertIn("test_frozen_legacy_permissions_are_audit_only", text)

    def test_static_fbr_and_erpnext_contracts_are_not_mass_retired(self):
        retained = (
            "setup/test_erpnext_phase10_contract.py",
            "setup/test_erpnext_phase11_contract.py",
            "setup/test_erpnext_phase12_contract.py",
            "setup/test_fbr_redesign_v2_snapshot_persistence_contract.py",
            "setup/test_fbr_v2_payload_builder_contract.py",
            "setup/test_fbr_v2_legacy_desk_retirement_contract.py",
        )
        for rel in retained:
            text = (APP_ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("LEGACY_BUSINESS_TEST_RETIRED = True", text, rel)


if __name__ == "__main__":
    unittest.main()
