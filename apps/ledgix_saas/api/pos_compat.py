from __future__ import annotations

"""Stable Ledgix POS RPC contracts backed by ERPNext-native services."""

import frappe
from frappe.utils import flt

from ledgix_saas.api import selling as selling_api
from ledgix_saas.api import selling_compat
from ledgix_saas.api.security import (
    LEDGIX_MANAGER_OR_ABOVE,
    has_any_role,
    require_ledgix_cashier_or_above,
)
from ledgix_saas.services import erpnext_pos


def _parse(value):
    return frappe.parse_json(value) if isinstance(value, str) else value


def _allow_rate_override() -> bool:
    return has_any_role(LEDGIX_MANAGER_OR_ABOVE)


def _native_print_target(result: dict, *, native_document: str, doctype: str) -> dict:
    """Attach the Phase 10 native print target without restoring legacy Sale IDs."""

    result = dict(result or {})
    result["native_document"] = native_document
    result["doctype"] = doctype
    result["print_doctype"] = doctype
    result["sale"] = ""
    if doctype == "POS Invoice":
        result["print_mode"] = "Thermal"
        result["print_format"] = "Ledgix ERPNext POS Receipt"
    else:
        result["print_mode"] = "A4"
        result["print_format"] = "Ledgix ERPNext Tax Invoice"
    result["print_deferred"] = False
    result["print_authority"] = "ERPNext native document + Ledgix print format"
    return result


@frappe.whitelist()
def get_pos_v2_boot(sale_channel="Retail", customer=None):
    require_ledgix_cashier_or_above()
    return erpnext_pos.boot(sale_channel=sale_channel, customer=customer)


@frappe.whitelist()
def search_pos_v2_items(query=None, category=None, customer=None, sale_channel="Retail", price_list=None, limit=80):
    require_ledgix_cashier_or_above()
    return erpnext_pos.search_items(
        query=query,
        category=category,
        customer=customer,
        sale_channel=sale_channel,
        price_list=price_list,
        limit=limit,
    )


@frappe.whitelist()
def get_pos_v2_customer_context(customer=None, sale_channel="Retail"):
    require_ledgix_cashier_or_above()
    return erpnext_pos.customer_context(customer, sale_channel)


@frappe.whitelist()
def preview_pos_v2_checkout(
    cart_items=None,
    customer=None,
    sale_channel="Retail",
    price_list=None,
    discount_type="Amount",
    discount_value=0,
):
    require_ledgix_cashier_or_above()
    if sale_channel == "B2B":
        return selling_compat.preview_b2b_invoice(
            customer=customer,
            items=cart_items,
            price_list=price_list,
            discount_type=discount_type,
            discount_value=discount_value,
        )
    return erpnext_pos.preview_checkout(
        cart_items=cart_items,
        customer=customer,
        price_list=price_list,
        discount_type=discount_type,
        discount_value=discount_value,
        allow_rate_override=_allow_rate_override(),
        source="Ledgix POS Retail Preview",
    )


@frappe.whitelist()
def complete_pos_v2_sale(
    cart_items=None,
    tenders=None,
    customer=None,
    sale_channel="Retail",
    price_list=None,
    discount_type="Amount",
    discount_value=0,
    client_sale_id=None,
):
    require_ledgix_cashier_or_above()
    if sale_channel == "B2B":
        result = selling_compat.complete_b2b_sale(
            customer=customer,
            cart_items=cart_items,
            tenders=tenders,
            price_list=price_list,
            client_sale_id=client_sale_id,
            discount_type=discount_type,
            discount_value=discount_value,
        )
        native = str(result.get("invoice") or result.get("invoice_number") or result.get("sale") or "")
        result["erpnext_sales_invoice"] = native
        return _native_print_target(result, native_document=native, doctype="Sales Invoice")

    invoice = erpnext_pos.complete_sale(
        cart_items=cart_items,
        tenders=tenders,
        customer=customer,
        price_list=price_list,
        discount_type=discount_type,
        discount_value=discount_value,
        client_sale_id=client_sale_id,
        allow_rate_override=_allow_rate_override(),
    )
    result = erpnext_pos.sale_result(invoice)
    return _native_print_target(result, native_document=invoice.name, doctype="POS Invoice")


@frappe.whitelist()
def get_active_shift_info():
    require_ledgix_cashier_or_above()
    return erpnext_pos.shift_info()


@frappe.whitelist()
def open_pos_shift(opening_cash=0, notes=None):
    require_ledgix_cashier_or_above()
    opening = erpnext_pos.open_shift(opening_cash=opening_cash, notes=notes)
    return {
        "success": True,
        "shift_id": opening.name,
        "opening_cash": erpnext_pos._opening_cash(opening),
        "expected_cash": erpnext_pos._opening_cash(opening),
        "message": f"ERPNext POS shift {opening.name} opened.",
        "authority": "ERPNext POS Opening Entry",
    }


@frappe.whitelist()
def close_pos_shift(actual_cash=0, closing_notes=None, shift_name=None, notes=None):
    require_ledgix_cashier_or_above()
    before = erpnext_pos.shift_info()
    opening, closing = erpnext_pos.close_shift(
        actual_cash=actual_cash,
        closing_notes=closing_notes or notes,
        shift_name=shift_name,
    )
    expected = flt(before.get("expected_cash"), 2)
    actual = flt(actual_cash, 2)
    return {
        "success": True,
        "shift_id": opening.name,
        "closing_entry": closing.name,
        "opening_cash": flt(before.get("opening_cash"), 2),
        "total_sales": flt(before.get("total_sales"), 2),
        "cash_sales": flt(before.get("cash_sales"), 2),
        "non_cash_sales": flt(before.get("non_cash_sales"), 2),
        "invoice_count": before.get("invoice_count") or 0,
        "expected_cash": expected,
        "actual_cash": actual,
        "cash_variance": flt(actual - expected, 2),
        "message": f"ERPNext POS shift {opening.name} closed.",
        "authority": "ERPNext POS Closing Entry",
    }


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
    doc = erpnext_pos.create_hold(
        cart_items=cart_items,
        sale_channel=sale_channel,
        customer=customer,
        price_list=price_list,
        discount_type=discount_type,
        discount_value=discount_value,
        notes=notes,
    )
    return {
        "success": True,
        "hold_id": doc.custom_ledgix_hold_id,
        "sale_channel": "Retail" if doc.doctype == "POS Invoice" else "B2B",
        "customer": doc.customer,
        "price_list": doc.selling_price_list,
        "total": flt(doc.grand_total, 2),
        "native_document": doc.name,
        "authority": f"ERPNext draft {doc.doctype}",
    }


@frappe.whitelist()
def get_pos_v2_holds():
    require_ledgix_cashier_or_above()
    return {"success": True, "holds": erpnext_pos.list_holds(), "authority": "ERPNext draft invoices"}


@frappe.whitelist()
def resume_pos_v2_hold(hold_id):
    require_ledgix_cashier_or_above()
    return erpnext_pos.resume_hold(hold_id)


@frappe.whitelist()
def cancel_pos_v2_hold(hold_id):
    require_ledgix_cashier_or_above()
    doc = erpnext_pos.cancel_hold(hold_id)
    return {"success": True, "hold_id": hold_id, "native_document": doc.name, "authority": f"ERPNext draft {doc.doctype}"}


@frappe.whitelist()
def get_pos_v2_return_context(sale_id):
    require_ledgix_cashier_or_above()
    retail = erpnext_pos.get_return_context(sale_id)
    if retail:
        return retail
    return selling_api.get_pos_return_context_compat(sale_id)


@frappe.whitelist()
def create_pos_v2_return(original_sale, return_items=None, reason=None, client_return_id=None):
    require_ledgix_cashier_or_above()
    if erpnext_pos._submitted_pos_invoice(original_sale):
        doc = erpnext_pos.create_return(
            original_sale=original_sale,
            return_items=_parse(return_items),
            reason=reason,
            client_return_id=client_return_id,
        )
        result = erpnext_pos.return_result(doc)
        return _native_print_target(result, native_document=doc.name, doctype="POS Invoice")
    result = selling_api.create_pos_return_compat(
        original_sale=original_sale,
        return_items=return_items,
        reason=reason,
        client_return_id=client_return_id,
    )
    native = str(result.get("return_id") or result.get("credit_note") or result.get("invoice") or "")
    if native and frappe.db.exists("Sales Invoice", native):
        return _native_print_target(result, native_document=native, doctype="Sales Invoice")
    return result
