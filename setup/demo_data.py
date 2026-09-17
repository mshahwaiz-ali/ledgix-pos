"""Safe compatibility entrypoint for Ledgix local demo data.

The original pre-cutover seeder wrote legacy Ledgix Item/Sale/Purchase/Payment
DocTypes. Phase 12 froze those records as historical evidence. This module is the
single supported demo entrypoint and orchestrates the ERPNext-authoritative V2
seed without mutating those frozen ledgers.
"""

import frappe
from frappe.utils import add_days, cint, flt, getdate, today

from ledgix_saas.services import erpnext_selling
from ledgix_saas.setup import erpnext_demo_data as native

SEED = native.SEED


def inspect_site() -> dict:
    return native.inspect_site()


def cleanup_seed_transactions() -> dict:
    return native.cleanup_seed_transactions()


def verify() -> dict:
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
    for customer, _customer_type, group, _limit in native.CUSTOMERS:
        if group != "Demo Trade" or not frappe.db.exists("Customer", customer):
            continue
        values = erpnext_selling.get_customer_receivables(customer, company=company)
        trade_outstanding += flt(values.get("outstanding"))
        overdue += flt(values.get("overdue"))

    negative = frappe.get_all(
        "Bin",
        filters={"warehouse": ["like", "Ledgix Demo%"], "actual_qty": ["<", -0.001]},
        fields=["item_code", "warehouse", "actual_qty"],
        order_by="item_code asc, warehouse asc",
        limit_page_length=0,
    )
    low_or_out = frappe.get_all(
        "Bin",
        filters={"warehouse": ["like", "Ledgix Demo POS Floor%"], "actual_qty": ["<=", 5]},
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

    fbr = frappe.get_single("Ledgix FBR Settings")
    fbr_safe = not cint(fbr.get("enabled")) and str(fbr.get("mode") or "Disabled") == "Disabled"
    active_opening = frappe.db.get_value(
        "POS Opening Entry",
        {
            "pos_profile": native.POS_PROFILE,
            "user": "Administrator",
            "status": "Open",
            "docstatus": 1,
        },
        "name",
        order_by="period_start_date desc",
    )
    result = {
        "seed": SEED,
        "company": company,
        "items": frappe.db.count("Item", {"item_code": ["like", "LXD-%"]}),
        "customers": sum(1 for row in native.CUSTOMERS if frappe.db.exists("Customer", row[0])),
        "suppliers": sum(1 for name in native.SUPPLIERS if frappe.db.exists("Supplier", name)),
        "pos_profile": native.POS_PROFILE if frappe.db.exists("POS Profile", native.POS_PROFILE) else None,
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
        "negative_demo_bins": [dict(row) for row in negative],
        "active_pos_opening": active_opening,
        "fbr_transport_disabled": fbr_safe,
    }
    result["ok"] = bool(
        result["items"] >= 20
        and result["customers"] >= 8
        and result["suppliers"] >= 5
        and result["total_sales"] >= 100
        and result["pos_returns"] >= 3
        and result["b2b_returns"] >= 2
        and result["purchase_invoices"] >= 6
        and result["payments"] >= 6
        and result["split_payment_invoices"] >= 2
        and result["trade_outstanding"] > 0
        and result["low_or_out_stock"]
        and not result["negative_demo_bins"]
        and result["active_pos_opening"]
        and fbr_safe
    )
    return result


def seed() -> dict:
    """Create the V2 native demo set; safe to rerun after a successful seed."""
    native._local_only()
    old_user = frappe.session.user or "Administrator"
    frappe.set_user("Administrator")
    base_date = getdate(today())
    try:
        native._disable_fbr_transport()
        context = native._masters()
        native._inventory(
            context["company"], context["main"], context["pos"], context["back"], base_date
        )
        retail = native._retail_sales(context["company"], context["pos"], base_date)
        b2b = native._b2b_sales(context["company"], context["pos"], base_date)

        # ERPNext POS returns are posted inside a real current opening. Historical
        # source invoices remain authoritative; B2B credit notes retain realistic
        # source-relative dates.
        return_opening = native._opening(context["company"], base_date, 99)
        for sequence, source in enumerate(retail[8::23][:4], 1):
            native._pos_return(source, sequence, base_date)
        native._close_opening(return_opening, 99)
        for sequence, source in enumerate(b2b[2::4][:3], 1):
            native._b2b_return(
                source,
                sequence,
                min(add_days(source.posting_date, 5), base_date),
            )

        native._shape_stock(context["company"], context["pos"], base_date)

        # Leave a clean current shift open so the seeded site is immediately
        # usable on the retained Ledgix POS screen.
        native._opening(context["company"], base_date, 100)

        result = verify()
        if not result["ok"]:
            frappe.throw(f"ERPNext demo verification failed: {result}")
        frappe.db.commit()
        return {"created": True, **result}
    except Exception:
        frappe.db.rollback()
        raise
    finally:
        frappe.set_user(old_user)


__all__ = ["SEED", "inspect_site", "cleanup_seed_transactions", "seed", "verify"]
