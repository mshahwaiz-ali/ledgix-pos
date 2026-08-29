from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from ledgix_saas.services.receivables import refresh_customer_credit_summary


def _validate_allocation_customer(customer, allocation):
	if allocation.get("reference_doctype") != "Ledgix Sale":
		return
	sale_customer = frappe.db.get_value("Ledgix Sale", allocation.get("reference_name"), "customer")
	if not sale_customer:
		frappe.throw(_("Sale not found for payment allocation."))
	if customer and sale_customer != customer:
		frappe.throw(_("Payment cannot be allocated across different customers."))


def post_payment(
	*,
	customer=None,
	payment_method,
	amount,
	allocations=None,
	reference_number=None,
	pos_shift=None,
	amount_tendered=None,
	currency="PKR",
):
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Payment amount must be greater than zero."))
	if not frappe.db.exists("Ledgix Payment Method", payment_method):
		frappe.throw(_("Unknown payment method: {0}").format(payment_method))

	allocations = allocations or []
	for allocation in allocations:
		_validate_allocation_customer(customer, allocation)

	payment = frappe.new_doc("Ledgix Payment")
	payment.payment_date = now_datetime()
	payment.customer = customer
	payment.payment_method = payment_method
	payment.amount = amount
	payment.amount_tendered = flt(amount_tendered) if amount_tendered is not None else amount
	payment.currency = currency or "PKR"
	payment.reference_number = reference_number or ""
	payment.cashier = frappe.session.user
	payment.pos_shift = pos_shift
	for allocation in allocations:
		payment.append("allocations", {
			"reference_doctype": allocation.get("reference_doctype") or "Ledgix Sale",
			"reference_name": allocation.get("reference_name"),
			"allocated_amount": flt(allocation.get("allocated_amount")),
			"remarks": allocation.get("remarks") or "",
		})
	payment.insert(ignore_permissions=True)
	payment.submit()
	if customer:
		refresh_customer_credit_summary(customer)
	return payment


def reverse_payment(payment_name, reason):
	if not (reason or "").strip():
		frappe.throw(_("Reversal reason is required."))
	original = frappe.get_doc("Ledgix Payment", payment_name)
	if original.docstatus != 1:
		frappe.throw(_("Only posted payments can be reversed."))
	if original.reversal_of:
		frappe.throw(_("A reversal payment cannot be reversed through this action."))
	if original.status == "Reversed":
		frappe.throw(_("Payment is already reversed."))

	reversal = frappe.new_doc("Ledgix Payment")
	reversal.payment_date = now_datetime()
	reversal.customer = original.customer
	reversal.payment_method = original.payment_method
	reversal.amount = original.amount
	reversal.amount_tendered = original.amount
	reversal.currency = original.currency
	reversal.reference_number = original.reference_number
	reversal.cashier = frappe.session.user
	reversal.pos_shift = original.pos_shift
	reversal.reversal_of = original.name
	reversal.reversal_reason = reason.strip()
	for row in original.allocations:
		reversal.append("allocations", {
			"reference_doctype": row.reference_doctype,
			"reference_name": row.reference_name,
			"allocated_amount": row.allocated_amount,
			"remarks": f"Reversal of {original.name}",
		})
	reversal.insert(ignore_permissions=True)
	reversal.submit()
	original.db_set("status", "Reversed", update_modified=False)
	if original.customer:
		refresh_customer_credit_summary(original.customer)
	return reversal
