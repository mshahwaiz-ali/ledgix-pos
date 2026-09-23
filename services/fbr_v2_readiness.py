from __future__ import annotations

"""Read-only V2 compliance readiness aggregation.

This module does not construct or submit an FBR invoice. It combines the
ERPNext-authoritative identity resolver, native tax collector, V2 mappings and
cached official FBR reference evidence into one fail-closed readiness report.
"""

import frappe
from frappe.utils import cint, flt, getdate
from frappe.utils.password import get_decrypted_password

from ledgix_saas.api import fbr_reference_v2
from ledgix_saas.services import (
    erpnext_fbr_identity,
    erpnext_fbr_snapshot,
)


SUPPORTED_DOCTYPES = {"Sales Invoice", "POS Invoice"}
PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
CERTIFICATION_DOCTYPE = "Ledgix FBR Sandbox Certification"
REFERENCE_DOCTYPE = "Ledgix FBR Reference Data"
MONEY_TOLERANCE = 0.011


def _text(value) -> str:
    return str(value or "").strip()


def _profile(company: str):
    name = frappe.db.get_value(PROFILE_DOCTYPE, {"company": company}, "name")
    return frappe.get_doc(PROFILE_DOCTYPE, name) if name else None


def _token_configured(profile, fieldname: str) -> bool:
    if not profile:
        return False
    try:
        return bool(
            get_decrypted_password(
                PROFILE_DOCTYPE,
                profile.name,
                fieldname,
                raise_exception=False,
            )
        )
    except Exception:
        return False


def _cached_reference_rows(reference_type: str, context_key: str) -> list[dict]:
    return [
        dict(row)
        for row in frappe.get_all(
            REFERENCE_DOCTYPE,
            filters={
                "reference_type": reference_type,
                "context_key": context_key,
                "active": 1,
                "stale": 0,
            },
            fields=["name", "fbr_id", "description", "context_key", "fetched_at"],
            limit_page_length=0,
        )
    ]


def _reference_match(
    reference_type: str,
    value: str,
    *,
    context_key: str = fbr_reference_v2.GLOBAL_CONTEXT_KEY,
) -> dict | None:
    value = _text(value)
    if not value:
        return None
    folded = value.casefold()
    for row in _cached_reference_rows(reference_type, context_key):
        if _text(row.get("fbr_id")).casefold() == folded:
            return row
        if _text(row.get("description")).casefold() == folded:
            return row
    return None


def _context_key(context: dict) -> str:
    return fbr_reference_v2._canonical_context(context)[0]


def _profile_state(profile) -> dict:
    if not profile:
        return {
            "exists": False,
            "name": "",
            "enabled": False,
            "mode": "Disabled",
            "submit_trigger": "Manual",
            "onboarding_status": "",
            "reference_sync_status": "",
            "sandbox_token_configured": False,
            "production_token_configured": False,
            "production_post_armed": False,
        }

    return {
        "exists": True,
        "name": profile.name,
        "enabled": bool(cint(profile.get("enabled"))),
        "mode": profile.get("mode") or "Disabled",
        "submit_trigger": profile.get("submit_trigger") or "Manual",
        "onboarding_status": profile.get("onboarding_status") or "",
        "reference_sync_status": profile.get("reference_sync_status") or "",
        "sandbox_token_configured": _token_configured(profile, "sandbox_token"),
        "production_token_configured": _token_configured(profile, "production_token"),
        "production_post_armed": bool(cint(profile.get("production_post_armed"))),
    }


def _sandbox_certification(profile) -> dict:
    if not profile:
        return {
            "name": "",
            "status": "",
            "evidence_complete": False,
            "complete": False,
        }

    rows = frappe.get_all(
        CERTIFICATION_DOCTYPE,
        filters={"integration_profile": profile.name},
        fields=["name", "status", "evidence_complete", "modified"],
        order_by="modified desc",
        limit_page_length=1,
    )
    if not rows:
        return {
            "name": "",
            "status": "",
            "evidence_complete": False,
            "complete": False,
        }

    row = rows[0]
    complete = row.get("status") == "Complete" and bool(cint(row.get("evidence_complete")))
    return {
        "name": row.get("name") or "",
        "status": row.get("status") or "",
        "evidence_complete": bool(cint(row.get("evidence_complete"))),
        "complete": complete,
    }


def _check_identity_references(identity: dict, errors: list[str]) -> dict:
    seller_province = _reference_match(
        "Province",
        identity.get("seller", {}).get("province"),
    )
    buyer_province = _reference_match(
        "Province",
        identity.get("buyer", {}).get("province"),
    )

    if identity.get("seller", {}).get("province") and not seller_province:
        errors.append(
            "Seller Address State/Province is not verified against active FBR Province reference data."
        )
    if identity.get("buyer", {}).get("province") and not buyer_province:
        errors.append(
            "Buyer Address State/Province is not verified against active FBR Province reference data."
        )

    return {
        "seller_province": seller_province or {},
        "buyer_province": buyer_province or {},
    }


def _check_line_references(
    line: dict,
    *,
    posting_date,
    seller_province_reference: dict,
    errors: list[str],
    warnings: list[str],
) -> dict:
    mapping = line.get("fbr_mapping") or {}
    item_code = line.get("item_code") or f"row {line.get('idx')}"

    if not mapping:
        errors.append(f"{item_code}: no active V2 FBR Item Mapping.")
        return {"item_code": item_code, "mapping_ready": False}

    if cint(mapping.get("needs_review")):
        errors.append(f"{item_code}: V2 FBR Item Mapping still requires review.")

    required = {
        "hs_code": "HS Code",
        "fbr_uom": "FBR UOM",
        "sales_type": "FBR Sale/Transaction Type",
        "fbr_rate_description": "FBR Rate Description",
    }
    missing = [
        label
        for fieldname, label in required.items()
        if not _text(mapping.get(fieldname))
    ]
    if missing:
        errors.append(f"{item_code}: missing " + ", ".join(missing) + ".")

    hs_reference = _reference_match("Item Code", mapping.get("hs_code"))
    if mapping.get("hs_code") and not hs_reference:
        errors.append(
            f"{item_code}: HS Code is not verified against active FBR Item Code reference data."
        )

    uom_reference = _reference_match("UOM", mapping.get("fbr_uom"))
    if mapping.get("fbr_uom") and not uom_reference:
        errors.append(
            f"{item_code}: FBR UOM is not verified against active FBR UOM reference data."
        )

    transaction_reference = _reference_match(
        "Transaction Type",
        mapping.get("sales_type"),
    )
    if mapping.get("sales_type") and not transaction_reference:
        errors.append(
            f"{item_code}: Sale Type is not verified against active FBR Transaction Type reference data."
        )

    hs_uom_reference = {}
    if mapping.get("hs_code") and mapping.get("fbr_uom"):
        hs_uom_context = {
            "hs_code": _text(mapping.get("hs_code")),
            "annexure_id": "3",
        }
        hs_uom_context_key = _context_key(hs_uom_context)
        hs_uom_reference = (
            _reference_match(
                "HS-UOM",
                mapping.get("fbr_uom"),
                context_key=hs_uom_context_key,
            )
            or {}
        )
        if not hs_uom_reference:
            errors.append(
                f"{item_code}: selected FBR UOM has no cached HS-UOM proof for the mapped HS Code."
            )

    rate_reference = {}
    seller_province_id = _text(seller_province_reference.get("fbr_id"))
    transaction_type_id = _text((transaction_reference or {}).get("fbr_id"))
    if (
        posting_date
        and seller_province_id
        and transaction_type_id
        and mapping.get("fbr_rate_description")
    ):
        rate_context = {
            "date": str(getdate(posting_date)),
            "transTypeId": transaction_type_id,
            "originationSupplier": seller_province_id,
        }
        rate_context_key = _context_key(rate_context)
        rate_reference = (
            _reference_match(
                "Rate",
                mapping.get("fbr_rate_description"),
                context_key=rate_context_key,
            )
            or {}
        )
        if not rate_reference:
            errors.append(
                f"{item_code}: FBR Rate Description has no cached SaleTypeToRate proof "
                "for invoice date, Sale Type and seller province."
            )
    elif mapping.get("fbr_rate_description"):
        errors.append(
            f"{item_code}: Rate reference context cannot be resolved because Province/Transaction Type reference evidence is incomplete."
        )

    if mapping.get("sro_schedule_number") or mapping.get("sro_item_serial_number"):
        errors.append(
            f"{item_code}: SRO mapping is present but V2 SRO payload semantics still require "
            "runtime proof before payload readiness can pass."
        )

    if mapping.get("tax_basis") == "Notified Retail Price" and flt(
        mapping.get("notified_retail_price")
    ) <= 0:
        errors.append(
            f"{item_code}: Notified Retail Price basis requires a positive notified value."
        )

    return {
        "item_code": item_code,
        "mapping_name": mapping.get("name") or "",
        "mapping_ready": not missing and not cint(mapping.get("needs_review")),
        "hs_reference": hs_reference or {},
        "uom_reference": uom_reference or {},
        "transaction_reference": transaction_reference or {},
        "hs_uom_reference": hs_uom_reference,
        "rate_reference": rate_reference,
    }


def _classify_tax_rows(doc, snapshot: dict, errors: list[str]) -> dict:
    mappings = snapshot.get("component_mappings") or {}
    classified = []
    unclassified = []

    for tax in doc.get("taxes") or []:
        amount = flt(tax.get("tax_amount_after_discount_amount"))
        if abs(amount) <= MONEY_TOLERANCE:
            continue

        row = {
            "idx": tax.get("idx"),
            "account_head": tax.get("account_head") or "",
            "description": tax.get("description") or "",
            "charge_type": tax.get("charge_type") or "",
            "amount": amount,
        }
        component = mappings.get(row["account_head"])
        if component:
            row["component"] = component
            classified.append(row)
        else:
            unclassified.append(row)

    if unclassified:
        accounts = ", ".join(
            sorted({row["account_head"] or row["description"] for row in unclassified})
        )
        errors.append(
            "ERPNext invoice has non-zero tax/charge rows with no explicit FBR V2 classification: "
            + accounts
            + ". Classify their payload treatment before V2 payload cutover."
        )

    return {
        "classified": classified,
        "unclassified": unclassified,
        "complete": not unclassified,
    }


def evaluate_invoice_readiness(reference_doctype: str, reference_name: str) -> dict:
    """Build a read-only V2 payload-input readiness report."""

    reference_doctype = _text(reference_doctype)
    reference_name = _text(reference_name)
    if reference_doctype not in SUPPORTED_DOCTYPES:
        frappe.throw("reference_doctype must be Sales Invoice or POS Invoice.")
    if not reference_name or not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw("Select an existing ERPNext invoice.")

    doc = frappe.get_doc(reference_doctype, reference_name)
    errors: list[str] = []
    warnings: list[str] = []

    profile = _profile(doc.company)
    profile_state = _profile_state(profile)
    if not profile:
        errors.append("Company has no V2 FBR Integration Profile.")

    identity = erpnext_fbr_identity.resolve_invoice_identity(doc)
    errors.extend(identity.get("errors") or [])
    warnings.extend(identity.get("warnings") or [])
    identity_references = _check_identity_references(identity, errors)

    snapshot = {}
    try:
        snapshot = erpnext_fbr_snapshot.build_snapshot_candidate(
            reference_doctype,
            reference_name,
        )
    except Exception as exc:
        errors.append(f"Native tax snapshot candidate failed: {exc}")

    line_reference_checks = []
    if snapshot:
        for line in snapshot.get("lines") or []:
            line_reference_checks.append(
                _check_line_references(
                    line,
                    posting_date=doc.get("posting_date") or doc.get("transaction_date"),
                    seller_province_reference=identity_references["seller_province"],
                    errors=errors,
                    warnings=warnings,
                )
            )

    tax_classification = (
        _classify_tax_rows(doc, snapshot, errors)
        if snapshot
        else {"classified": [], "unclassified": [], "complete": False}
    )

    certification = _sandbox_certification(profile)

    payload_input_ready = not errors
    sandbox_transport_ready = bool(
        payload_input_ready
        and profile_state["enabled"]
        and profile_state["mode"] == "Sandbox"
        and profile_state["sandbox_token_configured"]
    )
    production_transport_ready = bool(
        payload_input_ready
        and profile_state["enabled"]
        and profile_state["mode"] == "Production"
        and profile_state["production_token_configured"]
        and profile_state["production_post_armed"]
        and certification["complete"]
    )

    return {
        "source_doctype": reference_doctype,
        "source_name": reference_name,
        "source_docstatus": cint(doc.docstatus),
        "company": doc.company,
        "profile": profile_state,
        "identity": identity,
        "identity_references": identity_references,
        "native_snapshot_candidate": snapshot,
        "line_reference_checks": line_reference_checks,
        "tax_classification": tax_classification,
        "sandbox_certification": certification,
        "errors": errors,
        "warnings": warnings,
        "payload_input_ready": payload_input_ready,
        "sandbox_transport_ready": sandbox_transport_ready,
        "production_transport_ready": production_transport_ready,
        "payload_built": False,
        "database_write": False,
        "fbr_network_call": False,
        "contains_secrets": False,
    }
