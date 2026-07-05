import frappe
from frappe.utils import flt, now_datetime

from ledgix_saas.api.security import require_ledgix_manager_or_above
from ledgix_saas.api.stock_identity import (
    create_stock_lot_from_manual_entry,
    create_stock_serials_for_manual_entry,
    is_lot_based_item,
    is_serial_based_item,
    reduce_lots_fifo_for_manual_out,
)


def _movement_note(source_label, note=None):
    base = (source_label or "").strip()
    extra = (note or "").strip()
    if base and extra:
        return f"{base} — {extra}"
    return base or extra


def apply_movement_source(movement, movement_source):
    stock_meta = frappe.get_meta("Ledgix Stock Movement")
    if stock_meta.has_field("movement_source") and movement_source:
        movement.movement_source = movement_source


def _set_movement_fields(movement, movement_source, reference_note):
    stock_meta = frappe.get_meta("Ledgix Stock Movement")
    if stock_meta.has_field("movement_source") and movement_source:
        movement.movement_source = movement_source
    if stock_meta.has_field("reference_note") and reference_note:
        movement.reference_note = reference_note


def _create_submitted_movement(item, movement_type, qty, movement_source, reference_note):
    if not frappe.db.exists("Ledgix Item", item):
        frappe.throw(f"Item {item} does not exist.")

    qty = flt(qty)
    if qty <= 0:
        frappe.throw("Movement quantity must be greater than zero.")

    movement = frappe.new_doc("Ledgix Stock Movement")
    movement.item = item
    movement.movement_type = movement_type
    movement.quantity = qty
    movement.movement_date = now_datetime()
    movement.reference_doctype = "Ledgix Item"
    movement.reference_name = item
    _set_movement_fields(movement, movement_source, reference_note)
    movement.insert(ignore_permissions=True)
    movement.submit()
    return movement


@frappe.whitelist()
def manual_stock_entry(item, qty_in=0, qty_out=0, serial_numbers=None, note=None):
    require_ledgix_manager_or_above()
    qty_in = flt(qty_in)
    qty_out = flt(qty_out)

    if not item:
        frappe.throw("Item is required.")

    if qty_in <= 0 and qty_out <= 0:
        frappe.throw("Enter Add Stock or Remove Stock quantity.")

    if qty_in > 0 and qty_out > 0:
        frappe.throw("Enter either Add Stock or Remove Stock, not both at the same time.")

    if is_serial_based_item(item) and qty_out > 0:
        frappe.throw(
            "Serial Based items cannot be reduced from the item form. Use Sale or Sales Return instead."
        )

    created = []
    lot_name = None
    serial_count = 0

    if qty_in > 0:
        result = _apply_stock_in(
            item=item,
            qty=qty_in,
            serial_numbers=serial_numbers,
            movement_source="Manual IN",
            source_label="Manual IN",
            note=note,
        )
        created.append(result.get("movement_name"))
        lot_name = result.get("lot_name")
        serial_count = result.get("serial_count") or 0

    if qty_out > 0:
        movement_name = _apply_stock_out(
            item=item,
            qty=qty_out,
            movement_source="Manual OUT",
            source_label="Manual OUT",
            note=note,
        )
        created.append(movement_name)

    current_stock = frappe.db.get_value("Ledgix Item", item, "current_stock")

    return {
        "item": item,
        "movements": created,
        "lot_name": lot_name,
        "serial_count": serial_count,
        "current_stock": flt(current_stock),
    }


@frappe.whitelist()
def record_opening_stock(item, qty, serial_numbers=None):
    require_ledgix_manager_or_above()
    if flt(qty) <= 0:
        return None

    result = _apply_stock_in(
        item=item,
        qty=flt(qty),
        serial_numbers=serial_numbers,
        movement_source="Opening",
        source_label="Opening Stock",
        note=None,
    )
    return result.get("movement_name")


def _apply_stock_in(item, qty, serial_numbers, movement_source, source_label, note=None):
    qty = flt(qty)
    reference_note = _movement_note(source_label, note)
    lot_name = None
    serial_count = 0

    if is_serial_based_item(item):
        serial_count = create_stock_serials_for_manual_entry(
            item=item,
            qty=qty,
            serial_numbers=serial_numbers,
            cost_rate=flt(frappe.db.get_value("Ledgix Item", item, "cost_price")),
        )

    movement = _create_submitted_movement(
        item=item,
        movement_type="IN",
        qty=qty,
        movement_source=movement_source,
        reference_note=reference_note,
    )

    if is_lot_based_item(item):
        lot_name = create_stock_lot_from_manual_entry(
            item=item,
            qty=qty,
            rate=flt(frappe.db.get_value("Ledgix Item", item, "cost_price")),
            movement_name=movement.name,
        )

    return {
        "movement_name": movement.name,
        "lot_name": lot_name,
        "serial_count": serial_count,
    }


def _apply_stock_out(item, qty, movement_source, source_label, note=None):
    qty = flt(qty)
    reference_note = _movement_note(source_label, note)

    if is_lot_based_item(item):
        reduce_lots_fifo_for_manual_out(item, qty)

    movement = _create_submitted_movement(
        item=item,
        movement_type="OUT",
        qty=qty,
        movement_source=movement_source,
        reference_note=reference_note,
    )
    return movement.name
