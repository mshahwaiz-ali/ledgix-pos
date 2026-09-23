from __future__ import annotations

"""Desk-facing read-only/controlled API for the ERPNext-native Tax & FBR Center.

This is the V2 compliance-center surface. It exposes ERPNext tax-master status,
FBR V2 configuration status, official reference-cache status and invoice
readiness. It never calculates tax and never submits an FBR invoice.
"""

import frappe
from frappe.utils import cint

from ledgix_saas.services.fbr_v2_readiness import evaluate_invoice_readiness


VIEW_ROLES = {"System Manager", "Ledgix Admin", "Ledgix Manager"}
ADMIN_ROLES = {"System Manager", "Ledgix Admin"}

PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
ITEM_MAPPING_DOCTYPE = "Ledgix FBR Item Mapping"
COMPONENT_MAPPING_DOCTYPE = "Ledgix FBR Tax Component Mapping"
REFERENCE_DOCTYPE = "Ledgix FBR Reference Data"
CERTIFICATION_DOCTYPE = "Ledgix FBR Sandbox Certification"


def _roles() -> set[str]:
    return set(frappe.get_roles(frappe.session.user))


def _require_view() -> None:
    if not _roles().intersection(VIEW_ROLES):
        frappe.throw(
            "You do not have permission to access the Tax & FBR Center.",
            frappe.PermissionError,
        )


def _is_admin() -> bool:
    return bool(_roles().intersection(ADMIN_ROLES))


def _count(doctype: str, filters: dict | None = None) -> int:
    if not frappe.db.exists("DocType", doctype):
        return 0
    return cint(frappe.db.count(doctype, filters or {}))


def _missing_count(doctype: str, fieldname: str, extra_filters: dict | None = None) -> int:
    if not frappe.db.exists("DocType", doctype):
        return 0
    filters = dict(extra_filters or {})
    filters[fieldname] = ["in", ["", None]]
    return _count(doctype, filters)


def _profiles() -> list[dict]:
    if not frappe.db.exists("DocType", PROFILE_DOCTYPE):
        return []
    return [
        dict(row)
        for row in frappe.get_all(
            PROFILE_DOCTYPE,
            fields=[
                "name",
                "company",
                "enabled",
                "mode",
                "submit_trigger",
                "provider_type",
                "licensed_integrator_name",
                "onboarding_status",
                "ip_whitelist_status",
                "reference_sync_status",
                "last_reference_sync_at",
                "reference_version",
                "production_post_armed",
                "modified",
            ],
            order_by="company asc",
            limit_page_length=0,
        )
    ]


def _reference_summary() -> list[dict]:
    if not frappe.db.exists("DocType", REFERENCE_DOCTYPE):
        return []

    rows = frappe.get_all(
        REFERENCE_DOCTYPE,
        fields=[
            "reference_type",
            "count(name) as total",
            "sum(case when stale = 1 then 1 else 0 end) as stale_total",
        ],
        group_by="reference_type",
        order_by="reference_type asc",
        limit_page_length=0,
    )
    return [
        {
            "reference_type": row.get("reference_type") or "",
            "total": cint(row.get("total")),
            "stale_total": cint(row.get("stale_total")),
            "current_total": max(cint(row.get("total")) - cint(row.get("stale_total")), 0),
        }
        for row in rows
    ]


def _certification_summary() -> dict:
    if not frappe.db.exists("DocType", CERTIFICATION_DOCTYPE):
        return {
            "total": 0,
            "complete": 0,
            "in_progress": 0,
            "failed": 0,
            "evidence_complete": 0,
        }

    return {
        "total": _count(CERTIFICATION_DOCTYPE),
        "complete": _count(CERTIFICATION_DOCTYPE, {"status": "Complete"}),
        "in_progress": _count(CERTIFICATION_DOCTYPE, {"status": "In Progress"}),
        "failed": _count(CERTIFICATION_DOCTYPE, {"status": "Failed"}),
        "evidence_complete": _count(CERTIFICATION_DOCTYPE, {"evidence_complete": 1}),
    }


def _erpnext_tax_summary() -> dict:
    return {
        "tax_categories": _count("Tax Category"),
        "tax_rules": _count("Tax Rule"),
        "sales_tax_templates": _count("Sales Taxes and Charges Template"),
        "item_tax_templates": _count("Item Tax Template"),
    }


def _v2_mapping_summary() -> dict:
    total = _count(ITEM_MAPPING_DOCTYPE)
    active = _count(ITEM_MAPPING_DOCTYPE, {"active": 1})
    return {
        "total": total,
        "active": active,
        "needs_review": _count(ITEM_MAPPING_DOCTYPE, {"active": 1, "needs_review": 1}),
        "missing_hs_code": _missing_count(
            ITEM_MAPPING_DOCTYPE,
            "hs_code",
            {"active": 1},
        ),
        "missing_fbr_uom": _missing_count(
            ITEM_MAPPING_DOCTYPE,
            "fbr_uom",
            {"active": 1},
        ),
        "missing_sales_type": _missing_count(
            ITEM_MAPPING_DOCTYPE,
            "sales_type",
            {"active": 1},
        ),
        "missing_rate_description": _missing_count(
            ITEM_MAPPING_DOCTYPE,
            "fbr_rate_description",
            {"active": 1},
        ),
        "component_mappings": _count(COMPONENT_MAPPING_DOCTYPE, {"active": 1}),
    }


def _legacy_summary() -> dict:
    """Visibility only; legacy masters are not configuration authorities here."""

    return {
        "tax_profiles": _count("Ledgix Item Tax Profile"),
        "tax_categories": _count("Ledgix Tax Category"),
        "tax_rates": _count("Ledgix Tax Rate"),
        "old_fbr_settings_exists": bool(frappe.db.exists("DocType", "Ledgix FBR Settings")),
    }


@frappe.whitelist()
def get_v2_center_boot() -> dict:
    _require_view()

    profiles = _profiles()
    mapping = _v2_mapping_summary()
    references = _reference_summary()
    certification = _certification_summary()
    erpnext_tax = _erpnext_tax_summary()

    current_reference_rows = sum(row["current_total"] for row in references)
    stale_reference_rows = sum(row["stale_total"] for row in references)

    return {
        "architecture": "ERPNext Native + FBR V2",
        "is_admin": _is_admin(),
        "profiles": profiles,
        "profile_count": len(profiles),
        "erpnext_tax": erpnext_tax,
        "mapping": mapping,
        "references": references,
        "reference_totals": {
            "current": current_reference_rows,
            "stale": stale_reference_rows,
        },
        "certification": certification,
        "legacy": _legacy_summary(),
        "production_safety": {
            "armed_profiles": sum(bool(cint(row.get("production_post_armed"))) for row in profiles),
            "production_profiles": sum(row.get("mode") == "Production" for row in profiles),
            "note": "This Desk center has no Production invoice submit action.",
        },
        "runtime_cutover": {
            "final_payload_builder_active": False,
            "old_monetary_tax_engine_authoritative": False,
            "local_runtime_parity_required": True,
        },
    }


@frappe.whitelist()
def get_v2_item_mappings(page=1, page_size=20, search=None, needs_review=None) -> dict:
    _require_view()

    page = max(cint(page), 1)
    page_size = min(max(cint(page_size), 1), 100)
    start = (page - 1) * page_size

    filters: dict = {}
    if needs_review not in (None, "", "All"):
        filters["needs_review"] = 1 if cint(needs_review) else 0

    or_filters = None
    if search:
        term = f"%{str(search).strip()}%"
        or_filters = {
            "erpnext_item": ["like", term],
            "hs_code": ["like", term],
            "sales_type": ["like", term],
            "fbr_rate_description": ["like", term],
        }

    rows = frappe.get_all(
        ITEM_MAPPING_DOCTYPE,
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "company",
            "erpnext_item",
            "active",
            "needs_review",
            "hs_code",
            "fbr_uom",
            "sales_type",
            "fbr_rate_description",
            "tax_basis",
            "sro_schedule_number",
            "sro_item_serial_number",
            "reference_version",
            "modified",
        ],
        order_by="needs_review desc, modified desc",
        limit_start=start,
        limit_page_length=page_size,
    )
    total = frappe.db.count(ITEM_MAPPING_DOCTYPE, filters=filters)

    return {
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@frappe.whitelist()
def evaluate_v2_invoice_readiness(reference_doctype: str, reference_name: str) -> dict:
    _require_view()
    return evaluate_invoice_readiness(reference_doctype, reference_name)


@frappe.whitelist()
def get_fbr_readiness() -> dict:
    """Compatibility replacement for the old tax-center readiness RPC.

    Old callers receive V2 architecture status rather than legacy tax-engine
    readiness. This method performs no FBR network request.
    """

    boot = get_v2_center_boot()
    mapping = boot["mapping"]
    reference_totals = boot["reference_totals"]
    blocking = []

    if not boot["profile_count"]:
        blocking.append("No V2 FBR Integration Profile")
    if mapping["needs_review"]:
        blocking.append(f"{mapping['needs_review']} FBR item mapping(s) need review")
    if mapping["missing_hs_code"]:
        blocking.append(f"{mapping['missing_hs_code']} mapping(s) missing HS Code")
    if mapping["missing_fbr_uom"]:
        blocking.append(f"{mapping['missing_fbr_uom']} mapping(s) missing FBR UOM")
    if mapping["missing_sales_type"]:
        blocking.append(f"{mapping['missing_sales_type']} mapping(s) missing Sale Type")
    if mapping["missing_rate_description"]:
        blocking.append(
            f"{mapping['missing_rate_description']} mapping(s) missing FBR Rate Description"
        )
    if not reference_totals["current"]:
        blocking.append("Official FBR reference cache is empty")

    return {
        "architecture": boot["architecture"],
        "ready": not blocking,
        "blocking_gaps": blocking,
        "mapping": mapping,
        "references": boot["references"],
        "profiles": boot["profiles"],
        "certification": boot["certification"],
        "production_safety": boot["production_safety"],
        "final_payload_builder_active": False,
        "fbr_network_call": False,
        "contains_secrets": False,
    }
