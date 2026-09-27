from __future__ import annotations

"""Install/migrate synchronization for the standalone FBR V1.2 app.

No FBR network request is made here. These synchronizers only establish
ERPNext custom fields, the Third Schedule charge type, runtime metadata and
native print formats.
"""

from fbr_v12.setup import erpnext_fbr_schema, erpnext_phase9_extensions, print_formats


def sync_all() -> dict:
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
