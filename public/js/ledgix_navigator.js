(function () {
	"use strict";

	const pendingMounts = (window.LedgixNavigator && window.LedgixNavigator.__pendingMounts) || [];

	function getConfig() {
		const cfg = (window.LedgixNavigator && window.LedgixNavigator.config) || {};
		// Defensive compatibility: recover if an older config file nested it as { config: {...} }.
		return cfg && cfg.config && !cfg.nav_items ? cfg.config : cfg;
	}
	const state = {
		shell: null,
		nav: null,
		main: null,
		backdrop: null,
		content: null,
		mountedActiveKey: "",
		lastResolvedActiveKey: "",
		activeObserver: null,
		activeObserverTimer: null,
		mounted: false,
		collapsed: false,
		compact: false,
		mobileSheetOpen: false,
		mode: "inventory",
		modeKnown: false,
		profileDialog: null,
		navBusyUntil: 0,
		activeRefreshTimers: [],
		pendingActiveKey: "",
		pendingActivePath: "",
		pendingActiveOriginPath: "",
		pendingActiveOriginKey: "",
		pendingActiveStartedAt: 0,
		pendingActiveUntil: 0,
		groupCollapsed: {
			operations: false,
			reports: false
		}
	};

	function settings() {
		return getConfig().settings || {};
	}

	function storageValue(key, fallback) {
		if (!key) return fallback;
		try {
			const value = window.localStorage.getItem(key);
			return value === null ? fallback : value === "1";
		} catch (e) {
			return fallback;
		}
	}

	function setStorageValue(key, value) {
		if (!key) return;
		try {
			window.localStorage.setItem(key, value ? "1" : "0");
		} catch (e) {
			// Local storage can be unavailable in private browser contexts.
		}
	}

	function hasStorageValue(key) {
		if (!key) return false;
		try {
			return window.localStorage.getItem(key) !== null;
		} catch (e) {
			return false;
		}
	}

	function isTabletViewport() {
		return window.matchMedia && window.matchMedia("(min-width: 768px) and (max-width: 1024px)").matches;
	}

	function currentLocation() {
		return {
			pathname: window.location.pathname || "",
			search: window.location.search || ""
		};
	}

	function currentRoutePath() {
		const location = currentLocation();
		return `${location.pathname}${location.search}`;
	}

	function dispatchNavigatorLocationChange() {
		try {
			window.dispatchEvent(new Event("ledgix:navigator-location-change"));
		} catch (e) {
			const event = document.createEvent("Event");
			event.initEvent("ledgix:navigator-location-change", true, true);
			window.dispatchEvent(event);
		}
	}

	function installHistoryRouteWatcher() {
		if (!window.history || window.__ledgixNavigatorHistoryWatcherInstalled) return;
		window.__ledgixNavigatorHistoryWatcherInstalled = true;

		["pushState", "replaceState"].forEach(function (method) {
			const original = window.history[method];
			if (typeof original !== "function") return;

			window.history[method] = function () {
				const result = original.apply(this, arguments);
				dispatchNavigatorLocationChange();
				return result;
			};
		});
	}

	function isAllowedPage() {
		const location = currentLocation();
		const cfg = getConfig();
		const allowed = cfg.allowed_pages || [];
		return !allowed.length || allowed.includes(location.pathname);
	}

	function normalizeMode(mode) {
		const value = String(mode || "").toLowerCase();
		if (value.includes("billing")) return "billing";
		if (value.includes("inventory") || value.includes("strict")) return "inventory";
		return "";
	}

	function detectModeFromPage() {
		const dashboardMode = window.ledgix_dashboard_v2 && window.ledgix_dashboard_v2.state && window.ledgix_dashboard_v2.state.mode;
		const operationsMode = window.frappe && frappe.ledgix_operations && frappe.ledgix_operations.boot && frappe.ledgix_operations.boot.stock_control_mode;
		const reportState = document.querySelector(".lx-reports-page") && window.cur_page && window.cur_page.page && window.cur_page.page.ledgix_reports_state;
		const reportsMode = reportState && reportState.stock_control_mode;
		return normalizeMode(dashboardMode || operationsMode || reportsMode);
	}

	function loadModeFromSettings() {
		if (!window.frappe || !frappe.db || !frappe.db.get_doc) return;

		frappe.db.get_doc("Ledgix Mode Settings", "Ledgix Mode Settings")
			.then(function (doc) {
				const settingsMode = normalizeMode(doc && doc.stock_control_mode);
				if (!settingsMode) return;
				setMode(settingsMode);
			})
			.catch(function () {
				// Keep the page-local/default mode if settings are unavailable.
			});
	}

	function itemSupportsMode(item) {
		if (!item || !state.modeKnown) return true;
		const modes = item.modes || (item.inventory_only ? ["inventory"] : null);
		if (!modes || !modes.length) return true;
		return modes.includes(state.mode);
	}

	function userRoleSet() {
		const bootRoles = (window.frappe && frappe.boot && frappe.boot.user && frappe.boot.user.roles) || [];
		const sessionRoles = (window.frappe && frappe.user_roles) || [];
		return new Set([].concat(bootRoles, sessionRoles));
	}

	function isLedgixAdmin() {
		const roles = userRoleSet();
		return Boolean(
			(window.frappe && frappe.session && frappe.session.user === "Administrator") ||
			roles.has("System Manager") ||
			roles.has("Ledgix Admin")
		);
	}

	function isLedgixManagerOrAbove() {
		if (window.frappe && frappe.session && frappe.session.user === "Administrator") {
			return true;
		}
		return isLedgixAdmin() || userRoleSet().has("Ledgix Manager");
	}

	function itemSupportsRole(item) {
		if (!item) return false;
		const tier = item.tier || "manager";
		if (tier === "cashier") {
			return userRoleSet().has("Ledgix Cashier") || isLedgixManagerOrAbove();
		}
		return isLedgixManagerOrAbove();
	}

	function itemVisible(item) {
		return itemSupportsMode(item) && itemSupportsRole(item);
	}

	function getRouteKey() {
		const location = currentLocation();
		const params = new URLSearchParams(location.search);

		if (location.pathname === "/app/ledgix-dashboard") return "dashboard";
		if (location.pathname === "/app/ledgix-pos") return "pos";
		if (["/app/business-intelligence-center", "/app/business_intelligence_center", "/app/ledgix-business-intelligence", "/app/ledgix_business_intelligence"].includes(location.pathname)) return "business_intelligence";
		if (["/app/ledgix-tax-center", "/app/ledgix_tax_center", "/app/tax-center", "/app/tax_center"].includes(location.pathname)) return "tax_center";

		if (location.pathname === "/app/ledgix_operations") {
			const module = params.get("module");
			const map = {
				products: "products",
				categories: "categories",
				"product-categories": "categories",
				customers: "customers_ops",
				suppliers: "suppliers_ops",
				purchases: "purchases",
				sales: "sales",
				returns: "sales_returns",
				"sales-returns": "sales_returns",
				stock: "stock_movements",
				"stock-movements": "stock_movements",
				shifts: "shifts",
				"pos-shifts": "shifts"
			};
			return map[module] || "operations";
		}

		if (location.pathname === "/app/ledgix-reports") {
			const report = params.get("report");
			const map = {
				sales: "sales_report",
				purchases: "purchases_report",
				returns: "returns_report",
				stock: "stock_report",
				inventory: "inventory_report",
				item_full_cycle: "item_intelligence_report",
				profit: "profit_report",
				customers: "customer_statement",
				suppliers: "supplier_statement"
			};
			return map[report] || "reports";
		}

		return "";
	}

	function safeText(value) {
		const text = value === null || value === undefined ? "" : String(value);
		if (window.frappe && frappe.utils && frappe.utils.escape_html) {
			return frappe.utils.escape_html(text);
		}
		return text
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#039;");
	}

	function icon(key, className) {
		const icons = {
			dashboard: '<rect x="4" y="4" width="6" height="6" rx="1.5"></rect><rect x="14" y="4" width="6" height="6" rx="1.5"></rect><rect x="4" y="14" width="6" height="6" rx="1.5"></rect><rect x="14" y="14" width="6" height="6" rx="1.5"></rect>',
			pos: '<path d="M8 4h8v4H8V4Z"></path><path d="M6 8h12l1 5H5l1-5Z"></path><path d="M5 13h14v7H5v-7Z"></path><path d="M8 16h.01"></path><path d="M11 16h.01"></path><path d="M14 16h.01"></path><path d="M16 18h1.5"></path>',
			operations: '<circle cx="5.5" cy="8" r="1.7"></circle><circle cx="18.5" cy="8" r="1.7"></circle><circle cx="12" cy="17" r="1.7"></circle><path d="M7.2 8h9.6"></path><path d="M12 9.7v5.6"></path>',
			biCenter: '<rect x="5" y="5" width="14" height="14" rx="2"></rect><path d="M8.5 15.5v-4"></path><path d="M12 15.5V9"></path><path d="M15.5 15.5v-6.8"></path>',
			taxCenter: '<path d="M7 3.5h8.2L18.5 7v13.5H7V3.5Z"></path><path d="M15 3.5V7h3.5"></path><path d="M9.5 11h4.5"></path><path d="m10 16 4-4"></path><circle cx="10.3" cy="12.3" r=".55"></circle><circle cx="13.7" cy="15.7" r=".55"></circle>',
			reportsHub: '<path d="M7 3.5h8.2L18.5 7v13.5H7V3.5Z"></path><path d="M15 3.5V7h3.5"></path><path d="M10 11h5"></path><path d="M10 15h5"></path>',
			reports: '<path d="M7 3.5h8.2L18.5 7v13.5H7V3.5Z"></path><path d="M15 3.5V7h3.5"></path><path d="M10 11h5"></path><path d="M10 15h5"></path>',
			products: '<path d="m20 8-8-4.5L4 8l8 4.5L20 8Z"></path><path d="M4 8v8l8 4.5 8-4.5V8"></path><path d="M12 12.5v8"></path><path d="M16.5 5.9 8.5 10.4"></path>',
			categories: '<path d="M4 7h6v6H4V7Z"></path><path d="M14 7h6v6h-6V7Z"></path><path d="M4 15h6v6H4v-6Z"></path><path d="M14 15h6v6h-6v-6Z"></path>',
			purchases: '<path d="M8 4.5h8v2.2H8V4.5Z"></path><path d="M6.5 6.7h11v13H6.5v-13Z"></path><path d="M9.5 11h5"></path><path d="M12 12.5v4"></path><path d="m10.3 15 1.7 1.7 1.7-1.7"></path>',
			sales: '<path d="M8 7h8l1 13H7L8 7Z"></path><path d="M9.5 7V6a2.5 2.5 0 0 1 5 0v1"></path><path d="M10.2 12h3.7"></path><path d="M12 10.3v5.5"></path><path d="M10.5 15.8h2.3a1.3 1.3 0 0 0 0-2.6h-1.6a1.3 1.3 0 0 1 0-2.6h2.3"></path>',
			returns: '<path d="m18.5 8.5-6.5-3.7-6.5 3.7 6.5 3.7 6.5-3.7Z"></path><path d="M5.5 8.5v6.2l6.5 3.8 6.5-3.8V8.5"></path><path d="M12 12.2v6.3"></path><path d="M15.2 16H10a2.5 2.5 0 0 1 0-5h1.6"></path><path d="m10.2 9.5-2 1.5 2 1.5"></path>',
			stock: '<path d="m20 8-8-4.5L4 8l8 4.5L20 8Z"></path><path d="M4 8v8l8 4.5 8-4.5V8"></path><path d="M12 12.5v8"></path><path d="M8.5 16h-4"></path><path d="m6 13.8-2.2 2.2L6 18.2"></path><path d="M15.5 16h4"></path><path d="m18 13.8 2.2 2.2-2.2 2.2"></path>',
			shifts: '<circle cx="10" cy="8" r="3"></circle><path d="M4.8 20a5.2 5.2 0 0 1 10.1-1.7"></path><circle cx="17" cy="16.5" r="3"></circle><path d="M17 15.2v1.3l1 .7"></path>',
			wallet: '<circle cx="10" cy="8" r="3"></circle><path d="M4.8 20a5.2 5.2 0 0 1 10.1-1.7"></path><circle cx="17" cy="16.5" r="3"></circle><path d="M17 15.2v1.3l1 .7"></path>',
			salesReport: '<path d="M4 18.5h16"></path><path d="M6 16l4-4 3 3 5-7"></path><path d="M15 8h3v3"></path><path d="M7 18.5v-2.5"></path><path d="M12 18.5v-3.5"></path>',
			purchasesReport: '<path d="M8 4.5h8v2.2H8V4.5Z"></path><path d="M6.5 6.7h11v12.8H6.5V6.7Z"></path><path d="M9.5 11h5"></path><path d="M12 12.5v3.8"></path><path d="m10.4 14.8 1.6 1.6 1.6-1.6"></path><path d="M15.5 17.5h3v2.2h-3z"></path>',
			returnsReport: '<path d="M18 8.5H8a4.5 4.5 0 0 0 0 9h5"></path><path d="m10 5.5-3 3 3 3"></path>',
			stockReport: '<path d="m17.5 8-5.5-3-5.5 3 5.5 3 5.5-3Z"></path><path d="M6.5 8v5.8l5.5 3.2 5.5-3.2V8"></path><path d="M12 11v6"></path><path d="M18.5 19v-3"></path><path d="M21 19v-5"></path><path d="M16 19v-2"></path>',
			inventoryReport: '<path d="M4.5 8h15"></path><path d="M5.5 5h13v14h-13V5Z"></path><path d="M8.5 11h2.2"></path><path d="M13.3 11h2.2"></path><path d="M8.5 15h2.2"></path><path d="M13.3 15h2.2"></path>',
			itemIntelligenceReport: '<path d="m15.5 7.5-4-2.2-4 2.2 4 2.2 4-2.2Z"></path><path d="M7.5 7.5v4.7l4 2.2 4-2.2V7.5"></path><path d="M11.5 9.7v4.7"></path><circle cx="16.5" cy="16.5" r="2.4"></circle><path d="m18.3 18.3 1.7 1.7"></path>',
			profitReport: '<circle cx="10" cy="11" r="5.2"></circle><path d="M10 7.8v6.4"></path><path d="M8.3 9.3h2.5a1.4 1.4 0 0 1 0 2.8H9.2a1.4 1.4 0 0 0 0 2.8h2.5"></path><path d="M14.5 18.5 17 16l2 2"></path><path d="M17 16v5"></path>',
			customerStatement: '<circle cx="9" cy="8" r="3"></circle><path d="M4 19a5 5 0 0 1 10 0"></path><circle cx="16.5" cy="9" r="2.5"></circle><path d="M14 19a4.5 4.5 0 0 1 6 0"></path>',
			supplierStatement: '<path d="M4.5 8h9v8h-9V8Z"></path><path d="M13.5 11h3.2l2.8 3v2h-6v-5Z"></path><circle cx="8" cy="18" r="1.5"></circle><circle cx="17" cy="18" r="1.5"></circle><path d="M6.5 5h5"></path>',
			profit: '<path d="M4 18h16"></path><path d="M7 15l4-4 3 3 5-7"></path><path d="M16 7h3v3"></path>',
			plus: '<path d="M12 5v14"></path><path d="M5 12h14"></path>',
			userPlus: '<path d="M15 21a6 6 0 0 0-12 0"></path><circle cx="9" cy="7" r="4"></circle><path d="M19 8v6"></path><path d="M16 11h6"></path>',
			menu: '<path d="M4 7h16"></path><path d="M4 12h16"></path><path d="M4 17h16"></path>',
			collapse: '<path d="M15 18 9 12l6-6"></path>',
			expand: '<path d="m9 18 6-6-6-6"></path>',
			chevronDown: '<path d="m7 10 5 5 5-5"></path>',
			settings: '<path d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z"></path><path d="M19.4 15a1.8 1.8 0 0 0 .4 2l.1.1-2.1 3.6-.2-.1a1.8 1.8 0 0 0-2 .4l-.1.1h-4.2l-.1-.1a1.8 1.8 0 0 0-2-.4l-.2.1-2.1-3.6.1-.1a1.8 1.8 0 0 0 .4-2v-.2L5.3 12l2.1-2.8V9a1.8 1.8 0 0 0-.4-2l-.1-.1 2.1-3.6.2.1a1.8 1.8 0 0 0 2-.4l.1-.1h4.2l.1.1a1.8 1.8 0 0 0 2 .4l.2-.1 2.1 3.6-.1.1a1.8 1.8 0 0 0-.4 2v.2l2.1 2.8-2.1 2.8v.2Z"></path>',
			logout: '<path d="M10 17l5-5-5-5"></path><path d="M15 12H3"></path><path d="M21 4v16"></path>'
		};
		return `<span class="${safeText(className || "ledgix-nav-icon")}" data-ledgix-icon="${safeText(key)}"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">${icons[key] || icons.dashboard}</svg></span>`;
	}

	function userInfo() {
		const session = (window.frappe && frappe.session) || {};
		const boot = (window.frappe && frappe.boot) || {};
		const bootUser = boot.user || {};
		const fullName = session.user_fullname || bootUser.full_name || session.user || "Ledgix User";
		const role = (boot.user_roles || [])[0] || bootUser.role || "Desk User";
		const initials = String(fullName)
			.split(/\s+/)
			.filter(Boolean)
			.slice(0, 2)
			.map((part) => part.charAt(0).toUpperCase())
			.join("") || "L";

		return { fullName, role, initials };
	}

	function navItemTemplate(item) {
		if (!itemVisible(item)) return "";
		return `
			<a class="ledgix-nav-item" href="${safeText(item.route)}" data-ledgix-route="${safeText(item.route)}" data-ledgix-key="${safeText(item.key)}" title="${safeText(item.label)}">
				${icon(item.icon)}
				<span class="ledgix-nav-label">${safeText(item.label)}</span>
				<span class="ledgix-nav-tooltip">${safeText(item.label)}</span>
			</a>
		`;
	}

	function isCollapsibleGroup(groupKey) {
		return ["operations", "reports"].includes(String(groupKey || ""));
	}

	function groupStorageKey(groupKey) {
		return `ledgix.navigator.group.${groupKey}.collapsed`;
	}

	function loadGroupCollapseState() {
		["operations", "reports"].forEach(function (groupKey) {
			state.groupCollapsed[groupKey] = storageValue(groupStorageKey(groupKey), false);
		});
		expandActiveGroup(false);
	}

	function groupKeyForNavKey(navKey) {
		if (!navKey) return "";
		const groups = getConfig().nav_groups || [];
		for (let i = 0; i < groups.length; i += 1) {
			if ((groups[i].items || []).includes(navKey)) return groups[i].key || "";
		}
		return "";
	}

	function expandActiveGroup(persist, activeKey) {
		const groupKey = groupKeyForNavKey(activeKey || getRouteKey());
		if (!isCollapsibleGroup(groupKey)) return;
		state.groupCollapsed[groupKey] = false;
		if (persist) setStorageValue(groupStorageKey(groupKey), false);
	}

	function syncGroupCollapseClasses() {
		if (!state.shell) return;
		["operations", "reports"].forEach(function (groupKey) {
			const collapsed = Boolean(state.groupCollapsed[groupKey]);
			state.shell
				.find(`.ledgix-nav-group[data-ledgix-group="${groupKey}"]`)
				.toggleClass("is-group-collapsed", collapsed)
				.find(".ledgix-nav-group-toggle")
				.attr("aria-expanded", collapsed ? "false" : "true");
		});
	}

	function renderGroups() {
		const items = getConfig().nav_items || {};
		return (getConfig().nav_groups || []).map((group) => {
			const groupItems = (group.items || []).map((key) => items[key]).filter(itemVisible);
			if (!groupItems.length) return "";

			const groupKey = group.key || "";
			const collapsible = isCollapsibleGroup(groupKey);
			const collapsed = collapsible && Boolean(state.groupCollapsed[groupKey]);
			const labelMarkup = collapsible
				? `
					<button class="ledgix-nav-group-label ledgix-nav-group-toggle" type="button" data-ledgix-toggle-group="${safeText(groupKey)}" aria-expanded="${collapsed ? "false" : "true"}">
						<span>${safeText(group.label)}</span>
						${icon("chevronDown", "ledgix-nav-group-chevron")}
					</button>
				`
				: `<div class="ledgix-nav-group-label"><span>${safeText(group.label)}</span></div>`;

			return `
				<section class="ledgix-nav-group ${collapsible ? "is-group-collapsible" : ""} ${collapsed ? "is-group-collapsed" : ""}" data-ledgix-group="${safeText(groupKey)}">
					${labelMarkup}
					<div class="ledgix-nav-group-items">
						${groupItems.map(navItemTemplate).join("")}
					</div>
				</section>
			`;
		}).join("");
	}

	function mobileDockItemTemplate(key) {
		const item = (getConfig().nav_items || {})[key];
		if (!itemVisible(item)) return "";
		return `
			<a class="ledgix-mobile-dock-item" href="${safeText(item.route)}" data-ledgix-route="${safeText(item.route)}" data-ledgix-key="${safeText(item.key)}" title="${safeText(item.label)}">
				${icon(item.icon, "ledgix-mobile-dock-icon")}
				<span class="ledgix-mobile-dock-label">${safeText(item.label)}</span>
			</a>
		`;
	}

	function renderMobileDock() {
		return `
			<nav class="ledgix-mobile-dock" aria-label="Ledgix mobile navigation">
				${["dashboard", "pos", "operations", "reports"].map(mobileDockItemTemplate).join("")}
				<button class="ledgix-mobile-dock-item ledgix-mobile-more-btn" type="button" aria-label="Open more menu" aria-expanded="false">
					${icon("menu", "ledgix-mobile-dock-icon")}
					<span class="ledgix-mobile-dock-label">More</span>
				</button>
			</nav>
		`;
	}

	function mobileSheetItemTemplate(item) {
		if (!itemVisible(item)) return "";
		return `
			<a class="ledgix-mobile-sheet-item" href="${safeText(item.route)}" data-ledgix-route="${safeText(item.route)}" data-ledgix-key="${safeText(item.key)}" title="${safeText(item.label)}">
				${icon(item.icon, "ledgix-mobile-sheet-icon")}
				<span>${safeText(item.label)}</span>
			</a>
		`;
	}

	function renderMobileSheetGroups() {
		const items = getConfig().nav_items || {};
		return (getConfig().nav_groups || []).map((group) => {
			const groupItems = (group.items || [])
				.filter((key) => !["dashboard", "pos", "operations", "reports"].includes(key))
				.map((key) => items[key])
				.filter(itemVisible);
			if (!groupItems.length) return "";

			return `
				<section class="ledgix-mobile-sheet-section" data-ledgix-group="${safeText(group.key)}">
					<div class="ledgix-mobile-sheet-heading">${safeText(group.label)}</div>
					<div class="ledgix-mobile-sheet-grid">
						${groupItems.map(mobileSheetItemTemplate).join("")}
					</div>
				</section>
			`;
		}).join("");
	}

	function renderMobileSheetProfile() {
		const user = userInfo();
		const isAdmin = isLedgixAdmin();
		return `
			<section class="ledgix-mobile-sheet-profile">
				<div class="ledgix-mobile-profile-card">
					<span class="ledgix-nav-avatar">${safeText(user.initials)}</span>
					<span class="ledgix-mobile-profile-copy">
						<strong>${safeText(user.fullName)}</strong>
						<span>${safeText(user.role)}</span>
					</span>
					
				</div>
				<div class="ledgix-mobile-profile-actions">
					<button type="button" data-ledgix-profile-action="profile">${icon("userPlus", "ledgix-mobile-action-icon")}<span>Profile</span></button>
					${isAdmin ? `<button type="button" data-ledgix-setting-action="theme">${icon("settings", "ledgix-mobile-action-icon")}<span>Theme</span></button>` : ""}
					<button type="button" data-ledgix-profile-action="logout">${icon("logout", "ledgix-mobile-action-icon")}<span>Logout</span></button>
				</div>
			</section>
		`;
	}

	function renderMobileSheet() {
		return `
			<div class="ledgix-mobile-sheet-backdrop" hidden></div>
			<section class="ledgix-mobile-sheet" aria-label="Ledgix mobile menu" aria-hidden="true">
				<div class="ledgix-mobile-sheet-handle" aria-hidden="true"></div>
				<div class="ledgix-mobile-sheet-header">
					<div>
						<strong>${safeText((getConfig().app || {}).name || "Ledgix")}</strong>
						<span>${safeText((getConfig().app || {}).tagline || "Retail operations")}</span>
					</div>
					<button class="ledgix-mobile-sheet-close" type="button" aria-label="Close menu">Close</button>
				</div>
				<div class="ledgix-mobile-sheet-body">
					${renderMobileSheetGroups()}
					${renderMobileSheetProfile()}
				</div>
			</section>
		`;
	}

	function renderProfile() {
		const user = userInfo();
		const isAdmin = isLedgixAdmin();
		return `
			<section class="ledgix-nav-profile">
				<button class="ledgix-nav-profile-button" type="button" aria-expanded="false">
					<span class="ledgix-nav-avatar">${safeText(user.initials)}</span>
					<span class="ledgix-nav-profile-copy">
						<strong>${safeText(user.fullName)}</strong>
						<span>${safeText(user.role)}</span>
					</span>
				</button>
				<div class="ledgix-nav-profile-menu" hidden>
					<button type="button" data-ledgix-profile-action="profile">Profile</button>
					${isAdmin ? `<button type="button" data-ledgix-setting-action="theme">Theme</button>` : ""}
					<button type="button" data-ledgix-profile-action="logout">Logout</button>
				</div>
			</section>
		`;
	}


	function renderModeIndicator() {
		const mode = state.mode === "billing" ? "billing" : "inventory";
		const label = mode === "billing" ? "Billing" : "Inventory";
		const ariaLabel = `${label} Mode`;
		return `
			<span class="ledgix-nav-mode-indicator ledgix-nav-brand-mode-indicator" data-ledgix-mode="${safeText(mode)}" title="${safeText(ariaLabel)}" aria-label="${safeText(ariaLabel)}">
				<span class="ledgix-nav-mode-indicator-dot" aria-hidden="true"></span>
				<span class="ledgix-nav-mode-indicator-label">${safeText(label)}</span>
			</span>
		`;
	}

	function getBrand() {
		const FRAPPE_DEFAULT_LOGO = "/assets/frappe/images/frappe-framework-logo.svg";
		const boot = (window.frappe && frappe.boot) || {};
		const bootBrand = boot.ledgix_brand || {};
		const app = (getConfig().app || {});
		const deskLogo = boot.app_logo_url || FRAPPE_DEFAULT_LOGO;

		return {
			name: bootBrand.brand_name || app.name || boot.app_name || "Ledgix",
			tagline: bootBrand.brand_tagline || app.tagline || "Retail operations",
			symbolUrl: bootBrand.has_custom_symbol ? bootBrand.symbol_logo_url : deskLogo,
		};
	}

	function renderBrandMark() {
		const brand = getBrand();
		return `
			<div class="ledgix-nav-mark is-image-mark" title="${safeText(brand.name)}">
				<img class="ledgix-nav-mark-image" src="${safeText(brand.symbolUrl)}" alt="${safeText(brand.name)}">
			</div>
		`;
	}

	function renderNav() {
		const brand = getBrand();
		return `
			<aside class="ledgix-app-nav" aria-label="Ledgix navigation">
				<div class="ledgix-nav-brand">
					${renderBrandMark()}
					<div class="ledgix-nav-brand-copy">
						<strong>${safeText(brand.name)}</strong>
						<span>${safeText(brand.tagline)}</span>
					</div>
					${renderModeIndicator()}
					<button class="ledgix-nav-collapse" type="button" aria-label="Toggle navigation">${icon("collapse")}</button>
				</div>
				<div class="ledgix-nav-scroll">
					${renderGroups()}
				</div>
				${renderProfile()}
			</aside>
			${renderMobileDock()}
			${renderMobileSheet()}
		`;
	}

	function normalizeContent(content) {
		if (!content) return null;
		if (content.jquery) return content.first();
		if (content instanceof Element) return $(content);
		return $(content).first();
	}

	function cleanupFrappePageShell(content) {
		const $content = normalizeContent(content);
		if (!$content || !$content.length) return null;

		const $pageContainer = $content.closest(".page-container");
		if (!$pageContainer.length) return null;

		$pageContainer
			.addClass("ledgix-clean-page-shell")
			.find(".page-head, .page-head-content, .page-title, .title-area")
			.hide();

		$pageContainer
			.find(".layout-main-section, .layout-main-section-wrapper, .page-body")
			.addClass("ledgix-clean-layout-shell");

		$content
			.closest(".layout-main-section, .layout-main-section-wrapper, .page-body")
			.addClass("ledgix-clean-layout-shell");

		return $pageContainer;
	}

	function isLedgixDeskRoute() {
		const location = currentLocation();
		const allowed = [
			"/app/ledgix-dashboard",
			"/app/ledgix-pos",
			"/app/ledgix_operations",
			"/app/ledgix-reports",
			"/app/ledgix-tax-center",
			"/app/ledgix_tax_center",
			"/app/tax-center",
			"/app/tax_center",
			"/app/business-intelligence-center",
			"/app/business_intelligence_center",
			"/app/ledgix-business-intelligence",
			"/app/ledgix_business_intelligence",
			"/app/quick-item-scan"
		];

		return allowed.includes(location.pathname);
	}

	function isLedgixUser() {
		if (window.frappe && frappe.session && frappe.session.user === "Administrator") {
			return true;
		}
		const roles = userRoleSet();
		return (
			roles.has("System Manager") ||
			roles.has("Ledgix Admin") ||
			roles.has("Ledgix Manager") ||
			roles.has("Ledgix Cashier")
		);
	}

	function shouldUseLedgixShell() {
		if (!isLedgixUser()) return false;
		return isLedgixDeskRoute();
	}

	function isShellAttached() {
		return Boolean(state.shell && state.shell.length && document.body.contains(state.shell[0]));
	}

	function resetShellStateIfDetached() {
		if (!state.shell || !state.shell.length) return;
		if (document.body.contains(state.shell[0])) return;

		state.shell = null;
		state.nav = null;
		state.main = null;
		state.backdrop = null;
		state.content = null;
		state.mounted = false;
	}

	function findDeskMountContent() {
		const ledgixRoots = [
			".ledgix-operations-page",
			".lx-ops-shell",
			".lx-reports-page",
			".ledgix-pos-app",
			".lx-bi-page",
			".lx-tax-shell",
			".ledgix-dashboard-v2",
			".quick-item-scan-page",
			".quick-item-scan"
		];

		for (let i = 0; i < ledgixRoots.length; i += 1) {
			const $el = $(ledgixRoots[i]).filter(":visible").first();
			if ($el.length && !$el.closest(".ledgix-app-shell").length) {
				return $el;
			}
		}

		return null;
	}

	function syncDeskShellMount() {
		if (!shouldUseLedgixShell()) {
			syncLedgixAppChrome();
			return;
		}

		resetShellStateIfDetached();

		const $content = findDeskMountContent();
		if (!$content || !$content.length) {
			syncLedgixAppChrome();
			return;
		}

		if ($content.closest(".ledgix-app-shell").length) {
			syncLedgixAppChrome();
			scheduleActiveRefresh();
			return;
		}

		if (isLedgixDeskRoute()) {
			const ledgixOnly = $content.is(".ledgix-operations-page, .lx-ops-shell, .lx-reports-page, .ledgix-pos-app, .lx-bi-page, .lx-tax-shell, .ledgix-dashboard-v2, .quick-item-scan-page, .quick-item-scan");
			if (!ledgixOnly) {
				syncLedgixAppChrome();
				return;
			}
		}

		mount({ content: $content });
	}

	function scheduleDeskShellMount() {
		[0, 80, 180, 360, 700, 1200].forEach(function (delay) {
			window.setTimeout(syncDeskShellMount, delay);
		});
	}

	function enableLedgixAppChrome() {
		if (!document.body) return;
		document.body.classList.add("ledgix-hide-frappe-navbar");
		document.documentElement.classList.add("ledgix-hide-frappe-navbar");
	}

	function disableLedgixAppChrome() {
		if (!document.body) return;
		document.body.classList.remove("ledgix-hide-frappe-navbar");
		document.documentElement.classList.remove("ledgix-hide-frappe-navbar");
	}

	function syncLedgixAppChrome() {
		if (shouldUseLedgixShell() && isShellAttached()) {
			enableLedgixAppChrome();
			return;
		}
		if (isLedgixDeskRoute()) {
			enableLedgixAppChrome();
			return;
		}
		disableLedgixAppChrome();
	}

	function mountCurrentPageContent(content) {
		const $content = normalizeContent(content);
		if (!$content || !$content.length || !state.main) return null;

		if ($content.closest(".ledgix-app-main").length) {
			return $content;
		}

		state.main.append($content);
		state.content = $content;
		return $content;
	}

	function applyState() {
		if (!state.shell) return;

		state.shell
			.toggleClass("is-collapsed", state.collapsed)
			.toggleClass("is-compact", state.compact)
			.toggleClass("ledgix-mobile-sheet-open", state.mobileSheetOpen);

		state.shell.find(".ledgix-nav-collapse").attr("aria-label", state.collapsed ? "Expand navigation" : "Collapse navigation");

		const mode = state.mode === "billing" ? "billing" : "inventory";
		const modeLabel = mode === "billing" ? "Billing" : "Inventory";
		state.shell.find(".ledgix-nav-mode-indicator")
			.attr("data-ledgix-mode", mode)
			.attr("title", `${modeLabel} Mode`)
			.attr("aria-label", `${modeLabel} Mode`);
		state.shell.find(".ledgix-nav-mode-indicator-label").text(modeLabel);

		if (state.backdrop) {
			state.backdrop.prop("hidden", !state.mobileSheetOpen);
		}
		state.shell.find(".ledgix-mobile-sheet").attr("aria-hidden", state.mobileSheetOpen ? "false" : "true");
		state.shell.find(".ledgix-mobile-more-btn").attr("aria-expanded", state.mobileSheetOpen ? "true" : "false");
	}

	function routeToKey(route) {
		if (!route) return "";
		const anchor = document.createElement("a");
		anchor.href = route;
		const params = new URLSearchParams(anchor.search || "");

		if (anchor.pathname === "/app/ledgix-dashboard") return "dashboard";
		if (anchor.pathname === "/app/ledgix-pos") return "pos";
		if (["/app/business-intelligence-center", "/app/business_intelligence_center", "/app/ledgix-business-intelligence", "/app/ledgix_business_intelligence"].includes(anchor.pathname)) return "business_intelligence";
		if (["/app/ledgix-tax-center", "/app/ledgix_tax_center", "/app/tax-center", "/app/tax_center"].includes(anchor.pathname)) return "tax_center";
		if (anchor.pathname === "/app/ledgix_operations") {
			const module = params.get("module");
			const map = {
				products: "products",
				customers: "customers_ops",
				suppliers: "suppliers_ops",
				purchases: "purchases",
				sales: "sales",
				returns: "sales_returns",
				"sales-returns": "sales_returns",
				stock: "stock_movements",
				"stock-movements": "stock_movements",
				shifts: "shifts",
				"pos-shifts": "shifts"
			};
			return map[module] || "operations";
		}
		if (anchor.pathname === "/app/ledgix-reports") {
			const report = params.get("report");
			const map = {
				sales: "sales_report",
				purchases: "purchases_report",
				returns: "returns_report",
				stock: "stock_report",
				inventory: "inventory_report",
				item_full_cycle: "item_intelligence_report",
				profit: "profit_report",
				customers: "customer_statement",
				suppliers: "supplier_statement"
			};
			return map[report] || "reports";
		}
		return "";
	}

	function normalizeRouteName(value) {
		return String(value || "")
			.toLowerCase()
			.replace(/^\/app\//, "")
			.replace(/^page\//, "")
			.replace(/_/g, "-")
			.trim();
	}

	function routeNameToKey(routeName, params) {
		const name = normalizeRouteName(routeName);
		params = params || new URLSearchParams(currentLocation().search || "");

		if (name === "ledgix-dashboard") return "dashboard";
		if (name === "ledgix-pos") return "pos";
		if (["business-intelligence-center", "ledgix-business-intelligence", "business-intelligence"].includes(name)) return "business_intelligence";
		if (["ledgix-tax-center", "tax-center", "tax-compliance-center"].includes(name)) return "tax_center";
		if (name === "quick-item-scan") return "products";

		if (name === "ledgix-operations") {
			const module = params.get("module");
			const map = {
				products: "products",
				customers: "customers_ops",
				suppliers: "suppliers_ops",
				purchases: "purchases",
				sales: "sales",
				returns: "sales_returns",
				"sales-returns": "sales_returns",
				stock: "stock_movements",
				"stock-movements": "stock_movements",
				shifts: "shifts",
				"pos-shifts": "shifts"
			};
			return map[module] || "operations";
		}

		if (name === "ledgix-reports") {
			const report = params.get("report");
			const map = {
				sales: "sales_report",
				purchases: "purchases_report",
				returns: "returns_report",
				stock: "stock_report",
				inventory: "inventory_report",
				item_full_cycle: "item_intelligence_report",
				profit: "profit_report",
				customers: "customer_statement",
				suppliers: "supplier_statement"
			};
			return map[report] || "reports";
		}

		return "";
	}

	function getFrappeRouteKey() {
		if (!window.frappe) return "";

		let route = null;
		try {
			if (typeof frappe.get_route === "function") route = frappe.get_route();
		} catch (e) {
			route = null;
		}

		if (!route && frappe.router) {
			route = frappe.router.current_route || frappe.router.route || null;
		}

		if (typeof route === "string") route = route.split("/");
		if (Array.isArray(route) && route.length) {
			const key = routeNameToKey(route[0]);
			if (key) return key;
		}

		const curPage = window.cur_page && (window.cur_page.page_name || (window.cur_page.page && window.cur_page.page.page_name));
		return routeNameToKey(curPage);
	}

	function elementIsVisible(element) {
		if (!element || element.nodeType !== 1) return false;
		if (!document.documentElement.contains(element)) return false;
		const style = window.getComputedStyle ? window.getComputedStyle(element) : null;
		if (style && (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0)) return false;
		const rect = element.getBoundingClientRect ? element.getBoundingClientRect() : null;
		if (!rect) return true;
		return rect.width > 0 && rect.height > 0;
	}

	function getMainCandidates() {
		const candidates = [];
		function add(element) {
			if (!element || candidates.includes(element)) return;
			candidates.push(element);
		}

		try {
			const curWrapper = window.cur_page && window.cur_page.page && window.cur_page.page.wrapper;
			if (curWrapper) {
				const main = curWrapper.querySelector && curWrapper.querySelector(".ledgix-app-main");
				add(main || curWrapper);
			}
		} catch (e) {
			// Ignore Frappe wrapper lookup failures.
		}

		[
			".ledgix-app-shell .ledgix-app-main",
			".page-container .layout-main-section",
			".page-container .page-body",
			"main.ledgix-app-main"
		].forEach(function (selector) {
			document.querySelectorAll(selector).forEach(add);
		});

		return candidates
			.filter(elementIsVisible)
			.sort(function (a, b) {
				const ar = a.getBoundingClientRect();
				const br = b.getBoundingClientRect();
				return (br.width * br.height) - (ar.width * ar.height);
			});
	}

	function shouldPreferUrlNavKey(urlKey, contentKey) {
		if (!urlKey) return false;
		if (!contentKey || urlKey === contentKey) return true;

		const parentGroup = groupKeyForNavKey(urlKey);
		if (!parentGroup || !isCollapsibleGroup(parentGroup)) return false;

		// Submodule URL (?module=products, ?report=sales) beats parent shell match.
		return contentKey === parentGroup;
	}

	function resolveNavActiveKey(urlKey, contentKey) {
		const normalizedUrl = urlKey || "";
		const normalizedContent = contentKey || "";

		if (shouldPreferUrlNavKey(normalizedUrl, normalizedContent)) {
			return normalizedUrl;
		}

		return normalizedContent || normalizedUrl;
	}

	function detectKeyFromText(text) {
		const value = String(text || "").replace(/\s+/g, " ").trim();
		if (!value) return "";

		if (/business intelligence center|inventory health, profit, returns, stock flow|truth timeline/i.test(value)) return "business_intelligence";
		if (/tax\s*&\s*compliance center|ledgix compliance|invoice tax snapshots|return snapshots|fbr control|advanced tax setup/i.test(value)) return "tax_center";
		if (/reports\s*&\s*analytics|ledgix reports|report intelligence|sales report records|no sales records found/i.test(value)) {
			const routeKey = getRouteKey();
			if (
				[
					"sales_report",
					"purchases_report",
					"returns_report",
					"stock_report",
					"inventory_report",
					"item_intelligence_report",
					"profit_report",
					"customer_statement",
					"supplier_statement",
				].includes(routeKey)
			) {
				return routeKey;
			}
			return "reports";
		}
		if (/ledgix operations center|operations center|daily business operations workspace/i.test(value)) {
			const routeKey = getRouteKey();
			if (["products", "categories", "purchases", "sales", "sales_returns", "stock_movements", "shifts"].includes(routeKey)) return routeKey;
			return "operations";
		}
		if (/ledgix pos|point of sale|cart summary|checkout|cashier/i.test(value)) return "pos";
		if (/ledgix dashboard|dashboard|sales today|inventory snapshot/i.test(value)) return "dashboard";

		return "";
	}

	function detectActiveKeyFromVisibleDom() {
		const candidates = getMainCandidates();
		for (const element of candidates) {
			const key = detectKeyFromText(element.innerText || element.textContent || "");
			if (key) return key;
		}
		return "";
	}

	function contentMatches($content, selector) {
		if (!$content || !$content.length || !selector) return false;
		try {
			return $content.is(selector) || $content.find(selector).length > 0;
		} catch (e) {
			return false;
		}
	}

	function detectActiveKeyFromContent(content, options) {
		options = options || {};
		const explicitKey = options.activeKey || options.active || options.navKey || options.pageKey;
		if (explicitKey && getConfig().nav_items && getConfig().nav_items[explicitKey]) return explicitKey;

		const routeKey = routeToKey(options.route || options.path || "");
		if (routeKey) return routeKey;

		const urlKey = getRouteKey();
		const urlParentGroup = groupKeyForNavKey(urlKey);
		if (urlParentGroup && isCollapsibleGroup(urlParentGroup) && urlKey !== urlParentGroup) {
			return urlKey;
		}

		const $content = normalizeContent(content);
		if (!$content || !$content.length) return "";

		const checks = [
			{ key: "business_intelligence", selector: ".lx-bi-page, .lx-bi-shell, .ledgix-bi-page, .ledgix-business-intelligence-page, .business-intelligence-center" },
			{ key: "tax_center", selector: ".ledgix-tax-center-page, .lx-tax-page, .lx-tax-shell, .lx-tax-center, .tax-compliance-center" },
			{ key: "operations", selector: ".ledgix-operations-page, .ledgix-operations-center, .lx-operations-page, .lx-ops-shell" },
			{ key: "reports", selector: ".lx-reports-page, .lx-reports-shell, .ledgix-reports-page" },
			{ key: "dashboard", selector: ".ledgix-dashboard-page, .ledgix-dashboard-v2, .lx-dashboard-page" },
			{ key: "pos", selector: ".ledgix-pos-page, .ledgix-pos-shell, .lx-pos-page" }
		];

		for (const item of checks) {
			if (contentMatches($content, item.selector)) return item.key;
		}

		return "";
	}

	function setActiveKey(activeKey) {
		const $shells = state.shell && state.shell.length ? $(".ledgix-app-shell").add(state.shell) : $(".ledgix-app-shell");
		if (!$shells.length) return;
		$shells.find(".ledgix-nav-item, .ledgix-mobile-dock-item, .ledgix-mobile-sheet-item").each(function () {
			const $item = $(this);
			const key = $item.attr("data-ledgix-key");
			if (!key) return;
			const active = key === activeKey;
			$item.toggleClass("is-active", active).attr("aria-current", active ? "page" : null);
		});
	}

	function setPendingActive(route, activeKey) {
		const now = Date.now();
		state.pendingActiveKey = activeKey || "";
		state.pendingActivePath = route || "";
		state.pendingActiveOriginPath = currentRoutePath();
		state.pendingActiveOriginKey = detectActiveKeyFromVisibleDom() || getFrappeRouteKey() || getRouteKey() || state.lastResolvedActiveKey || "";
		state.pendingActiveStartedAt = now;
		state.pendingActiveUntil = now + 3200;
	}

	function clearPendingActive() {
		state.pendingActiveKey = "";
		state.pendingActivePath = "";
		state.pendingActiveOriginPath = "";
		state.pendingActiveOriginKey = "";
		state.pendingActiveStartedAt = 0;
		state.pendingActiveUntil = 0;
	}

	function getMountedActiveKey() {
		if (!state.mountedActiveKey) return "";
		if (state.content && state.content.length && document.documentElement.contains(state.content[0])) {
			return state.mountedActiveKey;
		}
		return "";
	}

	function getEffectiveActiveKey() {
		const urlKey = getRouteKey();
		const frappeKey = getFrappeRouteKey();
		const visibleKey = detectActiveKeyFromVisibleDom();
		const contentKey = visibleKey || getMountedActiveKey();
		const routeKey = frappeKey || urlKey;
		const currentPath = currentRoutePath();
		const now = Date.now();

		if (!state.pendingActiveKey) {
			return resolveNavActiveKey(routeKey, contentKey);
		}

		// The visible page changed after the click. This is the strongest signal in
		// Frappe desk, where URL/router updates can lag one click behind.
		if (contentKey && contentKey !== state.pendingActiveOriginKey) {
			clearPendingActive();
			return resolveNavActiveKey(routeKey, contentKey);
		}

		if (routeKey === state.pendingActiveKey || currentPath === state.pendingActivePath) {
			clearPendingActive();
			return routeKey || state.pendingActiveKey;
		}

		if (!contentKey && routeKey && routeKey !== state.pendingActiveOriginKey) {
			clearPendingActive();
			return routeKey;
		}

		if (now > state.pendingActiveUntil) {
			clearPendingActive();
			return resolveNavActiveKey(routeKey, contentKey);
		}

		// For the first moment after click, show instant feedback while the old page is
		// still visible. After that, avoid forcing stale pending state forever.
		if (now - state.pendingActiveStartedAt < 650) return state.pendingActiveKey;

		return resolveNavActiveKey(routeKey, contentKey) || state.pendingActiveKey;
	}

	function updateActiveState() {
		const activeKey = getEffectiveActiveKey();
		state.lastResolvedActiveKey = activeKey || state.lastResolvedActiveKey || "";
		setActiveKey(activeKey);
		expandActiveGroup(false, activeKey);
		syncGroupCollapseClasses();
	}

	function rerenderNavigation() {
		if (!state.shell) return;
		const brand = getBrand();
		if (state.nav && state.nav.length) {
			state.nav.find(".ledgix-nav-mark-image").attr({ src: brand.symbolUrl, alt: brand.name });
			state.nav.find(".ledgix-nav-brand-copy strong").text(brand.name);
			state.nav.find(".ledgix-nav-brand-copy span").text(brand.tagline);
		}
		state.shell.find(".ledgix-nav-scroll").html(renderGroups());
		state.shell.find(".ledgix-nav-profile").replaceWith(renderProfile());
		state.shell.find(".ledgix-mobile-dock").replaceWith(renderMobileDock());
		state.shell.find(".ledgix-mobile-sheet-backdrop, .ledgix-mobile-sheet").remove();
		state.shell.append(renderMobileSheet());
		state.backdrop = state.shell.find(".ledgix-mobile-sheet-backdrop");
		updateActiveState();
	}

	function refreshBrand() {
		rerenderNavigation();
	}

	function setMode(mode) {
		const normalized = normalizeMode(mode);
		if (!normalized) return;
		const changed = state.mode !== normalized || !state.modeKnown;
		state.mode = normalized;
		state.modeKnown = true;
		if (changed) {
			rerenderNavigation();
			applyState();
		}
	}

	function isMobileNavigatorViewport() {
		return window.matchMedia && window.matchMedia("(max-width: 1024px)").matches;
	}

	function installActiveDomObserver() {
		if (state.activeObserver || !window.MutationObserver || !document.body) return;

		state.activeObserver = new MutationObserver(function () {
			if (state.activeObserverTimer) window.clearTimeout(state.activeObserverTimer);
			state.activeObserverTimer = window.setTimeout(function () {
				state.activeObserverTimer = null;
				updateActiveState();
			}, 80);
		});

		state.activeObserver.observe(document.body, {
			childList: true,
			subtree: true,
			attributes: true,
			attributeFilter: ["class", "style", "hidden", "aria-hidden"]
		});
	}

	function clearActiveRefreshTimers() {
		(state.activeRefreshTimers || []).forEach(function (timer) {
			window.clearTimeout(timer);
		});
		state.activeRefreshTimers = [];
	}

	function scheduleActiveRefresh() {
		clearActiveRefreshTimers();
		[0, 40, 90, 160, 260, 420, 700, 1100, 1700, 2600, 3800].forEach(function (delay) {
			state.activeRefreshTimers.push(window.setTimeout(updateActiveState, delay));
		});
	}

	function navigateTo(route) {
		if (!route) return;

		const targetKey = routeToKey(route);
		if (targetKey) {
			setPendingActive(route, targetKey);
			setActiveKey(targetKey);
			expandActiveGroup(false, targetKey);
			syncGroupCollapseClasses();
		}

		state.mobileSheetOpen = false;
		applyState();
		scheduleActiveRefresh();

		if (currentRoutePath() === route) {
			clearPendingActive();
			updateActiveState();
			return;
		}

		// Query-based Ledgix submodules must stay as real URLs.
		// Passing `ledgix_operations?module=products` or `ledgix-reports?report=purchases`
		// into frappe.set_route makes Frappe search for a page with the query string in its name.
		// Use browser navigation for these routes so Frappe loads the base page correctly.
		if (route.indexOf("?") !== -1) {
			window.location.assign(route);
			return;
		}

		if (isMobileNavigatorViewport() && route.indexOf("/app/ledgix") === 0) {
			window.location.assign(route);
			return;
		}

		if (window.frappe && frappe.set_route) {
			try {
				frappe.set_route(route.replace(/^\/app\//, ""));
				return;
			} catch (e) {
				// Fall through to safe browser navigation.
			}
		}

		window.location.assign(route);
	}

	function closePanels() {
		if (!state.shell) return;
		state.shell.find(".ledgix-nav-profile-menu").prop("hidden", true);
		state.shell.find(".ledgix-nav-profile-button").attr("aria-expanded", "false");
	}

	function closeMobileSheet() {
		if (!state.mobileSheetOpen) return;
		state.mobileSheetOpen = false;
		applyState();
	}

	function openProfileModal() {
		if (!window.frappe || !frappe.ui || !frappe.ui.Dialog) return;
		const user = userInfo();
		const email = (frappe.session && frappe.session.user) || "";
		const dialog = new frappe.ui.Dialog({
			title: "Profile",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "profile",
					options: `
						<div class="ledgix-nav-modal ledgix-nav-profile-modal">
							<div class="ledgix-nav-modal-avatar">${safeText(user.initials)}</div>
							<div class="ledgix-nav-modal-copy">
								<strong>${safeText(user.fullName)}</strong>
								<span>${safeText(email)}</span>
								<em>${safeText(user.role)}</em>
							</div>
						</div>
					`
				}
			]
		});
		state.profileDialog = dialog;
		dialog.show();
	}


	const DISABLED_THEME_SETTINGS = {
		enable_custom_accent: 0,
		primary_accent_color: "",
		accent_hover: "",
		accent_soft: "",
		accent_soft_2: "",
		accent_border: "",
		accent_ring: "",
		accent_rgb: "",
		accent_soft_hover: "",
		accent_border_strong: "",
		accent_track_bg: "",
		accent_track_border: ""
	};

	const THEME_CSS_VARS = [
		"--lx-accent",
		"--accent",
		"--ledgix-accent",
		"--ledgix-primary",
		"--primary",
		"--lx-page-accent",
		"--bi-accent",
		"--lx-accent-hover",
		"--lx-page-accent-hover",
		"--accent-hover",
		"--lx-accent-soft",
		"--lx-page-accent-soft",
		"--accent-soft",
		"--lx-accent-soft-hover",
		"--lx-accent-soft-2",
		"--lx-page-accent-soft-2",
		"--accent-soft-2",
		"--lx-accent-border",
		"--lx-page-accent-border",
		"--accent-border",
		"--lx-accent-border-strong",
		"--lx-accent-ring",
		"--lx-page-accent-ring",
		"--accent-ring",
		"--lx-accent-rgb",
		"--ledgix-accent-rgb",
		"--accent-rgb",
		"--lx-accent-track-bg",
		"--lx-accent-track-border",
		"--lx-active-bg",
		"--lx-active-hover",
		"--lx-active-soft-bg",
		"--lx-active-soft-hover",
		"--lx-active-border",
		"--lx-accent-surface",
		"--lx-accent-surface-strong",
		"--lx-accent-shadow",
		"--lx-category-active-bg",
		"--lx-payment-active-bg",
		"--lx-split-active-bg",
		"--lx-modal-primary-bg",
		"--lx-modal-primary-hover"
	];

	function hexToRgb(hex) {
		const primary = normalizeHex(hex);
		if (!primary) return null;
		return {
			r: parseInt(primary.slice(1, 3), 16),
			g: parseInt(primary.slice(3, 5), 16),
			b: parseInt(primary.slice(5, 7), 16)
		};
	}

	function rgbString(hex) {
		const rgb = hexToRgb(hex);
		return rgb ? `${rgb.r}, ${rgb.g}, ${rgb.b}` : "";
	}

	function mixHex(hex, target, percentTarget) {
		const rgb = hexToRgb(hex);
		if (!rgb) return "";
		const targetRgb = target === "black"
			? { r: 0, g: 0, b: 0 }
			: { r: 255, g: 255, b: 255 };
		const p = Math.max(0, Math.min(100, Number(percentTarget))) / 100;
		const out = {
			r: Math.round(rgb.r * (1 - p) + targetRgb.r * p),
			g: Math.round(rgb.g * (1 - p) + targetRgb.g * p),
			b: Math.round(rgb.b * (1 - p) + targetRgb.b * p)
		};
		return `#${[out.r, out.g, out.b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
	}

	function rgbaFromHex(hex, alpha) {
		const rgb = rgbString(hex);
		return rgb ? `rgba(${rgb}, ${alpha})` : "";
	}

	function normalizeThemeSettings(settings) {
		const source = settings || {};
		const primary = normalizeHex(source.primary_accent_color);
		const explicitlyDisabled = source.enable_custom_accent === 0 || source.enable_custom_accent === false || source.enable_custom_accent === "0";
		const enabled = primary && !explicitlyDisabled ? 1 : 0;

		if (!enabled) {
			return Object.assign({}, DISABLED_THEME_SETTINGS);
		}

		return {
			enable_custom_accent: 1,
			primary_accent_color: primary,
			accent_hover: normalizeHex(source.accent_hover) || mixHex(primary, "black", 18),
			accent_soft: source.accent_soft || rgbaFromHex(primary, 0.10),
			accent_soft_2: source.accent_soft_2 || rgbaFromHex(primary, 0.16),
			accent_border: source.accent_border || rgbaFromHex(primary, 0.28),
			accent_ring: source.accent_ring || rgbaFromHex(primary, 0.18),
			accent_rgb: source.accent_rgb || rgbString(primary),
			accent_soft_hover: source.accent_soft_hover || rgbaFromHex(primary, 0.14),
			accent_border_strong: source.accent_border_strong || rgbaFromHex(primary, 0.42),
			accent_track_bg: source.accent_track_bg || rgbaFromHex(primary, 0.12),
			accent_track_border: source.accent_track_border || rgbaFromHex(primary, 0.30)
		};
	}

	function saveThemeToCache(settings) {
		const normalized = normalizeThemeSettings(settings);
		try {
			if (normalized.enable_custom_accent && normalized.primary_accent_color) {
				window.localStorage.setItem("ledgix_theme_settings", JSON.stringify(normalized));
				window.localStorage.setItem("ledgix_theme_primary_accent", normalized.primary_accent_color);
				window.localStorage.setItem("ledgix_pos_theme", JSON.stringify(normalized));
			} else {
				window.localStorage.removeItem("ledgix_theme_settings");
				window.localStorage.removeItem("ledgix_theme_primary_accent");
				window.localStorage.removeItem("ledgix_pos_theme");
			}
		} catch (e) {}
		return normalized;
	}

	function readThemeCache() {
		try {
			const cached = window.localStorage.getItem("ledgix_theme_settings");
			if (cached) {
				const normalized = normalizeThemeSettings(JSON.parse(cached));
				return normalized.enable_custom_accent && normalized.primary_accent_color ? normalized : null;
			}

			const cachedAccent = window.localStorage.getItem("ledgix_theme_primary_accent");
			if (cachedAccent) return normalizeThemeSettings({ enable_custom_accent: 1, primary_accent_color: cachedAccent });
		} catch (e) {}
		return null;
	}

	function broadcastThemeUpdate(theme) {
		const event = new CustomEvent("ledgix:theme-updated", {
			detail: { theme }
		});

		window.dispatchEvent(event);
		document.dispatchEvent(new CustomEvent("ledgix:theme-updated", {
			detail: { theme }
		}));

		if (window.ledgix_dashboard_v2?.apply_theme_settings) {
			window.ledgix_dashboard_v2.apply_theme_settings(theme);
		}

		if (window.frappe?.ledgix_operations?.apply_theme_variables) {
			window.frappe.ledgix_operations.boot = window.frappe.ledgix_operations.boot || {};
			window.frappe.ledgix_operations.boot.theme_settings = theme;
			window.frappe.ledgix_operations.apply_theme_variables(theme);
		}

		if (window.frappe?.ledgix_business_intelligence?.apply_theme_bridge) {
			window.frappe.ledgix_business_intelligence.apply_theme_bridge();
		}

		document.documentElement.setAttribute("data-ledgix-theme-updated", Date.now());
		document.body?.setAttribute("data-ledgix-theme-updated", Date.now());
	}

	function applyThemeSettings(settings, options) {
		const normalized = normalizeThemeSettings(settings);
		options = options || {};
		const targets = [
			document.documentElement,
			document.body,
			...document.querySelectorAll([
				".ledgix-nav-shell",
				".ledgix-app-shell",
				".ledgix-pos-app",
				".ledgix-dashboard-v2",
				".ledgix-operations-page",
				".lx-reports-page",
				".lx-bi-page",
				".lx-bi-shell",
				".ledgix-tax-center-page",
				".lx-tax-shell"
			].join(", "))
		].filter(Boolean).filter((target, index, list) => list.indexOf(target) === index);

		if (!normalized.enable_custom_accent || !normalized.primary_accent_color) {
			targets.forEach((target) => {
				THEME_CSS_VARS.forEach((name) => target.style.removeProperty(name));
				target.setAttribute("data-ledgix-theme", "disabled");
			});

			window.ledgix_theme = Object.assign({}, normalized, {
				accent: "",
				rgb: ""
			});
			window.LedgixTheme = Object.assign(window.LedgixTheme || {}, {
				accent: "",
				rgb: "",
				current: normalized
			});

			if (options.cache !== false) {
				saveThemeToCache(normalized);
			}

			if (options.broadcast) {
				broadcastThemeUpdate(normalized);
			}

			return normalized;
		}

		const primary = normalized.primary_accent_color;
		const hover = normalized.accent_hover;
		const soft = normalized.accent_soft;
		const soft2 = normalized.accent_soft_2;
		const border = normalized.accent_border;
		const ring = normalized.accent_ring;
		const rgb = normalized.accent_rgb;
		const softHover = normalized.accent_soft_hover;
		const borderStrong = normalized.accent_border_strong;
		const trackBg = normalized.accent_track_bg;
		const trackBorder = normalized.accent_track_border;

		const vars = {
			"--lx-accent": primary,
			"--accent": primary,
			"--ledgix-accent": primary,
			"--ledgix-primary": primary,
			"--primary": primary,
			"--lx-page-accent": primary,
			"--bi-accent": primary,
			"--lx-accent-hover": hover,
			"--lx-page-accent-hover": hover,
			"--accent-hover": hover,
			"--lx-accent-soft": soft,
			"--lx-page-accent-soft": soft,
			"--accent-soft": soft,
			"--lx-accent-soft-hover": softHover,
			"--lx-accent-soft-2": soft2,
			"--lx-page-accent-soft-2": soft2,
			"--accent-soft-2": soft2,
			"--lx-accent-border": border,
			"--lx-page-accent-border": border,
			"--accent-border": border,
			"--lx-accent-border-strong": borderStrong,
			"--lx-accent-ring": ring,
			"--lx-page-accent-ring": ring,
			"--accent-ring": ring,
			"--lx-accent-rgb": rgb,
			"--ledgix-accent-rgb": rgb,
			"--accent-rgb": rgb,
			"--lx-accent-track-bg": trackBg,
			"--lx-accent-track-border": trackBorder,
			"--lx-active-bg": primary,
			"--lx-active-hover": hover,
			"--lx-active-soft-bg": soft,
			"--lx-active-soft-hover": softHover,
			"--lx-active-border": border,
			"--lx-accent-surface": soft,
			"--lx-accent-surface-strong": soft2,
			"--lx-accent-shadow": ring,
			"--lx-category-active-bg": primary,
			"--lx-payment-active-bg": primary,
			"--lx-split-active-bg": primary,
			"--lx-modal-primary-bg": primary,
			"--lx-modal-primary-hover": hover
		};

		targets.forEach((target) => {
			target.setAttribute("data-ledgix-theme", "enabled");
			Object.entries(vars).forEach(([name, value]) => {
				if (value) target.style.setProperty(name, value);
			});
		});

		window.ledgix_theme = Object.assign({}, normalized, {
			accent: primary,
			rgb
		});
		window.LedgixTheme = Object.assign(window.LedgixTheme || {}, {
			accent: primary,
			rgb,
			current: normalized
		});

		if (options.cache !== false) {
			saveThemeToCache(normalized);
		}

		if (options.broadcast) {
			broadcastThemeUpdate(normalized);
		}

		return normalized;
	}

	function normalizeHex(value) {
		const text = String(value || "").trim();
		if (!text) return "";
		if (/^#[0-9a-fA-F]{6}$/.test(text)) return text;
		if (/^[0-9a-fA-F]{6}$/.test(text)) return `#${text}`;
		if (/^#[0-9a-fA-F]{3}$/.test(text)) {
			return `#${text.slice(1).split("").map((char) => char + char).join("")}`;
		}
		return "";
	}

	function loadThemeSettings() {
		const cachedTheme = readThemeCache();
		if (cachedTheme) {
			applyThemeSettings(cachedTheme, { cache: false });
		} else {
			applyThemeSettings(DISABLED_THEME_SETTINGS, { cache: false });
		}

		if (!window.frappe || !frappe.call) return;

		frappe.call({
			method: "ledgix_saas.api.api.get_pos_theme_settings",
			callback(r) {
				const theme = r.message || {};
				applyThemeSettings(theme);
			}
		});
	}

	function saveThemeSettings(settings) {
		const normalized = normalizeThemeSettings(settings);

		if (!window.frappe || !frappe.call) {
			const applied = applyThemeSettings(normalized, { broadcast: true });
			return Promise.resolve(applied);
		}

		return new Promise((resolve, reject) => {
			frappe.call({
				method: "ledgix_saas.api.api.save_pos_theme_settings",
				args: {
					primary_accent_color: normalized.primary_accent_color,
					enable_custom_accent: normalized.enable_custom_accent
				},
				freeze: true,
				callback(r) {
					const saved = r.message && r.message.theme_settings;
					const applied = applyThemeSettings(saved || normalized, { broadcast: true });
					if (state.shell) {
						state.shell.attr("data-ledgix-theme-updated", Date.now());
					}
					resolve(applied);
				},
				error(r) {
					reject(r);
				}
			});
		});
	}

	function openThemeSettings() {
		if (!window.frappe || !frappe.set_route) return;

		if (!frappe.ui || !frappe.ui.Dialog || !frappe.call) {
			frappe.set_route("Form", "Ledgix POS Theme Settings", "Ledgix POS Theme Settings");
			return;
		}

		frappe.call({
			method: "ledgix_saas.api.api.get_pos_theme_settings",
			callback(r) {
				const current = r.message || {};
				const dialog = new frappe.ui.Dialog({
					title: "Ledgix Theme",
					fields: [
						{
							fieldtype: "HTML",
							fieldname: "theme_summary",
							options: `
								<div class="ledgix-nav-modal ledgix-nav-theme-modal">
									<div class="ledgix-nav-modal-copy">
										<strong>Accent Theme</strong>
										<span>Controls Ledgix accent variables used by Navigator and theme-aware pages.</span>
									</div>
								</div>
							`
						},
						{
							fieldtype: "Check",
							fieldname: "enable_custom_accent",
							label: "Enable custom accent",
							default: current.enable_custom_accent ? 1 : 0
						},
						{
							fieldtype: "Color",
							fieldname: "primary_accent_color",
							label: "Primary Accent Color",
							default: normalizeHex(current.primary_accent_color) || "#0f766e",
							reqd: 1
						}
					],
					primary_action_label: "Save Theme",
					primary_action(values) {
						const enabled = values.enable_custom_accent ? 1 : 0;
						const primary = normalizeHex(values.primary_accent_color);
						if (enabled && !primary) {
							frappe.msgprint("Please select a valid accent color.");
							return;
						}

						dialog.disable_primary_action();
						window.LedgixTheme.save({
							enable_custom_accent: enabled,
							primary_accent_color: enabled ? primary : ""
						})
							.then(() => {
								dialog.hide();
								frappe.show_alert({ message: "Ledgix theme updated", indicator: "green" });
						})
							.catch(() => {
								frappe.show_alert({ message: "Unable to save Ledgix theme", indicator: "red" });
							})
							.finally(() => dialog.enable_primary_action());
					},
					secondary_action_label: "Open Full Settings",
					secondary_action() {
						dialog.hide();
						frappe.set_route("Form", "Ledgix POS Theme Settings", "Ledgix POS Theme Settings");
					}
				});

				dialog.show();
			}
		});
	}

	function openModeSettings() {
		if (!window.frappe || !frappe.set_route) return;

		if (!frappe.ui || !frappe.ui.Dialog) {
			frappe.set_route("Form", "Ledgix Mode Settings", "Ledgix Mode Settings");
			return;
		}

		const modeLabel = state.mode === "billing" ? "Billing Mode" : "Inventory Mode";
		const dialog = new frappe.ui.Dialog({
			title: "POS Mode",
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "mode_summary",
					options: `
						<div class="ledgix-nav-modal ledgix-nav-mode-modal">
							<div class="ledgix-nav-modal-copy">
								<strong>${safeText(modeLabel)}</strong>
								<span>Controls whether POS uses stock-first inventory checks or billing-first sales flow.</span>
							</div>
						</div>
					`
				}
			],
			primary_action_label: "Manage Settings",
			primary_action() {
				dialog.hide();
				frappe.set_route("Form", "Ledgix Mode Settings", "Ledgix Mode Settings");
			}
		});
		dialog.show();
	}

	function bindEvents() {
		if (!state.shell) return;

		state.shell.off(".ledgixNavigator");
		$(window).off(".ledgixNavigator");

		state.shell.on("click.ledgixNavigator", ".ledgix-nav-group-toggle[data-ledgix-toggle-group]", function (e) {
			e.preventDefault();
			e.stopPropagation();

			// When the full sidebar is icon-only, all nav icons stay visible.
			if (state.collapsed) return;

			const groupKey = $(this).attr("data-ledgix-toggle-group");
			if (!isCollapsibleGroup(groupKey)) return;

			state.groupCollapsed[groupKey] = !state.groupCollapsed[groupKey];
			setStorageValue(groupStorageKey(groupKey), state.groupCollapsed[groupKey]);
			syncGroupCollapseClasses();
		});

		state.shell.on("click.ledgixNavigator", ".ledgix-nav-item[data-ledgix-route]", function (e) {
			if (e.defaultPrevented) return;
			if (e.button && e.button !== 0) return;
			if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;

			const target = $(this).attr("target");
			if (target && target !== "_self") return;

			e.preventDefault();
			navigateTo($(this).attr("data-ledgix-route"));
		});

		state.shell.on("click.ledgixNavigator", ".ledgix-mobile-dock-item[data-ledgix-route], .ledgix-mobile-sheet-item[data-ledgix-route]", function (e) {
			if (e.defaultPrevented) return;
			if (e.button && e.button !== 0) return;
			if (e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return;

			const target = $(this).attr("target");
			if (target && target !== "_self") return;

			e.preventDefault();
			navigateTo($(this).attr("data-ledgix-route"));
		});

		state.shell.on("click.ledgixNavigator", ".ledgix-nav-collapse", function () {
			state.collapsed = !state.collapsed;
			setStorageValue(settings().collapsed_key, state.collapsed);
			applyState();
			syncGroupCollapseClasses();
		});

		state.shell.on("click.ledgixNavigator", ".ledgix-nav-mark", function () {
			if (!state.collapsed) return;
			state.collapsed = false;
			setStorageValue(settings().collapsed_key, state.collapsed);
			applyState();
			syncGroupCollapseClasses();
		});

		state.shell.on("click.ledgixNavigator", ".ledgix-mobile-more-btn", function (e) {
			e.preventDefault();
			e.stopPropagation();
			state.mobileSheetOpen = !state.mobileSheetOpen;
			applyState();
		});

		state.shell.on("click.ledgixNavigator", ".ledgix-mobile-sheet-backdrop, .ledgix-mobile-sheet-close", function () {
			closeMobileSheet();
		});

		state.shell.on("click.ledgixNavigator", ".ledgix-nav-profile-button", function (e) {
			e.stopPropagation();
			const $menu = state.shell.find(".ledgix-nav-profile-menu");
			const willOpen = $menu.prop("hidden");
			$menu.prop("hidden", !willOpen);
			$(this).attr("aria-expanded", willOpen ? "true" : "false");
		});

		state.shell.on("click.ledgixNavigator", "[data-ledgix-profile-action]", function () {
			const action = $(this).attr("data-ledgix-profile-action");

			if (action === "profile") {
				closeMobileSheet();
				openProfileModal();
				return;
			}

			if (action === "logout") {
				closeMobileSheet();
				if (window.frappe && frappe.app && frappe.app.logout) {
					frappe.app.logout();
				} else {
					window.location.href = "/?cmd=web_logout";
				}
			}
		});

		state.shell.on("change.ledgixNavigator", "[data-ledgix-setting='collapsed']", function () {
			state.collapsed = $(this).is(":checked");
			setStorageValue(settings().collapsed_key, state.collapsed);
			applyState();
		});

		state.shell.on("change.ledgixNavigator", "[data-ledgix-setting='compact']", function () {
			state.compact = $(this).is(":checked");
			setStorageValue(settings().compact_key, state.compact);
			applyState();
		});

		state.shell.on("click.ledgixNavigator", "[data-ledgix-setting-action]", function () {
			const action = $(this).attr("data-ledgix-setting-action");
			closePanels();
			closeMobileSheet();
			if (action === "mode") openModeSettings();
			if (action === "theme") openThemeSettings();
		});

		state.shell.on("click.ledgixNavigator", function (e) {
			if (!$(e.target).closest(".ledgix-nav-profile").length) {
				closePanels();
			}
		});

		installHistoryRouteWatcher();
		installActiveDomObserver();

		$(window).on("popstate.ledgixNavigator hashchange.ledgixNavigator focus.ledgixNavigator ledgix:navigator-location-change.ledgixNavigator", function () {
			scheduleActiveRefresh();
			scheduleDeskShellMount();
			syncLedgixAppChrome();
			window.setTimeout(syncLedgixAppChrome, 100);
		});
		$(window).on("keydown.ledgixNavigator", function (e) {
			if (e.key === "Escape") closeMobileSheet();
		});
		if (window.frappe && frappe.router && frappe.router.on && !window.__ledgixNavigatorRouterChangeBound) {
			window.__ledgixNavigatorRouterChangeBound = true;
			frappe.router.on("change", function () {
				scheduleActiveRefresh();
				scheduleDeskShellMount();
				window.setTimeout(syncLedgixAppChrome, 0);
				window.setTimeout(syncLedgixAppChrome, 100);
			});
		}
	}

	function mount(options) {
		options = options || {};
		if (!isAllowedPage() || !isLedgixDeskRoute()) {
			disableLedgixAppChrome();
			return null;
		}
		const $content = normalizeContent(options.content);
		if (!$content || !$content.length) return null;
		cleanupFrappePageShell($content);
		enableLedgixAppChrome();
		loadThemeSettings();

		const existingShell = $content.closest(".ledgix-app-shell");
		if (existingShell.length) {
			state.shell = existingShell;
			state.nav = existingShell.find(".ledgix-app-nav");
			state.main = existingShell.find(".ledgix-app-main");
			state.backdrop = existingShell.find(".ledgix-mobile-sheet-backdrop");
			state.content = $content;
			const existingRouteKey = getRouteKey();
			const existingContentKey = detectActiveKeyFromContent($content, options);
			state.mountedActiveKey = (state.pendingActiveKey && existingRouteKey === state.pendingActiveKey)
				? existingRouteKey
				: (existingContentKey || existingRouteKey || state.mountedActiveKey);
			if (!state.pendingActiveKey || state.mountedActiveKey === state.pendingActiveKey) clearPendingActive();
			state.mounted = true;
			bindEvents();
			applyState();
			syncLedgixAppChrome();
			scheduleActiveRefresh();
			return state.shell;
		}

		const $parent = $content.parent();
		loadGroupCollapseState();
		const $shell = $('<div class="ledgix-app-shell"></div>');
		$shell.html(`${renderNav()}<main class="ledgix-app-main"></main>`);
		$parent.append($shell);

		state.shell = $shell;
		state.nav = $shell.find(".ledgix-app-nav");
		state.main = $shell.find(".ledgix-app-main");
		state.backdrop = $shell.find(".ledgix-mobile-sheet-backdrop");
		state.collapsed = storageValue(settings().collapsed_key, Boolean(settings().default_collapsed));
		state.compact = storageValue(settings().compact_key, Boolean(settings().default_compact));
		state.mobileSheetOpen = false;
		state.mounted = true;
		const detectedMode = detectModeFromPage();
		state.mode = detectedMode || state.mode;
		state.modeKnown = Boolean(detectedMode);

		mountCurrentPageContent($content);
		const mountedRouteKey = getRouteKey();
		const mountedContentKey = detectActiveKeyFromContent($content, options);
		state.mountedActiveKey = (state.pendingActiveKey && mountedRouteKey === state.pendingActiveKey)
			? mountedRouteKey
			: (mountedContentKey || mountedRouteKey);
		if (!state.pendingActiveKey || state.mountedActiveKey === state.pendingActiveKey) clearPendingActive();
		bindEvents();
		applyState();
		loadModeFromSettings();
		syncLedgixAppChrome();
		scheduleActiveRefresh();

		return $shell;
	}

	function queueMount(options) {
		pendingMounts.push(options || {});
		return null;
	}

	function flushMountQueue() {
		while (pendingMounts.length) {
			mount(pendingMounts.shift());
		}
	}

	window.LedgixNavigator = Object.assign(window.LedgixNavigator || {}, {
		__pendingMounts: pendingMounts,
		mount,
		queueMount,
		flushMountQueue,
		mountCurrentPageContent,
		updateActiveState,
		detectActiveKeyFromVisibleDom,
		getFrappeRouteKey,
		isAllowedPage,
		getRouteKey,
		routeToKey,
		setMode,
		refreshBrand,
		getBrand
	});

		window.LedgixTheme = Object.assign(window.LedgixTheme || {}, {
			apply: applyThemeSettings,
			get() {
				const current = normalizeThemeSettings(window.LedgixTheme.current);
				if (current.enable_custom_accent && current.primary_accent_color) return current;
				return readThemeCache() || Object.assign({}, DISABLED_THEME_SETTINGS);
			},
			load: loadThemeSettings,
			save: saveThemeSettings,
			saveToCache: saveThemeToCache,
			readCache: readThemeCache,
		accent: (window.LedgixTheme && window.LedgixTheme.accent) || "",
		current: normalizeThemeSettings(window.LedgixTheme && window.LedgixTheme.current)
	});

	applyThemeSettings(readThemeCache() || DISABLED_THEME_SETTINGS, { cache: false });

	flushMountQueue();

	if (window.frappe && frappe.ready) {
		frappe.ready(function () {
			scheduleDeskShellMount();
		});
	} else {
		scheduleDeskShellMount();
	}
})();
