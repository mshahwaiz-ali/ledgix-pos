from __future__ import annotations

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api import tax_center
from ledgix_saas.api.fbr_settings import get_fbr_control_state, get_fbr_settings
from ledgix_saas.services.sales import get_seller_identity


NON_SCORING_KEYS = {
    "production_post",
    "auto_submit",
    "automatic_retransmission",
    "reference_api_sync",
}

PLACEHOLDER_EXACT = {
    "ledgix",
    "sweet bakery demo",
    "ledgix test seller",
    "test seller",
    "test outlet",
}
PLACEHOLDER_FRAGMENTS = (
    "demo data",
    "configure real",
    "test seller",
    "test outlet",
)


def _check(key, label, ready, value, level=None):
    if level is None:
        level = "ready" if ready else "missing"
    return {
        "key": key,
        "label": label,
        "ready": bool(ready),
        "value": value,
        "level": level,
    }


def _token_check(mode, target_mode, configured, label):
    if mode == target_mode:
        return _check(
            f"{target_mode.lower()}_token",
            label,
            configured,
            "Configured" if configured else "Missing",
            "ready" if configured else "missing",
        )
    if mode in {"Sandbox", "Production"}:
        return _check(
            f"{target_mode.lower()}_token",
            label,
            True,
            f"Not required in {mode}",
            "ready",
        )
    return _check(
        f"{target_mode.lower()}_token",
        label,
        False,
        "Select Sandbox or Production mode first",
        "warning",
    )


def _is_real_identity_value(value):
    normalized = " ".join(str(value or "").split()).strip().casefold()
    if not normalized:
        return False
    if normalized in PLACEHOLDER_EXACT:
        return False
    return not any(marker in normalized for marker in PLACEHOLDER_FRAGMENTS)


def _seller_checks():
    seller = get_seller_identity() or {}
    business_name = seller.get("name") or ""
    address = seller.get("address") or ""
    business_name_ready = _is_real_identity_value(business_name)
    address_ready = _is_real_identity_value(address)
    return seller, [
        _check("seller_ntn_cnic", "Seller NTN/CNIC", bool(seller.get("ntn_cnic")), seller.get("ntn_cnic") or "Missing"),
        _check(
            "seller_business_name",
            "Seller Business Name",
            business_name_ready,
            business_name or "Missing",
            "ready" if business_name_ready else "missing",
        ),
        _check("seller_province", "Seller Province", bool(seller.get("province")), seller.get("province") or "Missing"),
        _check(
            "seller_address",
            "Seller Address",
            address_ready,
            address or "Missing",
            "ready" if address_ready else "missing",
        ),
    ]


@frappe.whitelist()
def get_fbr_readiness():
    """Environment-aware FBR readiness without performing any FBR network call."""
    tax_center._require_tax_view()

    settings = get_fbr_settings() or {}
    control = get_fbr_control_state() or {}
    profile = tax_center._profile_dict() or {}
    mode = settings.get("mode") or "Disabled"
    enabled = bool(settings.get("enabled")) and mode in {"Sandbox", "Production"}

    active_profiles = tax_center._get_count("Ledgix Item Tax Profile", {"active": 1})
    taxable_profiles = tax_center._get_count("Ledgix Item Tax Profile", {"active": 1, "taxable": 1})
    missing_hs = tax_center._count_missing_hs_code()
    missing_uom = tax_center._count_missing_item_tax_field("uom_for_fbr")
    missing_scenario = tax_center._count_missing_item_tax_field("scenario_id")
    needs_review = tax_center._get_count("Ledgix Item Tax Profile", {"active": 1, "needs_review": 1})

    hs_covered = max(taxable_profiles - missing_hs, 0)
    uom_covered = max(taxable_profiles - missing_uom, 0)
    scenario_covered = max(taxable_profiles - missing_scenario, 0)
    hs_coverage = flt((hs_covered / taxable_profiles) * 100, 2) if taxable_profiles else 0
    uom_coverage = flt((uom_covered / taxable_profiles) * 100, 2) if taxable_profiles else 0
    scenario_coverage = flt((scenario_covered / taxable_profiles) * 100, 2) if taxable_profiles else 0

    sandbox_token_configured = bool(settings.get("sandbox_token_configured"))
    production_token_configured = bool(settings.get("production_token_configured"))
    seller, seller_checks = _seller_checks()

    checks = [
        _check("fbr_mode", "FBR Mode", mode in {"Sandbox", "Production"}, mode),
        _check("fbr_enabled", "FBR Enabled", enabled, "Enabled" if enabled else "Disabled"),
        _check("tax_engine", "Tax Engine", bool(cint(profile.get("tax_enabled"))), "Enabled" if cint(profile.get("tax_enabled")) else "Disabled"),
        _token_check(mode, "Sandbox", sandbox_token_configured, "Sandbox Token"),
        _token_check(mode, "Production", production_token_configured, "Production Token"),
        *seller_checks,
        _check("hs_code_coverage", "HS Code Coverage", taxable_profiles > 0 and missing_hs == 0, f"{hs_coverage}%"),
        _check("uom_coverage", "UOM for FBR Coverage", taxable_profiles > 0 and missing_uom == 0, f"{uom_coverage}%"),
    ]

    if mode == "Sandbox":
        checks.append(
            _check(
                "scenario_coverage",
                "Sandbox Scenario ID Coverage",
                taxable_profiles > 0 and missing_scenario == 0,
                f"{scenario_coverage}%",
            )
        )
    elif mode == "Production":
        checks.append(_check("scenario_coverage", "Sandbox Scenario ID Coverage", True, "Not required in Production payload", "ready"))
    else:
        checks.append(
            _check(
                "scenario_coverage",
                "Sandbox Scenario ID Coverage",
                False,
                f"{scenario_coverage}% · select Sandbox mode to make this required",
                "warning",
            )
        )

    checks.append(
        _check(
            "item_review",
            "Items Needing Review",
            needs_review == 0,
            needs_review,
            "ready" if needs_review == 0 else "warning",
        )
    )

    if mode == "Production":
        production_post_ready = bool(control.get("production_post_ready"))
        checks.append(
            _check(
                "production_post",
                "Production Posting Interlock",
                production_post_ready,
                "Armed and ready" if production_post_ready else "Not armed / not ready",
                "ready" if production_post_ready else "missing",
            )
        )
    elif mode == "Sandbox":
        checks.append(_check("production_post", "Production Posting Interlock", True, "Not required in Sandbox", "ready"))
    else:
        checks.append(_check("production_post", "Production Posting Interlock", False, "Production not selected", "warning"))

    submit_trigger = settings.get("submit_trigger") or "Manual"
    auto_submit_active = bool(control.get("auto_submit_active"))
    if submit_trigger == "On Submit":
        checks.append(
            _check(
                "auto_submit",
                "Auto Submit",
                auto_submit_active if mode == "Production" else bool(settings.get("sandbox_post_on_submit")),
                "Active" if (auto_submit_active or settings.get("sandbox_post_on_submit")) else "Configured On Submit but posting is not active",
                "ready" if (auto_submit_active or settings.get("sandbox_post_on_submit")) else "warning",
            )
        )
    else:
        checks.append(_check("auto_submit", "Auto Submit", True, f"{submit_trigger} by design", "ready"))

    retransmission_safe = not bool(control.get("retry_worker_active")) and not bool(control.get("offline_worker_active"))
    checks.append(
        _check(
            "automatic_retransmission",
            "Automatic Retransmission",
            retransmission_safe,
            "Disabled (fail-closed)" if retransmission_safe else "Unexpectedly active",
            "ready" if retransmission_safe else "missing",
        )
    )

    official_logo_configured = bool(settings.get("digital_invoicing_logo"))
    software_registration_configured = bool(settings.get("software_registration_number"))
    production_print_level = "missing" if mode == "Production" else "warning"
    checks.extend(
        [
            _check(
                "digital_invoicing_logo",
                "Official Digital Invoicing Logo",
                official_logo_configured,
                "Configured" if official_logo_configured else "Official FBR/PRAL/LI asset not configured",
                "ready" if official_logo_configured else production_print_level,
            ),
            _check(
                "software_registration_number",
                "Software Registration Number",
                software_registration_configured,
                settings.get("software_registration_number") or "Not configured",
                "ready" if software_registration_configured else production_print_level,
            ),
        ]
    )

    reference_token_ready = sandbox_token_configured if mode == "Sandbox" else production_token_configured if mode == "Production" else False
    checks.append(
        _check(
            "reference_api_sync",
            "Official Reference API Check",
            False,
            "Ready for manual lookup" if enabled and reference_token_ready else "Configure active environment/token first",
            "warning",
        )
    )

    sales_return_meta = frappe.get_meta("Ledgix Sales Return")
    return_fbr_ready = bool(
        sales_return_meta.has_field("fbr_status")
        and sales_return_meta.has_field("fbr_invoice_number")
        and sales_return_meta.has_field("fbr_qr_code")
    )
    checks.append(
        _check(
            "return_fbr_note",
            "Sales Return / FBR Note",
            return_fbr_ready,
            "Credit-note flow implemented; exact accepted FBR note contract remains Sandbox/PRAL verification." if return_fbr_ready else "Sales Return FBR fields missing",
            "ready" if return_fbr_ready else "missing",
        )
    )

    correction_ready = bool(frappe.db.exists("DocType", "Ledgix FBR Correction Request"))
    checks.append(
        _check(
            "correction_tracking",
            "72-Hour Correction Tracking",
            correction_ready,
            "Available" if correction_ready else "Correction request DocType missing",
            "ready" if correction_ready else "missing",
        )
    )

    scoring_exclusions = set(NON_SCORING_KEYS)
    if mode != "Production":
        scoring_exclusions.update({"digital_invoicing_logo", "software_registration_number"})
    if mode != "Sandbox":
        scoring_exclusions.add("scenario_coverage")

    scorable_checks = [row for row in checks if row.get("key") not in scoring_exclusions]
    ready_count = len([row for row in scorable_checks if row.get("ready")])
    blocking_gaps = [row.get("label") for row in scorable_checks if not row.get("ready") and row.get("level") == "missing"]
    warnings = [row.get("label") for row in checks if not row.get("ready") and row.get("level") == "warning"]

    return {
        "checks": checks,
        "stats": {
            "active_item_tax_profiles": active_profiles,
            "active_taxable_item_tax_profiles": taxable_profiles,
            "missing_hs_code": missing_hs,
            "missing_uom_for_fbr": missing_uom,
            "missing_scenario_id": missing_scenario,
            "items_needing_review": needs_review,
            "hs_code_coverage_percent": hs_coverage,
            "uom_for_fbr_coverage_percent": uom_coverage,
            "scenario_id_coverage_percent": scenario_coverage,
            "fbr_enabled": enabled,
            "fbr_mode": mode,
            "sandbox_token_configured": sandbox_token_configured,
            "production_token_configured": production_token_configured,
            "production_post_ready": bool(control.get("production_post_ready")),
            "auto_submit_active": auto_submit_active,
            "automatic_retransmission_active": not retransmission_safe,
            "official_digital_invoicing_logo_configured": official_logo_configured,
            "software_registration_number_configured": software_registration_configured,
            "seller_identity": {
                "name": seller.get("name") or "",
                "province": seller.get("province") or "",
                "ntn_cnic": seller.get("ntn_cnic") or "",
                "address": seller.get("address") or "",
            },
        },
        "ready_score": flt((ready_count / len(scorable_checks)) * 100, 2) if scorable_checks else 0,
        "blocking_gaps": blocking_gaps,
        "warnings": warnings,
        "target_environment": mode if mode in {"Sandbox", "Production"} else "Unselected",
        "settings_summary": {
            "enabled": bool(settings.get("enabled")),
            "mode": mode,
            "submit_trigger": submit_trigger,
            "sandbox_token_configured": sandbox_token_configured,
            "production_token_configured": production_token_configured,
            "software_registration_number": settings.get("software_registration_number") or "",
            "digital_invoicing_logo_configured": official_logo_configured,
            "production_post_armed": bool(settings.get("production_post_armed")),
            "retry_enabled": bool(settings.get("retry_enabled")),
        },
        "control_state": control,
    }
