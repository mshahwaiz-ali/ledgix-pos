import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix.doctype.v2_test_utils import (
	configure_v2_test_environment,
	ensure_cash_payment_method,
	make_customer,
	make_item,
	make_sale,
	unique_name,
)
from ledgix.report.ledgix_customer_statement.ledgix_customer_statement import get_data as get_statement_data
from ledgix_saas.services.payments import post_payment, reverse_payment
from ledgix_saas.services.receivables import get_customer_receivables


def make_payment_method(*, method_type="Card", enabled=1, requires_reference=0, allow_change=0):
	name = unique_name("PAY-METHOD")
	doc = frappe.get_doc({
		"doctype": "Ledgix Payment Method",
		"payment_method_name": name,
		"method_type": method_type,
		"enabled": enabled,
		"requires_reference": requires_reference,
		"allow_change": allow_change,
		"sort_order": 50,
	})
	doc.insert(ignore_permissions=True)
	return doc


class TestLedgixPayment(FrappeTestCase):
	def setUp(self):
		super().setUp()
		configure_v2_test_environment()
		ensure_cash_payment_method()

	def test_disabled_payment_method_is_rejected(self):
		method = make_payment_method(enabled=0)
		payment = frappe.new_doc("Ledgix Payment")
		payment.payment_method = method.name
		payment.amount = 25
		payment.amount_tendered = 25

		with self.assertRaises(frappe.ValidationError):
			payment.validate()

	def test_required_payment_reference_is_enforced(self):
		method = make_payment_method(requires_reference=1)
		payment = frappe.new_doc("Ledgix Payment")
		payment.payment_method = method.name
		payment.amount = 25
		payment.amount_tendered = 25

		with self.assertRaises(frappe.ValidationError):
			payment.validate()

	def test_non_cash_payment_method_cannot_return_change(self):
		method = make_payment_method(method_type="Card", allow_change=0)
		payment = frappe.new_doc("Ledgix Payment")
		payment.payment_method = method.name
		payment.amount = 100
		payment.amount_tendered = 120

		with self.assertRaises(frappe.ValidationError):
			payment.validate()

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
		item = make_item(selling_price=200)
		customer = make_customer(customer_type="B2B", credit_limit=500)
		sale = make_sale(customer.name, item.name, rate=200, sale_channel="B2B", submit=True)

		payment = frappe.new_doc("Ledgix Payment")
		payment.customer = customer.name
		payment.payment_method = "Cash"
		payment.amount = 100
		payment.amount_tendered = 100
		payment.append("allocations", {
			"reference_doctype": "Ledgix Sale",
			"reference_name": sale.name,
			"allocated_amount": 100.01,
		})

		with self.assertRaises(frappe.ValidationError):
			payment.validate()

	def test_allocation_cannot_exceed_invoice_outstanding(self):
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="B2B", credit_limit=500)
		sale = make_sale(customer.name, item.name, rate=100, sale_channel="B2B", submit=True)

		with self.assertRaises(frappe.ValidationError):
			post_payment(
				customer=customer.name,
				payment_method="Cash",
				amount=120,
				allocations=[{
					"reference_doctype": "Ledgix Sale",
					"reference_name": sale.name,
					"allocated_amount": 120,
				}],
			)

	def test_payment_allocation_reference_is_limited_to_sales(self):
		payment = frappe.new_doc("Ledgix Payment")
		payment.payment_method = "Cash"
		payment.amount = 10
		payment.amount_tendered = 10
		payment.append("allocations", {
			"reference_doctype": "Ledgix Customer",
			"reference_name": "Customer",
			"allocated_amount": 10,
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

	def test_cash_change_is_not_customer_credit(self):
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="B2B", credit_limit=500)
		sale = make_sale(customer.name, item.name, rate=100, sale_channel="B2B", submit=True)

		payment = post_payment(
			customer=customer.name,
			payment_method="Cash",
			amount=100,
			amount_tendered=120,
			allocations=[{
				"reference_doctype": "Ledgix Sale",
				"reference_name": sale.name,
				"allocated_amount": 100,
			}],
		)
		self.assertAlmostEqual(payment.change_amount, 20, places=2)
		self.assertAlmostEqual(payment.unallocated_amount, 0, places=2)
		credit = get_customer_receivables(customer.name)
		self.assertAlmostEqual(credit["unallocated_credit"], 0, places=2)
		self.assertAlmostEqual(credit["credit_balance"], 0, places=2)

	def test_unallocated_payment_credit_updates_exposure_and_statement(self):
		item = make_item(selling_price=100)
		customer = make_customer(customer_type="B2B", credit_limit=500)
		sale = make_sale(customer.name, item.name, rate=100, sale_channel="B2B", submit=True)

		payment = post_payment(
			customer=customer.name,
			payment_method="Cash",
			amount=150,
			amount_tendered=150,
			allocations=[{
				"reference_doctype": "Ledgix Sale",
				"reference_name": sale.name,
				"allocated_amount": 100,
			}],
		)
		self.assertAlmostEqual(payment.unallocated_amount, 50, places=2)

		credit = get_customer_receivables(customer.name)
		self.assertAlmostEqual(credit["outstanding"], 0, places=2)
		self.assertAlmostEqual(credit["unallocated_credit"], 50, places=2)
		self.assertAlmostEqual(credit["net_balance"], -50, places=2)
		self.assertAlmostEqual(credit["credit_balance"], 50, places=2)
		self.assertAlmostEqual(credit["available_credit"], 550, places=2)

		customer.reload()
		self.assertAlmostEqual(customer.unallocated_credit, 50, places=2)
		self.assertAlmostEqual(customer.credit_balance, 50, places=2)
		self.assertAlmostEqual(customer.available_credit, 550, places=2)

		statement = get_statement_data({"customer": customer.name})
		self.assertAlmostEqual(statement[-1]["balance"], -50, places=2)

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
