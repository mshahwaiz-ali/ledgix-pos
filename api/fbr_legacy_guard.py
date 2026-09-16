from __future__ import annotations

import frappe


@frappe.whitelist()
def reject_legacy_sale_submission(sale_name=None, **kwargs):
    """Fail closed after Phase 9 source cutover.

    Historical Ledgix Sale records remain readable for audit, but no new FBR
    validate/post workflow may issue an official invoice from the retired sales
    ledger. Use the native ERPNext Sales Invoice / POS Invoice source instead.
    """

    frappe.throw(
        "Legacy Ledgix Sale FBR submission is retired. Select the authoritative "
        "ERPNext Sales Invoice or POS Invoice in Tax & FBR Center."
    )
