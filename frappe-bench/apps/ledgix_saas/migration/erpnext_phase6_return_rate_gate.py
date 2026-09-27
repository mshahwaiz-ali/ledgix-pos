from __future__ import annotations

import frappe
from frappe.utils import flt

from ledgix_saas.migration import erpnext_phase6_selling_gate as selling_gate
from ledgix_saas.migration.erpnext_integration_bootstrap import (
    INTEGRATION_SITE,
    TEST_COMPANY,
)
from ledgix_saas.services import erpnext_selling

CLIENT_KIND = "return_rate_authority"
TAMPERED_RATE = 1.23
MONEY_TOLERANCE = 0.01


def _client_id() -> str:
    return selling_gate._client(CLIENT_KIND)


def run() -> dict:
    """Prove a client-supplied return rate cannot override ERPNext authority."""

    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 6 return-rate gate on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration Company {TEST_COMPANY!r} is missing.")

    frappe.set_user("Administrator")
    selling_gate._ensure_fixtures()
    legacy_before = selling_gate._legacy_counts()

    source = selling_gate._invoice(f"{CLIENT_KIND}_source")
    source.reload()
    source_row = source.items[0]

    credit = erpnext_selling.create_sales_return(
        sales_invoice=source.name,
        return_items=[
            {
                "sales_invoice_item": source_row.name,
                "return_qty": 1,
                "rate": TAMPERED_RATE,
            }
        ],
        reason="Phase 6 return-rate authority proof",
        client_return_id=_client_id(),
        checkout_source="Phase 6 Return Rate Gate",
    )
    credit.reload()

    credit_row = credit.items[0]
    legacy_after = selling_gate._legacy_counts()

    source_rate = flt(source_row.rate)
    credit_rate = flt(credit_row.rate)
    source_total = abs(flt(source.grand_total))
    credit_total = abs(flt(credit.grand_total))

    checks = {
        "credit_note_submitted": credit.docstatus == 1,
        "linked_to_source": credit.return_against == source.name,
        "source_row_link_preserved": credit_row.sales_invoice_item == source_row.name,
        "tampered_rate_not_used": abs(credit_rate - TAMPERED_RATE) > MONEY_TOLERANCE,
        "source_rate_preserved": abs(credit_rate - source_rate) < MONEY_TOLERANCE,
        "source_total_preserved_for_full_return": abs(credit_total - source_total) < MONEY_TOLERANCE,
        "no_parallel_ledgix_financial_docs": legacy_before == legacy_after,
    }
    complete = all(checks.values())

    result = {
        "site": frappe.local.site,
        "company": TEST_COMPANY,
        "source_invoice": source.name,
        "credit_note": credit.name,
        "source_rate": source_rate,
        "client_supplied_rate": TAMPERED_RATE,
        "credit_note_rate": credit_rate,
        "source_grand_total": source_total,
        "credit_note_grand_total": credit_total,
        "legacy_counts_before": legacy_before,
        "legacy_counts_after": legacy_after,
        "checks": checks,
        "phase6_return_rate_complete": complete,
        "passed": complete,
    }
    frappe.db.commit()
    return result
