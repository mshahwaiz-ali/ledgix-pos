(function () {
	"use strict";

	const DEFAULT_SYMBOL_LOGO = "/assets/ledgix_saas/images/brand/ledgix-symbol.svg";
	const DEFAULT_FULL_LOGO = "/assets/ledgix_saas/images/brand/ledgix-lockup.svg";
	const DEFAULT_FAVICON_LOGO = "/assets/ledgix_saas/images/brand/ledgix-favicon.svg";
	const DEFAULT_PRIMARY = "#8C2031";
	let refreshPromise = null;

	function bootState() {
		return (window.frappe && frappe.boot) || {};
	}

	function getBrand() {
		const boot = bootState();
		const brand = boot.ledgix_brand || {};

		return {
			name: brand.brand_name || boot.app_name || "Ledgix",
			tagline: brand.brand_tagline || "Retail operations",
			symbolUrl: brand.symbol_logo_url || boot.app_logo_url || DEFAULT_SYMBOL_LOGO,
			fullUrl: brand.full_logo_url || brand.symbol_logo_url || DEFAULT_FULL_LOGO,
			faviconUrl: brand.favicon_url || brand.symbol_logo_url || DEFAULT_FAVICON_LOGO,
			primaryColor: brand.primary_brand_color || DEFAULT_PRIMARY,
			hasCustomSymbol: !!brand.has_custom_symbol,
			hasCustomFull: !!brand.has_custom_full,
			hasCustomFavicon: !!brand.has_custom_favicon,
			fromBoot: !!boot.ledgix_brand,
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

	function contrastText(color) {
		const value = String(color || "").trim();
		const match = value.match(/^#([0-9a-f]{6})$/i);
		if (!match) return "#ffffff";

		const hex = match[1];
		const channels = [0, 2, 4].map((index) => parseInt(hex.slice(index, index + 2), 16) / 255);
		const linear = channels.map((channel) => channel <= 0.03928
			? channel / 12.92
			: Math.pow((channel + 0.055) / 1.055, 2.4));
		const luminance = (0.2126 * linear[0]) + (0.7152 * linear[1]) + (0.0722 * linear[2]);
		return luminance > 0.5 ? "#111827" : "#ffffff";
	}

	function applyBrandTokens() {
		const brand = getBrand();
		if (!document.documentElement) return;
		document.documentElement.style.setProperty("--lx-v2-primary", brand.primaryColor || DEFAULT_PRIMARY);
		document.documentElement.style.setProperty("--lx-v2-primary-contrast", contrastText(brand.primaryColor));
	}

	function ensureBrandImage(home, brand) {
		if (!home) return;

		let img;

		if (home.tagName === "IMG") {
			img = home;
		} else {
			img = home.querySelector("img.lx-brand-image");

			if (!img) {
				img = document.createElement("img");
			}

			// Frappe may render its own framework/letter icon inside the home
			// control. Ledgix owns this slot on Ledgix routes, so replace the
			// visual contents while keeping the native clickable container.
			home.replaceChildren(img);
			home.classList.add("lx-brand-home");
		}

		img.className = "app-logo lx-brand-image";
		img.style.display = "";
		img.src = brand.symbolUrl || DEFAULT_SYMBOL_LOGO;
		img.alt = brand.name || "Ledgix";
		img.setAttribute("aria-label", brand.name || "Ledgix");
		img.style.objectFit = "contain";

		// A broken client-uploaded logo must fall back to the bundled Ledgix
		// symbol instead of exposing Frappe's framework icon.
		img.onerror = () => {
			img.onerror = null;
			img.src = DEFAULT_SYMBOL_LOGO;
		};
	}

	function applyDeskBrand() {
		const brand = getBrand();
		// The favicon represents the Ledgix product, not an individual Desk route.
		// Keep navbar/logo DOM changes scoped so native Frappe screens stay native.
		setFavicon(brand.faviconUrl || brand.symbolUrl);
		if (!isLedgixDeskRoute()) return;

		// Prefer Frappe's dedicated home control. Older/newer Desk layouts may
		// expose only navbar-brand, so retain that as a compatibility fallback.
		const navbarHomes = document.querySelectorAll(".navbar-home");
		const targets = navbarHomes.length
			? navbarHomes
			: document.querySelectorAll(".navbar-brand");

		targets.forEach((home) => ensureBrandImage(home, brand));
	}

	function applyLoginBrand() {
		if (!document.body || !document.body.classList.contains("website-login")) return;
		const brand = getBrand();

		// Website context already renders the configured logo server-side. Only
		// replace it when fresh Brand Settings are available in client state.
		if (brand.fromBoot) {
			document.querySelectorAll(".app-logo").forEach((img) => {
				img.src = brand.fullUrl || brand.symbolUrl || DEFAULT_FULL_LOGO;
				img.alt = brand.name;
			});
			setFavicon(brand.faviconUrl || brand.symbolUrl);
		}
	}

	function applyAll() {
		applyBrandTokens();
		applyDeskBrand();
		applyLoginBrand();
	}

	function installBrandInBoot(brand) {
		if (!window.frappe) return;
		frappe.boot = frappe.boot || {};
		frappe.boot.ledgix_brand = brand || {};
		frappe.boot.app_logo_url = brand?.symbol_logo_url || DEFAULT_SYMBOL_LOGO;
		frappe.boot.app_name = brand?.brand_name || "Ledgix";
	}

	function refreshBrand() {
		if (refreshPromise) return refreshPromise;
		if (!(window.frappe && frappe.call)) {
			applyAll();
			return Promise.resolve(getBrand());
		}

		refreshPromise = frappe.call({
			method: "ledgix_saas.api.brand.get_public_brand_settings",
			freeze: false,
		}).then((response) => {
			installBrandInBoot(response.message || {});
			applyAll();
			return getBrand();
		}).finally(() => {
			refreshPromise = null;
		});

		return refreshPromise;
	}

	window.LedgixBrand = {
		get: getBrand,
		apply: applyAll,
		refresh: refreshBrand,
	};

	function scheduleApply() {
		window.setTimeout(applyAll, 0);
		window.setTimeout(applyAll, 120);
		window.setTimeout(applyAll, 400);

		// Login pages do not always expose Desk bootinfo. Fetch only public visual
		// identity fields so custom logos/colors still resolve without a reload.
		if (document.body?.classList.contains("website-login") && !getBrand().fromBoot) {
			window.setTimeout(() => refreshBrand().catch(() => {}), 60);
		}
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
