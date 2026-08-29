# Copyright (c) 2026, Ali and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	ensure_cash_payment_method,
	make_customer,
	make_item,
	make_price_list,
	make_sale,
	unique_name,
)
from ledgix_saas.services.receivables import get_customer_receivables


class TestLedgixSale(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()

	def test_b2b_sale_without_shift_captures_snapshot_and_receivable(self):
		b2b_price_list = make_price_list()
		item = make_item(selling_price=100, cost_price=35)
		customer = make_customer(
			customer_type="B2B",
			default_price_list=b2b_price_list.name,
			payment_terms_days=14,
			credit_limit=500,
		)

		sale = make_sale(
			customer.name,
			item.name,
			quantity=2,
			rate=100,
			sale_channel="B2B",
			submit=True,
		)

		self.assertEqual(sale.docstatus, 1)
		self.assertEqual(sale.sale_channel, "B2B")
		self.assertFalse(sale.pos_shift)
		self.assertEqual(sale.price_list, b2b_price_list.name)
		self.assertEqual(sale.payment_status, "Unpaid")
		self.assertAlmostEqual(sale.grand_total, 200, places=2)
		self.assertEqual(getdate(sale.due_date), add_days(getdate(today()), 14))
		self.assertEqual(sale.buyer_name_snapshot, customer.customer_name)
		self.assertEqual(sale.buyer_ntn_cnic_snapshot, "1234567-8")
		self.assertEqual(sale.buyer_strn_snapshot, "STRN-TEST")
		self.assertEqual(sale.buyer_province_snapshot, "Punjab")
		self.assertEqual(sale.buyer_address_snapshot, "Test Business Address")

		credit = get_customer_receivables(customer.name)
		self.assertAlmostEqual(credit["outstanding"], 200, places=2)
		self.assertAlmostEqual(credit["available_credit"], 300, places=2)

		frappe.db.set_value(
			"Ledgix Customer",
			customer.name,
			{
				"customer_name": customer.customer_name,
				"buyer_ntn_cnic": "7654321-0",
				"buyer_fbr_address": "Changed Address",
			},
			update_modified=False,
		)
		sale.reload()
		self.assertEqual(sale.buyer_ntn_cnic_snapshot, "1234567-8")
		self.assertEqual(sale.buyer_address_snapshot, "Test Business Address")

	def test_retail_sale_requires_open_shift(self):
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="Retail", credit_limit=0)

		with self.assertRaises(frappe.ValidationError):
			make_sale(
				customer.name,
				item.name,
				rate=100,
				sale_channel="Retail",
			)

	def test_b2b_credit_limit_is_enforced_server_side(self):
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="B2B", credit_limit=50)

		with self.assertRaises(frappe.ValidationError):
			make_sale(
				customer.name,
				item.name,
				rate=100,
				sale_channel="B2B",
			)

	def test_b2b_non_cash_overpayment_is_rejected(self):
		method_name = unique_name("CARD")
		frappe.get_doc({
			"doctype": "Ledgix Payment Method",
			"payment_method_name": method_name,
			"method_type": "Card",
			"enabled": 1,
			"requires_reference": 0,
			"allow_change": 0,
			"sort_order": 20,
		}).insert(ignore_permissions=True)
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="B2B", credit_limit=500)

		with self.assertRaises(frappe.ValidationError):
			make_sale(
				customer.name,
				item.name,
				rate=100,
				sale_channel="B2B",
				payments=[{"payment_method": method_name, "amount": 120}],
			)

	def test_legacy_tender_posts_authoritative_payment_allocation(self):
		ensure_cash_payment_method()
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="B2B", credit_limit=500)

		sale = make_sale(
			customer.name,
			item.name,
			rate=100,
			sale_channel="B2B",
			payments=[{"payment_method": "Cash", "amount": 40}],
			submit=True,
		)

		allocations = frappe.get_all(
			"Ledgix Payment Allocation",
			filters={
				"reference_doctype": "Ledgix Sale",
				"reference_name": sale.name,
			},
			fields=["parent", "allocated_amount"],
		)
		self.assertEqual(len(allocations), 1)
		self.assertAlmostEqual(allocations[0].allocated_amount, 40, places=2)

		payment = frappe.get_doc("Ledgix Payment", allocations[0].parent)
		self.assertEqual(payment.docstatus, 1)
		self.assertEqual(payment.status, "Posted")
		self.assertAlmostEqual(payment.amount, 40, places=2)
		self.assertAlmostEqual(payment.allocated_amount, 40, places=2)
		self.assertAlmostEqual(payment.unallocated_amount, 0, places=2)

		credit = get_customer_receivables(customer.name)
		self.assertAlmostEqual(credit["outstanding"], 60, places=2)
		self.assertAlmostEqual(credit["available_credit"], 440, places=2)

	def test_inventory_authoritative_sale_posts_and_cancels_stock_once(self):
		configure_v2_test_environment()
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

		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 3)
		self.assertEqual(
			frappe.db.count(
				"Ledgix Stock Movement",
				filters={"reference_doctype": "Ledgix Sale", "reference_name": sale.name, "docstatus": 1},
			),
			1,
		)

		sale.cancel()
		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 5)
		self.assertEqual(
			frappe.db.count(
				"Ledgix Stock Movement",
				filters={"reference_doctype": "Ledgix Sale", "reference_name": sale.name, "docstatus": 2},
			),
			1,
		)

	def test_sale_with_posted_payment_activity_cannot_be_cancelled(self):
		ensure_cash_payment_method()
		item = make_item(selling_price=100, cost_price=40, opening_stock=5)
		customer = make_customer(customer_type="B2B", credit_limit=500)

		sale = make_sale(
			customer.name,
			item.name,
			rate=100,
			sale_channel="B2B",
			payments=[{"payment_method": "Cash", "amount": 40}],
			submit=True,
		)
		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 4)

		with self.assertRaises(frappe.ValidationError):
			sale.cancel()

		sale.reload()
		self.assertEqual(sale.docstatus, 1)
		self.assertEqual(frappe.db.get_value("Ledgix Item", item.name, "current_stock"), 4)
		self.assertEqual(
			frappe.db.count(
				"Ledgix Payment Allocation",
				filters={"reference_doctype": "Ledgix Sale", "reference_name": sale.name},
			),
			1,
		)
