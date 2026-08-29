from __future__ import annotations

import frappe
from frappe.utils import flt


def _post_movement(*, item, quantity, movement_type, reference_doctype, reference_name, source, rate=0, note=None, movement_date=None):
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
	meta = frappe.get_meta("Ledgix Stock Movement")
	if movement_date and meta.has_field("movement_date"):
		movement.movement_date = movement_date
	if note and meta.has_field("reference_note"):
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


def post_purchase_movements(purchase):
	"""Post purchase stock through the same authoritative movement boundary."""
	for row in purchase.items:
		_post_movement(
			item=row.item,
			quantity=row.quantity,
			rate=row.rate,
			movement_type="IN",
			reference_doctype="Ledgix Purchase",
			reference_name=purchase.name,
			source="Purchase",
			movement_date=getattr(purchase, "purchase_date", None),
		)


def update_purchase_average_costs(purchase):
	"""Update moving average cost after movement posting without owning stock qty."""
	for row in purchase.items:
		item_doc = frappe.get_doc("Ledgix Item", row.item)
		old_qty = flt(item_doc.current_stock) - flt(row.quantity)
		old_cost = flt(item_doc.cost_price)
		new_qty = flt(row.quantity)
		new_rate = flt(row.rate)
		if old_qty <= 0:
			average_cost = new_rate
		else:
			average_cost = ((old_qty * old_cost) + (new_qty * new_rate)) / (old_qty + new_qty)
		item_doc.cost_price = average_cost
		item_doc.flags.allow_cost_update = True
		item_doc.save(ignore_permissions=True)


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
