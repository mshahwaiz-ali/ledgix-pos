# Copyright (c) 2026, Ali and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	make_customer,
	make_item,
	make_price_list,
	unique_name,
)
from ledgix_saas.api.shifts import close_pos_shift
from ledgix_saas.api.v2_pos import complete_pos_v2_sale
from ledgix_saas.services.payments import reverse_payment


class TestLedgixPOSShift(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def test_b2b_pos_checkout_is_idempotent_by_client_sale_id(self):
		price_list = make_price_list()
		item = make_item(selling_price=125, cost_price=50)
		customer = make_customer(
			customer_type="B2B",
			default_price_list=price_list.name,
			credit_limit=1000,
		)
		client_sale_id = unique_name("CLIENT-SALE")
		cart = [{"item": item.name, "qty": 1}]

		first = complete_pos_v2_sale(
			cart_items=cart,
			tenders=[],
			customer=customer.name,
			sale_channel="B2B",
			price_list=price_list.name,
			client_sale_id=client_sale_id,
		)
		second = complete_pos_v2_sale(
			cart_items=cart,
			tenders=[],
			customer=customer.name,
			sale_channel="B2B",
			price_list=price_list.name,
			client_sale_id=client_sale_id,
		)

		self.assertTrue(first["success"])
		self.assertTrue(second["success"])
		self.assertTrue(second["duplicate"])
		self.assertEqual(first["sale"], second["sale"])
		self.assertEqual(
			frappe.db.count("Ledgix Sale", filters={"client_sale_id": client_sale_id, "docstatus": 1}),
			1,
		)

	def test_retail_pos_api_requires_open_shift_before_sale_creation(self):
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="Retail", credit_limit=0)
		client_sale_id = unique_name("RETAIL-CLIENT")

		with patch("ledgix_saas.api.v2_pos._open_shift", return_value=None):
			with self.assertRaises(frappe.ValidationError):
				complete_pos_v2_sale(
					cart_items=[{"item": item.name, "qty": 1}],
					tenders=[],
					customer=customer.name,
					sale_channel="Retail",
					client_sale_id=client_sale_id,
				)

		self.assertFalse(frappe.db.exists("Ledgix Sale", {"client_sale_id": client_sale_id}))

	def test_shift_summary_uses_payment_ledger_and_cash_method_type(self):
		method_name = unique_name("TILL-CASH")
		frappe.get_doc({
			"doctype": "Ledgix Payment Method",
			"payment_method_name": method_name,
			"method_type": "Cash",
			"enabled": 1,
			"requires_reference": 0,
			"allow_change": 1,
			"sort_order": 5,
		}).insert(ignore_permissions=True)

		shift = frappe.get_doc({
			"doctype": "Ledgix POS Shift",
			"opening_cash": 50,
		})
		shift.insert(ignore_permissions=True)

		item = make_item(selling_price=100, cost_price=40)
		customer = make_customer(customer_type="Retail", credit_limit=0)
		sale = frappe.get_doc({
			"doctype": "Ledgix Sale",
			"customer": customer.name,
			"sale_channel": "Retail",
			"sale_date": today(),
			"pos_shift": shift.name,
		})
		sale.append("items", {
			"item": item.name,
			"quantity": 1,
			"list_rate": 100,
			"rate": 100,
			"cost_price": 40,
		})
		sale.append("payments", {
			"payment_method": method_name,
			"amount": 120,
		})
		sale.insert(ignore_permissions=True)
		sale.submit()
		sale.reload()

		self.assertAlmostEqual(sale.grand_total, 100, places=2)
		self.assertAlmostEqual(sale.paid_amount, 100, places=2)
		self.assertAlmostEqual(sale.change_amount, 20, places=2)
		self.assertEqual(sale.payment_status, "Paid")

		shift.reload()
		self.assertEqual(shift.invoice_count, 1)
		self.assertAlmostEqual(shift.total_sales, 100, places=2)
		self.assertAlmostEqual(shift.cash_sales, 100, places=2)
		self.assertAlmostEqual(shift.non_cash_sales, 0, places=2)
		self.assertAlmostEqual(shift.expected_cash, 150, places=2)

		payment_name = frappe.db.get_value(
			"Ledgix Payment",
			{"pos_shift": shift.name, "payment_method": method_name, "docstatus": 1, "reversal_of": ["is", "not set"]},
			"name",
		)
		self.assertTrue(payment_name)
		reverse_payment(payment_name, "Shift test reversal")

		shift.reload()
		self.assertAlmostEqual(shift.cash_sales, 0, places=2)
		self.assertAlmostEqual(shift.expected_cash, 50, places=2)
		self.assertAlmostEqual(shift.total_sales, 100, places=2)

		sale.reload()
		self.assertAlmostEqual(sale.paid_amount, 0, places=2)
		self.assertAlmostEqual(sale.remaining_amount, 100, places=2)
		self.assertEqual(sale.payment_status, "Unpaid")

	def test_close_shift_api_finalizes_submitted_shift(self):
		shift = frappe.get_doc({
			"doctype": "Ledgix POS Shift",
			"opening_cash": 125,
		})
		shift.insert(ignore_permissions=True)

		result = close_pos_shift(
			shift_name=shift.name,
			actual_cash=125,
			closing_notes="Till counted",
		)

		shift.reload()
		self.assertTrue(result["success"])
		self.assertEqual(shift.status, "Closed")
		self.assertEqual(shift.docstatus, 1)
		self.assertTrue(shift.closing_time)
		self.assertEqual(shift.closed_by, frappe.session.user)
		self.assertAlmostEqual(shift.expected_cash, 125, places=2)
		self.assertAlmostEqual(shift.actual_cash, 125, places=2)
		self.assertAlmostEqual(shift.cash_variance, 0, places=2)
