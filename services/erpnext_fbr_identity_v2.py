from __future__ import annotations

"""ERPNext-authoritative legal identity resolver for FBR V2.

No FBR network requests and no database writes occur here. Seller identity is
resolved from ERPNext Company + Company Address. Buyer identity is resolved
from ERPNext Customer + billing/primary Address, with only the genuinely
FBR-specific registration-type extension retained.
"""

import frappe
from frappe.utils import cint

from frappe.contacts.doctype.address.address import (
    get_company_address,
    get_default_address,
)


SUPPORTED_DOCTYPES = {"Sales Invoice", "POS Invoice"}
BUYER_REGISTRATION_TYPES = {"Registered", "Unregistered"}


def _text(value) -> str:
    return str(value or "").strip()


def _address_name_for_company(doc) -> str:
    explicit = _text(doc.get("company_address"))
    if explicit and frappe.db.exists("Address", explicit):
        return explicit

    resolved = get_company_address(doc.get("company")) or {}
    candidate = _text(resolved.get("company_address"))
    return candidate if candidate and frappe.db.exists("Address", candidate) else ""


def _address_name_for_customer(doc, customer) -> str:
    explicit = _text(doc.get("customer_address"))
    if explicit and frappe.db.exists("Address", explicit):
        return explicit

    primary = _text(customer.get("customer_primary_address"))
    if primary and frappe.db.exists("Address", primary):
        return primary

    candidate = _text(get_default_address("Customer", customer.name))
    return candidate if candidate and frappe.db.exists("Address", candidate) else ""


def _address_values(address_name: str) -> dict:
    if not address_name:
        return {
            "name": "",
            "address": "",
            "province": "",
            "city": "",
            "country": "",
        }

    address = frappe.get_cached_doc("Address", address_name)
    parts = []
    for fieldname in ("address_line1", "address_line2", "city", "state", "country"):
        value = _text(address.get(fieldname))
        if value and value not in parts:
            parts.append(value)

    return {
        "name": address.name,
        "address": ", ".join(parts),
        "province": _text(address.get("state")),
        "city": _text(address.get("city")),
        "country": _text(address.get("country")),
    }


def _buyer_registration_type(customer) -> str:
    value = _text(customer.get("custom_ledgix_buyer_registration_type"))
    return value if value in BUYER_REGISTRATION_TYPES else ""


def resolve_invoice_identity(doc) -> dict:
    """Resolve seller/buyer identity without mutating the invoice."""

    if not doc or doc.doctype not in SUPPORTED_DOCTYPES:
        frappe.throw("FBR V2 identity resolution requires Sales Invoice or POS Invoice.")

    errors: list[str] = []
    warnings: list[str] = []

    company_name = _text(doc.get("company"))
    if not company_name or not frappe.db.exists("Company", company_name):
        frappe.throw("Invoice has no valid ERPNext Company.")
    company = frappe.get_cached_doc("Company", company_name)

    seller_address = _address_values(_address_name_for_company(doc))
    seller = {
        "ntn_cnic": _text(company.get("tax_id")),
        "business_name": _text(company.get("company_name") or company.name),
        "province": seller_address["province"],
        "address": seller_address["address"],
        "address_name": seller_address["name"],
        "tax_id_source": "Company.tax_id",
        "business_name_source": "Company.company_name",
        "province_source": "Address.state",
        "address_source": "Address",
    }

    if not seller["ntn_cnic"]:
        errors.append("ERPNext Company Tax ID is required for FBR seller NTN/CNIC.")
    if not seller["business_name"]:
        errors.append("ERPNext Company Name is required for FBR seller business name.")
    if not seller["address_name"]:
        errors.append("ERPNext Company requires a linked/default Address for FBR.")
    if not seller["province"]:
        errors.append("ERPNext Company Address State/Province is required for FBR.")
    if not seller["address"]:
        errors.append("ERPNext Company Address is required for FBR.")

    customer_name = _text(doc.get("customer"))
    if not customer_name or not frappe.db.exists("Customer", customer_name):
        frappe.throw("Invoice has no valid ERPNext Customer.")
    customer = frappe.get_cached_doc("Customer", customer_name)

    buyer_address = _address_values(_address_name_for_customer(doc, customer))
    native_tax_id = _text(customer.get("tax_id"))
    legacy_tax_id = _text(customer.get("custom_ledgix_buyer_ntn_cnic"))
    registration_type = _buyer_registration_type(customer)

    if native_tax_id and legacy_tax_id and native_tax_id != legacy_tax_id:
        errors.append(
            "ERPNext Customer Tax ID conflicts with legacy Ledgix Buyer NTN/CNIC. "
            "Resolve the master-data conflict before FBR V2 cutover."
        )

    legacy_province = _text(customer.get("custom_ledgix_buyer_province"))
    legacy_address = _text(customer.get("custom_ledgix_buyer_fbr_address"))
    if legacy_province and buyer_address["province"] and legacy_province != buyer_address["province"]:
        warnings.append(
            "Legacy Buyer Province differs from ERPNext Address State/Province; "
            "V2 uses the ERPNext Address authority."
        )
    if legacy_address and buyer_address["address"] and legacy_address != buyer_address["address"]:
        warnings.append(
            "Legacy Buyer FBR Address differs from ERPNext Address; "
            "V2 uses the ERPNext Address authority."
        )

    buyer = {
        "ntn_cnic": native_tax_id or legacy_tax_id,
        "business_name": _text(customer.get("customer_name") or customer.name),
        "province": buyer_address["province"],
        "address": buyer_address["address"],
        "address_name": buyer_address["name"],
        "registration_type": registration_type,
        "tax_id_source": (
            "Customer.tax_id"
            if native_tax_id
            else (
                "Customer.custom_ledgix_buyer_ntn_cnic (transition fallback)"
                if legacy_tax_id
                else ""
            )
        ),
        "business_name_source": "Customer.customer_name",
        "province_source": "Address.state",
        "address_source": "Address",
        "registration_type_source": "Customer.custom_ledgix_buyer_registration_type",
    }

    if not buyer["business_name"]:
        errors.append("ERPNext Customer Name is required for FBR buyer business name.")
    if not buyer["address_name"]:
        errors.append("ERPNext Customer requires a billing/primary Address for FBR.")
    if not buyer["province"]:
        errors.append("ERPNext Customer Address State/Province is required for FBR.")
    if not buyer["address"]:
        errors.append("ERPNext Customer Address is required for FBR.")
    if not registration_type:
        errors.append(
            "Buyer Registration Type must be explicitly Registered or Unregistered."
        )
    if registration_type == "Registered" and not buyer["ntn_cnic"]:
        errors.append("Registered FBR buyer requires ERPNext Customer Tax ID.")

    if not native_tax_id and legacy_tax_id:
        warnings.append(
            "Buyer NTN/CNIC is using the legacy Ledgix transition fallback. "
            "Move it to ERPNext Customer Tax ID before final V2 cutover."
        )

    return {
        "authority": "ERPNext",
        "source_doctype": doc.doctype,
        "source_name": doc.name or "",
        "seller": seller,
        "buyer": buyer,
        "errors": errors,
        "warnings": warnings,
        "ready": not errors,
        "database_write": False,
        "fbr_network_call": False,
    }


def build_identity_candidate(reference_doctype: str, reference_name: str) -> dict:
    reference_doctype = _text(reference_doctype)
    reference_name = _text(reference_name)
    if reference_doctype not in SUPPORTED_DOCTYPES:
        frappe.throw("reference_doctype must be Sales Invoice or POS Invoice.")
    if not reference_name or not frappe.db.exists(reference_doctype, reference_name):
        frappe.throw("Select an existing ERPNext invoice.")

    doc = frappe.get_doc(reference_doctype, reference_name)
    result = resolve_invoice_identity(doc)
    result["source_docstatus"] = cint(doc.docstatus)
    return result
