from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from ledgix_saas.services.payments import post_payment, reverse_payment
from ledgix_saas.services.receivables import get_customer_receivables, refresh_customer_credit_summary


def _require_manager():
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection({"System Manager", "Ledgix Admin", "Ledgix Manager"}):
		frappe.throw(_("Manager or Admin access is required."), frappe.PermissionError)


def _require_admin():
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection({"System Manager", "Ledgix Admin"}):
		frappe.throw(_("Admin access is required."), frappe.PermissionError)


def _parse(value):
	return frappe.parse_json(value) if isinstance(value, str) else value


@frappe.whitelist()
def get_customer_credit(customer):
	_require_manager()
	return get_customer_receivables(customer)


@frappe.whitelist()
def refresh_customer_credit(customer):
	_require_manager()
	return refresh_customer_credit_summary(customer)


@frappe.whitelist()
def get_customer_open_invoices(customer):
	_require_manager()
	result = get_customer_receivables(customer)
	result["invoices"] = [row for row in result.get("invoices", []) if flt(row.get("outstanding")) > 0.005]
	return result


@frappe.whitelist()
def post_customer_payment(
	customer,
	payment_method,
	amount,
	allocations=None,
	reference_number=None,
	currency="PKR",
):
	_require_manager()
	allocations = _parse(allocations) or []
	if not allocations:
		credit = get_customer_receivables(customer)
		remaining = flt(amount)
		allocations = []
		for invoice in credit.get("invoices", []):
			if remaining <= 0:
				break
			outstanding = flt(invoice.get("outstanding"))
			if outstanding <= 0:
				continue
			allocated = min(remaining, outstanding)
			allocations.append({
				"reference_doctype": "Ledgix Sale",
				"reference_name": invoice["sale"],
				"allocated_amount": allocated,
			})
			remaining -= allocated

	payment = post_payment(
		customer=customer,
		payment_method=payment_method,
		amount=amount,
		allocations=allocations,
		reference_number=reference_number,
		currency=currency,
	)
	return {
		"payment": payment.name,
		"amount": flt(payment.amount),
		"allocated_amount": flt(payment.allocated_amount),
		"unallocated_amount": flt(payment.unallocated_amount),
		"credit": get_customer_receivables(customer),
	}


@frappe.whitelist()
def reverse_customer_payment(payment, reason):
	_require_admin()
	reversal = reverse_payment(payment, reason)
	return {
		"reversal": reversal.name,
		"original_payment": payment,
		"customer": reversal.customer,
		"credit": get_customer_receivables(reversal.customer) if reversal.customer else None,
	}
