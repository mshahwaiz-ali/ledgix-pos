(function () {
	"use strict";

	const DEFAULT_SYMBOL_LOGO = "/assets/ledgix_saas/images/brand/ledgix-symbol.svg";
	const LOGO_CLASS = "lx-workspace-sidebar-brand-image";
	let scheduled = false;
	let observer = null;

	function currentBrand() {
		try {
			return window.LedgixBrand?.get?.() || {};
		} catch (_error) {
			return {};
		}
	}

	function isLedgixSidebarItem(item) {
		if (!item) return false;

		const itemName = String(item.getAttribute("item-name") || "")
			.trim()
			.toLowerCase();
		const label = String(item.querySelector(".sidebar-item-label")?.textContent || "")
			.trim()
			.toLowerCase();

		return itemName === "ledgix" || label === "ledgix";
	}

	function findLedgixSidebarItems() {
		return Array.from(
			document.querySelectorAll(".desk-sidebar .sidebar-item-container")
		).filter(isLedgixSidebarItem);
	}

	function brandSidebarIcon(icon, brand) {
		if (!icon) return;

		let img = icon.querySelector(`img.${LOGO_CLASS}`);
		if (!img) {
			img = document.createElement("img");
			img.className = LOGO_CLASS;
			img.width = 18;
			img.height = 18;
			img.setAttribute("aria-hidden", "true");
			img.alt = "";
			img.style.width = "18px";
			img.style.height = "18px";
			img.style.display = "block";
			img.style.objectFit = "contain";
			img.style.flex = "0 0 18px";
			icon.appendChild(img);
		}

		// Frappe renders a framework/workspace SVG inside this exact slot.
		// Keep the native node intact for Desk behavior, but hide its visual so
		// asynchronous workspace rebuilds cannot bring the Frappe icon back.
		Array.from(icon.children).forEach((child) => {
			if (child !== img) child.style.display = "none";
		});

		const src = brand.symbolUrl || DEFAULT_SYMBOL_LOGO;
		if (img.getAttribute("src") !== src) img.src = src;
		img.style.display = "block";
		img.onerror = () => {
			img.onerror = null;
			img.src = DEFAULT_SYMBOL_LOGO;
		};
	}

	function applySidebarBrand() {
		scheduled = false;
		const brand = currentBrand();
		findLedgixSidebarItems().forEach((item) => {
			brandSidebarIcon(item.querySelector(".sidebar-item-icon"), brand);
		});
	}

	function scheduleApply() {
		if (scheduled) return;
		scheduled = true;
		window.requestAnimationFrame(applySidebarBrand);
	}

	function installObserver() {
		if (!document.body || observer) return;

		// Workspace.js builds and replaces .desk-sidebar asynchronously. Observe
		// the Desk body rather than the unrelated .sidebar-header structure.
		observer = new MutationObserver(scheduleApply);
		observer.observe(document.body, { childList: true, subtree: true });
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
