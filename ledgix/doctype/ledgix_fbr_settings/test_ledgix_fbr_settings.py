from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import configure_v2_test_environment, make_user_with_roles
from ledgix_saas.api import fbr_client, fbr_preflight, fbr_reference
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

	def test_print_compliance_metadata_is_safe_and_writable(self):
		admin = make_user_with_roles("Ledgix Admin")
		frappe.set_user(admin.name)
		result = save_fbr_settings({
			"software_registration_number": "TEST-SW-REG-001",
			"digital_invoicing_logo": "/files/fbr-approved-test.png",
		})
		self.assertEqual(result["software_registration_number"], "TEST-SW-REG-001")
		self.assertEqual(result["digital_invoicing_logo"], "/files/fbr-approved-test.png")
		self.assertNotIn("sandbox_token", result)
		self.assertNotIn("production_token", result)

		# Do not leak test print metadata into later test cases on the same site.
		save_fbr_settings({
			"software_registration_number": "",
			"digital_invoicing_logo": "",
		})

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

	def test_preflight_disabled_mode_does_not_mark_missing_tokens_ready(self):
		settings = {
			"enabled": False,
			"mode": "Disabled",
			"submit_trigger": "Manual",
			"sandbox_token_configured": False,
			"production_token_configured": False,
			"software_registration_number": "",
			"digital_invoicing_logo": "",
			"production_post_armed": False,
			"retry_enabled": False,
		}
		control = {
			"enabled": False,
			"mode": "Disabled",
			"production_post_ready": False,
			"auto_submit_active": False,
			"retry_worker_active": False,
			"offline_worker_active": False,
		}
		with (
			patch.object(fbr_preflight, "get_fbr_settings", return_value=settings),
			patch.object(fbr_preflight, "get_fbr_control_state", return_value=control),
		):
			result = fbr_preflight.get_fbr_readiness()

		checks = {row["key"]: row for row in result["checks"]}
		self.assertFalse(checks["sandbox_token"]["ready"])
		self.assertFalse(checks["production_token"]["ready"])
		self.assertFalse(checks["digital_invoicing_logo"]["ready"])
		self.assertEqual(result["target_environment"], "Unselected")

	def test_preflight_sandbox_does_not_require_production_controls(self):
		settings = {
			"enabled": True,
			"mode": "Sandbox",
			"submit_trigger": "Manual",
			"sandbox_token_configured": True,
			"production_token_configured": False,
			"software_registration_number": "",
			"digital_invoicing_logo": "",
			"production_post_armed": False,
			"retry_enabled": False,
			"sandbox_post_on_submit": False,
		}
		control = {
			"enabled": True,
			"mode": "Sandbox",
			"production_post_ready": False,
			"auto_submit_active": False,
			"retry_worker_active": False,
			"offline_worker_active": False,
		}
		with (
			patch.object(fbr_preflight, "get_fbr_settings", return_value=settings),
			patch.object(fbr_preflight, "get_fbr_control_state", return_value=control),
		):
			result = fbr_preflight.get_fbr_readiness()

		checks = {row["key"]: row for row in result["checks"]}
		self.assertTrue(checks["sandbox_token"]["ready"])
		self.assertTrue(checks["production_token"]["ready"])
		self.assertEqual(checks["production_token"]["value"], "Not required in Sandbox")
		self.assertTrue(checks["production_post"]["ready"])
		self.assertEqual(checks["production_post"]["value"], "Not required in Sandbox")
		self.assertTrue(checks["automatic_retransmission"]["ready"])

	def test_preflight_rejects_default_demo_seller_identity(self):
		settings = {
			"enabled": False,
			"mode": "Disabled",
			"submit_trigger": "Manual",
			"sandbox_token_configured": False,
			"production_token_configured": False,
			"software_registration_number": "",
			"digital_invoicing_logo": "",
			"production_post_armed": False,
			"retry_enabled": False,
		}
		control = {
			"enabled": False,
			"mode": "Disabled",
			"production_post_ready": False,
			"auto_submit_active": False,
			"retry_worker_active": False,
			"offline_worker_active": False,
		}
		with (
			patch.object(fbr_preflight, "get_fbr_settings", return_value=settings),
			patch.object(fbr_preflight, "get_fbr_control_state", return_value=control),
			patch.object(
				fbr_preflight,
				"get_seller_identity",
				return_value={
					"name": "Ledgix",
					"province": "Punjab",
					"ntn_cnic": "",
					"address": "Demo data - configure real outlet details before go-live",
				},
			),
		):
			result = fbr_preflight.get_fbr_readiness()

		checks = {row["key"]: row for row in result["checks"]}
		self.assertFalse(checks["seller_business_name"]["ready"])
		self.assertFalse(checks["seller_address"]["ready"])
		self.assertTrue(checks["seller_province"]["ready"])
		self.assertIn("Seller Business Name", result["blocking_gaps"])
		self.assertIn("Seller Address", result["blocking_gaps"])
