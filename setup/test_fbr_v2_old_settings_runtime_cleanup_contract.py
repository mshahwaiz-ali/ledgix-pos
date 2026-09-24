from __future__ import annotations

import json
import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]

SETTINGS = (APP_ROOT / "api" / "fbr_settings.py").read_text(encoding="utf-8")
SETTINGS_DOCTYPE_DIR = (
    APP_ROOT
    / "ledgix"
    / "doctype"
    / "ledgix_fbr_settings"
)
DEMO = (APP_ROOT / "setup" / "demo_data.py").read_text(encoding="utf-8")
NATIVE_DEMO = (APP_ROOT / "setup" / "erpnext_demo_data.py").read_text(encoding="utf-8")
VALIDATION = (APP_ROOT / "validation.py").read_text(encoding="utf-8")
PERMISSIONS = (APP_ROOT / "setup" / "permissions.py").read_text(encoding="utf-8")
GATE = (
    APP_ROOT / "migration" / "fbr_v2_old_settings_runtime_cleanup_gate.py"
).read_text(encoding="utf-8")

PRINTS = [
    json.loads(
        (
            APP_ROOT
            / "ledgix"
            / "print_format"
            / "ledgix_b2b_invoice"
            / "ledgix_b2b_invoice.json"
        ).read_text(encoding="utf-8")
    )["html"],
    json.loads(
        (
            APP_ROOT
            / "ledgix"
            / "print_format"
            / "ledgix_thermal_receipt"
            / "ledgix_thermal_receipt.json"
        ).read_text(encoding="utf-8")
    )["html"],
]


class TestOldFBRSettingsRuntimeCleanup(unittest.TestCase):
    def test_old_settings_api_is_inert_compatibility_shell(self):
        self.assertIn("LEGACY_SETTINGS_RETIRED_MESSAGE", SETTINGS)
        self.assertIn("return dict(DISABLED_DEFAULTS)", SETTINGS)
        self.assertIn("def save_fbr_settings(values=None):", SETTINGS)
        self.assertIn("frappe.throw(LEGACY_SETTINGS_RETIRED_MESSAGE)", SETTINGS)
        self.assertIn("def get_active_fbr_token(mode=None):", SETTINGS)
        self.assertNotIn("get_decrypted_password", SETTINGS)
        self.assertNotIn("frappe.get_single(", SETTINGS)
        self.assertNotIn("doc.save()", SETTINGS)

    def test_old_settings_doctype_source_is_removed(self):
        self.assertFalse(SETTINGS_DOCTYPE_DIR.exists())

    def test_demo_runtime_uses_company_scoped_v2_profile(self):
        self.assertNotIn("Ledgix FBR Settings", DEMO)
        self.assertNotIn("Ledgix FBR Settings", NATIVE_DEMO)
        self.assertIn('FBR_PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"', NATIVE_DEMO)
        self.assertIn("def _fbr_profile_state(company: str)", NATIVE_DEMO)
        self.assertIn("profile.production_post_armed = 0", NATIVE_DEMO)

    def test_legacy_prints_do_not_read_mutable_old_or_v2_config(self):
        for html in PRINTS:
            self.assertNotIn("Ledgix FBR Settings", html)
            self.assertNotIn("fbr_settings.", html)
            self.assertNotIn("Ledgix FBR Integration Profile", html)
            self.assertIn("doc.fbr_invoice_number", html)

    def test_validation_is_v2_owned(self):
        self.assertNotIn('"Ledgix FBR Settings": (', VALIDATION)
        self.assertNotIn('"ledgix_saas.api.fbr_settings",', VALIDATION)
        self.assertIn('"Ledgix FBR Integration Profile": (', VALIDATION)
        self.assertIn('"ledgix_saas.services.fbr_v2_status",', VALIDATION)
        self.assertIn("REQUIRED_SCHEDULER_METHODS = ()", VALIDATION)

    def test_permission_sync_no_longer_registers_old_settings(self):
        self.assertNotIn('"Ledgix FBR Settings":', PERMISSIONS)

    def test_runtime_gate_does_not_import_or_execute_compatibility_api(self):
        self.assertNotIn("from ledgix_saas.api import fbr_native, fbr_settings", GATE)
        self.assertNotIn("from ledgix_saas.api import fbr_settings", GATE)
        self.assertNotIn("fbr_settings.get_", GATE)
        self.assertNotIn("fbr_settings.save_", GATE)
        self.assertIn("SETTINGS_SOURCE", GATE)
        self.assertIn("LEGACY_SOURCE_DIR", GATE)
        self.assertIn('"legacy_singleton_removed"', GATE)
        self.assertIn('"legacy_doctype_source_removed"', GATE)
        self.assertIn('"database_write": False', GATE)
        self.assertIn('"real_fbr_network_calls": 0', GATE)


if __name__ == "__main__":
    unittest.main()
