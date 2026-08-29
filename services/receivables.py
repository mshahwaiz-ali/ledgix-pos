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


def get_customer_receivables(customer, as_of=None):
	if not frappe.db.exists("Ledgix Customer", customer):
		frappe.throw(f"Customer not found: {customer}")

	as_of = getdate(as_of or today())
	sales = _submitted_sales(customer)
	returns = _return_credits(customer)
	payments = _payment_allocations([row.name for row in sales])

	outstanding = 0.0
	overdue = 0.0
	oldest_due_date = None
	invoice_rows = []
	for sale in sales:
		gross = flt(sale.grand_total or sale.total_amount)
		balance = max(gross - returns[sale.name] - payments[sale.name], 0)
		due_date = getdate(sale.due_date) if sale.due_date else getdate(sale.sale_date)
		outstanding += balance
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
			"due_date": due_date,
		})

	credit_limit = flt(frappe.db.get_value("Ledgix Customer", customer, "credit_limit"))
	return {
		"customer": customer,
		"credit_limit": credit_limit,
		"outstanding": outstanding,
		"available_credit": max(credit_limit - outstanding, 0),
		"overdue": overdue,
		"oldest_due_date": oldest_due_date,
		"invoices": invoice_rows,
	}


def refresh_customer_credit_summary(customer):
	result = get_customer_receivables(customer)
	values = {
		"outstanding_amount": result["outstanding"],
		"available_credit": result["available_credit"],
		"overdue_amount": result["overdue"],
		"oldest_due_date": result["oldest_due_date"],
	}
	meta = frappe.get_meta("Ledgix Customer")
	values = {key: value for key, value in values.items() if meta.has_field(key)}
	if values:
		frappe.db.set_value("Ledgix Customer", customer, values, update_modified=False)
	return result
