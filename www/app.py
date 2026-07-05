from frappe.www.app import get_context as frappe_app_get_context

from ledgix_saas.api.brand import get_brand_settings, get_splash_logo_url

no_cache = 1


def get_context(context):
	frappe_app_get_context(context)
	brand = get_brand_settings()
	context["splash_image"] = get_splash_logo_url()
	context["favicon"] = brand["favicon_url"]
	if brand.get("brand_name"):
		context["app_name"] = brand["brand_name"]
	return context
