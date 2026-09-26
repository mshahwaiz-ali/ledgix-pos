from __future__ import annotations

"""Standalone ERPNext/FBR operational-readiness evidence.

This module intentionally has no Ledgix application dependency. Existing
Ledgix roles/evidence are accepted only as transition-compatible aliases.
"""

import json
import os
import re
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import now_datetime

from fbr_v12.services import erpnext_fbr_identity, fbr_v2_readiness

READINESS_SCHEMA_VERSION = 2
PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"

ADMIN_ROLES = {"System Manager", "Accounts Manager", "Ledgix Admin"}
OPERATIONAL_ROLES = (
    "Accounts Manager",
    "Accounts User",
    "Sales Manager",
    "Ledgix Admin",
    "Ledgix Manager",
)


def _require_admin() -> None:
    roles = set(frappe.get_roles())
    if not roles.intersection(ADMIN_ROLES):
        frappe.throw(
            _("FBR V1.2 readiness requires System Manager or Accounts Manager access."),
            frappe.PermissionError,
        )


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
    if not doc or not doc.meta.has_field(fieldname):
        return ""
    return str(doc.get(fieldname) or "").strip()


def _resolve_company() -> tuple[str, dict]:
    default_company = str(
        frappe.db.get_single_value("Global Defaults", "default_company") or ""
    ).strip()

    profiles = []
    if frappe.db.exists("DocType", PROFILE_DOCTYPE):
        profiles = frappe.get_all(
            PROFILE_DOCTYPE,
            fields=["name", "company", "enabled", "mode"],
            order_by="modified desc",
            limit_page_length=0,
        )

    companies = sorted(
        {
            str(row.get("company") or "").strip()
            for row in profiles
            if str(row.get("company") or "").strip()
        }
    )

    if default_company and default_company in companies:
        company = default_company
        source = "Global Defaults + FBR profile"
    elif len(companies) == 1:
        company = companies[0]
        source = "Single FBR integration profile"
    elif default_company:
        company = default_company
        source = "ERPNext Global Defaults"
    elif len(companies) == 1:
        company = companies[0]
        source = "Single FBR integration profile"
    else:
        company = ""
        source = "Unresolved"

    return company, {
        "source": source,
        "default_company": default_company,
        "profile_companies": companies,
        "profile_count": len(profiles),
        "ambiguous": not company and len(companies) > 1,
    }


def _operational_user_summary() -> dict:
    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "name": ["not in", ["Guest", "Administrator"]]},
        pluck="name",
        limit_page_length=0,
    )
    rows = []
    if users:
        rows = frappe.get_all(
            "Has Role",
            filters={
                "parent": ["in", users],
                "parenttype": "User",
                "role": ["in", list(OPERATIONAL_ROLES)],
            },
            fields=["parent", "role"],
            limit_page_length=0,
        )

    by_role = {role: 0 for role in OPERATIONAL_ROLES}
    operational_users = set()
    for row in rows:
        role = row.get("role")
        user = row.get("parent")
        if role in by_role and user:
            by_role[role] += 1
            operational_users.add(user)

    return {
        "enabled_named_users": len(users),
        "enabled_operational_users": len(operational_users),
        "role_counts": by_role,
    }


def _backup_candidates() -> list[Path]:
    backup_dir = Path(frappe.get_site_path("private", "backups"))
    if not backup_dir.exists():
        return []

    candidates: list[Path] = []
    patterns = (
        "*database.sql.gz",
        "*.sql.gz",
        "ledgix-backup-*.env",
        "*site_config_backup.json",
    )
    seen = set()
    for pattern in patterns:
        for path in backup_dir.glob(pattern):
            key = str(path)
            if key not in seen and path.is_file():
                seen.add(key)
                candidates.append(path)
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def _evidence_checks(strict_evidence: bool) -> tuple[list[dict], dict]:
    backups = _backup_candidates()
    compatibility_dirs = [
        Path(frappe.get_site_path("private", "ledgix-provisioning")),
        Path(frappe.get_site_path("private", "ledgix-release")),
    ]
    release_compatibility_evidence = any(path.exists() for path in compatibility_dirs)

    summary = {
        "backup_evidence_present": bool(backups),
        "latest_backup_evidence": backups[0].name if backups else "",
        "legacy_release_evidence_present": release_compatibility_evidence,
    }
    checks = [
        _check(
            "backup_evidence",
            bool(backups),
            "Retain a recent ERPNext site backup before production acceptance.",
            category="Operational evidence",
            blocking=strict_evidence,
            target="Site private backups",
            details=summary,
        )
    ]
    return checks, summary


def evaluate_client_readiness(strict_evidence: int | str = 0) -> dict:
    """Read-only readiness for a standalone ERPNext + FBR V1.2 installation."""

    _require_admin()
    strict = str(strict_evidence or "0").strip() not in {"", "0", "false", "False"}
    company, company_resolution = _resolve_company()

    checks: list[dict] = [
        _check(
            "company_resolved",
            bool(company) and frappe.db.exists("Company", company),
            "Configure one ERPNext Company for the FBR integration.",
            category="ERPNext company",
            target="Company",
            details=company_resolution,
        )
    ]

    company_doc = (
        frappe.get_doc("Company", company)
        if company and frappe.db.exists("Company", company)
        else None
    )
    if company_doc:
        checks.append(
            _check(
                "chart_of_accounts",
                frappe.db.count("Account", {"company": company}) > 0,
                "ERPNext Company must have a Chart of Accounts.",
                category="ERPNext accounting",
                target="Chart of Accounts",
            )
        )

    profile_bundle = (
        fbr_v2_readiness.get_company_profile_state(company)
        if company
        else {"profile": {}, "sandbox_certification": {}}
    )
    profile = dict(profile_bundle.get("profile") or {})
    checks.append(
        _check(
            "fbr_integration_profile",
            bool(profile.get("exists")),
            "Create a company-scoped FBR Integration Profile.",
            category="FBR configuration",
            target=PROFILE_DOCTYPE,
            details={"company": company, "profile": profile.get("name") or ""},
        )
    )

    identity = (
        erpnext_fbr_identity.resolve_company_seller_identity(company)
        if company
        else {"ready": False, "errors": ["Company is unresolved."]}
    )
    checks.append(
        _check(
            "fbr_seller_identity",
            bool(identity.get("ready")),
            "Complete ERPNext Company Tax ID and Company Address/Province for FBR.",
            category="FBR configuration",
            target="Company / Address",
            details={"errors": list(identity.get("errors") or [])},
        )
    )

    users = _operational_user_summary()
    checks.append(
        _check(
            "named_operational_user",
            users["enabled_operational_users"] > 0,
            "Assign at least one enabled named user an ERPNext accounting/sales operational role.",
            category="Users and roles",
            blocking=False,
            target="User",
            details=users,
        )
    )

    evidence_checks, evidence_summary = _evidence_checks(strict)
    checks.extend(evidence_checks)

    blockers = [row for row in checks if row["blocking"] and not row["passed"]]
    warnings = [row for row in checks if not row["blocking"] and not row["passed"]]

    pos_enabled = False
    if company and frappe.db.exists("DocType", "POS Profile"):
        pos_enabled = bool(frappe.db.count("POS Profile", {"company": company}))

    system_timezone = str(
        frappe.db.get_single_value("System Settings", "time_zone") or ""
    ).strip()

    return {
        "schema_version": READINESS_SCHEMA_VERSION,
        "site": getattr(frappe.local, "site", ""),
        "strict_evidence": strict,
        "business_profile": "Standalone FBR V1.2",
        "features": {
            "enable_fbr": True,
            "enable_pos": pos_enabled,
            "enable_sales_invoice": True,
        },
        "identity": {
            "company": company,
            "country": _field_value(company_doc, "country"),
            "currency": _field_value(company_doc, "default_currency"),
            "timezone": system_timezone,
        },
        "installed_apps": sorted(frappe.get_installed_apps()),
        "resolved": company_resolution,
        "evidence": evidence_summary,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "ready": not blockers,
        "next_workstream": "FBR Sandbox -> Production activation",
        "authority": "ERPNext business configuration + FBR V1.2 readiness evidence",
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

    evidence_dir = Path(frappe.get_site_path("private", "fbr-v12-readiness"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(evidence_dir, 0o700)
    timestamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    evidence_path = evidence_dir / f"site-readiness-{timestamp}.json"
    latest_path = evidence_dir / "latest.json"
    content = json.dumps(payload, sort_keys=True, indent=2, default=str) + "\n"
    evidence_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")
    os.chmod(evidence_path, 0o600)
    os.chmod(latest_path, 0o600)

    return {
        **readiness,
        "evidence_file": f"private/fbr-v12-readiness/{evidence_path.name}",
        "latest_evidence_file": "private/fbr-v12-readiness/latest.json",
        "release_sha": release_sha,
        "site_url": site_url,
        "evidence_written": True,
    }
