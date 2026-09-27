from __future__ import annotations

"""Fail-closed compatibility shell for retired legacy FBR reference RPCs.

The canonical reference-data implementation is ledgix_saas.api.fbr_reference_v2,
which is company/profile scoped and uses the neutral GET-only transport.
This legacy module intentionally performs no network request and reads no legacy
FBR token/settings.
"""

import frappe


LEGACY_REFERENCE_RETIRED_MESSAGE = (
    "Legacy FBR reference APIs are retired. "
    "Use the V2 FBR reference workflow backed by Ledgix FBR Integration Profile."
)


def _retired():
    frappe.throw(LEGACY_REFERENCE_RETIRED_MESSAGE)


@frappe.whitelist()
def get_provinces():
    return _retired()


@frappe.whitelist()
def get_document_types():
    return _retired()


@frappe.whitelist()
def get_transaction_types():
    return _retired()


@frappe.whitelist()
def get_uoms():
    return _retired()


@frappe.whitelist()
def get_rates(posting_date=None, transaction_type_id=None, origination_supplier=None):
    return _retired()


@frappe.whitelist()
def get_hs_uoms(hs_code=None, annexure_id=3):
    return _retired()


@frappe.whitelist()
def get_sro_schedules(
    rate_id=None,
    posting_date=None,
    origination_supplier_csv=None,
):
    return _retired()


@frappe.whitelist()
def get_sro_items(posting_date=None, sro_id=None):
    return _retired()


@frappe.whitelist()
def get_sales_tax_registration_status(registration_no=None, posting_date=None):
    return _retired()


@frappe.whitelist()
def get_registration_type(registration_no=None):
    return _retired()
