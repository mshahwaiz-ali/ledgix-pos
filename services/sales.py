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
