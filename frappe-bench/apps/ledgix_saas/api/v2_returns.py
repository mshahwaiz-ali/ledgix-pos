from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, flt

from ledgix_saas.api.security import require_ledgix_cashier_or_above
from ledgix_saas.api.settings import get_stock_control_mode, sale_matches_current_stock_mode
from ledgix_saas.api.stock_identity import is_serial_based_item, parse_serial_numbers


def _return_item_has_original_row():
    return bool(frappe.get_meta("Ledgix Sales Return Item").has_field("original_sale_item_row"))


def _legacy_returned_qty_by_item(original_sale):
    if not _return_item_has_original_row():
        return {}

    rows = frappe.db.sql(
        """
        SELECT ri.item, COALESCE(SUM(ri.quantity), 0) AS quantity
        FROM `tabLedgix Sales Return Item` ri
        INNER JOIN `tabLedgix Sales Return` r ON r.name = ri.parent
        WHERE r.original_sale = %s
          AND r.docstatus = 1
          AND (ri.original_sale_item_row IS NULL OR ri.original_sale_item_row = '')
        GROUP BY ri.item
        """,
        (original_sale,),
        as_dict=True,
    )
    return {row.item: flt(row.quantity) for row in rows}


def _row_returned_qty(original_sale, sale_item_row, legacy_remainder_by_item=None):
    row_qty = 0.0
    if _return_item_has_original_row():
        row_qty = frappe.db.sql(
            """
            SELECT COALESCE(SUM(ri.quantity), 0)
            FROM `tabLedgix Sales Return Item` ri
            INNER JOIN `tabLedgix Sales Return` r ON r.name = ri.parent
            WHERE r.original_sale = %s
              AND r.docstatus = 1
              AND ri.original_sale_item_row = %s
            """,
            (original_sale, sale_item_row.name),
        )[0][0]

    legacy_qty = 0.0
    if legacy_remainder_by_item is not None:
        item = sale_item_row.item
        available_for_legacy = max(flt(sale_item_row.quantity) - flt(row_qty), 0)
        legacy_qty = min(flt(legacy_remainder_by_item.get(item)), available_for_legacy)
        legacy_remainder_by_item[item] = max(flt(legacy_remainder_by_item.get(item)) - legacy_qty, 0)

    return flt(row_qty) + flt(legacy_qty)


def _returned_qty_by_sale_row(sale):
    legacy_remainder = _legacy_returned_qty_by_item(sale.name)
    returned_by_row = {}
    for sale_item in sorted(sale.items, key=lambda row: (row.idx or 0, row.name or "")):
        returned_by_row[sale_item.name] = _row_returned_qty(sale.name, sale_item, legacy_remainder)
    return returned_by_row


def _requested_return_qty_by_item(return_items):
    requested = {}
    for row in return_items:
        item = row.get("item")
        qty = flt(row.get("return_qty") or row.get("quantity") or row.get("qty"))
        if not item or qty <= 0:
            continue
        requested[item] = flt(requested.get(item)) + qty
    return requested


def _returnable_serial_numbers(sale, sale_item):
    """Return the exact original serial identities that are still in Sold state."""
    if not is_serial_based_item(sale_item.item):
        return ""

    original_serials = parse_serial_numbers(getattr(sale_item, "serial_numbers", None))
    if not original_serials:
        original_serials = frappe.get_all(
            "Ledgix Stock Serial",
            filters={"item": sale_item.item, "sale": sale.name, "status": "Sold"},
            pluck="serial_no",
            order_by="sold_date asc, creation asc",
        )

    available = []
    for serial_no in original_serials:
        serial = frappe.db.get_value(
            "Ledgix Stock Serial",
            {"serial_no": serial_no},
            ["item", "status", "sale", "sale_item_row"],
            as_dict=True,
        )
        if not serial:
            continue
        if serial.item != sale_item.item or serial.sale != sale.name or serial.status != "Sold":
            continue
        if serial.sale_item_row and serial.sale_item_row != sale_item.name:
            continue
        available.append(serial_no)

    return "\n".join(available)


def _validate_requested_serials(sale, sale_item, qty, serial_numbers):
    """Validate an explicit POS return serial selection against the original Sale."""
    if not is_serial_based_item(sale_item.item):
        return ""

    value = str(serial_numbers or "").strip()
    if not value:
        return ""

    serials = parse_serial_numbers(value)
    qty = flt(qty)
    if qty != cint(qty) or cint(qty) != len(serials):
        frappe.throw(
            _("Serial Based item {0} requires {1} serial number(s) for this return.").format(
                sale_item.item,
                cint(qty),
            )
        )

    for serial_no in serials:
        serial = frappe.db.get_value(
            "Ledgix Stock Serial",
            {"serial_no": serial_no},
            ["item", "status", "sale", "sale_item_row"],
            as_dict=True,
        )
        if not serial:
            frappe.throw(_("Serial number {0} does not exist.").format(serial_no))
        if serial.item != sale_item.item:
            frappe.throw(
                _("Serial number {0} belongs to item {1}, not {2}.").format(
                    serial_no,
                    serial.item,
                    sale_item.item,
                )
            )
        if serial.sale != sale.name:
            frappe.throw(
                _("Serial number {0} was not sold on original Sale {1}.").format(
                    serial_no,
                    sale.name,
                )
            )
        if serial.sale_item_row and serial.sale_item_row != sale_item.name:
            frappe.throw(
                _("Serial number {0} belongs to a different original Sale row.").format(serial_no)
            )
        if serial.status != "Sold":
            frappe.throw(
                _("Serial number {0} is not returnable. Current status: {1}.").format(
                    serial_no,
                    serial.status,
                )
            )

    return "\n".join(serials)


def _return_allocation_from_sale_item(sale_item, qty, serial_numbers=""):
    return {
        "item": sale_item.item,
        "quantity": qty,
        "rate": flt(sale_item.rate),
        "amount": flt(qty) * flt(sale_item.rate),
        "cost_price": flt(sale_item.cost_price),
        "profit_per_unit": flt(sale_item.profit_per_unit),
        "item_total_profit": flt(qty) * flt(sale_item.profit_per_unit),
        "original_sale_item_row": sale_item.name,
        "serial_numbers": serial_numbers or "",
    }


def _allocate_return_items_from_sale(sale, return_items):
    """Allocate requested quantities against exact submitted Sale Item rows.

    New V2 callers should send original_sale_item_row. Item-only rows remain
    supported for upgraded legacy clients and are allocated deterministically
    across matching sale rows without allowing over-return.
    """
    sale_items_by_row = {row.name: row for row in sale.items}
    returned_by_row = _returned_qty_by_sale_row(sale)
    allocations = []
    legacy_return_items = []

    for requested_row in return_items:
        requested_qty = flt(
            requested_row.get("return_qty")
            or requested_row.get("quantity")
            or requested_row.get("qty")
        )
        if requested_qty <= 0:
            continue

        original_sale_item_row = str(requested_row.get("original_sale_item_row") or "").strip()
        if not original_sale_item_row:
            legacy_return_items.append(requested_row)
            continue

        sale_item = sale_items_by_row.get(original_sale_item_row)
        if not sale_item:
            frappe.throw(_("Selected return row does not belong to the original sale."))

        requested_item = requested_row.get("item")
        if requested_item and requested_item != sale_item.item:
            frappe.throw(_("Selected return item does not match the original sale row."))

        available_qty = max(flt(sale_item.quantity) - flt(returned_by_row.get(sale_item.name)), 0)
        if requested_qty > available_qty:
            frappe.throw(
                _("Return quantity for item {0} exceeds remaining returnable quantity ({1}).").format(
                    sale_item.item,
                    f"{available_qty:g}",
                )
            )

        serial_numbers = _validate_requested_serials(
            sale,
            sale_item,
            requested_qty,
            requested_row.get("serial_numbers"),
        )
        allocations.append(_return_allocation_from_sale_item(sale_item, requested_qty, serial_numbers))
        returned_by_row[sale_item.name] = flt(returned_by_row.get(sale_item.name)) + requested_qty

    requested_by_item = _requested_return_qty_by_item(legacy_return_items)
    for sale_item in sorted(sale.items, key=lambda row: (row.idx or 0, row.name or "")):
        requested_qty = flt(requested_by_item.get(sale_item.item))
        if requested_qty <= 0:
            continue

        available_qty = max(flt(sale_item.quantity) - flt(returned_by_row.get(sale_item.name)), 0)
        allocate_qty = min(requested_qty, available_qty)
        if allocate_qty <= 0:
            continue

        allocations.append(_return_allocation_from_sale_item(sale_item, allocate_qty))
        returned_by_row[sale_item.name] = flt(returned_by_row.get(sale_item.name)) + allocate_qty
        requested_by_item[sale_item.item] = requested_qty - allocate_qty

    remaining = {item: qty for item, qty in requested_by_item.items() if flt(qty) > 0}
    if remaining:
        item, qty = next(iter(remaining.items()))
        frappe.throw(
            _("Return quantity for item {0} exceeds remaining returnable quantity ({1} over).").format(
                item,
                f"{flt(qty):g}",
            )
        )

    return allocations


def _resolve_submitted_sale(sale_id):
    sale_id = str(sale_id or "").strip()
    if not sale_id:
        frappe.throw(_("Sale ID or Invoice Number is required."))

    sale_name = None
    if frappe.db.exists("Ledgix Sale", sale_id):
        sale_name = sale_id
    if not sale_name:
        sale_name = frappe.db.get_value(
            "Ledgix Sale",
            {"invoice_number": sale_id, "docstatus": 1},
            "name",
        )
    if not sale_name:
        frappe.throw(_("No submitted sale found for: {0}").format(sale_id))

    sale = frappe.get_doc("Ledgix Sale", sale_name)
    if sale.docstatus != 1:
        frappe.throw(_("Only submitted sales can be returned."))
    if not sale_matches_current_stock_mode(sale.name):
        frappe.throw(
            _("This invoice belongs to a different stock mode. Current mode: {0}.").format(
                get_stock_control_mode()
            )
        )
    return sale


@frappe.whitelist()
def get_pos_v2_return_context(sale_id=None):
    """Return authoritative submitted-sale rows still available for correction."""
    require_ledgix_cashier_or_above()
    sale = _resolve_submitted_sale(sale_id)
    returned_by_row = _returned_qty_by_sale_row(sale)
    items = []

    for row in sorted(sale.items, key=lambda sale_row: (sale_row.idx or 0, sale_row.name or "")):
        already_returned_qty = flt(returned_by_row.get(row.name))
        returnable_qty = flt(row.quantity) - already_returned_qty
        if returnable_qty <= 0:
            continue
        items.append({
            "item": row.item,
            "original_sale_item_row": row.name,
            "item_name": frappe.db.get_value("Ledgix Item", row.item, "item_name") or row.item,
            "tracking_type": frappe.db.get_value("Ledgix Item", row.item, "tracking_type") or "Normal",
            "serial_numbers": _returnable_serial_numbers(sale, row),
            "sold_qty": flt(row.quantity),
            "already_returned_qty": already_returned_qty,
            "returnable_qty": returnable_qty,
            "return_qty": 0,
            "rate": flt(row.rate),
            "amount": 0,
            "cost_price": flt(row.cost_price),
            "profit_per_unit": flt(row.profit_per_unit),
            "item_total_profit": 0,
        })

    return {
        "success": True,
        "sale_id": sale.name,
        "invoice_number": sale.invoice_number,
        "customer": sale.customer,
        "sale_date": sale.sale_date,
        "items": items,
    }


@frappe.whitelist()
def create_pos_v2_return(original_sale=None, return_items=None, reason=None):
    """Create a submitted correction against exact original Sale Item rows."""
    require_ledgix_cashier_or_above()
    return_items = frappe.parse_json(return_items) if isinstance(return_items, str) else return_items
    reason = str(reason or "").strip()

    if not original_sale:
        frappe.throw(_("Original sale is required."))
    if not return_items:
        frappe.throw(_("No return items selected."))
    if not reason:
        frappe.throw(_("Return Reason is required."))

    sale = _resolve_submitted_sale(original_sale)
    allocations = _allocate_return_items_from_sale(sale, return_items)
    if not allocations:
        frappe.throw(_("Enter a return quantity for at least one item."))

    return_doc = frappe.new_doc("Ledgix Sales Return")
    return_doc.original_sale = sale.name
    return_doc.return_reason = reason
    for row in allocations:
        return_doc.append("items", row)
    return_doc.insert(ignore_permissions=True)
    return_doc.submit()

    return {
        "success": True,
        "return_id": return_doc.name,
        "original_sale": sale.name,
        "customer": return_doc.customer,
        "total_amount": flt(return_doc.total_amount),
        "tax_amount": flt(return_doc.tax_amount),
        "grand_total": flt(return_doc.grand_total or return_doc.total_amount),
        "fbr_status": return_doc.fbr_status or "",
    }
