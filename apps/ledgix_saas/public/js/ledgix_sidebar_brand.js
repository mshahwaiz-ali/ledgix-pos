(function () {
	"use strict";

	const LEDGIX_SYMBOL = "/assets/ledgix_saas/images/brand/Ledgix_logo_symbol.png";
	const FBR_V1_SYMBOL = "/assets/ledgix_saas/images/brand/fbr_v1.png";
	const FBR_V12_SYMBOL = "/assets/ledgix_saas/images/brand/fbr_v12.png";

	const ICON_CLASS = "lx-workspace-sidebar-brand-image";

	let scheduled = false;
	let observer = null;

	function itemIdentity(item) {
		if (!item) return "";

		const itemName = String(item.getAttribute("item-name") || "")
			.trim()
			.toLowerCase();

		const label = String(
			item.querySelector(".sidebar-item-label")?.textContent || ""
		)
			.trim()
			.toLowerCase();

		const value = itemName || label;

		if (value === "ledgix") return "ledgix";
		if (value === "fbr v1") return "fbr-v1";
		if (value === "fbr v1.2") return "fbr-v12";

		return "";
	}

	function imageFor(identity) {
		if (identity === "ledgix") return LEDGIX_SYMBOL;
		if (identity === "fbr-v1") return FBR_V1_SYMBOL;
		if (identity === "fbr-v12") return FBR_V12_SYMBOL;
		return "";
	}

	function prepareIconSlot(icon) {
		icon.style.width = "20px";
		icon.style.minWidth = "20px";
		icon.style.height = "20px";
		icon.style.flex = "0 0 20px";
		icon.style.marginRight = "7px";
		icon.style.display = "inline-flex";
		icon.style.alignItems = "center";
		icon.style.justifyContent = "center";
	}

	function applyImage(icon, src, identity) {
		if (!icon || !src) return;

		prepareIconSlot(icon);

		let img = icon.querySelector(`img.${ICON_CLASS}`);

		if (!img) {
			img = document.createElement("img");
			img.className = ICON_CLASS;
			img.alt = "";
			img.setAttribute("aria-hidden", "true");

			img.style.width = "20px";
			img.style.height = "20px";
			img.style.objectFit = "contain";
			img.style.display = "block";

			icon.appendChild(img);
		}

		Array.from(icon.children).forEach((child) => {
			if (child !== img) child.style.display = "none";
		});

		img.dataset.identity = identity;

		if (img.getAttribute("src") !== src) {
			img.src = src;
		}

		img.style.display = "block";
	}

	function applySidebarBrand() {
		scheduled = false;

		document
			.querySelectorAll(".desk-sidebar .sidebar-item-container")
			.forEach((item) => {
				const identity = itemIdentity(item);
				if (!identity) return;

				const icon = item.querySelector(".sidebar-item-icon");
				applyImage(icon, imageFor(identity), identity);
			});
	}

	function scheduleApply() {
		if (scheduled) return;
		scheduled = true;
		window.requestAnimationFrame(applySidebarBrand);
	}

	function start() {
		if (!observer && document.body) {
			observer = new MutationObserver(scheduleApply);
			observer.observe(document.body, {
				childList: true,
				subtree: true,
			});
		}

		applySidebarBrand();
	}

	if (window.frappe?.ready) {
		frappe.ready(start);
	} else if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", start, {
			once: true,
		});
	} else {
		start();
	}

	if (window.frappe?.router?.on) {
		frappe.router.on("change", scheduleApply);
	}
})();
