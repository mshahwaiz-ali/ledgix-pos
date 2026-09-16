from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from ledgix_saas.migration import erpnext_stock_purchase_behavioral_spike as base


PO_MARKER_FIELD = "order_confirmation_no"
REMARK_MARKER_DOCTYPES = ("Purchase Receipt", "Purchase Invoice", "Sales Invoice")


def _assert_marker_schema() -> None:
    """Fail clearly if the ERPNext v15 marker fields used by this spike drift."""

    if not frappe.get_meta("Purchase Order").has_field(PO_MARKER_FIELD):
        frappe.throw(
            f"ERPNext Purchase Order no longer exposes {PO_MARKER_FIELD!r}; "
            "update the behavioral spike marker before continuing."
        )

    for doctype in REMARK_MARKER_DOCTYPES:
        if not frappe.get_meta(doctype).has_field("remarks"):
            frappe.throw(
                f"ERPNext {doctype} no longer exposes 'remarks'; "
                "update the behavioral spike marker before continuing."
            )


def _ensure_purchase_order(supplier: str, item_code: str, warehouse: str):
    """Create/reuse the spike PO without querying a non-existent `remarks` column.

    ERPNext v15 Purchase Order has `order_confirmation_no` but no `remarks`
    column. The original base helper used a generic remarks marker, which is
    valid for the downstream Purchase Receipt, Purchase Invoice and Sales
    Invoice documents but not for Purchase Order.
    """

    name = frappe.db.get_value(
        "Purchase Order",
        {
            "company": base.TEST_COMPANY,
            PO_MARKER_FIELD: base.PO_MARKER,
            "docstatus": 1,
        },
        "name",
    )
    if name:
        return frappe.get_doc("Purchase Order", name)

    purchase_order = frappe.get_doc(
        {
            "doctype": "Purchase Order",
            "company": base.TEST_COMPANY,
            "supplier": supplier,
            "transaction_date": nowdate(),
            "schedule_date": nowdate(),
            "currency": base.CURRENCY,
            "buying_price_list": base.BUYING_PRICE_LIST,
            "set_warehouse": warehouse,
            PO_MARKER_FIELD: base.PO_MARKER,
            "items": [
                {
                    "item_code": item_code,
                    "qty": base.PURCHASE_QTY,
                    "uom": "Nos",
                    "rate": base.BUY_RATE,
                    "schedule_date": nowdate(),
                    "warehouse": warehouse,
                }
            ],
        }
    )
    purchase_order.insert(ignore_permissions=True)
    purchase_order.submit()
    return purchase_order


def run() -> dict:
    """Rerun-safe wrapper around the native purchase/stock behavioral spike.

    Assertions are tied to the ERPNext vouchers created by this spike rather
    than the warehouse's absolute balance. That lets a later POS spike consume
    stock without making a second Phase 2 batch run report a false failure.
    """

    base._assert_safe_site()
    _assert_marker_schema()
    ledgix_before = base._ledgix_counts()

    warehouse = base._leaf_warehouse()
    supplier = base._ensure_supplier()
    customer = base._ensure_customer()
    item_code = base._ensure_stock_item()
    buying_item_price = base._ensure_item_price(item_code, base.BUYING_PRICE_LIST, base.BUY_RATE)
    selling_item_price = base._ensure_item_price(item_code, base.SELLING_PRICE_LIST, base.SELL_RATE)
    cash_account = base._ensure_cash_mode_account()

    purchase_order = _ensure_purchase_order(supplier, item_code, warehouse)
    purchase_receipt = base._ensure_purchase_receipt(purchase_order, warehouse)
    purchase_invoice = base._ensure_purchase_invoice(purchase_receipt)
    supplier_payment = base._ensure_supplier_payment(purchase_invoice, cash_account)
    purchase_invoice.reload()

    stock_sale = base._ensure_stock_sale(customer, item_code, warehouse)
    stock_return = base._ensure_stock_return(stock_sale)
    stock_sale.reload()
    stock_return.reload()

    receipt_sle_qty = base._sle_qty("Purchase Receipt", purchase_receipt.name, item_code)
    sale_sle_qty = base._sle_qty("Sales Invoice", stock_sale.name, item_code)
    return_sle_qty = base._sle_qty("Sales Invoice", stock_return.name, item_code)
    own_net_stock_contribution = flt(receipt_sle_qty + sale_sle_qty + return_sle_qty)

    ledgix_after = base._ledgix_counts()

    evidence = {
        "site": frappe.local.site,
        "company": base.TEST_COMPANY,
        "warehouse": warehouse,
        "supplier": supplier,
        "customer": customer,
        "marker_schema": {
            "Purchase Order": PO_MARKER_FIELD,
            "Purchase Receipt": "remarks",
            "Purchase Invoice": "remarks",
            "Sales Invoice": "remarks",
        },
        "item": {
            "name": item_code,
            "is_stock_item": bool(frappe.db.get_value("Item", item_code, "is_stock_item")),
            "buying_item_price": buying_item_price,
            "selling_item_price": selling_item_price,
            "current_bin_qty": base._bin_qty(item_code, warehouse),
        },
        "purchase_path": {
            "purchase_order": purchase_order.name,
            "purchase_order_docstatus": purchase_order.docstatus,
            "purchase_order_marker": purchase_order.get(PO_MARKER_FIELD),
            "purchase_receipt": purchase_receipt.name,
            "purchase_receipt_docstatus": purchase_receipt.docstatus,
            "purchase_receipt_sle_qty": receipt_sle_qty,
            "purchase_invoice": purchase_invoice.name,
            "purchase_invoice_docstatus": purchase_invoice.docstatus,
            "purchase_invoice_gl_entries": base._gl_count("Purchase Invoice", purchase_invoice.name),
            "purchase_invoice_outstanding_after_payment": flt(purchase_invoice.outstanding_amount),
            "supplier_payment": supplier_payment.name,
            "supplier_payment_docstatus": supplier_payment.docstatus,
            "supplier_payment_gl_entries": base._gl_count("Payment Entry", supplier_payment.name),
        },
        "stock_sale_return_path": {
            "sales_invoice": stock_sale.name,
            "sales_invoice_docstatus": stock_sale.docstatus,
            "sales_invoice_gl_entries": base._gl_count("Sales Invoice", stock_sale.name),
            "sales_invoice_sle_qty": sale_sle_qty,
            "return_invoice": stock_return.name,
            "return_docstatus": stock_return.docstatus,
            "return_against": stock_return.return_against,
            "return_gl_entries": base._gl_count("Sales Invoice", stock_return.name),
            "return_sle_qty": return_sle_qty,
            "own_net_stock_contribution": own_net_stock_contribution,
        },
        "parallel_ledgix_guard": {
            "before": ledgix_before,
            "after": ledgix_after,
            "unchanged": ledgix_before == ledgix_after,
        },
    }

    checks = {
        "stock_item": evidence["item"]["is_stock_item"] is True,
        "purchase_order_submitted": purchase_order.docstatus == 1,
        "purchase_order_marker_persisted": purchase_order.get(PO_MARKER_FIELD) == base.PO_MARKER,
        "purchase_receipt_submitted": purchase_receipt.docstatus == 1,
        "purchase_receipt_added_stock": abs(receipt_sle_qty - base.PURCHASE_QTY) < 0.005,
        "purchase_invoice_submitted": purchase_invoice.docstatus == 1,
        "purchase_invoice_has_gl": evidence["purchase_path"]["purchase_invoice_gl_entries"] > 0,
        "supplier_payment_submitted": supplier_payment.docstatus == 1,
        "supplier_payment_has_gl": evidence["purchase_path"]["supplier_payment_gl_entries"] > 0,
        "purchase_invoice_fully_paid": abs(
            evidence["purchase_path"]["purchase_invoice_outstanding_after_payment"]
        ) < 0.005,
        "stock_sale_submitted": stock_sale.docstatus == 1,
        "stock_sale_has_gl": evidence["stock_sale_return_path"]["sales_invoice_gl_entries"] > 0,
        "stock_sale_reduced_stock": abs(sale_sle_qty + base.SALE_QTY) < 0.005,
        "stock_return_submitted": stock_return.docstatus == 1,
        "stock_return_linked": stock_return.return_against == stock_sale.name,
        "stock_return_has_gl": evidence["stock_sale_return_path"]["return_gl_entries"] > 0,
        "stock_return_restored_stock": abs(return_sle_qty - base.SALE_QTY) < 0.005,
        "own_vouchers_net_to_purchase_receipt": abs(
            own_net_stock_contribution - base.PURCHASE_QTY
        ) < 0.005,
        "no_parallel_ledgix_docs_created": evidence["parallel_ledgix_guard"]["unchanged"],
    }

    evidence["checks"] = checks
    evidence["passed"] = all(checks.values())
    frappe.db.commit()
    return evidence
