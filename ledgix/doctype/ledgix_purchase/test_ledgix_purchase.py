# Copyright (c) 2026, Ali and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	make_item,
	make_purchase,
	make_supplier,
)
from ledgix_saas.services.stock import post_purchase_movements


class TestLedgixPurchase(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def test_purchase_submit_posts_stock_and_average_cost(self):
		item = make_item(cost_price=10, opening_stock=0)
		supplier = make_supplier()
		purchase = make_purchase(supplier.name, item.name, quantity=5, rate=20, submit=True)

		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 5)
		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "cost_price"), 20)
		movements = frappe.get_all(
			"Ledgix Stock Movement",
			filters={"reference_doctype": "Ledgix Purchase", "reference_name": purchase.name, "docstatus": 1},
			fields=["movement_type", "quantity"],
		)
		self.assertEqual(len(movements), 1)
		self.assertEqual(movements[0].movement_type, "IN")
		self.assertEqual(movements[0].quantity, 5)

	def test_purchase_stock_posting_is_idempotent(self):
		item = make_item(cost_price=10, opening_stock=0)
		supplier = make_supplier()
		purchase = make_purchase(supplier.name, item.name, quantity=3, rate=25, submit=True)

		post_purchase_movements(purchase)

		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 3)
		count = frappe.db.count(
			"Ledgix Stock Movement",
			filters={"reference_doctype": "Ledgix Purchase", "reference_name": purchase.name, "docstatus": 1},
		)
		self.assertEqual(count, 1)

	def test_purchase_cancel_reverses_stock_and_cost(self):
		item = make_item(cost_price=10, opening_stock=0)
		supplier = make_supplier()
		purchase = make_purchase(supplier.name, item.name, quantity=4, rate=30, submit=True)

		purchase.cancel()

		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 0)
		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "cost_price"), 0)
		self.assertEqual(
			frappe.db.count(
				"Ledgix Stock Movement",
				filters={"reference_doctype": "Ledgix Purchase", "reference_name": purchase.name, "docstatus": 2},
			),
			1,
		)
