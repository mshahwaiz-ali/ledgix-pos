from __future__ import annotations

import frappe


def post_sale_movements(sale):
	for row in sale.items:
		movement = frappe.new_doc("Ledgix Stock Movement")
		movement.item = row.item
		movement.quantity = row.quantity
		movement.rate = row.cost_price
		movement.movement_type = "OUT"
		movement.reference_doctype = "Ledgix Sale"
		movement.reference_name = sale.name
		from ledgix_saas.api.stock_ops import apply_movement_source
		apply_movement_source(movement, "Sale")
		movement.insert(ignore_permissions=True)
		movement.submit()


def cancel_reference_movements(reference_doctype, reference_name):
	movements = frappe.get_all(
		"Ledgix Stock Movement",
		filters={"reference_doctype": reference_doctype, "reference_name": reference_name, "docstatus": 1},
		pluck="name",
	)
	for movement_name in movements:
		frappe.get_doc("Ledgix Stock Movement", movement_name).cancel()
