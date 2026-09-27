from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from ledgix_saas.migration.erpnext_integration_bootstrap import (
    CURRENCY,
    INTEGRATION_SITE,
    TEST_COMPANY,
)


TEST_CUSTOMER = "Ledgix Invoice Spike Customer"
TEST_ITEM = "LEDGIX-NONSTOCK-SPIKE"
TEST_RATE = 1250.0
SELLING_PRICE_LIST = "Standard Selling"
PAYMENT_INVOICE_MARKER = "LEDGIX-ERPNEXT-INVOICE-PAYMENT-SPIKE-V1"
RETURN_SOURCE_MARKER = "LEDGIX-ERPNEXT-INVOICE-RETURN-SOURCE-V1"
RETURN_MARKER = "LEDGIX-ERPNEXT-INVOICE-RETURN-V1"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing ERPNext invoice behavioral spike on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )

    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing; run the integration bootstrap first.")


def _count_if_exists(doctype: str) -> int | None:
    if not frappe.db.exists("DocType", doctype):
        return None
    return frappe.db.count(doctype)


def _ensure_customer() -> str:
    existing = frappe.db.get_value("Customer", {"customer_name": TEST_CUSTOMER}, "name")
    if existing:
        return existing

    customer = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": TEST_CUSTOMER,
            "customer_type": "Individual",
            "customer_group": "Individual",
            "territory": "Pakistan",
        }
    )
    customer.insert(ignore_permissions=True)
    return customer.name


def _ensure_nonstock_item() -> str:
    if frappe.db.exists("Item", TEST_ITEM):
        item = frappe.get_doc("Item", TEST_ITEM)
        if item.is_stock_item:
            frappe.throw(f"Safety check failed: test item {TEST_ITEM!r} unexpectedly became a stock item.")
        return item.name

    item = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": TEST_ITEM,
            "item_name": "Ledgix Non-Stock Invoice Spike",
            "description": "ERPNext native non-stock invoice behavioral spike item",
            "item_group": "Services",
            "stock_uom": "Nos",
            "is_stock_item": 0,
            "include_item_in_manufacturing": 0,
        }
    )
    item.insert(ignore_permissions=True)
    return item.name


def _ensure_item_price(item_code: str) -> str:
    existing = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "price_list": SELLING_PRICE_LIST,
            "currency": CURRENCY,
            "uom": "Nos",
        },
        "name",
    )
    if existing:
        return existing

    price = frappe.get_doc(
        {
            "doctype": "Item Price",
            "item_code": item_code,
            "price_list": SELLING_PRICE_LIST,
            "price_list_rate": TEST_RATE,
            "currency": CURRENCY,
            "uom": "Nos",
        }
    )
    price.insert(ignore_permissions=True)
    return price.name


def _ensure_cash_mode_account() -> str:
    cash_account = frappe.db.get_value(
        "Account",
        {"company": TEST_COMPANY, "account_type": "Cash", "is_group": 0},
        "name",
    )
    if not cash_account:
        frappe.throw(f"No leaf Cash account exists for {TEST_COMPANY!r}.")

    mode = frappe.get_doc("Mode of Payment", "Cash")
    row = next((entry for entry in mode.accounts if entry.company == TEST_COMPANY), None)
    if not row:
        mode.append("accounts", {"company": TEST_COMPANY, "default_account": cash_account})
        mode.save(ignore_permissions=True)
    elif row.default_account != cash_account:
        row.default_account = cash_account
        mode.save(ignore_permissions=True)

    return cash_account


def _get_submitted_invoice(marker: str):
    name = frappe.db.get_value(
        "Sales Invoice",
        {"company": TEST_COMPANY, "remarks": marker, "docstatus": 1},
        "name",
    )
    return frappe.get_doc("Sales Invoice", name) if name else None


def _create_sales_invoice(customer: str, item_code: str, marker: str):
    existing = _get_submitted_invoice(marker)
    if existing:
        return existing

    invoice = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "company": TEST_COMPANY,
            "customer": customer,
            "posting_date": nowdate(),
            "currency": CURRENCY,
            "selling_price_list": SELLING_PRICE_LIST,
            "remarks": marker,
            "update_stock": 0,
            "items": [
                {
                    "item_code": item_code,
                    "qty": 1,
                    "uom": "Nos",
                    "rate": TEST_RATE,
                }
            ],
        }
    )
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return invoice


def _find_payment_entry(invoice_name: str):
    rows = frappe.db.sql(
        """
        select pe.name
        from `tabPayment Entry` pe
        inner join `tabPayment Entry Reference` ref on ref.parent = pe.name
        where pe.docstatus = 1
          and ref.reference_doctype = 'Sales Invoice'
          and ref.reference_name = %s
        order by pe.creation asc
        limit 1
        """,
        invoice_name,
        as_dict=True,
    )
    return frappe.get_doc("Payment Entry", rows[0].name) if rows else None


def _ensure_payment(invoice, cash_account: str):
    existing = _find_payment_entry(invoice.name)
    if existing:
        return existing

    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    payment = get_payment_entry("Sales Invoice", invoice.name)
    payment.mode_of_payment = "Cash"
    payment.paid_to = cash_account
    payment.insert(ignore_permissions=True)
    payment.submit()
    return payment


def _ensure_return(source_invoice):
    existing_name = frappe.db.get_value(
        "Sales Invoice",
        {
            "company": TEST_COMPANY,
            "is_return": 1,
            "return_against": source_invoice.name,
            "remarks": RETURN_MARKER,
            "docstatus": 1,
        },
        "name",
    )
    if existing_name:
        return frappe.get_doc("Sales Invoice", existing_name)

    from erpnext.controllers.sales_and_purchase_return import make_return_doc

    return_doc = make_return_doc("Sales Invoice", source_invoice.name)
    return_doc.remarks = RETURN_MARKER
    return_doc.insert(ignore_permissions=True)
    return_doc.submit()
    return return_doc


def _gl_count(voucher_type: str, voucher_no: str) -> int:
    return frappe.db.count(
        "GL Entry",
        {"voucher_type": voucher_type, "voucher_no": voucher_no, "is_cancelled": 0},
    )


def _sle_count(voucher_type: str, voucher_no: str) -> int:
    return frappe.db.count(
        "Stock Ledger Entry",
        {"voucher_type": voucher_type, "voucher_no": voucher_no, "is_cancelled": 0},
    )


def run() -> dict:
    """Exercise ERPNext's native invoice-only path on the isolated integration site.

    The spike deliberately uses a non-stock Item. It proves that Ledgix can offer
    an invoice/FBR-only product profile without inventing negative inventory or a
    parallel custom sale/payment/return ledger.
    """

    _assert_safe_site()

    ledgix_sale_count_before = _count_if_exists("Ledgix Sale")

    customer = _ensure_customer()
    item_code = _ensure_nonstock_item()
    item_price = _ensure_item_price(item_code)
    cash_account = _ensure_cash_mode_account()

    payment_invoice = _create_sales_invoice(customer, item_code, PAYMENT_INVOICE_MARKER)
    payment_entry = _ensure_payment(payment_invoice, cash_account)
    payment_invoice.reload()

    return_source = _create_sales_invoice(customer, item_code, RETURN_SOURCE_MARKER)
    return_invoice = _ensure_return(return_source)
    return_source.reload()
    return_invoice.reload()

    ledgix_sale_count_after = _count_if_exists("Ledgix Sale")

    evidence = {
        "site": frappe.local.site,
        "company": TEST_COMPANY,
        "customer": customer,
        "item": {
            "name": item_code,
            "is_stock_item": bool(frappe.db.get_value("Item", item_code, "is_stock_item")),
            "item_price": item_price,
            "rate": TEST_RATE,
        },
        "cash_account": cash_account,
        "payment_path": {
            "sales_invoice": payment_invoice.name,
            "invoice_docstatus": payment_invoice.docstatus,
            "grand_total": flt(payment_invoice.grand_total),
            "outstanding_after_payment": flt(payment_invoice.outstanding_amount),
            "invoice_gl_entries": _gl_count("Sales Invoice", payment_invoice.name),
            "invoice_stock_ledger_entries": _sle_count("Sales Invoice", payment_invoice.name),
            "payment_entry": payment_entry.name,
            "payment_docstatus": payment_entry.docstatus,
            "paid_amount": flt(payment_entry.paid_amount),
            "unallocated_amount": flt(payment_entry.unallocated_amount),
            "payment_gl_entries": _gl_count("Payment Entry", payment_entry.name),
        },
        "return_path": {
            "source_invoice": return_source.name,
            "source_grand_total": flt(return_source.grand_total),
            "source_outstanding_after_return": flt(return_source.outstanding_amount),
            "return_invoice": return_invoice.name,
            "return_docstatus": return_invoice.docstatus,
            "return_against": return_invoice.return_against,
            "return_grand_total": flt(return_invoice.grand_total),
            "return_gl_entries": _gl_count("Sales Invoice", return_invoice.name),
            "return_stock_ledger_entries": _sle_count("Sales Invoice", return_invoice.name),
        },
        "parallel_ledgix_sale_guard": {
            "before": ledgix_sale_count_before,
            "after": ledgix_sale_count_after,
            "unchanged": ledgix_sale_count_before == ledgix_sale_count_after,
        },
    }

    checks = {
        "nonstock_item": evidence["item"]["is_stock_item"] is False,
        "invoice_submitted": payment_invoice.docstatus == 1,
        "invoice_has_gl": evidence["payment_path"]["invoice_gl_entries"] > 0,
        "invoice_has_no_stock_ledger": evidence["payment_path"]["invoice_stock_ledger_entries"] == 0,
        "payment_submitted": payment_entry.docstatus == 1,
        "payment_has_gl": evidence["payment_path"]["payment_gl_entries"] > 0,
        "invoice_fully_paid": abs(evidence["payment_path"]["outstanding_after_payment"]) < 0.005,
        "return_submitted": return_invoice.docstatus == 1,
        "return_linked_to_source": return_invoice.return_against == return_source.name,
        "return_is_negative": evidence["return_path"]["return_grand_total"] < 0,
        "return_has_gl": evidence["return_path"]["return_gl_entries"] > 0,
        "return_has_no_stock_ledger": evidence["return_path"]["return_stock_ledger_entries"] == 0,
        "no_parallel_ledgix_sale_created": evidence["parallel_ledgix_sale_guard"]["unchanged"],
    }

    evidence["checks"] = checks
    evidence["passed"] = all(checks.values())

    frappe.db.commit()
    return evidence
