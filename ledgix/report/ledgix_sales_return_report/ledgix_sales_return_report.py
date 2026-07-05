# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

import frappe


RETURN_DOCTYPE = "Ledgix Sales Return"
RETURN_ITEM_DOCTYPE = "Ledgix Sales Return Item"


def execute(filters=None):
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)
	summary = get_report_summary(data)

	message = None
	if not data:
		message = """
			<div style="padding: 20px; text-align: center; color: #667085;">
				No sales return data found for selected filters.
			</div>
		"""

	return columns, data, message, None, summary


def get_columns():
	return [
		{"label": "Return ID", "fieldname": "sales_return", "fieldtype": "Link", "options": RETURN_DOCTYPE, "width": 145},
		{"label": "Original Sale", "fieldname": "original_sale", "fieldtype": "Link", "options": "Ledgix Sale", "width": 135},
		{"label": "Date", "fieldname": "return_date", "fieldtype": "Date", "width": 105},
		{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Ledgix Customer", "width": 180},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 105},
		{"label": "Items", "fieldname": "items_count", "fieldtype": "Int", "width": 80},
		{"label": "Return Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 110},
		{"label": "Return Amount", "fieldname": "return_amount", "fieldtype": "Currency", "width": 135},
		{"label": "Profit Reversal", "fieldname": "total_profit_reversal", "fieldtype": "Currency", "width": 135},
		{"label": "Avg Return Value", "fieldname": "avg_return_value", "fieldtype": "Currency", "width": 140},
		{"label": "View", "fieldname": "view_action", "fieldtype": "HTML", "width": 60},
		{"label": "Print", "fieldname": "print_action", "fieldtype": "HTML", "width": 60},
	]


def get_data(filters):
	parent_meta = frappe.get_meta(RETURN_DOCTYPE)
	child_table = f"tab{RETURN_ITEM_DOCTYPE}"

	date_field = get_existing_field(parent_meta, ["return_date", "sales_return_date", "posting_date", "date"])
	customer_field = get_existing_field(parent_meta, ["customer"])
	original_sale_field = get_existing_field(parent_meta, ["original_sale", "sale", "sales_invoice"])
	amount_field = get_existing_field(parent_meta, ["total_return_amount", "return_amount", "total_amount", "grand_total"])
	profit_reversal_field = get_existing_field(parent_meta, ["total_profit_reversal"])

	conditions, query_filters = get_conditions(filters, date_field, customer_field)

	date_select = f"sr.{date_field}" if date_field else "DATE(sr.creation)"
	customer_select = f"sr.{customer_field}" if customer_field else "NULL"
	original_sale_select = f"sr.{original_sale_field}" if original_sale_field else "NULL"
	amount_select = f"sr.{amount_field}" if amount_field else "IFNULL(SUM(sri.amount), 0)"
	profit_reversal_select = f"sr.{profit_reversal_field}" if profit_reversal_field else "0"

	return frappe.db.sql(
		f"""
		SELECT
			sr.name AS sales_return,
			{original_sale_select} AS original_sale,
			{date_select} AS return_date,
			{customer_select} AS customer,
			CASE
				WHEN sr.docstatus = 0 THEN 'Draft'
				WHEN sr.docstatus = 1 THEN 'Submitted'
				WHEN sr.docstatus = 2 THEN 'Cancelled'
			END AS status,
			COUNT(sri.name) AS items_count,
			IFNULL(SUM(sri.quantity), 0) AS total_qty,
			IFNULL({amount_select}, 0) AS return_amount,
			IFNULL({profit_reversal_select}, 0) AS total_profit_reversal,
			CASE
				WHEN IFNULL(SUM(sri.quantity), 0) > 0
				THEN IFNULL({amount_select}, 0) / IFNULL(SUM(sri.quantity), 0)
				ELSE 0
			END AS avg_return_value,
			sr.name AS view_action,
			sr.name AS print_action
		FROM `tab{RETURN_DOCTYPE}` sr
		LEFT JOIN `{child_table}` sri
			ON sri.parent = sr.name
		WHERE {conditions}
		GROUP BY sr.name
		ORDER BY return_date DESC, sr.creation DESC
		""",
		query_filters,
		as_dict=True,
	)


def get_conditions(filters, date_field=None, customer_field=None):
	conditions = ["1=1"]
	query_filters = dict(filters)

	if filters.get("from_date") and date_field:
		conditions.append(f"sr.{date_field} >= %(from_date)s")

	if filters.get("to_date") and date_field:
		conditions.append(f"sr.{date_field} <= %(to_date)s")

	if filters.get("customer") and customer_field:
		conditions.append(f"sr.{customer_field} = %(customer)s")

	if filters.get("docstatus"):
		status_map = {
			"Draft": 0,
			"Submitted": 1,
			"Cancelled": 2,
		}
		query_filters["docstatus"] = status_map.get(filters.get("docstatus"))
		conditions.append("sr.docstatus = %(docstatus)s")

	return " AND ".join(conditions), query_filters


def get_report_summary(data):
	total_returns = len(data)
	total_items = sum(row.get("items_count") or 0 for row in data)
	total_qty = sum(row.get("total_qty") or 0 for row in data)
	return_amount = sum(row.get("return_amount") or 0 for row in data)
	total_profit_reversal = sum(row.get("total_profit_reversal") or 0 for row in data)
	avg_return_value = return_amount / total_returns if total_returns else 0

	return [
		{"value": total_returns, "label": "Returns", "datatype": "Int"},
		{"value": total_items, "label": "Line Items", "datatype": "Int"},
		{"value": total_qty, "label": "Return Qty", "datatype": "Float"},
		{"value": return_amount, "label": "Return Amount", "datatype": "Currency"},
		{"value": total_profit_reversal, "label": "Profit Reversal", "datatype": "Currency"},
		{"value": avg_return_value, "label": "Avg Return Value", "datatype": "Currency"},
	]


def get_existing_field(meta, fieldnames):
	existing = {df.fieldname for df in meta.fields}
	for fieldname in fieldnames:
		if fieldname in existing:
			return fieldname
	return None