from __future__ import annotations

import frappe

from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


REQUIRED_FIELDS = {
    "Sales Invoice": [
        "taxes",
        "taxes_and_charges",
        "total_taxes_and_charges",
        "grand_total",
        "base_grand_total",
    ],
    "Sales Invoice Item": [
        "item_tax_template",
        "amount",
        "net_amount",
        "rate",
        "net_rate",
    ],
    "Sales Taxes and Charges": [
        "charge_type",
        "account_head",
        "description",
        "rate",
        "tax_amount",
        "included_in_print_rate",
        "add_deduct_tax",
        "category",
        "item_wise_tax_detail",
    ],
    "Item Tax Template": ["title", "company", "taxes"],
    "Item Tax Template Detail": ["tax_type", "tax_rate"],
}


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing ERPNext tax architecture probe on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )


def _doctype_probe(doctype: str, fields: list[str]) -> dict:
    exists = bool(frappe.db.exists("DocType", doctype))
    if not exists:
        return {"exists": False, "missing_fields": fields}
    meta = frappe.get_meta(doctype)
    return {
        "exists": True,
        "missing_fields": [fieldname for fieldname in fields if not meta.has_field(fieldname)],
    }


def _select_options(doctype: str, fieldname: str) -> list[str]:
    meta = frappe.get_meta(doctype)
    field = meta.get_field(fieldname)
    if not field or not field.options:
        return []
    return [value.strip() for value in str(field.options).splitlines() if value.strip()]


def run() -> dict:
    """Record the native tax primitives needed before the Phase 4 parity matrix.

    This probe makes no accounting changes. It answers only the Phase 2
    architecture question: which tax concepts can use ERPNext financial rows,
    and which Ledgix/FBR concepts still require an extension and explicit parity
    evidence before authority changes.
    """

    _assert_safe_site()

    doctypes = {doctype: _doctype_probe(doctype, fields) for doctype, fields in REQUIRED_FIELDS.items()}
    optional_doctypes = {
        "Tax Category": bool(frappe.db.exists("DocType", "Tax Category")),
        "Tax Withholding Category": bool(frappe.db.exists("DocType", "Tax Withholding Category")),
    }
    charge_types = _select_options("Sales Taxes and Charges", "charge_type")
    add_deduct_options = _select_options("Sales Taxes and Charges", "add_deduct_tax")

    primitive_checks = {
        "required_doctypes_present": all(result["exists"] for result in doctypes.values()),
        "required_fields_present": all(not result["missing_fields"] for result in doctypes.values()),
        "supports_on_net_total": "On Net Total" in charge_types,
        "supports_actual_tax_rows": "Actual" in charge_types,
        "supports_inclusive_tax_flag": frappe.get_meta("Sales Taxes and Charges").has_field(
            "included_in_print_rate"
        ),
        "supports_add_deduct_rows": bool(add_deduct_options),
        "supports_item_tax_template": optional_doctypes["Tax Category"]
        and bool(frappe.db.exists("DocType", "Item Tax Template")),
    }

    decisions = {
        "ordinary_percentage_sales_tax": "USE NATIVE ERPNext tax rows/item tax templates",
        "tax_inclusive_price": "USE NATIVE ERPNext included_in_print_rate behavior; prove totals in Phase 4",
        "zero_rated_and_exempt": "EXTEND NATIVE with Ledgix FBR classification; prove ERPNext zero-tax accounting in Phase 4",
        "further_tax": "USE/EXTEND NATIVE ERPNext financial tax row plus immutable Ledgix FBR metadata",
        "extra_tax": "USE/EXTEND NATIVE ERPNext financial tax row plus immutable Ledgix FBR metadata",
        "fed": "USE/EXTEND NATIVE ERPNext financial tax row plus immutable Ledgix FBR metadata",
        "sales_tax_withheld_at_source": "CUSTOM PARITY REQUIRED in Phase 4; do not map blindly to generic withholding",
        "third_schedule_notified_retail_price": "CUSTOM FBR/tax-basis extension required while ERPNext remains final ledger authority",
        "fbr_hs_uom_sales_type_sro_scenario": "KEEP LEDGIX compliance metadata, relink to ERPNext Item/invoice snapshots",
        "authoritative_grand_total": "ERPNext only after Phase 4 parity passes",
    }

    return {
        "site": frappe.local.site,
        "doctypes": doctypes,
        "optional_doctypes": optional_doctypes,
        "charge_types": charge_types,
        "add_deduct_options": add_deduct_options,
        "primitive_checks": primitive_checks,
        "decisions": decisions,
        "phase4_parity_required": True,
        "passed": all(primitive_checks.values()),
    }
