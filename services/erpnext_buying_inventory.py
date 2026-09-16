from __future__ import annotations

"""ERPNext-native buying and inventory authority for Ledgix Phase 7.

This module is the compatibility boundary for new Ledgix buying/stock operations.
It deliberately writes only standard ERPNext purchase, payment and stock documents.
Legacy Ledgix Purchase / Stock Movement / Stock Lot / Stock Serial documents remain
historical migration sources and are never mutated here.
"""

from collections.abc import Iterable

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

MONEY_TOLERANCE = 0.005


def _company(company: str | None = None) -> str:
    company = str(company or frappe.defaults.get_user_default("Company") or "").strip()
    if not company:
        company = frappe.db.get_single_value("Global Defaults", "default_company") or ""
    if not company or not frappe.db.exists("Company", company):
        frappe.throw(_("A valid ERPNext Company is required."))
    return company


def _lock_company(company: str) -> None:
    frappe.db.sql("select name from `tabCompany` where name = %s for update", company)


def _resolve_supplier(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        frappe.throw(_("Supplier is required."))
    if frappe.db.exists("Supplier", value):
        return value
    name = frappe.db.get_value("Supplier", {"custom_ledgix_legacy_supplier": value}, "name")
    if name:
        return name
    if frappe.db.exists("Ledgix Supplier", value):
        supplier_name = frappe.db.get_value("Ledgix Supplier", value, "supplier_name")
        if supplier_name and frappe.db.exists("Supplier", supplier_name):
            return supplier_name
    frappe.throw(_("No migrated ERPNext Supplier is mapped to {0}.").format(value))


def _resolve_item(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        frappe.throw(_("Item is required."))
    if frappe.db.exists("Item", value):
        return value
    name = frappe.db.get_value("Item", {"custom_ledgix_legacy_item": value}, "name")
    if name:
        return name
    if frappe.db.exists("Ledgix Item", value):
        item_code = frappe.db.get_value("Ledgix Item", value, "item_code")
        if item_code and frappe.db.exists("Item", item_code):
            return item_code
    frappe.throw(_("No migrated ERPNext Item is mapped to {0}.").format(value))


def _resolve_mode_of_payment(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        frappe.throw(_("Mode of Payment is required."))
    if frappe.db.exists("Mode of Payment", value):
        return value
    name = frappe.db.get_value(
        "Mode of Payment", {"custom_ledgix_legacy_payment_method": value}, "name"
    )
    if name:
        return name
    frappe.throw(_("No migrated ERPNext Mode of Payment is mapped to {0}.").format(value))


def _resolve_warehouse(warehouse: str | None, company: str) -> str:
    warehouse = str(warehouse or "").strip()
    if warehouse:
        if not frappe.db.exists(
            "Warehouse", {"name": warehouse, "company": company, "is_group": 0, "disabled": 0}
        ):
            frappe.throw(_("Warehouse {0} is not an active leaf warehouse for {1}.").format(warehouse, company))
        return warehouse

    # ERPNext v15 owns the general stock default on Stock Settings, not Company.
    # Stock Settings is global, so only accept its default when that Warehouse
    # actually belongs to the requested Company; otherwise choose a company leaf.
    default = str(frappe.db.get_single_value("Stock Settings", "default_warehouse") or "").strip()
    if default and frappe.db.exists(
        "Warehouse",
        {"name": default, "company": company, "is_group": 0, "disabled": 0},
    ):
        return default

    rows = frappe.get_all(
        "Warehouse",
        filters={"company": company, "is_group": 0, "disabled": 0},
        pluck="name",
        order_by="name asc",
        limit=1,
    )
    if not rows:
        frappe.throw(_("No active leaf Warehouse exists for {0}.").format(company))
    return rows[0]


def default_warehouse(company: str | None = None) -> str:
    company = _company(company)
    return _resolve_warehouse(None, company)


def _active_by_client_id(doctype: str, fieldname: str, client_id: str | None):
    client_id = str(client_id or "").strip()
    if not client_id:
        return None
    name = frappe.db.get_value(
        doctype,
        {fieldname: client_id, "docstatus": ["!=", 2]},
        "name",
    )
    return frappe.get_doc(doctype, name) if name else None


def _item_row(raw: dict, company: str, fallback_warehouse: str | None = None) -> dict:
    item_code = _resolve_item(raw.get("item_code") or raw.get("item") or raw.get("name"))
    qty = flt(raw.get("qty") or raw.get("quantity"))
    if qty <= 0:
        frappe.throw(_("Purchase quantity for item {0} must be greater than zero.").format(item_code))

    stock_uom = frappe.db.get_value("Item", item_code, "stock_uom") or "Nos"
    is_stock_item = cint(frappe.db.get_value("Item", item_code, "is_stock_item"))
    row = {
        "item_code": item_code,
        "qty": qty,
        "uom": str(raw.get("uom") or stock_uom),
        "rate": max(flt(raw.get("rate")), 0),
    }
    if raw.get("schedule_date"):
        row["schedule_date"] = raw.get("schedule_date")
    if is_stock_item:
        row["warehouse"] = _resolve_warehouse(raw.get("warehouse") or fallback_warehouse, company)
    return row


def _purchase_items(items, company: str, warehouse: str | None = None) -> list[dict]:
    if isinstance(items, str):
        items = frappe.parse_json(items)
    rows = [_item_row(dict(raw), company, warehouse) for raw in (items or [])]
    if not rows:
        frappe.throw(_("At least one purchase item is required."))
    return rows


def stock_snapshot(item: str, *, warehouse: str | None = None, company: str | None = None) -> dict:
    company = _company(company)
    item_code = _resolve_item(item)
    warehouse = _resolve_warehouse(warehouse, company)
    row = frappe.db.get_value(
        "Bin",
        {"item_code": item_code, "warehouse": warehouse},
        ["actual_qty", "reserved_qty", "projected_qty", "valuation_rate", "stock_value"],
        as_dict=True,
    ) or {}
    return {
        "item": item_code,
        "warehouse": warehouse,
        "actual_qty": flt(row.get("actual_qty")),
        "reserved_qty": flt(row.get("reserved_qty")),
        "projected_qty": flt(row.get("projected_qty")),
        "valuation_rate": flt(row.get("valuation_rate")),
        "stock_value": flt(row.get("stock_value")),
        "authority": "ERPNext Bin + Stock Ledger Entry",
    }


def available_serials(
    item: str,
    *,
    warehouse: str | None = None,
    company: str | None = None,
    limit: int = 200,
) -> list[dict]:
    company = _company(company)
    item_code = _resolve_item(item)
    if not cint(frappe.db.get_value("Item", item_code, "has_serial_no")):
        frappe.throw(_("Serial selection is only available for ERPNext serial-tracked items."))
    warehouse = _resolve_warehouse(warehouse, company) if warehouse else None
    limit = min(max(int(limit or 200), 1), 500)
    filters = {"item_code": item_code, "warehouse": ["is", "set"]}
    if warehouse:
        filters["warehouse"] = warehouse

    meta = frappe.get_meta("Serial No")
    fields = ["name", "item_code", "warehouse", "creation"]
    for optional in ("purchase_document_no", "purchase_date"):
        if meta.has_field(optional):
            fields.append(optional)
    rows = frappe.get_all(
        "Serial No",
        filters=filters,
        fields=fields,
        order_by="creation asc, name asc",
        limit_page_length=limit,
    )
    result = []
    for row in rows:
        result.append(
            {
                "name": row.name,
                "serial_no": row.name,
                "item_code": row.item_code,
                "warehouse": row.warehouse,
                "purchase": row.get("purchase_document_no") or "",
                "purchase_date": row.get("purchase_date") or row.get("creation"),
            }
        )
    return result


def create_purchase_order(
    *,
    supplier: str,
    items,
    company: str | None = None,
    warehouse: str | None = None,
    client_purchase_id: str | None = None,
    source: str = "Ledgix Phase 7",
    submit: bool = True,
):
    company = _company(company)
    _lock_company(company)
    existing = _active_by_client_id("Purchase Order", "custom_ledgix_client_purchase_id", client_purchase_id)
    if existing:
        existing.flags.ledgix_duplicate_client_purchase = True
        return existing

    supplier = _resolve_supplier(supplier)
    warehouse = _resolve_warehouse(warehouse, company)
    rows = _purchase_items(items, company, warehouse)
    for row in rows:
        row["schedule_date"] = row.get("schedule_date") or nowdate()

    doc = frappe.get_doc(
        {
            "doctype": "Purchase Order",
            "company": company,
            "supplier": supplier,
            "transaction_date": nowdate(),
            "schedule_date": nowdate(),
            "set_warehouse": warehouse,
            "custom_ledgix_client_purchase_id": str(client_purchase_id or "").strip(),
            "custom_ledgix_buying_source": source,
            "items": rows,
        }
    )
    doc.insert(ignore_permissions=True)
    if submit:
        doc.submit()
    doc.reload()
    doc.flags.ledgix_duplicate_client_purchase = False
    return doc


def create_purchase_receipt(
    *,
    purchase_order: str,
    client_receipt_id: str | None = None,
    warehouse: str | None = None,
    source: str = "Ledgix Phase 7",
):
    order = frappe.get_doc("Purchase Order", purchase_order)
    if order.docstatus != 1:
        frappe.throw(_("A submitted Purchase Order is required."))
    _lock_company(order.company)
    existing = _active_by_client_id("Purchase Receipt", "custom_ledgix_client_receipt_id", client_receipt_id)
    if existing:
        existing.flags.ledgix_duplicate_client_receipt = True
        return existing

    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

    receipt = make_purchase_receipt(order.name)
    resolved_warehouse = _resolve_warehouse(warehouse or order.set_warehouse, order.company)
    receipt.set_warehouse = resolved_warehouse
    receipt.custom_ledgix_client_receipt_id = str(client_receipt_id or "").strip()
    receipt.custom_ledgix_client_purchase_id = order.get("custom_ledgix_client_purchase_id") or ""
    receipt.custom_ledgix_buying_source = source
    for row in receipt.items:
        if cint(frappe.db.get_value("Item", row.item_code, "is_stock_item")):
            row.warehouse = resolved_warehouse
    receipt.insert(ignore_permissions=True)
    receipt.submit()
    receipt.reload()
    receipt.flags.ledgix_duplicate_client_receipt = False
    return receipt


def create_purchase_invoice_from_receipt(
    *,
    purchase_receipt: str,
    client_invoice_id: str | None = None,
    source: str = "Ledgix Phase 7",
):
    receipt = frappe.get_doc("Purchase Receipt", purchase_receipt)
    if receipt.docstatus != 1:
        frappe.throw(_("A submitted Purchase Receipt is required."))
    _lock_company(receipt.company)
    existing = _active_by_client_id(
        "Purchase Invoice", "custom_ledgix_client_purchase_invoice_id", client_invoice_id
    )
    if existing:
        existing.flags.ledgix_duplicate_client_purchase_invoice = True
        return existing

    from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice

    invoice = make_purchase_invoice(receipt.name)
    invoice.custom_ledgix_client_purchase_invoice_id = str(client_invoice_id or "").strip()
    invoice.custom_ledgix_client_purchase_id = receipt.get("custom_ledgix_client_purchase_id") or ""
    invoice.custom_ledgix_buying_source = source
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    invoice.reload()
    invoice.flags.ledgix_duplicate_client_purchase_invoice = False
    return invoice


def create_direct_purchase_invoice(
    *,
    supplier: str,
    items,
    company: str | None = None,
    warehouse: str | None = None,
    update_stock: bool = True,
    client_purchase_id: str | None = None,
    client_invoice_id: str | None = None,
    source: str = "Ledgix Phase 7 Direct Purchase",
):
    company = _company(company)
    _lock_company(company)
    existing = _active_by_client_id(
        "Purchase Invoice", "custom_ledgix_client_purchase_invoice_id", client_invoice_id
    )
    if existing:
        existing.flags.ledgix_duplicate_client_purchase_invoice = True
        return existing

    supplier = _resolve_supplier(supplier)
    warehouse = _resolve_warehouse(warehouse, company)
    rows = _purchase_items(items, company, warehouse)
    doc = frappe.get_doc(
        {
            "doctype": "Purchase Invoice",
            "company": company,
            "supplier": supplier,
            "posting_date": nowdate(),
            "set_warehouse": warehouse,
            "update_stock": 1 if update_stock else 0,
            "custom_ledgix_client_purchase_id": str(client_purchase_id or "").strip(),
            "custom_ledgix_client_purchase_invoice_id": str(client_invoice_id or "").strip(),
            "custom_ledgix_buying_source": source,
            "items": rows,
        }
    )
    doc.insert(ignore_permissions=True)
    doc.submit()
    doc.reload()
    doc.flags.ledgix_duplicate_client_purchase_invoice = False
    return doc


def post_supplier_payment(
    *,
    purchase_invoice: str,
    mode_of_payment: str,
    client_payment_id: str | None = None,
    reference_number: str | None = None,
    amount: float | None = None,
    source: str = "Ledgix Phase 7 Supplier Payment",
):
    invoice = frappe.get_doc("Purchase Invoice", purchase_invoice)
    if invoice.docstatus != 1 or cint(invoice.is_return):
        frappe.throw(_("A submitted non-return Purchase Invoice is required."))
    _lock_company(invoice.company)
    existing = _active_by_client_id("Payment Entry", "custom_ledgix_client_payment_id", client_payment_id)
    if existing:
        existing.flags.ledgix_duplicate_client_payment = True
        return existing

    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    mode = _resolve_mode_of_payment(mode_of_payment)
    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mode, "company": invoice.company},
        "default_account",
    )
    if not account:
        frappe.throw(_("Mode of Payment {0} has no default account for {1}.").format(mode, invoice.company))

    payment = get_payment_entry("Purchase Invoice", invoice.name)
    payment.mode_of_payment = mode
    payment.paid_from = account
    target = flt(amount) if amount is not None else flt(invoice.outstanding_amount)
    if target <= 0 or target - flt(invoice.outstanding_amount) > MONEY_TOLERANCE:
        frappe.throw(_("Supplier payment amount must be positive and cannot exceed invoice outstanding."))
    if abs(target - flt(invoice.outstanding_amount)) > MONEY_TOLERANCE:
        payment.paid_amount = target
        payment.received_amount = target
        for row in payment.references:
            if row.reference_doctype == "Purchase Invoice" and row.reference_name == invoice.name:
                row.allocated_amount = target
                break
    payment.custom_ledgix_client_payment_id = str(client_payment_id or "").strip()
    payment.custom_ledgix_payment_source = source
    if reference_number:
        payment.reference_no = str(reference_number).strip()
        payment.reference_date = nowdate()
    payment.insert(ignore_permissions=True)
    payment.submit()
    payment.reload()
    payment.flags.ledgix_duplicate_client_payment = False
    return payment


def create_purchase_return(
    *,
    purchase_invoice: str,
    client_invoice_id: str | None = None,
    source: str = "Ledgix Phase 7 Purchase Return",
):
    original = frappe.get_doc("Purchase Invoice", purchase_invoice)
    if original.docstatus != 1 or cint(original.is_return):
        frappe.throw(_("A submitted non-return Purchase Invoice is required."))
    _lock_company(original.company)
    existing = _active_by_client_id(
        "Purchase Invoice", "custom_ledgix_client_purchase_invoice_id", client_invoice_id
    )
    if existing:
        existing.flags.ledgix_duplicate_client_purchase_invoice = True
        return existing

    from erpnext.controllers.sales_and_purchase_return import make_return_doc

    credit = make_return_doc("Purchase Invoice", original.name)
    credit.custom_ledgix_client_purchase_invoice_id = str(client_invoice_id or "").strip()
    credit.custom_ledgix_client_purchase_id = original.get("custom_ledgix_client_purchase_id") or ""
    credit.custom_ledgix_buying_source = source
    credit.insert(ignore_permissions=True)
    credit.submit()
    credit.reload()
    credit.flags.ledgix_duplicate_client_purchase_invoice = False
    return credit


def create_stock_entry(
    *,
    item: str,
    qty: float,
    purpose: str,
    company: str | None = None,
    source_warehouse: str | None = None,
    target_warehouse: str | None = None,
    valuation_rate: float | None = None,
    batch_no: str | None = None,
    serial_numbers: Iterable[str] | str | None = None,
    client_stock_id: str | None = None,
    source: str = "Ledgix Phase 7 Stock",
    remarks: str | None = None,
):
    company = _company(company)
    _lock_company(company)
    existing = _active_by_client_id("Stock Entry", "custom_ledgix_client_stock_id", client_stock_id)
    if existing:
        existing.flags.ledgix_duplicate_client_stock = True
        return existing

    item_code = _resolve_item(item)
    if not cint(frappe.db.get_value("Item", item_code, "is_stock_item")):
        frappe.throw(_("Item {0} is non-stock and cannot create a Stock Entry.").format(item_code))
    qty = flt(qty)
    if qty <= 0:
        frappe.throw(_("Stock Entry quantity must be greater than zero."))

    normalized_purpose = str(purpose or "").strip()
    allowed = {"Material Receipt", "Material Issue", "Material Transfer"}
    if normalized_purpose not in allowed:
        frappe.throw(_("Unsupported Stock Entry purpose {0}.").format(normalized_purpose))

    from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

    serial_no = ""
    if isinstance(serial_numbers, str):
        serial_no = "\n".join(x.strip() for x in serial_numbers.replace(",", "\n").splitlines() if x.strip())
    elif serial_numbers:
        serial_no = "\n".join(str(x).strip() for x in serial_numbers if str(x).strip())

    kwargs = {
        "item_code": item_code,
        "qty": qty,
        "company": company,
        "do_not_save": True,
        "purpose": normalized_purpose,
        "use_serial_batch_fields": 1 if (batch_no or serial_no) else 0,
    }
    if normalized_purpose in {"Material Issue", "Material Transfer"}:
        kwargs["from_warehouse"] = _resolve_warehouse(source_warehouse, company)
    if normalized_purpose in {"Material Receipt", "Material Transfer"}:
        kwargs["to_warehouse"] = _resolve_warehouse(target_warehouse, company)
    if valuation_rate is not None:
        kwargs["rate"] = max(flt(valuation_rate), 0)
    if batch_no:
        kwargs["batch_no"] = str(batch_no).strip()
    if serial_no:
        kwargs["serial_no"] = serial_no

    doc = make_stock_entry(**kwargs)
    doc.custom_ledgix_client_stock_id = str(client_stock_id or "").strip()
    doc.custom_ledgix_stock_source = source
    doc.remarks = str(remarks or source).strip()
    doc.insert(ignore_permissions=True)
    doc.submit()
    doc.reload()
    doc.flags.ledgix_duplicate_client_stock = False
    return doc


def create_stock_reconciliation(
    *,
    item: str,
    qty: float,
    valuation_rate: float,
    warehouse: str | None = None,
    company: str | None = None,
    client_reconciliation_id: str | None = None,
    source: str = "Ledgix Phase 7 Reconciliation",
):
    company = _company(company)
    _lock_company(company)
    existing = _active_by_client_id(
        "Stock Reconciliation", "custom_ledgix_client_stock_reconciliation_id", client_reconciliation_id
    )
    if existing:
        existing.flags.ledgix_duplicate_client_reconciliation = True
        return existing

    item_code = _resolve_item(item)
    if not cint(frappe.db.get_value("Item", item_code, "is_stock_item")):
        frappe.throw(_("Only stock Items can be reconciled."))
    warehouse = _resolve_warehouse(warehouse, company)
    doc = frappe.get_doc(
        {
            "doctype": "Stock Reconciliation",
            "company": company,
            "purpose": "Stock Reconciliation",
            "posting_date": nowdate(),
            "custom_ledgix_client_stock_reconciliation_id": str(client_reconciliation_id or "").strip(),
            "custom_ledgix_stock_source": source,
            "items": [
                {
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "qty": flt(qty),
                    "valuation_rate": max(flt(valuation_rate), 0),
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)
    doc.submit()
    doc.reload()
    doc.flags.ledgix_duplicate_client_reconciliation = False
    return doc


def ensure_batch(item: str, batch_no: str, *, manufacturing_date: str | None = None) -> str:
    item_code = _resolve_item(item)
    batch_no = str(batch_no or "").strip()
    if not batch_no:
        frappe.throw(_("Batch number is required."))
    if frappe.db.exists("Batch", batch_no):
        existing_item = frappe.db.get_value("Batch", batch_no, "item")
        if existing_item != item_code:
            frappe.throw(_("Batch {0} belongs to another Item.").format(batch_no))
        return batch_no
    doc = frappe.get_doc(
        {
            "doctype": "Batch",
            "batch_id": batch_no,
            "item": item_code,
            "manufacturing_date": manufacturing_date or nowdate(),
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def stock_ledger_qty(voucher_type: str, voucher_no: str, item: str) -> float:
    item_code = _resolve_item(item)
    value = frappe.db.sql(
        """
        select coalesce(sum(actual_qty), 0)
        from `tabStock Ledger Entry`
        where voucher_type = %s
          and voucher_no = %s
          and item_code = %s
          and is_cancelled = 0
        """,
        (voucher_type, voucher_no, item_code),
    )
    return flt(value[0][0] if value else 0)


def cancel_native_voucher(doctype: str, name: str):
    if doctype not in {"Purchase Order", "Purchase Receipt", "Purchase Invoice", "Payment Entry", "Stock Entry", "Stock Reconciliation"}:
        frappe.throw(_("Unsupported native voucher cancellation type."))
    doc = frappe.get_doc(doctype, name)
    if doc.docstatus != 1:
        frappe.throw(_("Only submitted native vouchers can be cancelled."))
    doc.cancel()
    doc.reload()
    return doc
