from __future__ import annotations

import frappe
from frappe.utils import flt, get_datetime, now_datetime, nowdate

from ledgix_saas.migration.erpnext_integration_bootstrap import (
    CURRENCY,
    INTEGRATION_SITE,
    TEST_COMPANY,
)
from ledgix_saas.migration.erpnext_stock_purchase_behavioral_spike import (
    SELL_RATE,
    TEST_ITEM,
    _bin_qty,
    _ensure_cash_mode_account,
    _leaf_warehouse,
)


TEST_POS_PROFILE = "Ledgix ERPNext POS Spike"
TEST_POS_CUSTOMER = "Ledgix POS Spike Customer"
POS_MARKER = "LEDGIX-ERPNEXT-POS-SPLIT-SPIKE-V1"
POS_USER = "Administrator"
PRIMARY_MODE = "Cash"
SECONDARY_MODE = "Credit Card"
POS_QTY = 1.0
CASH_SHARE = 0.60
SECONDARY_SHARE = 0.40


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing ERPNext POS behavioral spike on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )

    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing; run the integration bootstrap first.")

    if not frappe.db.exists("Item", TEST_ITEM):
        frappe.throw(
            f"Stock test item {TEST_ITEM!r} is missing; run the stock/purchase behavioral spike first."
        )


def _count_if_exists(doctype: str) -> int | None:
    if not frappe.db.exists("DocType", doctype):
        return None
    return frappe.db.count(doctype)


def _ledgix_counts() -> dict:
    doctypes = ["Ledgix Sale", "Ledgix Payment", "Ledgix POS Shift", "Ledgix Stock Movement"]
    return {doctype: _count_if_exists(doctype) for doctype in doctypes}


def _ensure_customer() -> str:
    existing = frappe.db.get_value("Customer", {"customer_name": TEST_POS_CUSTOMER}, "name")
    if existing:
        return existing

    customer = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": TEST_POS_CUSTOMER,
            "customer_type": "Individual",
            "customer_group": "Individual",
            "territory": "Pakistan",
        }
    )
    customer.insert(ignore_permissions=True)
    return customer.name


def _leaf_cost_center() -> str:
    rows = frappe.get_all(
        "Cost Center",
        filters={"company": TEST_COMPANY, "is_group": 0, "disabled": 0},
        pluck="name",
        order_by="name asc",
        limit=1,
    )
    if not rows:
        frappe.throw(f"No active leaf Cost Center exists for {TEST_COMPANY!r}.")
    return rows[0]


def _write_off_account() -> str:
    preferred = frappe.get_all(
        "Account",
        filters={
            "company": TEST_COMPANY,
            "is_group": 0,
            "disabled": 0,
            "root_type": "Expense",
            "account_name": ["like", "%Write Off%"],
        },
        pluck="name",
        order_by="name asc",
        limit=1,
    )
    if preferred:
        return preferred[0]

    rows = frappe.get_all(
        "Account",
        filters={"company": TEST_COMPANY, "is_group": 0, "disabled": 0, "root_type": "Expense"},
        pluck="name",
        order_by="name asc",
        limit=1,
    )
    if not rows:
        frappe.throw(f"No leaf Expense account exists for {TEST_COMPANY!r}.")
    return rows[0]


def _secondary_payment_account(cash_account: str) -> str:
    bank = frappe.get_all(
        "Account",
        filters={"company": TEST_COMPANY, "account_type": "Bank", "is_group": 0, "disabled": 0},
        pluck="name",
        order_by="name asc",
        limit=1,
    )
    return bank[0] if bank else cash_account


def _ensure_mode_account(mode_name: str, account: str) -> str:
    if not frappe.db.exists("Mode of Payment", mode_name):
        frappe.throw(f"Mode of Payment {mode_name!r} is missing from ERPNext fixtures.")

    mode = frappe.get_doc("Mode of Payment", mode_name)
    row = next((entry for entry in mode.accounts if entry.company == TEST_COMPANY), None)
    if not row:
        mode.append("accounts", {"company": TEST_COMPANY, "default_account": account})
        mode.save(ignore_permissions=True)
    elif row.default_account != account:
        row.default_account = account
        mode.save(ignore_permissions=True)
    return account


def _ensure_pos_profile(customer: str, warehouse: str, cash_account: str) -> str:
    if frappe.db.exists("POS Profile", TEST_POS_PROFILE):
        return TEST_POS_PROFILE

    secondary_account = _secondary_payment_account(cash_account)
    _ensure_mode_account(PRIMARY_MODE, cash_account)
    _ensure_mode_account(SECONDARY_MODE, secondary_account)

    profile = frappe.get_doc(
        {
            "doctype": "POS Profile",
            "name": TEST_POS_PROFILE,
            "company": TEST_COMPANY,
            "warehouse": warehouse,
            "customer": customer,
            "selling_price_list": "Standard Selling",
            "currency": CURRENCY,
            "write_off_account": _write_off_account(),
            "write_off_cost_center": _leaf_cost_center(),
            "allow_partial_payment": 1,
            "validate_stock_on_save": 1,
            "payments": [
                {"mode_of_payment": PRIMARY_MODE, "default": 1},
                {"mode_of_payment": SECONDARY_MODE, "default": 0},
            ],
            "applicable_for_users": [{"user": POS_USER, "default": 1}],
        }
    )
    profile.insert(ignore_permissions=True)
    return profile.name


def _existing_pos_invoice():
    name = frappe.db.get_value(
        "POS Invoice",
        {"company": TEST_COMPANY, "remarks": POS_MARKER, "docstatus": 1},
        "name",
    )
    return frappe.get_doc("POS Invoice", name) if name else None


def _existing_closing_for_invoice(invoice_name: str):
    rows = frappe.db.sql(
        """
        select ref.parent
        from `tabPOS Invoice Reference` ref
        inner join `tabPOS Closing Entry` closing on closing.name = ref.parent
        where ref.parenttype = 'POS Closing Entry'
          and ref.pos_invoice = %s
          and closing.docstatus = 1
        order by closing.creation asc
        limit 1
        """,
        invoice_name,
        as_dict=True,
    )
    return frappe.get_doc("POS Closing Entry", rows[0].parent) if rows else None


def _ensure_opening(profile: str, period_start=None):
    name = frappe.db.get_value(
        "POS Opening Entry",
        {"company": TEST_COMPANY, "pos_profile": profile, "user": POS_USER, "status": "Open", "docstatus": 1},
        "name",
    )
    if name:
        return frappe.get_doc("POS Opening Entry", name)

    opening = frappe.get_doc(
        {
            "doctype": "POS Opening Entry",
            "period_start_date": period_start or now_datetime(),
            "posting_date": nowdate(),
            "company": TEST_COMPANY,
            "pos_profile": profile,
            "user": POS_USER,
            "balance_details": [
                {"mode_of_payment": PRIMARY_MODE, "opening_amount": 0},
                {"mode_of_payment": SECONDARY_MODE, "opening_amount": 0},
            ],
        }
    )
    opening.insert(ignore_permissions=True)
    opening.submit()
    return opening


def _ensure_pos_invoice(customer: str, profile: str, warehouse: str):
    existing = _existing_pos_invoice()
    if existing:
        return existing

    total = flt(SELL_RATE * POS_QTY)
    cash_amount = flt(total * CASH_SHARE, 2)
    secondary_amount = flt(total - cash_amount, 2)

    invoice = frappe.get_doc(
        {
            "doctype": "POS Invoice",
            "company": TEST_COMPANY,
            "customer": customer,
            "posting_date": nowdate(),
            "currency": CURRENCY,
            "selling_price_list": "Standard Selling",
            "pos_profile": profile,
            "set_warehouse": warehouse,
            "remarks": POS_MARKER,
            "is_pos": 1,
            "items": [
                {
                    "item_code": TEST_ITEM,
                    "qty": POS_QTY,
                    "uom": "Nos",
                    "rate": SELL_RATE,
                    "warehouse": warehouse,
                }
            ],
            "payments": [
                {"mode_of_payment": PRIMARY_MODE, "amount": cash_amount},
                {
                    "mode_of_payment": SECONDARY_MODE,
                    "amount": secondary_amount,
                    "reference_no": "LEDGIX-SPLIT-SPIKE",
                },
            ],
        }
    )
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return invoice


def _ensure_closing(opening, invoice):
    existing = _existing_closing_for_invoice(invoice.name)
    if existing:
        return existing

    from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening

    closing = make_closing_entry_from_opening(opening)
    if not any(row.pos_invoice == invoice.name for row in closing.pos_transactions):
        frappe.throw(
            f"POS closing entry did not pick up expected POS Invoice {invoice.name}; "
            "check opening period/profile/user alignment."
        )
    closing.insert(ignore_permissions=True)
    closing.submit()
    return closing


def _sle_qty(voucher_type: str, voucher_no: str) -> float:
    result = frappe.db.sql(
        """
        select coalesce(sum(actual_qty), 0)
        from `tabStock Ledger Entry`
        where voucher_type = %s and voucher_no = %s and item_code = %s and is_cancelled = 0
        """,
        (voucher_type, voucher_no, TEST_ITEM),
    )
    return flt(result[0][0] if result else 0)


def _gl_count(voucher_type: str, voucher_no: str) -> int:
    return frappe.db.count(
        "GL Entry",
        {"voucher_type": voucher_type, "voucher_no": voucher_no, "is_cancelled": 0},
    )


def run() -> dict:
    """Exercise ERPNext native POS opening, split payment, stock and closing consolidation."""

    _assert_safe_site()
    ledgix_before = _ledgix_counts()

    warehouse = _leaf_warehouse()
    starting_qty = _bin_qty(TEST_ITEM, warehouse)
    if starting_qty < POS_QTY:
        frappe.throw(
            f"Insufficient stock for POS spike: {starting_qty} available in {warehouse!r}; "
            "run the stock/purchase behavioral spike first."
        )

    customer = _ensure_customer()
    cash_account = _ensure_cash_mode_account()
    profile = _ensure_pos_profile(customer, warehouse, cash_account)

    existing_invoice = _existing_pos_invoice()
    if existing_invoice and existing_invoice.consolidated_invoice:
        opening_name = frappe.db.get_value(
            "POS Opening Entry",
            {"pos_profile": profile, "pos_closing_entry": ["is", "set"]},
            "name",
            order_by="creation desc",
        )
        opening = frappe.get_doc("POS Opening Entry", opening_name) if opening_name else None
        invoice = existing_invoice
        closing = _existing_closing_for_invoice(invoice.name)
        if not closing:
            frappe.throw(f"Consolidated POS Invoice {invoice.name} has no submitted POS Closing Entry reference.")
    else:
        period_start = None
        if existing_invoice:
            period_start = get_datetime(
                f"{existing_invoice.posting_date} {existing_invoice.posting_time or '00:00:00'}"
            )
        opening = _ensure_opening(profile, period_start=period_start)
        invoice = existing_invoice or _ensure_pos_invoice(customer, profile, warehouse)
        closing = _ensure_closing(opening, invoice)

    invoice.reload()
    closing.reload()
    if opening:
        opening.reload()

    consolidated_invoice = invoice.consolidated_invoice
    if not consolidated_invoice:
        frappe.throw(f"POS Invoice {invoice.name} was not linked to a consolidated Sales Invoice after closing.")

    payment_rows = {
        row.mode_of_payment: flt(row.amount)
        for row in invoice.payments
        if row.mode_of_payment in {PRIMARY_MODE, SECONDARY_MODE}
    }
    reconciliation_modes = {
        row.mode_of_payment: {
            "opening_amount": flt(row.opening_amount),
            "expected_amount": flt(row.expected_amount),
            "closing_amount": flt(row.closing_amount),
        }
        for row in closing.payment_reconciliation
    }

    ending_qty = _bin_qty(TEST_ITEM, warehouse)
    ledgix_after = _ledgix_counts()

    evidence = {
        "site": frappe.local.site,
        "company": TEST_COMPANY,
        "warehouse": warehouse,
        "customer": customer,
        "pos_profile": profile,
        "opening_entry": opening.name if opening else None,
        "opening_status": opening.status if opening else None,
        "pos_invoice": {
            "name": invoice.name,
            "docstatus": invoice.docstatus,
            "grand_total": flt(invoice.grand_total),
            "paid_amount": flt(invoice.paid_amount),
            "outstanding_amount": flt(invoice.outstanding_amount),
            "payments": payment_rows,
            "stock_ledger_qty": _sle_qty("POS Invoice", invoice.name),
            "consolidated_invoice": consolidated_invoice,
        },
        "closing_entry": {
            "name": closing.name,
            "docstatus": closing.docstatus,
            "status": closing.status,
            "grand_total": flt(closing.grand_total),
            "payment_reconciliation": reconciliation_modes,
        },
        "consolidated_sales_invoice": {
            "name": consolidated_invoice,
            "docstatus": frappe.db.get_value("Sales Invoice", consolidated_invoice, "docstatus"),
            "gl_entries": _gl_count("Sales Invoice", consolidated_invoice),
        },
        "stock": {
            "starting_qty": starting_qty,
            "ending_qty": ending_qty,
            "expected_delta": -POS_QTY,
            "actual_delta": flt(ending_qty - starting_qty),
        },
        "parallel_ledgix_guard": {
            "before": ledgix_before,
            "after": ledgix_after,
            "unchanged": ledgix_before == ledgix_after,
        },
    }

    checks = {
        "pos_profile_exists": frappe.db.exists("POS Profile", profile) is not None,
        "opening_submitted": opening is not None and opening.docstatus == 1,
        "opening_closed": opening is not None and opening.status == "Closed",
        "pos_invoice_submitted": invoice.docstatus == 1,
        "split_payment_has_cash": PRIMARY_MODE in payment_rows and payment_rows[PRIMARY_MODE] > 0,
        "split_payment_has_secondary": SECONDARY_MODE in payment_rows and payment_rows[SECONDARY_MODE] > 0,
        "split_payment_sums_to_total": abs(sum(payment_rows.values()) - flt(invoice.grand_total)) < 0.005,
        "pos_invoice_fully_paid": abs(flt(invoice.outstanding_amount)) < 0.005,
        "pos_stock_reduced_once": abs(evidence["stock"]["actual_delta"] + POS_QTY) < 0.005,
        "closing_submitted": closing.docstatus == 1,
        "closing_has_both_payment_modes": {PRIMARY_MODE, SECONDARY_MODE}.issubset(reconciliation_modes),
        "consolidated_invoice_linked": bool(consolidated_invoice),
        "consolidated_invoice_submitted": evidence["consolidated_sales_invoice"]["docstatus"] == 1,
        "consolidated_invoice_has_gl": evidence["consolidated_sales_invoice"]["gl_entries"] > 0,
        "no_parallel_ledgix_docs_created": evidence["parallel_ledgix_guard"]["unchanged"],
    }

    evidence["checks"] = checks
    evidence["passed"] = all(checks.values())

    frappe.db.commit()
    return evidence
