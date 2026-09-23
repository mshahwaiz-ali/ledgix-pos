from __future__ import annotations

"""Controlled local migration preview/apply for the FBR V2 redesign.

This helper is deliberately restricted to ledgix-erpnext.local. It migrates
only FBR compliance/classification data. It never migrates legacy monetary tax
authority and never enables or arms FBR submission.
"""

from collections import defaultdict

import frappe
from frappe.utils import cint, flt
from frappe.utils.password import get_decrypted_password

from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


LEGACY_SETTINGS = "Ledgix FBR Settings"
LEGACY_ITEM_PROFILE = "Ledgix Item Tax Profile"
V2_PROFILE = "Ledgix FBR Integration Profile"
V2_ITEM_MAPPING = "Ledgix FBR Item Mapping"

APPLY_CONFIRMATION = "APPLY FBR V2 LOCAL MIGRATION"

MIGRATED_ITEM_FIELDS = (
    "hs_code",
    "sales_type",
    "fbr_rate_description",
    "tax_basis",
    "notified_retail_price",
    "sro_schedule_number",
    "sro_item_serial_number",
)

IGNORED_MONETARY_FIELDS = (
    "default_tax_rate",
    "sales_tax_withheld_at_source_per_unit",
    "extra_tax_per_unit",
    "further_tax_per_unit",
    "fed_payable_per_unit",
)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing FBR V2 migration on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )


def _assert_doctypes() -> None:
    missing = [
        doctype
        for doctype in (
            LEGACY_SETTINGS,
            LEGACY_ITEM_PROFILE,
            V2_PROFILE,
            V2_ITEM_MAPPING,
        )
        if not frappe.db.exists("DocType", doctype)
    ]
    if missing:
        frappe.throw(
            "Run bench migrate before the FBR V2 migration preview. Missing DocTypes: "
            + ", ".join(missing)
        )


def _company(company: str) -> str:
    company = str(company or "").strip()
    if not company or not frappe.db.exists("Company", company):
        frappe.throw("Select a valid ERPNext Company for the FBR V2 migration.")
    return company


def _password_configured(doctype: str, name: str, fieldname: str) -> bool:
    try:
        return bool(
            get_decrypted_password(
                doctype,
                name,
                fieldname,
                raise_exception=False,
            )
        )
    except Exception:
        return False


def _legacy_settings_summary() -> dict:
    doc = frappe.get_single(LEGACY_SETTINGS)
    return {
        "enabled": bool(cint(doc.get("enabled"))),
        "mode": doc.get("mode") or "Disabled",
        "submit_trigger": doc.get("submit_trigger") or "Manual",
        "production_post_armed": bool(cint(doc.get("production_post_armed"))),
        "block_sale_if_fbr_fails": bool(cint(doc.get("block_sale_if_fbr_fails"))),
        "software_registration_number": doc.get("software_registration_number") or "",
        "sandbox_token_configured": _password_configured(
            LEGACY_SETTINGS,
            LEGACY_SETTINGS,
            "sandbox_token",
        ),
        "production_token_configured": _password_configured(
            LEGACY_SETTINGS,
            LEGACY_SETTINGS,
            "production_token",
        ),
        "duplicated_seller_identity_present": bool(
            str(doc.get("seller_ntn_cnic") or "").strip()
            or str(doc.get("seller_business_name") or "").strip()
            or str(doc.get("seller_province") or "").strip()
            or str(doc.get("seller_address") or "").strip()
        ),
    }


def _profile_preview(company: str) -> dict:
    existing_name = frappe.db.get_value(V2_PROFILE, {"company": company}, "name")
    legacy = _legacy_settings_summary()
    return {
        "company": company,
        "existing_v2_profile": existing_name or "",
        "action": "update_safe_fields" if existing_name else "create_disabled_profile",
        "proposed": {
            "enabled": False,
            "mode": "Disabled",
            "submit_trigger": "Manual",
            "production_post_armed": False,
            "block_sale_if_fbr_fails": legacy["block_sale_if_fbr_fails"],
            "software_registration_number": legacy["software_registration_number"],
            "onboarding_status": "Not Started",
            "reference_sync_status": "Never Synced",
            "sandbox_token_will_copy": legacy["sandbox_token_configured"],
            "production_token_will_copy": legacy["production_token_configured"],
        },
        "not_migrated": {
            "legacy_enabled_state": legacy["enabled"],
            "legacy_mode": legacy["mode"],
            "legacy_submit_trigger": legacy["submit_trigger"],
            "legacy_production_post_armed": legacy["production_post_armed"],
            "duplicated_seller_identity": legacy["duplicated_seller_identity_present"],
        },
        "reason": (
            "V2 migration is fail-closed: the destination profile remains Disabled, "
            "Manual and Production-unarmed regardless of legacy state."
        ),
    }


def _legacy_item_rows() -> list[dict]:
    fields = [
        "name",
        "erpnext_item",
        "item",
        "active",
        "needs_review",
        "hs_code",
        "uom_for_fbr",
        "sales_type",
        "fbr_rate_description",
        "tax_basis",
        "notified_retail_price",
        "scenario_id",
        "sro_schedule_number",
        "sro_item_serial_number",
        *IGNORED_MONETARY_FIELDS,
    ]
    return [
        dict(row)
        for row in frappe.get_all(
            LEGACY_ITEM_PROFILE,
            fields=fields,
            order_by="name asc",
            limit_page_length=0,
        )
    ]


def _item_candidate(company: str, row: dict) -> dict:
    item_code = str(row.get("erpnext_item") or "").strip()
    blocker = ""
    if not item_code:
        blocker = "missing_erpnext_item"
    elif not frappe.db.exists("Item", item_code):
        blocker = "erpnext_item_not_found"

    existing = (
        frappe.db.get_value(
            V2_ITEM_MAPPING,
            {
                "company": company,
                "erpnext_item": item_code,
                "active": 1,
            },
            "name",
        )
        if item_code
        else None
    )

    monetary_values = {
        fieldname: flt(row.get(fieldname))
        for fieldname in IGNORED_MONETARY_FIELDS
        if abs(flt(row.get(fieldname))) > 0.000001
    }

    values = {
        "company": company,
        "erpnext_item": item_code,
        "active": bool(cint(row.get("active"))),
        "needs_review": True,
        "hs_code": row.get("hs_code") or "",
        "fbr_uom": row.get("uom_for_fbr") or "",
        "sales_type": row.get("sales_type") or "",
        "fbr_rate_description": row.get("fbr_rate_description") or "",
        "tax_basis": row.get("tax_basis") or "Transaction Value",
        "notified_retail_price": flt(row.get("notified_retail_price")),
        "sro_schedule_number": row.get("sro_schedule_number") or "",
        "sro_item_serial_number": row.get("sro_item_serial_number") or "",
    }

    return {
        "legacy_name": row["name"],
        "legacy_item": row.get("item") or "",
        "erpnext_item": item_code,
        "existing_v2_mapping": existing or "",
        "action": (
            "blocked"
            if blocker
            else ("review_existing" if existing else "create_review_required")
        ),
        "blocker": blocker,
        "proposed": values,
        "ignored": {
            "scenario_id": row.get("scenario_id") or "",
            "monetary_fields": monetary_values,
        },
    }


def preview_v2_migration(company: str) -> dict:
    """Read-only preview. Contains no password values and performs no writes."""

    _assert_safe_site()
    _assert_doctypes()
    company = _company(company)

    legacy_rows = _legacy_item_rows()
    candidates = [_item_candidate(company, row) for row in legacy_rows]

    grouped = defaultdict(list)
    for candidate in candidates:
        if candidate["erpnext_item"]:
            grouped[candidate["erpnext_item"]].append(candidate["legacy_name"])

    duplicate_sources = {
        item_code: names
        for item_code, names in grouped.items()
        if len(names) > 1
    }
    for candidate in candidates:
        names = duplicate_sources.get(candidate["erpnext_item"])
        if names and not candidate["blocker"]:
            candidate["action"] = "blocked"
            candidate["blocker"] = "multiple_legacy_profiles_for_erpnext_item"

    blockers = [
        {
            "legacy_name": row["legacy_name"],
            "erpnext_item": row["erpnext_item"],
            "reason": row["blocker"],
        }
        for row in candidates
        if row["blocker"]
    ]

    ignored_monetary = [
        {
            "legacy_name": row["legacy_name"],
            "erpnext_item": row["erpnext_item"],
            "fields": row["ignored"]["monetary_fields"],
        }
        for row in candidates
        if row["ignored"]["monetary_fields"]
    ]
    ignored_scenarios = [
        {
            "legacy_name": row["legacy_name"],
            "erpnext_item": row["erpnext_item"],
            "scenario_id": row["ignored"]["scenario_id"],
        }
        for row in candidates
        if row["ignored"]["scenario_id"]
    ]

    return {
        "site": frappe.local.site,
        "company": company,
        "read_only": True,
        "contains_secrets": False,
        "production_post_armed_changed": False,
        "profile": _profile_preview(company),
        "item_candidates": candidates,
        "summary": {
            "legacy_item_profiles": len(legacy_rows),
            "create_candidates": sum(
                row["action"] == "create_review_required" for row in candidates
            ),
            "existing_review_candidates": sum(
                row["action"] == "review_existing" for row in candidates
            ),
            "blocked_candidates": len(blockers),
            "ignored_monetary_profiles": len(ignored_monetary),
            "ignored_sandbox_scenarios": len(ignored_scenarios),
        },
        "blockers": blockers,
        "ignored_monetary_fields": ignored_monetary,
        "ignored_sandbox_scenarios": ignored_scenarios,
    }


def _copy_password_if_present(source_field: str, target_doc, target_field: str) -> bool:
    value = get_decrypted_password(
        LEGACY_SETTINGS,
        LEGACY_SETTINGS,
        source_field,
        raise_exception=False,
    )
    if not value:
        return False
    if hasattr(target_doc, "set_password"):
        target_doc.set_password(target_field, value)
    else:
        target_doc.set(target_field, value)
    return True


def _apply_profile(company: str) -> tuple[str, dict]:
    preview = _profile_preview(company)
    name = preview["existing_v2_profile"]
    if name:
        doc = frappe.get_doc(V2_PROFILE, name)
    else:
        doc = frappe.new_doc(V2_PROFILE)
        doc.company = company

    proposed = preview["proposed"]
    doc.enabled = 0
    doc.mode = "Disabled"
    doc.submit_trigger = "Manual"
    doc.production_post_armed = 0
    doc.block_sale_if_fbr_fails = 1 if proposed["block_sale_if_fbr_fails"] else 0
    doc.software_registration_number = proposed["software_registration_number"]
    doc.onboarding_status = "Not Started"

    sandbox_copied = _copy_password_if_present(
        "sandbox_token",
        doc,
        "sandbox_token",
    )
    production_copied = _copy_password_if_present(
        "production_token",
        doc,
        "production_token",
    )

    if doc.is_new():
        doc.insert(ignore_permissions=True)
    else:
        doc.save(ignore_permissions=True)

    return doc.name, {
        "sandbox_token_copied": sandbox_copied,
        "production_token_copied": production_copied,
        "enabled": False,
        "mode": "Disabled",
        "submit_trigger": "Manual",
        "production_post_armed": False,
    }


def _create_item_mapping(candidate: dict) -> str:
    values = candidate["proposed"]
    doc = frappe.get_doc(
        {
            "doctype": V2_ITEM_MAPPING,
            **values,
            "source_notes": (
                f"Migrated from {LEGACY_ITEM_PROFILE} {candidate['legacy_name']}. "
                "Monetary tax fields and Sandbox scenario were intentionally not migrated. "
                "Review against official FBR reference data before use."
            ),
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def apply_v2_migration(company: str, confirmation: str) -> dict:
    """Apply only safe V2 metadata migration on the local integration site."""

    _assert_safe_site()
    _assert_doctypes()
    company = _company(company)
    if str(confirmation or "") != APPLY_CONFIRMATION:
        frappe.throw(
            f"Explicit confirmation required: {APPLY_CONFIRMATION}"
        )

    preview = preview_v2_migration(company)
    if preview["blockers"]:
        frappe.throw(
            "FBR V2 migration has blockers. Resolve the preview blockers before apply."
        )

    savepoint = "fbr_v2_local_migration"
    frappe.db.savepoint(savepoint)
    try:
        profile_name, profile_result = _apply_profile(company)
        created = []
        skipped_existing = []
        for candidate in preview["item_candidates"]:
            if candidate["existing_v2_mapping"]:
                skipped_existing.append(candidate["existing_v2_mapping"])
                continue
            created.append(_create_item_mapping(candidate))
    except Exception:
        frappe.db.rollback(save_point=savepoint)
        raise

    return {
        "site": frappe.local.site,
        "company": company,
        "profile": profile_name,
        "profile_result": profile_result,
        "created_item_mappings": created,
        "skipped_existing_item_mappings": skipped_existing,
        "ignored_monetary_profiles": preview["summary"]["ignored_monetary_profiles"],
        "ignored_sandbox_scenarios": preview["summary"]["ignored_sandbox_scenarios"],
        "production_post_armed": False,
        "fbr_submission_enabled": False,
        "contains_secrets": False,
    }
