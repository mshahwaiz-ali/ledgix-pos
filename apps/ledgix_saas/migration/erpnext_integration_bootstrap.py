from __future__ import annotations

import frappe

from ledgix_saas.migration.erpnext_behavioral_preflight import run as run_preflight


INTEGRATION_SITE = "ledgix-erpnext.local"
TEST_COMPANY = "Ledgix ERPNext Integration"
TEST_COMPANY_ABBR = "LEI"
COUNTRY = "Pakistan"
CURRENCY = "PKR"
FY_START_DATE = "2026-07-01"
FY_END_DATE = "2027-06-30"
CHART_OF_ACCOUNTS = "Standard"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing integration bootstrap on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )

    installed_apps = set(frappe.get_installed_apps())
    required = {"frappe", "erpnext", "ledgix_saas"}
    missing = sorted(required - installed_apps)
    if missing:
        frappe.throw(f"Missing required apps for integration bootstrap: {', '.join(missing)}")


def run() -> dict:
    """Bootstrap ERPNext's official defaults on the isolated integration site.

    This intentionally reuses ERPNext's own setup-wizard operations instead of
    creating Ledgix-owned copies of accounting, stock, pricing, or master data.
    It is restricted to the dedicated local integration site and only performs
    the setup when no Company exists yet.
    """

    _assert_safe_site()

    before = run_preflight()
    if before.get("companies"):
        return {
            "site": frappe.local.site,
            "created": False,
            "reason": "company_already_exists",
            "company": before.get("default_company") or before["companies"][0],
            "preflight": before,
        }

    from erpnext.setup.setup_wizard.setup_wizard import setup_complete

    args = frappe._dict(
        {
            "company_name": TEST_COMPANY,
            "company_abbr": TEST_COMPANY_ABBR,
            "country": COUNTRY,
            "currency": CURRENCY,
            "fy_start_date": FY_START_DATE,
            "fy_end_date": FY_END_DATE,
            "chart_of_accounts": CHART_OF_ACCOUNTS,
            "domain": None,
            "bank_account": None,
            "setup_demo": 0,
        }
    )

    setup_complete(args)
    frappe.db.commit()

    after = run_preflight()
    return {
        "site": frappe.local.site,
        "created": True,
        "company": TEST_COMPANY,
        "company_abbr": TEST_COMPANY_ABBR,
        "country": COUNTRY,
        "currency": CURRENCY,
        "fiscal_year": f"{FY_START_DATE} to {FY_END_DATE}",
        "chart_of_accounts": CHART_OF_ACCOUNTS,
        "preflight": after,
    }
