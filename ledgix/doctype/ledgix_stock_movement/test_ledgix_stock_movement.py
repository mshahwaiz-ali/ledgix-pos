# Copyright (c) 2026, Ali and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	make_customer,
	make_item,
	make_purchase,
	make_sale,
	make_sales_return,
	make_supplier,
)
from ledgix_saas.api.stock_ops import manual_stock_entry


class TestLedgixStockMovement(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def _item_values(self, item):
		return frappe.db.get_value(
			"Ledgix Item",
			item,
			["current_stock", "cost_price"],
			as_dict=True,
		)

	def test_purchase_moving_average_and_cancel_restore_opening_valuation(self):
		item = make_item(cost_price=40, opening_stock=10)
		supplier = make_supplier()
		purchase = make_purchase(supplier.name, item.name, quantity=10, rate=60, submit=True)

		values = self._item_values(item.name)
		self.assertAlmostEqual(values.current_stock, 20, places=6)
		self.assertAlmostEqual(values.cost_price, 50, places=6)

		movement = frappe.db.get_value(
			"Ledgix Stock Movement",
			{
				"reference_doctype": "Ledgix Purchase",
				"reference_name": purchase.name,
				"item": item.name,
				"docstatus": 1,
			},
			["quantity", "valuation_rate"],
			as_dict=True,
		)
		self.assertAlmostEqual(movement.quantity, 10, places=6)
		self.assertAlmostEqual(movement.valuation_rate, 60, places=6)

		purchase.cancel()
		values = self._item_values(item.name)
		self.assertAlmostEqual(values.current_stock, 10, places=6)
		self.assertAlmostEqual(values.cost_price, 40, places=6)

	def test_duplicate_purchase_item_lines_create_one_weighted_stock_movement(self):
		item = make_item(cost_price=40, opening_stock=10)
		supplier = make_supplier()
		purchase = make_purchase(supplier.name, item.name, quantity=2, rate=60, submit=False)
		purchase.append("items", {
			"item": item.name,
			"quantity": 3,
			"rate": 80,
			"unit": "Piece",
		})
		purchase.save(ignore_permissions=True)
		purchase.submit()

		movements = frappe.get_all(
			"Ledgix Stock Movement",
			filters={
				"reference_doctype": "Ledgix Purchase",
				"reference_name": purchase.name,
				"item": item.name,
				"docstatus": 1,
			},
			fields=["quantity", "valuation_rate"],
		)
		self.assertEqual(len(movements), 1)
		self.assertAlmostEqual(movements[0].quantity, 5, places=6)
		self.assertAlmostEqual(movements[0].valuation_rate, 72, places=6)
		values = self._item_values(item.name)
		self.assertAlmostEqual(values.current_stock, 15, places=6)
		self.assertAlmostEqual(values.cost_price, (10 * 40 + 5 * 72) / 15, places=6)

	def test_manual_adjustment_requires_reason_and_snapshots_current_valuation(self):
		item = make_item(cost_price=45, opening_stock=4)

		with self.assertRaises(frappe.ValidationError):
			manual_stock_entry(item.name, qty_in=2, note="")

		result = manual_stock_entry(item.name, qty_in=2, note="Cycle count correction")
		movement = frappe.get_doc("Ledgix Stock Movement", result["movements"][0])
		self.assertEqual(movement.movement_source, "Manual IN")
		self.assertIn("Cycle count correction", movement.reference_note)
		self.assertAlmostEqual(movement.valuation_rate, 45, places=6)
		self.assertAlmostEqual(self._item_values(item.name).current_stock, 6, places=6)

	def test_cancelling_earlier_sale_replays_later_purchase_valuation(self):
		item = make_item(cost_price=40, opening_stock=10)
		customer = make_customer(customer_type="B2B", credit_limit=5000)
		sale = make_sale(
			customer.name,
			item.name,
			quantity=10,
			rate=100,
			sale_channel="B2B",
			submit=True,
		)
		self.assertAlmostEqual(self._item_values(item.name).current_stock, 0, places=6)

		supplier = make_supplier()
		make_purchase(supplier.name, item.name, quantity=10, rate=60, submit=True)
		values = self._item_values(item.name)
		self.assertAlmostEqual(values.current_stock, 10, places=6)
		self.assertAlmostEqual(values.cost_price, 60, places=6)

		sale.cancel()
		values = self._item_values(item.name)
		self.assertAlmostEqual(values.current_stock, 20, places=6)
		self.assertAlmostEqual(values.cost_price, 50, places=6)

	def test_sales_return_uses_original_cost_snapshot_in_current_average(self):
		item = make_item(cost_price=40, opening_stock=10)
		customer = make_customer(customer_type="B2B", credit_limit=5000)
		sale = make_sale(
			customer.name,
			item.name,
			quantity=5,
			rate=100,
			sale_channel="B2B",
			submit=True,
		)
		supplier = make_supplier()
		make_purchase(supplier.name, item.name, quantity=5, rate=80, submit=True)
		self.assertAlmostEqual(self._item_values(item.name).cost_price, 60, places=6)

		return_doc = make_sales_return(sale, quantity=1, submit=True)
		movement = frappe.db.get_value(
			"Ledgix Stock Movement",
			{
				"reference_doctype": "Ledgix Sales Return",
				"reference_name": return_doc.name,
				"item": item.name,
				"docstatus": 1,
			},
			["valuation_rate", "quantity"],
			as_dict=True,
		)
		self.assertAlmostEqual(movement.valuation_rate, 40, places=6)
		self.assertAlmostEqual(movement.quantity, 1, places=6)
		values = self._item_values(item.name)
		self.assertAlmostEqual(values.current_stock, 11, places=6)
		self.assertAlmostEqual(values.cost_price, ((10 * 60) + 40) / 11, places=6)
