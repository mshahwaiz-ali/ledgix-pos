from __future__ import annotations

"""Phase 12 migrate-time retirement synchronization.

The existing Ledgix permission policy is intentionally left intact until an
explicit successful freeze.  Once the retirement state is Frozen, this module
reapplies read-only audit permissions after every migrate so earlier setup hooks
cannot accidentally reopen legacy business DocTypes.
"""

import frappe
from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
from frappe.permissions import setup_custom_perms

from ledgix_saas.api import legacy_retirement
from ledgix_saas.setup.permissions import PERM_KEYS

AUDIT_ROLES = ("System Manager", "Ledgix Admin", "Ledgix Manager")
MANAGED_ROLES = ("System Manager", "Ledgix Admin", "Ledgix Manager", "Ledgix Cashier")


def _audit_values() -> dict:
    values = {key: 0 for key in PERM_KEYS}
    values.update({"read": 1, "report": 1, "export": 1, "print": 1})
    return values


def _insert_audit_perm(doctype: str, role: str) -> None:
    frappe.get_doc(
        {
            "doctype": "Custom DocPerm",
            "parent": doctype,
            "parenttype": "DocType",
            "parentfield": "permissions",
            "role": role,
            "permlevel": 0,
            "if_owner": 0,
            **_audit_values(),
        }
    ).insert(ignore_permissions=True)


def sync_legacy_read_only_permissions() -> dict:
    changed = []
    for doctype in legacy_retirement.LEGACY_TOP_LEVEL_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        setup_custom_perms(doctype)
        frappe.db.delete(
            "Custom DocPerm",
            {
                "parent": doctype,
                "parenttype": "DocType",
                "permlevel": 0,
                "role": ["in", list(MANAGED_ROLES)],
            },
        )
        for role in AUDIT_ROLES:
            if frappe.db.exists("Role", role):
                _insert_audit_perm(doctype, role)
        validate_permissions_for_doctype(doctype)
        frappe.clear_cache(doctype=doctype)
        changed.append(doctype)
    frappe.db.commit()
    return {
        "frozen": legacy_retirement.is_frozen(),
        "doctypes": changed,
        "audit_roles": list(AUDIT_ROLES),
        "cashier_legacy_access": False,
    }


def read_only_permission_status() -> dict:
    rows = {}
    violations = []
    for doctype in legacy_retirement.LEGACY_TOP_LEVEL_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        permissions = frappe.get_all(
            "Custom DocPerm",
            filters={
                "parent": doctype,
                "parenttype": "DocType",
                "permlevel": 0,
                "role": ["in", list(MANAGED_ROLES)],
            },
            fields=["role", *PERM_KEYS],
            order_by="role asc",
            limit_page_length=0,
        )
        normalized = []
        for row in permissions:
            values = {key: int(row.get(key) or 0) for key in PERM_KEYS}
            normalized.append({"role": row.role, **values})
            forbidden = [
                key
                for key in ("write", "create", "delete", "submit", "cancel", "amend", "share", "email")
                if values.get(key)
            ]
            if forbidden:
                violations.append({"doctype": doctype, "role": row.role, "forbidden": forbidden})
            if row.role == "Ledgix Cashier":
                violations.append({"doctype": doctype, "role": row.role, "forbidden": ["legacy_cashier_access"]})
        expected_roles = set(AUDIT_ROLES)
        actual_roles = {row["role"] for row in normalized}
        if actual_roles != expected_roles:
            violations.append(
                {
                    "doctype": doctype,
                    "role_mismatch": {
                        "expected": sorted(expected_roles),
                        "actual": sorted(actual_roles),
                    },
                }
            )
        rows[doctype] = normalized
    return {"rows": rows, "violations": violations, "ready": not violations}


def sync_all() -> dict:
    if legacy_retirement.is_frozen():
        return sync_legacy_read_only_permissions()
    return {
        "frozen": False,
        "doctypes": [],
        "policy": "Legacy permissions remain available until explicit Phase 12 reconciliation/freeze succeeds.",
    }


def after_migrate() -> None:
    sync_all()
