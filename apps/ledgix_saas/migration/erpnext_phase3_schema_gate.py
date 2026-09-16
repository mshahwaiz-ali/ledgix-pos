from __future__ import annotations

import json

import frappe
from frappe.utils import cint, nowdate

from ledgix_saas.migration.erpnext_integration_bootstrap import CURRENCY, INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.setup import erpnext_extensions as extensions

TEST_CUSTOMER = "Ledgix Phase 3 Customer"
TEST_ITEM = "LEDGIX-PHASE3-SCHEMA"
TEST_TAX_CATEGORY = "Phase 3 Schema Tax"
TEST_INVOICE_MARKER = "LEDGIX-ERPNEXT-PHASE3-SCHEMA-V1"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 3 schema gate on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing; run the integration bootstrap first.")


def _field_contracts() -> tuple[dict, list[str]]:
    evidence = {}
    errors = []
    for doctype, definitions in extensions.CUSTOM_FIELDS.items():
        meta = frappe.get_meta(doctype, cached=False)
        doctype_evidence = {}
        for definition in definitions:
            fieldname = definition["fieldname"]
            field = meta.get_field(fieldname)
            field_result = {
                "exists": bool(field),
                "fieldtype": field.fieldtype if field else None,
                "options": field.options if field else None,
                "read_only": cint(field.read_only) if field else None,
                "no_copy": cint(field.no_copy) if field else None,
            }
            doctype_evidence[fieldname] = field_result
            if not field:
                errors.append(f"{doctype}.{fieldname} is missing")
                continue
            if field.fieldtype != definition.get("fieldtype"):
                errors.append(
                    f"{doctype}.{fieldname} fieldtype={field.fieldtype!r}, expected {definition.get('fieldtype')!r}"
                )
            expected_options = definition.get("options")
            if expected_options is not None and str(field.options or "") != str(expected_options):
                errors.append(f"{doctype}.{fieldname} options differ from Phase 3 contract")
            if cint(definition.get("read_only")) and not cint(field.read_only):
                errors.append(f"{doctype}.{fieldname} must be read-only")
            if cint(definition.get("no_copy")) and not cint(field.no_copy):
                errors.append(f"{doctype}.{fieldname} must be no-copy")
        evidence[doctype] = doctype_evidence
    return evidence, errors


def _custom_field_uniqueness() -> tuple[dict, list[str]]:
    evidence = {}
    errors = []
    for doctype, definitions in extensions.CUSTOM_FIELDS.items():
        for definition in definitions:
            fieldname = definition["fieldname"]
            count = frappe.db.count("Custom Field", {"dt": doctype, "fieldname": fieldname})
            evidence[f"{doctype}.{fieldname}"] = count
            if count != 1:
                errors.append(f"{doctype}.{fieldname} has {count} Custom Field records; expected exactly 1")
    return evidence, errors


def _permission_contracts() -> tuple[dict, list[str]]:
    evidence = {}
    errors = []
    for doctype, desired_by_role in extensions.ERPNext_ROLE_PERMISSIONS.items():
        if not frappe.db.exists("DocType", doctype):
            errors.append(f"Permission target DocType {doctype} is missing")
            continue
        evidence[doctype] = {}
        for role, desired in desired_by_role.items():
            row = frappe.db.get_value(
                "Custom DocPerm",
                {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
                ["name", *extensions.PERM_KEYS],
                as_dict=True,
            )
            role_result = {"exists": bool(row)}
            evidence[doctype][role] = role_result
            if not row:
                errors.append(f"{doctype} has no Custom DocPerm for {role}")
                continue
            mismatches = {
                key: {"actual": cint(row.get(key)), "expected": cint(desired.get(key, 0))}
                for key in extensions.PERM_KEYS
                if cint(row.get(key)) != cint(desired.get(key, 0))
            }
            role_result["mismatches"] = mismatches
            if mismatches:
                errors.append(f"{doctype} permission mismatch for {role}: {sorted(mismatches)}")
    return evidence, errors


def _ensure_test_item() -> str:
    if frappe.db.exists("Item", TEST_ITEM):
        item = frappe.get_doc("Item", TEST_ITEM)
        if cint(item.is_stock_item):
            frappe.throw(f"Safety check failed: {TEST_ITEM} must remain a non-stock Phase 3 test item.")
        return item.name

    item = frappe.get_doc(
        {
            "doctype": "Item",
            "item_code": TEST_ITEM,
            "item_name": "Ledgix Phase 3 Schema Item",
            "description": "Dedicated non-stock Item for ERPNext extension schema proof",
            "item_group": "Services",
            "stock_uom": "Nos",
            "is_stock_item": 0,
        }
    )
    item.insert(ignore_permissions=True)
    return item.name


def _customer_group() -> str:
    value = frappe.db.get_value("Customer Group", {"is_group": 0}, "name", order_by="name asc")
    if not value:
        frappe.throw("No leaf Customer Group exists for Phase 3 schema test.")
    return value


def _territory() -> str:
    value = frappe.db.get_value("Territory", {"is_group": 0}, "name", order_by="name asc")
    if not value:
        frappe.throw("No leaf Territory exists for Phase 3 schema test.")
    return value


def _ensure_test_customer() -> str:
    name = frappe.db.get_value("Customer", {"customer_name": TEST_CUSTOMER}, "name")
    if name:
        customer = frappe.get_doc("Customer", name)
    else:
        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": TEST_CUSTOMER,
                "customer_type": "Individual",
                "customer_group": _customer_group(),
                "territory": _territory(),
            }
        )
        customer.insert(ignore_permissions=True)

    customer.custom_ledgix_buyer_registration_type = "Registered"
    customer.custom_ledgix_buyer_ntn_cnic = "1234567-8"
    customer.custom_ledgix_buyer_strn = "P3-STRN-001"
    customer.custom_ledgix_buyer_province = "Sindh"
    customer.custom_ledgix_buyer_fbr_address = "Phase 3 Integration Address"
    customer.custom_ledgix_fbr_verification_status = "Verified"
    customer.custom_ledgix_last_fbr_verification_date = nowdate()
    customer.save(ignore_permissions=True)
    return customer.name


def _ensure_tax_category() -> str:
    if frappe.db.exists("Ledgix Tax Category", TEST_TAX_CATEGORY):
        return TEST_TAX_CATEGORY
    doc = frappe.get_doc(
        {
            "doctype": "Ledgix Tax Category",
            "category_name": TEST_TAX_CATEGORY,
            "tax_type": "Sales Tax",
            "default_rate": 18,
            "active": 1,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_item_profile(item_code: str) -> str:
    name = frappe.db.get_value(
        "Ledgix Item Tax Profile",
        {"erpnext_item": item_code, "active": 1},
        "name",
    )
    if name:
        return name
    doc = frappe.get_doc(
        {
            "doctype": "Ledgix Item Tax Profile",
            "erpnext_item": item_code,
            "tax_category": _ensure_tax_category(),
            "taxable": 1,
            "active": 1,
            "needs_review": 0,
            "tax_basis": "Transaction Value",
            "hs_code": "0101.21",
            "uom_for_fbr": "Numbers",
            "sales_type": "Goods at standard rate",
            "fbr_rate_description": "18%",
            "scenario_id": "SN000",
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _snapshot_payload(customer: str, item_code: str, profile: str) -> dict:
    return {
        "version": 1,
        "customer": customer,
        "item": item_code,
        "item_profile": profile,
        "buyer": {
            "registration_type": "Registered",
            "ntn_cnic": "1234567-8",
            "province": "Sindh",
        },
    }


def _ensure_snapshot_invoice(customer: str, item_code: str, profile: str):
    name = frappe.db.get_value(
        "Sales Invoice",
        {"company": TEST_COMPANY, "remarks": TEST_INVOICE_MARKER, "docstatus": 0},
        "name",
    )
    snapshot = _snapshot_payload(customer, item_code, profile)
    header_snapshot = json.dumps(snapshot, sort_keys=True)
    line_snapshot = json.dumps({**snapshot, "line": 1}, sort_keys=True)

    if name:
        invoice = frappe.get_doc("Sales Invoice", name)
        invoice.set("items", [])
    else:
        invoice = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "company": TEST_COMPANY,
                "customer": customer,
                "posting_date": nowdate(),
                "currency": CURRENCY,
                "selling_price_list": "Standard Selling",
                "remarks": TEST_INVOICE_MARKER,
            }
        )

    invoice.custom_ledgix_fbr_status = "Ready"
    invoice.custom_ledgix_client_sale_id = "P3-SCHEMA-CLIENT-001"
    invoice.custom_ledgix_fbr_snapshot_version = 1
    invoice.custom_ledgix_fbr_snapshot_json = header_snapshot
    invoice.append(
        "items",
        {
            "item_code": item_code,
            "qty": 1,
            "uom": "Nos",
            "rate": 100,
            "custom_ledgix_fbr_item_profile": profile,
            "custom_ledgix_fbr_hs_code": "0101.21",
            "custom_ledgix_fbr_uom": "Numbers",
            "custom_ledgix_fbr_sales_type": "Goods at standard rate",
            "custom_ledgix_fbr_rate_description": "18%",
            "custom_ledgix_fbr_scenario_id": "SN000",
            "custom_ledgix_fbr_tax_basis": "Transaction Value",
            "custom_ledgix_fbr_notified_retail_price": 0,
            "custom_ledgix_fbr_sales_tax_withheld": 5,
            "custom_ledgix_fbr_extra_tax": 10,
            "custom_ledgix_fbr_further_tax": 15,
            "custom_ledgix_fbr_fed_payable": 20,
            "custom_ledgix_fbr_snapshot_version": 1,
            "custom_ledgix_fbr_snapshot_json": line_snapshot,
        },
    )
    invoice.set_missing_values()
    if invoice.is_new():
        invoice.insert(ignore_permissions=True)
    else:
        invoice.save(ignore_permissions=True)
    invoice.reload()
    return invoice, header_snapshot, line_snapshot


def _business_profile_contract() -> tuple[dict, list[str]]:
    errors = []
    meta = frappe.get_meta("Ledgix Business Profile", cached=False)
    evidence = {
        "exists": bool(frappe.db.exists("DocType", "Ledgix Business Profile")),
        "is_single": bool(meta.issingle),
        "profiles": list(extensions.PROFILE_DEFAULTS),
    }
    if not meta.issingle:
        errors.append("Ledgix Business Profile must be a Single DocType")

    doc = frappe.get_single("Ledgix Business Profile")
    original = {"business_profile": doc.business_profile, "use_profile_defaults": doc.use_profile_defaults}
    original.update({fieldname: doc.get(fieldname) for fieldname in extensions.FEATURE_FIELDS})
    profile_results = {}
    try:
        for profile in ("Invoice + FBR Only", "Mixed"):
            doc.business_profile = profile
            doc.use_profile_defaults = 1
            doc.save(ignore_permissions=True)
            doc.reload()
            actual = {fieldname: cint(doc.get(fieldname)) for fieldname in extensions.FEATURE_FIELDS}
            expected = extensions.PROFILE_DEFAULTS[profile]
            profile_results[profile] = {"actual": actual, "expected": expected, "matches": actual == expected}
            if actual != expected:
                errors.append(f"Business Profile defaults did not resolve for {profile}")
    finally:
        doc.business_profile = original["business_profile"] or extensions.DEFAULT_BUSINESS_PROFILE
        doc.use_profile_defaults = original["use_profile_defaults"] if original["use_profile_defaults"] is not None else 1
        if cint(doc.use_profile_defaults):
            extensions.apply_business_profile_defaults(doc)
        else:
            for fieldname in extensions.FEATURE_FIELDS:
                doc.set(fieldname, original[fieldname])
        doc.save(ignore_permissions=True)

    evidence["profile_results"] = profile_results
    return evidence, errors


def run() -> dict:
    """Prove the complete Phase 3 target schema on the isolated integration site."""

    _assert_safe_site()
    frappe.set_user("Administrator")

    first_sync = extensions.sync_all()
    second_sync = extensions.sync_all()

    field_evidence, field_errors = _field_contracts()
    uniqueness_evidence, uniqueness_errors = _custom_field_uniqueness()
    permission_evidence, permission_errors = _permission_contracts()
    business_profile_evidence, business_profile_errors = _business_profile_contract()

    item_meta = frappe.get_meta("Ledgix Item Tax Profile", cached=False)
    erpnext_item_field = item_meta.get_field("erpnext_item")
    legacy_item_field = item_meta.get_field("item")
    item_profile_schema = {
        "erpnext_item_exists": bool(erpnext_item_field),
        "erpnext_item_options": erpnext_item_field.options if erpnext_item_field else None,
        "legacy_item_retained": bool(legacy_item_field),
        "legacy_item_required": cint(legacy_item_field.reqd) if legacy_item_field else None,
    }
    item_profile_errors = []
    if not erpnext_item_field or erpnext_item_field.options != "Item":
        item_profile_errors.append("Ledgix Item Tax Profile.erpnext_item must link to ERPNext Item")
    if not legacy_item_field:
        item_profile_errors.append("Legacy Ledgix Item compatibility field was removed too early")
    elif cint(legacy_item_field.reqd):
        item_profile_errors.append("Legacy Ledgix Item compatibility field must not remain mandatory")

    item_code = _ensure_test_item()
    customer = _ensure_test_customer()
    item_profile = _ensure_item_profile(item_code)
    invoice, header_snapshot, line_snapshot = _ensure_snapshot_invoice(customer, item_code, item_profile)
    customer_doc = frappe.get_doc("Customer", customer)
    profile_doc = frappe.get_doc("Ledgix Item Tax Profile", item_profile)
    line = invoice.items[0]

    persistence = {
        "customer": {
            "name": customer,
            "buyer_registration_type": customer_doc.custom_ledgix_buyer_registration_type,
            "buyer_ntn_cnic": customer_doc.custom_ledgix_buyer_ntn_cnic,
            "buyer_province": customer_doc.custom_ledgix_buyer_province,
        },
        "item_profile": {
            "name": item_profile,
            "erpnext_item": profile_doc.erpnext_item,
            "legacy_item": profile_doc.item,
            "hs_code": profile_doc.hs_code,
        },
        "sales_invoice": {
            "name": invoice.name,
            "docstatus": invoice.docstatus,
            "fbr_status": invoice.custom_ledgix_fbr_status,
            "client_sale_id": invoice.custom_ledgix_client_sale_id,
            "snapshot_version": cint(invoice.custom_ledgix_fbr_snapshot_version),
            "snapshot_json_matches": invoice.custom_ledgix_fbr_snapshot_json == header_snapshot,
        },
        "sales_invoice_item": {
            "item_code": line.item_code,
            "item_profile": line.custom_ledgix_fbr_item_profile,
            "hs_code": line.custom_ledgix_fbr_hs_code,
            "tax_basis": line.custom_ledgix_fbr_tax_basis,
            "sales_tax_withheld": float(line.custom_ledgix_fbr_sales_tax_withheld or 0),
            "extra_tax": float(line.custom_ledgix_fbr_extra_tax or 0),
            "further_tax": float(line.custom_ledgix_fbr_further_tax or 0),
            "fed_payable": float(line.custom_ledgix_fbr_fed_payable or 0),
            "snapshot_json_matches": line.custom_ledgix_fbr_snapshot_json == line_snapshot,
        },
    }

    persistence_checks = {
        "customer_fbr_fields_persist": (
            persistence["customer"]["buyer_registration_type"] == "Registered"
            and persistence["customer"]["buyer_ntn_cnic"] == "1234567-8"
            and persistence["customer"]["buyer_province"] == "Sindh"
        ),
        "item_profile_targets_erpnext_item": persistence["item_profile"]["erpnext_item"] == item_code,
        "item_profile_does_not_require_legacy_item": not bool(persistence["item_profile"]["legacy_item"]),
        "invoice_fbr_header_persists": (
            persistence["sales_invoice"]["fbr_status"] == "Ready"
            and persistence["sales_invoice"]["client_sale_id"] == "P3-SCHEMA-CLIENT-001"
            and persistence["sales_invoice"]["snapshot_version"] == 1
            and persistence["sales_invoice"]["snapshot_json_matches"]
        ),
        "invoice_line_snapshot_persists": (
            persistence["sales_invoice_item"]["item_profile"] == item_profile
            and persistence["sales_invoice_item"]["hs_code"] == "0101.21"
            and persistence["sales_invoice_item"]["tax_basis"] == "Transaction Value"
            and persistence["sales_invoice_item"]["snapshot_json_matches"]
        ),
        "special_tax_snapshot_amounts_persist": (
            persistence["sales_invoice_item"]["sales_tax_withheld"] == 5
            and persistence["sales_invoice_item"]["extra_tax"] == 10
            and persistence["sales_invoice_item"]["further_tax"] == 15
            and persistence["sales_invoice_item"]["fed_payable"] == 20
        ),
    }

    errors = [
        *field_errors,
        *uniqueness_errors,
        *permission_errors,
        *business_profile_errors,
        *item_profile_errors,
        *[name for name, passed in persistence_checks.items() if not passed],
    ]
    checks = {
        "custom_field_contracts": not field_errors,
        "custom_fields_idempotent_unique": not uniqueness_errors,
        "standard_role_permissions_installed": not permission_errors,
        "business_profile_contract": not business_profile_errors,
        "item_tax_profile_relinked_safely": not item_profile_errors,
        **persistence_checks,
    }

    frappe.db.commit()
    return {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "sync": {"first": first_sync, "second": second_sync},
        "custom_fields": field_evidence,
        "custom_field_counts": uniqueness_evidence,
        "role_permissions": permission_evidence,
        "business_profile": business_profile_evidence,
        "item_tax_profile_schema": item_profile_schema,
        "persistence": persistence,
        "checks": checks,
        "errors": errors,
        "legacy_master_authority_cutover_performed": False,
        "phase3_complete": all(checks.values()),
        "phase4_ready": all(checks.values()),
        "next_phase": "Phase 4 — Tax Parity and Accounting Foundation" if all(checks.values()) else None,
        "passed": all(checks.values()),
    }
