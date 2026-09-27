from __future__ import annotations

import re

import frappe

from ledgix_saas.api import legacy_tax_guard


HS_CODE_PATTERN = re.compile(r"^[0-9]{2,8}(\.[0-9]{1,8})?$")


def validate_item_tax_profile_hs_code(doc):
    hs_code = str(doc.get("hs_code") or "").strip()
    if hs_code and not HS_CODE_PATTERN.fullmatch(hs_code):
        frappe.throw(
            "HS Code must contain 2-8 digits with an optional numeric decimal suffix."
        )


@frappe.whitelist()
def preview_sale_tax_for_form(
    items=None,
    posting_date=None,
    sale_date=None,
    customer=None,
):
    return legacy_tax_guard.reject_legacy_tax_action(
        action="preview_sale_tax_for_form",
        items=items,
        posting_date=posting_date,
        sale_date=sale_date,
        customer=customer,
    )
