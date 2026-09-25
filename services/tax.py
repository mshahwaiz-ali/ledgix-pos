from __future__ import annotations

from ledgix_saas.api import legacy_tax_guard


def apply_sale_tax_snapshot(doc):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="apply_sale_tax_snapshot",
        source_doctype=getattr(doc, "doctype", None),
        source_name=getattr(doc, "name", None),
    )
