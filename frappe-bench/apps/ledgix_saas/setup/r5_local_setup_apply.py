from __future__ import annotations

"""Guarded local/integration adapter for closing the R5 setup marker.

This helper exists only for the repository R5 runtime gate. It reuses the
Phase-13 client setup service after independently proving that the supplied
profile/configuration is already ready. It never creates missing business
masters and it refuses non-local sites.
"""

import frappe

from ledgix_saas.api import client_setup


def _is_local_site(site: str) -> bool:
    return site.endswith(".local") or site.endswith(".localhost")


def apply_existing_ready_setup(payload=None) -> dict:
    site = str(frappe.local.site or "")
    if not _is_local_site(site):
        frappe.throw(f"R5 local setup apply refuses non-local site: {site}")

    original_user = frappe.session.user
    try:
        frappe.set_user("Administrator")
        parsed = client_setup._parse(payload)
        evaluation = client_setup.evaluate_client_setup(parsed)
        if not evaluation.get("ready"):
            blockers = [row.get("key") for row in evaluation.get("blockers") or []]
            frappe.throw(
                "R5 local setup apply requires an already-ready Phase 13 configuration; "
                f"blocking checks: {', '.join(blockers) or 'unknown'}"
            )

        result = client_setup.apply_client_setup(parsed)
        frappe.db.commit()
        return {
            "site": site,
            "applied": bool(result.get("applied")),
            "business_profile": (result.get("state") or {}).get("business_profile"),
            "setup_complete": bool((result.get("state") or {}).get("setup_complete")),
            "authority": "existing Phase 13 configuration only; ERPNext business authority unchanged",
            "business_masters_created": False,
            "fbr_production_activated": False,
        }
    finally:
        frappe.set_user(original_user or "Guest")
