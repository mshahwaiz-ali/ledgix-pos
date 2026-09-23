from __future__ import annotations

"""Transitional tax-authority boundary for the FBR/ERPNext-native redesign.

The final product must use ERPNext as the only monetary tax authority. During
the controlled cutover we keep one narrow compatibility switch so existing
sites can remain on the proven legacy bridge until the native path is exercised
against the local integration dataset.

This module is intentionally the *only* transaction-layer place that may call
the old Ledgix tax foundation. Once the native runtime gate passes, the legacy
branch and the site-config switch are removed.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

NATIVE_TAX_SITE_CONFIG_KEY = "ledgix_erpnext_native_tax_authority"
LEGACY_MANAGED_TAX_PREFIX = "[LEDGIX-TAX]"
NOT_APPLICABLE_TAX = "N/A"


def native_tax_authority_enabled() -> bool:
    """Return the temporary internal cutover flag.

    This is an engineering migration switch, not client tax configuration.
    Normal business tax/FBR configuration remains Desk-driven.
    """

    try:
        return bool(cint((frappe.conf or {}).get(NATIVE_TAX_SITE_CONFIG_KEY)))
    except Exception:
        return False


def current_tax_authority() -> str:
    return "ERPNext Native" if native_tax_authority_enabled() else "Legacy Bridge"


def _parse_item_tax_rate(value) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return dict(parsed or {}) if isinstance(parsed, dict) else {}


def _account_state(account: str | None) -> dict:
    account = str(account or "").strip()
    if not account:
        return {}
    row = frappe.db.get_value(
        "Account",
        account,
        ["name", "company", "is_group", "disabled"],
        as_dict=True,
    )
    return dict(row or {})


def _template_state(template: str | None) -> dict:
    template = str(template or "").strip()
    if not template:
        return {}
    row = frappe.db.get_value(
        "Sales Taxes and Charges Template",
        template,
        ["name", "company", "disabled", "tax_category"],
        as_dict=True,
    )
    return dict(row or {})


def _item_template_state(template: str | None) -> dict:
    template = str(template or "").strip()
    if not template:
        return {}
    row = frappe.db.get_value(
        "Item Tax Template",
        template,
        ["name", "company", "disabled"],
        as_dict=True,
    )
    return dict(row or {})


def evaluate_native_tax_contract(doc) -> dict:
    """Inspect an unsaved/saved ERPNext sales document without changing tax rows."""

    errors: list[str] = []
    warnings: list[str] = []

    if not doc or doc.doctype not in {"Sales Invoice", "POS Invoice"}:
        return {
            "valid": False,
            "errors": ["Native tax contract requires Sales Invoice or POS Invoice."],
            "warnings": [],
            "authority": "ERPNext Native",
        }

    company = str(doc.get("company") or "").strip()
    if not company or not frappe.db.exists("Company", company):
        errors.append("A valid ERPNext Company is required for native tax authority.")

    invoice_tax_accounts = set()
    legacy_rows = []
    for row in doc.get("taxes") or []:
        description = str(row.get("description") or "")
        if description.startswith(LEGACY_MANAGED_TAX_PREFIX):
            legacy_rows.append(row.idx or len(legacy_rows) + 1)

        account = str(row.get("account_head") or "").strip()
        if not account:
            errors.append(f"Tax row {row.idx or '?'} has no Account Head.")
            continue

        state = _account_state(account)
        if not state:
            errors.append(f"Tax row {row.idx or '?'} references missing Account {account}.")
            continue
        if company and state.get("company") != company:
            errors.append(
                f"Tax row {row.idx or '?'} Account {account} belongs to another Company."
            )
        if cint(state.get("is_group")):
            errors.append(f"Tax row {row.idx or '?'} Account {account} is a group account.")
        if cint(state.get("disabled")):
            errors.append(f"Tax row {row.idx or '?'} Account {account} is disabled.")
        invoice_tax_accounts.add(account)

    if legacy_rows:
        errors.append(
            "Native tax authority cannot run with legacy [LEDGIX-TAX] managed rows "
            f"(rows: {', '.join(str(value) for value in legacy_rows)})."
        )

    master = str(doc.get("taxes_and_charges") or "").strip()
    if master:
        state = _template_state(master)
        if not state:
            errors.append(f"Sales Taxes and Charges Template {master} does not exist.")
        else:
            if company and state.get("company") != company:
                errors.append(
                    f"Sales Taxes and Charges Template {master} belongs to another Company."
                )
            if cint(state.get("disabled")):
                errors.append(f"Sales Taxes and Charges Template {master} is disabled.")

    positive_item_tax_accounts = set()
    item_templates = set()

    for item in doc.get("items") or []:
        template = str(item.get("item_tax_template") or "").strip()
        if template:
            item_templates.add(template)
            state = _item_template_state(template)
            if not state:
                errors.append(
                    f"Row {item.idx or '?'} Item Tax Template {template} does not exist."
                )
            else:
                if company and state.get("company") != company:
                    errors.append(
                        f"Row {item.idx or '?'} Item Tax Template {template} belongs to another Company."
                    )
                if cint(state.get("disabled")):
                    errors.append(
                        f"Row {item.idx or '?'} Item Tax Template {template} is disabled."
                    )

        tax_map = _parse_item_tax_rate(item.get("item_tax_rate"))
        if template and not tax_map:
            warnings.append(
                f"Row {item.idx or '?'} has Item Tax Template {template} but no item_tax_rate map."
            )

        for account, rate in tax_map.items():
            account = str(account or "").strip()
            if not account:
                continue

            state = _account_state(account)
            if not state:
                errors.append(
                    f"Row {item.idx or '?'} item tax map references missing Account {account}."
                )
                continue
            if company and state.get("company") != company:
                errors.append(
                    f"Row {item.idx or '?'} item tax Account {account} belongs to another Company."
                )

            if rate == NOT_APPLICABLE_TAX:
                continue

            numeric_rate = flt(rate)
            if abs(numeric_rate) > 0.000001:
                positive_item_tax_accounts.add(account)

    missing_tax_rows = sorted(positive_item_tax_accounts - invoice_tax_accounts)
    if missing_tax_rows:
        errors.append(
            "Positive Item Tax Template accounts are not represented in invoice taxes: "
            + ", ".join(missing_tax_rows)
            + ". Configure the native Sales Taxes and Charges Template / Accounts Settings correctly."
        )

    if not master and not invoice_tax_accounts and not item_templates:
        warnings.append(
            "No native sales tax template or Item Tax Template is resolved. "
            "This is valid only when the invoice is intentionally non-taxable/exempt."
        )

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "authority": "ERPNext Native",
        "company": company,
        "tax_category": str(doc.get("tax_category") or ""),
        "taxes_and_charges": master,
        "invoice_tax_accounts": sorted(invoice_tax_accounts),
        "item_tax_templates": sorted(item_templates),
        "positive_item_tax_accounts": sorted(positive_item_tax_accounts),
    }


def assert_native_tax_contract(doc) -> dict:
    result = evaluate_native_tax_contract(doc)
    if not result.get("valid"):
        frappe.throw(
            _("ERPNext native tax configuration is not ready:\n- {0}").format(
                "\n- ".join(result.get("errors") or [])
            )
        )
    return result


def prepare_native_tax_state(doc) -> None:
    """Let ERPNext resolve any missing native tax rows before calculation.

    Ledgix does not construct monetary tax rows here. ERPNext's own
    set_missing_values() has already resolved party/POS/item context; this step
    invokes the standard server-side tax population hook used during validation
    so Accounts Settings, Sales Taxes and Charges Templates and Item Tax
    Templates can populate their native rows before totals are calculated.

    Existing mapped return rows are left intact because callers use
    recalculate=False for those lifecycle paths.
    """

    if not doc or doc.doctype not in {"Sales Invoice", "POS Invoice"}:
        frappe.throw(_("ERPNext native tax preparation requires Sales Invoice or POS Invoice."))

    doc.run_method("set_taxes_and_charges")


def apply_sales_tax_authority(
    doc,
    *,
    replace_managed_rows: bool = True,
    recalculate: bool = True,
) -> dict:
    """Apply the currently selected transitional tax authority.

    Legacy mode preserves the pre-redesign behavior.
    Native mode never creates Ledgix tax rows; ERPNext's own set_missing_values,
    Tax Rule, POS Profile, Sales Taxes and Charges Template and Item Tax Template
    outputs must already be present on the document.
    """

    if native_tax_authority_enabled():
        if recalculate:
            prepare_native_tax_state(doc)
            doc.run_method("calculate_taxes_and_totals")
        contract = assert_native_tax_contract(doc)
        return {
            "authority": "ERPNext Native",
            "contract": contract,
        }

    # Transitional fallback only. Remove after the Phase 1 native runtime gate.
    from ledgix_saas.setup import erpnext_tax_foundation

    plan = erpnext_tax_foundation.apply_tax_plan(
        doc,
        replace_managed_rows=replace_managed_rows,
    )
    if recalculate:
        doc.run_method("calculate_taxes_and_totals")
    return {
        "authority": "Legacy Bridge",
        "plan": plan,
    }
