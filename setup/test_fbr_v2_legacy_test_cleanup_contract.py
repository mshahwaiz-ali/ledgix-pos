from pathlib import Path
import ast
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_COMMIT = "808f384311b0545e1d3e39791f085db5678832bb"

SALE_TEST = APP_ROOT / "ledgix/doctype/ledgix_sale/test_ledgix_sale.py"
RETURN_TEST = APP_ROOT / "ledgix/doctype/ledgix_sales_return/test_ledgix_sales_return.py"
ITEM_TAX_TEST = APP_ROOT / "ledgix/doctype/ledgix_item_tax_profile/test_ledgix_item_tax_profile.py"
SETTINGS_TEST = APP_ROOT / "ledgix/doctype/ledgix_fbr_settings/test_ledgix_fbr_settings.py"
TEST_UTILS = APP_ROOT / "ledgix/doctype/v2_test_utils.py"
RETIREMENT_CONTRACT = APP_ROOT / "setup/test_phase12_legacy_business_test_retirement_contract.py"


class TestLegacyFBRTestCleanup(unittest.TestCase):
    def test_shared_helper_never_executes_old_settings(self):
        text = TEST_UTILS.read_text(encoding="utf-8")
        for forbidden in (
            'set_single_value("Ledgix FBR Settings"',
            "set_single_value('Ledgix FBR Settings'",
            'clear_cache(doctype="Ledgix FBR Settings")',
            "clear_cache(doctype='Ledgix FBR Settings')",
            'get_single("Ledgix FBR Settings")',
            "get_single('Ledgix FBR Settings')",
        ):
            self.assertNotIn(forbidden, text)

    def test_old_settings_execution_suite_is_removed_and_replaced(self):
        self.assertFalse(SETTINGS_TEST.exists())

        runtime_contract = (
            APP_ROOT / "setup/test_fbr_v2_old_settings_runtime_cleanup_contract.py"
        ).read_text(encoding="utf-8")
        source_contract = (
            APP_ROOT / "setup/test_fbr_v2_old_settings_source_deregistration_contract.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "test_old_settings_api_is_inert_compatibility_shell",
            runtime_contract,
        )
        self.assertIn(
            "test_runtime_gate_does_not_import_or_execute_compatibility_api",
            runtime_contract,
        )
        self.assertIn(
            "test_interim_package_is_preserved_but_migration_authority_is_retired",
            source_contract,
        )

    def test_legacy_business_test_helpers_cannot_reopen_frozen_engine(self):
        text = TEST_UTILS.read_text(encoding="utf-8")
        self.assertIn("_retired_legacy_business_fixture", text)
        for helper in (
            "make_price_list",
            "make_item",
            "make_item_price",
            "make_customer",
            "make_supplier",
            "ensure_cash_payment_method",
            "make_sale",
            "make_purchase",
            "make_sales_return",
        ):
            self.assertIn(
                f'return _retired_legacy_business_fixture("{helper}")',
                text,
                helper,
            )

    def _assert_import_safe_historical_stub(self, path: Path):
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        self.assertIn("LEGACY_BUSINESS_TEST_RETIRED = True", text)
        self.assertIn(
            f'LEGACY_HISTORICAL_SOURCE_COMMIT = "{HISTORICAL_COMMIT}"',
            text,
        )
        self.assertIn(
            "@unittest.skip(LEGACY_BUSINESS_TEST_RETIREMENT_REASON)",
            text,
        )
        for forbidden in (
            "import frappe",
            "from frappe",
            "from ledgix",
            "from ledgix_saas",
            "legacy_write_bypass(",
            "release_legacy_freeze_for_rollback(",
        ):
            self.assertNotIn(forbidden, text)

    def test_sale_submission_test_is_archived_as_import_safe_historical_suite(self):
        self._assert_import_safe_historical_stub(SALE_TEST)
        text = SALE_TEST.read_text(encoding="utf-8")
        self.assertIn(
            'LEGACY_HISTORICAL_SOURCE_PATH = "ledgix/doctype/ledgix_sale/test_ledgix_sale.py"',
            text,
        )

    def test_return_submission_tests_are_archived_as_import_safe_historical_suite(self):
        self._assert_import_safe_historical_stub(RETURN_TEST)
        text = RETURN_TEST.read_text(encoding="utf-8")
        self.assertIn(
            'LEGACY_HISTORICAL_SOURCE_PATH = "ledgix/doctype/ledgix_sales_return/test_ledgix_sales_return.py"',
            text,
        )

    def test_historical_payload_snapshot_suite_is_archived_not_reexecuted(self):
        self._assert_import_safe_historical_stub(ITEM_TAX_TEST)
        text = ITEM_TAX_TEST.read_text(encoding="utf-8")
        self.assertIn(
            'LEGACY_HISTORICAL_SOURCE_PATH = "ledgix/doctype/ledgix_item_tax_profile/test_ledgix_item_tax_profile.py"',
            text,
        )

    def test_native_v2_contracts_replace_historical_execution_authority(self):
        snapshot = (
            APP_ROOT / "setup/test_fbr_redesign_v2_snapshot_persistence_contract.py"
        ).read_text(encoding="utf-8")
        payload = (
            APP_ROOT / "setup/test_fbr_v2_payload_builder_contract.py"
        ).read_text(encoding="utf-8")
        retirement = RETIREMENT_CONTRACT.read_text(encoding="utf-8")

        self.assertIn("test_snapshot_is_hash_verified_and_refuses_overwrite", snapshot)
        self.assertIn("test_snapshot_v2_freezes_identity_and_explicit_discount_evidence", snapshot)
        self.assertIn("test_builder_uses_persisted_v2_readiness_only", payload)
        self.assertIn("test_payload_reconciles_to_erpnext_grand_total", payload)
        self.assertIn("test_fully_retired_modules_are_import_safe_stubs", retirement)


if __name__ == "__main__":
    unittest.main()
