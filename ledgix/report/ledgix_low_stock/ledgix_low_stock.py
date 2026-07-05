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
				No low stock items found. Inventory looks healthy for selected filters.
			</div>
		"""

	return columns, data, message, None, summary


def get_columns():
	return [
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Ledgix Item", "width": 150},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 190},
		{"label": "Category", "fieldname": "category", "fieldtype": "Data", "width": 145},
		{"label": "Current Stock", "fieldname": "current_stock", "fieldtype": "Float", "width": 120},
		{"label": "Minimum Stock", "fieldname": "minimum_stock", "fieldtype": "Float", "width": 125},
		{"label": "Shortage Qty", "fieldname": "shortage_qty", "fieldtype": "Float", "width": 120},
		{"label": "Cost Price", "fieldname": "cost_price", "fieldtype": "Currency", "width": 115},
		{"label": "Selling Price", "fieldname": "selling_price", "fieldtype": "Currency", "width": 120},
		{"label": "Stock Value", "fieldname": "stock_value", "fieldtype": "Currency", "width": 125},
		{"label": "Potential Sales Gap", "fieldname": "potential_sales_gap", "fieldtype": "Currency", "width": 150},
		{"label": "Risk Status", "fieldname": "risk_status", "fieldtype": "Data", "width": 125},
		{"label": "View", "fieldname": "view_action", "fieldtype": "HTML", "width": 60},
		{"label": "Print", "fieldname": "print_action", "fieldtype": "HTML", "width": 60},
	]


def get_data(filters):
	conditions = get_conditions(filters)

	return frappe.db.sql(
		f"""
		SELECT
			name AS item,
			item_name,
			category,
			IFNULL(current_stock, 0) AS current_stock,
			IFNULL(minimum_stock, 0) AS minimum_stock,
			CASE
				WHEN IFNULL(minimum_stock, 0) - IFNULL(current_stock, 0) > 0
				THEN IFNULL(minimum_stock, 0) - IFNULL(current_stock, 0)
				ELSE 0
			END AS shortage_qty,
			IFNULL(cost_price, 0) AS cost_price,
			IFNULL(selling_price, 0) AS selling_price,
			IFNULL(current_stock, 0) * IFNULL(cost_price, 0) AS stock_value,
			CASE
				WHEN IFNULL(minimum_stock, 0) - IFNULL(current_stock, 0) > 0
				THEN (IFNULL(minimum_stock, 0) - IFNULL(current_stock, 0)) * IFNULL(selling_price, 0)
				ELSE 0
			END AS potential_sales_gap,
			CASE
				WHEN IFNULL(current_stock, 0) <= 0 THEN 'Out of Stock'
				WHEN IFNULL(current_stock, 0) < IFNULL(minimum_stock, 0) THEN 'Low Stock'
				WHEN IFNULL(current_stock, 0) = IFNULL(minimum_stock, 0) THEN 'At Minimum'
				ELSE 'Healthy'
			END AS risk_status,
			name AS view_action,
			name AS print_action
		FROM `tabLedgix Item`
		WHERE {conditions}
		ORDER BY
			CASE
				WHEN IFNULL(current_stock, 0) <= 0 THEN 1
				WHEN IFNULL(current_stock, 0) < IFNULL(minimum_stock, 0) THEN 2
				WHEN IFNULL(current_stock, 0) = IFNULL(minimum_stock, 0) THEN 3
				ELSE 4
			END,
			shortage_qty DESC,
			item_name ASC
		""",
		filters,
		as_dict=True,
	)


def get_conditions(filters):
	conditions = [
		"IFNULL(minimum_stock, 0) > 0",
		"IFNULL(current_stock, 0) <= IFNULL(minimum_stock, 0)"
	]

	if filters.get("category"):
		conditions.append("category = %(category)s")

	if filters.get("risk_status"):
		if filters.get("risk_status") == "Out of Stock":
			conditions.append("IFNULL(current_stock, 0) <= 0")

		if filters.get("risk_status") == "Low Stock":
			conditions.append("IFNULL(current_stock, 0) > 0")
			conditions.append("IFNULL(current_stock, 0) < IFNULL(minimum_stock, 0)")

		if filters.get("risk_status") == "At Minimum":
			conditions.append("IFNULL(current_stock, 0) = IFNULL(minimum_stock, 0)")

	return " AND ".join(conditions)


def get_report_summary(data):
	total_items = len(data)
	out_of_stock = sum(1 for row in data if row.get("risk_status") == "Out of Stock")
	low_stock = sum(1 for row in data if row.get("risk_status") == "Low Stock")
	at_minimum = sum(1 for row in data if row.get("risk_status") == "At Minimum")
	total_shortage = sum(row.get("shortage_qty") or 0 for row in data)
	potential_sales_gap = sum(row.get("potential_sales_gap") or 0 for row in data)

	return [
		{"value": total_items, "label": "Risk Items", "datatype": "Int"},
		{"value": out_of_stock, "label": "Out of Stock", "datatype": "Int"},
		{"value": low_stock, "label": "Low Stock", "datatype": "Int"},
		{"value": at_minimum, "label": "At Minimum", "datatype": "Int"},
		{"value": total_shortage, "label": "Shortage Qty", "datatype": "Float"},
		{"value": potential_sales_gap, "label": "Sales Gap", "datatype": "Currency"},
	]
