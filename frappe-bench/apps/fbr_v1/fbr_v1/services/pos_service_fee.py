from __future__ import annotations

"""ERPNext-native statutory Re.1 FBR POS Service Fee handling.

The fee is an ERPNext financial charge and is NOT an undocumented FBR V1
wire field. The V1 payload keeps the documented schema and reconciles the
fee only through TotalBillAmount versus the item/tax totals.
"""

from decimal import Decimal

import frappe
from frappe.utils import cint, flt

from fbr_v1.services.pos_identity import get_profile, profile_active, is_consolidated

SUPPORTED_DOCTYPES = {"Sales Invoice", "POS Invoice"}
POS_SERVICE_FEE_AMOUNT = Decimal("1.00")
POS_SERVICE_FEE_DESCRIPTION = "FBR POS Service Fee"


def _account_row(account_name: str):
    if not account_name:
        return None
    return frappe.db.get_value(
        "Account",
        account_name,
        ["name", "company", "root_type", "is_group"],
        as_dict=True,
    )


def service_fee_configuration_blockers(profile) -> list[str]:
    """Return Production blockers for the statutory POS Service Fee account."""

    if not profile or profile.get("mode") != "Production":
        return []

    account_name = str(profile.get("pos_service_fee_account") or "").strip()
    if not account_name:
        return ["FBR POS Service Fee payable account is required for Production."]

    account = _account_row(account_name)
    if not account:
        return ["Configured FBR POS Service Fee account does not exist."]
    if account.get("company") != profile.get("company"):
        return ["FBR POS Service Fee account must belong to the profile company."]
    if cint(account.get("is_group")) or account.get("root_type") != "Liability":
        return ["FBR POS Service Fee account must be a leaf Liability account."]
    return []


def _validate_runtime_account(profile) -> str:
    blockers = service_fee_configuration_blockers(profile)
    if blockers:
        frappe.throw("; ".join(blockers))
    return str(profile.get("pos_service_fee_account") or "").strip()


def _matching_rows(doc, account_name: str):
    return [
        row
        for row in (doc.get("taxes") or [])
        if str(row.get("account_head") or "").strip() == account_name
        or str(row.get("description") or "").strip() == POS_SERVICE_FEE_DESCRIPTION
    ]


def ensure_pos_service_fee(doc, method=None) -> None:
    """Ensure one native ERPNext Actual Re.1 charge on each new V1 sale."""

    if not doc or doc.doctype not in SUPPORTED_DOCTYPES:
        return
    if cint(doc.docstatus) == 1 and str(getattr(doc, "_action", "") or "") != "submit":
        return

    profile = get_profile(doc.get("company"))
    if not profile_active(profile) or profile.get("mode") not in {"Sandbox", "Production"}:
        return

    account_name = str(profile.get("pos_service_fee_account") or "").strip()

    # A return/credit note does not collect a fresh Re.1 POS service fee.
    # ERPNext return creation may copy the original Actual charge, so remove
    # only this specifically identified statutory row before recalculation.
    if cint(doc.get("is_return")):
        for row in list(_matching_rows(doc, account_name)):
            doc.remove(row)
        return

    # Never mutate ERPNext POS consolidation accounting here.
    if is_consolidated(doc):
        return

    if profile.get("mode") == "Production":
        account_name = _validate_runtime_account(profile)
    elif not account_name:
        # Sandbox may remain usable before a client-specific payable account is configured.
        return

    rows = _matching_rows(doc, account_name)
    if len(rows) > 1:
        frappe.throw("Multiple FBR POS Service Fee rows exist on the invoice.")

    if rows:
        row = rows[0]
        if str(row.get("account_head") or "").strip() not in {"", account_name}:
            frappe.throw("FBR POS Service Fee description is attached to another account.")
    else:
        row = doc.append("taxes", {})

    row.charge_type = "Actual"
    row.account_head = account_name
    row.description = POS_SERVICE_FEE_DESCRIPTION
    row.rate = 0
    row.tax_amount = float(POS_SERVICE_FEE_AMOUNT)
    row.included_in_print_rate = 0


def extract_pos_service_fee(doc) -> float:
    """Read the recalculated ERPNext service-fee evidence from one invoice."""

    if not doc or doc.doctype not in SUPPORTED_DOCTYPES or cint(doc.get("is_return")):
        return 0.0

    profile = get_profile(doc.get("company"))
    if not profile_active(profile) or profile.get("mode") not in {"Sandbox", "Production"}:
        return 0.0

    account_name = str(profile.get("pos_service_fee_account") or "").strip()
    if not account_name:
        return 0.0

    rows = _matching_rows(doc, account_name)
    if len(rows) > 1:
        frappe.throw("Multiple FBR POS Service Fee rows exist on the invoice.")
    if not rows:
        return 0.0

    row = rows[0]
    if str(row.get("account_head") or "").strip() != account_name:
        frappe.throw("FBR POS Service Fee row uses the wrong account.")
    if row.get("charge_type") != "Actual":
        frappe.throw("FBR POS Service Fee must use ERPNext charge type Actual.")
    if cint(row.get("included_in_print_rate")):
        frappe.throw("FBR POS Service Fee must not be included in item print rates.")

    amount = abs(
        Decimal(
            str(
                row.get("tax_amount_after_discount_amount")
                if row.get("tax_amount_after_discount_amount") is not None
                else row.get("tax_amount") or 0
            )
        )
    )
    if amount != POS_SERVICE_FEE_AMOUNT:
        frappe.throw("FBR POS Service Fee must be exactly Re.1 per sale invoice.")
    return flt(amount, 2)
