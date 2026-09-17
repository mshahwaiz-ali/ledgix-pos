from __future__ import annotations

"""ERPNext-v15 runtime adapter for the local retail operating dataset.

ERPNext v15 stores POS Invoice payment rows in the standard
`Sales Invoice Payment` child DocType. The local retail runtime also needs the
stock chronology guard from :mod:`retail_seed_safe`. This module is the single
supported execution adapter used by the preparation script so schema and stock
assumptions are checked before the long seed begins.
"""

import frappe

from ledgix_saas.setup import demo_data
from ledgix_saas.setup import erpnext_demo_data as native
from ledgix_saas.setup import retail_operating_profile as retail
from ledgix_saas.setup import retail_seed_safe

PAYMENT_CHILD_DOCTYPE = "Sales Invoice Payment"
_ORIGINAL_VERIFY = demo_data.verify
_ORIGINAL_POS_INVOICE = retail._ORIGINAL_POS_INVOICE


def _assert_v15_contract() -> None:
    native._local_only()
    if not frappe.db.exists("DocType", PAYMENT_CHILD_DOCTYPE):
        frappe.throw(
            f"ERPNext v15 payment child DocType is missing: {PAYMENT_CHILD_DOCTYPE}."
        )

    payment_field = frappe.get_meta("POS Invoice").get_field("payments")
    if not payment_field or payment_field.options != PAYMENT_CHILD_DOCTYPE:
        frappe.throw(
            "POS Invoice.payments schema does not match the pinned ERPNext v15 contract: "
            f"expected {PAYMENT_CHILD_DOCTYPE}, got "
            f"{getattr(payment_field, 'options', None)}."
        )

    child_meta = frappe.get_meta(PAYMENT_CHILD_DOCTYPE)
    for fieldname in ("mode_of_payment", "amount", "reference_no", "account"):
        if not child_meta.has_field(fieldname):
            frappe.throw(
                f"{PAYMENT_CHILD_DOCTYPE}.{fieldname} is required by the local retail loader."
            )


def _pos_invoice_v15(*args, **kwargs):
    invoice = _ORIGINAL_POS_INVOICE(*args, **kwargs)
    for row in invoice.get("payments") or []:
        reference_no = str(row.reference_no or "")
        if reference_no.startswith("DEMO-"):
            frappe.db.set_value(
                PAYMENT_CHILD_DOCTYPE,
                row.name,
                "reference_no",
                reference_no.replace("DEMO-", "POS-", 1),
                update_modified=False,
            )
    return invoice


def _verify_v15() -> dict:
    """Run the existing verifier against ERPNext v15's standard payment table."""
    _assert_v15_contract()
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
    """Run the complete retail seed with v15 schema and stock chronology guards."""
    _assert_v15_contract()

    previous_retail_pos_invoice = retail._pos_invoice
    previous_verify = demo_data.verify

    # retail_seed_safe.seed() calls retail.configure() internally. Replacing the
    # profile function here ensures that configure() installs the v15-safe POS
    # implementation while the stock-safe inventory/shape overrides are active.
    retail._pos_invoice = _pos_invoice_v15
    demo_data.verify = _verify_v15
    try:
        return retail_seed_safe.seed()
    finally:
        demo_data.verify = previous_verify
        retail._pos_invoice = previous_retail_pos_invoice


__all__ = ["seed", "verify", "PAYMENT_CHILD_DOCTYPE"]
