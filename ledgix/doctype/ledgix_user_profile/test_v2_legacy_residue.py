from pathlib import Path

from frappe.tests.utils import FrappeTestCase


APP_ROOT = Path(__file__).resolve().parents[4]


class TestV2LegacyResidue(FrappeTestCase):
    def test_active_ui_and_business_controllers_have_no_retired_mode_or_navigator_contract(self):
        roots = [
            APP_ROOT / "ledgix" / "page",
            APP_ROOT / "ledgix" / "doctype",
        ]
        forbidden = (
            "LedgixNavigator",
            "ledgix-page-no-frappe-head",
            "stock_control_mode",
            "Billing Only",
            "Ledgix POS Theme Settings",
            "Ledgix Mode Settings",
            "Ledgix Super Admin",
        )

        violations = []
        for root in roots:
            for path in root.rglob("*"):
                if path.suffix not in {".py", ".js", ".json", ".css"}:
                    continue
                if path.name.startswith("test_"):
                    continue
                text = path.read_text(encoding="utf-8")
                for token in forbidden:
                    if token in text:
                        violations.append(f"{path.relative_to(APP_ROOT)} -> {token}")

        self.assertEqual(violations, [], "Retired runtime concepts remain:\n" + "\n".join(violations))

    def test_retired_custom_page_source_directories_are_absent(self):
        page_root = APP_ROOT / "ledgix" / "page"
        for slug in (
            "ledgix_dashboard",
            "ledgix_operations",
            "ledgix_reports",
            "quick_item_scan",
        ):
            self.assertFalse((page_root / slug).exists(), f"Retired Page source still exists: {slug}")

    def test_retired_product_doctype_source_directories_are_absent(self):
        doctype_root = APP_ROOT / "ledgix" / "doctype"
        for slug in (
            "ledgix_mode_settings",
            "ledgix_pos_theme_settings",
            "ledgix_maintenance_tool",
        ):
            self.assertFalse((doctype_root / slug).exists(), f"Retired DocType source still exists: {slug}")

    def test_destructive_maintenance_api_is_not_part_of_product_runtime(self):
        self.assertFalse((APP_ROOT / "api" / "maintenance.py").exists())
