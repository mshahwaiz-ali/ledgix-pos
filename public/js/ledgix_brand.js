(function () {
	"use strict";

	const FRAPPE_DEFAULT_LOGO = "/assets/frappe/images/frappe-framework-logo.svg";
	const CUSTOM_PAGE_TITLES = {
		"ledgix-pos": "Ledgix POS",
		"ledgix-tax-center": "Tax & FBR Center",
		"business-intelligence-center": "Inventory Intelligence",
	};

	function getBrand() {
		const boot = (window.frappe && frappe.boot) || {};
		const brand = boot.ledgix_brand || {};
		const deskLogo = boot.app_logo_url || FRAPPE_DEFAULT_LOGO;

		return {
			name: brand.brand_name || boot.app_name || "Ledgix",
			tagline: brand.brand_tagline || "Retail operations",
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

	function currentRouteName() {
		if (window.frappe?.get_route) {
			const route = frappe.get_route() || [];
			return String(route[0] || "");
		}
		const path = window.location?.pathname || "";
		return path.replace(/^\/app\//, "").split("/")[0] || "";
	}

	function isLedgixDeskRoute() {
		const route = currentRouteName().toLowerCase();
		const path = (window.location?.pathname || "").toLowerCase();
		return route.startsWith("ledgix-")
			|| route === "business-intelligence-center"
			|| route === "ledgix"
			|| path.startsWith("/app/ledgix-")
			|| path === "/app/ledgix"
			|| path.startsWith("/app/business-intelligence-center");
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

	function applyBrandTokens() {
		const brand = getBrand();
		if (!brand.primaryColor || !document.documentElement) return;
		document.documentElement.style.setProperty("--lx-v2-primary", brand.primaryColor);
	}

	function restoreNativeDeskChrome() {
		const route = currentRouteName().toLowerCase();
		const title = CUSTOM_PAGE_TITLES[route];
		if (!title) return;

		const activePage = window.frappe?.container?.page;
		if (activePage?.set_title) {
			activePage.set_title(title);
		}

		document.querySelectorAll(".page-container").forEach((container) => {
			if (!container.offsetParent && container.getAttribute("aria-hidden") === "true") return;
			container.classList.remove("ledgix-page-no-frappe-head");
			container.querySelectorAll(".page-head, .page-head-content, .page-title, .title-area, .page-actions").forEach((element) => {
				element.style.removeProperty("display");
				element.removeAttribute("hidden");
			});
		});

		const titleNodes = document.querySelectorAll(
			".page-container .page-title .title-text, .page-container .page-title h3, .page-container .title-area .title-text"
		);
		titleNodes.forEach((node) => {
			if (node.offsetParent !== null && !String(node.textContent || "").trim()) {
				node.textContent = title;
			}
		});
	}

	function applyDeskBrand() {
		if (!isLedgixDeskRoute()) return;
		const brand = getBrand();
		const logoUrl = brand.symbolUrl || FRAPPE_DEFAULT_LOGO;
		document.querySelectorAll(".navbar-brand img.app-logo, .navbar-home img.app-logo, .navbar-home img").forEach((img) => {
			if (!img || img.tagName !== "IMG") return;
			img.src = logoUrl;
			img.alt = brand.name;
			img.style.objectFit = "contain";
		});
		setFavicon(brand.faviconUrl || logoUrl);
		restoreNativeDeskChrome();
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
		applyBrandTokens();
		applyDeskBrand();
		applyLoginBrand();
	}

	window.LedgixBrand = {
		get: getBrand,
		apply: applyAll,
		restoreNativeDeskChrome,
	};

	function scheduleApply() {
		window.setTimeout(applyAll, 0);
		window.setTimeout(applyAll, 120);
		window.setTimeout(applyAll, 400);
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
