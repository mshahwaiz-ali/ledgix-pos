from __future__ import annotations

from uuid import uuid4

import frappe
from frappe.utils import today


def unique_name(prefix: str) -> str:
	return f"TEST-{prefix}-{uuid4().hex[:10]}"


def configure_v2_test_environment(stock_mode: str = "Billing Only") -> None:
	"""Keep integration tests local, deterministic, and free of external FBR calls."""
	frappe.set_user("Administrator")
	frappe.db.set_single_value("Ledgix Mode Settings", "stock_control_mode", stock_mode)
	frappe.db.set_single_value("Ledgix FBR Settings", "enabled", 0)
	frappe.db.set_single_value("Ledgix FBR Settings", "mode", "Disabled")
	frappe.db.set_single_value("Ledgix FBR Settings", "submit_trigger", "Manual")
	frappe.db.set_single_value("Ledgix FBR Settings", "block_sale_if_fbr_fails", 0)
	frappe.clear_cache(doctype="Ledgix Mode Settings")
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


def make_item(*, selling_price: float = 100, cost_price: float = 40, opening_stock: float = 0):
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


def make_sales_return(sale, *, quantity: float = 1, include_row_reference: bool = True, submit: bool = False):
	sale_doc = frappe.get_doc("Ledgix Sale", sale) if isinstance(sale, str) else sale
	original_row = sale_doc.items[0]
	doc = frappe.get_doc({
		"doctype": "Ledgix Sales Return",
		"original_sale": sale_doc.name,
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
