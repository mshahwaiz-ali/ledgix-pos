from __future__ import annotations

"""Local-only payment-account provisioning for the retail operating dataset.

The production/native seeder intentionally requires accounting ledgers to
already exist. The local retail acceptance dataset is self-contained, so this
module fills only missing Cash/Bank ledgers without changing existing accounts.
"""

import frappe

from ledgix_saas.setup import erpnext_demo_data as native

_ORIGINAL_FIND_LEAF_ACCOUNT = native._find_leaf_account


def _existing_leaf(company: str, account_type: str, fallback_field: str | None) -> str | None:
    if fallback_field and frappe.get_meta("Company").has_field(fallback_field):
        account = frappe.db.get_value("Company", company, fallback_field)
        if account and frappe.db.exists(
            "Account",
            {"name": account, "company": company, "is_group": 0, "disabled": 0},
        ):
            return account
    return frappe.db.get_value(
        "Account",
        {"company": company, "account_type": account_type, "is_group": 0, "disabled": 0},
        "name",
        order_by="name asc",
    )


def _asset_parent(company: str) -> str:
    for account_name in ("Current Assets", "Application of Funds (Assets)", "Assets"):
        parent = frappe.db.get_value(
            "Account",
            {
                "company": company,
                "account_name": account_name,
                "is_group": 1,
                "disabled": 0,
            },
            "name",
        )
        if parent:
            return parent

    rows = frappe.get_all(
        "Account",
        filters={"company": company, "root_type": "Asset", "is_group": 1, "disabled": 0},
        fields=["name", "parent_account", "lft"],
        order_by="lft asc",
        limit_page_length=0,
    )
    nested = next((row.name for row in rows if row.parent_account), None)
    if nested:
        return nested
    if rows:
        return rows[0].name
    frappe.throw(f"An Asset group Account is required for {company} before local retail setup.")


def _ensure_group(company: str, account_name: str) -> str:
    existing = frappe.db.get_value(
        "Account",
        {"company": company, "account_name": account_name, "is_group": 1, "disabled": 0},
        "name",
    )
    if existing:
        return existing

    doc = frappe.get_doc(
        {
            "doctype": "Account",
            "account_name": account_name,
            "company": company,
            "parent_account": _asset_parent(company),
            "is_group": 1,
            "disabled": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def _ensure_leaf(company: str, account_type: str) -> str:
    if account_type == "Bank":
        group_name = "Bank Accounts"
        leaf_name = "Operating Bank Account"
    elif account_type == "Cash":
        group_name = "Cash In Hand"
        leaf_name = "POS Cash Counter"
    else:
        frappe.throw(f"Unsupported local payment account type: {account_type}")

    existing = frappe.db.get_value(
        "Account",
        {"company": company, "account_name": leaf_name, "is_group": 0, "disabled": 0},
        "name",
    )
    if existing:
        return existing

    doc = frappe.get_doc(
        {
            "doctype": "Account",
            "account_name": leaf_name,
            "company": company,
            "parent_account": _ensure_group(company, group_name),
            "account_type": account_type,
            "is_group": 0,
            "disabled": 0,
        }
    )
    doc.insert(ignore_permissions=True)
    return doc.name


def find_or_create_payment_account(
    company: str, account_type: str, fallback_field: str | None = None
) -> str:
    native._local_only()
    existing = _existing_leaf(company, account_type, fallback_field)
    if existing:
        return existing

    account = _ensure_leaf(company, account_type)
    if (
        fallback_field
        and frappe.get_meta("Company").has_field(fallback_field)
        and not frappe.db.get_value("Company", company, fallback_field)
    ):
        frappe.db.set_value(
            "Company", company, fallback_field, account, update_modified=False
        )
    return account


def configure() -> None:
    native._find_leaf_account = find_or_create_payment_account


__all__ = ["configure", "find_or_create_payment_account"]
