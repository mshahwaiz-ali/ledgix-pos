/* global frappe */

(() => {
	"use strict";

	const HIDDEN_CLASS = "lx-phase11-hidden";
	const GENERIC_DESK_HOME_PATHS = new Set(["/app", "/app/home", "/app/workspaces"]);
	let scheduled = false;
	let observer = null;

	function context() {
		return window.frappe?.boot?.ledgix_product || {};
	}

	function isSystemManager() {
		return context().role_level === "system";
	}

	function setVisible(element, visible) {
		if (!element) return;
		element.classList.toggle(HIDDEN_CLASS, !visible);
		element.style.display = visible ? "" : "none";
	}

	function curateSidebar() {
		const product = context();
		if (!product.curated_sidebar || isSystemManager()) return;
		document.querySelectorAll(".desk-sidebar .sidebar-item-container").forEach((item) => {
			const name = String(item.getAttribute("item-name") || "").trim().toLowerCase();
			const parent = String(item.getAttribute("item-parent") || "").trim().toLowerCase();
			setVisible(item, name === "ledgix" || parent === "ledgix");
		});
	}

	function isLedgixWorkspaceRoute() {
		const path = String(window.location.pathname || "").replace(/\/+$/, "").toLowerCase();
		return path === "/app/ledgix";
	}

	function curateWorkspace() {
		if (!isLedgixWorkspaceRoute()) return;
		const product = context();
		const visibleCards = new Set(product.visible_workspace_cards || []);
		const visibleLinks = new Set(product.visible_workspace_links || []);

		document.querySelectorAll(".links-widget-box").forEach((widget) => {
			const title = String(widget.querySelector(".widget-title .ellipsis")?.textContent || "").trim();
			const cardVisible = visibleCards.has(title) || isSystemManager();
			const block = widget.closest(".ce-block") || widget;
			if (!cardVisible) {
				setVisible(block, false);
				return;
			}
			setVisible(block, true);

			let visibleCount = 0;
			widget.querySelectorAll("a.link-item").forEach((link) => {
				const label = String(link.getAttribute("title") || link.textContent || "").trim();
				const visible = isSystemManager() || visibleLinks.has(label);
				setVisible(link, visible);
				if (visible) visibleCount += 1;
			});
			if (!visibleCount) setVisible(block, false);
		});
	}

	function routeFromGenericDeskHome() {
		const product = context();
		if (!product.landing_route || product.role_level === "none" || isSystemManager()) return;
		const path = String(window.location.pathname || "").replace(/\/+$/, "").toLowerCase();
		if (!GENERIC_DESK_HOME_PATHS.has(path)) return;
		const target = product.landing_route === "ledgix-pos" ? "ledgix-pos" : "ledgix";
		frappe.set_route(target);
	}

	function apply() {
		scheduled = false;
		routeFromGenericDeskHome();
		curateSidebar();
		curateWorkspace();
	}

	function scheduleApply() {
		if (scheduled) return;
		scheduled = true;
		window.requestAnimationFrame(apply);
	}

	function start() {
		if (!document.body) return;
		if (!observer) {
			observer = new MutationObserver(scheduleApply);
			observer.observe(document.body, { childList: true, subtree: true });
		}
		scheduleApply();
	}

	if (window.frappe?.ready) frappe.ready(start);
	else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
	else start();

	if (window.frappe?.router?.on) frappe.router.on("change", scheduleApply);
})();
