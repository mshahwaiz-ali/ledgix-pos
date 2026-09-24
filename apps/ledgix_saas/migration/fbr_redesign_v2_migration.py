from __future__ import annotations

"""Historical compatibility tombstone for the retired FBR V2 migration helper.

The V2 Integration Profile and V2 compliance mappings are already the active
architecture. This module remains temporarily importable only so stale local
operator commands fail closed with an explicit retirement message instead of
silently reviving the legacy singleton migration path.
"""

import frappe


RETIREMENT_CODE = "FBR_V2_LEGACY_MIGRATION_RETIRED"
RETIREMENT_MESSAGE = (
    "Legacy FBR V2 migration is retired. V2 Integration Profile and V2 compliance "
    "mappings are authoritative. This compatibility module must not read, decrypt, "
    "copy, or write legacy settings/item-profile state. Remaining legacy database "
    "metadata is handled only by the dedicated controlled cleanup phase."
)


def _retired() -> None:
    frappe.throw(f"{RETIREMENT_CODE}: {RETIREMENT_MESSAGE}")


def preview_v2_migration(company: str | None = None) -> dict:
    """Fail closed for callers of the historical preview entry point."""

    _retired()


def apply_v2_migration(
    company: str | None = None,
    confirmation: str | None = None,
) -> dict:
    """Fail closed for callers of the historical apply entry point."""

    _retired()
