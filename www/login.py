from frappe.www.login import get_context as frappe_login_get_context

from ledgix_saas.api.brand import get_brand_settings, get_splash_logo_url


def get_context(context):
	frappe_login_get_context(context)
	brand = get_brand_settings()
	context.logo = brand["full_logo_url"]
	context.app_name = brand["brand_name"]
	context["splash_image"] = get_splash_logo_url()
	context["favicon"] = brand["favicon_url"]
	context["ledgix_brand"] = brand
