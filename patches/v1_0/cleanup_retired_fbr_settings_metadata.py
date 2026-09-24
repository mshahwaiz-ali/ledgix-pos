from __future__ import annotations

"""Guarded cleanup for the retired Ledgix FBR Settings singleton metadata.

IMPORTANT:
- This module is intentionally NOT registered in patches.txt yet.
- preview_cleanup() is read-only.
- execute() is destructive metadata cleanup and requires an explicit site-config
  authorization proving the operator has already taken and verified a backup.
- No FBR network operation is performed here.
"""

import frappe
from frappe.utils import cint


LEGACY_DOCTYPE = "Ledgix FBR Settings"
V2_PROFILE = "Ledgix FBR Integration Profile"
AUTHORIZATION_KEY = "ledgix_legacy_fbr_settings_cleanup_authorization"
AUTHORIZATION_VALUE = "VERIFIED_BACKUP_AND_APPROVED_FBR_SETTINGS_CLEANUP"


def _profile_rows() -> list[dict]:
    if not frappe.db.exists("DocType", V2_PROFILE):
        return []
    return [
        dict(row)
        for row in frappe.get_all(
            V2_PROFILE,
            fields=[
                "name",
                "company",
                "enabled",
                "mode",
                "submit_trigger",
                "production_post_armed",
            ],
            limit_page_length=0,
        )
    ]


def _assert_safe_v2_state() -> None:
    profiles = _profile_rows()
    unsafe = [
        row
        for row in profiles
        if cint(row.get("enabled"))
        or (row.get("mode") or "Disabled") != "Disabled"
        or cint(row.get("production_post_armed"))
    ]
    if unsafe:
        frappe.throw(
            "Refusing legacy FBR Settings cleanup while any V2 Integration "
            "Profile is enabled, non-Disabled, or Production-armed. "
            + frappe.as_json([row.get("name") for row in unsafe])
        )


def _assert_authorized() -> None:
    value = str(frappe.conf.get(AUTHORIZATION_KEY) or "").strip()
    if value != AUTHORIZATION_VALUE:
        frappe.throw(
            "Legacy FBR Settings cleanup is not authorized. Take and verify a "
            "fresh site backup first, then set site_config.json "
            f"{AUTHORIZATION_KEY}={AUTHORIZATION_VALUE!r} for the controlled "
            "cleanup run only."
        )


def preview_cleanup() -> dict:
    """Read-only evidence of the exact metadata targeted by execute()."""

    old_exists = bool(frappe.db.exists("DocType", LEGACY_DOCTYPE))
    return {
        "legacy_doctype": LEGACY_DOCTYPE,
        "legacy_doctype_exists": old_exists,
        "workspace_links": frappe.db.count(
            "Workspace Link",
            filters={"link_to": LEGACY_DOCTYPE},
        ),
        "docperms": frappe.db.count(
            "DocPerm",
            filters={"parent": LEGACY_DOCTYPE},
        ),
        "custom_docperms": frappe.db.count(
            "Custom DocPerm",
            filters={"parent": LEGACY_DOCTYPE},
        ),
        "single_rows": frappe.db.count(
            "Singles",
            filters={"doctype": LEGACY_DOCTYPE},
        ),
        "v2_profiles": _profile_rows(),
        "read_only": True,
        "database_write": False,
        "fbr_network_call": False,
        "registered_in_patches_txt": False,
    }


def execute() -> None:
    """Delete only retired singleton metadata after explicit backup authorization."""

    _assert_authorized()
    _assert_safe_v2_state()

    if not frappe.db.exists("DocType", LEGACY_DOCTYPE):
        return

    # Remove external metadata references first. frappe.delete_doc then removes
    # the DocType definition/children using Frappe's own deletion semantics.
    frappe.db.delete("Workspace Link", {"link_to": LEGACY_DOCTYPE})
    frappe.db.delete("Custom DocPerm", {"parent": LEGACY_DOCTYPE})
    frappe.db.delete("DocPerm", {"parent": LEGACY_DOCTYPE})
    frappe.db.delete("Singles", {"doctype": LEGACY_DOCTYPE})

    frappe.delete_doc(
        "DocType",
        LEGACY_DOCTYPE,
        force=True,
        ignore_permissions=True,
        for_reload=True,
    )

    frappe.clear_cache(doctype=LEGACY_DOCTYPE)
