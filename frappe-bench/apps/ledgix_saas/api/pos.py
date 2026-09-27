"""Legacy POS method names backed exclusively by ERPNext-native authority.

These endpoints are retained for older clients/bookmarks.  Phase 12 removes the
last direct dependency from this compatibility surface to Ledgix Sale, POS Shift,
POS Hold, Item, Payment and Stock Serial business-engine tables.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt

from ledgix_saas.api import pos_compat
from ledgix_saas.api.printing import get_native_invoice_print_context
from ledgix_saas.api.security import require_ledgix_cashier_or_above
from ledgix_saas.services import erpnext_buying_inventory, erpnext_pos


def _resolve_exact_item_code(code: str) -> str | None:
    code = str(code or "").strip()
    if not code:
        return None
    if frappe.db.exists("Item", code):
        return code
    barcode_parent = frappe.db.get_value("Item Barcode", {"barcode": code}, "parent")
    if barcode_parent:
        return barcode_parent
    if frappe.get_meta("Item").has_field("custom_ledgix_legacy_sku"):
        sku_item = frappe.db.get_value("Item", {"custom_ledgix_legacy_sku": code, "disabled": 0}, "name")
        if sku_item:
            return sku_item
    return None


@frappe.whitelist()
def get_item_by_barcode_or_sku(code):
    require_ledgix_cashier_or_above()
    item_code = _resolve_exact_item_code(code)
    if not item_code:
        return {"found": False, "message": "No active ERPNext Item found for this barcode / SKU / item code"}
    result = erpnext_pos.search_items(query=item_code, sale_channel="Retail", limit=20)
    item = next((row for row in result.get("items") or [] if row.get("item_code") == item_code), None)
    return {
        "found": bool(item),
        "item": item,
        "authority": "ERPNext Item / Item Barcode / Item Price / Bin",
    }


@frappe.whitelist()
def get_pos_boot_data():
    boot = pos_compat.get_pos_v2_boot(sale_channel="Retail")
    catalog = pos_compat.search_pos_v2_items(sale_channel="Retail", limit=60)
    return {
        "categories": boot.get("categories") or [],
        "items": catalog.get("items") or [],
        "payment_methods": boot.get("payment_methods") or [],
        "active_shift": boot.get("active_shift"),
        "price_list": boot.get("price_list"),
        "authority": "ERPNext POS",
    }


@frappe.whitelist()
def search_pos_items(query=None, category=None):
    result = pos_compat.search_pos_v2_items(
        query=query,
        category=category,
        sale_channel="Retail",
        limit=80,
    )
    return {"items": result.get("items") or [], "authority": "ERPNext Item / Price / Bin"}


@frappe.whitelist()
def get_available_serials_for_pos(item, limit=100):
    require_ledgix_cashier_or_above()
    rows = erpnext_buying_inventory.available_serials(item, limit=limit)
    return {
        "item": erpnext_buying_inventory._resolve_item(item),
        "serials": [
            {
                "name": row.get("name"),
                "serial_number": row.get("serial_no"),
                "item": row.get("item_code"),
                "purchase": row.get("purchase") or "",
                "purchase_date": row.get("purchase_date"),
                "status": "Available",
                "warehouse": row.get("warehouse") or "",
            }
            for row in rows
        ],
        "authority": "ERPNext Serial No",
    }


@frappe.whitelist()
def create_pos_sale(
    cart_items=None,
    payments=None,
    discount_type="Amount",
    discount_value=0,
    client_sale_id=None,
):
    tenders = frappe.parse_json(payments) if isinstance(payments, str) else (payments or [])
    normalized = [
        {
            "payment_method": row.get("payment_method") or row.get("mode_of_payment"),
            "amount": row.get("amount"),
            "reference_number": row.get("reference_number") or row.get("reference_no"),
            "notes": row.get("notes"),
        }
        for row in tenders
    ]
    return pos_compat.complete_pos_v2_sale(
        cart_items=cart_items,
        tenders=normalized,
        sale_channel="Retail",
        discount_type=discount_type,
        discount_value=discount_value,
        client_sale_id=client_sale_id,
    )


@frappe.whitelist()
def hold_pos_sale(cart_items=None, discount_type="Amount", discount_value=0, notes=None):
    return pos_compat.hold_pos_v2_sale(
        cart_items=cart_items,
        sale_channel="Retail",
        discount_type=discount_type,
        discount_value=discount_value,
        notes=notes,
    )


@frappe.whitelist()
def get_held_pos_sales():
    return pos_compat.get_pos_v2_holds()


@frappe.whitelist()
def resume_held_pos_sale(hold_id=None):
    return pos_compat.resume_pos_v2_hold(hold_id=hold_id)


@frappe.whitelist()
def delete_held_pos_sale(hold_id=None):
    return pos_compat.cancel_pos_v2_hold(hold_id=hold_id)


@frappe.whitelist()
def get_pos_sale_for_return(sale_id=None):
    return pos_compat.get_pos_v2_return_context(sale_id=sale_id)


@frappe.whitelist()
def create_pos_sales_return(original_sale=None, return_items=None, reason=None):
    return pos_compat.create_pos_v2_return(
        original_sale=original_sale,
        return_items=return_items,
        reason=reason,
    )


@frappe.whitelist()
def get_recent_pos_sales(limit=10, offset=0, query=None):
    """Compatibility list over submitted native ERPNext POS Invoices."""

    require_ledgix_cashier_or_above()
    limit = min(max(int(limit or 10), 1), 50)
    offset = max(int(offset or 0), 0)
    query = str(query or "").strip()
    filters = {"docstatus": 1, "is_return": 0}
    or_filters = None
    if query:
        like = f"%{query}%"
        or_filters = {
            "name": ["like", like],
            "customer": ["like", like],
            "customer_name": ["like", like],
        }
    rows = frappe.get_all(
        "POS Invoice",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "creation",
            "posting_date",
            "customer",
            "customer_name",
            "pos_profile",
            "net_total",
            "total_taxes_and_charges",
            "grand_total",
            "paid_amount",
            "change_amount",
            "outstanding_amount",
            "owner",
        ],
        order_by="creation desc",
        limit_start=offset,
        limit_page_length=limit,
    )
    total_count = frappe.db.count("POS Invoice", filters=filters)
    result = []
    for invoice in rows:
        item_rows = frappe.get_all(
            "POS Invoice Item",
            filters={"parent": invoice.name, "parenttype": "POS Invoice"},
            fields=["item_code", "item_name", "qty"],
            order_by="idx asc",
            limit_page_length=4,
        )
        item_count = frappe.db.count(
            "POS Invoice Item", filters={"parent": invoice.name, "parenttype": "POS Invoice"}
        )
        outstanding = flt(invoice.outstanding_amount, 2)
        total = flt(invoice.grand_total, 2)
        payment_status = "Paid" if abs(outstanding) <= 0.005 else "Partial" if outstanding < total - 0.005 else "Unpaid"
        result.append(
            {
                "name": invoice.name,
                "invoice_number": invoice.name,
                "creation": invoice.creation,
                "sale_date": invoice.posting_date,
                "customer": invoice.customer,
                "customer_name": invoice.customer_name,
                "sale_channel": "Retail",
                "pos_shift": invoice.pos_profile,
                "total_amount": flt(invoice.net_total, 2),
                "tax_amount": flt(invoice.total_taxes_and_charges, 2),
                "grand_total": total,
                "paid_amount": flt(invoice.paid_amount, 2),
                "change_amount": flt(invoice.change_amount, 2),
                "payment_status": payment_status,
                "owner": invoice.owner,
                "item_count": item_count,
                "items_preview": ", ".join(
                    f"{row.item_name or row.item_code} x {flt(row.qty):g}" for row in item_rows
                ),
                "authority": "ERPNext POS Invoice",
            }
        )
    return {
        "success": True,
        "sales": result,
        "limit": limit,
        "offset": offset,
        "total_count": total_count,
        "has_more": offset + limit < total_count,
        "authority": "ERPNext POS Invoice",
    }


@frappe.whitelist()
def get_pos_sale_receipt_data(sale_id=None):
    """Compatibility receipt shape from the Phase 10 native print context."""

    require_ledgix_cashier_or_above()
    if not sale_id:
        frappe.throw("Sale ID is required")
    context = get_native_invoice_print_context("POS Invoice", sale_id)
    return {
        "success": True,
        "receipt": {
            "sale_id": context["name"],
            "invoice_number": context["name"],
            "date_time": context.get("posting_time"),
            "customer": (context.get("buyer") or {}).get("name") or "",
            "cashier": frappe.db.get_value("POS Invoice", sale_id, "owner") or "",
            "shift_id": frappe.db.get_value("POS Invoice", sale_id, "pos_profile") or "",
            "items": [
                {
                    "item": row.get("item_code"),
                    "item_name": row.get("item_name"),
                    "qty": row.get("qty"),
                    "rate": row.get("rate"),
                    "amount": row.get("amount"),
                }
                for row in context.get("items") or []
            ],
            "subtotal": context.get("net_total"),
            "discount": max(flt(context.get("net_total")) + flt(context.get("tax_total")) - flt(context.get("grand_total")), 0),
            "tax": context.get("tax_total"),
            "total": context.get("grand_total"),
            "paid": context.get("paid_amount"),
            "remaining": context.get("outstanding_amount"),
            "change": context.get("change_amount"),
            "payment_status": "Paid" if flt(context.get("outstanding_amount")) <= 0.005 else "Unpaid",
            "fbr_status": context.get("fbr_status"),
            "fbr_invoice_number": context.get("fbr_invoice_number"),
            "fbr_qr_code": context.get("fbr_qr_data_uri"),
            "payments": context.get("payments") or [],
            "authority": context.get("authority"),
        },
    }
