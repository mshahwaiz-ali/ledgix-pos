from __future__ import annotations

import frappe

from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE
from ledgix_saas.setup.fbr_v2_component_mappings import (
    preview_component_mappings,
    provision_component_mappings,
)


COMPANY = "Ledgix ERPNext Integration"

# This plan is deliberately local-fixture specific. It records the exact account
# semantics proven by the Phase-1 ERPNext-native parity gates on the canonical
# integration site. It must never be reused as a generic production account map.
LOCAL_COMPONENT_PLAN = (
    ("GST - LEI", "Sales Tax Applicable"),
    ("Ledgix P4 Extra Tax Payable - LEI", "Extra Tax"),
    ("Ledgix P4 Further Tax Payable - LEI", "Further Tax"),
    ("Ledgix P4 FED Payable - LEI", "FED Payable"),
    (
        "Ledgix P4 Sales Tax Withheld - LEI",
        "Sales Tax Withheld At Source",
    ),
)

LEGACY_MONETARY_SALES_TAX_ACCOUNT = "Ledgix P4 Sales Tax Payable - LEI"
APPLY_CONFIRMATION = "APPLY FBR V2 COMPONENT MAPPINGS LOCAL"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing local FBR V2 component mapping driver on "
            f"{frappe.local.site!r}; expected {INTEGRATION_SITE!r}."
        )


def _assert_plan_contract() -> None:
    accounts = {account for account, _component in LOCAL_COMPONENT_PLAN}

    if LEGACY_MONETARY_SALES_TAX_ACCOUNT in accounts:
        frappe.throw(
            "Legacy [LEDGIX-TAX] Sales Tax account must not be provisioned "
            "as the V2 Sales Tax Applicable authority."
        )


def preview() -> dict:
    _assert_safe_site()
    _assert_plan_contract()

    result = preview_component_mappings(COMPANY, LOCAL_COMPONENT_PLAN)
    result.update(
        {
            "site": frappe.local.site,
            "local_only": True,
            "legacy_sales_tax_account_excluded": (
                LEGACY_MONETARY_SALES_TAX_ACCOUNT
            ),
            "source_of_semantics": (
                "Phase-1 ERPNext-native rollback-safe parity gates"
            ),
        }
    )
    return result


def apply(confirmation: str | None = None) -> dict:
    _assert_safe_site()
    _assert_plan_contract()

    if str(confirmation or "") != APPLY_CONFIRMATION:
        frappe.throw(
            "Refusing FBR V2 component mapping apply without exact local "
            f"confirmation: {APPLY_CONFIRMATION}"
        )

    before = preview()
    if before["blockers"]:
        frappe.throw(
            "Refusing FBR V2 component mapping apply because preview has blockers."
        )

    result = provision_component_mappings(
        COMPANY,
        LOCAL_COMPONENT_PLAN,
        notes=(
            "Local integration mapping proven by Phase-1 ERPNext-native "
            "rollback-safe parity gates. Classification only; ERPNext owns money."
        ),
    )
    result.update(
        {
            "site": frappe.local.site,
            "local_only": True,
            "confirmation_verified": True,
        }
    )
    return result
