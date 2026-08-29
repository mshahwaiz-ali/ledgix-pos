import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	ensure_cash_payment_method,
	make_customer,
	make_item,
	make_sale,
)
from ledgix_saas.services.payments import post_payment, reverse_payment
from ledgix_saas.services.receivables import get_customer_receivables


class TestLedgixPayment(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()
		ensure_cash_payment_method()

	def test_allocation_amount_must_be_positive(self):
		payment = frappe.new_doc("Ledgix Payment")
		payment.payment_method = "Cash"
		payment.amount = 100
		payment.amount_tendered = 100
		payment.append("allocations", {
			"reference_doctype": "Ledgix Sale",
			"reference_name": "SAL-NOT-USED",
			"allocated_amount": -10,
		})

		with self.assertRaises(frappe.ValidationError):
			payment.validate()

	def test_allocations_cannot_exceed_payment_amount(self):
		payment = frappe.new_doc("Ledgix Payment")
		payment.payment_method = "Cash"
		payment.amount = 100
		payment.amount_tendered = 100
		payment.append("allocations", {
			"reference_doctype": "Ledgix Sale",
			"reference_name": "SAL-NOT-USED",
			"allocated_amount": 100.01,
		})

		with self.assertRaises(frappe.ValidationError):
			payment.validate()

	def test_amount_tendered_cannot_be_less_than_payment_amount(self):
		payment = frappe.new_doc("Ledgix Payment")
		payment.payment_method = "Cash"
		payment.amount = 100
		payment.amount_tendered = 90

		with self.assertRaises(frappe.ValidationError):
			payment.validate()

	def test_payment_and_reversal_update_customer_receivable(self):
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="B2B", credit_limit=500)
		sale = make_sale(
			customer.name,
			item.name,
			rate=100,
			sale_channel="B2B",
			submit=True,
		)

		payment = post_payment(
			customer=customer.name,
			payment_method="Cash",
			amount=35,
			allocations=[{
				"reference_doctype": "Ledgix Sale",
				"reference_name": sale.name,
				"allocated_amount": 35,
			}],
		)
		self.assertEqual(payment.docstatus, 1)
		self.assertEqual(payment.status, "Posted")
		self.assertAlmostEqual(get_customer_receivables(customer.name)["outstanding"], 65, places=2)

		reversal = reverse_payment(payment.name, "Test reversal")
		payment.reload()
		self.assertEqual(payment.status, "Reversed")
		self.assertEqual(reversal.docstatus, 1)
		self.assertEqual(reversal.reversal_of, payment.name)
		self.assertAlmostEqual(get_customer_receivables(customer.name)["outstanding"], 100, places=2)

	def test_payment_cannot_allocate_sale_from_another_customer(self):
		item = make_item(selling_price=100)
		customer_a = make_customer(customer_type="B2B", credit_limit=500)
		customer_b = make_customer(customer_type="B2B", credit_limit=500)
		sale = make_sale(
			customer_a.name,
			item.name,
			rate=100,
			sale_channel="B2B",
			submit=True,
		)

		with self.assertRaises(frappe.ValidationError):
			post_payment(
				customer=customer_b.name,
				payment_method="Cash",
				amount=25,
				allocations=[{
					"reference_doctype": "Ledgix Sale",
					"reference_name": sale.name,
					"allocated_amount": 25,
				}],
			)
