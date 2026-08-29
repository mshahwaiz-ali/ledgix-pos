from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import flt, getdate, today


def _submitted_sales(customer):
	return frappe.get_all(
		"Ledgix Sale",
		filters={"customer": customer, "docstatus": 1},
		fields=["name", "grand_total", "total_amount", "due_date", "sale_date"],
		order_by="sale_date asc, creation asc",
	)


def _return_credits(customer):
	rows = frappe.get_all(
		"Ledgix Sales Return",
		filters={"customer": customer, "docstatus": 1},
		fields=["original_sale", "grand_total", "total_amount"],
	)
	credits = defaultdict(float)
	for row in rows:
		credits[row.original_sale] += flt(row.grand_total or row.total_amount)
	return credits


def _payment_allocations(sale_names):
	if not sale_names or not frappe.db.exists("DocType", "Ledgix Payment"):
		return defaultdict(float)
	rows = frappe.get_all(
		"Ledgix Payment Allocation",
		filters={"reference_doctype": "Ledgix Sale", "reference_name": ["in", sale_names]},
		fields=["parent", "reference_name", "allocated_amount"],
	)
	if not rows:
		return defaultdict(float)
	payment_names = list({row.parent for row in rows})
	payments = {
		row.name: row
		for row in frappe.get_all(
			"Ledgix Payment",
			filters={"name": ["in", payment_names], "docstatus": 1},
			fields=["name", "reversal_of"],
		)
	}
	allocated = defaultdict(float)
	for row in rows:
		payment = payments.get(row.parent)
		if not payment:
			continue
		sign = -1 if payment.reversal_of else 1
		allocated[row.reference_name] += sign * flt(row.allocated_amount)
	return allocated


def _unallocated_payment_credit(customer):
	"""Return net unapplied customer cash from posted payments and reversals."""
	if not frappe.db.exists("DocType", "Ledgix Payment"):
		return 0.0

	rows = frappe.get_all(
		"Ledgix Payment",
		filters={"customer": customer, "docstatus": 1},
		fields=["amount", "allocated_amount", "reversal_of"],
	)
	credit = 0.0
	for row in rows:
		unallocated = max(flt(row.amount) - flt(row.allocated_amount), 0)
		sign = -1 if row.reversal_of else 1
		credit += sign * unallocated
	return max(flt(credit), 0)


def get_customer_receivables(customer, as_of=None):
	if not frappe.db.exists("Ledgix Customer", customer):
		frappe.throw(f"Customer not found: {customer}")

	as_of = getdate(as_of or today())
	sales = _submitted_sales(customer)
	returns = _return_credits(customer)
	payments = _payment_allocations([row.name for row in sales])

	outstanding = 0.0
	invoice_credit = 0.0
	overdue = 0.0
	oldest_due_date = None
	invoice_rows = []
	for sale in sales:
		gross = flt(sale.grand_total or sale.total_amount)
		net_invoice_balance = flt(gross - returns[sale.name] - payments[sale.name], 2)
		balance = max(net_invoice_balance, 0)
		credit = max(-net_invoice_balance, 0)
		due_date = getdate(sale.due_date) if sale.due_date else getdate(sale.sale_date)
		outstanding += balance
		invoice_credit += credit
		if balance > 0 and due_date < as_of:
			overdue += balance
			if oldest_due_date is None or due_date < oldest_due_date:
				oldest_due_date = due_date
		invoice_rows.append({
			"sale": sale.name,
			"gross": gross,
			"returns": returns[sale.name],
			"payments": payments[sale.name],
			"outstanding": balance,
			"credit": credit,
			"net_balance": net_invoice_balance,
			"due_date": due_date,
		})

	unallocated_credit = _unallocated_payment_credit(customer)
	total_credit = flt(invoice_credit + unallocated_credit, 2)
	net_balance = flt(outstanding - total_credit, 2)
	credit_balance = max(-net_balance, 0)
	credit_limit = flt(frappe.db.get_value("Ledgix Customer", customer, "credit_limit"))
	return {
		"customer": customer,
		"credit_limit": credit_limit,
		"outstanding": flt(outstanding, 2),
		"invoice_credit": flt(invoice_credit, 2),
		"unallocated_credit": flt(unallocated_credit, 2),
		"net_balance": net_balance,
		"credit_balance": flt(credit_balance, 2),
		"available_credit": max(flt(credit_limit - net_balance, 2), 0),
		"overdue": flt(overdue, 2),
		"oldest_due_date": oldest_due_date,
		"invoices": invoice_rows,
	}


def refresh_customer_credit_summary(customer):
	result = get_customer_receivables(customer)
	values = {
		"outstanding_amount": result["outstanding"],
		"unallocated_credit": result["unallocated_credit"],
		"credit_balance": result["credit_balance"],
		"available_credit": result["available_credit"],
		"overdue_amount": result["overdue"],
		"oldest_due_date": result["oldest_due_date"],
	}
	meta = frappe.get_meta("Ledgix Customer")
	values = {key: value for key, value in values.items() if meta.has_field(key)}
	if values:
		frappe.db.set_value("Ledgix Customer", customer, values, update_modified=False)
	return result
