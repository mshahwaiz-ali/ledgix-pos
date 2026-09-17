from __future__ import annotations

"""ERPNext v15 compatibility adapter for local retail operating data.

ERPNext v15 stores POS Invoice payment rows in the standard
`Sales Invoice Payment` child DocType. Older Ledgix demo tooling referenced a
non-existent `POS Invoice Payment` table in two local-only paths: payment
reference cleanup and split-payment verification. This adapter corrects those
local paths without modifying ERPNext core or production behavior.
"""

import frappe

from ledgix_saas.setup import demo_data
from ledgix_saas.setup import erpnext_demo_data as native
from ledgix_saas.setup import retail_operating_profile as retail
from ledgix_saas.setup import retail_seed_safe

_ORIGINAL_VERIFY = demo_data.verify
_ORIGINAL_POS_INVOICE = retail._ORIGINAL_POS_INVOICE


def _pos_invoice_v15(*args, **kwargs):
    invoice = _ORIGINAL_POS_INVOICE(*args, **kwargs)
    for row in invoice.get("payments") or []:
        reference_no = str(row.reference_no or "")
        if reference_no.startswith("DEMO-"):
            frappe.db.set_value(
                "Sales Invoice Payment",
                row.name,
                "reference_no",
                reference_no.replace("DEMO-", "POS-", 1),
                update_modified=False,
            )
    return invoice


def _verify_v15() -> dict:
    """Run the existing verifier against ERPNext v15's payment child table."""
    original_sql = frappe.db.sql

    def sql_compat(query, *args, **kwargs):
        if isinstance(query, str) and "`tabPOS Invoice Payment`" in query:
            query = query.replace(
                "`tabPOS Invoice Payment`", "`tabSales Invoice Payment`"
            )
        return original_sql(query, *args, **kwargs)

    frappe.db.sql = sql_compat
    try:
        return _ORIGINAL_VERIFY()
    finally:
        frappe.db.sql = original_sql


def verify() -> dict:
    native._local_only()
    return _verify_v15()


def seed() -> dict:
    """Run retail seed with historical-stock and ERPNext-v15 payment guards."""
    native._local_only()

    previous_stock_entry = native._stock_entry
    previous_native_pos_invoice = native._pos_invoice
    previous_retail_pos_invoice = retail._pos_invoice
    previous_verify = demo_data.verify

    # demo_data.seed() invokes retail.configure() internally. Patch the retail
    # function itself so that configure() installs the v15-safe implementation.
    retail._pos_invoice = _pos_invoice_v15
    native._pos_invoice = _pos_invoice_v15
    native._stock_entry = retail_seed_safe._historical_safe_stock_entry
    demo_data.verify = _verify_v15

    try:
        return demo_data.seed()
    finally:
        demo_data.verify = previous_verify
        native._stock_entry = previous_stock_entry
        native._pos_invoice = previous_native_pos_invoice
        retail._pos_invoice = previous_retail_pos_invoice


__all__ = ["seed", "verify"]
