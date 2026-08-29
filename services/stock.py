from __future__ import annotations

import frappe


def _post_movement(*, item, quantity, movement_type, reference_doctype, reference_name, source, rate=0, note=None):
	existing = frappe.db.exists(
		"Ledgix Stock Movement",
		{
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"item": item,
			"movement_type": movement_type,
			"quantity": quantity,
			"docstatus": ["!=", 2],
		},
	)
	if existing:
		return existing

	movement = frappe.new_doc("Ledgix Stock Movement")
	movement.item = item
	movement.quantity = quantity
	movement.rate = rate
	movement.movement_type = movement_type
	movement.reference_doctype = reference_doctype
	movement.reference_name = reference_name
	if note and frappe.get_meta("Ledgix Stock Movement").has_field("reference_note"):
		movement.reference_note = note
	from ledgix_saas.api.stock_ops import apply_movement_source
	apply_movement_source(movement, source)
	movement.insert(ignore_permissions=True)
	movement.submit()
	return movement.name


def post_sale_movements(sale):
	for row in sale.items:
		_post_movement(
			item=row.item,
			quantity=row.quantity,
			rate=getattr(row, "cost_price", 0),
			movement_type="OUT",
			reference_doctype="Ledgix Sale",
			reference_name=sale.name,
			source="Sale",
		)


def post_sales_return_movements(sales_return):
	if not sales_return.original_sale:
		return
	original_has_stock = frappe.db.exists(
		"Ledgix Stock Movement",
		{"reference_doctype": "Ledgix Sale", "reference_name": sales_return.original_sale, "docstatus": 1},
	)
	if not original_has_stock:
		return
	for row in sales_return.items:
		_post_movement(
			item=row.item,
			quantity=row.quantity,
			rate=getattr(row, "cost_price", 0),
			movement_type="IN",
			reference_doctype="Ledgix Sales Return",
			reference_name=sales_return.name,
			source="Return",
			note=f"Return against {sales_return.original_sale}",
		)


def cancel_reference_movements(reference_doctype, reference_name):
	movements = frappe.get_all(
		"Ledgix Stock Movement",
		filters={"reference_doctype": reference_doctype, "reference_name": reference_name, "docstatus": 1},
		pluck="name",
	)
	for movement_name in movements:
		frappe.get_doc("Ledgix Stock Movement", movement_name).cancel()
