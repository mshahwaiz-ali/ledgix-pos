from pathlib import Path

from frappe.tests.utils import FrappeTestCase


APP_ROOT = Path(__file__).resolve().parents[3]


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
            ".page-head,",
        )

        for path in files:
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                self.assertNotIn(token, text, f"{path.name} must preserve native Frappe page chrome: {token}")

    def test_surviving_custom_pages_use_native_frappe_page_titles(self):
        expected = {
            APP_ROOT / "ledgix" / "page" / "ledgix_tax_center" / "ledgix_tax_center.js": 'title: "Tax & FBR Center"',
            APP_ROOT / "ledgix" / "page" / "business_intelligence_center" / "business_intelligence_center.js": 'title: "Inventory Intelligence"',
            APP_ROOT / "ledgix" / "page" / "ledgix_pos" / "ledgix_pos.js": 'title: "Ledgix POS"',
        }
        for path, token in expected.items():
            self.assertIn(token, path.read_text(encoding="utf-8"), f"{path.name} must use the native Frappe page title")

    def test_frappe_desk_entrypoint_is_not_shadowed(self):
        www = APP_ROOT / "www"
        self.assertFalse((www / "app.html").exists(), "Ledgix must not copy or replace Frappe's /app Desk template")
        self.assertFalse((www / "app.py").exists(), "Ledgix must not shadow Frappe's /app Desk controller")

    def test_global_hooks_keep_workflow_css_route_scoped(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        self.assertNotIn("ledgix_modal_forms.css", hooks)
        self.assertNotIn("ledgix_navigator", hooks)
        self.assertIn("ledgix_brand.css", hooks)
        self.assertIn("ledgix_v2_tokens.css", hooks)

    def test_permissions_have_one_after_migrate_authority(self):
        hooks = (APP_ROOT / "hooks.py").read_text(encoding="utf-8")
        fast_permissions = (APP_ROOT / "setup" / "fast_permissions.py").read_text(encoding="utf-8")

        # permissions.py remains the policy source of truth, while fast_permissions.py
        # is the single idempotent after-migrate executor for that policy.
        self.assertEqual(hooks.count("ledgix_saas.setup.fast_permissions.after_migrate"), 1)
        self.assertNotIn("ledgix_saas.setup.permissions.after_migrate", hooks)
        self.assertIn("from ledgix_saas.setup import permissions as policy", fast_permissions)
        self.assertNotIn("v2_permissions", hooks)
        self.assertFalse((APP_ROOT / "setup" / "v2_permissions.py").exists())

    def test_pos_has_no_user_facing_stock_mode_switch(self):
        pos_js = (APP_ROOT / "ledgix" / "page" / "ledgix_pos" / "ledgix_pos.js").read_text(encoding="utf-8")
        self.assertNotIn("stock_control_mode", pos_js)
        self.assertNotIn("Billing Only", pos_js)
        self.assertNotIn("Strict Inventory", pos_js)
        self.assertIn("Live Inventory", pos_js)
