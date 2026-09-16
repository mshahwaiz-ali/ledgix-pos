from __future__ import annotations

import frappe
from frappe.utils import flt

from ledgix_saas.services import erpnext_buying_inventory

TOLERANCE = 0.01


def _erpnext_supplier_payable(supplier: str, company: str) -> float:
    rows = frappe.get_all(
        "GL Entry",
        filters={
            "company": company,
            "party_type": "Supplier",
            "party": supplier,
            "is_cancelled": 0,
        },
        fields=["debit", "credit"],
        limit_page_length=0,
    )
    return flt(sum(flt(row.credit) - flt(row.debit) for row in rows), 2)


def run(company: str | None = None) -> dict:
    """Compare mapped Ledgix Supplier current AP with ERPNext GL authority.

    `opening_balance` is retained as migration provenance. `current_balance` is
    the cutover comparison because Phase 7 must reconcile today's payable state,
    not manufacture a new liability from an old opening seed.
    """

    company = erpnext_buying_inventory._company(company)
    rows = frappe.get_all(
        "Supplier",
        filters={"custom_ledgix_legacy_supplier": ["is", "set"]},
        fields=["name", "custom_ledgix_legacy_supplier"],
        order_by="name asc",
        limit_page_length=0,
    )

    comparisons = []
    blockers = []
    for row in rows:
        legacy_name = row.custom_ledgix_legacy_supplier
        if not legacy_name or not frappe.db.exists("Ledgix Supplier", legacy_name):
            continue
        values = frappe.db.get_value(
            "Ledgix Supplier",
            legacy_name,
            ["opening_balance", "current_balance"],
            as_dict=True,
        ) or {}
        legacy_current = flt(values.get("current_balance"), 2)
        native_current = _erpnext_supplier_payable(row.name, company)
        difference = flt(native_current - legacy_current, 2)
        record = {
            "legacy_supplier": legacy_name,
            "erpnext_supplier": row.name,
            "legacy_opening_balance_provenance": flt(values.get("opening_balance"), 2),
            "legacy_current_payable": legacy_current,
            "erpnext_current_payable": native_current,
            "difference": difference,
            "matches": abs(difference) <= TOLERANCE,
        }
        comparisons.append(record)
        if not record["matches"]:
            blockers.append(record)

    return {
        "company": company,
        "mapped_supplier_count": len(comparisons),
        "comparisons": comparisons,
        "blocking_suppliers": blockers,
        "ready": not blockers,
        "policy": (
            "Non-zero legacy/native supplier payable differences block Phase 7 cutover. "
            "Opening-balance provenance is reported but never silently reposted as a new liability."
        ),
    }
