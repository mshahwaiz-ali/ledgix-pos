"""Retired Ledgix V2 runtime. Historical implementation remains in Git history.

Only compatibility rejection is executable; never reads credentials or fiscal state.
"""
import frappe
from ledgix_saas.api.fbr_legacy_guard import reject_legacy_v2_action

PROVINCES_URL = "https://gw.fbr.gov.pk/pdi/v1/provinces"
DOCUMENT_TYPES_URL = "https://gw.fbr.gov.pk/pdi/v1/doctypecode"
TRANSACTION_TYPES_URL = "https://gw.fbr.gov.pk/pdi/v1/transtypecode"
UOM_URL = "https://gw.fbr.gov.pk/pdi/v1/uom"
ITEM_CODE_URL = "https://gw.fbr.gov.pk/pdi/v1/itemdesccode"
SRO_ITEM_CODE_URL = "https://gw.fbr.gov.pk/pdi/v1/sroitemcode"
SRO_SCHEDULE_URL = "https://gw.fbr.gov.pk/pdi/v1/SroSchedule"
RATE_URL = "https://gw.fbr.gov.pk/pdi/v2/SaleTypeToRate"
HS_UOM_URL = "https://gw.fbr.gov.pk/pdi/v2/HS_UOM"
SRO_ITEM_URL = "https://gw.fbr.gov.pk/pdi/v2/SROItem"
STATL_URL = "https://gw.fbr.gov.pk/dist/v1/statl"
REGISTRATION_TYPE_URL = "https://gw.fbr.gov.pk/dist/v1/Get_Reg_Type"
PROFILE_DOCTYPE = "Ledgix FBR Integration Profile"
REFERENCE_DOCTYPE = "Ledgix FBR Reference Data"
DEFAULT_PROTOCOL_VERSION = "DI API V1.12"
GLOBAL_CONTEXT_KEY = "GLOBAL"
FBR_VIEW_ROLES = {"System Manager", "Ledgix Admin", "Ledgix Manager"}
FBR_ADMIN_ROLES = {"System Manager", "Ledgix Admin"}
CORE_STATIC_REFERENCE_TYPES = ("Province", "Document Type", "Transaction Type", "UOM")


def _assert_view_permission(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _assert_admin_permission(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _safe_error(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _required_text(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _profile(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _profile_token(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _reference_get(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _casefold_row(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _value(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _normalize_rows(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _canonical_context(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _protocol_version(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _context_existing_names(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _existing_reference_name(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _upsert_family(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _sync_reference(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def sync_reference_family_internal(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _sync_parameterized(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def sync_reference_family(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def sync_core_reference_data(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def sync_rates(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def sync_hs_uoms(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def sync_sro_schedules(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def sync_sro_items(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


def _cached_rows(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def lookup_sales_tax_registration_status(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def lookup_registration_type(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def get_cached_reference_data(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)


@frappe.whitelist()
def get_cached_contextual_reference_data(*args, **kwargs):
    return reject_legacy_v2_action(*args, **kwargs)
