import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	make_customer,
	make_user_with_roles,
)
from ledgix_saas.api.v2_b2b import get_customer_credit


class TestLedgixUserProfile(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_cashier_is_limited_to_cashier_surface(self):
		cashier = make_user_with_roles("Ledgix Cashier")
		customer = make_customer(customer_type="B2B", credit_limit=500)
		frappe.set_user(cashier.name)

		self.assertTrue(frappe.has_permission("Ledgix Item", ptype="read"))
		self.assertFalse(frappe.has_permission("Ledgix Item", ptype="write"))
		self.assertTrue(frappe.has_permission("Ledgix Customer", ptype="create"))
		self.assertFalse(frappe.has_permission("Ledgix Sale", ptype="create"))
		with self.assertRaises(frappe.PermissionError):
			get_customer_credit(customer.name)

	def test_manager_can_use_b2b_api_but_not_directly_create_sales(self):
		manager = make_user_with_roles("Ledgix Manager")
		customer = make_customer(customer_type="B2B", credit_limit=500)
		frappe.set_user(manager.name)

		credit = get_customer_credit(customer.name)
		self.assertEqual(credit["customer"], customer.name)
		self.assertTrue(frappe.has_permission("Ledgix Sale", ptype="read"))
		self.assertFalse(frappe.has_permission("Ledgix Sale", ptype="create"))
		self.assertTrue(frappe.has_permission("Ledgix Purchase", ptype="create"))

	def test_v2_pricing_and_payment_permissions_share_main_role_contract(self):
		cashier = make_user_with_roles("Ledgix Cashier")
		frappe.set_user(cashier.name)
		self.assertTrue(frappe.has_permission("Ledgix Price List", ptype="read"))
		self.assertFalse(frappe.has_permission("Ledgix Price List", ptype="write"))
		self.assertTrue(frappe.has_permission("Ledgix Payment Method", ptype="read"))
		self.assertFalse(frappe.has_permission("Ledgix Payment", ptype="create"))

		manager = make_user_with_roles("Ledgix Manager")
		frappe.set_user(manager.name)
		self.assertTrue(frappe.has_permission("Ledgix Price List", ptype="create"))
		self.assertFalse(frappe.has_permission("Ledgix Payment Method", ptype="write"))
		self.assertTrue(frappe.has_permission("Ledgix Payment", ptype="read"))
		self.assertFalse(frappe.has_permission("Ledgix Payment", ptype="create"))

		admin = make_user_with_roles("Ledgix Admin")
		frappe.set_user(admin.name)
		self.assertTrue(frappe.has_permission("Ledgix Payment", ptype="create"))
		self.assertTrue(frappe.has_permission("Ledgix Payment", ptype="submit"))
		self.assertFalse(frappe.has_permission("Ledgix Payment", ptype="cancel"))

	def test_page_and_workspace_roles_match_v2_navigation_contract(self):
		def roles_for(parent, parenttype):
			return set(frappe.get_all(
				"Has Role",
				filters={"parent": parent, "parenttype": parenttype},
				pluck="role",
			))

		self.assertEqual(
			roles_for("ledgix-pos", "Page"),
			{"System Manager", "Ledgix Admin", "Ledgix Manager", "Ledgix Cashier"},
		)
		for page in ("ledgix-tax-center", "business-intelligence-center"):
			self.assertEqual(
				roles_for(page, "Page"),
				{"System Manager", "Ledgix Admin", "Ledgix Manager"},
			)
		self.assertEqual(
			roles_for("Ledgix", "Workspace"),
			{"System Manager", "Ledgix Admin", "Ledgix Manager"},
		)

	def test_only_three_custom_ledgix_pages_remain(self):
		pages = set(frappe.get_all("Page", filters={"module": "Ledgix"}, pluck="name"))
		self.assertEqual(
			pages,
			{"ledgix-pos", "ledgix-tax-center", "business-intelligence-center"},
		)

	def test_workspace_shortcuts_resolve_to_real_frappe_targets(self):
		workspace = frappe.get_doc("Workspace", "Ledgix")
		self.assertTrue(workspace.shortcuts)
		for shortcut in workspace.shortcuts:
			target_type = shortcut.type
			target = shortcut.link_to
			if target_type == "DocType":
				exists = frappe.db.exists("DocType", target)
			elif target_type == "Page":
				exists = frappe.db.exists("Page", target)
			elif target_type == "Report":
				exists = frappe.db.exists("Report", target)
			else:
				self.fail(f"Unsupported Workspace shortcut type {target_type}: {target}")
			self.assertTrue(exists, f"Workspace shortcut target is missing: {target_type} {target}")

	def test_role_home_pages_route_cashier_to_pos_and_management_to_workspace(self):
		self.assertEqual(frappe.db.get_value("Role", "Ledgix Cashier", "home_page"), "ledgix-pos")
		self.assertEqual(frappe.db.get_value("Role", "Ledgix Manager", "home_page"), "Ledgix")
		self.assertEqual(frappe.db.get_value("Role", "Ledgix Admin", "home_page"), "Ledgix")

	def test_retired_product_settings_maintenance_and_role_are_absent(self):
		for doctype in (
			"Ledgix Mode Settings",
			"Ledgix POS Theme Settings",
			"Ledgix Maintenance Tool",
		):
			self.assertFalse(frappe.db.exists("DocType", doctype))
		self.assertFalse(frappe.db.exists("Role", "Ledgix Super Admin"))

		workspace = frappe.get_doc("Workspace", "Ledgix")
		labels = {row.label for row in workspace.shortcuts}
		self.assertNotIn("POS Settings", labels)
		self.assertNotIn("Maintenance Tool", labels)
		self.assertIn("Brand Settings", labels)

	def test_stock_movement_is_a_read_only_business_ledger(self):
		admin = make_user_with_roles("Ledgix Admin")
		frappe.set_user(admin.name)
		self.assertTrue(frappe.has_permission("Ledgix Stock Movement", ptype="read"))
		self.assertTrue(frappe.has_permission("Ledgix Stock Movement", ptype="report"))
		self.assertFalse(frappe.has_permission("Ledgix Stock Movement", ptype="create"))
		self.assertFalse(frappe.has_permission("Ledgix Stock Movement", ptype="write"))
		self.assertFalse(frappe.has_permission("Ledgix Stock Movement", ptype="cancel"))
