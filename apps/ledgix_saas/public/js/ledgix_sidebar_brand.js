(function () {
	"use strict";

	const DEFAULT_SYMBOL_LOGO = "/assets/ledgix_saas/images/brand/ledgix-symbol.svg";
	const LEDGIX_LOGO_CLASS = "lx-workspace-sidebar-brand-image";
	const FBR_ICON_CLASS = "lx-fbr-workspace-sidebar-icon";
	const FBR_V1_COLOR = "#0F766E";
	const FBR_V12_COLOR = "#B42318";
	let scheduled = false;
	let observer = null;

	function currentBrand() {
		try {
			return window.LedgixBrand?.get?.() || {};
		} catch (_error) {
			return {};
		}
	}

	function itemIdentity(item) {
		if (!item) return "";

		const itemName = String(item.getAttribute("item-name") || "")
			.trim()
			.toLowerCase();
		const label = String(item.querySelector(".sidebar-item-label")?.textContent || "")
			.trim()
			.toLowerCase();
		const value = itemName || label;

		if (value === "ledgix") return "ledgix";
		if (value === "fbr v1") return "fbr-v1";
		if (value === "fbr v1.2") return "fbr-v12";
		return "";
	}

	function sidebarItems() {
		return Array.from(
			document.querySelectorAll(".desk-sidebar .sidebar-item-container")
		).filter((item) => Boolean(itemIdentity(item)));
	}

	function prepareIconSlot(icon) {
		if (!icon) return;

		icon.style.width = "18px";
		icon.style.minWidth = "18px";
		icon.style.flex = "0 0 18px";
		icon.style.marginRight = "7px";
		icon.style.display = "inline-flex";
		icon.style.alignItems = "center";
		icon.style.justifyContent = "center";
	}

	function hideNativeChildren(icon, keep) {
		Array.from(icon.children).forEach((child) => {
			if (child !== keep) child.style.display = "none";
		});
	}

	function brandLedgixIcon(icon, brand) {
		if (!icon) return;
		prepareIconSlot(icon);

		let img = icon.querySelector(`img.${LEDGIX_LOGO_CLASS}`);
		if (!img) {
			img = document.createElement("img");
			img.className = LEDGIX_LOGO_CLASS;
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

		hideNativeChildren(icon, img);

		const src = brand.symbolUrl || DEFAULT_SYMBOL_LOGO;
		if (img.getAttribute("src") !== src) img.src = src;
		img.style.display = "block";
		img.onerror = () => {
			img.onerror = null;
			img.src = DEFAULT_SYMBOL_LOGO;
		};
	}

	function makeFiscalReceiptIcon(color, variant) {
		const ns = "http://www.w3.org/2000/svg";
		const svg = document.createElementNS(ns, "svg");
		svg.setAttribute("viewBox", "0 0 24 24");
		svg.setAttribute("width", "18");
		svg.setAttribute("height", "18");
		svg.setAttribute("aria-hidden", "true");
		svg.classList.add(FBR_ICON_CLASS);
		svg.dataset.variant = variant;
		svg.style.color = color;
		svg.style.display = "block";
		svg.style.flex = "0 0 18px";

		const receipt = document.createElementNS(ns, "path");
		receipt.setAttribute(
			"d",
			"M6.5 3.5h11v17l-1.8-1.25L14 20.5l-2-1.25-2 1.25-1.7-1.25L6.5 20.5z"
		);
		receipt.setAttribute("fill", "none");
		receipt.setAttribute("stroke", "currentColor");
		receipt.setAttribute("stroke-width", "1.8");
		receipt.setAttribute("stroke-linecap", "round");
		receipt.setAttribute("stroke-linejoin", "round");
		svg.appendChild(receipt);

		for (const [x1, y1, x2, y2] of [
			[9, 8, 15, 8],
			[9, 12, 15, 12],
			[9, 16, 13, 16],
		]) {
			const line = document.createElementNS(ns, "line");
			line.setAttribute("x1", String(x1));
			line.setAttribute("y1", String(y1));
			line.setAttribute("x2", String(x2));
			line.setAttribute("y2", String(y2));
			line.setAttribute("stroke", "currentColor");
			line.setAttribute("stroke-width", "1.8");
			line.setAttribute("stroke-linecap", "round");
			svg.appendChild(line);
		}

		if (variant === "v12") {
			const dot = document.createElementNS(ns, "circle");
			dot.setAttribute("cx", "17.5");
			dot.setAttribute("cy", "5.5");
			dot.setAttribute("r", "2.25");
			dot.setAttribute("fill", "currentColor");
			dot.setAttribute("stroke", "white");
			dot.setAttribute("stroke-width", "1");
			svg.appendChild(dot);
		}

		return svg;
	}

	function brandFbrIcon(icon, variant) {
		if (!icon) return;
		prepareIconSlot(icon);

		let svg = icon.querySelector(`svg.${FBR_ICON_CLASS}[data-variant="${variant}"]`);
		if (!svg) {
			icon.querySelectorAll(`svg.${FBR_ICON_CLASS}`).forEach((node) => node.remove());
			svg = makeFiscalReceiptIcon(
				variant === "v12" ? FBR_V12_COLOR : FBR_V1_COLOR,
				variant
			);
			icon.appendChild(svg);
		}

		hideNativeChildren(icon, svg);
		svg.style.display = "block";
	}

	function applySidebarBrand() {
		scheduled = false;
		const brand = currentBrand();

		sidebarItems().forEach((item) => {
			const icon = item.querySelector(".sidebar-item-icon");
			const identity = itemIdentity(item);
			if (identity === "ledgix") brandLedgixIcon(icon, brand);
			if (identity === "fbr-v1") brandFbrIcon(icon, "v1");
			if (identity === "fbr-v12") brandFbrIcon(icon, "v12");
		});
	}

	function scheduleApply() {
		if (scheduled) return;
		scheduled = true;
		window.requestAnimationFrame(applySidebarBrand);
	}

	function installObserver() {
		if (!document.body || observer) return;

		observer = new MutationObserver(scheduleApply);
		observer.observe(document.body, { childList: true, subtree: true });
	}

	function start() {
		installObserver();
		applySidebarBrand();
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
