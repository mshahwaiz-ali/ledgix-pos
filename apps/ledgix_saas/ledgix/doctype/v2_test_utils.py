from __future__ import annotations

from uuid import uuid4

import frappe
from frappe.utils import today


def unique_name(prefix: str) -> str:
	return f"TEST-{prefix}-{uuid4().hex[:10]}"


def configure_v2_test_environment() -> None:
    """Keep legacy compatibility tests local and unable to activate FBR network."""

    frappe.set_user("Administrator")

    from ledgix_saas.api import fbr_native

    if getattr(fbr_native, "V2_NETWORK_CUTOVER_ACTIVE", None) is not False:
        frappe.throw("V2_NETWORK_CUTOVER_ACTIVE must remain False in tests.")

    # Legacy Sale snapshot tests now use the retained Brand/Tax compatibility
    # masters.  The retired Ledgix FBR Settings singleton is never mutated.
    frappe.db.set_single_value("Ledgix Brand Settings", "legal_business_name", "")
    frappe.db.set_single_value("Ledgix Brand Settings", "business_address", "")
    frappe.db.set_single_value("Ledgix Brand Settings", "ntn", "")
    frappe.db.set_single_value("Ledgix Brand Settings", "strn", "")

    frappe.db.set_single_value("Ledgix Tax Profile", "tax_enabled", 0)
    frappe.db.set_single_value("Ledgix Tax Profile", "price_includes_tax", 0)
    frappe.db.set_single_value("Ledgix Tax Profile", "default_tax_category", "")
    frappe.db.set_single_value("Ledgix Tax Profile", "default_sales_type", "")
    frappe.db.set_single_value("Ledgix Tax Profile", "default_buyer_type", "Unregistered")
    frappe.db.set_single_value("Ledgix Tax Profile", "province", "Punjab")
    frappe.db.set_single_value("Ledgix Tax Profile", "outlet_address", "Test Outlet")

    frappe.clear_cache(doctype="Ledgix Brand Settings")
    frappe.clear_cache(doctype="Ledgix Tax Profile")



def configure_tax_profile(tax_category, *, price_includes_tax: bool = False) -> None:
    frappe.db.set_single_value("Ledgix Tax Profile", "tax_enabled", 1)
    frappe.db.set_single_value(
        "Ledgix Tax Profile",
        "price_includes_tax",
        1 if price_includes_tax else 0,
    )
    frappe.db.set_single_value("Ledgix Tax Profile", "default_tax_category", tax_category)
    frappe.db.set_single_value(
        "Ledgix Tax Profile",
        "default_sales_type",
        "Goods at standard rate",
    )
    frappe.db.set_single_value("Ledgix Tax Profile", "default_buyer_type", "Registered")
    frappe.db.set_single_value("Ledgix Tax Profile", "province", "Punjab")
    frappe.db.set_single_value("Ledgix Tax Profile", "outlet_address", "Test Outlet")

    # Historical Ledgix Sale snapshot compatibility uses Brand Settings for
    # seller name/NTN/address and Tax Profile for province fallback.
    frappe.db.set_single_value(
        "Ledgix Brand Settings",
        "legal_business_name",
        "Ledgix Test Seller",
    )
    frappe.db.set_single_value("Ledgix Brand Settings", "ntn", "1234567")
    frappe.db.set_single_value(
        "Ledgix Brand Settings",
        "business_address",
        "Test Seller Address",
    )

    frappe.clear_cache(doctype="Ledgix Tax Profile")
    frappe.clear_cache(doctype="Ledgix Brand Settings")



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
	name = unique_name("TAX")
	doc = frappe.get_doc({
		"doctype": "Ledgix Tax Category",
		"category_name": name,
		"tax_type": "Sales Tax",
		"default_rate": rate,
		"is_exempt": 0,
		"is_zero_rated": 0,
		"active": 1,
	})
	doc.insert(ignore_permissions=True)
	return doc


def make_tax_rate(tax_category, *, rate: float = 18, province: str = "Punjab"):
	doc = frappe.get_doc({
		"doctype": "Ledgix Tax Rate",
		"tax_category": tax_category,
		"rate": rate,
		"effective_from": today(),
		"applies_to": "Sales",
		"province": province,
		"active": 1,
	})
	doc.insert(ignore_permissions=True)
	return doc


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
	doc = frappe.get_doc({
		"doctype": "Ledgix Item Tax Profile",
		"item": item,
		"taxable": 1,
		"tax_category": tax_category,
		"tax_basis": tax_basis,
		"notified_retail_price": notified_retail_price,
		"fbr_rate_description": fbr_rate_description,
		"sales_tax_withheld_at_source_per_unit": sales_tax_withheld_at_source_per_unit,
		"extra_tax_per_unit": extra_tax_per_unit,
		"further_tax_per_unit": further_tax_per_unit,
		"fed_payable_per_unit": fed_payable_per_unit,
		"hs_code": "2202.10",
		"uom_for_fbr": "Numbers, pieces, units",
		"sales_type": "Goods at standard rate",
		"scenario_id": scenario_id,
		"needs_review": 0,
		"active": 1,
	})
	doc.insert(ignore_permissions=True)
	return doc


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
