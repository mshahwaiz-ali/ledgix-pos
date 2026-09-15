from __future__ import annotations

import frappe
from frappe.utils import flt, get_datetime

from ledgix_saas.migration import erpnext_pos_behavioral_spike as base


def _payment_account(mode_name: str, company: str) -> str:
    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mode_name, "company": company},
        "default_account",
    )
    if not account:
        frappe.throw(f"Mode of Payment {mode_name!r} has no default account for {company!r}.")
    return account


def _payment_type(mode_name: str) -> str:
    payment_type = frappe.db.get_value("Mode of Payment", mode_name, "type")
    if not payment_type:
        frappe.throw(f"Mode of Payment {mode_name!r} has no payment type.")
    return payment_type


def _ensure_pos_profile(customer: str, warehouse: str, cash_account: str) -> str:
    """Create or repair the isolated POS profile so reruns survive partial failures."""

    secondary_account = base._secondary_payment_account(cash_account)
    base._ensure_mode_account(base.PRIMARY_MODE, cash_account)
    base._ensure_mode_account(base.SECONDARY_MODE, secondary_account)

    if frappe.db.exists("POS Profile", base.TEST_POS_PROFILE):
        profile = frappe.get_doc("POS Profile", base.TEST_POS_PROFILE)
    else:
        profile = frappe.get_doc(
            {
                "doctype": "POS Profile",
                "name": base.TEST_POS_PROFILE,
            }
        )

    profile.company = base.TEST_COMPANY
    profile.warehouse = warehouse
    profile.customer = customer
    profile.selling_price_list = "Standard Selling"
    profile.currency = base.CURRENCY
    profile.write_off_account = base._write_off_account()
    profile.write_off_cost_center = base._leaf_cost_center()
    profile.allow_partial_payment = 1
    profile.validate_stock_on_save = 1
    profile.disabled = 0
    profile.set(
        "payments",
        [
            {"mode_of_payment": base.PRIMARY_MODE, "default": 1},
            {"mode_of_payment": base.SECONDARY_MODE, "default": 0},
        ],
    )
    profile.set("applicable_for_users", [{"user": base.POS_USER, "default": 1}])

    if profile.is_new():
        profile.insert(ignore_permissions=True)
    else:
        profile.save(ignore_permissions=True)

    return profile.name


def _ensure_pos_invoice(customer: str, profile: str, warehouse: str):
    existing = base._existing_pos_invoice()
    if existing:
        return existing

    total = flt(base.SELL_RATE * base.POS_QTY)
    cash_amount = flt(total * base.CASH_SHARE, 2)
    secondary_amount = flt(total - cash_amount, 2)

    cash_account = _payment_account(base.PRIMARY_MODE, base.TEST_COMPANY)
    secondary_account = _payment_account(base.SECONDARY_MODE, base.TEST_COMPANY)

    invoice = frappe.get_doc(
        {
            "doctype": "POS Invoice",
            "company": base.TEST_COMPANY,
            "customer": customer,
            "posting_date": frappe.utils.nowdate(),
            "currency": base.CURRENCY,
            "selling_price_list": "Standard Selling",
            "pos_profile": profile,
            "set_warehouse": warehouse,
            "remarks": base.POS_MARKER,
            "is_pos": 1,
            "items": [
                {
                    "item_code": base.TEST_ITEM,
                    "qty": base.POS_QTY,
                    "uom": "Nos",
                    "rate": base.SELL_RATE,
                    "warehouse": warehouse,
                }
            ],
            "payments": [
                {
                    "mode_of_payment": base.PRIMARY_MODE,
                    "amount": cash_amount,
                    "account": cash_account,
                    "type": _payment_type(base.PRIMARY_MODE),
                    "default": 1,
                },
                {
                    "mode_of_payment": base.SECONDARY_MODE,
                    "amount": secondary_amount,
                    "account": secondary_account,
                    "type": _payment_type(base.SECONDARY_MODE),
                    "default": 0,
                    "reference_no": "LEDGIX-SPLIT-SPIKE",
                },
            ],
        }
    )
    invoice.set_missing_values()
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    return invoice


def _consolidated_sle_qty(invoice_name: str) -> float:
    result = frappe.db.sql(
        """
        select coalesce(sum(actual_qty), 0)
        from `tabStock Ledger Entry`
        where voucher_type = 'Sales Invoice'
          and voucher_no = %s
          and item_code = %s
          and is_cancelled = 0
        """,
        (invoice_name, base.TEST_ITEM),
    )
    return flt(result[0][0] if result else 0)


def run() -> dict:
    """Rerun-safe ERPNext native POS opening/split-payment/closing spike."""

    base._assert_safe_site()
    ledgix_before = base._ledgix_counts()

    warehouse = base._leaf_warehouse()
    customer = base._ensure_customer()
    cash_account = base._ensure_cash_mode_account()
    profile = _ensure_pos_profile(customer, warehouse, cash_account)

    existing_invoice = base._existing_pos_invoice()
    if existing_invoice and existing_invoice.consolidated_invoice:
        invoice = existing_invoice
        closing = base._existing_closing_for_invoice(invoice.name)
        if not closing:
            frappe.throw(f"Consolidated POS Invoice {invoice.name} has no submitted POS Closing Entry reference.")
        opening = frappe.get_doc("POS Opening Entry", closing.pos_opening_entry)
    else:
        available = base._bin_qty(base.TEST_ITEM, warehouse)
        if available < base.POS_QTY:
            frappe.throw(
                f"Insufficient stock for POS spike: {available} available in {warehouse!r}; "
                "run the stock/purchase behavioral spike first."
            )

        period_start = None
        if existing_invoice:
            period_start = get_datetime(
                f"{existing_invoice.posting_date} {existing_invoice.posting_time or '00:00:00'}"
            )

        opening = base._ensure_opening(profile, period_start=period_start)
        invoice = existing_invoice or _ensure_pos_invoice(customer, profile, warehouse)
        closing = base._ensure_closing(opening, invoice)

    invoice.reload()
    closing.reload()
    opening.reload()

    consolidated_invoice = invoice.consolidated_invoice
    if not consolidated_invoice:
        frappe.throw(f"POS Invoice {invoice.name} was not linked to a consolidated Sales Invoice after closing.")

    consolidated_docstatus = frappe.db.get_value("Sales Invoice", consolidated_invoice, "docstatus")
    consolidated_gl_entries = base._gl_count("Sales Invoice", consolidated_invoice)
    consolidated_sle_qty = _consolidated_sle_qty(consolidated_invoice)
    pos_invoice_sle_qty = base._sle_qty("POS Invoice", invoice.name)

    payment_rows = {
        row.mode_of_payment: flt(row.amount)
        for row in invoice.payments
        if row.mode_of_payment in {base.PRIMARY_MODE, base.SECONDARY_MODE}
    }
    payment_accounts = {
        row.mode_of_payment: row.account
        for row in invoice.payments
        if row.mode_of_payment in {base.PRIMARY_MODE, base.SECONDARY_MODE}
    }
    reconciliation_modes = {
        row.mode_of_payment: {
            "opening_amount": flt(row.opening_amount),
            "expected_amount": flt(row.expected_amount),
            "closing_amount": flt(row.closing_amount),
        }
        for row in closing.payment_reconciliation
    }

    ledgix_after = base._ledgix_counts()

    evidence = {
        "site": frappe.local.site,
        "company": base.TEST_COMPANY,
        "warehouse": warehouse,
        "customer": customer,
        "pos_profile": profile,
        "opening_entry": opening.name,
        "opening_status": opening.status,
        "pos_invoice": {
            "name": invoice.name,
            "docstatus": invoice.docstatus,
            "grand_total": flt(invoice.grand_total),
            "paid_amount": flt(invoice.paid_amount),
            "outstanding_amount": flt(invoice.outstanding_amount),
            "payments": payment_rows,
            "payment_accounts": payment_accounts,
            "direct_stock_ledger_qty": pos_invoice_sle_qty,
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
            "docstatus": consolidated_docstatus,
            "gl_entries": consolidated_gl_entries,
            "stock_ledger_qty": consolidated_sle_qty,
        },
        "current_bin_qty": base._bin_qty(base.TEST_ITEM, warehouse),
        "parallel_ledgix_guard": {
            "before": ledgix_before,
            "after": ledgix_after,
            "unchanged": ledgix_before == ledgix_after,
        },
    }

    checks = {
        "pos_profile_exists": bool(frappe.db.exists("POS Profile", profile)),
        "opening_submitted": opening.docstatus == 1,
        "opening_closed": opening.status == "Closed",
        "pos_invoice_submitted": invoice.docstatus == 1,
        "split_payment_has_cash": base.PRIMARY_MODE in payment_rows and payment_rows[base.PRIMARY_MODE] > 0,
        "split_payment_has_secondary": (
            base.SECONDARY_MODE in payment_rows and payment_rows[base.SECONDARY_MODE] > 0
        ),
        "split_payment_accounts_populated": all(payment_accounts.values()),
        "split_payment_sums_to_total": abs(sum(payment_rows.values()) - flt(invoice.grand_total)) < 0.005,
        "pos_invoice_fully_paid": abs(flt(invoice.outstanding_amount)) < 0.005,
        "pos_invoice_does_not_double_post_stock": abs(pos_invoice_sle_qty) < 0.005,
        "closing_submitted": closing.docstatus == 1,
        "closing_has_both_payment_modes": {
            base.PRIMARY_MODE,
            base.SECONDARY_MODE,
        }.issubset(reconciliation_modes),
        "consolidated_invoice_linked": bool(consolidated_invoice),
        "consolidated_invoice_submitted": consolidated_docstatus == 1,
        "consolidated_invoice_has_gl": consolidated_gl_entries > 0,
        "consolidated_invoice_reduced_stock": abs(consolidated_sle_qty + base.POS_QTY) < 0.005,
        "no_parallel_ledgix_docs_created": evidence["parallel_ledgix_guard"]["unchanged"],
    }

    evidence["checks"] = checks
    evidence["passed"] = all(checks.values())
    frappe.db.commit()
    return evidence
