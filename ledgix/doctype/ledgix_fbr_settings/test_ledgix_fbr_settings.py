import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import configure_v2_test_environment, make_user_with_roles
from ledgix_saas.api.fbr_settings import get_fbr_settings, save_fbr_settings


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
		self.assertTrue(result["success"])
		settings = get_fbr_settings()
		self.assertEqual(settings["mode"], "Manual Only")
		self.assertNotIn("sandbox_token", settings)
		self.assertNotIn("production_token", settings)
