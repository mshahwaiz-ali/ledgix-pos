from __future__ import annotations

import frappe
from frappe.utils import flt

from ledgix_saas.services import erpnext_selling
from ledgix_saas.services.receivables import get_customer_receivables as get_legacy_receivables

TOLERANCE = 0.01


def run(company: str | None = None) -> dict:
    """Compare mapped legacy customer AR with current ERPNext AR before cutover.

    This is deliberately a report, not an automatic history converter. A real
    site with non-zero mismatches must choose and reconcile its opening-AR or
    transaction-history migration before the receivable UI is switched.
    """

    company = company or erpnext_selling._company(None)
    rows = frappe.get_all(
        "Customer",
        filters={"custom_ledgix_legacy_customer": ["is", "set"]},
        fields=["name", "custom_ledgix_legacy_customer"],
        order_by="name asc",
        limit_page_length=0,
    )

    comparisons = []
    blockers = []
    for row in rows:
        legacy_name = row.custom_ledgix_legacy_customer
        if not legacy_name or not frappe.db.exists("Ledgix Customer", legacy_name):
            continue
        legacy = get_legacy_receivables(legacy_name)
        native = erpnext_selling.get_customer_receivables(row.name, company=company)
        legacy_net = flt(legacy.get("net_balance"), 2)
        native_net = flt(native.get("net_balance"), 2)
        difference = flt(native_net - legacy_net, 2)
        record = {
            "legacy_customer": legacy_name,
            "erpnext_customer": row.name,
            "legacy_net_balance": legacy_net,
            "erpnext_net_balance": native_net,
            "difference": difference,
            "legacy_outstanding": flt(legacy.get("outstanding"), 2),
            "legacy_unallocated_credit": flt(legacy.get("unallocated_credit"), 2),
            "erpnext_outstanding": flt(native.get("outstanding"), 2),
            "erpnext_unallocated_credit": flt(native.get("unallocated_credit"), 2),
            "matches": abs(difference) <= TOLERANCE,
        }
        comparisons.append(record)
        if not record["matches"]:
            blockers.append(record)

    return {
        "company": company,
        "mapped_customer_count": len(comparisons),
        "comparisons": comparisons,
        "blocking_customers": blockers,
        "ready": not blockers,
        "policy": (
            "Non-zero legacy/native AR differences are a cutover blocker. "
            "This preflight does not invent opening invoices or silently discard history."
        ),
    }
