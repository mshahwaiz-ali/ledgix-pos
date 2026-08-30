from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import configure_v2_test_environment, make_user_with_roles
from ledgix_saas.api import fbr_client, fbr_reference
from ledgix_saas.api.fbr_settings import (
	get_fbr_control_state_internal,
	get_fbr_settings,
	save_fbr_settings,
	should_submit_on_sale_submit,
)


class TestLedgixFBRSettings(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_cashier_cannot_view_fbr_settings(self):
		cashier = make_user_with_roles("Ledgix Cashier")
		frappe.set_user(cashier.name)
		with self.assertRaises(frappe.PermissionError):
			get_fbr_settings()

	def test_manager_can_view_but_cannot_modify_fbr_settings(self):
		manager = make_user_with_roles("Ledgix Manager")
		frappe.set_user(manager.name)
		settings = get_fbr_settings()
		self.assertEqual(settings["mode"], "Disabled")
		with self.assertRaises(frappe.PermissionError):
			save_fbr_settings({"mode": "Manual Only"})

	def test_admin_can_modify_fbr_control_without_exposing_passwords(self):
		admin = make_user_with_roles("Ledgix Admin")
		frappe.set_user(admin.name)
		result = save_fbr_settings({
			"enabled": 0,
			"mode": "Manual Only",
			"submit_trigger": "Manual",
			"seller_business_name": "Test Seller",
		})
		self.assertEqual(result["mode"], "Manual Only")
		self.assertEqual(result["seller_business_name"], "Test Seller")
		self.assertNotIn("sandbox_token", result)
		self.assertNotIn("production_token", result)

	def test_production_post_is_blocked_until_explicitly_armed(self):
		admin = make_user_with_roles("Ledgix Admin")
		frappe.set_user(admin.name)
		save_fbr_settings({
			"enabled": 1,
			"mode": "Production",
			"submit_trigger": "On Submit",
			"production_post_armed": 0,
		})

		self.assertFalse(should_submit_on_sale_submit())
		result = fbr_client.post_invoice({"invoiceType": "Sale Invoice"}, mode="Production")
		self.assertFalse(result.get("network_call"))
		self.assertEqual(result.get("status"), "Not Ready")
		self.assertIn("not armed", (result.get("error") or "").lower())

	def test_leaving_production_automatically_disarms_posting(self):
		admin = make_user_with_roles("Ledgix Admin")
		frappe.set_user(admin.name)
		armed = save_fbr_settings({
			"enabled": 1,
			"mode": "Production",
			"submit_trigger": "Manual",
			"production_post_armed": 1,
		})
		self.assertTrue(armed["production_post_armed"])

		disarmed = save_fbr_settings({"mode": "Sandbox"})
		self.assertFalse(disarmed["production_post_armed"])

	def test_recovery_workers_stay_fail_closed_when_retry_toggle_is_enabled(self):
		admin = make_user_with_roles("Ledgix Admin")
		frappe.set_user(admin.name)
		save_fbr_settings({
			"enabled": 1,
			"mode": "Production",
			"submit_trigger": "On Submit",
			"production_post_armed": 1,
			"retry_enabled": 1,
			"max_retry_count": 3,
		})

		state = get_fbr_control_state_internal()
		self.assertFalse(state["retry_worker_active"])
		self.assertFalse(state["offline_worker_active"])

	def test_production_network_error_requires_reconciliation_before_retransmission(self):
		fake_requests = Mock()
		fake_requests.post.side_effect = TimeoutError("network down")

		with patch.object(fbr_client, "requests", fake_requests):
			result = fbr_client._send_fbr_request(
				fbr_client.PRODUCTION_POST_URL,
				{"invoiceType": "Sale Invoice"},
				"test-token",
			)

		self.assertTrue(result["network_call"])
		self.assertEqual(result["status"], "Network Error")
		self.assertIn("ambiguous", result["error"].lower())
		self.assertIn("reconcile", result["error"].lower())
		self.assertIn("automatic recovery", result["error"].lower())

	def test_registration_reference_checks_use_official_request_contracts(self):
		fake_response = Mock()
		fake_response.status_code = 200
		fake_response.json.side_effect = [
			{"status code": "00", "status": "Active"},
			{"statuscode": "00", "REGISTRATION_NO": "0788762", "REGISTRATION_TYPE": "Registered"},
		]
		fake_requests = Mock()
		fake_requests.get.return_value = fake_response

		with (
			patch.object(fbr_client, "requests", fake_requests),
			patch.object(fbr_reference, "_active_mode_and_token", return_value=("Sandbox", "test-token")),
		):
			statl = fbr_reference.get_sales_tax_registration_status("0788762", "2025-05-18")
			reg_type = fbr_reference.get_registration_type("0788762")

		self.assertEqual(statl["data"]["status"], "Active")
		self.assertEqual(reg_type["data"]["REGISTRATION_TYPE"], "Registered")
		self.assertEqual(fake_requests.get.call_count, 2)

		statl_call, reg_type_call = fake_requests.get.call_args_list
		self.assertEqual(statl_call.args[0], fbr_reference.STATL_URL)
		self.assertEqual(statl_call.kwargs["params"], {"regno": "0788762", "date": "2025-05-18"})
		self.assertEqual(statl_call.kwargs["headers"]["Authorization"], "Bearer test-token")
		self.assertEqual(reg_type_call.args[0], fbr_reference.REGISTRATION_TYPE_URL)
		self.assertEqual(reg_type_call.kwargs["params"], {"Registration_No": "0788762"})
