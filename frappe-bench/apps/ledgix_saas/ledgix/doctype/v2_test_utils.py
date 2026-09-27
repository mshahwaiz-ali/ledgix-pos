from __future__ import annotations

from uuid import uuid4

import frappe


def unique_name(prefix: str) -> str:
	return f"TEST-{prefix}-{uuid4().hex[:10]}"


def configure_v2_test_environment() -> None:
    frappe.set_user("Administrator")

    from ledgix_saas.api import fbr_native

    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False in tests.")

    frappe.db.set_single_value("Ledgix Brand Settings", "legal_business_name", "")
    frappe.db.set_single_value("Ledgix Brand Settings", "business_address", "")
    frappe.db.set_single_value("Ledgix Brand Settings", "ntn", "")
    frappe.db.set_single_value("Ledgix Brand Settings", "strn", "")
    frappe.clear_cache(doctype="Ledgix Brand Settings")


def configure_tax_profile(tax_category, *, price_includes_tax: bool = False) -> None:
    _ = tax_category, price_includes_tax
    frappe.throw(
        "Legacy tax-profile test configuration is retired; use ERPNext-native "
        "tax fixtures and FBR V2 mappings.",
        frappe.ValidationError,
    )


def _retired_legacy_business_fixture(helper_name: str):
	frappe.throw(
		(
			f"{helper_name} is retired after the Phase 12 ERPNext cutover. "
			"Legacy Ledgix business DocTypes are frozen historical audit data; "
			"use ERPNext-native test fixtures instead."
		),
		frappe.ValidationError,
	)

def make_price_list(*, default_retail: bool = False, priority: int = 10):
	return _retired_legacy_business_fixture("make_price_list")


def make_item(*, selling_price: float = 100, cost_price: float = 40, opening_stock: float = 100):
	return _retired_legacy_business_fixture("make_item")


def make_item_price(item, price_list, rate: float, *, effective_from=None, effective_to=None):
	return _retired_legacy_business_fixture("make_item_price")


def make_customer(
	*,
	customer_type: str = "B2B",
	default_price_list=None,
	payment_terms_days: int = 0,
	credit_limit: float = 10000,
):
	return _retired_legacy_business_fixture("make_customer")


def make_supplier():
	return _retired_legacy_business_fixture("make_supplier")


def make_tax_category(*, rate: float = 18):
    _ = rate
    return _retired_legacy_business_fixture("make_tax_category")


def make_tax_rate(tax_category, *, rate: float = 18, province: str = "Punjab"):
    _ = tax_category, rate, province
    return _retired_legacy_business_fixture("make_tax_rate")


def make_item_tax_profile(
    item,
    tax_category,
    *,
    tax_basis: str = "Transaction Value",
    notified_retail_price: float = 0,
    scenario_id: str = "SN001",
    fbr_rate_description: str = "",
    sales_tax_withheld_at_source_per_unit: float = 0,
    extra_tax_per_unit: float = 0,
    further_tax_per_unit: float = 0,
    fed_payable_per_unit: float = 0,
):
    _ = (
        item,
        tax_category,
        tax_basis,
        notified_retail_price,
        scenario_id,
        fbr_rate_description,
        sales_tax_withheld_at_source_per_unit,
        extra_tax_per_unit,
        further_tax_per_unit,
        fed_payable_per_unit,
    )
    return _retired_legacy_business_fixture("make_item_tax_profile")


def make_user_with_roles(*roles):
	email = f"{unique_name('USER').lower()}@example.com"
	doc = frappe.get_doc({
		"doctype": "User",
		"email": email,
		"first_name": "Ledgix Test User",
		"enabled": 1,
		"send_welcome_email": 0,
		"user_type": "System User",
	})
	for role in roles:
		doc.append("roles", {"role": role})
	doc.insert(ignore_permissions=True)
	return doc


def ensure_cash_payment_method() -> str:
	return _retired_legacy_business_fixture("ensure_cash_payment_method")


def make_sale(
	customer,
	item,
	*,
	quantity: float = 1,
	rate: float = 100,
	sale_channel: str = "B2B",
	payments=None,
	submit: bool = False,
):
	return _retired_legacy_business_fixture("make_sale")


def make_purchase(supplier, item, *, quantity: float = 1, rate: float = 50, submit: bool = False):
	return _retired_legacy_business_fixture("make_purchase")


def make_sales_return(
	sale,
	*,
	quantity: float = 1,
	include_row_reference: bool = True,
	return_reason: str = "Test return",
	submit: bool = False,
):
	return _retired_legacy_business_fixture("make_sales_return")
