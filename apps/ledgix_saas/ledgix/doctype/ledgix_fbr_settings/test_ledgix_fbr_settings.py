from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
    configure_v2_test_environment,
    make_user_with_roles,
)
from ledgix_saas.api import fbr_client, fbr_preflight, fbr_reference
from ledgix_saas.api.fbr_settings import (
    get_active_fbr_token,
    get_fbr_control_state_internal,
    get_fbr_settings,
    save_fbr_settings,
    should_submit_on_sale_submit,
)


class TestLedgixFBRSettingsRetirement(FrappeTestCase):
    def setUp(self):
        super().setUp()
        configure_v2_test_environment()

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def test_cashier_cannot_view_retired_settings_compatibility_state(self):
        cashier = make_user_with_roles("Ledgix Cashier")
        frappe.set_user(cashier.name)
        with self.assertRaises(frappe.PermissionError):
            get_fbr_settings()

    def test_manager_can_view_inert_state_but_cannot_write(self):
        manager = make_user_with_roles("Ledgix Manager")
        frappe.set_user(manager.name)

        settings = get_fbr_settings()
        self.assertTrue(settings["retired"])
        self.assertFalse(settings["enabled"])
        self.assertEqual(settings["mode"], "Disabled")
        self.assertEqual(settings["submit_trigger"], "Manual")
        self.assertFalse(settings["production_post_armed"])
        self.assertNotIn("sandbox_token", settings)
        self.assertNotIn("production_token", settings)

        with self.assertRaises(frappe.PermissionError):
            save_fbr_settings({"mode": "Production"})

    def test_admin_write_is_rejected_because_singleton_is_retired(self):
        admin = make_user_with_roles("Ledgix Admin")
        frappe.set_user(admin.name)

        with self.assertRaises(frappe.ValidationError) as exc:
            save_fbr_settings({"mode": "Production"})

        self.assertIn("retired", str(exc.exception).lower())

    def test_legacy_control_and_token_helpers_are_fail_closed(self):
        frappe.set_user("Administrator")

        state = get_fbr_control_state_internal()
        self.assertTrue(state["retired"])
        self.assertFalse(state["enabled"])
        self.assertFalse(state["can_attempt_submission"])
        self.assertFalse(state["can_manual_validate"])
        self.assertFalse(state["can_manual_submit"])
        self.assertFalse(state["can_auto_submit"])
        self.assertTrue(state["is_manual_only"])

        self.assertFalse(should_submit_on_sale_submit())
        self.assertIsNone(get_active_fbr_token("Sandbox"))
        self.assertIsNone(get_active_fbr_token("Production"))

    def test_legacy_invoice_client_is_retired_without_network(self):
        validate = fbr_client.validate_invoice(
            {"invoiceType": "Sale Invoice"},
            mode="Sandbox",
        )
        post = fbr_client.post_invoice(
            {"invoiceType": "Sale Invoice"},
            mode="Production",
        )

        for result in (validate, post):
            self.assertFalse(result["network_call"])
            self.assertEqual(result["status"], "Retired")
            self.assertIn("retired", (result.get("error") or "").lower())

    def test_legacy_reference_network_apis_are_retired(self):
        for call in (
            lambda: fbr_reference.get_provinces(),
            lambda: fbr_reference.get_document_types(),
            lambda: fbr_reference.get_transaction_types(),
            lambda: fbr_reference.get_uoms(),
            lambda: fbr_reference.get_rates("2025-05-18", "1", "Sindh"),
            lambda: fbr_reference.get_hs_uoms("0101.21", 3),
            lambda: fbr_reference.get_sro_schedules("1", "2025-05-18", "Sindh"),
            lambda: fbr_reference.get_sro_items("2025-05-18", "1"),
            lambda: fbr_reference.get_sales_tax_registration_status(
                "0788762",
                "2025-05-18",
            ),
            lambda: fbr_reference.get_registration_type("0788762"),
        ):
            with self.assertRaises(frappe.ValidationError) as exc:
                call()
            self.assertIn("Legacy FBR reference APIs are retired", str(exc.exception))

    def test_preflight_routes_to_v2_readiness(self):
        expected = {
            "architecture": "ERPNext Native + FBR V2",
            "ready": False,
            "blocking_gaps": ["Official FBR reference cache is empty"],
        }

        with patch.object(
            fbr_preflight.fbr_v2_center,
            "get_fbr_readiness",
            return_value=expected,
        ):
            result = fbr_preflight.get_fbr_readiness()

        self.assertEqual(result, expected)
        self.assertEqual(result["architecture"], "ERPNext Native + FBR V2")
