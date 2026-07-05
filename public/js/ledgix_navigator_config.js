(function () {
	"use strict";

	const config = {
		app: {
			name: "Ledgix",
			tagline: "Retail operations",
			version: "1.0.0"
		},

		allowed_pages: [
			"/app/ledgix-dashboard",
			"/app/ledgix-pos",
			"/app/ledgix_operations",
			"/app/ledgix-operations",
			"/app/business-intelligence-center",
			"/app/business_intelligence_center",
			"/app/ledgix-tax-center",
			"/app/ledgix_tax_center",
			"/app/ledgix-reports",
			"/app/quick-item-scan"
		],

		routes: {
			dashboard: "/app/ledgix-dashboard",
			pos: "/app/ledgix-pos",
			operations: "/app/ledgix_operations",
			business_intelligence: "/app/business-intelligence-center",
			tax_center: "/app/ledgix-tax-center",
			reports: "/app/ledgix-reports"
		},

		nav_groups: [
			{
				key: "main",
				label: "Main",
				items: ["dashboard", "pos", "operations", "business_intelligence", "tax_center", "reports"]
			},
			{
				key: "operations",
				label: "Operations",
				items: ["products", "categories", "purchases", "sales", "sales_returns", "stock_movements", "shifts"]
			},
			{
				key: "reports",
				label: "Reports",
				// Same order as get_ledgix_report_modules() in ledgix_reports.js.
				items: [
					"sales_report",
					"purchases_report",
					"returns_report",
					"stock_report",
					"inventory_report",
					"item_intelligence_report",
					"profit_report",
					"customer_statement",
					"supplier_statement"
				]
			}
		],

		nav_items: {
			dashboard: {
				key: "dashboard",
				label: "Dashboard",
				icon: "dashboard",
				route: "/app/ledgix-dashboard",
				modes: ["inventory", "billing"]
			},
			pos: {
				key: "pos",
				label: "POS",
				icon: "pos",
				route: "/app/ledgix-pos",
				modes: ["inventory", "billing"],
				tier: "cashier"
			},
			operations: {
				key: "operations",
				label: "Operations",
				icon: "operations",
				route: "/app/ledgix_operations",
				modes: ["inventory", "billing"]
			},
			business_intelligence: {
				key: "business_intelligence",
				label: "BI Center",
				icon: "biCenter",
				route: "/app/business-intelligence-center",
				modes: ["inventory", "billing"]
			},
			tax_center: {
				key: "tax_center",
				label: "Tax Center",
				icon: "taxCenter",
				route: "/app/ledgix-tax-center",
				modes: ["inventory", "billing"]
			},
			reports: {
				key: "reports",
				label: "Reports",
				icon: "reportsHub",
				route: "/app/ledgix-reports",
				modes: ["inventory", "billing"]
			},

			products: {
				key: "products",
				label: "Products",
				icon: "products",
				route: "/app/ledgix_operations?module=products",
				modes: ["inventory", "billing"]
			},
			categories: {
				key: "categories",
				label: "Categories",
				icon: "categories",
				route: "/app/ledgix_operations?module=categories",
				modes: ["inventory", "billing"]
			},
			purchases: {
				key: "purchases",
				label: "Purchases",
				icon: "purchases",
				route: "/app/ledgix_operations?module=purchases",
				modes: ["inventory"]
			},
			sales: {
				key: "sales",
				label: "Sales",
				icon: "sales",
				route: "/app/ledgix_operations?module=sales",
				modes: ["inventory", "billing"]
			},
			sales_returns: {
				key: "sales_returns",
				label: "Sales Returns",
				icon: "returns",
				route: "/app/ledgix_operations?module=sales-returns",
				modes: ["inventory", "billing"]
			},
			stock_movements: {
				key: "stock_movements",
				label: "Stock Movements",
				icon: "stock",
				route: "/app/ledgix_operations?module=stock-movements",
				modes: ["inventory"]
			},
			shifts: {
				key: "shifts",
				label: "Shifts",
				icon: "shifts",
				route: "/app/ledgix_operations?module=pos-shifts",
				modes: ["inventory", "billing"]
			},

			sales_report: {
				key: "sales_report",
				label: "Sales Report",
				icon: "salesReport",
				route: "/app/ledgix-reports?report=sales",
				modes: ["inventory", "billing"]
			},
			purchases_report: {
				key: "purchases_report",
				label: "Purchases Report",
				icon: "purchasesReport",
				route: "/app/ledgix-reports?report=purchases",
				modes: ["inventory"]
			},
			returns_report: {
				key: "returns_report",
				label: "Returns Report",
				icon: "returnsReport",
				route: "/app/ledgix-reports?report=returns",
				modes: ["inventory", "billing"]
			},
			stock_report: {
				key: "stock_report",
				label: "Stock Report",
				icon: "stockReport",
				route: "/app/ledgix-reports?report=stock",
				modes: ["inventory"]
			},
			inventory_report: {
				key: "inventory_report",
				label: "Inventory Report",
				icon: "inventoryReport",
				route: "/app/ledgix-reports?report=inventory",
				modes: ["inventory"]
			},
			item_intelligence_report: {
				key: "item_intelligence_report",
				label: "Item Intelligence",
				icon: "itemIntelligenceReport",
				route: "/app/ledgix-reports?report=item_full_cycle",
				modes: ["inventory"]
			},
			profit_report: {
				key: "profit_report",
				label: "Profit Report",
				icon: "profitReport",
				route: "/app/ledgix-reports?report=profit",
				modes: ["inventory", "billing"]
			},
			customer_statement: {
				key: "customer_statement",
				label: "Customers",
				icon: "customerStatement",
				route: "/app/ledgix-reports?report=customers",
				modes: ["inventory", "billing"]
			},
			supplier_statement: {
				key: "supplier_statement",
				label: "Suppliers",
				icon: "supplierStatement",
				route: "/app/ledgix-reports?report=suppliers",
				modes: ["inventory"]
			}
		},

		quick_actions: [
			{
				key: "new_purchase",
				label: "New Purchase",
				icon: "plus",
				doctype: "Ledgix Purchase"
			},
			{
				key: "add_customer",
				label: "Add Customer",
				icon: "userPlus",
				doctype: "Ledgix Customer"
			}
		],

		settings: {
			collapsed_key: "ledgix.navigator.collapsed",
			default_collapsed: true,
			compact_key: "ledgix.navigator.compact",
			default_compact: false,
			expanded_width: 248,
			collapsed_width: 60
		}
	};

	const existing = window.LedgixNavigator || {};
	const pendingMounts = existing.__pendingMounts || [];

	function queueMount(options) {
		pendingMounts.push(options || {});
		return null;
	}

	window.LedgixNavigator = Object.assign(existing, {
		config: config,
		__pendingMounts: pendingMounts
	});

	// Important: page JS may run before the real navigator implementation.
	// Keep a temporary mount function so existing page calls are queued safely.
	if (typeof window.LedgixNavigator.mount !== "function") {
		window.LedgixNavigator.mount = queueMount;
	}
	if (typeof window.LedgixNavigator.queueMount !== "function") {
		window.LedgixNavigator.queueMount = queueMount;
	}

	if (typeof window.LedgixNavigator.flushMountQueue === "function") {
		window.LedgixNavigator.flushMountQueue();
	}
})();
