from __future__ import annotations

"""Client onboarding/readiness evidence over ERPNext-native configuration.

R5 does not create client business masters, enable FBR Production, or replace
ERPNext authority. It evaluates whether an already provisioned/configured site
is ready for operational handover and can persist a non-secret evidence snapshot.
"""

import json
import os
import re
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from ledgix_saas.api import client_setup

READINESS_SCHEMA_VERSION = 1
ADMIN_ROLES = {"System Manager", "Ledgix Admin"}
LEDGIX_OPERATIONAL_ROLES = ("Ledgix Admin", "Ledgix Manager", "Ledgix Cashier")


def _require_admin() -> None:
    roles = set(frappe.get_roles())
    if not roles.intersection(ADMIN_ROLES):
        frappe.throw(_("Ledgix client readiness requires Ledgix Admin or System Manager access."), frappe.PermissionError)


def _check(
    key: str,
    passed: bool,
    message: str,
    *,
    category: str,
    blocking: bool = True,
    target: str = "",
    details: dict | None = None,
) -> dict:
    return {
        "key": key,
        "passed": bool(passed),
        "blocking": bool(blocking),
        "category": category,
        "message": message,
        "target": target,
        "details": details or {},
    }


def _field_value(doc, fieldname: str) -> str:
    if not doc.meta.has_field(fieldname):
        return ""
    return str(doc.get(fieldname) or "").strip()


def _company_checks(company: str, features: dict) -> list[dict]:
    category = "ERPNext accounting"
    if not company or not frappe.db.exists("Company", company):
        return [
            _check(
                "company_accounting",
                False,
                "Select and configure an ERPNext Company before client handover.",
                category=category,
                target="Company",
            )
        ]

    doc = frappe.get_doc("Company", company)
    checks = [
        _check(
            "chart_of_accounts",
            frappe.db.count("Account", {"company": company}) > 0,
            "Company must have an ERPNext Chart of Accounts.",
            category=category,
            target="Chart of Accounts",
        )
    ]

    needs_selling = any(features.get(key) for key in ("enable_sales_invoice", "enable_pos", "enable_b2b"))
    needs_buying = bool(features.get("enable_buying"))

    required_fields: list[tuple[str, str, bool]] = [
        ("default_receivable_account", "Default Receivable Account", needs_selling),
        ("default_income_account", "Default Income Account", needs_selling),
        ("default_payable_account", "Default Payable Account", needs_buying),
        ("default_expense_account", "Default Expense Account", needs_buying),
    ]
    for fieldname, label, required in required_fields:
        if not required or not doc.meta.has_field(fieldname):
            continue
        checks.append(
            _check(
                f"company_{fieldname}",
                bool(_field_value(doc, fieldname)),
                f"Company needs {label} for the selected Ledgix profile.",
                category=category,
                target="Company",
            )
        )

    return checks


def _payment_checks(company: str, features: dict) -> list[dict]:
    needs_payments = any(features.get(key) for key in ("enable_sales_invoice", "enable_pos", "enable_b2b"))
    if not needs_payments:
        return []

    mappings = []
    if company and frappe.db.exists("DocType", "Mode of Payment Account"):
        mappings = frappe.get_all(
            "Mode of Payment Account",
            filters={"company": company},
            fields=["parent", "default_account"],
            limit_page_length=0,
        )
    valid = [row for row in mappings if str(row.get("default_account") or "").strip()]
    return [
        _check(
            "payment_account_mapping",
            bool(valid),
            "Configure at least one ERPNext Mode of Payment with an account mapping for this Company.",
            category="ERPNext payments",
            target="Mode of Payment",
            details={"mapped_modes": len(valid)},
        )
    ]


def _operational_user_summary() -> dict:
    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "name": ["not in", ["Guest", "Administrator"]]},
        pluck="name",
        limit_page_length=0,
    )
    roles = []
    if users:
        roles = frappe.get_all(
            "Has Role",
            filters={"parent": ["in", users], "parenttype": "User", "role": ["in", list(LEDGIX_OPERATIONAL_ROLES)]},
            fields=["parent", "role"],
            limit_page_length=0,
        )

    by_role = {role: 0 for role in LEDGIX_OPERATIONAL_ROLES}
    ledgix_users = set()
    for row in roles:
        role = row.get("role")
        parent = row.get("parent")
        if role in by_role and parent:
            by_role[role] += 1
            ledgix_users.add(parent)

    return {
        "enabled_named_users": len(users),
        "enabled_ledgix_users": len(ledgix_users),
        "role_counts": by_role,
    }


def _user_checks(features: dict) -> list[dict]:
    category = "Users and roles"
    missing_roles = [role for role in LEDGIX_OPERATIONAL_ROLES if not frappe.db.exists("Role", role)]
    summary = _operational_user_summary()
    checks = [
        _check(
            "ledgix_roles_installed",
            not missing_roles,
            "Ledgix Admin, Manager and Cashier role definitions must be installed.",
            category=category,
            target="Role",
            details={"missing_roles": missing_roles},
        ),
        _check(
            "named_operational_user",
            summary["enabled_ledgix_users"] > 0,
            "Create at least one enabled named user with a Ledgix operational role before handover.",
            category=category,
            target="User",
            details=summary,
        ),
    ]

    if features.get("enable_pos"):
        checks.append(
            _check(
                "cashier_user",
                summary["role_counts"].get("Ledgix Cashier", 0) > 0,
                "POS-enabled clients should have at least one named Ledgix Cashier user.",
                category=category,
                blocking=False,
                target="User",
                details=summary,
            )
        )
    return checks


def _fbr_checks(features: dict) -> list[dict]:
    if not features.get("enable_fbr"):
        return []

    category = "FBR handoff"
    if not frappe.db.exists("DocType", "Ledgix FBR Settings"):
        return [
            _check(
                "fbr_settings_installed",
                False,
                "Ledgix FBR Settings must be installed for an FBR-enabled profile.",
                category=category,
                target="Ledgix FBR Settings",
            )
        ]

    doc = frappe.get_single("Ledgix FBR Settings")
    seller_fields = ("seller_ntn_cnic", "seller_business_name", "seller_province", "seller_address")
    missing_identity = [fieldname for fieldname in seller_fields if not str(doc.get(fieldname) or "").strip()]
    armed = bool(cint(doc.get("production_post_armed")))
    mode = str(doc.get("mode") or "Disabled")

    return [
        _check(
            "fbr_settings_installed",
            True,
            "Ledgix FBR Settings are installed.",
            category=category,
            target="Ledgix FBR Settings",
        ),
        _check(
            "fbr_pre_activation_interlock",
            not armed,
            "FBR Production posting must remain unarmed until the dedicated Sandbox-to-Production activation gate.",
            category=category,
            target="Ledgix FBR Settings",
            details={"mode": mode, "production_post_armed": armed},
        ),
        _check(
            "fbr_seller_identity",
            not missing_identity,
            "Complete FBR seller identity before the next FBR Sandbox/Production workstream.",
            category=category,
            blocking=False,
            target="Ledgix FBR Settings",
            details={"missing_fields": missing_identity, "mode": mode},
        ),
    ]


def _evidence_checks(strict_evidence: bool) -> tuple[list[dict], dict]:
    site_root = Path(frappe.get_site_path())
    provisioning = site_root / "private" / "ledgix-provisioning" / "initial-provisioning.env"
    release = site_root / "private" / "ledgix-release" / "last-successful.env"
    backup_dir = site_root / "private" / "backups"
    backups = sorted(backup_dir.glob("ledgix-backup-*.env"), key=lambda path: path.stat().st_mtime, reverse=True) if backup_dir.exists() else []

    identity_evidence = provisioning.exists() or release.exists()
    summary = {
        "provisioning_evidence": provisioning.exists(),
        "release_evidence": release.exists(),
        "verified_backup_metadata": bool(backups),
        "latest_backup_metadata": backups[0].name if backups else "",
    }
    checks = [
        _check(
            "release_identity_evidence",
            identity_evidence,
            "Retain provisioning or release identity evidence for this client site.",
            category="Operational evidence",
            blocking=strict_evidence,
            target="Site private Ledgix evidence",
            details=summary,
        ),
        _check(
            "verified_backup_evidence",
            bool(backups),
            "Retain a verified backup metadata set before production acceptance.",
            category="Operational evidence",
            blocking=strict_evidence,
            target="Verified backup",
            details=summary,
        ),
    ]
    return checks, summary


def evaluate_client_readiness(strict_evidence: int | str = 0) -> dict:
    """Read-only operational readiness evaluation for an already configured site."""

    _require_admin()
    strict = bool(cint(strict_evidence))
    profile = frappe.get_single("Ledgix Business Profile")
    company = str(profile.get("setup_company") or "").strip()
    setup_evaluation = client_setup.evaluate_client_setup(
        {
            "business_profile": profile.get("business_profile"),
            "company": company,
        }
    )
    features = dict(setup_evaluation.get("features") or {})
    resolved = dict(setup_evaluation.get("resolved") or {})
    company = resolved.get("company") or company

    checks = [
        _check(
            "client_setup_applied",
            bool(cint(profile.get("setup_complete"))),
            "Apply the Ledgix client setup profile before operational handover.",
            category="Ledgix setup",
            target="Ledgix Client Setup",
        ),
        _check(
            "client_setup_current_readiness",
            bool(setup_evaluation.get("ready")),
            "The current Business Profile must still satisfy its ERPNext configuration prerequisites.",
            category="Ledgix setup",
            target="Ledgix Client Setup",
            details={"setup_blockers": [row.get("key") for row in setup_evaluation.get("blockers") or []]},
        ),
    ]
    checks.extend(_company_checks(company, features))
    checks.extend(_payment_checks(company, features))
    checks.extend(_user_checks(features))
    checks.extend(_fbr_checks(features))
    evidence_checks, evidence_summary = _evidence_checks(strict)
    checks.extend(evidence_checks)

    blockers = [row for row in checks if row["blocking"] and not row["passed"]]
    warnings = [row for row in checks if not row["blocking"] and not row["passed"]]

    company_doc = frappe.get_doc("Company", company) if company and frappe.db.exists("Company", company) else None
    system_timezone = str(frappe.db.get_single_value("System Settings", "time_zone") or "").strip()
    installed_apps = sorted(frappe.get_installed_apps())

    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "site": getattr(frappe.local, "site", ""),
        "strict_evidence": strict,
        "business_profile": profile.get("business_profile"),
        "features": features,
        "identity": {
            "company": company,
            "country": _field_value(company_doc, "country") if company_doc else "",
            "currency": _field_value(company_doc, "default_currency") if company_doc else "",
            "timezone": system_timezone,
            "setup_completed_at": profile.get("setup_completed_at"),
            "setup_completed_by": profile.get("setup_completed_by") or "",
        },
        "installed_apps": installed_apps,
        "resolved": resolved,
        "evidence": evidence_summary,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "ready": not blockers,
        "next_workstream": "FBR Sandbox -> Production activation" if features.get("enable_fbr") else "Printing / devices / profile UAT",
        "authority": "ERPNext business configuration + Ledgix onboarding evidence",
    }


@frappe.whitelist()
def get_client_readiness(strict_evidence: int | str = 0) -> dict:
    return evaluate_client_readiness(strict_evidence=strict_evidence)


@frappe.whitelist()
def generate_client_readiness_evidence(
    release_sha: str = "",
    site_url: str = "",
    operator: str = "",
    strict_evidence: int | str = 0,
) -> dict:
    """Persist a non-secret readiness snapshot under the site's private directory."""

    _require_admin()
    release_sha = str(release_sha or "").strip()
    site_url = str(site_url or "").strip()
    operator = str(operator or frappe.session.user or "").strip()
    if release_sha and not re.fullmatch(r"[0-9a-fA-F]{40}", release_sha):
        frappe.throw(_("release_sha must be a full 40-character Git commit SHA."))
    if site_url and not re.fullmatch(r"https?://[^\s]+", site_url):
        frappe.throw(_("site_url must be an http(s) URL."))

    readiness = evaluate_client_readiness(strict_evidence=strict_evidence)
    generated_at = now_datetime()
    payload = {
        "schema_version": READINESS_SCHEMA_VERSION,
        "generated_at": generated_at,
        "operator": operator,
        "release_sha": release_sha,
        "site_url": site_url,
        "readiness": readiness,
        "contains_secrets": False,
        "business_data_authority": "ERPNext",
    }

    evidence_dir = Path(frappe.get_site_path("private", "ledgix-readiness"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(evidence_dir, 0o700)
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    evidence_path = evidence_dir / f"client-readiness-{timestamp}.json"
    latest_path = evidence_dir / "latest.json"
    content = json.dumps(payload, sort_keys=True, indent=2, default=str) + "\n"
    evidence_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")
    os.chmod(evidence_path, 0o600)
    os.chmod(latest_path, 0o600)

    return {
        **readiness,
        "evidence_file": f"private/ledgix-readiness/{evidence_path.name}",
        "latest_evidence_file": "private/ledgix-readiness/latest.json",
        "release_sha": release_sha,
        "site_url": site_url,
        "evidence_written": True,
    }
