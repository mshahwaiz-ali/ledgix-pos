"""Supported local operating-data entrypoint for Ledgix acceptance testing.

The transaction engine remains ERPNext-native. This wrapper supplies a
coherent fictional supermarket dataset, local-only prerequisites, cleanup of
known older Ledgix demo/spike artifacts, and strict post-load verification.
"""

import frappe
from frappe.utils import add_days, cint, flt, getdate, today

from ledgix_saas.services import erpnext_selling
from ledgix_saas.setup import erpnext_demo_data as native
from ledgix_saas.setup import retail_account_setup
from ledgix_saas.setup import retail_local_hygiene
from ledgix_saas.setup import retail_operating_profile as retail

SEED = retail.SEED


def inspect_site() -> dict:
    retail.configure()
    native._local_only()
    company = native._company()
    doctypes = (
        "Item",
        "Customer",
        "Supplier",
        "Purchase Order",
        "Purchase Receipt",
        "Purchase Invoice",
        "Sales Invoice",
        "POS Invoice",
        "Payment Entry",
        "Stock Entry",
        "Stock Reconciliation",
        "POS Opening Entry",
        "POS Closing Entry",
        "Ledgix FBR Submission Log",
    )
    counts = {
        doctype: frappe.db.count(doctype)
        for doctype in doctypes
        if frappe.db.exists("DocType", doctype)
    }
    return {
        "site": frappe.local.site,
        "company": company,
        "counts": counts,
        "legacy_retirement_status": frappe.db.get_single_value(
            "Ledgix Legacy Retirement State", "status"
        )
        if frappe.db.exists("DocType", "Ledgix Legacy Retirement State")
        else "Not Installed",
        "fbr_mode": frappe.db.get_single_value("Ledgix FBR Settings", "mode") or "Disabled",
        "dataset": SEED,
        "retail_data_present": bool(
            frappe.db.exists(
                "POS Invoice", {"custom_ledgix_client_sale_id": ["like", f"{SEED}-%"]}
            )
            or frappe.db.exists(
                "Sales Invoice", {"custom_ledgix_client_sale_id": ["like", f"{SEED}-%"]}
            )
        ),
        "visible_old_artifacts": retail_local_hygiene.visible_old_artifacts(),
    }


def cleanup_seed_transactions() -> dict:
    retail.configure()
    return native.cleanup_seed_transactions()


def cleanup_old_local_artifacts() -> dict:
    return retail_local_hygiene.cleanup_old_local_artifacts()


def _normalize_retail_customers(company: str) -> None:
    """Move reused synthetic customers out of historical Demo groups."""
    for name, customer_type, group_token, credit_limit in retail.CUSTOMERS:
        if not frappe.db.exists("Customer", name):
            continue
        doc = frappe.get_doc("Customer", name)
        target_group = retail.CUSTOMER_GROUP_MAP.get(group_token, group_token)
        changed = False
        if doc.customer_type != customer_type:
            doc.customer_type = customer_type
            changed = True
        if doc.customer_group != target_group:
            doc.customer_group = target_group
            changed = True
        if credit_limit:
            row = next(
                (entry for entry in (doc.get("credit_limits") or []) if entry.company == company),
                None,
            )
            if row:
                if flt(row.credit_limit) != flt(credit_limit):
                    row.credit_limit = credit_limit
                    changed = True
            else:
                doc.append("credit_limits", {"company": company, "credit_limit": credit_limit})
                changed = True
        if changed:
            doc.save(ignore_permissions=True)


def verify() -> dict:
    retail.configure()
    native._local_only()
    company = native._company()
    pos_sales = frappe.db.count(
        "POS Invoice",
        {"custom_ledgix_client_sale_id": ["like", f"{SEED}-%"], "docstatus": 1, "is_return": 0},
    )
    pos_returns = frappe.db.count(
        "POS Invoice",
        {"custom_ledgix_client_return_id": ["like", f"{SEED}-%"], "docstatus": 1, "is_return": 1},
    )
    b2b_sales = frappe.db.count(
        "Sales Invoice",
        {"custom_ledgix_client_sale_id": ["like", f"{SEED}-%"], "docstatus": 1, "is_return": 0},
    )
    b2b_returns = frappe.db.count(
        "Sales Invoice",
        {"custom_ledgix_client_return_id": ["like", f"{SEED}-%"], "docstatus": 1, "is_return": 1},
    )
    payments = frappe.db.count(
        "Payment Entry",
        {"custom_ledgix_client_payment_id": ["like", f"{SEED}-%"], "docstatus": 1},
    )
    purchases = frappe.db.count(
        "Purchase Invoice",
        {"custom_ledgix_client_purchase_invoice_id": ["like", f"{SEED}-%"], "docstatus": 1},
    )
    stock_entries = frappe.db.count(
        "Stock Entry",
        {"custom_ledgix_client_stock_id": ["like", f"{SEED}-%"], "docstatus": 1},
    )

    trade_outstanding = 0.0
    overdue = 0.0
    for customer, _customer_type, group, _limit in retail.CUSTOMERS:
        if group != "Demo Trade" or not frappe.db.exists("Customer", customer):
            continue
        values = erpnext_selling.get_customer_receivables(customer, company=company)
        trade_outstanding += flt(values.get("outstanding"))
        overdue += flt(values.get("overdue"))

    negative = frappe.get_all(
        "Bin",
        filters={
            "warehouse": ["like", f"{retail.WAREHOUSE_POS_NAME}%"],
            "actual_qty": ["<", -0.001],
        },
        fields=["item_code", "warehouse", "actual_qty"],
        order_by="item_code asc, warehouse asc",
        limit_page_length=0,
    )
    low_or_out = frappe.get_all(
        "Bin",
        filters={
            "warehouse": ["like", f"{retail.WAREHOUSE_POS_NAME}%"],
            "actual_qty": ["<=", 5],
        },
        fields=["item_code", "warehouse", "actual_qty"],
        order_by="actual_qty asc, item_code asc",
        limit_page_length=0,
    )
    split_payment_invoices = frappe.db.sql(
        """
        select count(*)
        from (
            select parent
            from `tabPOS Invoice Payment`
            where parenttype = 'POS Invoice'
            group by parent
            having count(*) > 1
        ) split_rows
        inner join `tabPOS Invoice` p on p.name = split_rows.parent
        where p.docstatus = 1 and p.custom_ledgix_client_sale_id like %s
        """,
        (f"{SEED}-%",),
    )[0][0]
    unconsolidated_pos = frappe.db.sql(
        """
        select name, is_return, posting_date, posting_time
        from `tabPOS Invoice`
        where docstatus = 1
          and (
            custom_ledgix_client_sale_id like %s
            or custom_ledgix_client_return_id like %s
          )
          and ifnull(consolidated_invoice, '') = ''
        order by posting_date asc, posting_time asc, name asc
        """,
        (f"{SEED}-%", f"{SEED}-%"),
        as_dict=True,
    )

    fbr = frappe.get_single("Ledgix FBR Settings")
    fbr_safe = not cint(fbr.get("enabled")) and str(fbr.get("mode") or "Disabled") == "Disabled"
    active_opening = frappe.db.get_value(
        "POS Opening Entry",
        {
            "pos_profile": retail.POS_PROFILE,
            "user": "Administrator",
            "status": "Open",
            "docstatus": 1,
        },
        "name",
        order_by="period_start_date desc",
    )
    old_visible = retail_local_hygiene.visible_old_artifacts()
    result = {
        "dataset": SEED,
        "company": company,
        "items": frappe.db.count(
            "Item", {"item_code": ["like", f"{retail.ITEM_CODE_PREFIX}%"]}
        ),
        "customers": sum(
            1 for row in retail.CUSTOMERS if frappe.db.exists("Customer", row[0])
        ),
        "suppliers": sum(1 for name in retail.SUPPLIERS if frappe.db.exists("Supplier", name)),
        "pos_profile": retail.POS_PROFILE if frappe.db.exists("POS Profile", retail.POS_PROFILE) else None,
        "pos_sales": pos_sales,
        "b2b_sales": b2b_sales,
        "total_sales": pos_sales + b2b_sales,
        "pos_returns": pos_returns,
        "b2b_returns": b2b_returns,
        "payments": payments,
        "purchase_invoices": purchases,
        "stock_entries": stock_entries,
        "trade_outstanding": flt(trade_outstanding, 2),
        "trade_overdue": flt(overdue, 2),
        "split_payment_invoices": int(split_payment_invoices or 0),
        "low_or_out_stock": [dict(row) for row in low_or_out],
        "negative_retail_bins": [dict(row) for row in negative],
        "unconsolidated_managed_pos": [dict(row) for row in unconsolidated_pos],
        "active_pos_opening": active_opening,
        "fbr_transport_disabled": fbr_safe,
        "visible_old_artifacts": old_visible,
    }
    result["ok"] = bool(
        result["items"] >= 45
        and result["customers"] >= 12
        and result["suppliers"] >= 7
        and result["total_sales"] >= 100
        and result["pos_returns"] >= 3
        and result["b2b_returns"] >= 2
        and result["purchase_invoices"] >= 6
        and result["payments"] >= 6
        and result["split_payment_invoices"] >= 2
        and result["trade_outstanding"] > 0
        and result["low_or_out_stock"]
        and not result["negative_retail_bins"]
        and not result["unconsolidated_managed_pos"]
        and result["active_pos_opening"]
        and fbr_safe
        and not old_visible
    )
    return result


def seed() -> dict:
    """Create the realistic retail operating dataset; safe to rerun locally."""
    retail.configure()
    retail_account_setup.configure()
    native._local_only()
    old_user = frappe.session.user or "Administrator"
    frappe.set_user("Administrator")
    base_date = getdate(today())
    try:
        native._disable_fbr_transport()
        company = native._company()
        fiscal = retail_local_hygiene.ensure_fiscal_year_window(
            company, add_days(base_date, -90), base_date
        )
        context = native._masters()
        _normalize_retail_customers(context["company"])
        native._inventory(
            context["company"], context["main"], context["pos"], context["back"], base_date
        )
        retail_sales = native._retail_sales(context["company"], context["pos"], base_date)
        b2b_sales = native._b2b_sales(context["company"], context["pos"], base_date)

        # Keep the dedicated return shift fully historical. Native return rows use
        # a fixed 15:xx posting time; putting both opening and returns yesterday
        # guarantees they are inside the closing window regardless of when the
        # loader runs today.
        return_date = add_days(base_date, -1)
        return_opening = native._opening(context["company"], return_date, 99)
        for sequence, source in enumerate(retail_sales[8::23][:4], 1):
            native._pos_return(source, sequence, return_date)
        native._close_opening(return_opening, 99)
        for sequence, source in enumerate(b2b_sales[2::4][:3], 1):
            native._b2b_return(
                source,
                sequence,
                min(add_days(source.posting_date, 5), base_date),
            )

        native._shape_stock(context["company"], context["pos"], base_date)
        native._opening(context["company"], base_date, 100)

        # Commit the complete operating dataset first. Old-group cleanup is run
        # once more by the shell wrapper after reused customers are normalized.
        result = verify()
        # Old visible artifacts are permitted at this intermediate point only;
        # all core operating assertions must already be green.
        core_ok = bool(
            result["items"] >= 45
            and result["customers"] >= 12
            and result["suppliers"] >= 7
            and result["total_sales"] >= 100
            and result["pos_returns"] >= 3
            and result["b2b_returns"] >= 2
            and result["purchase_invoices"] >= 6
            and result["payments"] >= 6
            and result["split_payment_invoices"] >= 2
            and result["trade_outstanding"] > 0
            and result["low_or_out_stock"]
            and not result["negative_retail_bins"]
            and not result["unconsolidated_managed_pos"]
            and result["active_pos_opening"]
            and result["fbr_transport_disabled"]
        )
        if not core_ok:
            frappe.throw(f"Retail operating data verification failed: {result}")
        frappe.db.commit()
        return {"created": True, **fiscal, **result, "core_ok": True}
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.set_user(old_user)


__all__ = [
    "SEED",
    "inspect_site",
    "cleanup_seed_transactions",
    "cleanup_old_local_artifacts",
    "seed",
    "verify",
]
