from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from ledgix_saas.migration.erpnext_integration_bootstrap import (
    CURRENCY,
    INTEGRATION_SITE,
    TEST_COMPANY,
)


TEST_SUPPLIER = "Ledgix Stock Spike Supplier"
TEST_CUSTOMER = "Ledgix Stock Spike Customer"
TEST_ITEM = "LEDGIX-STOCK-SPIKE"
BUY_RATE = 500.0
SELL_RATE = 800.0
PURCHASE_QTY = 10.0
SALE_QTY = 2.0
BUYING_PRICE_LIST = "Standard Buying"
SELLING_PRICE_LIST = "Standard Selling"
PO_MARKER = "LEDGIX-ERPNEXT-STOCK-PO-SPIKE-V1"
PR_MARKER = "LEDGIX-ERPNEXT-STOCK-PR-SPIKE-V1"
PI_MARKER = "LEDGIX-ERPNEXT-STOCK-PI-SPIKE-V1"
SALE_MARKER = "LEDGIX-ERPNEXT-STOCK-SALE-SPIKE-V1"
RETURN_MARKER = "LEDGIX-ERPNEXT-STOCK-RETURN-SPIKE-V1"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing ERPNext stock/purchase behavioral spike on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )

    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing; run the integration bootstrap first.")


def _count_if_exists(doctype: str) -> int | None:
    if not frappe.db.exists("DocType", doctype):
        return None
    return frappe.db.count(doctype)


def _ledgix_counts() -> dict:
    doctypes = ["Ledgix Sale", "Ledgix Purchase", "Ledgix Payment", "Ledgix Stock Movement"]
    return {doctype: _count_if_exists(doctype) for doctype in doctypes}


def _leaf_warehouse() -> str:
    stores = frappe.get_all(
        "Warehouse",
        filters={"company": TEST_COMPANY, "warehouse_name": "Stores", "is_group": 0, "disabled": 0},
        pluck="name",
        limit=1,
    )
    if stores:
        return stores[0]

    warehouses = frappe.get_all(
        "Warehouse",
        filters={"company": TEST_COMPANY, "is_group": 0, "disabled": 0},
        pluck="name",
        order_by="name asc",
        limit=1,
    )
    if not warehouses:
        frappe.throw(f"No active leaf Warehouse exists for {TEST_COMPANY!r}.")
    return warehouses[0]


def _ensure_supplier() -> str:
    existing = frappe.db.get_value("Supplier", {"supplier_name": TEST_SUPPLIER}, "name")
    if existing:
        return existing

    supplier = frappe.get_doc(
        {
            "doctype": "Supplier",
            "supplier_name": TEST_SUPPLIER,
            "supplier_type": "Company",
            "supplier_group": "Local",
        }
    )
    supplier.insert(ignore_permissions=True)
    return supplier.name


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


def _ensure_stock_item() -> str:
    if frappe.db.exists("Item", TEST_ITEM):
        item = frappe.get_doc("Item", TEST_ITEM)
        if not item.is_stock_item:
            frappe.throw(f"Safety check failed: test item {TEST_ITEM!r} is no longer a stock item.")
        return item.name

    item = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": TEST_ITEM,
            "item_name": "Ledgix ERPNext Stock Spike",
            "description": "ERPNext native purchase, stock, sale and return behavioral spike item",
            "item_group": "Products",
            "stock_uom": "Nos",
            "is_stock_item": 1,
            "include_item_in_manufacturing": 0,
            "valuation_method": "FIFO",
        }
    )
    item.insert(ignore_permissions=True)
    return item.name


def _ensure_item_price(item_code: str, price_list: str, rate: float) -> str:
    existing = frappe.db.get_value(
        "Item Price",
        {
            "item_code": item_code,
            "price_list": price_list,
            "currency": CURRENCY,
            "uom": "Nos",
        },
        "name",
    )
    if existing:
        price = frappe.get_doc("Item Price", existing)
        if flt(price.price_list_rate) != flt(rate):
            price.price_list_rate = rate
            price.save(ignore_permissions=True)
        return price.name

    price = frappe.get_doc(
        {
            "doctype": "Item Price",
            "item_code": item_code,
            "price_list": price_list,
            "price_list_rate": rate,
            "currency": CURRENCY,
            "uom": "Nos",
        }
    )
    price.insert(ignore_permissions=True)
    return price.name


def _ensure_cash_mode_account() -> str:
    cash_account = frappe.db.get_value(
        "Account",
        {"company": TEST_COMPANY, "account_type": "Cash", "is_group": 0, "disabled": 0},
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


def _get_submitted(doctype: str, marker: str):
    name = frappe.db.get_value(
        doctype,
        {"company": TEST_COMPANY, "remarks": marker, "docstatus": 1},
        "name",
    )
    return frappe.get_doc(doctype, name) if name else None


def _ensure_purchase_order(supplier: str, item_code: str, warehouse: str):
    existing = _get_submitted("Purchase Order", PO_MARKER)
    if existing:
        return existing

    purchase_order = frappe.get_doc(
        {
            "doctype": "Purchase Order",
            "company": TEST_COMPANY,
            "supplier": supplier,
            "transaction_date": nowdate(),
            "schedule_date": nowdate(),
            "currency": CURRENCY,
            "buying_price_list": BUYING_PRICE_LIST,
            "set_warehouse": warehouse,
            "remarks": PO_MARKER,
            "items": [
                {
                    "item_code": item_code,
                    "qty": PURCHASE_QTY,
                    "uom": "Nos",
                    "rate": BUY_RATE,
                    "schedule_date": nowdate(),
                    "warehouse": warehouse,
                }
            ],
        }
    )
    purchase_order.insert(ignore_permissions=True)
    purchase_order.submit()
    return purchase_order


def _ensure_purchase_receipt(purchase_order, warehouse: str):
    existing = _get_submitted("Purchase Receipt", PR_MARKER)
    if existing:
        return existing

    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

    receipt = make_purchase_receipt(purchase_order.name)
    receipt.set_warehouse = warehouse
    receipt.remarks = PR_MARKER
    for row in receipt.items:
        row.warehouse = warehouse
    receipt.insert(ignore_permissions=True)
    receipt.submit()
    return receipt


def _ensure_purchase_invoice(receipt):
    existing = _get_submitted("Purchase Invoice", PI_MARKER)
    if existing:
        return existing

    from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice

    invoice = make_purchase_invoice(receipt.name)
    invoice.remarks = PI_MARKER
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return invoice


def _find_payment_entry(reference_doctype: str, reference_name: str):
    rows = frappe.db.sql(
        """
        select pe.name
        from `tabPayment Entry` pe
        inner join `tabPayment Entry Reference` ref on ref.parent = pe.name
        where pe.docstatus = 1
          and ref.reference_doctype = %s
          and ref.reference_name = %s
        order by pe.creation asc
        limit 1
        """,
        (reference_doctype, reference_name),
        as_dict=True,
    )
    return frappe.get_doc("Payment Entry", rows[0].name) if rows else None


def _ensure_supplier_payment(invoice, cash_account: str):
    existing = _find_payment_entry("Purchase Invoice", invoice.name)
    if existing:
        return existing

    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    payment = get_payment_entry("Purchase Invoice", invoice.name)
    payment.mode_of_payment = "Cash"
    payment.paid_from = cash_account
    payment.insert(ignore_permissions=True)
    payment.submit()
    return payment


def _ensure_stock_sale(customer: str, item_code: str, warehouse: str):
    existing = _get_submitted("Sales Invoice", SALE_MARKER)
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
            "set_warehouse": warehouse,
            "update_stock": 1,
            "remarks": SALE_MARKER,
            "items": [
                {
                    "item_code": item_code,
                    "qty": SALE_QTY,
                    "uom": "Nos",
                    "rate": SELL_RATE,
                    "warehouse": warehouse,
                }
            ],
        }
    )
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return invoice


def _ensure_stock_return(source_invoice):
    name = frappe.db.get_value(
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
    if name:
        return frappe.get_doc("Sales Invoice", name)

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


def _sle_qty(voucher_type: str, voucher_no: str, item_code: str) -> float:
    result = frappe.db.sql(
        """
        select coalesce(sum(actual_qty), 0)
        from `tabStock Ledger Entry`
        where voucher_type = %s and voucher_no = %s and item_code = %s and is_cancelled = 0
        """,
        (voucher_type, voucher_no, item_code),
    )
    return flt(result[0][0] if result else 0)


def _bin_qty(item_code: str, warehouse: str) -> float:
    return flt(
        frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty") or 0
    )


def run() -> dict:
    """Exercise ERPNext's native purchasing, stock, sale, return and AP paths."""

    _assert_safe_site()
    ledgix_before = _ledgix_counts()

    warehouse = _leaf_warehouse()
    supplier = _ensure_supplier()
    customer = _ensure_customer()
    item_code = _ensure_stock_item()
    buying_item_price = _ensure_item_price(item_code, BUYING_PRICE_LIST, BUY_RATE)
    selling_item_price = _ensure_item_price(item_code, SELLING_PRICE_LIST, SELL_RATE)
    cash_account = _ensure_cash_mode_account()

    purchase_order = _ensure_purchase_order(supplier, item_code, warehouse)
    purchase_receipt = _ensure_purchase_receipt(purchase_order, warehouse)
    purchase_invoice = _ensure_purchase_invoice(purchase_receipt)
    supplier_payment = _ensure_supplier_payment(purchase_invoice, cash_account)
    purchase_invoice.reload()

    stock_sale = _ensure_stock_sale(customer, item_code, warehouse)
    stock_return = _ensure_stock_return(stock_sale)
    stock_sale.reload()
    stock_return.reload()

    ledgix_after = _ledgix_counts()

    evidence = {
        "site": frappe.local.site,
        "company": TEST_COMPANY,
        "warehouse": warehouse,
        "supplier": supplier,
        "customer": customer,
        "item": {
            "name": item_code,
            "is_stock_item": bool(frappe.db.get_value("Item", item_code, "is_stock_item")),
            "buying_item_price": buying_item_price,
            "selling_item_price": selling_item_price,
            "bin_qty_after_flow": _bin_qty(item_code, warehouse),
        },
        "purchase_path": {
            "purchase_order": purchase_order.name,
            "purchase_order_docstatus": purchase_order.docstatus,
            "purchase_receipt": purchase_receipt.name,
            "purchase_receipt_docstatus": purchase_receipt.docstatus,
            "purchase_receipt_sle_qty": _sle_qty("Purchase Receipt", purchase_receipt.name, item_code),
            "purchase_invoice": purchase_invoice.name,
            "purchase_invoice_docstatus": purchase_invoice.docstatus,
            "purchase_invoice_gl_entries": _gl_count("Purchase Invoice", purchase_invoice.name),
            "purchase_invoice_outstanding_after_payment": flt(purchase_invoice.outstanding_amount),
            "supplier_payment": supplier_payment.name,
            "supplier_payment_docstatus": supplier_payment.docstatus,
            "supplier_payment_gl_entries": _gl_count("Payment Entry", supplier_payment.name),
        },
        "stock_sale_return_path": {
            "sales_invoice": stock_sale.name,
            "sales_invoice_docstatus": stock_sale.docstatus,
            "sales_invoice_gl_entries": _gl_count("Sales Invoice", stock_sale.name),
            "sales_invoice_sle_qty": _sle_qty("Sales Invoice", stock_sale.name, item_code),
            "return_invoice": stock_return.name,
            "return_docstatus": stock_return.docstatus,
            "return_against": stock_return.return_against,
            "return_gl_entries": _gl_count("Sales Invoice", stock_return.name),
            "return_sle_qty": _sle_qty("Sales Invoice", stock_return.name, item_code),
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
        "purchase_receipt_submitted": purchase_receipt.docstatus == 1,
        "purchase_receipt_added_stock": abs(
            evidence["purchase_path"]["purchase_receipt_sle_qty"] - PURCHASE_QTY
        ) < 0.005,
        "purchase_invoice_submitted": purchase_invoice.docstatus == 1,
        "purchase_invoice_has_gl": evidence["purchase_path"]["purchase_invoice_gl_entries"] > 0,
        "supplier_payment_submitted": supplier_payment.docstatus == 1,
        "supplier_payment_has_gl": evidence["purchase_path"]["supplier_payment_gl_entries"] > 0,
        "purchase_invoice_fully_paid": abs(
            evidence["purchase_path"]["purchase_invoice_outstanding_after_payment"]
        ) < 0.005,
        "stock_sale_submitted": stock_sale.docstatus == 1,
        "stock_sale_has_gl": evidence["stock_sale_return_path"]["sales_invoice_gl_entries"] > 0,
        "stock_sale_reduced_stock": abs(
            evidence["stock_sale_return_path"]["sales_invoice_sle_qty"] + SALE_QTY
        ) < 0.005,
        "stock_return_submitted": stock_return.docstatus == 1,
        "stock_return_linked": stock_return.return_against == stock_sale.name,
        "stock_return_has_gl": evidence["stock_sale_return_path"]["return_gl_entries"] > 0,
        "stock_return_restored_stock": abs(
            evidence["stock_sale_return_path"]["return_sle_qty"] - SALE_QTY
        ) < 0.005,
        "final_stock_matches_purchase_qty": abs(
            evidence["item"]["bin_qty_after_flow"] - PURCHASE_QTY
        ) < 0.005,
        "no_parallel_ledgix_docs_created": evidence["parallel_ledgix_guard"]["unchanged"],
    }

    evidence["checks"] = checks
    evidence["passed"] = all(checks.values())

    frappe.db.commit()
    return evidence
