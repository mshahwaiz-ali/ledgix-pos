"""Central Ledgix brand/logo helpers."""

from __future__ import annotations

import frappe

FRAPPE_DEFAULT_LOGO = "/assets/frappe/images/frappe-framework-logo.svg"
FRAPPE_DEFAULT_SPLASH_LOGO = "/assets/frappe/images/frappe-framework-logo.png"
SETTINGS_DOCTYPE = "Ledgix Brand Settings"


def _asset_url(path: str | None) -> str:
	if not path:
		return ""

	path = path.strip()
	if path.startswith(("http://", "https://")):
		return path
	if path.startswith("/"):
		return path
	return f"/files/{path}"


def _get_settings_doc():
	if not frappe.db.exists("DocType", SETTINGS_DOCTYPE):
		return None
	try:
		return frappe.get_single(SETTINGS_DOCTYPE)
	except Exception:
		return None


def get_brand_settings():
	doc = _get_settings_doc()
	brand_name = (doc and doc.brand_name) or "Ledgix"
	brand_tagline = (doc and doc.brand_tagline) or "Retail operations"
	primary_color = (doc and doc.primary_brand_color) or "#8C2031"

	has_custom_symbol = bool(doc and doc.symbol_logo)
	has_custom_full = bool(doc and doc.full_logo)
	has_custom_favicon = bool(doc and doc.favicon)

	symbol_logo_url = _asset_url(doc.symbol_logo) if has_custom_symbol else FRAPPE_DEFAULT_LOGO
	full_logo_url = _asset_url(doc.full_logo) if has_custom_full else FRAPPE_DEFAULT_LOGO
	favicon_url = (
		_asset_url(doc.favicon)
		if has_custom_favicon
		else (_asset_url(doc.symbol_logo) if has_custom_symbol else FRAPPE_DEFAULT_LOGO)
	)

	return {
		"brand_name": brand_name,
		"brand_tagline": brand_tagline,
		"primary_brand_color": primary_color,
		"symbol_logo_url": symbol_logo_url,
		"full_logo_url": full_logo_url,
		"favicon_url": favicon_url,
		"has_custom_symbol": has_custom_symbol,
		"has_custom_full": has_custom_full,
		"has_custom_favicon": has_custom_favicon,
	}


def get_login_logo_url() -> str:
	return get_brand_settings()["full_logo_url"]


def get_desk_logo_url() -> str:
	return get_brand_settings()["symbol_logo_url"]


def get_splash_logo_url() -> str:
	brand = get_brand_settings()
	if brand.get("has_custom_symbol"):
		return brand["symbol_logo_url"]
	if brand.get("has_custom_full"):
		return brand["full_logo_url"]
	return FRAPPE_DEFAULT_SPLASH_LOGO


def extend_bootinfo(bootinfo):
	brand = get_brand_settings()
	bootinfo.ledgix_brand = brand
	if brand.get("has_custom_symbol"):
		bootinfo.app_logo_url = brand["symbol_logo_url"]
	if brand.get("brand_name"):
		bootinfo.app_name = brand["brand_name"]


def update_website_context(context):
	brand = get_brand_settings()
	context["logo"] = brand["full_logo_url"]
	context["app_name"] = brand["brand_name"]
	context["splash_image"] = get_splash_logo_url()
	context["favicon"] = brand["favicon_url"]
	context["ledgix_brand"] = brand


@frappe.whitelist()
def get_public_brand_settings():
	return get_brand_settings()
