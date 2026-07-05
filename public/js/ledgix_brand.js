(function () {
	"use strict";

	const FRAPPE_DEFAULT_LOGO = "/assets/frappe/images/frappe-framework-logo.svg";

	function getBrand() {
		const boot = (window.frappe && frappe.boot) || {};
		const brand = boot.ledgix_brand || {};
		const config = (window.LedgixNavigator && window.LedgixNavigator.config) || {};
		const app = config.app || {};
		const deskLogo = boot.app_logo_url || FRAPPE_DEFAULT_LOGO;

		return {
			name: brand.brand_name || app.name || boot.app_name || "Ledgix",
			tagline: brand.brand_tagline || app.tagline || "Retail operations",
			symbolUrl: brand.has_custom_symbol ? brand.symbol_logo_url : deskLogo,
			fullUrl: brand.has_custom_full ? brand.full_logo_url : (brand.has_custom_symbol ? brand.symbol_logo_url : deskLogo),
			faviconUrl: brand.has_custom_favicon
				? brand.favicon_url
				: (brand.has_custom_symbol ? brand.symbol_logo_url : deskLogo),
			primaryColor: brand.primary_brand_color || "#8C2031",
			hasCustomSymbol: !!brand.has_custom_symbol,
			hasCustomFull: !!brand.has_custom_full,
		};
	}

	function setFavicon(url) {
		if (!url) return;
		let link = document.querySelector('link[rel="icon"]');
		if (!link) {
			link = document.createElement("link");
			link.rel = "icon";
			document.head.appendChild(link);
		}
		link.href = url;
	}

	function applyDeskNavbarBrand() {
		const path = window.location && window.location.pathname;
		const allowed = (window.LedgixNavigator && window.LedgixNavigator.config && window.LedgixNavigator.config.allowed_pages) || [];
		if (!allowed.includes(path)) return;
		const brand = getBrand();
		const logoUrl = brand.symbolUrl || FRAPPE_DEFAULT_LOGO;
		document.querySelectorAll(".navbar-brand img.app-logo, .navbar-home img.app-logo, .navbar-home img").forEach((img) => {
			if (!img || img.tagName !== "IMG") return;
			img.src = logoUrl;
			img.alt = brand.name;
			img.style.objectFit = "contain";
		});
		setFavicon(brand.faviconUrl || logoUrl);
	}

	function applyLoginBrand() {
		if (!document.body || !document.body.classList.contains("website-login")) return;
		const brand = getBrand();
		const logoUrl = brand.fullUrl || brand.symbolUrl || FRAPPE_DEFAULT_LOGO;
		document.querySelectorAll(".app-logo").forEach((img) => {
			img.src = logoUrl;
			img.alt = brand.name;
		});
		setFavicon(brand.faviconUrl || logoUrl);
	}

	function applyAll() {
		applyDeskNavbarBrand();
		applyLoginBrand();
		if (window.LedgixNavigator && typeof window.LedgixNavigator.refreshBrand === "function") {
			window.LedgixNavigator.refreshBrand();
		}
	}

	window.LedgixBrand = {
		get: getBrand,
		apply: applyAll,
	};

	function scheduleApply() {
		window.setTimeout(applyAll, 0);
		window.setTimeout(applyDeskNavbarBrand, 120);
		window.setTimeout(applyDeskNavbarBrand, 400);
	}

	if (window.frappe && frappe.ready) {
		frappe.ready(scheduleApply);
	} else {
		document.addEventListener("DOMContentLoaded", scheduleApply);
	}

	if (window.frappe && frappe.router && frappe.router.on) {
		frappe.router.on("change", scheduleApply);
	}
})();
