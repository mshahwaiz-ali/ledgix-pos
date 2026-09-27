from __future__ import annotations

"""Phase 13 client provisioning over ERPNext-native configuration.

The setup wizard never creates a second business engine or silently manufactures
accounting masters. It selects a Ledgix product preset, validates the required
ERPNext configuration, and can apply safe site-level defaults for an already
configured Company.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from ledgix_saas.services import fbr_v2_readiness
from ledgix_saas.setup.erpnext_extensions import (
    DEFAULT_BUSINESS_PROFILE,
    PROFILE_DEFAULTS,
    apply_business_profile_defaults,
    get_effective_business_features,
)

SETUP_VERSION = 1
ADMIN_ROLES = {"System Manager", "Ledgix Admin"}

PROFILE_COPY = {
    "Invoice + FBR Only": {
        "title": "Invoice + FBR Only",
        "summary": "Sales Invoice, accounting and FBR without POS or stock workflows.",
        "best_for": "Service, tax-invoice and e-invoicing clients that do not manage inventory in Ledgix.",
    },
    "Small Retail": {
        "title": "Small Retail",
        "summary": "Fast POS, normal inventory and buying with simplified stock controls.",
        "best_for": "Small shops that need POS, purchases and stock but not advanced serial/batch operations.",
    },
    "Full Retail": {
        "title": "Full Retail",
        "summary": "Retail POS plus advanced inventory, serial/batch and stock control workflows.",
        "best_for": "Retail businesses that need full ERPNext stock operations behind the Ledgix UX.",
    },
    "B2B": {
        "title": "B2B",
        "summary": "Sales Invoice, customer credit/receivables and FBR without retail POS requirements.",
        "best_for": "Wholesale and account customers using invoice-led selling.",
    },
    "Mixed": {
        "title": "Mixed",
        "summary": "Retail POS, B2B, buying and advanced inventory in one site.",
        "best_for": "Clients that operate both counter retail and account/B2B sales.",
    },
}


def _require_setup_admin() -> None:
    roles = set(frappe.get_roles())
    if not roles.intersection(ADMIN_ROLES):
        frappe.throw(_("Ledgix client setup requires Ledgix Admin or System Manager access."), frappe.PermissionError)


def _parse(value) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return dict(value)
    parsed = frappe.parse_json(value)
    if not isinstance(parsed, dict):
        frappe.throw(_("Client setup payload must be a JSON object."))
    return dict(parsed)


def _profile(name: str | None) -> tuple[str, dict]:
    name = str(name or DEFAULT_BUSINESS_PROFILE).strip()
    if name not in PROFILE_DEFAULTS:
        frappe.throw(_("Unsupported Ledgix Business Profile: {0}").format(name))
    return name, {key: cint(value) for key, value in PROFILE_DEFAULTS[name].items()}


def _company(value: str | None = None) -> str:
    explicit = str(value or "").strip()
    if explicit:
        return explicit if frappe.db.exists("Company", explicit) else ""
    candidate = str(
        frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
        or ""
    ).strip()
    if candidate and frappe.db.exists("Company", candidate):
        return candidate
    return ""


def _selling_price_list(value: str | None = None) -> str:
    explicit = str(value or "").strip()
    if explicit:
        return explicit if frappe.db.exists("Price List", {"name": explicit, "enabled": 1, "selling": 1}) else ""
    candidate = str(frappe.db.get_single_value("Selling Settings", "selling_price_list") or "").strip()
    if candidate and frappe.db.exists("Price List", {"name": candidate, "enabled": 1, "selling": 1}):
        return candidate
    rows = frappe.get_all(
        "Price List",
        filters={"enabled": 1, "selling": 1},
        pluck="name",
        order_by="name asc",
        limit=1,
    )
    return rows[0] if rows else ""


def _warehouse(company: str, value: str | None = None) -> str:
    explicit = str(value or "").strip()
    if explicit:
        if frappe.db.exists(
            "Warehouse",
            {"name": explicit, "company": company, "is_group": 0, "disabled": 0},
        ):
            return explicit
        return ""
    candidate = str(frappe.db.get_single_value("Stock Settings", "default_warehouse") or "").strip()
    if candidate and frappe.db.exists(
        "Warehouse",
        {"name": candidate, "company": company, "is_group": 0, "disabled": 0},
    ):
        return candidate
    rows = frappe.get_all(
        "Warehouse",
        filters={"company": company, "is_group": 0, "disabled": 0},
        pluck="name",
        order_by="name asc",
        limit=1,
    )
    return rows[0] if rows else ""


def _pos_profile(company: str, value: str | None = None) -> str:
    candidate = str(value or "").strip()
    if candidate:
        if frappe.db.exists("POS Profile", {"name": candidate, "company": company, "disabled": 0}):
            return candidate
        return ""
    rows = frappe.get_all(
        "POS Profile",
        filters={"company": company, "disabled": 0},
        pluck="name",
        order_by="modified desc, name asc",
        limit=1,
    )
    return rows[0] if rows else ""


def _check(key: str, passed: bool, message: str, *, blocking: bool = True, target: str = "") -> dict:
    return {
        "key": key,
        "passed": bool(passed),
        "blocking": bool(blocking),
        "message": message,
        "target": target,
    }


def _pos_profile_checks(name: str, company: str) -> list[dict]:
    if not name:
        return [_check("pos_profile", False, "Create or select an enabled ERPNext POS Profile for this Company.", target="POS Profile")]
    doc = frappe.get_doc("POS Profile", name)
    return [
        _check("pos_profile_company", doc.company == company, "POS Profile must belong to the selected Company.", target="POS Profile"),
        _check("pos_profile_enabled", not cint(doc.get("disabled")), "POS Profile must be enabled.", target="POS Profile"),
        _check("pos_customer", bool(str(doc.get("customer") or "").strip()), "POS Profile needs a default Customer.", target="POS Profile"),
        _check("pos_warehouse", bool(str(doc.get("warehouse") or "").strip()), "POS Profile needs a Warehouse.", target="POS Profile"),
        _check("pos_price_list", bool(str(doc.get("selling_price_list") or "").strip()), "POS Profile needs a Selling Price List.", target="POS Profile"),
        _check("pos_payments", bool(doc.get("payments") or []), "POS Profile needs at least one Mode of Payment.", target="POS Profile"),
    ]


def evaluate_client_setup(payload=None) -> dict:
    """Evaluate a client configuration without mutating the site."""

    _require_setup_admin()
    payload = _parse(payload)
    profile_name, features = _profile(payload.get("business_profile"))
    company = _company(payload.get("company"))
    price_list = _selling_price_list(payload.get("selling_price_list"))
    warehouse = _warehouse(company, payload.get("warehouse")) if company else ""
    pos_profile = _pos_profile(company, payload.get("pos_profile")) if company else ""

    installed = set(frappe.get_installed_apps())
    checks = [
        _check("erpnext_installed", "erpnext" in installed, "ERPNext must be installed on this site."),
        _check("ledgix_installed", "ledgix_saas" in installed, "Ledgix must be installed on this site."),
        _check("company", bool(company), "Select an existing ERPNext Company.", target="Company"),
    ]

    needs_selling = any(features.get(key) for key in ("enable_sales_invoice", "enable_pos", "enable_b2b"))
    if needs_selling:
        checks.append(
            _check(
                "selling_price_list",
                bool(price_list),
                "Configure an enabled ERPNext Selling Price List.",
                target="Selling Settings",
            )
        )

    needs_warehouse = any(features.get(key) for key in ("enable_pos", "enable_inventory", "enable_buying"))
    if needs_warehouse:
        checks.append(
            _check(
                "warehouse",
                bool(warehouse),
                "Configure an enabled leaf ERPNext Warehouse for the selected Company.",
                target="Warehouse",
            )
        )

    if features.get("enable_pos") and company:
        checks.extend(_pos_profile_checks(pos_profile, company))

    if features.get("enable_fbr"):
        state = fbr_v2_readiness.get_company_profile_state(company).get(
            "profile"
        ) or {}
        checks.append(
            _check(
                "fbr_integration_profile",
                bool(state.get("exists")),
                (
                    "Company-scoped Ledgix FBR Integration Profile is available."
                    if state.get("exists")
                    else "Create a Ledgix FBR Integration Profile for the selected Company."
                ),
                blocking=True,
                target="Ledgix FBR Integration Profile",
            )
        )
        checks.append(
            _check(
                "fbr_activation",
                False,
                (
                    "Complete ERPNext seller identity, V2 mappings, official reference "
                    "evidence, Sandbox token/certification and the dedicated activation "
                    "gate before enabling FBR network submission."
                ),
                blocking=False,
                target="Tax & FBR Center",
            )
        )

    blockers = [row for row in checks if row["blocking"] and not row["passed"]]
    warnings = [row for row in checks if not row["blocking"] and not row["passed"]]
    return {
        "setup_version": SETUP_VERSION,
        "business_profile": profile_name,
        "features": features,
        "resolved": {
            "company": company,
            "selling_price_list": price_list,
            "warehouse": warehouse,
            "pos_profile": pos_profile,
        },
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "ready": not blockers,
        "authority": "ERPNext native configuration + Ledgix product preset",
    }


def _profile_state() -> dict:
    doc = frappe.get_single("Ledgix Business Profile")
    return {
        "business_profile": doc.business_profile or DEFAULT_BUSINESS_PROFILE,
        "use_profile_defaults": cint(doc.use_profile_defaults),
        "setup_version": cint(doc.get("setup_version")),
        "setup_complete": cint(doc.get("setup_complete")),
        "setup_completed_at": doc.get("setup_completed_at"),
        "setup_completed_by": doc.get("setup_completed_by") or "",
        "setup_company": doc.get("setup_company") or "",
        "features": get_effective_business_features(),
    }


def _options(company: str) -> dict:
    warehouses = []
    pos_profiles = []
    if company:
        warehouses = frappe.get_all(
            "Warehouse",
            filters={"company": company, "is_group": 0, "disabled": 0},
            pluck="name",
            order_by="name asc",
            limit_page_length=0,
        )
        pos_profiles = frappe.get_all(
            "POS Profile",
            filters={"company": company, "disabled": 0},
            pluck="name",
            order_by="name asc",
            limit_page_length=0,
        )
    return {
        "companies": frappe.get_all("Company", pluck="name", order_by="name asc", limit_page_length=0),
        "warehouses": warehouses,
        "selling_price_lists": frappe.get_all(
            "Price List",
            filters={"enabled": 1, "selling": 1},
            pluck="name",
            order_by="name asc",
            limit_page_length=0,
        ),
        "pos_profiles": pos_profiles,
    }


@frappe.whitelist()
def get_client_setup_boot(company: str | None = None) -> dict:
    _require_setup_admin()
    resolved_company = _company(company)
    state = _profile_state()
    current = evaluate_client_setup(
        {
            "business_profile": state["business_profile"],
            "company": resolved_company or state.get("setup_company"),
        }
    )
    return {
        "setup_version": SETUP_VERSION,
        "presets": [
            {"name": name, **PROFILE_COPY[name], "features": dict(PROFILE_DEFAULTS[name])}
            for name in PROFILE_DEFAULTS
        ],
        "state": state,
        "current": current,
        "options": _options(current["resolved"]["company"]),
        "rules": {
            "configuration_only": True,
            "creates_business_masters": False,
            "permissions_remain_authoritative": True,
            "erpnext_core_modified": False,
        },
    }


@frappe.whitelist()
def apply_client_setup(payload=None) -> dict:
    """Apply a validated Ledgix product preset and safe ERPNext site defaults."""

    _require_setup_admin()
    payload = _parse(payload)
    evaluation = evaluate_client_setup(payload)
    if not evaluation["ready"]:
        messages = "; ".join(row["message"] for row in evaluation["blockers"])
        frappe.throw(_("Client setup is blocked: {0}").format(messages))

    profile = frappe.get_single("Ledgix Business Profile")
    profile.business_profile = evaluation["business_profile"]
    profile.use_profile_defaults = 1
    apply_business_profile_defaults(profile)
    profile.setup_version = SETUP_VERSION
    profile.setup_complete = 1
    profile.setup_completed_at = now_datetime()
    profile.setup_completed_by = frappe.session.user
    profile.setup_company = evaluation["resolved"]["company"]
    profile.setup_snapshot_json = json.dumps(
        {
            "business_profile": evaluation["business_profile"],
            "features": evaluation["features"],
            "resolved": evaluation["resolved"],
        },
        sort_keys=True,
        default=str,
    )
    profile.save(ignore_permissions=True)

    if cint(payload.get("apply_standard_defaults", 1)):
        frappe.db.set_single_value("Global Defaults", "default_company", evaluation["resolved"]["company"])
        if evaluation["resolved"]["selling_price_list"]:
            frappe.db.set_single_value(
                "Selling Settings",
                "selling_price_list",
                evaluation["resolved"]["selling_price_list"],
            )
        if evaluation["resolved"]["warehouse"] and any(
            evaluation["features"].get(key) for key in ("enable_pos", "enable_inventory", "enable_buying")
        ):
            frappe.db.set_single_value(
                "Stock Settings",
                "default_warehouse",
                evaluation["resolved"]["warehouse"],
            )

    frappe.clear_cache()
    return {
        "applied": True,
        "state": _profile_state(),
        "evaluation": evaluate_client_setup(
            {
                "business_profile": evaluation["business_profile"],
                **evaluation["resolved"],
            }
        ),
        "message": _("Ledgix client configuration applied without creating duplicate business masters."),
    }
