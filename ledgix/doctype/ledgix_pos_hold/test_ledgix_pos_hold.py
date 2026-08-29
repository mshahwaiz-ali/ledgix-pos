# Copyright (c) 2026, Ali and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	make_customer,
	make_item,
	make_price_list,
	make_user_with_roles,
)
from ledgix_saas.api.v2_holds import (
	get_pos_v2_holds,
	hold_pos_v2_sale,
	resume_pos_v2_hold,
)


class TestLedgixPOSHold(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def test_b2b_hold_preserves_customer_price_list_and_resumes_without_shift(self):
		price_list = make_price_list()
		item = make_item(selling_price=125, cost_price=50)
		customer = make_customer(
			customer_type="B2B",
			default_price_list=price_list.name,
			credit_limit=1000,
		)

		result = hold_pos_v2_sale(
			cart_items=[{"item": item.name, "qty": 2, "rate": 125}],
			sale_channel="B2B",
			customer=customer.name,
			price_list=price_list.name,
			discount_type="Amount",
			discount_value=10,
		)
		hold = frappe.get_doc("Ledgix POS Hold", result["hold_id"])
		self.assertEqual(hold.sale_channel, "B2B")
		self.assertEqual(hold.customer, customer.name)
		self.assertEqual(hold.price_list, price_list.name)
		self.assertFalse(hold.shift)
		self.assertAlmostEqual(hold.total, 240, places=2)

		listed = get_pos_v2_holds()["holds"]
		self.assertTrue(any(row.name == hold.name for row in listed))

		resumed = resume_pos_v2_hold(hold.name)
		self.assertEqual(resumed["sale_channel"], "B2B")
		self.assertEqual(resumed["customer"], customer.name)
		self.assertEqual(resumed["price_list"], price_list.name)
		self.assertEqual(len(resumed["cart_items"]), 1)
		self.assertAlmostEqual(resumed["cart_items"][0]["qty"], 2, places=6)
		self.assertEqual(frappe.db.get_value("Ledgix POS Hold", hold.name, "status"), "Resumed")

		with self.assertRaises(frappe.ValidationError):
			resume_pos_v2_hold(hold.name)

	def test_retail_hold_requires_open_shift(self):
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="Retail", credit_limit=0)
		cashier = make_user_with_roles("Ledgix Cashier")

		frappe.set_user(cashier.name)
		try:
			self.assertFalse(
				frappe.db.exists(
					"Ledgix POS Shift",
					{"opened_by": cashier.name, "status": "Open", "docstatus": 0},
				)
			)
			with self.assertRaises(frappe.ValidationError):
				hold_pos_v2_sale(
					cart_items=[{"item": item.name, "qty": 1, "rate": 100}],
					sale_channel="Retail",
					customer=customer.name,
				)
		finally:
			frappe.set_user("Administrator")
