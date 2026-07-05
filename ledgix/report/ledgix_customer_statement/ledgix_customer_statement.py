# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}

	columns = get_columns()

	if not filters.get("customer"):
		message = """
			<div style="padding: 20px; text-align: center; color: #667085;">
				Please select a customer to view statement.
			</div>
		"""
		return columns, [], message, None, []

	data = get_data(filters)
	summary = get_report_summary(data)

	message = None
	if not data:
		message = """
			<div style="padding: 20px; text-align: center; color: #667085;">
				No customer statement data found for selected filters.
			</div>
		"""

	return columns, data, message, None, summary


def get_columns():
	return [
		{"label": "Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 105},
		{"label": "Type", "fieldname": "reference_doctype", "fieldtype": "Data", "width": 155},
		{"label": "Reference", "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 145},
		{"label": "Invoice No", "fieldname": "invoice_number", "fieldtype": "Data", "width": 125},
		{"label": "Payment Status", "fieldname": "payment_status", "fieldtype": "Data", "width": 125},
		{"label": "Details", "fieldname": "details", "fieldtype": "Data", "width": 220},
		{"label": "Debit", "fieldname": "debit", "fieldtype": "Currency", "width": 120},
		{"label": "Credit", "fieldname": "credit", "fieldtype": "Currency", "width": 120},
		{"label": "Balance", "fieldname": "balance", "fieldtype": "Currency", "width": 125},
		{"label": "Open", "fieldname": "open_action", "fieldtype": "HTML", "width": 60},
	]


def get_data(filters):
	opening_balance = get_opening_balance(filters)
	transactions = get_transactions(filters)

	data = []
	running_balance = opening_balance

	if opening_balance:
		data.append({
			"posting_date": filters.get("from_date"),
			"reference_doctype": "Opening Balance",
			"reference_name": "",
			"invoice_number": "",
			"payment_status": "",
			"details": "Balance before selected period",
			"debit": opening_balance if opening_balance > 0 else 0,
			"credit": abs(opening_balance) if opening_balance < 0 else 0,
			"balance": opening_balance,
			"open_action": "",
			"is_opening": 1,
		})

	for row in transactions:
		debit = flt(row.get("debit"))
		credit = flt(row.get("credit"))
		running_balance += debit - credit

		row["balance"] = running_balance
		row["open_action"] = row.get("reference_name")
		data.append(row)

	return data


def get_transactions(filters):
	conditions = get_date_conditions(filters)

	sales = frappe.db.sql(
		f"""
		SELECT
			s.sale_date AS posting_date,
			'Ledgix Sale' AS reference_doctype,
			s.name AS reference_name,
			s.invoice_number,
			s.payment_status,
			CONCAT('Sale invoice - ', IFNULL(s.status, 'Submitted')) AS details,
			IFNULL(s.total_amount, 0) AS debit,
			IFNULL(s.paid_amount, 0) AS credit,
			s.creation AS sort_time
		FROM `tabLedgix Sale` s
		WHERE s.docstatus = 1
			AND s.customer = %(customer)s
			{conditions}
		""",
		filters,
		as_dict=True,
	)

	returns = frappe.db.sql(
		f"""
		SELECT
			DATE(sr.creation) AS posting_date,
			'Ledgix Sales Return' AS reference_doctype,
			sr.name AS reference_name,
			'' AS invoice_number,
			'' AS payment_status,
			CONCAT('Sales return against ', IFNULL(sr.original_sale, '-')) AS details,
			0 AS debit,
			IFNULL(sr.total_amount, 0) AS credit,
			sr.creation AS sort_time
		FROM `tabLedgix Sales Return` sr
		LEFT JOIN `tabLedgix Sale` s
			ON s.name = sr.original_sale
		WHERE sr.docstatus = 1
			AND (
				s.customer = %(customer)s
				OR sr.customer = %(customer)s
			)
			{conditions.replace("s.sale_date", "DATE(sr.creation)")}
		""",
		filters,
		as_dict=True,
	)

	rows = sales + returns
	rows.sort(key=lambda row: (row.get("posting_date") or "", row.get("sort_time") or "", row.get("reference_name") or ""))

	return rows


def get_opening_balance(filters):
	if not filters.get("from_date"):
		return 0

	sale_opening = frappe.db.sql(
		"""
		SELECT
			IFNULL(SUM(IFNULL(total_amount, 0)), 0) AS debit,
			IFNULL(SUM(IFNULL(paid_amount, 0)), 0) AS credit
		FROM `tabLedgix Sale`
		WHERE docstatus = 1
			AND customer = %(customer)s
			AND sale_date < %(from_date)s
		""",
		filters,
		as_dict=True,
	)[0]

	return_opening = frappe.db.sql(
		"""
		SELECT
			IFNULL(SUM(IFNULL(sr.total_amount, 0)), 0) AS credit
		FROM `tabLedgix Sales Return` sr
		LEFT JOIN `tabLedgix Sale` s
			ON s.name = sr.original_sale
		WHERE sr.docstatus = 1
			AND (
				s.customer = %(customer)s
				OR sr.customer = %(customer)s
			)
			AND DATE(sr.creation) < %(from_date)s
		""",
		filters,
		as_dict=True,
	)[0]

	return flt(sale_opening.get("debit")) - flt(sale_opening.get("credit")) - flt(return_opening.get("credit"))


def get_date_conditions(filters):
	conditions = []

	if filters.get("from_date"):
		conditions.append("AND s.sale_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("AND s.sale_date <= %(to_date)s")

	return "\n".join(conditions)


def get_report_summary(data):
	transaction_rows = [row for row in data if not row.get("is_opening")]

	total_debit = sum(row.get("debit") or 0 for row in transaction_rows)
	total_credit = sum(row.get("credit") or 0 for row in transaction_rows)
	closing_balance = data[-1].get("balance") if data else 0

	return [
		{"value": len(transaction_rows), "label": "Transactions", "datatype": "Int"},
		{"value": total_debit, "label": "Debit", "datatype": "Currency"},
		{"value": total_credit, "label": "Credit", "datatype": "Currency"},
		{"value": closing_balance, "label": "Closing Balance", "datatype": "Currency"},
	]
