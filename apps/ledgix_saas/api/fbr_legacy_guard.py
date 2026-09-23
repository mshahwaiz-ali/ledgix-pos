from __future__ import annotations

import frappe


LEGACY_FBR_RETIRED_MESSAGE = (
    "Legacy Ledgix Sale / Sales Return FBR execution is retired. "
    "Use the authoritative ERPNext Sales Invoice or POS Invoice FBR workflow."
)


@frappe.whitelist()
def reject_legacy_fbr_action(**kwargs):
    """Fail closed for every retired legacy FBR RPC surface."""

    frappe.throw(LEGACY_FBR_RETIRED_MESSAGE)


@frappe.whitelist()
def reject_legacy_sale_submission(sale_name=None, **kwargs):
    """Backward-compatible alias for the retired legacy Sale submit RPC."""

    return reject_legacy_fbr_action(sale_name=sale_name, **kwargs)
