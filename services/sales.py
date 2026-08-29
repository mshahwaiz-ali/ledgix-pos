from __future__ import annotations

import frappe
from frappe.utils import add_days, cint, getdate, today

from ledgix_saas.services.pricing import resolve_price_list


def infer_sale_channel(customer, explicit=None):
	if explicit in {"Retail", "B2B"}:
		return explicit
	customer_type = frappe.db.get_value("Ledgix Customer", customer, "customer_type") if customer else None
	return "B2B" if customer_type in {"Wholesale", "B2B"} else "Retail"


def _buyer_defaults():
	if not frappe.db.exists("DocType", "Ledgix Tax Profile"):
		return {"registration_type": "Unregistered", "province": "", "address": ""}
	registration_type = frappe.db.get_single_value("Ledgix Tax Profile", "default_buyer_type") or "Unregistered"
	if registration_type == "Consumer":
		registration_type = "Unregistered"
	return {
		"registration_type": registration_type,
		"province": frappe.db.get_single_value("Ledgix Tax Profile", "province") or "",
		"address": frappe.db.get_single_value("Ledgix Tax Profile", "outlet_address") or "",
	}


def _brand_identity():
	if not frappe.db.exists("DocType", "Ledgix Brand Settings"):
		return {}
	return {
		"brand_name": frappe.db.get_single_value("Ledgix Brand Settings", "brand_name") or "",
		"legal_business_name": frappe.db.get_single_value("Ledgix Brand Settings", "legal_business_name") or "",
		"business_address": frappe.db.get_single_value("Ledgix Brand Settings", "business_address") or "",
		"business_phone": frappe.db.get_single_value("Ledgix Brand Settings", "business_phone") or "",
		"business_email": frappe.db.get_single_value("Ledgix Brand Settings", "business_email") or "",
		"ntn": frappe.db.get_single_value("Ledgix Brand Settings", "ntn") or "",
		"strn": frappe.db.get_single_value("Ledgix Brand Settings", "strn") or "",
	}


def get_seller_identity():
	"""Resolve the current site seller identity from canonical Ledgix settings."""
	from ledgix_saas.api.fbr_settings import get_fbr_settings_internal

	brand = _brand_identity()
	fbr = get_fbr_settings_internal() or {}
	province = fbr.get("seller_province") or ""
	outlet_address = ""
	if frappe.db.exists("DocType", "Ledgix Tax Profile"):
		province = province or frappe.db.get_single_value("Ledgix Tax Profile", "province") or ""
		outlet_address = frappe.db.get_single_value("Ledgix Tax Profile", "outlet_address") or ""

	return {
		"name": fbr.get("seller_business_name") or brand.get("legal_business_name") or brand.get("brand_name") or "Ledgix",
		"address": fbr.get("seller_address") or brand.get("business_address") or outlet_address,
		"province": province,
		"ntn_cnic": fbr.get("seller_ntn_cnic") or brand.get("ntn") or "",
		"strn": brand.get("strn") or "",
		"phone": brand.get("business_phone") or "",
		"email": brand.get("business_email") or "",
	}


def apply_seller_snapshot(sale):
	"""Freeze legal seller identity used by invoices and FBR payloads.

	Presentation assets such as logo and colors remain live branding. Legal/tax
	identity is historical transaction data and must not change on reprint/retry.
	"""
	identity = get_seller_identity()
	sale.seller_name_snapshot = identity["name"]
	sale.seller_address_snapshot = identity["address"]
	sale.seller_province_snapshot = identity["province"]
	sale.seller_ntn_cnic_snapshot = identity["ntn_cnic"]
	sale.seller_strn_snapshot = identity["strn"]
	sale.seller_phone_snapshot = identity["phone"]
	sale.seller_email_snapshot = identity["email"]


def apply_item_snapshots(sale):
	"""Freeze customer-facing item identity on Sale rows.

	Item names, codes and UOMs are master data and may be edited or renamed later.
	Receipts and invoices must continue to describe the item as it was sold.
	"""
	for row in sale.get("items") or []:
		if not row.item:
			continue
		item = frappe.db.get_value(
			"Ledgix Item",
			row.item,
			["item_code", "item_name", "unit"],
			as_dict=True,
		)
		if not item:
			row.item_code_snapshot = row.item_code_snapshot or row.item
			row.item_name_snapshot = row.item_name_snapshot or row.item
			continue
		row.item_code_snapshot = item.item_code or row.item
		row.item_name_snapshot = item.item_name or item.item_code or row.item
		row.unit_snapshot = item.unit or ""


def apply_customer_snapshot(sale):
	if not sale.customer:
		return
	customer = frappe.db.get_value(
		"Ledgix Customer",
		sale.customer,
		[
			"customer_name", "customer_type", "default_price_list", "payment_terms_days",
			"buyer_ntn_cnic", "buyer_strn", "buyer_registration_type", "buyer_province",
			"buyer_fbr_address", "address_line_1", "city",
		],
		as_dict=True,
	)
	if not customer:
		return

	defaults = _buyer_defaults()
	sale.sale_channel = infer_sale_channel(sale.customer, getattr(sale, "sale_channel", None))
	sale.price_list = resolve_price_list(sale.customer, getattr(sale, "price_list", None), sale.sale_channel)
	if sale.sale_channel == "B2B":
		sale.payment_terms_days = cint(getattr(sale, "payment_terms_days", 0) or customer.payment_terms_days)
	else:
		sale.payment_terms_days = 0
	sale.due_date = add_days(getdate(sale.sale_date or today()), sale.payment_terms_days)
	sale.buyer_name_snapshot = customer.customer_name
	sale.buyer_ntn_cnic_snapshot = customer.buyer_ntn_cnic
	sale.buyer_strn_snapshot = customer.buyer_strn
	sale.buyer_registration_type_snapshot = customer.buyer_registration_type or defaults["registration_type"]
	sale.buyer_province_snapshot = customer.buyer_province or defaults["province"]
	sale.buyer_address_snapshot = (
		customer.buyer_fbr_address
		or ", ".join(filter(None, [customer.address_line_1, customer.city]))
		or defaults["address"]
	)
