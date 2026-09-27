from __future__ import annotations

"""ERPNext-v15 runtime adapter for the local retail operating dataset.

ERPNext v15 stores POS Invoice payment rows in the standard
`Sales Invoice Payment` child DocType. The local retail runtime also needs the
stock chronology guard from :mod:`retail_seed_safe`. This module is the single
supported execution adapter used by the preparation script so schema, stock,
and historical receivable-date assumptions are checked in one place.
"""

from datetime import time

import frappe
from frappe.utils import add_days, getdate

from ledgix_saas.services import erpnext_selling
from ledgix_saas.setup import demo_data
from ledgix_saas.setup import erpnext_demo_data as native
from ledgix_saas.setup import retail_operating_profile as retail
from ledgix_saas.setup import retail_seed_safe

PAYMENT_CHILD_DOCTYPE = "Sales Invoice Payment"
_ORIGINAL_VERIFY = demo_data.verify
_ORIGINAL_POS_INVOICE = retail._ORIGINAL_POS_INVOICE
_ORIGINAL_BUILD_SALES_INVOICE = erpnext_selling.build_sales_invoice


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


def _build_sales_invoice_v15(*args, **kwargs):
    """Keep managed historical B2B invoices on an explicit Net-21 schedule.

    ERPNext can populate a payment schedule while set_missing_values() runs.
    For our deliberately backdated operating history, that generated schedule
    must not be allowed to override the explicit historical due date during
    Sales Invoice validation. Rebuild the schedule from the requested posting
    and due dates, and opt into editable historical posting date/time.
    """
    invoice = _ORIGINAL_BUILD_SALES_INVOICE(*args, **kwargs)
    client_sale_id = str(kwargs.get("client_sale_id") or "")
    is_managed_b2b = bool(
        kwargs.get("sale_channel") == "B2B"
        and client_sale_id.startswith(f"{retail.SEED}-B2B-")
    )
    if not is_managed_b2b:
        return invoice

    posting_date = getdate(kwargs.get("posting_date") or invoice.posting_date)
    requested_due_date = getdate(
        kwargs.get("due_date") or invoice.due_date or add_days(posting_date, 21)
    )
    if requested_due_date < posting_date:
        frappe.throw(
            f"Managed B2B invoice {client_sale_id} has invalid dates: "
            f"posting {posting_date}, due {requested_due_date}."
        )

    invoice.posting_date = posting_date
    invoice.posting_time = time(12, 0)
    invoice.set_posting_time = 1
    invoice.payment_terms_template = ""
    invoice.ignore_default_payment_terms_template = 0
    invoice.set("payment_schedule", [])
    invoice.due_date = requested_due_date
    return invoice


def _due_date_violations() -> tuple[list[dict], list[dict]]:
    invoice_rows = frappe.db.sql(
        """
        select name, posting_date, due_date
        from `tabSales Invoice`
        where docstatus = 1
          and is_return = 0
          and custom_ledgix_client_sale_id like %s
          and due_date < posting_date
        order by posting_date asc, name asc
        """,
        (f"{retail.SEED}-B2B-%",),
        as_dict=True,
    )
    schedule_rows = frappe.db.sql(
        """
        select si.name, si.posting_date, ps.due_date
        from `tabSales Invoice` si
        inner join `tabPayment Schedule` ps
          on ps.parent = si.name and ps.parenttype = 'Sales Invoice'
        where si.docstatus = 1
          and si.is_return = 0
          and si.custom_ledgix_client_sale_id like %s
          and ps.due_date < si.posting_date
        order by si.posting_date asc, si.name asc, ps.idx asc
        """,
        (f"{retail.SEED}-B2B-%",),
        as_dict=True,
    )
    return [dict(row) for row in invoice_rows], [dict(row) for row in schedule_rows]


def _verify_v15() -> dict:
    """Run the existing verifier plus v15 schema/date integrity assertions."""
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
        result = _ORIGINAL_VERIFY()
    finally:
        frappe.db.sql = original_sql

    invalid_invoices, invalid_schedules = _due_date_violations()
    result["invalid_b2b_due_dates"] = invalid_invoices
    result["invalid_b2b_payment_schedule_dates"] = invalid_schedules
    result["ok"] = bool(
        result.get("ok") and not invalid_invoices and not invalid_schedules
    )
    return result


def verify() -> dict:
    native._local_only()
    return _verify_v15()


def seed() -> dict:
    """Run the complete retail seed with all local ERPNext-v15 guards enabled."""
    _assert_v15_contract()

    previous_retail_pos_invoice = retail._pos_invoice
    previous_verify = demo_data.verify
    previous_build_sales_invoice = erpnext_selling.build_sales_invoice

    # retail_seed_safe.seed() calls retail.configure() internally. Replacing the
    # profile function here ensures that configure() installs the v15-safe POS
    # implementation while the stock-safe inventory/shape overrides are active.
    # The selling builder wrapper is scoped to this process and only changes
    # managed B2B rows for this local operating dataset.
    retail._pos_invoice = _pos_invoice_v15
    demo_data.verify = _verify_v15
    erpnext_selling.build_sales_invoice = _build_sales_invoice_v15
    try:
        return retail_seed_safe.seed()
    finally:
        erpnext_selling.build_sales_invoice = previous_build_sales_invoice
        demo_data.verify = previous_verify
        retail._pos_invoice = previous_retail_pos_invoice


__all__ = ["seed", "verify", "PAYMENT_CHILD_DOCTYPE"]
