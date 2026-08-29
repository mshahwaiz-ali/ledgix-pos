from pathlib import Path

from frappe.tests.utils import FrappeTestCase


APP_ROOT = Path(__file__).resolve().parents[4]


class TestV2UIArchitecture(FrappeTestCase):
    def test_surviving_custom_pages_do_not_replace_frappe_chrome(self):
        files = [
            APP_ROOT / "ledgix" / "page" / "ledgix_tax_center" / "ledgix_tax_center.js",
            APP_ROOT / "ledgix" / "page" / "ledgix_tax_center" / "ledgix_tax_center.css",
            APP_ROOT / "ledgix" / "page" / "business_intelligence_center" / "business_intelligence_center.js",
            APP_ROOT / "ledgix" / "page" / "business_intelligence_center" / "business_intelligence_center.css",
            APP_ROOT / "public" / "js" / "ledgix_brand.js",
            APP_ROOT / "public" / "css" / "ledgix_brand.css",
        ]
        forbidden = (
            "LedgixNavigator",
            "ledgix-page-no-frappe-head",
            'find(".page-head',
            ".page-head,")

        for path in files:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{path.name} must preserve native Frappe page chrome: {token}")

    def test_global_hooks_keep_workflow_css_route_scoped(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertNotIn("ledgix_modal_forms.css", hooks)
        self.assertNotIn("ledgix_navigator", hooks)
        self.assertIn("ledgix_brand.css", hooks)
        self.assertIn("ledgix_v2_tokens.css", hooks)

    def test_pos_has_no_user_facing_stock_mode_switch(self):
        pos_js = (APP_ROOT / "ledgix" / "page" / "ledgix_pos" / "ledgix_pos.js").read_text(encoding="utf-8")
        self.assertNotIn("stock_control_mode", pos_js)
        self.assertNotIn("Billing Only", pos_js)
        self.assertNotIn("Strict Inventory", pos_js)
        self.assertIn("Live Inventory", pos_js)
