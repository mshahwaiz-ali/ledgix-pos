(function () {
	"use strict";

	const DEFAULT_SYMBOL_LOGO = "/assets/ledgix_saas/images/brand/ledgix-symbol.svg";
	let scheduled = false;

	function isLedgixRoute() {
		const path = String(window.location?.pathname || "").toLowerCase();
		if (path === "/app/ledgix" || path.startsWith("/app/ledgix-")) return true;
		if (path.startsWith("/app/business-intelligence-center")) return true;

		if (window.frappe?.get_route) {
			const route = (frappe.get_route() || []).join("/").toLowerCase();
			return route.includes("ledgix") || route.includes("business-intelligence-center");
		}
		return false;
	}

	function currentBrand() {
		try {
			return window.LedgixBrand?.get?.() || {};
		} catch (_error) {
			return {};
		}
	}

	function removeSidebarLogo() {
		document
			.querySelectorAll(".sidebar-header img.lx-sidebar-brand-image")
			.forEach((img) => img.remove());
	}

	function ensureSidebarLogo() {
		if (!isLedgixRoute()) {
			removeSidebarLogo();
			return;
		}

		const brand = currentBrand();
		const src = brand.symbolUrl || DEFAULT_SYMBOL_LOGO;
		const label = brand.name || "Ledgix";

		document.querySelectorAll(".sidebar-header").forEach((header) => {
			const anchor = header.querySelector(".title-container") || header.querySelector(".header-title");
			if (!anchor) return;

			let img = header.querySelector("img.lx-sidebar-brand-image");
			if (!img) {
				img = document.createElement("img");
				img.className = "lx-sidebar-brand-image";
				img.width = 26;
				img.height = 26;
				img.style.width = "26px";
				img.style.height = "26px";
				img.style.objectFit = "contain";
				img.style.flex = "0 0 26px";
				img.style.marginRight = "8px";
				img.style.borderRadius = "6px";

				if (anchor.classList.contains("title-container")) {
					header.insertBefore(img, anchor);
				} else if (anchor.parentNode) {
					anchor.parentNode.insertBefore(img, anchor);
				}
			}

			img.src = src;
			img.alt = label;
			img.setAttribute("aria-label", label);
			img.onerror = () => {
				img.onerror = null;
				img.src = DEFAULT_SYMBOL_LOGO;
			};
		});
	}

	function scheduleApply() {
		if (scheduled) return;
		scheduled = true;
		window.requestAnimationFrame(() => {
			scheduled = false;
			ensureSidebarLogo();
		});
	}

	function installObserver() {
		const root = document.querySelector(".body-sidebar") || document.body;
		if (!root || root.dataset.ledgixBrandObserved === "1") return;
		root.dataset.ledgixBrandObserved = "1";
		new MutationObserver(scheduleApply).observe(root, { childList: true, subtree: true });
	}

	function start() {
		installObserver();
		scheduleApply();
		window.setTimeout(scheduleApply, 120);
		window.setTimeout(scheduleApply, 400);
	}

	if (window.frappe?.ready) {
		frappe.ready(start);
	} else if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", start, { once: true });
	} else {
		start();
	}

	if (window.frappe?.router?.on) {
		frappe.router.on("change", start);
	}
})();
