from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from ledgix_saas.api import brand


APP_ROOT = Path(__file__).resolve().parents[3]


class TestBrandWiring(FrappeTestCase):
	def test_empty_settings_use_bundled_ledgix_identity(self):
		with patch.object(brand, "_get_settings_doc", return_value=None):
			settings = brand.get_brand_settings()

		self.assertEqual(settings["symbol_logo_url"], brand.DEFAULT_SYMBOL_LOGO)
		self.assertEqual(settings["full_logo_url"], brand.DEFAULT_FULL_LOGO)
		self.assertEqual(settings["favicon_url"], brand.DEFAULT_FAVICON_LOGO)
		self.assertEqual(brand.DEFAULT_SPLASH_LOGO, brand.DEFAULT_SYMBOL_LOGO)
		self.assertEqual(settings["primary_brand_color"], brand.DEFAULT_PRIMARY_COLOR)
		self.assertNotIn("/assets/frappe/", settings["symbol_logo_url"])
		self.assertTrue(brand.DEFAULT_SYMBOL_LOGO.endswith("ledgix-symbol.svg"))
		self.assertTrue(brand.DEFAULT_FULL_LOGO.endswith("ledgix-lockup.svg"))
		self.assertTrue(brand.DEFAULT_FAVICON_LOGO.endswith("ledgix-favicon.svg"))

	def test_boot_always_publishes_brand_identity(self):
		bootinfo = frappe._dict()
		with patch.object(brand, "_get_settings_doc", return_value=None):
			brand.extend_bootinfo(bootinfo)

		self.assertEqual(bootinfo.app_logo_url, brand.DEFAULT_SYMBOL_LOGO)
		self.assertEqual(bootinfo.app_name, "Ledgix")
		self.assertEqual(bootinfo.ledgix_brand["primary_brand_color"], brand.DEFAULT_PRIMARY_COLOR)

	def test_frontend_wires_brand_setting_into_ledgix_surfaces(self):
		brand_js = (APP_ROOT / "public" / "js" / "ledgix_brand.js").read_text(encoding="utf-8")
		brand_css = (APP_ROOT / "public" / "css" / "ledgix_brand.css").read_text(encoding="utf-8")
		settings_js = (
			APP_ROOT / "ledgix" / "doctype" / "ledgix_brand_settings" / "ledgix_brand_settings.js"
		).read_text(encoding="utf-8")

		self.assertIn("--lx-v2-primary", brand_js)
		self.assertIn("refresh: refreshBrand", brand_js)
		self.assertIn("ledgix_saas.api.brand.get_public_brand_settings", brand_js)
		self.assertIn("ledgix-favicon.svg", brand_js)
		self.assertIn("home.replaceChildren(img)", brand_js)
		self.assertIn("LedgixBrand.refresh", settings_js)
		self.assertIn("#page-ledgix-pos .lx-pos-v2 .btn-primary", brand_css)
		self.assertIn("#page-ledgix-tax-center .lx-tax-v2", brand_css)
		self.assertIn("#page-business-intelligence-center .lx-ii-v2 .btn-primary", brand_css)

	def test_bundled_brand_assets_are_vector_only(self):
		brand_dir = APP_ROOT / "public" / "images" / "brand"
		self.assertTrue((brand_dir / "ledgix-symbol.svg").exists())
		self.assertTrue((brand_dir / "ledgix-lockup.svg").exists())
		self.assertTrue((brand_dir / "ledgix-favicon.svg").exists())
		self.assertFalse((brand_dir / "ledgix-symbol.png").exists())
		self.assertFalse((brand_dir / "ledgix-lockup.png").exists())

	def test_list_polish_regressions_are_present(self):
		payment_list = (
			APP_ROOT / "ledgix" / "doctype" / "ledgix_payment" / "ledgix_payment_list.js"
		).read_text(encoding="utf-8")
		stock_list = (
			APP_ROOT / "ledgix" / "doctype" / "ledgix_stock_movement" / "ledgix_stock_movement_list.js"
		).read_text(encoding="utf-8")

		self.assertIn("payment_date", payment_list)
		self.assertIn('IN: "green"', stock_list)
		self.assertIn('OUT: "red"', stock_list)
