from __future__ import annotations

"""Explicit ERPNext setup for the statutory FBR POS Service Fee.

Nothing here runs automatically during install/migrate. Operators call the
setup deliberately for the target Company/POS Profile.
"""

import frappe
from frappe.utils import cint

from fbr_v1.services.pos_identity import get_profile
from fbr_v1.services.pos_service_fee import (
    POS_SERVICE_FEE_AMOUNT,
    POS_SERVICE_FEE_DESCRIPTION,
)


def ensure_company_pos_service_fee_setup(company: str, pos_profile: str) -> dict:
    company = str(company or "").strip()
    pos_profile = str(pos_profile or "").strip()
    if not company or not frappe.db.exists("Company", company):
        frappe.throw("Select an existing Company.")

    company_doc = frappe.get_doc("Company", company)
    parent = frappe.db.get_value(
        "Account",
        {"company": company, "account_name": "Duties and Taxes", "is_group": 1},
        "name",
    )
    if not parent:
        frappe.throw("Company requires a Duties and Taxes account group.")

    account = frappe.db.get_value(
        "Account",
        {"company": company, "account_name": "FBR POS Service Fee Payable"},
        ["name", "root_type", "is_group", "parent_account"],
        as_dict=True,
    )
    created_account = False
    if not account:
        account_doc = frappe.get_doc(
            {
                "doctype": "Account",
                "account_name": "FBR POS Service Fee Payable",
                "company": company,
                "parent_account": parent,
                "root_type": "Liability",
                "account_type": "Tax",
                "is_group": 0,
            }
        ).insert(ignore_permissions=True)
        account_name = account_doc.name
        created_account = True
    else:
        if cint(account.get("is_group")) or account.get("root_type") != "Liability":
            frappe.throw("Existing FBR POS Service Fee Payable account is not a leaf Liability.")
        if account.get("parent_account") != parent:
            frappe.throw("Existing FBR POS Service Fee Payable account is outside Duties and Taxes.")
        account_name = account.get("name")

    profile = get_profile(company)
    if not profile:
        frappe.throw("Create the FBR V1 Integration Profile first.")
    frappe.db.set_value(
        "Ledgix FBR Integration Profile",
        profile.name,
        "pos_service_fee_account",
        account_name,
        update_modified=False,
    )

    pos = frappe.db.get_value(
        "POS Profile",
        pos_profile,
        ["name", "company", "taxes_and_charges"],
        as_dict=True,
    )
    if not pos or pos.get("company") != company:
        frappe.throw("POS Profile must exist and belong to the Company.")
    if not pos.get("taxes_and_charges"):
        frappe.throw("POS Profile requires a Sales Taxes and Charges Template.")

    template = frappe.get_doc("Sales Taxes and Charges Template", pos.get("taxes_and_charges"))
    matches = [
        row
        for row in (template.get("taxes") or [])
        if str(row.get("account_head") or "").strip() == account_name
        or str(row.get("description") or "").strip() == POS_SERVICE_FEE_DESCRIPTION
    ]
    if len(matches) > 1:
        frappe.throw("Tax template contains multiple FBR POS Service Fee rows.")
    if matches:
        row = matches[0]
        if str(row.get("account_head") or "").strip() not in {"", account_name}:
            frappe.throw("FBR POS Service Fee template row points to another account.")
        created_template_row = False
    else:
        row = template.append("taxes", {})
        created_template_row = True

    row.charge_type = "Actual"
    row.account_head = account_name
    row.description = POS_SERVICE_FEE_DESCRIPTION
    row.rate = 0
    row.tax_amount = float(POS_SERVICE_FEE_AMOUNT)
    row.included_in_print_rate = 0
    template.save(ignore_permissions=True)

    # The statutory fee is not a V1 tax-component wire field.
    if frappe.db.exists(
        "Ledgix FBR Tax Component Mapping",
        {"company": company, "account_head": account_name, "active": 1},
    ):
        frappe.throw("Do not map the FBR POS Service Fee account as an FBR tax component.")

    # Make the exact Account Link the final write so no stale in-memory
    # profile value can survive this explicit setup operation.
    frappe.db.set_value(
        "Ledgix FBR Integration Profile",
        profile.name,
        "pos_service_fee_account",
        account_name,
        update_modified=False,
    )
    frappe.db.commit()

    stored_account = frappe.db.get_value(
        "Ledgix FBR Integration Profile",
        profile.name,
        "pos_service_fee_account",
    )
    if stored_account != account_name:
        frappe.throw(
            "FBR POS Service Fee profile link did not persist exactly: "
            f"expected {account_name!r}, got {stored_account!r}."
        )

    return {
        "company": company,
        "pos_profile": pos_profile,
        "tax_template": template.name,
        "account": account_name,
        "profile_account": stored_account,
        "amount": float(POS_SERVICE_FEE_AMOUNT),
        "created_account": created_account,
        "created_template_row": created_template_row,
        "network_call": False,
    }
