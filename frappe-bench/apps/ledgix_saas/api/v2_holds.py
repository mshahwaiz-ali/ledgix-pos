from __future__ import annotations

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api.security import has_any_role, require_ledgix_cashier_or_above
from ledgix_saas.api.shifts import _get_open_shift_for_user
from ledgix_saas.api.stock_identity import parse_serial_numbers


PRIVILEGED_HOLD_ROLES = ("System Manager", "Ledgix Admin", "Ledgix Manager")


def _parse_rows(cart_items):
    rows = frappe.parse_json(cart_items) if isinstance(cart_items, str) else cart_items
    return rows or []


def _normalize_channel(value):
    channel = str(value or "Retail").strip()
    if channel not in {"Retail", "B2B"}:
        frappe.throw("Sale channel must be Retail or B2B.")
    return channel


def _available_serials(item, qty):
    rows = frappe.get_all(
        "Ledgix Stock Serial",
        filters={"item": item, "status": "Available"},
        fields=["serial_no"],
        order_by="purchase_date asc, creation asc, serial_no asc",
        limit_page_length=max(cint(qty), 1),
    )
    return [row.serial_no for row in rows]


def _normalize_serial_selection(item, tracking_type, qty, serial_numbers):
    if tracking_type != "Serial Based":
        return ""

    qty = flt(qty)
    if qty != cint(qty):
        frappe.throw(f"Serial Based item {item} quantity must be a whole number.")

    serials = parse_serial_numbers(serial_numbers)
    if not serials:
        serials = _available_serials(item, qty)

    if cint(qty) != len(serials):
        frappe.throw(
            f"Serial Based item {item} requires {cint(qty)} serial number(s), "
            f"but {len(serials)} available/selected."
        )

    for serial_no in serials:
        serial = frappe.db.get_value(
            "Ledgix Stock Serial",
            {"serial_no": serial_no},
            ["item", "status"],
            as_dict=True,
        )
        if not serial:
            frappe.throw(f"Serial number {serial_no} does not exist for item {item}.")
        if serial.item != item:
            frappe.throw(f"Serial number {serial_no} belongs to item {serial.item}, not {item}.")
        if serial.status != "Available":
            frappe.throw(
                f"Serial number {serial_no} for item {item} is not available. "
                f"Current status: {serial.status}."
            )

    return "\n".join(serials)


def _prepare_hold_rows(cart_items):
    prepared = []
    subtotal = 0.0

    for row in _parse_rows(cart_items):
        item_name = str(row.get("item") or "").strip()
        qty = flt(row.get("qty") or row.get("quantity"))
        rate = flt(row.get("rate"))

        if not item_name:
            frappe.throw("Item is required before holding a sale.")
        if qty <= 0:
            frappe.throw("Held quantity must be greater than zero.")

        item = frappe.db.get_value(
            "Ledgix Item",
            item_name,
            ["name", "item_name", "active", "tracking_type"],
            as_dict=True,
        )
        if not item or not item.active:
            frappe.throw(f"Active item not found: {item_name}")

        tracking_type = item.tracking_type or "Normal"
        serial_numbers = _normalize_serial_selection(
            item.name,
            tracking_type,
            qty,
            row.get("serial_numbers") or "",
        )

        # Held rates are display context only. Resume/checkout always re-prices on
        # the authoritative V2 pricing service before a Sale can be submitted.
        amount = qty * max(rate, 0)
        subtotal += amount
        prepared.append({
            "item": item.name,
            "item_name": item.item_name or item.name,
            "tracking_type": tracking_type,
            "serial_numbers": serial_numbers,
            "quantity": qty,
            "rate": max(rate, 0),
            "amount": amount,
        })

    if not prepared:
        frappe.throw("Cart is empty.")

    return prepared, flt(subtotal, 2)


def _discount_amount(subtotal, discount_type, discount_value):
    discount_type = str(discount_type or "Amount").strip()
    if discount_type not in {"Amount", "Percent"}:
        frappe.throw("Discount type must be Amount or Percent.")

    value = max(flt(discount_value), 0)
    if discount_type == "Percent":
        value = min(value, 100)
        amount = subtotal * value / 100
    else:
        amount = value

    return discount_type, value, flt(min(amount, subtotal), 2)


def _validate_hold_context(channel, customer=None, price_list=None):
    if channel == "B2B" and not customer:
        frappe.throw("B2B held sales require a customer.")

    if customer and not frappe.db.exists("Ledgix Customer", customer):
        frappe.throw("Selected customer was not found.")
    if price_list and not frappe.db.exists("Ledgix Price List", price_list):
        frappe.throw("Selected price list was not found.")


def _retail_shift(channel):
    # B2B holds are back-office commercial context and must never inherit an
    # unrelated cashier register shift merely because the same user has one open.
    if channel != "Retail":
        return None

    shift = _get_open_shift_for_user()
    if not shift:
        frappe.throw("Please open a POS shift before holding a Retail sale.")
    return shift


def _can_access_hold(hold):
    if hold.cashier == frappe.session.user:
        return True
    return has_any_role(PRIVILEGED_HOLD_ROLES)


def _assert_resume_context(hold):
    if not _can_access_hold(hold):
        frappe.throw("You cannot access another cashier's held sale.", frappe.PermissionError)

    if hold.sale_channel == "Retail":
        active_shift = _get_open_shift_for_user()
        if not active_shift:
            frappe.throw("Open a POS shift before resuming this Retail sale.")
        if hold.shift and hold.shift != active_shift:
            frappe.throw("This held Retail sale belongs to a different POS shift.")


def _resume_cart_rows(hold):
    cart_items = []
    for row in hold.items:
        tracking_type = row.tracking_type or frappe.db.get_value(
            "Ledgix Item", row.item, "tracking_type"
        ) or "Normal"
        serial_numbers = _normalize_serial_selection(
            row.item,
            tracking_type,
            row.quantity,
            row.serial_numbers or "",
        )
        cart_items.append({
            "item": row.item,
            "item_name": row.item_name,
            "tracking_type": tracking_type,
            "serial_numbers": serial_numbers,
            "qty": flt(row.quantity),
            "rate": flt(row.rate),
            "current_stock": flt(
                frappe.db.get_value("Ledgix Item", row.item, "current_stock") or 0
            ),
        })
    return cart_items


@frappe.whitelist()
def hold_pos_v2_sale(
    cart_items=None,
    sale_channel="Retail",
    customer=None,
    price_list=None,
    discount_type="Amount",
    discount_value=0,
    notes=None,
):
    require_ledgix_cashier_or_above()

    channel = _normalize_channel(sale_channel)
    _validate_hold_context(channel, customer=customer, price_list=price_list)
    shift = _retail_shift(channel)
    rows, subtotal = _prepare_hold_rows(cart_items)
    discount_type, discount_value, discount_amount = _discount_amount(
        subtotal,
        discount_type,
        discount_value,
    )

    hold = frappe.new_doc("Ledgix POS Hold")
    hold.status = "Hold"
    hold.shift = shift
    hold.cashier = frappe.session.user
    hold.sale_channel = channel
    hold.customer = customer or ""
    hold.price_list = price_list or ""
    hold.subtotal = subtotal
    hold.discount_type = discount_type
    hold.discount_value = discount_value
    hold.discount_amount = discount_amount
    hold.total = flt(subtotal - discount_amount, 2)
    hold.notes = notes or ""
    for row in rows:
        hold.append("items", row)
    hold.insert(ignore_permissions=True)

    return {
        "success": True,
        "hold_id": hold.name,
        "sale_channel": channel,
        "customer": hold.customer or "",
        "price_list": hold.price_list or "",
        "total": flt(hold.total, 2),
    }


@frappe.whitelist()
def get_pos_v2_holds():
    require_ledgix_cashier_or_above()

    filters = {"status": "Hold"}
    if not has_any_role(PRIVILEGED_HOLD_ROLES):
        filters["cashier"] = frappe.session.user

    rows = frappe.get_all(
        "Ledgix POS Hold",
        filters=filters,
        fields=[
            "name",
            "creation",
            "cashier",
            "shift",
            "sale_channel",
            "customer",
            "price_list",
            "subtotal",
            "discount_amount",
            "total",
        ],
        order_by="creation desc",
        limit_page_length=100,
    )

    active_shift = _get_open_shift_for_user()
    visible = []
    for row in rows:
        channel = row.sale_channel or "Retail"
        if channel == "Retail" and row.shift and row.shift != active_shift:
            continue

        items = frappe.get_all(
            "Ledgix POS Hold Item",
            filters={
                "parent": row.name,
                "parenttype": "Ledgix POS Hold",
                "parentfield": "items",
            },
            fields=["item_name", "quantity"],
            order_by="idx asc",
            limit_page_length=4,
        )
        row["item_count"] = frappe.db.count(
            "Ledgix POS Hold Item",
            filters={
                "parent": row.name,
                "parenttype": "Ledgix POS Hold",
                "parentfield": "items",
            },
        )
        row["items_preview"] = ", ".join(
            f"{item.item_name} x {flt(item.quantity):g}" for item in items
        )
        visible.append(row)

    return {"success": True, "holds": visible}


@frappe.whitelist()
def resume_pos_v2_hold(hold_id=None):
    require_ledgix_cashier_or_above()
    if not hold_id:
        frappe.throw("Hold ID is required.")

    hold = frappe.get_doc("Ledgix POS Hold", hold_id)
    if hold.status != "Hold":
        frappe.throw("Only active held sales can be resumed.")
    _assert_resume_context(hold)

    # Revalidate serialized identity before consuming the hold. A serial may have
    # been sold or adjusted while the cart was parked.
    cart_items = _resume_cart_rows(hold)

    # A resumed hold is consumed. If the cashier needs to defer it again, the
    # current cart can be held as a fresh snapshot with current pricing context.
    hold.status = "Resumed"
    hold.save(ignore_permissions=True)

    return {
        "success": True,
        "hold_id": hold.name,
        "sale_channel": hold.sale_channel or "Retail",
        "customer": hold.customer or "",
        "price_list": hold.price_list or "",
        "cart_items": cart_items,
        "discount_type": hold.discount_type or "Amount",
        "discount_value": flt(hold.discount_value),
        "total": flt(hold.total),
    }


@frappe.whitelist()
def cancel_pos_v2_hold(hold_id=None):
    require_ledgix_cashier_or_above()
    if not hold_id:
        frappe.throw("Hold ID is required.")

    hold = frappe.get_doc("Ledgix POS Hold", hold_id)
    if hold.status != "Hold":
        frappe.throw("Only active held sales can be cancelled.")
    _assert_resume_context(hold)
    hold.status = "Cancelled"
    hold.save(ignore_permissions=True)
    return {"success": True, "hold_id": hold.name}
