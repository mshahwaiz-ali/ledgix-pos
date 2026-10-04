from __future__ import annotations

"""Install/migrate synchronization for the standalone FBR V1 app.

No FBR network request is made here. These synchronizers only establish
ERPNext custom fields, the Third Schedule charge type, runtime metadata and
native print formats.
"""

import frappe

from fbr_v1.setup import erpnext_fbr_schema, erpnext_phase9_extensions, print_formats


def sync_standard_doctypes() -> None:
    # A fresh install can enter after_install with an in-process module map
    # created before fbr_v1 became visible. Rebuild that map before reload_doc;
    # otherwise Link custom fields can validate before their target DocTypes exist.
    frappe.clear_cache()
    frappe.setup_module_map(include_all_apps=True)

    # Standard schema first: Link custom fields validate their targets immediately.
    # reload_doc synchronizes metadata/schema without replacing business records.
    for name in (
        "ledgix_fbr_legacy_evidence", "ledgix_fbr_pos_device",
        "ledgix_fbr_integration_profile", "ledgix_fbr_item_mapping",
        "ledgix_fbr_tax_component_mapping", "ledgix_fbr_submission_log",
        "ledgix_fbr_fiscal_event_log", "ledgix_fbr_fiscal_closing",
        "ledgix_fbr_correction_request",
    ):
        frappe.reload_doc("fbr_v1", "doctype", name, force=True)


def sync_all() -> dict:
    sync_standard_doctypes()
    schema = erpnext_fbr_schema.sync_all()
    runtime = erpnext_phase9_extensions.sync_all()
    print_formats.sync_native_print_formats()
    return {
        "schema": schema,
        "runtime": runtime,
        "print_formats": True,
        "network_call_made": False,
    }


def after_install() -> None:
    sync_all()


def after_migrate() -> None:
    sync_all()
