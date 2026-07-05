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
				No stock movement data found for selected filters.
			</div>
		"""

	return columns, data, message, None, summary


def get_columns():
	return [
		{"label": "Movement ID", "fieldname": "movement", "fieldtype": "Link", "options": "Ledgix Stock Movement", "width": 155},
		{"label": "Date", "fieldname": "movement_date", "fieldtype": "Datetime", "width": 155},
		{"label": "Item", "fieldname": "item", "fieldtype": "Link", "options": "Ledgix Item", "width": 190},
		{"label": "Movement Type", "fieldname": "movement_type", "fieldtype": "Data", "width": 130},
		{"label": "Qty", "fieldname": "quantity", "fieldtype": "Float", "width": 95},
		{"label": "Reference Type", "fieldname": "reference_doctype", "fieldtype": "Data", "width": 145},
		{"label": "Reference ID", "fieldname": "reference_name", "fieldtype": "Dynamic Link", "options": "reference_doctype", "width": 150},
		{"label": "Reference Note", "fieldname": "reference_note", "fieldtype": "Data", "width": 180},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 105},
		{"label": "Created By", "fieldname": "owner", "fieldtype": "Data", "width": 180},
		{"label": "View", "fieldname": "view_action", "fieldtype": "HTML", "width": 60},
		{"label": "Print", "fieldname": "print_action", "fieldtype": "HTML", "width": 60},
	]


def get_data(filters):
	conditions = get_conditions(filters)

	return frappe.db.sql(
		f"""
		SELECT
			sm.name AS movement,
			sm.movement_date,
			sm.item,
			sm.movement_type,
			IFNULL(sm.quantity, 0) AS quantity,
			sm.reference_doctype,
			sm.reference_name,
			sm.reference_note,
			CASE
				WHEN sm.docstatus = 0 THEN 'Draft'
				WHEN sm.docstatus = 1 THEN 'Submitted'
				WHEN sm.docstatus = 2 THEN 'Cancelled'
				ELSE 'Unknown'
			END AS status,
			sm.owner,
			sm.name AS view_action,
			sm.name AS print_action
		FROM `tabLedgix Stock Movement` sm
		WHERE {conditions}
		ORDER BY sm.movement_date DESC, sm.creation DESC
		""",
		filters,
		as_dict=True,
	)


def get_conditions(filters):
	conditions = ["1=1"]

	if filters.get("from_date"):
		conditions.append("DATE(sm.movement_date) >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("DATE(sm.movement_date) <= %(to_date)s")

	if filters.get("item"):
		conditions.append("sm.item = %(item)s")

	if filters.get("movement_type"):
		conditions.append("sm.movement_type = %(movement_type)s")

	if filters.get("reference_doctype"):
		conditions.append("sm.reference_doctype = %(reference_doctype)s")

	if filters.get("reference_name"):
		conditions.append("sm.reference_name = %(reference_name)s")

	if filters.get("docstatus"):
		status_map = {
			"Draft": 0,
			"Submitted": 1,
			"Cancelled": 2,
		}

		docstatus = status_map.get(filters.get("docstatus"))

		if docstatus is not None:
			filters["docstatus_value"] = docstatus
			conditions.append("sm.docstatus = %(docstatus_value)s")

	return " AND ".join(conditions)


def get_report_summary(data):
	total_movements = len(data)

	in_qty = sum(row.get("quantity") or 0 for row in data if row.get("movement_type") == "IN")
	out_qty = sum(row.get("quantity") or 0 for row in data if row.get("movement_type") == "OUT")
	adjustment_qty = sum(row.get("quantity") or 0 for row in data if row.get("movement_type") == "ADJUSTMENT")

	net_qty = in_qty - out_qty

	return [
		{"value": total_movements, "label": "Movements", "datatype": "Int"},
		{"value": in_qty, "label": "Total IN", "datatype": "Float"},
		{"value": out_qty, "label": "Total OUT", "datatype": "Float"},
		{"value": adjustment_qty, "label": "Adjustments", "datatype": "Float"},
		{"value": net_qty, "label": "Net Qty", "datatype": "Float"},
	]