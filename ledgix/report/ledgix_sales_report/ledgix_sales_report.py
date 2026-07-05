# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)
	summary = get_report_summary(data)

	message = None
	if not data:
		message = """
			<div style="padding: 20px; text-align: center; color: #667085;">
				No sales data found for selected filters.
			</div>
		"""

	return columns, data, message, None, summary


def get_columns():
	return [
		{"label": "Sale ID", "fieldname": "sale", "fieldtype": "Link", "options": "Ledgix Sale", "width": 135},
		{"label": "Invoice No", "fieldname": "invoice_number", "fieldtype": "Data", "width": 130},
		{"label": "Date", "fieldname": "sale_date", "fieldtype": "Date", "width": 105},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Ledgix Customer", "width": 180},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 105},
		{"label": "Items", "fieldname": "items_count", "fieldtype": "Int", "width": 80},
		{"label": "Total Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 110},
		{"label": "Total Amount", "fieldname": "total_amount", "fieldtype": "Currency", "width": 135},
		{"label": "Total Profit", "fieldname": "total_profit", "fieldtype": "Currency", "width": 130},
		{"label": "Avg Sale Value", "fieldname": "avg_sale_value", "fieldtype": "Currency", "width": 135},
		{"label": "View", "fieldname": "view_action", "fieldtype": "HTML", "width": 60},
		{"label": "Print", "fieldname": "print_action", "fieldtype": "HTML", "width": 60},
	]


def get_data(filters):
	conditions = get_conditions(filters)

	return frappe.db.sql(
		f"""
		SELECT
			s.name AS sale,
			s.invoice_number,
			s.sale_date,
			s.customer,
			CASE
				WHEN s.docstatus = 0 THEN 'Draft'
				WHEN s.docstatus = 1 THEN 'Submitted'
				WHEN s.docstatus = 2 THEN 'Cancelled'
			END AS status,
			COUNT(si.name) AS items_count,
			IFNULL(SUM(si.quantity), 0) AS total_qty,
			IFNULL(s.total_amount, 0) AS total_amount,
			IFNULL(s.total_profit, 0) AS total_profit,
			CASE
				WHEN IFNULL(SUM(si.quantity), 0) > 0
				THEN IFNULL(s.total_amount, 0) / IFNULL(SUM(si.quantity), 0)
				ELSE 0
			END AS avg_sale_value,
			s.name AS view_action,
			s.name AS print_action
		FROM `tabLedgix Sale` s
		LEFT JOIN `tabLedgix Sale Item` si
			ON si.parent = s.name
		WHERE {conditions}
		GROUP BY
			s.name,
			s.invoice_number,
			s.sale_date,
			s.customer,
			s.docstatus,
			s.total_amount,
			s.total_profit
		ORDER BY s.sale_date DESC, s.creation DESC
		""",
		filters,
		as_dict=True,
	)


def get_conditions(filters):
	conditions = ["1=1"]

	if filters.get("from_date"):
		conditions.append("s.sale_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("s.sale_date <= %(to_date)s")

	if filters.get("customer"):
		conditions.append("s.customer = %(customer)s")

	if filters.get("docstatus"):
		status_map = {
			"Draft": 0,
			"Submitted": 1,
			"Cancelled": 2,
		}
		filters["docstatus"] = status_map.get(filters.get("docstatus"))
		conditions.append("s.docstatus = %(docstatus)s")

	return " AND ".join(conditions)


def get_report_summary(data):
	total_sales = len(data)
	total_items = sum(row.get("items_count") or 0 for row in data)
	total_qty = sum(row.get("total_qty") or 0 for row in data)
	total_amount = sum(row.get("total_amount") or 0 for row in data)
	total_profit = sum(row.get("total_profit") or 0 for row in data)
	avg_sale_value = total_amount / total_sales if total_sales else 0

	return [
		{"value": total_sales, "label": "Sales", "datatype": "Int"},
		{"value": total_items, "label": "Line Items", "datatype": "Int"},
		{"value": total_qty, "label": "Total Qty", "datatype": "Float"},
		{"value": total_amount, "label": "Total Amount", "datatype": "Currency"},
		{"value": total_profit, "label": "Total Profit", "datatype": "Currency"},
		{"value": avg_sale_value, "label": "Avg Sale Value", "datatype": "Currency"},
	]