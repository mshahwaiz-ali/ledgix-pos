from __future__ import annotations

from uuid import uuid4

import frappe
from frappe.utils import today


def unique_name(prefix: str) -> str:
	return f"TEST-{prefix}-{uuid4().hex[:10]}"


def configure_v2_test_environment() -> None:
	"""Keep integration tests local, deterministic, and free of external FBR calls."""
	frappe.set_user("Administrator")
	frappe.db.set_single_value("Ledgix FBR Settings", "enabled", 0)
	frappe.db.set_single_value("Ledgix FBR Settings", "mode", "Disabled")
	frappe.db.set_single_value("Ledgix FBR Settings", "submit_trigger", "Manual")
	frappe.db.set_single_value("Ledgix FBR Settings", "production_post_armed", 0)
	frappe.db.set_single_value("Ledgix FBR Settings", "block_sale_if_fbr_fails", 0)
	frappe.db.set_single_value("Ledgix FBR Settings", "sandbox_post_on_submit", 0)
	frappe.db.set_single_value("Ledgix FBR Settings", "retry_enabled", 0)
	frappe.db.set_single_value("Ledgix FBR Settings", "seller_ntn_cnic", "")
	frappe.db.set_single_value("Ledgix FBR Settings", "seller_business_name", "")
	frappe.db.set_single_value("Ledgix FBR Settings", "seller_province", "")
	frappe.db.set_single_value("Ledgix FBR Settings", "seller_address", "")
	frappe.db.set_single_value("Ledgix Tax Profile", "tax_enabled", 0)
	frappe.db.set_single_value("Ledgix Tax Profile", "price_includes_tax", 0)
	frappe.db.set_single_value("Ledgix Tax Profile", "default_tax_category", "")
	frappe.db.set_single_value("Ledgix Tax Profile", "default_sales_type", "")
	frappe.db.set_single_value("Ledgix Tax Profile", "default_buyer_type", "Unregistered")
	frappe.db.set_single_value("Ledgix Tax Profile", "province", "Punjab")
	frappe.db.set_single_value("Ledgix Tax Profile", "outlet_address", "Test Outlet")
	frappe.clear_cache(doctype="Ledgix FBR Settings")
	frappe.clear_cache(doctype="Ledgix Tax Profile")


def configure_tax_profile(tax_category, *, price_includes_tax: bool = False) -> None:
	frappe.db.set_single_value("Ledgix Tax Profile", "tax_enabled", 1)
	frappe.db.set_single_value("Ledgix Tax Profile", "price_includes_tax", 1 if price_includes_tax else 0)
	frappe.db.set_single_value("Ledgix Tax Profile", "default_tax_category", tax_category)
	frappe.db.set_single_value("Ledgix Tax Profile", "default_sales_type", "Goods at standard rate")
	frappe.db.set_single_value("Ledgix Tax Profile", "default_buyer_type", "Registered")
	frappe.db.set_single_value("Ledgix Tax Profile", "province", "Punjab")
	frappe.db.set_single_value("Ledgix Tax Profile", "outlet_address", "Test Outlet")
	frappe.db.set_single_value("Ledgix FBR Settings", "seller_ntn_cnic", "1234567")
	frappe.db.set_single_value("Ledgix FBR Settings", "seller_business_name", "Ledgix Test Seller")
	frappe.db.set_single_value("Ledgix FBR Settings", "seller_province", "Punjab")
	frappe.db.set_single_value("Ledgix FBR Settings", "seller_address", "Test Seller Address")
	frappe.clear_cache(doctype="Ledgix Tax Profile")
	frappe.clear_cache(doctype="Ledgix FBR Settings")


def make_price_list(*, default_retail: bool = False, priority: int = 10):
	name = unique_name("PL")
	doc = frappe.get_doc({
		"doctype": "Ledgix Price List",
		"price_list_name": name,
		"enabled": 1,
		"is_default_retail": 1 if default_retail else 0,
		"currency": "PKR",
		"priority": priority,
	})
	doc.insert(ignore_permissions=True)
	return doc


def make_item(*, selling_price: float = 100, cost_price: float = 40, opening_stock: float = 100):
	name = unique_name("ITEM")
	doc = frappe.get_doc({
		"doctype": "Ledgix Item",
		"item_code": name,
		"item_name": name,
		"unit": "Piece",
		"selling_price": selling_price,
		"cost_price": cost_price,
		"opening_stock": opening_stock,
		"minimum_stock": 0,
		"active": 1,
		"tracking_type": "Normal",
	})
	doc.insert(ignore_permissions=True)
	return doc


def make_item_price(item, price_list, rate: float, *, effective_from=None, effective_to=None):
	doc = frappe.get_doc({
		"doctype": "Ledgix Item Price",
		"item": item,
		"price_list": price_list,
		"rate": rate,
		"effective_from": effective_from,
		"effective_to": effective_to,
		"enabled": 1,
		"uom": "Piece",
	})
	doc.insert(ignore_permissions=True)
	return doc


def make_customer(
	*,
	customer_type: str = "B2B",
	default_price_list=None,
	payment_terms_days: int = 0,
	credit_limit: float = 10000,
):
	name = unique_name("CUSTOMER")
	doc = frappe.get_doc({
		"doctype": "Ledgix Customer",
		"customer_name": name,
		"customer_type": customer_type,
		"default_price_list": default_price_list,
		"payment_terms_days": payment_terms_days,
		"credit_limit": credit_limit,
		"buyer_ntn_cnic": "1234567-8",
		"buyer_strn": "STRN-TEST",
		"buyer_registration_type": "Registered",
		"buyer_province": "Punjab",
		"buyer_fbr_address": "Test Business Address",
		"address_line_1": "Fallback Address",
		"city": "Lahore",
		"is_active": 1,
	})
	doc.insert(ignore_permissions=True)
	return doc


def make_supplier():
	name = unique_name("SUPPLIER")
	doc = frappe.get_doc({
		"doctype": "Ledgix Supplier",
		"supplier_name": name,
		"company_name": name,
		"supplier_type": "Local",
		"is_active": 1,
	})
	doc.insert(ignore_permissions=True)
	return doc


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
	if not frappe.db.exists("Ledgix Payment Method", "Cash"):
		doc = frappe.get_doc({
			"doctype": "Ledgix Payment Method",
			"payment_method_name": "Cash",
			"method_type": "Cash",
			"enabled": 1,
			"allow_change": 1,
			"sort_order": 1,
		})
		doc.insert(ignore_permissions=True)
	return "Cash"


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
	doc = frappe.get_doc({
		"doctype": "Ledgix Sale",
		"customer": customer,
		"sale_channel": sale_channel,
		"sale_date": today(),
	})
	doc.append("items", {
		"item": item,
		"quantity": quantity,
		"list_rate": rate,
		"rate": rate,
		"cost_price": frappe.db.get_value("Ledgix Item", item, "cost_price") or 0,
	})
	for payment in payments or []:
		doc.append("payments", payment)
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc


def make_purchase(supplier, item, *, quantity: float = 1, rate: float = 50, submit: bool = False):
	doc = frappe.get_doc({
		"doctype": "Ledgix Purchase",
		"supplier": supplier,
		"purchase_date": today(),
	})
	doc.append("items", {
		"item": item,
		"quantity": quantity,
		"rate": rate,
		"unit": "Piece",
	})
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc


def make_sales_return(
	sale,
	*,
	quantity: float = 1,
	include_row_reference: bool = True,
	return_reason: str = "Test return",
	submit: bool = False,
):
	sale_doc = frappe.get_doc("Ledgix Sale", sale) if isinstance(sale, str) else sale
	original_row = sale_doc.items[0]
	doc = frappe.get_doc({
		"doctype": "Ledgix Sales Return",
		"original_sale": sale_doc.name,
		"return_reason": return_reason,
	})
	doc.append("items", {
		"item": original_row.item,
		"original_sale_item_row": original_row.name if include_row_reference else None,
		"quantity": quantity,
		"rate": 0,
		"cost_price": 0,
	})
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	return doc
