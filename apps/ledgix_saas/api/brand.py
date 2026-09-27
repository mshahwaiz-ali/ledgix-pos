"""Central Ledgix brand/logo helpers."""

from __future__ import annotations

import frappe

SETTINGS_DOCTYPE = "Ledgix Brand Settings"
DEFAULT_PRIMARY_COLOR = "#8C2031"
DEFAULT_SYMBOL_LOGO = "/assets/ledgix_saas/images/brand/ledgix-symbol.svg"
DEFAULT_FULL_LOGO = "/assets/ledgix_saas/images/brand/ledgix-lockup.svg"
DEFAULT_SPLASH_LOGO = DEFAULT_SYMBOL_LOGO
DEFAULT_FAVICON_LOGO = "/assets/ledgix_saas/images/brand/ledgix-favicon.svg"


def _asset_url(path: str | None) -> str:
	if not path:
		return ""

	path = path.strip()
	if path.startswith(("http://", "https://")):
		return path
	if path.startswith("/"):
		return path
	return f"/files/{path}"


def _usable_custom_asset(path: str | None) -> str:
	url = _asset_url(path)
	if not url:
		return ""

	# External and bundled assets are already stable URLs.
	if url.startswith(("http://", "https://", "/assets/")):
		return url

	# Attach/Attach Image values should resolve to a live public File row. A
	# stale Brand Settings attachment must never override the bundled Ledgix
	# identity after cache clears or file cleanup.
	if url.startswith("/files/") and frappe.db.exists(
		"File",
		{"file_url": url, "is_private": 0},
	):
		return url

	return ""


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
	primary_color = (doc and doc.primary_brand_color) or DEFAULT_PRIMARY_COLOR

	custom_symbol = _usable_custom_asset(doc.symbol_logo) if doc else ""
	custom_full = _usable_custom_asset(doc.full_logo) if doc else ""
	custom_favicon = _usable_custom_asset(doc.favicon) if doc else ""

	has_custom_symbol = bool(custom_symbol)
	has_custom_full = bool(custom_full)
	has_custom_favicon = bool(custom_favicon)

	# Ledgix owns its default identity. Brand Settings may override these assets,
	# but an empty setting must never fall back to Frappe's framework logo.
	symbol_logo_url = custom_symbol or DEFAULT_SYMBOL_LOGO
	full_logo_url = custom_full or custom_symbol or DEFAULT_FULL_LOGO
	favicon_url = custom_favicon or custom_symbol or DEFAULT_FAVICON_LOGO

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


def get_print_logo_url() -> str:
	"""Return the configured full logo with the bundled Ledgix lockup fallback."""
	return get_brand_settings()["full_logo_url"]


def get_desk_logo_url() -> str:
	return get_brand_settings()["symbol_logo_url"]


def get_splash_logo_url() -> str:
	brand = get_brand_settings()
	if brand.get("has_custom_symbol"):
		return brand["symbol_logo_url"]
	if brand.get("has_custom_full"):
		return brand["full_logo_url"]
	return DEFAULT_SPLASH_LOGO


def extend_bootinfo(bootinfo):
	brand = get_brand_settings()
	bootinfo.ledgix_brand = brand
	# Always publish a Ledgix desk logo, including the bundled default. This makes
	# Brand Settings authoritative while preserving a deterministic fallback.
	bootinfo.app_logo_url = brand["symbol_logo_url"]
	bootinfo.app_name = brand["brand_name"]


def update_website_context(context):
	brand = get_brand_settings()
	context["logo"] = brand["full_logo_url"]
	context["app_name"] = brand["brand_name"]
	context["splash_image"] = get_splash_logo_url()
	context["favicon"] = brand["favicon_url"]
	context["ledgix_brand"] = brand


@frappe.whitelist(allow_guest=True)
def get_public_brand_settings():
	"""Return only public visual identity fields for Desk/login live branding."""
	return get_brand_settings()
