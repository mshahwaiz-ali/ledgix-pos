# Copyright (c) 2026, Ali and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	make_customer,
	make_item,
	make_sale,
	make_sales_return,
)
from ledgix_saas.api.v2_returns import create_pos_v2_return, get_pos_v2_return_context
from ledgix_saas.services.receivables import get_customer_receivables


class TestLedgixSalesReturn(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def _make_stock_sale(self):
		item = make_item(selling_price=100, cost_price=40, opening_stock=5)
		customer = make_customer(customer_type="B2B", credit_limit=1000)
		sale = make_sale(
			customer.name,
			item.name,
			quantity=2,
			rate=100,
			sale_channel="B2B",
			submit=True,
		)
		return item, customer, sale

	def test_return_requires_reason(self):
		_item, _customer, sale = self._make_stock_sale()
		doc = frappe.new_doc("Ledgix Sales Return")
		doc.original_sale = sale.name
		doc.return_reason = ""
		doc.append("items", {
			"item": sale.items[0].item,
			"original_sale_item_row": sale.items[0].name,
			"quantity": 1,
		})

		with self.assertRaises(frappe.ValidationError):
			doc.validate()

	def test_return_derives_customer_financials_and_stock_from_original_sale(self):
		item, customer, sale = self._make_stock_sale()
		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 3)

		return_doc = make_sales_return(
			sale,
			quantity=1,
			include_row_reference=False,
			submit=True,
		)

		self.assertEqual(return_doc.customer, customer.name)
		self.assertEqual(return_doc.items[0].original_sale_item_row, sale.items[0].name)
		self.assertAlmostEqual(return_doc.items[0].rate, 100, places=2)
		self.assertAlmostEqual(return_doc.items[0].cost_price, 40, places=2)
		self.assertAlmostEqual(return_doc.total_amount, 100, places=2)
		self.assertAlmostEqual(return_doc.grand_total, 100, places=2)
		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 4)

		credit = get_customer_receivables(customer.name)
		self.assertAlmostEqual(credit["outstanding"], 100, places=2)

	def test_pos_return_contract_preserves_reason_and_exact_sale_row(self):
		_item, _customer, sale = self._make_stock_sale()
		context = get_pos_v2_return_context(sale.name)
		self.assertEqual(context["sale_id"], sale.name)
		self.assertEqual(len(context["items"]), 1)
		row = context["items"][0]
		self.assertEqual(row["original_sale_item_row"], sale.items[0].name)

		result = create_pos_v2_return(
			original_sale=sale.name,
			return_items=[{
				"item": row["item"],
				"original_sale_item_row": row["original_sale_item_row"],
				"qty": 1,
			}],
			reason="Damaged item",
		)
		return_doc = frappe.get_doc("Ledgix Sales Return", result["return_id"])
		self.assertEqual(return_doc.return_reason, "Damaged item")
		self.assertEqual(return_doc.items[0].original_sale_item_row, sale.items[0].name)
		self.assertEqual(return_doc.customer, sale.customer)
		self.assertAlmostEqual(return_doc.grand_total, 100, places=2)

	def test_return_cannot_exceed_remaining_original_quantity(self):
		_item, _customer, sale = self._make_stock_sale()
		make_sales_return(sale, quantity=1, include_row_reference=False, submit=True)

		with self.assertRaises(frappe.ValidationError):
			make_sales_return(sale, quantity=2, include_row_reference=False, submit=False)

	def test_return_cancel_restores_stock_and_receivable(self):
		item, customer, sale = self._make_stock_sale()
		return_doc = make_sales_return(sale, quantity=1, include_row_reference=True, submit=True)

		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 4)
		self.assertAlmostEqual(get_customer_receivables(customer.name)["outstanding"], 100, places=2)

		return_doc.cancel()

		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 3)
		self.assertAlmostEqual(get_customer_receivables(customer.name)["outstanding"], 200, places=2)
		self.assertEqual(
			frappe.db.count(
				"Ledgix Stock Movement",
				filters={"reference_doctype": "Ledgix Sales Return", "reference_name": return_doc.name, "docstatus": 2},
			),
			1,
		)
