import re

import frappe
from frappe.utils import cint, flt, today


# ============================================================
# STOCK IDENTITY / LOT TRACKING HELPERS
# ============================================================

def get_item_tracking_type(item_code):
    if not item_code:
        return "Normal"

    tracking_type = frappe.db.get_value("Ledgix Item", item_code, "tracking_type")
    return tracking_type or "Normal"


def lock_item_stock_row(item_code):
    if not item_code:
        frappe.throw("Item is required for stock lock.")
    frappe.db.sql(
        "SELECT name FROM `tabLedgix Item` WHERE name=%s FOR UPDATE",
        (item_code,),
    )


def get_locked_current_stock(item_code):
    lock_item_stock_row(item_code)
    return flt(frappe.db.get_value("Ledgix Item", item_code, "current_stock"))


def is_lot_based_item(item_code):
    return get_item_tracking_type(item_code) == "Lot Based"


def is_serial_based_item(item_code):
    return get_item_tracking_type(item_code) == "Serial Based"


def parse_serial_numbers(value):
    serials = []
    seen = set()

    for serial_no in re.split(r"[\n,;]+", value or ""):
        serial_no = serial_no.strip()

        if not serial_no:
            continue

        if serial_no in seen:
            frappe.throw(f"Duplicate serial number {serial_no} in serial number field.")

        seen.add(serial_no)
        serials.append(serial_no)

    return serials


def _validate_serial_qty(item_code, qty, serials):
    qty = flt(qty)

    if qty != cint(qty):
        frappe.throw(f"Serial Based item {item_code} quantity must be a whole number.")

    if cint(qty) != len(serials):
        frappe.throw(
            f"Serial Based item {item_code} requires {cint(qty)} serial number(s), "
            f"but {len(serials)} provided."
        )


def _get_required_serial_qty(item_code, qty):
    qty = flt(qty)

    if qty != cint(qty):
        frappe.throw(f"Serial Based item {item_code} quantity must be a whole number.")

    return cint(qty)


def _has_serial_number_input(value):
    for serial_no in re.split(r"[\n,;]+", value or ""):
        if serial_no.strip():
            return True

    return False


def _write_serial_numbers(row, serials):
    row.serial_numbers = "\n".join(serials)


def _serial_item_prefix(item_code):
    prefix = re.sub(r"[^A-Za-z0-9]+", "", item_code or "ITEM").upper()
    return (prefix or "ITEM")[:12]


def _generate_purchase_serial_numbers(item_code, qty):
    serials = []
    serial_date = today().replace("-", "")
    prefix = _serial_item_prefix(item_code)

    while len(serials) < qty:
        serial_no = f"LXSN-{serial_date}-{prefix}-{frappe.generate_hash(length=8).upper()}"

        if serial_no in serials:
            continue

        if frappe.db.exists("Ledgix Stock Serial", {"serial_no": serial_no}):
            continue

        serials.append(serial_no)

    return serials


def _select_available_sale_serial_numbers(item_code, qty, excluded_serials=None):
    excluded_serials = set(excluded_serials or [])
    serial_rows = frappe.get_all(
        "Ledgix Stock Serial",
        filters={
            "item": item_code,
            "status": "Available",
        },
        fields=["serial_no", "purchase_date", "creation"],
        order_by="purchase_date asc, creation asc",
        limit_page_length=qty + len(excluded_serials) + 50,
    )

    serials = []

    for serial in serial_rows:
        if serial.serial_no in excluded_serials:
            continue

        serials.append(serial.serial_no)

        if len(serials) >= qty:
            break

    if len(serials) != qty:
        frappe.throw(
            f"Serial Based item {item_code} requires {qty} available serial number(s), "
            f"but only {len(serials)} available."
        )

    return serials


def _select_return_serial_numbers(item_code, original_sale, qty, excluded_serials=None):
    excluded_serials = set(excluded_serials or [])
    serial_rows = frappe.get_all(
        "Ledgix Stock Serial",
        filters={
            "item": item_code,
            "sale": original_sale,
            "status": "Sold",
        },
        fields=["serial_no", "sold_date", "creation"],
        order_by="sold_date asc, creation asc",
        limit_page_length=qty + len(excluded_serials) + 50,
    )

    serials = []

    for serial in serial_rows:
        if serial.serial_no in excluded_serials:
            continue

        serials.append(serial.serial_no)

        if len(serials) >= qty:
            break

    if len(serials) != qty:
        frappe.throw(
            f"Serial Based item {item_code} requires {qty} sold serial number(s) from Sale {original_sale}, "
            f"but only {len(serials)} returnable serial number(s) are available."
        )

    return serials


def normalize_purchase_serials(purchase_doc):
    for row in purchase_doc.get("items") or []:
        if not is_serial_based_item(row.item):
            continue

        if _has_serial_number_input(getattr(row, "serial_numbers", None)):
            continue

        qty = _get_required_serial_qty(row.item, row.quantity)
        _write_serial_numbers(row, _generate_purchase_serial_numbers(row.item, qty))


def normalize_sale_serials(sale_doc):
    selected_serials = set()

    for row in sale_doc.get("items") or []:
        if not is_serial_based_item(row.item):
            continue

        if _has_serial_number_input(getattr(row, "serial_numbers", None)):
            for serial_no in parse_serial_numbers(getattr(row, "serial_numbers", None)):
                selected_serials.add(serial_no)
            continue

        qty = _get_required_serial_qty(row.item, row.quantity)
        serials = _select_available_sale_serial_numbers(row.item, qty, selected_serials)
        _write_serial_numbers(row, serials)
        selected_serials.update(serials)


def normalize_sales_return_serials(return_doc):
    if not getattr(return_doc, "original_sale", None):
        return

    selected_serials = set()

    for row in return_doc.get("items") or []:
        if not is_serial_based_item(row.item):
            continue

        if _has_serial_number_input(getattr(row, "serial_numbers", None)):
            for serial_no in parse_serial_numbers(getattr(row, "serial_numbers", None)):
                selected_serials.add(serial_no)
            continue

        qty = _get_required_serial_qty(row.item, row.quantity)
        serials = _select_return_serial_numbers(
            row.item,
            return_doc.original_sale,
            qty,
            selected_serials,
        )
        _write_serial_numbers(row, serials)
        selected_serials.update(serials)


def create_stock_lot_from_purchase_item(purchase_doc, purchase_item):
    if not purchase_item or not purchase_item.item:
        return None

    if not is_lot_based_item(purchase_item.item):
        return None

    existing_lot = frappe.db.exists(
        "Ledgix Stock Lot",
        {
            "purchase": purchase_doc.name,
            "purchase_item_row": purchase_item.name,
            "item": purchase_item.item,
        },
    )

    if existing_lot:
        create_purchase_lot_allocation(purchase_doc, purchase_item, existing_lot)
        return existing_lot

    qty = flt(purchase_item.quantity)
    rate = flt(purchase_item.rate)

    if qty <= 0:
        return None

    lot = frappe.new_doc("Ledgix Stock Lot")
    lot.item = purchase_item.item
    lot.purchase = purchase_doc.name
    lot.purchase_item_row = purchase_item.name
    lot.supplier = purchase_doc.supplier
    lot.purchase_date = purchase_doc.purchase_date
    lot.purchased_qty = qty
    lot.sold_qty = 0
    lot.returned_qty = 0
    lot.remaining_qty = qty
    lot.cost_rate = rate
    lot.total_cost = qty * rate
    lot.status = "Open"

    lot.insert(ignore_permissions=True)
    create_purchase_lot_allocation(purchase_doc, purchase_item, lot.name)

    return lot.name


def create_purchase_lot_allocation(purchase_doc, purchase_item, lot_name):
    if not lot_name or not purchase_item or not purchase_item.item:
        return None

    qty = flt(purchase_item.quantity)

    if qty <= 0:
        return None

    existing_allocation = frappe.db.exists(
        "Ledgix Stock Lot Allocation",
        {
            "stock_lot": lot_name,
            "purchase": purchase_doc.name,
            "purchase_item_row": purchase_item.name,
            "allocation_type": "Purchase",
        },
    )

    if existing_allocation:
        return existing_allocation

    allocation = frappe.new_doc("Ledgix Stock Lot Allocation")
    allocation.stock_lot = lot_name
    allocation.item = purchase_item.item
    allocation.purchase = purchase_doc.name
    allocation.purchase_item_row = purchase_item.name
    allocation.allocation_type = "Purchase"
    allocation.qty = qty
    allocation.cost_rate = flt(purchase_item.rate)
    allocation.sale_rate = 0
    allocation.profit_amount = 0
    allocation.transaction_date = purchase_doc.purchase_date or today()
    allocation.is_reversed = 0
    allocation.insert(ignore_permissions=True)

    return allocation.name


def create_stock_lots_for_purchase(purchase_doc):
    created_lots = []

    for row in purchase_doc.get("items") or []:
        lot_name = create_stock_lot_from_purchase_item(purchase_doc, row)
        if lot_name:
            created_lots.append(lot_name)

    return created_lots


def reverse_purchase_lots(purchase_doc):
    lots = frappe.get_all(
        "Ledgix Stock Lot",
        filters={
            "purchase": purchase_doc.name,
            "status": ["!=", "Cancelled"],
        },
        fields=[
            "name",
            "item",
            "purchase_item_row",
            "purchased_qty",
            "remaining_qty",
            "sold_qty",
            "returned_qty",
            "cost_rate",
        ],
        order_by="creation asc",
    )

    if not lots:
        return []

    reversed_allocations = []

    for lot in lots:
        active_downstream_allocation = frappe.db.exists(
            "Ledgix Stock Lot Allocation",
            {
                "stock_lot": lot.name,
                "allocation_type": ["in", ["Sale", "Return"]],
                "is_reversed": 0,
            },
        )

        if active_downstream_allocation:
            frappe.throw(
                f"Cannot cancel Purchase {purchase_doc.name}. Lot {lot.name} already has active Sale/Return allocation."
            )

        if flt(lot.sold_qty) != 0 or flt(lot.returned_qty) != 0:
            frappe.throw(
                f"Cannot cancel Purchase {purchase_doc.name}. Lot {lot.name} has non-zero sold/returned quantities."
            )

        if flt(lot.remaining_qty) != flt(lot.purchased_qty):
            frappe.throw(
                f"Cannot cancel Purchase {purchase_doc.name}. Lot {lot.name} remaining quantity does not match purchased quantity."
            )

        purchase_allocations = frappe.get_all(
            "Ledgix Stock Lot Allocation",
            filters={
                "stock_lot": lot.name,
                "purchase": purchase_doc.name,
                "allocation_type": "Purchase",
                "is_reversed": 0,
            },
            fields=["name", "qty", "cost_rate"],
        )

        for allocation in purchase_allocations:
            frappe.db.set_value(
                "Ledgix Stock Lot Allocation",
                allocation.name,
                "is_reversed",
                1,
                update_modified=False,
            )

            cancel_allocation = frappe.new_doc("Ledgix Stock Lot Allocation")
            cancel_allocation.stock_lot = lot.name
            cancel_allocation.item = lot.item
            cancel_allocation.purchase = purchase_doc.name
            cancel_allocation.purchase_item_row = lot.purchase_item_row
            cancel_allocation.allocation_type = "Cancel"
            cancel_allocation.qty = flt(allocation.qty)
            cancel_allocation.cost_rate = flt(allocation.cost_rate)
            cancel_allocation.sale_rate = 0
            cancel_allocation.profit_amount = 0
            cancel_allocation.transaction_date = purchase_doc.purchase_date or today()
            cancel_allocation.is_reversed = 1
            cancel_allocation.insert(ignore_permissions=True)
            reversed_allocations.append(cancel_allocation.name)

        frappe.db.set_value(
            "Ledgix Stock Lot",
            lot.name,
            {
                "remaining_qty": 0,
                "status": "Cancelled",
            },
            update_modified=False,
        )

    return reversed_allocations


# ============================================================
# FIFO SALE LOT ALLOCATION
# ============================================================

def get_fifo_lots(item_code, for_update=False):
    if for_update:
        return frappe.db.sql(
            """
            SELECT name, remaining_qty, cost_rate, purchase_date
            FROM `tabLedgix Stock Lot`
            WHERE item = %s AND status = 'Open' AND remaining_qty > 0
            ORDER BY purchase_date asc, creation asc
            FOR UPDATE
            """,
            (item_code,),
            as_dict=True,
        )

    return frappe.get_all(
        "Ledgix Stock Lot",
        filters={
            "item": item_code,
            "status": "Open",
            "remaining_qty": [">", 0],
        },
        fields=["name", "remaining_qty", "cost_rate", "purchase_date"],
        order_by="purchase_date asc, creation asc",
    )


def allocate_sale_item_fifo(sale_doc, sale_item):
    if not is_lot_based_item(sale_item.item):
        return []

    existing_allocation = frappe.db.exists(
        "Ledgix Stock Lot Allocation",
        {
            "sale": sale_doc.name,
            "sale_item_row": sale_item.name,
            "allocation_type": "Sale",
            "is_reversed": 0,
        },
    )

    if existing_allocation:
        return []

    required_qty = flt(sale_item.quantity)

    if required_qty <= 0:
        return []

    fifo_lots = get_fifo_lots(sale_item.item, for_update=True)
    allocations = []

    for lot in fifo_lots:
        if required_qty <= 0:
            break

        available_qty = flt(lot.remaining_qty)

        if available_qty <= 0:
            continue

        consume_qty = min(required_qty, available_qty)

        allocation = frappe.new_doc("Ledgix Stock Lot Allocation")
        allocation.stock_lot = lot.name
        allocation.item = sale_item.item
        allocation.sale = sale_doc.name
        allocation.sale_item_row = sale_item.name
        allocation.allocation_type = "Sale"
        allocation.qty = consume_qty
        allocation.cost_rate = flt(lot.cost_rate)
        allocation.sale_rate = flt(sale_item.rate)
        allocation.profit_amount = (
            flt(sale_item.rate) - flt(lot.cost_rate)
        ) * consume_qty
        allocation.transaction_date = sale_doc.sale_date or sale_doc.creation
        allocation.is_reversed = 0
        allocation.insert(ignore_permissions=True)

        lot_doc = frappe.get_doc("Ledgix Stock Lot", lot.name)
        lot_doc.sold_qty = flt(lot_doc.sold_qty) + consume_qty
        lot_doc.remaining_qty = flt(lot_doc.remaining_qty) - consume_qty

        if flt(lot_doc.remaining_qty) <= 0:
            lot_doc.status = "Closed"

        lot_doc.save(ignore_permissions=True)

        allocations.append({
            "lot": lot.name,
            "qty": consume_qty,
        })

        required_qty -= consume_qty

    if required_qty > 0:
        frappe.throw(
            f"Not enough FIFO stock lots available for item {sale_item.item}"
        )

    return allocations


def allocate_sale_fifo(sale_doc):
    all_allocations = []

    for row in sale_doc.get("items") or []:
        allocations = allocate_sale_item_fifo(sale_doc, row)

        if allocations:
            all_allocations.extend(allocations)

    return all_allocations


# ============================================================
# FIFO SALE CANCEL REVERSAL
# ============================================================

def reverse_sale_fifo_allocations(sale_doc):
    existing_cancel = frappe.db.exists(
        "Ledgix Stock Lot Allocation",
        {
            "sale": sale_doc.name,
            "allocation_type": "Cancel",
        },
    )

    if existing_cancel:
        return []

    submitted_return = frappe.db.exists(
        "Ledgix Sales Return",
        {
            "original_sale": sale_doc.name,
            "docstatus": 1,
        },
    )

    if submitted_return:
        frappe.throw("Cancel submitted Sales Returns before cancelling this Sale.")

    sale_allocations = frappe.get_all(
        "Ledgix Stock Lot Allocation",
        filters={
            "sale": sale_doc.name,
            "allocation_type": "Sale",
            "is_reversed": 0,
        },
        fields=[
            "name",
            "stock_lot",
            "item",
            "sale_item_row",
            "qty",
            "cost_rate",
            "sale_rate",
            "profit_amount",
            "transaction_date",
        ],
        order_by="creation asc",
    )

    if not sale_allocations:
        return []

    reversed_allocations = []

    for allocation in sale_allocations:
        qty = flt(allocation.qty)

        if qty <= 0:
            continue

        lot_doc = frappe.get_doc("Ledgix Stock Lot", allocation.stock_lot)

        new_sold_qty = flt(lot_doc.sold_qty) - qty
        _validate_lot_quantity_update(allocation.stock_lot, allocation.item, qty, lot_doc, new_sold_qty)

        new_remaining_qty = flt(lot_doc.remaining_qty) + qty
        new_status = "Open" if new_remaining_qty > 0 else lot_doc.status

        frappe.db.set_value(
            "Ledgix Stock Lot",
            allocation.stock_lot,
            {
                "sold_qty": new_sold_qty,
                "remaining_qty": new_remaining_qty,
                "status": new_status,
            },
            update_modified=False,
        )

        frappe.db.set_value(
            "Ledgix Stock Lot Allocation",
            allocation.name,
            "is_reversed",
            1,
            update_modified=False,
        )

        reverse_allocation = frappe.new_doc("Ledgix Stock Lot Allocation")
        reverse_allocation.stock_lot = allocation.stock_lot
        reverse_allocation.item = allocation.item
        reverse_allocation.sale = sale_doc.name
        reverse_allocation.sale_item_row = allocation.sale_item_row
        reverse_allocation.allocation_type = "Cancel"
        reverse_allocation.qty = qty
        reverse_allocation.cost_rate = flt(allocation.cost_rate)
        reverse_allocation.sale_rate = flt(allocation.sale_rate)
        reverse_allocation.profit_amount = -flt(allocation.profit_amount)
        reverse_allocation.transaction_date = sale_doc.sale_date or sale_doc.creation
        reverse_allocation.is_reversed = 1
        reverse_allocation.insert(ignore_permissions=True)

        reversed_allocations.append(reverse_allocation.name)

    return reversed_allocations


# ============================================================
# FIFO SALES RETURN LOT RESTORATION
# ============================================================

def _get_return_transaction_date(return_doc):
    return getattr(return_doc, "return_date", None) or today()


def _validate_lot_quantity_update(
    lot_name,
    item,
    attempted_qty,
    lot_doc,
    new_sold_qty=None,
    new_returned_qty=None,
    new_remaining_qty=None,
):
    sold_qty = flt(lot_doc.sold_qty)
    returned_qty = flt(lot_doc.returned_qty)
    remaining_qty = flt(lot_doc.remaining_qty)

    if (
        (new_sold_qty is not None and flt(new_sold_qty) < 0)
        or (new_returned_qty is not None and flt(new_returned_qty) < 0)
        or (new_remaining_qty is not None and flt(new_remaining_qty) < 0)
    ):
        frappe.throw(
            f"Invalid lot quantity update for lot {lot_name}. "
            f"Item: {item}. Attempted qty: {attempted_qty}. "
            f"Current balances - Sold: {sold_qty}, Returned: {returned_qty}, Remaining: {remaining_qty}."
        )


def _get_already_restored_qty(sale, item, stock_lot, sale_item_row):
    return flt(frappe.db.sql(
        """
        SELECT COALESCE(SUM(qty), 0)
        FROM `tabLedgix Stock Lot Allocation`
        WHERE sale = %s
          AND item = %s
          AND stock_lot = %s
          AND sale_item_row = %s
          AND allocation_type = 'Return'
          AND is_reversed = 0
        """,
        (sale, item, stock_lot, sale_item_row),
    )[0][0])


def restore_sale_return_fifo_allocations(return_doc):
    if not getattr(return_doc, "original_sale", None):
        return []

    existing_return = frappe.db.exists(
        "Ledgix Stock Lot Allocation",
        {
            "sales_return": return_doc.name,
            "allocation_type": "Return",
            "is_reversed": 0,
        },
    )

    if existing_return:
        return []

    restored_allocations = []

    for return_item in return_doc.get("items") or []:
        if not is_lot_based_item(return_item.item):
            continue

        remaining_return_qty = flt(return_item.quantity)

        if remaining_return_qty <= 0:
            continue

        sale_allocation_filters = {
            "sale": return_doc.original_sale,
            "allocation_type": "Sale",
            "is_reversed": 0,
            "item": return_item.item,
        }

        original_sale_item_row = getattr(return_item, "original_sale_item_row", None)
        if original_sale_item_row:
            sale_allocation_filters["sale_item_row"] = original_sale_item_row

        sale_allocations = frappe.get_all(
            "Ledgix Stock Lot Allocation",
            filters=sale_allocation_filters,
            fields=[
                "name",
                "stock_lot",
                "item",
                "sale_item_row",
                "qty",
                "cost_rate",
                "sale_rate",
                "profit_amount",
            ],
            order_by="creation desc",
        )

        for allocation in sale_allocations:
            if remaining_return_qty <= 0:
                break

            allocated_qty = flt(allocation.qty)
            already_restored_qty = _get_already_restored_qty(
                return_doc.original_sale,
                allocation.item,
                allocation.stock_lot,
                allocation.sale_item_row,
            )
            available_restore_qty = allocated_qty - already_restored_qty

            if available_restore_qty <= 0:
                continue

            restored_qty = min(remaining_return_qty, available_restore_qty)
            profit_per_unit = (
                flt(allocation.profit_amount) / allocated_qty
                if allocated_qty > 0 else 0
            )

            lot_doc = frappe.get_doc("Ledgix Stock Lot", allocation.stock_lot)
            new_remaining_qty = flt(lot_doc.remaining_qty) + restored_qty
            new_returned_qty = flt(lot_doc.returned_qty) + restored_qty
            new_status = "Open" if new_remaining_qty > 0 else lot_doc.status

            frappe.db.set_value(
                "Ledgix Stock Lot",
                allocation.stock_lot,
                {
                    "remaining_qty": new_remaining_qty,
                    "returned_qty": new_returned_qty,
                    "status": new_status,
                },
                update_modified=False,
            )

            return_allocation = frappe.new_doc("Ledgix Stock Lot Allocation")
            return_allocation.stock_lot = allocation.stock_lot
            return_allocation.item = allocation.item
            return_allocation.sale = return_doc.original_sale
            return_allocation.sale_item_row = allocation.sale_item_row
            return_allocation.sales_return = return_doc.name
            return_allocation.allocation_type = "Return"
            return_allocation.qty = restored_qty
            return_allocation.cost_rate = flt(allocation.cost_rate)
            return_allocation.sale_rate = flt(allocation.sale_rate)
            return_allocation.profit_amount = -(profit_per_unit * restored_qty)
            return_allocation.transaction_date = _get_return_transaction_date(return_doc)
            return_allocation.is_reversed = 0
            return_allocation.insert(ignore_permissions=True)

            restored_allocations.append(return_allocation.name)
            remaining_return_qty -= restored_qty

        if remaining_return_qty > 0:
            frappe.throw(
                f"Could not match returned lot quantity for item {return_item.item}. "
                f"Unmatched quantity: {remaining_return_qty}"
            )

    return restored_allocations


# ============================================================
# FIFO SALES RETURN CANCEL REVERSAL
# ============================================================

def reverse_sales_return_fifo_allocations(return_doc):
    existing_cancel = frappe.db.exists(
        "Ledgix Stock Lot Allocation",
        {
            "sales_return": return_doc.name,
            "allocation_type": "Cancel",
        },
    )

    if existing_cancel:
        return []

    return_allocations = frappe.get_all(
        "Ledgix Stock Lot Allocation",
        filters={
            "sales_return": return_doc.name,
            "allocation_type": "Return",
            "is_reversed": 0,
        },
        fields=[
            "name",
            "stock_lot",
            "item",
            "sale",
            "sale_item_row",
            "qty",
            "cost_rate",
            "sale_rate",
            "profit_amount",
        ],
        order_by="creation asc",
    )

    if not return_allocations:
        return []

    reversed_allocations = []

    for allocation in return_allocations:
        qty = flt(allocation.qty)

        if qty <= 0:
            continue

        lot_doc = frappe.get_doc("Ledgix Stock Lot", allocation.stock_lot)
        new_remaining_qty = flt(lot_doc.remaining_qty) - qty
        new_returned_qty = flt(lot_doc.returned_qty) - qty
        _validate_lot_quantity_update(
            allocation.stock_lot,
            allocation.item,
            qty,
            lot_doc,
            new_returned_qty=new_returned_qty,
            new_remaining_qty=new_remaining_qty,
        )

        new_status = "Closed" if new_remaining_qty <= 0 else "Open"

        frappe.db.set_value(
            "Ledgix Stock Lot",
            allocation.stock_lot,
            {
                "remaining_qty": new_remaining_qty,
                "returned_qty": new_returned_qty,
                "status": new_status,
            },
            update_modified=False,
        )

        frappe.db.set_value(
            "Ledgix Stock Lot Allocation",
            allocation.name,
            "is_reversed",
            1,
            update_modified=False,
        )

        cancel_allocation = frappe.new_doc("Ledgix Stock Lot Allocation")
        cancel_allocation.stock_lot = allocation.stock_lot
        cancel_allocation.item = allocation.item
        cancel_allocation.sale = allocation.sale
        cancel_allocation.sale_item_row = allocation.sale_item_row
        cancel_allocation.sales_return = return_doc.name
        cancel_allocation.allocation_type = "Cancel"
        cancel_allocation.qty = qty
        cancel_allocation.cost_rate = flt(allocation.cost_rate)
        cancel_allocation.sale_rate = flt(allocation.sale_rate)
        cancel_allocation.profit_amount = -flt(allocation.profit_amount)
        cancel_allocation.transaction_date = today()
        cancel_allocation.is_reversed = 1
        cancel_allocation.insert(ignore_permissions=True)

        reversed_allocations.append(cancel_allocation.name)

    return reversed_allocations


# ============================================================
# SERIAL STOCK IDENTITY
# ============================================================

def validate_purchase_serial_numbers(purchase_doc):
    for row in purchase_doc.get("items") or []:
        if not is_serial_based_item(row.item):
            continue

        serials = parse_serial_numbers(getattr(row, "serial_numbers", None))
        _validate_serial_qty(row.item, row.quantity, serials)


def validate_sale_serial_numbers(sale_doc):
    for row in sale_doc.get("items") or []:
        if not is_serial_based_item(row.item):
            continue

        serials = parse_serial_numbers(getattr(row, "serial_numbers", None))
        _validate_serial_qty(row.item, row.quantity, serials)


def validate_sales_return_serial_numbers(return_doc):
    for row in return_doc.get("items") or []:
        if not is_serial_based_item(row.item):
            continue

        if not getattr(return_doc, "original_sale", None):
            frappe.throw(f"Sales Return for Serial Based item {row.item} requires an original Sale.")

        serials = parse_serial_numbers(getattr(row, "serial_numbers", None))
        _validate_serial_qty(row.item, row.quantity, serials)


def create_stock_serials_for_purchase(purchase_doc):
    created_serials = []

    for row in purchase_doc.get("items") or []:
        if not is_serial_based_item(row.item):
            continue

        serials = parse_serial_numbers(getattr(row, "serial_numbers", None))
        _validate_serial_qty(row.item, row.quantity, serials)

        for serial_no in serials:
            existing_serial = frappe.db.get_value(
                "Ledgix Stock Serial",
                {"serial_no": serial_no},
                ["name", "purchase", "purchase_item_row", "status"],
                as_dict=True,
            )

            if existing_serial:
                if (
                    existing_serial.purchase == purchase_doc.name
                    and existing_serial.purchase_item_row == row.name
                    and existing_serial.status != "Cancelled"
                ):
                    continue

                frappe.throw(f"Serial number {serial_no} already exists for item {row.item}.")

            serial_doc = frappe.new_doc("Ledgix Stock Serial")
            serial_doc.serial_no = serial_no
            serial_doc.item = row.item
            serial_doc.status = "Available"
            serial_doc.purchase = purchase_doc.name
            serial_doc.purchase_item_row = row.name
            serial_doc.supplier = getattr(purchase_doc, "supplier", None)
            serial_doc.purchase_date = getattr(purchase_doc, "purchase_date", None)
            serial_doc.cost_rate = flt(getattr(row, "rate", 0))
            serial_doc.insert(ignore_permissions=True)
            created_serials.append(serial_doc.name)

    return created_serials


def reverse_purchase_serials(purchase_doc):
    serials = frappe.get_all(
        "Ledgix Stock Serial",
        filters={"purchase": purchase_doc.name, "status": ["!=", "Cancelled"]},
        fields=["name", "serial_no", "item", "status", "sale", "sales_return"],
        order_by="creation asc",
    )

    for serial in serials:
        if serial.status in ("Sold", "Returned") or serial.sale or serial.sales_return:
            frappe.throw(
                f"Cannot cancel Purchase {purchase_doc.name}. Serial {serial.serial_no} "
                f"for item {serial.item} has already been sold or returned."
            )

        if serial.status != "Available":
            frappe.throw(
                f"Cannot cancel Purchase {purchase_doc.name}. Serial {serial.serial_no} "
                f"for item {serial.item} is not Available."
            )

    cancelled = []

    for serial in serials:
        frappe.db.set_value(
            "Ledgix Stock Serial",
            serial.name,
            "status",
            "Cancelled",
            update_modified=False,
        )
        cancelled.append(serial.name)

    return cancelled


def allocate_sale_serials(sale_doc):
    allocated_serials = []

    for row in sale_doc.get("items") or []:
        if not is_serial_based_item(row.item):
            continue

        serials = parse_serial_numbers(getattr(row, "serial_numbers", None))
        _validate_serial_qty(row.item, row.quantity, serials)

        for serial_no in serials:
            serial_doc = frappe.db.get_value(
                "Ledgix Stock Serial",
                {"serial_no": serial_no},
                ["name", "item", "status", "sale", "sale_item_row"],
                as_dict=True,
            )

            if not serial_doc:
                frappe.throw(f"Serial number {serial_no} does not exist for item {row.item}.")

            if serial_doc.item != row.item:
                frappe.throw(
                    f"Serial number {serial_no} belongs to item {serial_doc.item}, not {row.item}."
                )

            if serial_doc.sale == sale_doc.name and serial_doc.sale_item_row == row.name:
                allocated_serials.append(serial_doc.name)
                continue

            if serial_doc.status != "Available":
                frappe.throw(
                    f"Serial number {serial_no} for item {row.item} is not Available. "
                    f"Current status: {serial_doc.status}."
                )

            frappe.db.set_value(
                "Ledgix Stock Serial",
                serial_doc.name,
                {
                    "status": "Sold",
                    "sale": sale_doc.name,
                    "sale_item_row": row.name,
                    "customer": getattr(sale_doc, "customer", None),
                    "sold_date": getattr(sale_doc, "sale_date", None) or today(),
                },
                update_modified=False,
            )
            allocated_serials.append(serial_doc.name)

    return allocated_serials


def reverse_sale_serial_allocations(sale_doc):
    submitted_return = frappe.db.exists(
        "Ledgix Sales Return",
        {
            "original_sale": sale_doc.name,
            "docstatus": 1,
        },
    )

    if submitted_return:
        frappe.throw("Cancel submitted Sales Returns before cancelling this Sale.")

    serials = frappe.get_all(
        "Ledgix Stock Serial",
        filters={"sale": sale_doc.name},
        fields=["name", "serial_no", "item", "status", "sales_return"],
        order_by="creation asc",
    )

    reversed_serials = []

    for serial in serials:
        if serial.sales_return:
            frappe.throw(
                f"Cannot cancel Sale {sale_doc.name}. Serial {serial.serial_no} "
                f"for item {serial.item} is linked to Sales Return {serial.sales_return}."
            )

        if serial.status == "Available":
            frappe.throw(
                f"Cannot cancel Sale {sale_doc.name}. Serial {serial.serial_no} "
                f"for item {serial.item} has already been returned."
            )

        if serial.status != "Sold":
            continue

        frappe.db.set_value(
            "Ledgix Stock Serial",
            serial.name,
            {
                "status": "Available",
                "sale": None,
                "sale_item_row": None,
                "customer": None,
                "sold_date": None,
            },
            update_modified=False,
        )
        reversed_serials.append(serial.name)

    return reversed_serials


def restore_sales_return_serials(return_doc):
    if not getattr(return_doc, "original_sale", None):
        return []

    restored_serials = []

    for row in return_doc.get("items") or []:
        if not is_serial_based_item(row.item):
            continue

        serials = parse_serial_numbers(getattr(row, "serial_numbers", None))
        _validate_serial_qty(row.item, row.quantity, serials)

        for serial_no in serials:
            serial_doc = frappe.db.get_value(
                "Ledgix Stock Serial",
                {"serial_no": serial_no},
                [
                    "name",
                    "item",
                    "status",
                    "sale",
                    "sales_return",
                    "return_item_row",
                ],
                as_dict=True,
            )

            if not serial_doc:
                frappe.throw(f"Serial number {serial_no} does not exist for item {row.item}.")

            if serial_doc.item != row.item:
                frappe.throw(
                    f"Serial number {serial_no} belongs to item {serial_doc.item}, not {row.item}."
                )

            if serial_doc.sale != return_doc.original_sale:
                frappe.throw(
                    f"Serial number {serial_no} was not sold in original Sale {return_doc.original_sale}."
                )

            if (
                serial_doc.sales_return == return_doc.name
                and serial_doc.return_item_row == row.name
            ):
                restored_serials.append(serial_doc.name)
                continue

            if serial_doc.status != "Sold":
                frappe.throw(
                    f"Serial number {serial_no} for item {row.item} cannot be returned. "
                    f"Current status: {serial_doc.status}."
                )

            frappe.db.set_value(
                "Ledgix Stock Serial",
                serial_doc.name,
                {
                    "status": "Available",
                    "sales_return": return_doc.name,
                    "return_item_row": row.name,
                    "return_date": _get_return_transaction_date(return_doc),
                },
                update_modified=False,
            )
            restored_serials.append(serial_doc.name)

    return restored_serials


def reverse_sales_return_serials(return_doc):
    serials = frappe.get_all(
        "Ledgix Stock Serial",
        filters={"sales_return": return_doc.name},
        fields=["name", "serial_no", "item", "status"],
        order_by="creation asc",
    )

    reversed_serials = []

    for serial in serials:
        if serial.status == "Sold":
            continue

        if serial.status != "Available":
            frappe.throw(
                f"Cannot cancel Sales Return {return_doc.name}. Serial {serial.serial_no} "
                f"for item {serial.item} is not Available."
            )

        frappe.db.set_value(
            "Ledgix Stock Serial",
            serial.name,
            {
                "status": "Sold",
                "sales_return": None,
                "return_item_row": None,
                "return_date": None,
            },
            update_modified=False,
        )
        reversed_serials.append(serial.name)

    return reversed_serials


# ============================================================
# MANUAL / OPENING STOCK IDENTITY
# ============================================================

def create_stock_lot_from_manual_entry(item, qty, rate, movement_name):
    if not item or not is_lot_based_item(item):
        return None

    qty = flt(qty)
    if qty <= 0:
        return None

    lot = frappe.new_doc("Ledgix Stock Lot")
    lot.item = item
    lot.purchase_date = today()
    lot.purchased_qty = qty
    lot.sold_qty = 0
    lot.returned_qty = 0
    lot.remaining_qty = qty
    lot.cost_rate = flt(rate)
    lot.total_cost = qty * flt(rate)
    lot.status = "Open"
    lot.insert(ignore_permissions=True)

    allocation = frappe.new_doc("Ledgix Stock Lot Allocation")
    allocation.stock_lot = lot.name
    allocation.item = item
    allocation.purchase_item_row = movement_name or ""
    allocation.allocation_type = "Purchase"
    allocation.qty = qty
    allocation.cost_rate = flt(rate)
    allocation.sale_rate = 0
    allocation.profit_amount = 0
    allocation.transaction_date = today()
    allocation.is_reversed = 0
    allocation.insert(ignore_permissions=True)

    return lot.name


def reduce_lots_fifo_for_manual_out(item, qty):
    if not item or not is_lot_based_item(item):
        return []

    required_qty = flt(qty)
    if required_qty <= 0:
        return []

    fifo_lots = get_fifo_lots(item, for_update=True)
    allocations = []

    for lot in fifo_lots:
        if required_qty <= 0:
            break

        available_qty = flt(lot.remaining_qty)
        if available_qty <= 0:
            continue

        consume_qty = min(required_qty, available_qty)

        allocation = frappe.new_doc("Ledgix Stock Lot Allocation")
        allocation.stock_lot = lot.name
        allocation.item = item
        allocation.allocation_type = "Sale"
        allocation.qty = consume_qty
        allocation.cost_rate = flt(lot.cost_rate)
        allocation.sale_rate = 0
        allocation.profit_amount = 0
        allocation.transaction_date = today()
        allocation.is_reversed = 0
        allocation.insert(ignore_permissions=True)

        lot_doc = frappe.get_doc("Ledgix Stock Lot", lot.name)
        lot_doc.sold_qty = flt(lot_doc.sold_qty) + consume_qty
        lot_doc.remaining_qty = flt(lot_doc.remaining_qty) - consume_qty
        if flt(lot_doc.remaining_qty) <= 0:
            lot_doc.status = "Closed"
        lot_doc.save(ignore_permissions=True)

        allocations.append({"lot": lot.name, "qty": consume_qty})
        required_qty -= consume_qty

    if required_qty > 0:
        frappe.throw(f"Not enough FIFO stock lots available for item {item}.")

    return allocations


def create_stock_serials_for_manual_entry(item, qty, serial_numbers=None, cost_rate=0):
    if not item or not is_serial_based_item(item):
        return 0

    required_qty = _get_required_serial_qty(item, qty)
    serials = parse_serial_numbers(serial_numbers) if _has_serial_number_input(serial_numbers) else []

    if not serials:
        serials = _generate_purchase_serial_numbers(item, required_qty)

    _validate_serial_qty(item, qty, serials)

    for serial_no in serials:
        if frappe.db.exists("Ledgix Stock Serial", {"serial_no": serial_no}):
            frappe.throw(f"Serial number {serial_no} already exists for item {item}.")

        serial_doc = frappe.new_doc("Ledgix Stock Serial")
        serial_doc.serial_no = serial_no
        serial_doc.item = item
        serial_doc.status = "Available"
        serial_doc.purchase_date = today()
        serial_doc.cost_rate = flt(cost_rate)
        serial_doc.insert(ignore_permissions=True)

    return len(serials)
