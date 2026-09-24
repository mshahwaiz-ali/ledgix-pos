from __future__ import annotations

"""Fail-closed compatibility shell for the retired Ledgix Sale FBR preview."""

import frappe

from ledgix_saas.api import fbr_legacy_guard


@frappe.whitelist()
def get_fbr_sale_preview(sale_name=None):
    """Legacy Sale preview is retired; use native Sales/POS Invoice preview."""

    return fbr_legacy_guard.reject_legacy_fbr_action(
        sale_name=sale_name,
    )
