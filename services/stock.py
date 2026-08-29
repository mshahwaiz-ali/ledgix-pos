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
	movement.valuation_rate = max(flt(rate), 0)
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
	"""Post purchase inventory and valuation through the Stock Movement boundary."""
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
	"""Compatibility no-op.

	Moving-average valuation is owned by Ledgix Stock Movement.on_submit in V2.
	"""
	return None


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


def _legacy_reference_rate(row):
	"""Recover valuation for pre-V2 movements where possible without guessing."""
	if row.reference_doctype == "Ledgix Purchase" and row.reference_name:
		value = frappe.db.get_value(
			"Ledgix Purchase Item",
			{"parent": row.reference_name, "item": row.item},
			"rate",
		)
		return flt(value) if value is not None else None

	if row.reference_doctype == "Ledgix Sales Return" and row.reference_name:
		value = frappe.db.get_value(
			"Ledgix Sales Return Item",
			{"parent": row.reference_name, "item": row.item},
			"cost_price",
		)
		return flt(value) if value is not None else None

	# OUT movements do not alter moving-average cost, so their missing valuation
	# does not block a rebuild.
	if row.movement_type == "OUT":
		return 0.0

	return None


def rebuild_item_average_cost(item, exclude_movement=None):
	"""Replay submitted inventory events to rebuild moving-average valuation.

	This is primarily used after cancellation, where simply reversing the last
	average is unsafe if later receipts/returns occurred. Historical IN movements
	without any recoverable valuation snapshot cause a safe no-op instead of an
	invented cost.
	"""
	rows = frappe.get_all(
		"Ledgix Stock Movement",
		filters={"item": item, "docstatus": 1},
		fields=[
			"name",
			"item",
			"movement_type",
			"movement_source",
			"quantity",
			"valuation_rate",
			"reference_doctype",
			"reference_name",
			"movement_date",
			"creation",
		],
		order_by="movement_date asc, creation asc, name asc",
		limit_page_length=0,
	)

	qty = 0.0
	average = 0.0
	for row in rows:
		if exclude_movement and row.name == exclude_movement:
			continue

		movement_qty = flt(row.quantity)
		if movement_qty <= 0:
			continue

		if row.movement_type == "IN":
			rate = row.valuation_rate
			if rate is None:
				rate = _legacy_reference_rate(row)
			if rate is None:
				frappe.logger("ledgix").warning(
					"Skipped valuation rebuild for %s: movement %s has no recoverable valuation rate.",
					item,
					row.name,
				)
				return {"updated": False, "reason": "legacy valuation snapshot missing"}
			rate = max(flt(rate), 0)
			new_qty = qty + movement_qty
			average = ((qty * average) + (movement_qty * rate)) / new_qty if new_qty else average
			qty = new_qty
		elif row.movement_type == "OUT":
			qty = max(qty - movement_qty, 0)
		elif row.movement_type == "ADJUSTMENT":
			qty = movement_qty
			if row.valuation_rate is not None:
				average = max(flt(row.valuation_rate), 0)

	item_doc = frappe.get_doc("Ledgix Item", item)
	item_doc.cost_price = flt(average, 6) if qty > 0 else 0
	item_doc.flags.allow_cost_update = True
	item_doc.save(ignore_permissions=True)
	return {"updated": True, "quantity": qty, "average_cost": flt(item_doc.cost_price, 6)}
