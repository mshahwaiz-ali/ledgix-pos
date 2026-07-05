# ============================================================
# LEDGIX POS APIs
# ============================================================
# POS boot/search/sale/hold/return/receipt APIs.
# Public functions are re-exported from api.py to preserve existing JS paths.

import frappe
from frappe.utils import today, flt

from ledgix_saas.api.settings import (
    get_stock_control_mode,
    get_pos_theme_settings,
    save_pos_theme_settings,
    is_strict_inventory_mode,
    sale_matches_current_stock_mode,
)
from ledgix_saas.api.security import require_ledgix_cashier_or_above
from ledgix_saas.api.taxation import apply_tax_snapshot_to_sale_doc


def _has_doctype_field(doctype, fieldname):
    return frappe.get_meta(doctype).has_field(fieldname)


def _set_doc_field_if_exists(doc, fieldname, value):
    if _has_doctype_field(doc.doctype, fieldname):
        doc.set(fieldname, value)


def _get_open_pos_shift_for_current_user():
    filters = {"status": "Open", "docstatus": 0}

    if _has_doctype_field("Ledgix POS Shift", "opened_by"):
        filters["opened_by"] = frappe.session.user

    return frappe.db.get_value(
        "Ledgix POS Shift",
        filters,
        "name",
        order_by="creation desc"
    )


def _sale_response(sale, message=None):
    return {
        "success": True,
        "sale_id": sale.name,
        "invoice_number": sale.invoice_number,
        "total_amount": flt(sale.total_amount),
        "tax_amount": flt(sale.tax_amount),
        "grand_total": flt(sale.grand_total or sale.total_amount),
        "paid_amount": flt(sale.paid_amount),
        "remaining_amount": flt(sale.remaining_amount),
        "change_amount": flt(sale.change_amount),
        "fbr_status": getattr(sale, "fbr_status", None) or "",
        "fbr_invoice_number": getattr(sale, "fbr_invoice_number", None) or "",
        "fbr_qr_code": getattr(sale, "fbr_qr_code", None) or "",
        "message": message or f"Sale completed: {sale.name}"
    }

# ============================================================
# BARCODE / SKU ITEM LOOKUP APIs 
# ============================================================

@frappe.whitelist()
def get_item_by_barcode_or_sku(code):
    """
    Finds active Ledgix Item by barcode, SKU, or item code.
    Used by future POS barcode scanner/search flow.
    """
    require_ledgix_cashier_or_above()

    if not code:
        frappe.throw("Barcode / SKU / Item Code is required")

    code = code.strip()

    item = frappe.db.get_value(
        "Ledgix Item",
        {
            "active": 1,
            "barcode": code
        },
        [
            "name",
            "item_name",
            "item_code",
            "sku",
            "barcode",
            "unit",
            "tracking_type",
            "selling_price",
            "cost_price",
            "current_stock"
        ],
        as_dict=True
    )

    if not item:
        item = frappe.db.get_value(
            "Ledgix Item",
            {
                "active": 1,
                "sku": code
            },
            [
                "name",
                "item_name",
                "item_code",
                "sku",
                "barcode",
                "unit",
                "tracking_type",
                "selling_price",
                "cost_price",
                "current_stock"
            ],
            as_dict=True
        )

    if not item:
        item = frappe.db.get_value(
            "Ledgix Item",
            {
                "active": 1,
                "item_code": code
            },
            [
                "name",
                "item_name",
                "item_code",
                "sku",
                "barcode",
                "unit",
                "tracking_type",
                "selling_price",
                "cost_price",
                "current_stock"
            ],
            as_dict=True
        )

    if not item:
        return {
            "found": False,
            "message": "No active item found for this barcode / SKU / item code"
        }

    return {
        "found": True,
        "item": item
    }


# ============================================================
# POS BOOT / ITEM SEARCH APIs
# ============================================================

@frappe.whitelist()
def get_pos_boot_data():
    require_ledgix_cashier_or_above()

    categories = frappe.get_all(
        "Ledgix Category",
        filters={
            "is_active": 1
        },
        fields=[
            "name",
            "category_name",
            "category_icon",
            "custom_icon_image",
            "accent_color"
        ],
        order_by="category_name asc"
    )
    

    items = frappe.get_all(
        "Ledgix Item",
        filters={
            "active": 1
        },
        fields=[
            "name",
            "item_code",
            "item_name",
            "sku",
            "barcode",
            "category",
            "unit",
            "tracking_type",
            "selling_price",
            "current_stock"
        ],
        order_by="item_name asc",
        limit_page_length=60
    )

    return {
        "categories": categories,
        "items": items,
        "payment_methods": [
            "Cash",
            "Card",
            "JazzCash",
            "EasyPaisa",
            "Bank Transfer"
        ],
        "stock_control_mode": get_stock_control_mode(),
        "theme_settings": get_pos_theme_settings()
    }


@frappe.whitelist()
def search_pos_items(query=None, category=None):
    require_ledgix_cashier_or_above()

    filters = {
        "active": 1
    }

    if category and category != "All":
        filters["category"] = category

    or_filters = []

    if query:
        query = query.strip()

        or_filters = [
            ["Ledgix Item", "item_name", "like", f"%{query}%"],
            ["Ledgix Item", "item_code", "like", f"%{query}%"],
            ["Ledgix Item", "sku", "like", f"%{query}%"],
            ["Ledgix Item", "barcode", "like", f"%{query}%"]
        ]

    items = frappe.get_all(
        "Ledgix Item",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "item_code",
            "item_name",
            "sku",
            "barcode",
            "category",
            "unit",
            "tracking_type",
            "selling_price",
            "current_stock"
        ],
        order_by="item_name asc",
        limit_page_length=80
    )

    return {
        "items": items
    }


@frappe.whitelist()
def get_available_serials_for_pos(item, limit=100):
    require_ledgix_cashier_or_above()

    item = (item or "").strip()

    if not item:
        frappe.throw("Item is required")

    item_name = frappe.db.exists("Ledgix Item", item)

    if not item_name:
        frappe.throw(f"Item not found: {item}")

    limit = int(limit or 100)
    if limit <= 0:
        limit = 100
    limit = min(limit, 500)

    serials = frappe.get_all(
        "Ledgix Stock Serial",
        filters={
            "item": item_name,
            "status": "Available"
        },
        fields=[
            "name",
            "serial_no",
            "item",
            "purchase",
            "purchase_date",
            "status"
        ],
        order_by="purchase_date asc, creation asc",
        limit_page_length=limit
    )

    return {
        "item": item_name,
        "serials": [
            {
                "name": serial.name,
                "serial_number": serial.serial_no,
                "item": serial.item,
                "purchase": serial.purchase,
                "purchase_date": serial.purchase_date,
                "status": serial.status
            }
            for serial in serials
        ]
    }



# ============================================================
# POS SALE CREATION API
# ============================================================

def _client_sale_lock(client_sale_id):
    return frappe.cache().lock(
        f"ledgix:pos-sale-client-id:{client_sale_id}",
        timeout=120,
        blocking_timeout=0,
    )


@frappe.whitelist()
def create_pos_sale(cart_items=None, payments=None, discount_type="Amount", discount_value=0, client_sale_id=None):
    require_ledgix_cashier_or_above()

    client_sale_id = str(client_sale_id or "").strip()

    if client_sale_id and _has_doctype_field("Ledgix Sale", "client_sale_id"):
        try:
            with _client_sale_lock(client_sale_id):
                return _create_pos_sale_locked(cart_items, payments, discount_type, discount_value, client_sale_id)
        except Exception as exc:
            if "Lock" in exc.__class__.__name__:
                frappe.throw("Sale already processing. Please wait before retrying.")
            raise

    return _create_pos_sale_locked(cart_items, payments, discount_type, discount_value, client_sale_id)


def _create_pos_sale_locked(cart_items=None, payments=None, discount_type="Amount", discount_value=0, client_sale_id=None):
    cart_items = frappe.parse_json(cart_items) if isinstance(cart_items, str) else cart_items
    payments = frappe.parse_json(payments) if isinstance(payments, str) else payments

    if not cart_items:
        frappe.throw("Cart is empty")

    client_sale_id = str(client_sale_id or "").strip()

    if client_sale_id and _has_doctype_field("Ledgix Sale", "client_sale_id"):
        existing = frappe.db.get_value(
            "Ledgix Sale",
            {"client_sale_id": client_sale_id, "docstatus": 1},
            "name",
            order_by="creation desc"
        )
        if existing:
            return _sale_response(
                frappe.get_doc("Ledgix Sale", existing),
                message=f"Sale already completed: {existing}"
            )

        existing_draft = frappe.db.get_value(
            "Ledgix Sale",
            {"client_sale_id": client_sale_id, "docstatus": 0},
            "name",
            order_by="creation desc"
        )
        if existing_draft:
            frappe.throw("Sale is already processing. Refresh the invoice status before retrying.")

    shift_name = _get_open_pos_shift_for_current_user()

    if not shift_name:
        frappe.throw("Please open a POS shift before completing sale")

    customer = frappe.db.exists("Ledgix Customer", "Walk-in Customer")

    if not customer:
        customer = frappe.db.get_value("Ledgix Customer", {}, "name", order_by="creation asc")

    if not customer:
        frappe.throw("No Ledgix Customer found. Please create Walk-in Customer first.")

    subtotal = 0

    prepared_items = []

    for row in cart_items:
        item_name = row.get("item")
        qty = flt(row.get("qty"))
        rate = flt(row.get("rate"))

        if not item_name:
            frappe.throw("Item is required")

        if qty <= 0:
            frappe.throw("Quantity must be greater than zero")

        item = frappe.db.get_value(
            "Ledgix Item",
            item_name,
            [
                "name",
                "item_name",
                "selling_price",
                "cost_price",
                "current_stock"
            ],
            as_dict=True
        )

        if not item:
            frappe.throw(f"Item not found: {item_name}")

        if is_strict_inventory_mode() and flt(item.current_stock) < qty:
            frappe.throw(f"Not enough stock for {item.item_name}")

        if rate < flt(item.selling_price):
            frappe.throw(f"Rate cannot be below selling price for {item.item_name}")

        amount = qty * rate
        subtotal += amount

        prepared_items.append({
            "item": item.name,
            "quantity": qty,
            "rate": rate,
            "cost_price": flt(item.cost_price),
            "serial_numbers": row.get("serial_numbers") or ""
        })

    discount_value = flt(discount_value)
    discount_amount = 0

    if discount_type == "Percent":
        if discount_value > 100:
            discount_value = 100
        discount_amount = subtotal * discount_value / 100
    else:
        discount_amount = discount_value

    if discount_amount > subtotal:
        discount_amount = subtotal

    discount_ratio = 0

    if subtotal > 0 and discount_amount > 0:
        discount_ratio = discount_amount / subtotal

    sale = frappe.new_doc("Ledgix Sale")
    sale.customer = customer
    sale.sale_date = today()
    sale.pos_shift = shift_name
    sale.status = "Draft"
    _set_doc_field_if_exists(sale, "client_sale_id", client_sale_id)
    _set_doc_field_if_exists(sale, "subtotal_before_discount", subtotal)
    _set_doc_field_if_exists(sale, "discount_type", discount_type)
    _set_doc_field_if_exists(sale, "discount_value", discount_value)
    _set_doc_field_if_exists(sale, "discount_amount", discount_amount)

    for row in prepared_items:
        final_rate = flt(row["rate"]) * (1 - discount_ratio)
        final_amount = flt(row["quantity"]) * final_rate
        profit_per_unit = final_rate - flt(row["cost_price"])

        sale.append("items", {
            "item": row["item"],
            "quantity": row["quantity"],
            "serial_numbers": row.get("serial_numbers") or "",
            "rate": final_rate,
            "amount": final_amount,
            "cost_price": row["cost_price"],
            "profit_per_unit": profit_per_unit,
            "item_total_profit": profit_per_unit * flt(row["quantity"])
        })

    total_amount = subtotal - discount_amount
    sale.calculate_totals()
    apply_tax_snapshot_to_sale_doc(sale)
    payable_total = flt(sale.grand_total or sale.total_amount or total_amount)

    total_paid = 0

    if not payments:
        payments = []

    for payment in payments:
        method = payment.get("payment_method")
        amount = flt(payment.get("amount"))

        if not method or amount <= 0:
            continue

        total_paid += amount

        sale.append("payments", {
            "payment_method": method,
            "amount": amount,
            "is_cash_payment": 1 if method == "Cash" else 0,
            "reference_no": payment.get("reference_no") or "",
            "notes": payment.get("notes") or ""
        })

    sale.paid_amount = total_paid
    sale.remaining_amount = max(payable_total - total_paid, 0)
    sale.change_amount = max(total_paid - payable_total, 0)

    if sale.remaining_amount > 0 and not getattr(sale, "allow_partial_payment", 0):
        frappe.throw("Paid amount is less than payable total. Partial payment is not enabled for POS checkout.")

    sale.payment_status = "Paid" if sale.remaining_amount <= 0 else "Partial"

    sale.insert(ignore_permissions=True)
    sale.submit()

    return _sale_response(sale)


# ============================================================
# POS HOLD SALE APIs
# ============================================================

@frappe.whitelist()
def hold_pos_sale(cart_items=None, discount_type="Amount", discount_value=0, notes=None):
    require_ledgix_cashier_or_above()

    cart_items = frappe.parse_json(cart_items) if isinstance(cart_items, str) else cart_items

    if not cart_items:
        frappe.throw("Cart is empty")

    shift_name = _get_open_pos_shift_for_current_user()

    if not shift_name:
        frappe.throw("Please open a POS shift before holding sale")

    subtotal = 0
    prepared_items = []

    for row in cart_items:
        item_name = row.get("item")
        qty = flt(row.get("qty"))
        rate = flt(row.get("rate"))

        if not item_name:
            frappe.throw("Item is required")

        if qty <= 0:
            frappe.throw("Quantity must be greater than zero")

        item = frappe.db.get_value(
            "Ledgix Item",
            item_name,
            ["name", "item_name", "selling_price"],
            as_dict=True
        )

        if not item:
            frappe.throw(f"Item not found: {item_name}")

        amount = qty * rate
        subtotal += amount

        prepared_items.append({
            "item": item.name,
            "item_name": item.item_name,
            "quantity": qty,
            "rate": rate,
            "amount": amount
        })

    discount_value = flt(discount_value)
    discount_amount = 0

    if discount_type == "Percent":
        if discount_value > 100:
            discount_value = 100
        discount_amount = subtotal * discount_value / 100
    else:
        discount_amount = discount_value

    if discount_amount > subtotal:
        discount_amount = subtotal

    total = subtotal - discount_amount

    hold = frappe.new_doc("Ledgix POS Hold")
    hold.status = "Hold"
    hold.shift = shift_name
    hold.cashier = frappe.session.user
    hold.subtotal = subtotal
    hold.discount_type = discount_type
    hold.discount_value = discount_value
    hold.discount_amount = discount_amount
    hold.total = total

    if notes:
        hold.notes = notes

    for row in prepared_items:
        hold.append("items", row)

    hold.insert(ignore_permissions=True)

    return {
        "success": True,
        "hold_id": hold.name,
        "total": flt(total),
        "message": f"Sale held: {hold.name}"
    }


@frappe.whitelist()
def get_held_pos_sales():
    require_ledgix_cashier_or_above()

    shift_name = _get_open_pos_shift_for_current_user()

    if not shift_name:
        frappe.throw("Please open a POS shift first")

    holds = frappe.get_all(
        "Ledgix POS Hold",
        filters={
            "status": "Hold",
            "shift": shift_name
        },
        fields=[
            "name",
            "creation",
            "cashier",
            "subtotal",
            "discount_amount",
            "total"
        ],
        order_by="creation desc"
    )

    for hold in holds:

        item_count = frappe.db.count(
            "Ledgix POS Hold Item",
            filters={
                "parent": hold.name,
                "parenttype": "Ledgix POS Hold",
                "parentfield": "items"
            }
        )

        hold["item_count"] = item_count

        items = frappe.get_all(
            "Ledgix POS Hold Item",
            filters={
                "parent": hold.name,
                "parenttype": "Ledgix POS Hold",
                "parentfield": "items"
            },
            fields=[
                "item_name",
                "quantity"
            ],
            order_by="idx asc"
        )

        hold["items_preview"] = ", ".join([
            f"{item.item_name} x {flt(item.quantity):g}"
            for item in items
        ])

    return {
        "success": True,
        "holds": holds
    }

@frappe.whitelist()
def resume_held_pos_sale(hold_id=None):
    require_ledgix_cashier_or_above()

    if not hold_id:
        frappe.throw("Hold ID is required")

    hold = frappe.get_doc("Ledgix POS Hold", hold_id)

    if hold.status != "Hold":
        frappe.throw("Only held sales can be resumed")

    cart_items = []

    for row in hold.items:
        cart_items.append({
            "item": row.item,
            "item_name": row.item_name,
            "qty": flt(row.quantity),
            "rate": flt(row.rate),
            "stock": flt(frappe.db.get_value("Ledgix Item", row.item, "current_stock") or 0)
        })

    return {
        "success": True,
        "hold_id": hold.name,
        "cart_items": cart_items,
        "discount_type": hold.discount_type or "Amount",
        "discount_value": flt(hold.discount_value),
        "total": flt(hold.total)
    }

@frappe.whitelist()
def delete_held_pos_sale(hold_id=None):
    require_ledgix_cashier_or_above()

    if not hold_id:
        frappe.throw("Hold ID is required")

    hold = frappe.get_doc("Ledgix POS Hold", hold_id)

    if hold.status != "Hold":
        frappe.throw("Only held sales can be cancelled")

    hold.status = "Cancelled"
    hold.save(ignore_permissions=True)

    return {
        "success": True,
        "hold_id": hold.name,
        "message": f"Held sale cancelled: {hold.name}"
    }



# ============================================================
# POS SALES RETURN APIs
# ============================================================


def _return_item_has_original_row():
    return _has_doctype_field("Ledgix Sales Return Item", "original_sale_item_row")


def _row_returned_qty(original_sale, sale_item_row, legacy_remainder_by_item=None):
    row_qty = 0
    item = sale_item_row.item

    if _return_item_has_original_row():
        row_qty = frappe.db.sql("""
            SELECT COALESCE(SUM(ri.quantity), 0)
            FROM `tabLedgix Sales Return Item` ri
            INNER JOIN `tabLedgix Sales Return` r ON r.name = ri.parent
            WHERE r.original_sale = %s
              AND r.docstatus = 1
              AND ri.original_sale_item_row = %s
        """, (original_sale, sale_item_row.name))[0][0]

    legacy_qty = 0
    if legacy_remainder_by_item is not None:
        available_for_legacy = max(flt(sale_item_row.quantity) - flt(row_qty), 0)
        legacy_qty = min(flt(legacy_remainder_by_item.get(item)), available_for_legacy)
        legacy_remainder_by_item[item] = max(flt(legacy_remainder_by_item.get(item)) - legacy_qty, 0)

    return flt(row_qty) + flt(legacy_qty)


def _legacy_returned_qty_by_item(original_sale):
    rows = frappe.db.sql("""
        SELECT ri.item, COALESCE(SUM(ri.quantity), 0) AS quantity
        FROM `tabLedgix Sales Return Item` ri
        INNER JOIN `tabLedgix Sales Return` r ON r.name = ri.parent
        WHERE r.original_sale = %s
          AND r.docstatus = 1
          AND (ri.original_sale_item_row IS NULL OR ri.original_sale_item_row = '')
        GROUP BY ri.item
    """, (original_sale,), as_dict=True)

    return {row.item: flt(row.quantity) for row in rows}


def _requested_return_qty_by_item(return_items):
    requested = {}

    for row in return_items:
        item = row.get("item")
        qty = flt(row.get("return_qty") or row.get("quantity") or row.get("qty"))

        if not item or qty <= 0:
            continue

        requested[item] = flt(requested.get(item)) + qty

    return requested


def _return_allocation_from_sale_item(sale_item, qty):
    return {
        "item": sale_item.item,
        "quantity": qty,
        "rate": flt(sale_item.rate),
        "amount": flt(qty) * flt(sale_item.rate),
        "cost_price": flt(sale_item.cost_price),
        "profit_per_unit": flt(sale_item.profit_per_unit),
        "item_total_profit": flt(qty) * flt(sale_item.profit_per_unit),
        "original_sale_item_row": sale_item.name,
    }


def _returned_qty_by_sale_row(sale):
    legacy_remainder = _legacy_returned_qty_by_item(sale.name)
    returned_by_row = {}

    for sale_item in sorted(sale.items, key=lambda row: (row.idx or 0, row.name or "")):
        returned_by_row[sale_item.name] = _row_returned_qty(sale.name, sale_item, legacy_remainder)

    return returned_by_row


def _allocate_return_items_from_sale(sale, return_items):
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
            frappe.throw("Selected return row does not belong to the original sale.")

        requested_item = requested_row.get("item")
        if requested_item and requested_item != sale_item.item:
            frappe.throw("Selected return item does not match the original sale row.")

        available_qty = max(flt(sale_item.quantity) - flt(returned_by_row.get(sale_item.name)), 0)

        if requested_qty > available_qty:
            frappe.throw(
                f"Return quantity for item {sale_item.item} exceeds remaining returnable quantity ({available_qty:g})."
            )

        allocations.append(_return_allocation_from_sale_item(sale_item, requested_qty))
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
        frappe.throw(f"Return quantity for item {item} exceeds remaining returnable quantity ({flt(qty):g} over).")

    return allocations


@frappe.whitelist()
def get_pos_sale_for_return(sale_id=None):
    require_ledgix_cashier_or_above()

    if not sale_id:
        frappe.throw("Sale ID or Invoice Number is required")

    sale_id = str(sale_id).strip()

    sale_name = None

    # Direct Ledgix Sale ID
    if frappe.db.exists("Ledgix Sale", sale_id):
        sale_name = sale_id

    # Customer invoice number e.g. INV-00029
    if not sale_name:
        sale_name = frappe.db.get_value(
            "Ledgix Sale",
            {
                "invoice_number": sale_id,
                "docstatus": 1
            },
            "name"
        )

    if not sale_name:
        frappe.throw(f"No submitted sale found for: {sale_id}")

    sale = frappe.get_doc("Ledgix Sale", sale_name)

    if sale.docstatus != 1:
        frappe.throw("Only submitted sales can be returned")

    if not sale_matches_current_stock_mode(sale.name):
        current_mode = get_stock_control_mode()
        frappe.throw(
            f"This invoice belongs to a different POS mode. Current mode: {current_mode}."
        )

    items = []

    legacy_remainder = _legacy_returned_qty_by_item(sale.name)

    for row in sorted(sale.items, key=lambda sale_row: (sale_row.idx or 0, sale_row.name or "")):
        already_returned_qty = _row_returned_qty(sale.name, row, legacy_remainder)

        returnable_qty = flt(row.quantity) - flt(already_returned_qty)

        if returnable_qty > 0:
            items.append({
                "item": row.item,
                "original_sale_item_row": row.name,
                "item_name": frappe.db.get_value("Ledgix Item", row.item, "item_name") or row.item,
                "sold_qty": flt(row.quantity),
                "already_returned_qty": flt(already_returned_qty),
                "returnable_qty": flt(returnable_qty),
                "return_qty": 0,
                "rate": flt(row.rate),
                "amount": 0,
                "cost_price": flt(row.cost_price),
                "profit_per_unit": flt(row.profit_per_unit),
                "item_total_profit": 0
            })

    return {
        "success": True,
        "sale_id": sale.name,
        "invoice_number": sale.invoice_number,
        "customer": sale.customer,
        "sale_date": sale.sale_date,
        "items": items
    }

@frappe.whitelist()
def create_pos_sales_return(original_sale=None, return_items=None):
    require_ledgix_cashier_or_above()

    return_items = frappe.parse_json(return_items) if isinstance(return_items, str) else return_items

    if not original_sale:
        frappe.throw("Original sale is required")

    if not return_items:
        frappe.throw("No return items selected")

    sale = frappe.get_doc("Ledgix Sale", original_sale)

    if sale.docstatus != 1:
        frappe.throw("Only submitted sales can be returned")

    if not sale_matches_current_stock_mode(sale.name):
        current_mode = get_stock_control_mode()
        frappe.throw(
            f"This invoice belongs to a different POS mode. Current mode: {current_mode}."
        )

    sales_return = frappe.new_doc("Ledgix Sales Return")
    sales_return.original_sale = sale.name
    sales_return.customer = sale.customer

    allocations = _allocate_return_items_from_sale(sale, return_items)

    if not allocations:
        frappe.throw("Please enter return quantity for at least one item")

    for row in allocations:
        sales_return.append("items", row)

    sales_return.insert(ignore_permissions=True)
    sales_return.submit()

    return {
        "success": True,
        "return_id": sales_return.name,
        "original_sale": sale.name,
        "customer": sale.customer,
        "total_amount": flt(sales_return.total_amount),
        "message": f"Return completed: {sales_return.name}"
    }

@frappe.whitelist()
def get_recent_pos_sales(limit=10, offset=0, query=None):
    require_ledgix_cashier_or_above()

    limit = int(limit or 10)
    offset = int(offset or 0)

    if limit not in [10, 20, 30, 40, 50]:
        limit = 10

    if offset < 0:
        offset = 0

    query = (query or "").strip()
    stock_control_mode = get_stock_control_mode()

    where_conditions = [
        "s.docstatus = 1"
    ]

    values = {
        "limit": limit,
        "offset": offset
    }

    if stock_control_mode == "Strict Inventory":
        where_conditions.append("""
            EXISTS (
                SELECT 1
                FROM `tabLedgix Stock Movement` sm
                WHERE
                    sm.reference_doctype = 'Ledgix Sale'
                    AND sm.reference_name = s.name
                    AND sm.docstatus = 1
            )
        """)
    else:
        where_conditions.append("""
            NOT EXISTS (
                SELECT 1
                FROM `tabLedgix Stock Movement` sm
                WHERE
                    sm.reference_doctype = 'Ledgix Sale'
                    AND sm.reference_name = s.name
                    AND sm.docstatus = 1
            )
        """)

    if query:
        values["query"] = f"%{query}%"
        where_conditions.append("""
            (
                s.name LIKE %(query)s
                OR s.invoice_number LIKE %(query)s
                OR s.customer LIKE %(query)s
            )
        """)

    where_sql = " AND ".join(where_conditions)

    total_count = frappe.db.sql(f"""
        SELECT COUNT(*)
        FROM `tabLedgix Sale` s
        WHERE {where_sql}
    """, values)[0][0]

    sales = frappe.db.sql(f"""
        SELECT
            s.name,
            s.name AS sale_id,
            s.invoice_number,
            s.creation,
            s.sale_date,
            s.customer,
            s.pos_shift,
            s.total_amount,
            s.tax_amount,
            s.grand_total,
            s.paid_amount,
            s.change_amount,
            s.payment_status,
            s.owner
        FROM `tabLedgix Sale` s
        WHERE {where_sql}
        ORDER BY s.creation DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, values, as_dict=True)

    for sale in sales:
        item_count = frappe.db.count(
            "Ledgix Sale Item",
            filters={
                "parent": sale.name,
                "parenttype": "Ledgix Sale",
                "parentfield": "items"
            }
        )

        items = frappe.get_all(
            "Ledgix Sale Item",
            filters={
                "parent": sale.name,
                "parenttype": "Ledgix Sale",
                "parentfield": "items"
            },
            fields=[
                "item",
                "quantity"
            ],
            order_by="idx asc",
            limit_page_length=4
        )

        item_labels = []

        for item in items:
            item_name = frappe.db.get_value("Ledgix Item", item.item, "item_name") or item.item
            item_labels.append(f"{item_name} x {flt(item.quantity):g}")

        preview = ", ".join(item_labels)

        if item_count > 4:
            preview = preview + f" +{item_count - 4} more"

        payments = frappe.get_all(
            "Ledgix Sale Payment",
            filters={
                "parent": sale.name,
                "parenttype": "Ledgix Sale",
                "parentfield": "payments"
            },
            fields=[
                "payment_method",
                "amount"
            ],
            order_by="idx asc"
        )

        payment_methods = []

        for payment in payments:
            if payment.payment_method and payment.payment_method not in payment_methods:
                payment_methods.append(payment.payment_method)

        sale["item_count"] = item_count
        sale["items_preview"] = preview or "No item details"
        sale["payment_methods"] = " + ".join(payment_methods) if payment_methods else "Payment"

    return {
        "success": True,
        "sales": sales,
        "limit": limit,
        "offset": offset,
        "total_count": total_count,
        "has_more": offset + limit < total_count,
        "stock_control_mode": stock_control_mode
    }

@frappe.whitelist()
def get_pos_sale_receipt_data(sale_id=None):
    require_ledgix_cashier_or_above()

    if not sale_id:
        frappe.throw("Sale ID is required")

    sale = frappe.get_doc("Ledgix Sale", sale_id)

    if sale.docstatus != 1:
        frappe.throw("Only submitted sales can be printed")

    items = []

    for row in sale.items:
        item_name = frappe.db.get_value("Ledgix Item", row.item, "item_name") or row.item

        items.append({
            "item": row.item,
            "item_name": item_name,
            "qty": flt(row.quantity),
            "rate": flt(row.rate),
            "amount": flt(row.amount)
        })

    payments = []

    for row in sale.payments:
        payments.append({
            "payment_method": row.payment_method,
            "amount": flt(row.amount),
            "reference_no": row.reference_no or "",
            "notes": row.notes or ""
        })

    return {
        "success": True,
        "receipt": {
            "sale_id": sale.name,
            "invoice_number": sale.invoice_number,
            "date_time": sale.creation,
            "customer": sale.customer,
            "cashier": sale.owner,
            "shift_id": sale.pos_shift,
            "items": items,
            "subtotal": flt(sale.total_amount) + flt(getattr(sale, "discount_amount", 0)),
            "discount": flt(getattr(sale, "discount_amount", 0)),
            "tax": flt(getattr(sale, "tax_amount", 0)),
            "total": flt(getattr(sale, "grand_total", 0) or sale.total_amount),
            "paid": flt(sale.paid_amount),
            "remaining": flt(sale.remaining_amount),
            "change": flt(sale.change_amount),
            "payment_status": sale.payment_status,
            "fbr_status": getattr(sale, "fbr_status", None) or "",
            "fbr_invoice_number": getattr(sale, "fbr_invoice_number", None) or "",
            "fbr_qr_code": getattr(sale, "fbr_qr_code", None) or "",
            "payments": payments
        }
    }

# ============================================================
