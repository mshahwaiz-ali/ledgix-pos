from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint

from ledgix_saas.api import legacy_tax_guard


CUSTOM_FIELD_MODULE = "Ledgix"


def _cf(fieldname: str, fieldtype: str, label: str = "", **values) -> dict:
    row = {
        "fieldname": fieldname,
        "fieldtype": fieldtype,
        "module": CUSTOM_FIELD_MODULE,
    }
    if label:
        row["label"] = label
    row.update(values)
    return row


COMPANY_TAX_FIELDS = [
    _cf(
        "custom_ledgix_tax_accounts_section",
        "Section Break",
        "Ledgix Tax Accounting",
        insert_after="default_income_account",
        collapsible=1,
    ),
    _cf(
        "custom_ledgix_sales_tax_account",
        "Link",
        "Sales Tax Payable Account",
        insert_after="custom_ledgix_tax_accounts_section",
        options="Account",
    ),
    _cf(
        "custom_ledgix_extra_tax_account",
        "Link",
        "Extra Tax Payable Account",
        insert_after="custom_ledgix_sales_tax_account",
        options="Account",
    ),
    _cf(
        "custom_ledgix_further_tax_account",
        "Link",
        "Further Tax Payable Account",
        insert_after="custom_ledgix_extra_tax_account",
        options="Account",
    ),
    _cf(
        "custom_ledgix_fed_account",
        "Link",
        "FED Payable Account",
        insert_after="custom_ledgix_further_tax_account",
        options="Account",
    ),
    _cf(
        "custom_ledgix_tax_accounts_column",
        "Column Break",
        insert_after="custom_ledgix_fed_account",
    ),
    _cf(
        "custom_ledgix_sales_tax_withheld_account",
        "Link",
        "Sales Tax Withheld Account (Reserved)",
        insert_after="custom_ledgix_tax_accounts_column",
        options="Account",
        description=(
            "Reserved for a future legally verified withholding posting model. "
            "Current V2 evidence keeps withheld tax non-posting."
        ),
    ),
]

CUSTOM_FIELDS = {"Company": COMPANY_TAX_FIELDS}

COMPONENT_ACCOUNT_FIELDS = {
    "sales_tax": "custom_ledgix_sales_tax_account",
    "extra_tax": "custom_ledgix_extra_tax_account",
    "further_tax": "custom_ledgix_further_tax_account",
    "fed_payable": "custom_ledgix_fed_account",
    "sales_tax_withheld_at_source": "custom_ledgix_sales_tax_withheld_account",
}

FINANCIAL_COMPONENTS = (
    "sales_tax",
    "extra_tax",
    "further_tax",
    "fed_payable",
)


def sync_custom_fields() -> int:
    if not frappe.db.exists("DocType", "Company"):
        frappe.throw(
            "ERPNext Company DocType is required for Ledgix tax accounting foundation."
        )
    create_custom_fields(CUSTOM_FIELDS, update=True)
    frappe.clear_cache(doctype="Company")
    return len(COMPANY_TAX_FIELDS)


def sync_all() -> dict:
    return {"company_tax_fields_expected": sync_custom_fields()}


def after_migrate() -> None:
    sync_all()


def _account_is_valid(company: str, account: str | None) -> bool:
    if not account:
        return False
    row = frappe.db.get_value(
        "Account",
        account,
        ["company", "is_group", "disabled"],
        as_dict=True,
    )
    return bool(
        row
        and row.company == company
        and not cint(row.is_group)
        and not cint(row.disabled)
    )


def get_company_tax_accounts(
    company: str,
    *,
    require_financial: bool = True,
) -> dict:
    if not frappe.db.exists("Company", company):
        frappe.throw(f"Company {company!r} does not exist.")

    company_doc = frappe.get_cached_doc("Company", company)
    accounts = {
        component: company_doc.get(fieldname) or ""
        for component, fieldname in COMPONENT_ACCOUNT_FIELDS.items()
    }

    invalid = [
        component
        for component in FINANCIAL_COMPONENTS
        if require_financial
        and not _account_is_valid(company, accounts.get(component))
    ]
    if invalid:
        frappe.throw(
            "Ledgix ERPNext tax account mapping is missing/invalid for: "
            + ", ".join(invalid)
        )
    return accounts


def _retired_adapter(action: str):
    return legacy_tax_guard.reject_legacy_tax_action(action=action)


def build_line_snapshot(doc, row, *, price_includes_tax: bool = False):
    _ = doc, row, price_includes_tax
    return _retired_adapter("erpnext_tax_foundation.build_line_snapshot")


def build_tax_plan(doc, *, price_includes_tax: bool = False):
    _ = doc, price_includes_tax
    return _retired_adapter("erpnext_tax_foundation.build_tax_plan")


def apply_tax_plan(
    doc,
    *,
    price_includes_tax: bool = False,
    replace_managed_rows: bool = True,
):
    _ = doc, price_includes_tax, replace_managed_rows
    return _retired_adapter("erpnext_tax_foundation.apply_tax_plan")


def build_fbr_tax_preview(doc):
    _ = doc
    return _retired_adapter("erpnext_tax_foundation.build_fbr_tax_preview")
