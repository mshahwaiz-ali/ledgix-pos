// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

// ============================================================
// LEDGIX REPORTS PAGE
// ============================================================

const LEDGIX_REPORT_THEME_VARS = [
	"--lx-accent",
	"--accent",
	"--ledgix-accent",
	"--ledgix-primary",
	"--primary",
	"--lx-page-accent",
	"--lx-accent-hover",
	"--accent-hover",
	"--lx-accent-soft",
	"--accent-soft",
	"--lx-accent-soft-2",
	"--accent-soft-2",
	"--lx-accent-border",
	"--accent-border",
	"--lx-accent-ring",
	"--accent-ring",
	"--lx-accent-rgb",
	"--ledgix-accent-rgb",
	"--accent-rgb",
	"--lx-accent-surface",
	"--lx-accent-surface-strong",
	"--lx-accent-shadow"
];

frappe.pages["ledgix-reports"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "",
		single_column: true
	});
	page.set_title("");

	const $page_container = $(wrapper).closest(".page-container");
	$page_container.addClass("ledgix-page-no-frappe-head");

	$page_container
		.find(".page-head, .page-head-content, .page-title, .title-area, .page-actions")
		.hide();

	const report_modules = get_ledgix_report_modules();

	const state = {
		active_key: get_initial_ledgix_report_key(report_modules),
		page: 1,
		page_size: 15,

		// Chart state stays isolated from table search/filter/pagination.
		chart_date_preset: "this_month",
		chart_from_date: frappe.datetime.month_start(),
		chart_to_date: frappe.datetime.month_end(),
		chart_filters: get_empty_report_filters(),
		chart_mode: "value",
		chart_type: "bar",
		chart_data: [],
		chart_summary: {},
		chart_requires_party: 0,

		// Table state controls records only.
		table_date_preset: "this_month",
		table_from_date: frappe.datetime.month_start(),
		table_to_date: frappe.datetime.month_end(),
		table_filters: get_empty_report_filters(),
		search: "",
		sort_by: "",
		sort_order: "asc",

		loading: false,
		rows: [],
		summary: {},
		total_count: 0,
		table_requires_party: 0,
		theme_settings: null,
		selected_rows: {},
		summary_source: "chart",
		analytics_collapsed: true,
		item_cycle_guide_open: false,
		stock_control_mode: "Strict Inventory",
		table_request_id: 0,
		chart_request_id: 0,
		item_search_request_id: 0
	};

	page.ledgix_reports_state = state;

	$(page.body).html(get_ledgix_reports_html(report_modules, state.active_key));

	window.LedgixNavigator?.mount?.({
		page: page,
		wrapper: wrapper,
		content: $(page.body).find(".lx-reports-page").first(),
		active: "reports"
	});

	apply_ledgix_report_theme(page);
	bind_ledgix_report_theme_updates(page, state);
	bind_ledgix_report_events(page, report_modules, state);
	load_ledgix_report_boot(page, report_modules, state);
};

;

// ============================================================
// REPORT CONFIG
// ============================================================

function get_ledgix_report_modules() {
	return [
		{
			key: "sales",
			label: "Sales",
			title: "Sales Overview",
			table_title: "Sales Report Records",
			api_method: "ledgix_saas.api.api.get_sales_report_data",
			search_placeholder: "Search invoice or customer...",
			summary: [
				{ key: "total_sales", label: "Total Sales", type: "currency" },
				{ key: "total_profit", label: "Total Profit", type: "currency" },
				{ key: "invoice_count", label: "Invoices", type: "number" },
				{ key: "avg_order", label: "Avg Order", type: "currency" }
			],
			columns: [
				{ key: "invoice", label: "Invoice" },
				{ key: "customer", label: "Customer" },
				{ key: "status", label: "Status" },
				{ key: "amount", label: "Amount", type: "currency", align: "right" },
				{ key: "profit", label: "Profit", type: "currency", align: "right" },
				{ key: "payment_mode", label: "Payment" },
				{ key: "date", label: "Date" },
				{ key: "actions", label: "Actions", is_action: true }
			]
		},
		{
			key: "purchases",
			label: "Purchases",
			api_method: "ledgix_saas.api.api.get_purchase_report_data",
			title: "Purchase Overview",
			table_title: "Purchase Report Records",
			search_placeholder: "Search purchase or supplier...",
			summary: [
				{ key: "total_purchases", label: "Total Purchases", type: "currency" },
				{ key: "suppliers", label: "Suppliers", type: "number" },
				{ key: "items_bought", label: "Items Bought", type: "number" },
				{ key: "avg_purchase", label: "Avg Purchase", type: "currency" }
			],
			columns: [
				{ key: "purchase", label: "Purchase" },
				{ key: "supplier", label: "Supplier" },
				{ key: "status", label: "Status" },
				{ key: "amount", label: "Amount", type: "currency", align: "right" },
				{ key: "total_qty", label: "Qty", type: "number", align: "right" },
				{ key: "date", label: "Date" },
				{ key: "actions", label: "Actions", is_action: true }
			]
		},
		{
			key: "returns",
			label: "Returns",
			api_method: "ledgix_saas.api.api.get_return_report_data",
			title: "Returns Overview",
			table_title: "Sales Return Records",
			search_placeholder: "Search return, sale, or customer...",
			summary: [
				{ key: "return_amount", label: "Return Amount", type: "currency" },
				{ key: "return_count", label: "Returns", type: "number" },
				{ key: "items_returned", label: "Items Returned", type: "number" },
				{ key: "return_rate", label: "Return Rate", type: "percent" }
			],
			columns: [
				{ key: "return", label: "Return" },
				{ key: "sale", label: "Sale" },
				{ key: "customer", label: "Customer" },
				{ key: "status", label: "Status" },
				{ key: "amount", label: "Amount", type: "currency", align: "right" },
				{ key: "total_qty", label: "Qty", type: "number", align: "right" },
				{ key: "date", label: "Date" },
				{ key: "actions", label: "Actions", is_action: true }
			]
		},
		{
			key: "stock",
			label: "Stock",
			api_method: "ledgix_saas.api.api.get_stock_report_data",
			title: "Stock Overview",
			table_title: "Stock Movement Records",
			search_placeholder: "Search movement or item...",
			summary: [
				{ key: "in_qty", label: "In Qty", type: "number" },
				{ key: "out_qty", label: "Out Qty", type: "number" },
				{ key: "adjustments", label: "Adjustments", type: "number" },
				{ key: "stock_value", label: "Stock Value", type: "currency" }
			],
			columns: [
				{ key: "movement", label: "Movement" },
				{ key: "item", label: "Item" },
				{ key: "type", label: "Type" },
				{ key: "quantity", label: "Quantity", type: "number", align: "right" },
				{ key: "reference", label: "Reference" },
				{ key: "date", label: "Date" },
				{ key: "actions", label: "Actions", is_action: true }
			]
		},
		{
			key: "inventory",
			label: "Inventory",
			api_method: "ledgix_saas.api.reports.get_inventory_report_data",
			title: "Inventory Overview",
			table_title: "Inventory Stock Records",
			search_placeholder: "Search item, SKU, barcode, or category...",
			summary: [
				{ key: "inventory_value", label: "Inventory Value", type: "currency" },
				{ key: "total_items", label: "Total Items", type: "number" },
				{ key: "low_stock", label: "Low Stock", type: "number" },
				{ key: "out_of_stock", label: "Out of Stock", type: "number" }
			],
			columns: [
				{ key: "item", label: "Item" },
				{ key: "category", label: "Category" },
				{ key: "current_stock", label: "Current Stock", type: "number", align: "right" },
				{ key: "minimum_stock", label: "Minimum Stock", type: "number", align: "right" },
				{ key: "stock_status", label: "Stock Status" },
				{ key: "cost_price", label: "Cost", type: "currency", align: "right" },
				{ key: "selling_price", label: "Selling", type: "currency", align: "right" },
				{ key: "inventory_value", label: "Value", type: "currency", align: "right" },
				{ key: "profit_margin", label: "Margin", type: "percent", align: "right" },
				{ key: "actions", label: "Actions", is_action: true }
			]
		},
		{
			key: "item_full_cycle",
			label: "Item Intelligence",
			api_method: "ledgix_saas.api.report_adapters.get_item_intelligence_report_data",
			title: "Item Intelligence",
			table_title: "Item Intelligence Records",
			search_placeholder: "After item selection: search lot, purchase, sale, return, supplier, customer...",
			requires_item: true,
			inventory_only: true,
			disable_chart: true,
			summary: [
				{ key: "purchased_qty", label: "Purchased Qty", type: "number" },
				{ key: "current_lot_qty", label: "Current Lot Qty", type: "number" },
				{ key: "sold_qty", label: "Sold Qty", type: "number" },
				{ key: "returned_qty", label: "Returned Qty", type: "number" },
				{ key: "net_sold_qty", label: "Net Sold Qty", type: "number" },
				{ key: "selling_amount", label: "Selling Amount", type: "currency" },
				{ key: "profit", label: "Profit", type: "currency" },
				{ key: "loss", label: "Loss", type: "currency" }
			],
			columns: [
				{ key: "lot_no", label: "Lot No" },
				{ key: "lot_status", label: "Lot Status" },
				{ key: "row_type", label: "Row Type" },
				{ key: "cycle_status", label: "Status" },
				{ key: "profit", label: "Profit", type: "currency", align: "right" },
				{ key: "loss", label: "Loss", type: "currency", align: "right" },
				{ key: "current_lot_qty", label: "Current Lot Qty", type: "number", align: "right" },
				{ key: "purchased_qty", label: "Purchased Qty", type: "number", align: "right" },
				{ key: "sale_qty", label: "Sale Qty", type: "number", align: "right" },
				{ key: "return_qty", label: "Return Qty", type: "number", align: "right" },
				{ key: "net_sold_qty", label: "Net Sold Qty", type: "number", align: "right" },
				{ key: "unit_cost", label: "Unit Cost", type: "currency", align: "right" },
				{ key: "total_cost", label: "Total Cost", type: "currency", align: "right" },
				{ key: "selling_amount", label: "Selling Amount", type: "currency", align: "right" },
				{ key: "return_amount", label: "Return Amount", type: "currency", align: "right" },
				{ key: "purchase_no", label: "Purchase No" },
				{ key: "purchase_invoice", label: "Purchase Invoice" },
				{ key: "purchase_date", label: "Purchase Date", type: "date" },
				{ key: "supplier", label: "Supplier" },
				{ key: "purchase_rate", label: "Purchase Rate", type: "currency", align: "right" },
				{ key: "purchase_amount", label: "Purchase Amount", type: "currency", align: "right" },
				{ key: "sale_no", label: "Sale No" },
				{ key: "sale_invoice", label: "Sale Invoice" },
				{ key: "sale_date", label: "Sale Date", type: "date" },
				{ key: "customer", label: "Customer" },
				{ key: "return_no", label: "Return No" },
				{ key: "return_date", label: "Return Date", type: "date" },
				{ key: "return_reason", label: "Return Reason / Note" },
				{ key: "actions", label: "Actions", is_action: true }
			]
		},
		{
			key: "profit",
			label: "Profit",
			api_method: "ledgix_saas.api.api.get_profit_report_data",
			title: "Profit Overview",
			table_title: "Profit Report Records",
			search_placeholder: "Search reference or item...",
			summary: [
				{ key: "gross_profit", label: "Gross Profit", type: "currency" },
				{ key: "profit_margin", label: "Profit Margin", type: "percent" },
				{ key: "best_item", label: "Best Item", type: "text" },
				{ key: "avg_profit", label: "Avg Profit", type: "currency" }
			],
			columns: [
				{ key: "reference", label: "Reference" },
				{ key: "item", label: "Item" },
				{ key: "revenue", label: "Revenue", type: "currency", align: "right" },
				{ key: "cost", label: "Cost", type: "currency", align: "right" },
				{ key: "profit", label: "Profit", type: "currency", align: "right" },
				{ key: "margin", label: "Margin", type: "percent", align: "right" },
				{ key: "date", label: "Date" },
				{ key: "actions", label: "Actions", is_action: true }
			]
		},
		{
			key: "customers",
			label: "Customers",
			api_method: "ledgix_saas.api.api.get_customer_statement",
			title: "Customer Statement",
			table_title: "Customer Statement Records",
			search_placeholder: "Search customer or reference...",
			summary: [
				{ key: "receivable", label: "Receivable", type: "currency" },
				{ key: "customers", label: "Customers", type: "number" },
				{ key: "invoices", label: "Invoices", type: "number" },
				{ key: "balance", label: "Balance", type: "currency" }
			],
			columns: [
				{ key: "date", label: "Date" },
				{ key: "reference", label: "Reference" },
				{ key: "description", label: "Description" },
				{ key: "debit", label: "Debit", type: "currency", align: "right" },
				{ key: "credit", label: "Credit", type: "currency", align: "right" },
				{ key: "balance", label: "Balance", type: "currency", align: "right" },
				{ key: "actions", label: "Actions", is_action: true }
			]
		},
		{
			key: "suppliers",
			label: "Suppliers",
			api_method: "ledgix_saas.api.api.get_supplier_statement",
			title: "Supplier Statement",
			table_title: "Supplier Statement Records",
			search_placeholder: "Search supplier or reference...",
			summary: [
				{ key: "payable", label: "Payable", type: "currency" },
				{ key: "suppliers", label: "Suppliers", type: "number" },
				{ key: "purchases", label: "Purchases", type: "number" },
				{ key: "balance", label: "Balance", type: "currency" }
			],
			columns: [
				{ key: "date", label: "Date" },
				{ key: "reference", label: "Reference" },
				{ key: "description", label: "Description" },
				{ key: "debit", label: "Debit", type: "currency", align: "right" },
				{ key: "credit", label: "Credit", type: "currency", align: "right" },
				{ key: "balance", label: "Balance", type: "currency", align: "right" },
				{ key: "actions", label: "Actions", is_action: true }
			]
		}
	];
}

function get_active_report(report_modules, state) {
	return report_modules.find((report) => report.key === state.active_key) || report_modules[0];
}

// ============================================================
// PAGE HTML
// ============================================================

function get_ledgix_reports_html(report_modules, active_key) {
	return `
		<div class="lx-reports-page is-mode-loading">
			<div class="lx-reports-header">

				<div class="lx-reports-header-main">
					<div class="lx-reports-eyebrow">
						LEDGIX REPORTS
					</div>

					<h2 class="lx-reports-title">Reports & Analytics</h2>

					<p class="lx-reports-subtitle">
						Operational reports, statements, and business insights for daily decisions.
					</p>
				</div>

				<div class="lx-reports-header-side">

					<div class="lx-report-mode-badge lx-mode-inventory" data-mode-badge>
						<i class="fa fa-shield"></i>
						<span>Inventory Mode</span>
					</div>

					<div class="lx-reports-header-actions">
						<button class="lx-report-header-btn" data-action="refresh-page" title="Refresh">
							<i class="fa fa-refresh"></i>
						</button>
					</div>

				</div>

			</div>


			<div class="lx-report-modules">
				${report_modules.map((module) => {
					const inventory_only = is_inventory_mode_only_report(module.key);
					return `
						<button class="lx-report-module-btn ${module.key === active_key ? "active" : ""}" data-report-key="${module.key}" ${inventory_only ? 'data-inventory-only="1"' : ''}>
							${frappe.utils.escape_html(module.label)}
						</button>
					`;
				}).join("")}
			</div>

			<div class="lx-item-cycle-guide-slot"></div>

			<div class="lx-report-toolbar lx-report-toolbar-compact" style="display:none;"></div>

			<div class="lx-report-analytics-panel collapsed">
				<button class="lx-analytics-collapse-bar" type="button" data-action="toggle-analytics" aria-expanded="false">
					<span><i class="fa fa-area-chart"></i> Report Intelligence</span>
					<i class="fa fa-angle-down"></i>
				</button>

				<div class="lx-report-analytics-grid">
					<div class="lx-report-chart-card">
					<div class="lx-report-card-header lx-report-chart-header">
						<h4></h4>
						<div class="lx-chart-header-controls">
							<button class="lx-report-filter-box lx-report-date-filter lx-icon-only" data-action="date-range" data-scope="chart" title="Chart date range" aria-label="Chart date range">
								<i class="fa fa-calendar"></i>
							</button>
							<button class="lx-report-filter-box lx-icon-only" data-action="advanced-filters" data-scope="chart" title="Chart filters" aria-label="Chart filters">
								<i class="fa fa-sliders"></i>
							</button>
							<div class="lx-chart-type-toggle" data-chart-type="bar" title="Chart type">
								<button data-chart-type-option="line" title="Line chart" aria-label="Line chart">
									<i class="fa fa-line-chart"></i>
								</button>

								<button class="active" data-chart-type-option="bar" title="Bar chart" aria-label="Bar chart">
									<i class="fa fa-bar-chart"></i>
								</button>
							</div>
							<div class="lx-chart-mode-pills" data-active="value">
								<button class="active" data-chart-mode="value">Value</button>
								<button data-chart-mode="count">Count</button>
							</div>
						</div>
					</div>

					<div class="lx-report-chart-shell">
						<div class="lx-chart-skeleton-top">
							<div>
								<span>Selected range</span>
								<strong class="lx-selected-range-label">This Month</strong>
							</div>

							<div class="lx-chart-trend-badge">
								<i class="fa fa-line-chart"></i>
								<span>Ready</span>
							</div>
						</div>

						<div class="lx-report-chart-area">
							<div class="lx-report-chart-real"></div>
						</div>
					</div>
				</div>

				<div class="lx-report-summary-card">
					<div class="lx-report-card-header lx-summary-card-header">
						<h4>Summary</h4>
						<strong class="lx-summary-source-label">Chart range summary</strong>
					</div>
					<div class="lx-report-summary-list"></div>
				</div>
			</div>

			<div class="lx-report-table-card">
				<div class="lx-report-card-header">
					<h4></h4>
					<div class="lx-report-table-meta">
						
						<button class="lx-report-filter-box lx-report-date-filter" data-action="date-range" data-scope="table" title="Table date range">
							<i class="fa fa-calendar"></i>
						</button>
						<button class="lx-report-filter-box" data-action="advanced-filters" data-scope="table" title="Table filters">
							<i class="fa fa-sliders"></i>
						</button>
						<button class="lx-report-filter-box lx-report-clear-table-btn" data-action="clear-table-controls" title="Clear table filters/search/date">
							<i class="fa fa-filter"></i><i class="fa fa-times"></i>
						</button>
						<button class="lx-report-filter-box lx-report-clear-selection-btn" data-bulk-action="clear" title="Clear selected rows" style="display:none;">
							<i class="fa fa-check-square-o"></i><i class="fa fa-times"></i>
						</button>
						<span class="lx-report-selected-badge" style="display:none;">0 selected</span>

						<button class="lx-report-filter-box lx-report-table-export-btn" data-action="export" title="Export">
							<i class="fa fa-download"></i>
						</button>

						<button class="lx-report-filter-box lx-report-table-print-btn" data-action="print" title="Print">
							<i class="fa fa-print"></i>
						</button>
						<button class="lx-report-table-party-btn" data-action="select-party" style="display:none;">
							<i class="fa fa-user-circle-o"></i>
							<span>Select Party</span>
						</button>
						<span class="lx-report-total-badge">0 records</span>
					</div>
				</div>

				<div class="lx-report-table-wrapper">
					<table class="lx-report-table">
						<thead><tr></tr></thead>
						<tbody></tbody>
					</table>
				</div>

				<div class="lx-report-pagination">
					<div class="lx-report-pagination-info">Showing 0 of 0 entries</div>
					<div class="lx-report-pagination-controls">
						<button class="lx-pagination-btn" data-page-action="prev">Previous</button>
						<div class="lx-pagination-page">1</div>
						<button class="lx-pagination-btn" data-page-action="next">Next</button>
					</div>
				</div>
			</div>
		</div>
	`;
}

// ============================================================
// EVENTS
// ============================================================

function bind_ledgix_report_events(page, report_modules, state) {
	const $body = $(page.body);
	const debounced_search = ledgix_debounce(() => {
		if (state.loading) return;

		state.page = 1;
		load_table_report(page, report_modules, state);
	}, 350);

	$body.off(".ledgixReports");
	$(window).off("popstate.ledgixReports").on("popstate.ledgixReports", function() {
		sync_ledgix_report_from_url(page, report_modules, state);
	});

	$body.on("click.ledgixReports", ".lx-report-module-btn", function() {
		const report_key = $(this).data("report-key");
		if (is_billing_mode(state) && is_inventory_mode_only_report(report_key)) {
			state.active_key = "sales";
			update_ledgix_report_url("sales");
			apply_report_mode_ui(page, report_modules, state);
			load_active_report(page, report_modules, state);
			return;
		}

		const selected_report = report_modules.find((report) => report.key === report_key);
		if (!selected_report) return;

		state.active_key = report_key;
		state.page = 1;
		state.search = "";
		state.sort_by = "";
		state.sort_order = "asc";
		state.table_filters = get_empty_report_filters();
		state.chart_filters = get_empty_report_filters();
		clear_report_selection(page, state);
		update_ledgix_report_url(report_key);
		window.LedgixNavigator?.updateActiveState?.();

		$body.find(".lx-report-module-btn").removeClass("active");
		$(this).addClass("active");
		$body.find(".lx-report-search input").val("").attr("placeholder", selected_report.search_placeholder || "Search report...");
		$body.find(".lx-report-search-clear").removeClass("visible");
		hide_item_intelligence_search_picker(page);

		requestAnimationFrame(() => {
			load_active_report(page, report_modules, state);
		});
	});

	$body.on("click.ledgixReports", "[data-action='select-party'], [data-action='select-item']", function() {
		const report = get_active_report(report_modules, state);

		if (report && report.key === "item_full_cycle") {
			open_report_item_picker(page, report_modules, state);
			return;
		}

		open_report_party_picker(page, report_modules, state);
	});

	$body.on("click.ledgixReports", "[data-action='print']", function(e) {
		e.preventDefault();
		e.stopPropagation();

		const row_index = $(this).data("row-index");
		if (row_index !== undefined) {
			print_single_ledgix_report_row(page, report_modules, state, cint(row_index));
			return;
		}

		if (get_selected_report_rows(state).length) {
			print_selected_ledgix_report_rows(page, report_modules, state);
			return;
		}

		print_active_ledgix_report(page, report_modules, state);
	});

	$body.on("click.ledgixReports", ".lx-report-search-clear", function() {
		state.search = "";
		state.page = 1;
		$body.find(".lx-report-search input").val("").focus();
		$body.find(".lx-report-search-clear").removeClass("visible");
		hide_item_intelligence_search_picker(page);
		load_table_report(page, report_modules, state);
	});

	$body.on("input.ledgixReports", ".lx-report-search input", function() {
		const report = get_active_report(report_modules, state);
		const value = $(this).val().trim();

		$body.find(".lx-report-search-clear").toggleClass("visible", !!value);

		if (report && report.key === "item_full_cycle" && !get_item_filter_value(state.table_filters)) {
			state.search = value;
			state.page = 1;
			render_item_intelligence_select_first_state(page, report, state, value);
			load_item_intelligence_search_picker(page, report_modules, state, value);
			return;
		}

		hide_item_intelligence_search_picker(page);
		state.search = value;
		state.page = 1;
		debounced_search();
	});

	$body.on("click.ledgixReports", ".lx-item-intel-search-option", function(e) {
		e.preventDefault();
		const item = String($(this).data("item") || "").trim();
		if (!item) return;
		select_item_intelligence_item(page, report_modules, state, item);
	});

	$body.on("keydown.ledgixReports", ".lx-report-search input", function(e) {
		const report = get_active_report(report_modules, state);
		if (!report || report.key !== "item_full_cycle" || get_item_filter_value(state.table_filters)) return;
		if (e.key !== "Enter") return;

		const $first = $(page.body).find(".lx-item-intel-search-option").first();
		if (!$first.length) return;
		e.preventDefault();
		$first.trigger("click");
	});

	$body.on("click.ledgixReports", "[data-action='date-range']", function() {
		show_date_range_dialog(page, report_modules, state, $(this).data("scope") || "table");
	});

	$body.on("click.ledgixReports", "[data-action='advanced-filters']", function() {
		show_advanced_filter_dialog(page, report_modules, state, $(this).data("scope") || "table");
	});

	$body.on("click.ledgixReports", "[data-action='clear-table-controls']", function() {
		state.search = "";
		state.table_date_preset = "this_month";
		state.table_from_date = frappe.datetime.month_start();
		state.table_to_date = frappe.datetime.month_end();
		state.table_filters = get_empty_report_filters();
		state.sort_by = "";
		state.sort_order = "asc";
		state.page = 1;
		$body.find(".lx-report-search input").val("").focus();
		$body.find(".lx-report-search-clear").removeClass("visible");
		hide_item_intelligence_search_picker(page);
		update_report_filter_state_ui(page, state);
		update_item_intelligence_selection_ui(page, state);
		load_table_report(page, report_modules, state);
	});

	$body.on("click.ledgixReports", ".lx-report-filter-box[data-action='refresh-report'], .lx-report-header-btn[data-action='refresh-page']", function() {
		load_active_report(page, report_modules, state);
	});

	$body.on("click.ledgixReports", ".lx-chart-mode-pills button", function() {
		const mode = $(this).data("chart-mode") || "value";
		state.chart_mode = mode;
		$(this).closest(".lx-chart-mode-pills").attr("data-active", mode);
		$body.find(".lx-chart-mode-pills button").removeClass("active");
		$(this).addClass("active");
		render_report_chart(page, state);
	});

	$body.on("change.ledgixReports", ".lx-chart-type-select", function() {
		state.chart_type = ["line", "bar"].includes($(this).val()) ? $(this).val() : "line";
		$body.find(".lx-chart-type-toggle").attr("data-chart-type", state.chart_type);
		$body.find("[data-chart-type-option]").removeClass("active")
			.filter(`[data-chart-type-option='${state.chart_type}']`).addClass("active");
		render_report_chart(page, state);
	});

	$body.on("click.ledgixReports", "[data-chart-type-option]", function() {
		state.chart_type = ["line", "bar"].includes($(this).data("chart-type-option"))
			? $(this).data("chart-type-option")
			: "line";

		$body.find(".lx-chart-type-toggle").attr("data-chart-type", state.chart_type);
		$body.find("[data-chart-type-option]").removeClass("active");
		$(this).addClass("active");
		render_report_chart(page, state);
	});

	$body.on("click.ledgixReports", "[data-action='toggle-analytics']", function() {
		const was_collapsed = !!state.analytics_collapsed;

		state.analytics_collapsed = !state.analytics_collapsed;
		update_analytics_panel_state(page, state);

		if (was_collapsed && !state.analytics_collapsed) {
			const report = get_active_report(report_modules, state);

			if (report && report.key === "item_full_cycle") {
				render_lifecycle_flow(page, report, state);
			} else {
				render_chart_loading(page);
				load_chart_report(page, report_modules, state);
			}
		}
	});

	$body.on("click.ledgixReports", "[data-action='toggle-item-cycle-guide']", function() {
		state.item_cycle_guide_open = !state.item_cycle_guide_open;
		render_item_cycle_guide(page, get_active_report(report_modules, state), state);
	});

	$body.on("click.ledgixReports", ".lx-pagination-btn", function() {
		const action = $(this).data("page-action");
		const total_pages = Math.max(1, Math.ceil((state.total_count || 0) / state.page_size));

		if (action === "prev" && state.page > 1) state.page -= 1;
		else if (action === "next" && state.page < total_pages) state.page += 1;
		else return;

		load_table_report(page, report_modules, state);
	});

	$body.on("click.ledgixReports", ".lx-report-table thead th[data-sort-key]", function() {
		const sort_key = $(this).data("sort-key");
		if (!sort_key) return;

		if (state.sort_by === sort_key) {
			state.sort_order = state.sort_order === "asc" ? "desc" : "asc";
		} else {
			state.sort_by = sort_key;
			state.sort_order = "asc";
		}

		state.page = 1;
		load_table_report(page, report_modules, state);
	});

	$body.on("change.ledgixReports", ".lx-report-select-all", function() {
		const checked = $(this).is(":checked");

		(state.rows || []).forEach((row, row_index) => {
			const key = get_report_row_key(row, row_index);
			if (checked) state.selected_rows[key] = Object.assign({}, row, { __page: state.page });
			else delete state.selected_rows[key];
		});

		render_table_rows(page, get_active_report(report_modules, state), state);
		render_summary(page, get_active_report(report_modules, state), state);
		render_bulk_selection_toolbar(page, state);
	});

	$body.on("change.ledgixReports", ".lx-report-row-checkbox", function() {
		const row_index = cint($(this).data("row-index"));
		const row = (state.rows || [])[row_index];
		if (!row) return;

		const key = get_report_row_key(row, row_index);
		if ($(this).is(":checked")) state.selected_rows[key] = Object.assign({}, row, { __page: state.page });
		else delete state.selected_rows[key];

		render_table_rows(page, get_active_report(report_modules, state), state);
		render_summary(page, get_active_report(report_modules, state), state);
		render_bulk_selection_toolbar(page, state);
	});

	$body.on("click.ledgixReports", "[data-bulk-action='clear']", function() {
		clear_report_selection(page, state);
		render_summary(page, get_active_report(report_modules, state), state);
	});

	$body.on("click.ledgixReports", ".lx-table-action-btn[data-action='view']", function() {
		const row_index = cint($(this).data("row-index"));
		const row = state.rows[row_index];
		if (!row) return;
		show_report_preview_modal(get_active_report(report_modules, state), row);
	});

	$body.on("click.ledgixReports", ".lx-report-header-btn[data-action='export']", function(e) {
		e.preventDefault();
		e.stopPropagation();

		if (get_selected_report_rows(state).length) {
			export_selected_ledgix_report_rows_csv(page, report_modules, state);
			return;
		}

		export_active_ledgix_report_csv(page, report_modules, state);
	});

	$body.on("click.ledgixReports", ".lx-table-action-btn[data-action='export']", function(e) {
		e.preventDefault();
		e.stopPropagation();
		export_single_ledgix_report_row_csv(page, report_modules, state, cint($(this).data("row-index")));
	});

}

function get_initial_ledgix_report_key(report_modules) {
	const report_key = new URLSearchParams(window.location.search || "").get("report");
	return report_modules.some((report) => report.key === report_key) ? report_key : "sales";
}

function update_ledgix_report_url(report_key) {
	const clean_key = encodeURIComponent(report_key || "sales");
	window.history.pushState({}, "", `/app/ledgix-reports?report=${clean_key}`);
}

function sync_ledgix_report_from_url(page, report_modules, state) {
	let next_key = get_initial_ledgix_report_key(report_modules);
	next_key = get_safe_report_key_for_mode(next_key, state);
	if (!next_key || next_key === state.active_key) {
		window.LedgixNavigator?.updateActiveState?.();
		return;
	}

	const $body = $(page.body);
	state.active_key = next_key;
	state.page = 1;
	state.search = "";
	state.sort_by = "";
	state.sort_order = "asc";
	state.table_filters = get_empty_report_filters();
	state.chart_filters = get_empty_report_filters();
	clear_report_selection(page, state);

	$body.find(".lx-report-module-btn").removeClass("active");
	$body.find(`.lx-report-module-btn[data-report-key="${next_key}"]`).addClass("active");
	window.LedgixNavigator?.updateActiveState?.();
	load_active_report(page, report_modules, state);
}


// ============================================================
// BOOT / MODE
// ============================================================

function load_ledgix_report_boot(page, report_modules, state) {
	frappe.call({
		method: "ledgix_saas.api.api.get_reports_boot_data",
		callback(r) {
			const data = r.message || {};
			state.stock_control_mode = data.stock_control_mode || "Strict Inventory";
			window.LedgixNavigator?.setMode?.(state.stock_control_mode);
			apply_report_mode_ui(page, report_modules, state);
			load_active_report(page, report_modules, state);
		},
		error() {
			state.stock_control_mode = "Strict Inventory";
			window.LedgixNavigator?.setMode?.(state.stock_control_mode);
			apply_report_mode_ui(page, report_modules, state);
			load_active_report(page, report_modules, state);
		}
	});
}

function is_billing_mode(state) {
	return String(state.stock_control_mode || "").toLowerCase() === "billing only";
}

function is_inventory_mode_only_report(key) {
	const report = get_ledgix_report_modules().find((module) => module.key === key);
	return !!(report && report.inventory_only) || ["purchases", "stock", "inventory", "suppliers"].includes(key);
}

function get_safe_report_key_for_mode(key, state) {
	if (is_billing_mode(state) && is_inventory_mode_only_report(key)) return "sales";
	return key || "sales";
}

function apply_report_mode_ui(page, report_modules, state) {
	const billing = is_billing_mode(state);
	const $body = $(page.body);
	const $page = $body.find(".lx-reports-page").first();
	const $badge = $body.find("[data-mode-badge]");

	$page
		.removeClass("is-mode-loading")
		.toggleClass("is-billing-mode", billing)
		.toggleClass("is-inventory-mode", !billing);

	$badge
		.toggleClass("lx-mode-billing", billing)
		.toggleClass("lx-mode-inventory", !billing)
		.find("span")
		.text(billing ? "Billing Mode" : "Inventory Mode");

	$badge.find("i").attr("class", billing ? "fa fa-file-text-o" : "fa fa-shield");

	$body.find(".lx-report-module-btn").each(function() {
		const key = $(this).data("report-key");
		const inventory_only = is_inventory_mode_only_report(key);
		$(this)
			.attr("data-inventory-only", inventory_only ? "1" : null)
			.toggle(!(billing && inventory_only));
	});

	if (billing && is_inventory_mode_only_report(state.active_key)) {
		state.active_key = "sales";
		$body.find(".lx-report-module-btn").removeClass("active");
		$body.find(".lx-report-module-btn[data-report-key='sales']").addClass("active");
	}
}

function update_analytics_panel_state(page, state) {
	const collapsed = !!state.analytics_collapsed;
	const $panel = $(page.body).find(".lx-report-analytics-panel");
	$panel.toggleClass("collapsed", collapsed).toggleClass("open", !collapsed);
	$panel.find(".lx-analytics-collapse-bar").attr("aria-expanded", collapsed ? "false" : "true");
	$panel.find(".lx-analytics-collapse-bar > i").attr("class", collapsed ? "fa fa-angle-down" : "fa fa-angle-up");
}

// ============================================================
// DATA LOADING
// ============================================================

function load_active_report(page, report_modules, state) {
	const safe_key = get_safe_report_key_for_mode(state.active_key, state);
	if (safe_key !== state.active_key) {
		state.active_key = safe_key;
		update_ledgix_report_url(safe_key);
		apply_report_mode_ui(page, report_modules, state);
	}

	const report = get_active_report(report_modules, state);
	render_report_shell(page, report, state);

	if (!report.api_method) {
		render_report_data(page, report, state, {
			rows: [],
			summary: {},
			total_count: 0,
			table_requires_party: 0,
			page: state.page,
			page_size: state.page_size,
			chart_data: []
		});
		return;
	}

	// Load table records every time a report/module opens.
	load_table_report(page, report_modules, state);

	// Load chart only when analytics panel is open.
	if (!state.analytics_collapsed) {
		state.chart_data = [];

		if (report && report.key === "item_full_cycle") {
			render_lifecycle_flow(page, report, state);
		} else {
			render_chart_loading(page);
			load_chart_report(page, report_modules, state);
		}
	}
}

function load_chart_report(page, report_modules, state) {
	const report = get_active_report(report_modules, state);
	if (!report || !report.api_method || state.analytics_collapsed || report.disable_chart) return;
	if (is_billing_mode(state) && is_inventory_mode_only_report(report.key)) return;

	const request_id = ++state.chart_request_id;
	const report_key = state.active_key;

	frappe.call({
		method: report.api_method,
		args: build_report_api_args(state, "chart"),
		callback(r) {
			if (request_id !== state.chart_request_id || report_key !== state.active_key || state.analytics_collapsed) return;

			const data = r.message || {};
			state.chart_data = data.chart_data || [];
			state.chart_summary = data.summary || {};
			state.chart_requires_party = get_requires_party(report, state, "chart", data);
			render_summary(page, report, state);
			render_report_chart(page, state);
		},
		error() {
			if (request_id !== state.chart_request_id || report_key !== state.active_key || state.analytics_collapsed) return;

			state.chart_data = [];
			render_report_chart(page, state);
			frappe.show_alert({ message: "Unable to load chart data", indicator: "orange" });
		}
	});
}

function load_table_report(page, report_modules, state) {
	const report = get_active_report(report_modules, state);
	if (!report || !report.api_method) return;
	if (is_billing_mode(state) && is_inventory_mode_only_report(report.key)) {
		state.loading = false;
		state.active_key = "sales";
		apply_report_mode_ui(page, report_modules, state);
		load_active_report(page, report_modules, state);
		return;
	}

	const request_id = ++state.table_request_id;
	const report_key = state.active_key;

	state.loading = true;
	render_table_loading(page, report);

	frappe.call({
		method: report.api_method,
		args: build_report_api_args(state, "table"),
		callback(r) {
			if (request_id !== state.table_request_id || report_key !== state.active_key) return;

			state.loading = false;
			const data = r.message || {};
			render_table_report_data(page, report, state, data);
		},
		error() {
			if (request_id !== state.table_request_id || report_key !== state.active_key) return;

			state.loading = false;
			render_report_error(page, report, __("Unable to load report data."));
		}
	});
}
function build_report_api_args(state, scope) {
	const is_chart = scope === "chart";
	const filters = is_chart ? (state.chart_filters || {}) : (state.table_filters || {});
	const active_key = state.active_key || "";

	const args = {
		from_date: is_chart ? state.chart_from_date : state.table_from_date,
		to_date: is_chart ? state.chart_to_date : state.table_to_date,
		search: is_chart ? "" : state.search,
		status: filters.status || "",
		type: filters.type || "",
		party: filters.party || "",
		min_amount: filters.min_amount || "",
		max_amount: filters.max_amount || "",
		page: is_chart ? 1 : state.page,
		page_size: is_chart ? 120 : state.page_size,
		sort_by: is_chart ? "" : (state.sort_by || ""),
		sort_order: is_chart ? "" : (state.sort_order || "asc")
	};

	if (active_key === "item_full_cycle") {
		args.item = get_item_filter_value(filters);
		args.view_mode = filters.type || state.stock_control_mode || "Strict Inventory";
	}

	return args;
}

function get_item_filter_value(filters) {
	const value = filters && (filters.item || filters.party);
	return String(value || "").trim();
}

function render_report_shell(page, report, state) {
	const $body = $(page.body);
	const is_item_intelligence = report && report.key === "item_full_cycle";

	if (is_item_intelligence) {
		state.analytics_collapsed = false;
	}

	$body.find(".lx-report-chart-card .lx-report-card-header h4").text(report.title);
	$body.find(".lx-report-table-card .lx-report-card-header h4").text(report.table_title);
	$body.find(".lx-reports-page").toggleClass("is-item-intelligence-report", is_item_intelligence);
	$body.find(".lx-report-chart-card .lx-report-card-header h4").text(is_item_intelligence ? "Lifecycle Flow" : report.title);
	$body.find(".lx-report-search input").attr("placeholder", report.search_placeholder || "Search report...");
	$body.find(".lx-selected-range-label").text(get_date_range_label(state, "chart"));
	$body.find(".lx-report-date-filter[data-scope='chart'] span").text(get_date_range_label(state, "chart"));
	$body.find(".lx-chart-type-select").val(state.chart_type || "line");
	$body.find(".lx-chart-mode-pills").attr("data-active", state.chart_mode || "value");
	$body.find(".lx-chart-mode-pills button").removeClass("active");
	$body.find(`.lx-chart-mode-pills button[data-chart-mode='${state.chart_mode || "value"}']`).addClass("active");
	$body.find(".lx-chart-trend-badge span").text("Loading");
	update_analytics_panel_state(page, state);
	update_report_filter_state_ui(page, state);

	if (!state.analytics_collapsed) {
		if (is_item_intelligence) render_lifecycle_flow(page, report, state);
		else render_chart_loading(page);
	}

	$body.find(".lx-report-summary-list").html(report.summary.map((item) => `
		<div class="lx-summary-item">
			<span>${frappe.utils.escape_html(item.label)}</span>
			<strong>${format_report_value(0, item.type)}</strong>
		</div>
	`).join(""));

	$body.find(".lx-report-table thead tr").html(`
		<th class="lx-select-col">
			<label class="lx-report-check-wrap" title="Select all visible rows">
				<input type="checkbox" class="lx-report-select-all" />
				<span></span>
			</label>
		</th>
		${report.columns.map((column) => render_table_header_cell(column, state)).join("")}
	`);

	const is_statement_report = ["customers", "suppliers"].includes(report.key);
	const show_selector_button = is_statement_report || is_item_intelligence;

	const $selector_btn = $body.find(".lx-report-table-party-btn");

	$selector_btn
		.toggle(show_selector_button)
		.attr("data-action", is_item_intelligence ? "select-item" : "select-party")
		.find("span")
		.text(
			is_item_intelligence
				? get_item_filter_value(state.table_filters) || "Select Item"
				: report.key === "suppliers"
					? "Select Supplier"
					: "Select Customer"
		);

	$selector_btn.find("i").attr(
		"class",
		is_item_intelligence ? "fa fa-cubes" : "fa fa-user-circle-o"
	);

	if (is_item_intelligence) {
		const $meta = $body.find(".lx-report-table-meta").first();
		const $date_btn = $meta.find(".lx-report-date-filter[data-scope='table']").first();

		if ($date_btn.length) {
			$selector_btn.insertBefore($date_btn);
		}
	}

	ensure_item_intelligence_search_picker(page);
	update_item_intelligence_selection_ui(page, state);

	render_item_cycle_guide(page, report, state);
}

function render_table_header_cell(column, state) {
	const sortable = !column.is_action;
	const active = sortable && state.sort_by === column.key;
	const classes = [
		column.align === "right" ? "lx-text-right" : "",
		sortable ? "lx-sortable-col" : "",
		active ? "lx-sort-active" : ""
	].filter(Boolean).join(" ");

	return `
		<th class="${classes}" ${sortable ? `data-sort-key="${frappe.utils.escape_html(column.key)}"` : ""}>
			<span>${frappe.utils.escape_html(column.label)}</span>
		</th>
	`;
}

function render_chart_loading(page) {
	$(page.body).find(".lx-report-chart-real").html(`
		<div class="lx-chart-loading-clean">
			<div class="lx-chart-loading-line"></div>
			<div class="lx-chart-loading-line short"></div>
			<span>Preparing report chart…</span>
		</div>
	`);
}

function render_report_data(page, report, state, data) {
	state.rows = normalize_report_rows(data.rows || [], state);
	state.summary = data.summary || {};
	state.chart_summary = data.summary || {};
	state.total_count = cint(data.total_count || 0);
	state.page = cint(data.page || state.page || 1);
	state.page_size = cint(data.page_size || state.page_size || 15);
	state.chart_data = data.chart_data || [];
	state.table_requires_party = get_requires_party(report, state, "table", data);

	render_summary(page, report, state);
	render_lifecycle_flow(page, report, state);
	render_table_rows(page, report, state);
	render_pagination(page, state);

	if (!state.analytics_collapsed) {
		render_report_chart(page, state);
	}
}

function render_table_report_data(page, report, state, data) {
	state.rows = normalize_report_rows(data.rows || [], state);
	state.summary = data.summary || {};
	state.total_count = cint(data.total_count || 0);
	state.page = cint(data.page || state.page || 1);
	state.page_size = cint(data.page_size || state.page_size || 15);
	state.table_requires_party = get_requires_party(report, state, "table", data);

	render_summary(page, report, state);
	render_lifecycle_flow(page, report, state);
	render_table_rows(page, report, state);
	render_pagination(page, state);
}

function get_requires_party(report, state, scope, data) {
	const filters = scope === "chart" ? state.chart_filters : state.table_filters;

	if (report && report.requires_item) {
		const has_item = !!get_item_filter_value(filters);
		return has_item ? cint(data && data.requires_party || 0) : 1;
	}

	if (!["customers", "suppliers"].includes(report.key)) return cint(data && data.requires_party || 0);

	const has_party = !!(filters && filters.party);
	const has_scope_search = scope === "table" ? !!state.search : false;
	return !has_scope_search && !has_party ? 1 : cint(data && data.requires_party || 0);
}

function has_summary_values(summary) {
	return !!(summary && Object.keys(summary).length);
}

function render_summary(page, report, state) {
	const selected_rows = get_selected_report_rows(state);
	const using_selection = selected_rows.length > 0;
	const item_intelligence = report && report.key === "item_full_cycle";
	let summary = {};

	if (using_selection) {
		summary = calculate_selected_summary(report, selected_rows);
		state.summary_source = "selection";
	} else if (item_intelligence) {
		summary = state.summary || {};
		state.summary_source = "report";
	} else if (state.analytics_collapsed) {
		summary = state.summary || {};
		state.summary_source = "table";
	} else {
		summary = has_summary_values(state.chart_summary) ? state.chart_summary : (state.summary || {});
		state.summary_source = has_summary_values(state.chart_summary) ? "chart" : "table";
	}

	const summary_label = {
		selection: "Selected rows",
		report: "Report",
		table: "Table",
		chart: "Chart"
	}[state.summary_source] || "Report";

	$(page.body).find(".lx-summary-source-label")
		.text(summary_label)
		.toggleClass("is-selection", using_selection);

	$(page.body).find(".lx-report-summary-list").html(report.summary.map((item) => {
		const raw_value = summary[item.key];
		return `
			<div class="lx-summary-item">
				<span>${frappe.utils.escape_html(item.label)}</span>
				<strong>${format_report_value(raw_value, item.type)}</strong>
			</div>
		`;
	}).join(""));
}

function render_item_intelligence_select_first_state(page, report, state, search_value) {
	if (!report || report.key !== "item_full_cycle") return;

	const safe_search = frappe.utils.escape_html(search_value || "");
	const $body = $(page.body);

	render_lifecycle_flow(page, report, state);

	$body.find(".lx-report-table tbody").html(`
		<tr>
			<td colspan="${report.columns.length + 1}">
				<div class="lx-report-empty-state lx-item-intel-select-first-table">
					<i class="fa fa-cubes"></i>
					<strong>Select exact item first</strong>
					<span>${safe_search ? `“${safe_search}” is typed in record search. Use Select Item to choose the exact Ledgix Item, then this same search box will filter lifecycle rows.` : "Use Select Item to choose one item, then search lots, sales, returns, supplier, or customer rows."}</span>
				</div>
			</td>
		</tr>
	`);

	render_pagination(page, Object.assign({}, state, { total_count: 0, page: 1 }));
}

function render_table_rows(page, report, state) {
	const $tbody = $(page.body).find(".lx-report-table tbody");
	const rows = state.rows || [];

	if (state.table_requires_party) {
		$tbody.html(`
			<tr>
				<td colspan="${report.columns.length + 1}">
					<div class="lx-report-empty-state ${report.requires_item ? "lx-item-intel-select-first-table" : ""}">
						<i class="fa ${report.requires_item ? "fa-cubes" : "fa-user-circle-o"}"></i>
						<strong>${report.requires_item ? "Select item to view lifecycle intelligence" : `Select a ${report.key === "suppliers" ? "supplier" : "customer"} to view statement`}</strong>
						<span>${report.requires_item ? "Click Select Item, choose the exact Ledgix Item, then search inside its lifecycle records." : "Use Select Party or table filters, then apply."}</span>
					</div>
				</td>
			</tr>
		`);
		return;
	}

	if (!rows.length) {
		$tbody.html(`
			<tr>
				<td colspan="${report.columns.length + 1}">
					<div class="lx-report-empty-state">
						<i class="fa fa-folder-open-o"></i>
						<strong>No ${frappe.utils.escape_html(report.label.toLowerCase())} records found</strong>
						<span>Try changing table date, search, or filters. Chart remains unchanged.</span>
					</div>
				</td>
			</tr>
		`);
		render_bulk_selection_toolbar(page, state);
		return;
	}

	$tbody.html(rows.map((row, row_index) => {
		const row_key = get_report_row_key(row, row_index);
		const checked = !!(state.selected_rows || {})[row_key];

		return `
			<tr class="${checked ? "lx-row-selected" : ""}">
				<td class="lx-select-col">
					<label class="lx-report-check-wrap" title="Select row">
						<input type="checkbox" class="lx-report-row-checkbox" data-row-index="${row_index}" ${checked ? "checked" : ""} />
						<span></span>
					</label>
				</td>
				${report.columns.map((column) => render_table_cell(column, row, row_index)).join("")}
			</tr>
		`;
	}).join(""));

	render_bulk_selection_toolbar(page, state);
}


function render_table_cell(column, row, row_index) {
	if (column.is_action) {
		return `
			<td>
				<div class="lx-report-row-actions">
					<button class="lx-table-action-btn" data-action="view" data-row-index="${row_index}" title="View">
						<i class="fa fa-eye"></i>
					</button>
					<button class="lx-table-action-btn" data-action="print" data-row-index="${row_index}" title="Print">
						<i class="fa fa-print"></i>
					</button>
					<button class="lx-table-action-btn" data-action="export" data-row-index="${row_index}" title="Export">
						<i class="fa fa-download"></i>
					</button>
				</div>
			</td>
		`;
	}

	const value = row[column.key];
	const classes = [
		column.align === "right" ? "lx-text-right" : "",
		column.key === "status" ? "lx-status-cell" : ""
	].filter(Boolean).join(" ");

	if (["status", "stock_status", "cycle_status", "lot_status"].includes(column.key)) {
		return `<td class="${classes}">${render_status_badge(value)}</td>`;
	}

	if (["payment_mode", "type", "event_type", "row_type"].includes(column.key)) {
		return `<td>${render_soft_badge(value || "-")}</td>`;
	}

	if (column.key === "impact_type") {
		return `<td>${render_impact_badge(value || "-")}</td>`;
	}

	if (column.key === "flow_step") {
		return `<td>${render_step_badge(value || row.step || "-")}</td>`;
	}

	if (column.key === "stock_flow") {
		return `<td>${render_stock_flow_value(row)}</td>`;
	}

	return `<td class="${classes}">${format_report_value(value, column.type)}</td>`;
}

function render_table_loading(page, report) {
	$(page.body).find(".lx-report-table tbody").html(`
		<tr>
			<td colspan="${report.columns.length + 1}">
				<div class="lx-report-loading">
					<div></div><div></div><div></div>
				</div>
			</td>
		</tr>
	`);
}

function render_report_error(page, report, message) {
	$(page.body).find(".lx-report-table tbody").html(`
		<tr>
			<td colspan="${report.columns.length + 1}">
				<div class="lx-report-empty-state lx-report-error-state">
					<i class="fa fa-warning"></i>
					<strong>${frappe.utils.escape_html(message)}</strong>
					<span>Check the backend method or console error, then refresh.</span>
				</div>
			</td>
		</tr>
	`);
}

function render_pagination(page, state) {
	const total = cint(state.total_count || 0);
	const page_no = cint(state.page || 1);
	const page_size = cint(state.page_size || 15);
	const total_pages = Math.max(1, Math.ceil(total / page_size));

	const start = total ? ((page_no - 1) * page_size) + 1 : 0;
	const end = Math.min(page_no * page_size, total);

	const $body = $(page.body);

	$body.find(".lx-report-pagination-info").text(`Showing ${start}–${end} of ${total} entries`);
	$body.find(".lx-pagination-page").text(page_no);
	$body.find(".lx-report-total-badge").text(`${total} records`);

	$body.find(".lx-pagination-btn[data-page-action='prev']").prop("disabled", page_no <= 1);
	$body.find(".lx-pagination-btn[data-page-action='next']").prop("disabled", page_no >= total_pages);
	render_bulk_selection_toolbar(page, state);
}

function render_report_chart(page, state) {
	const rows = state.chart_data || [];
	const $body = $(page.body);
	const $badge = $body.find(".lx-chart-trend-badge span");
	const $real = $body.find(".lx-report-chart-real");

	state.report_chart = null;
	$real.attr("data-chart-loading", "0").empty();

	if (state.active_key === "item_full_cycle") {
		render_lifecycle_flow(page, get_active_report(get_ledgix_report_modules(), state), state);
		return;
	}

	const is_statement_report = ["customers", "suppliers"].includes(state.active_key);
	const party_label = state.active_key === "suppliers" ? "supplier" : "customer";

	if (state.chart_requires_party) {
		$badge.text("Select Party");
		$real.html(`
			<div class="lx-chart-empty-clean lx-chart-empty-statement">
				<i class="fa fa-user-circle-o"></i>
				<strong>Select ${party_label} to generate statement chart</strong>
				<span>Use Select ${to_title_case(party_label)} or Advanced Filters → Party.</span>
			</div>
		`);
		return;
	}

	const mode = state.chart_mode === "count" ? "count" : "value";

	const clean_rows = (rows || [])
		.map((row) => {
			const value = Number(mode === "count" ? row.count : row.value);
			return {
				label: format_report_chart_x_label(row, state),
				value: Number.isFinite(value) ? value : 0
			};
		})
		.filter((row) => row.label && Number.isFinite(row.value));

	if (!clean_rows.length) {
		$badge.text("No Data");
		$real.html(`
			<div class="lx-chart-empty-clean">
				<i class="fa fa-line-chart"></i>
				<strong>No chart data for this range</strong>
				<span>Try another date range or clear filters.</span>
			</div>
		`);
		return;
	}

	const chart_type = state.chart_type === "bar" ? "bar" : "line";
	const values = clean_rows.map((row) => row.value);
	const max_value = Math.max(...values, 0);
	const safe_max = max_value > 0 ? max_value : 1;

	const width = 900;
	const height = 250;
	const pad = { top: 22, right: 24, bottom: 42, left: 56 };
	const plot_w = width - pad.left - pad.right;
	const plot_h = height - pad.top - pad.bottom;

	const point_x = (index) => {
		if (clean_rows.length === 1) return pad.left + plot_w / 2;
		return pad.left + (index / (clean_rows.length - 1)) * plot_w;
	};

	const point_y = (value) => {
		return pad.top + plot_h - ((value || 0) / safe_max) * plot_h;
	};

	const points = clean_rows.map((row, index) => ({
		x: point_x(index),
		y: point_y(row.value),
		value: row.value,
		label: row.label
	}));

	const grid_lines = [0, 0.25, 0.5, 0.75, 1].map((ratio) => {
		const y = pad.top + plot_h - ratio * plot_h;
		const value = safe_max * ratio;
		return `
			<line x1="${pad.left}" y1="${y}" x2="${width - pad.right}" y2="${y}" class="lx-svg-chart-grid" />
			<text x="${pad.left - 10}" y="${y + 4}" text-anchor="end" class="lx-svg-chart-axis-label">
				${mode === "count" ? Math.round(value) : format_compact_chart_value(value)}
			</text>
		`;
	}).join("");

	const x_labels = points
		.filter((point, index) => {
			if (clean_rows.length <= 8) return true;
			const step = Math.ceil(clean_rows.length / 6);
			return index === 0 || index === clean_rows.length - 1 || index % step === 0;
		})
		.map((point) => `
			<text x="${point.x}" y="${height - 14}" text-anchor="middle" class="lx-svg-chart-axis-label">
				${frappe.utils.escape_html(point.label)}
			</text>
		`).join("");

	const chart_body = chart_type === "bar"
		? render_ledgix_svg_bars(points, pad, plot_h, clean_rows.length)
		: render_ledgix_svg_line(points, pad, plot_h, width);

	$badge.text(is_statement_report ? "Statement Trend" : (mode === "count" ? "Count Trend" : "Value Trend"));

	$real.html(`
		<div class="lx-svg-chart-wrap">
			<svg class="lx-svg-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="Report chart">
				${grid_lines}
				<line x1="${pad.left}" y1="${pad.top + plot_h}" x2="${width - pad.right}" y2="${pad.top + plot_h}" class="lx-svg-chart-axis" />
				${chart_body}
				${x_labels}
			</svg>
		</div>
	`);
}

function render_lifecycle_flow(page, report, state) {
	if (!report || report.key !== "item_full_cycle") return;

	const $body = $(page.body);
	const $badge = $body.find(".lx-chart-trend-badge span");
	const $real = $body.find(".lx-report-chart-real");
	const summary = state.summary || {};
	const selected_item = get_item_filter_value(state.table_filters);
	const has_item = !!selected_item && !state.table_requires_party;

	$badge.text(has_item ? "Lifecycle Ready" : "Select Item");

	if (!has_item) {
		$real.html(`
			<div class="lx-item-intel-empty">
				<div class="lx-item-intel-empty-copy">
					<span class="lx-item-intel-kicker">Item Intelligence</span>
					<strong>Select one item to start lifecycle review</strong>
					<p>This report is intentionally single-item first. Choose an item, then Ledgix will show purchase lots, sold quantity, returns, remaining lot quantity, selling amount, profit, and loss in one clean flow.</p>
				</div>
				<div class="lx-item-intel-empty-actions">
					<button type="button" class="lx-item-intel-primary-btn" data-action="select-item">
						<i class="fa fa-cubes"></i>
						<span>Select Item</span>
					</button>
					<button type="button" class="lx-item-intel-secondary-btn" data-action="advanced-filters" data-scope="table">
						<i class="fa fa-sliders"></i>
						<span>Advanced Filters</span>
					</button>
				</div>
			</div>
		`);
		return;
	}

	const metrics = [
		{ key: "purchased_qty", label: "Purchased", type: "number", tone: "in", icon: "fa-shopping-bag" },
		{ key: "sold_qty", label: "Sold", type: "number", tone: "out", icon: "fa-arrow-up" },
		{ key: "returned_qty", label: "Returned", type: "number", tone: "return", icon: "fa-undo" },
		{ key: "net_sold_qty", label: "Net Sold", type: "number", tone: "neutral", icon: "fa-balance-scale" },
		{ key: "current_lot_qty", label: "Current Lot", type: "number", tone: "stock", icon: "fa-archive" }
	];

	const money_metrics = [
		{ key: "selling_amount", label: "Selling Amount", type: "currency", tone: "neutral" },
		{ key: "profit", label: "Profit", type: "currency", tone: "profit" },
		{ key: "loss", label: "Loss", type: "currency", tone: flt(summary.loss || 0) > 0 ? "loss" : "neutral" }
	];

	$real.html(`
		<div class="lx-item-intel-board">
			<div class="lx-item-intel-hero">
				<div>
					<span class="lx-item-intel-kicker">Selected Item</span>
					<h3>${frappe.utils.escape_html(selected_item)}</h3>
					<p>Real lifecycle movement from purchase lots, sales, returns, and current stock balance.</p>
				</div>
				<div class="lx-item-intel-actions">
					<button type="button" class="lx-item-intel-secondary-btn" data-action="select-item">
						<i class="fa fa-refresh"></i>
						<span>Change Item</span>
					</button>
					<button type="button" class="lx-item-intel-secondary-btn" data-action="advanced-filters" data-scope="table">
						<i class="fa fa-sliders"></i>
						<span>Filters</span>
					</button>
				</div>
			</div>

			<div class="lx-item-intel-flow">
				${metrics.map((item, index) => `
					<div class="lx-item-intel-step is-${item.tone}">
						<div class="lx-item-intel-step-icon"><i class="fa ${item.icon}"></i></div>
						<span>${frappe.utils.escape_html(item.label)}</span>
						<strong>${format_report_value(summary[item.key], item.type)}</strong>
					</div>
					${index < metrics.length - 1 ? `<div class="lx-item-intel-step-arrow"><i class="fa fa-angle-right"></i></div>` : ""}
				`).join("")}
			</div>

			<div class="lx-item-intel-money-grid">
				${money_metrics.map((item) => `
					<div class="lx-item-intel-money-card is-${item.tone}">
						<span>${frappe.utils.escape_html(item.label)}</span>
						<strong>${format_report_value(summary[item.key], item.type)}</strong>
					</div>
				`).join("")}
			</div>
		</div>
	`);
}

function render_ledgix_svg_line(points, pad, plot_h, width) {
	if (!points.length) return "";

	const path = points.map((point, index) => {
		return `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
	}).join(" ");

	const area_path = `
		${path}
		L ${points[points.length - 1].x.toFixed(2)} ${(pad.top + plot_h).toFixed(2)}
		L ${points[0].x.toFixed(2)} ${(pad.top + plot_h).toFixed(2)}
		Z
	`;

	return `
		<path d="${area_path}" class="lx-svg-chart-area"></path>
		<path d="${path}" class="lx-svg-chart-line"></path>
		${points.map((point) => `
			<circle cx="${point.x}" cy="${point.y}" r="4" class="lx-svg-chart-dot">
				<title>${frappe.utils.escape_html(point.label)}: ${format_number_safe(point.value)}</title>
			</circle>
		`).join("")}
	`;
}

function render_ledgix_svg_bars(points, pad, plot_h, count) {
	if (!points.length) return "";

	const available = Math.max(1, points.length);
	const slot = 820 / available;
	const bar_width = Math.max(8, Math.min(38, slot * 0.48));
	const base_y = pad.top + plot_h;

	return points.map((point) => {
		const height = Math.max(2, base_y - point.y);
		const x = point.x - bar_width / 2;

		return `
			<rect x="${x.toFixed(2)}" y="${point.y.toFixed(2)}" width="${bar_width.toFixed(2)}" height="${height.toFixed(2)}" rx="6" class="lx-svg-chart-bar">
				<title>${frappe.utils.escape_html(point.label)}: ${format_number_safe(point.value)}</title>
			</rect>
		`;
	}).join("");
}

function format_compact_chart_value(value) {
	const amount = Number(value || 0);

	if (amount >= 1000000) return `${(amount / 1000000).toFixed(1)}M`;
	if (amount >= 1000) return `${(amount / 1000).toFixed(1)}K`;

	return amount.toFixed(0);
}


function format_report_chart_x_label(row, state) {
	const raw = String(row.label || row.date || "").trim();
	if (!raw) return "-";

	const dt = parse_report_chart_date(raw);
	if (!dt) return raw;

	const from = parse_report_chart_date(state.chart_from_date);
	const to = parse_report_chart_date(state.chart_to_date);

	const range_days = from && to
		? Math.max(1, Math.round((to - from) / 86400000) + 1)
		: 0;

	if (range_days > 92 || /^\d{4}-\d{2}$/.test(raw)) {
		return dt.toLocaleString("en-US", { month: "short" });
	}

	return `${dt.getDate()} ${dt.toLocaleString("en-US", { month: "short" })}`;
}

function parse_report_chart_date(value) {
	if (!value) return null;

	const raw = String(value).trim();

	let match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
	if (match) {
		return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
	}

	match = raw.match(/^(\d{4})-(\d{2})$/);
	if (match) {
		return new Date(Number(match[1]), Number(match[2]) - 1, 1);
	}

	return null;
}

function get_report_chart_axis_steps(values, mode) {
	const max_value = Math.max(0, ...((values || []).map(value => flt(value || 0))));

	if (max_value <= 0) return [0];

	const rough_step = max_value / 4;
	const magnitude = Math.pow(10, Math.floor(Math.log10(rough_step || 1)));
	const normalized = rough_step / magnitude;
	let step = magnitude;

	if (normalized > 5) step = 10 * magnitude;
	else if (normalized > 2) step = 5 * magnitude;
	else if (normalized > 1) step = 2 * magnitude;

	if (mode === "count") step = Math.max(1, Math.ceil(step));

	const top = Math.ceil(max_value / step) * step;
	const ticks = [];
	for (let value = 0; value <= top; value += step) {
		ticks.push(value);
	}

	return ticks.slice(0, 6);
}


function normalize_report_rows(rows, state) {
	return (rows || []).map((row, index) => {
		const copy = Object.assign({}, row || {});
		const natural_key = copy.name || copy.invoice || copy.purchase || copy.return || copy.movement || copy.reference || copy.item;
		copy.__row_key = natural_key ? String(natural_key) : `${state.active_key || "report"}-page-${state.page || 1}-row-${index}`;
		return copy;
	});
}

// ============================================================
// BULK SELECTION
// ============================================================

function get_report_row_key(row, row_index) {
	const candidates = [
		row && row.__row_key,
		row && row.name,
		row && row.invoice,
		row && row.purchase,
		row && row.return,
		row && row.movement,
		row && row.reference,
		row && row.item
	].filter(Boolean);

	if (candidates.length) {
		return String(candidates[0]);
	}

	return `row-${row_index}`;
}

function get_selected_report_rows(state) {
	return Object.values(state.selected_rows || {});
}

function clear_report_selection(page, state) {
	state.selected_rows = {};
	render_bulk_selection_toolbar(page, state);
	$(page.body).find(".lx-report-select-all, .lx-report-row-checkbox").prop("checked", false);
	$(page.body).find(".lx-report-table tbody tr").removeClass("lx-row-selected");
}

function render_bulk_selection_toolbar(page, state) {
	const $body = $(page.body);
	const selected_count = get_selected_report_rows(state).length;
	const visible_count = (state.rows || []).length;
	const all_visible_selected = visible_count > 0 && (state.rows || []).every((row, index) => !!(state.selected_rows || {})[get_report_row_key(row, index)]);

	$body.find(".lx-report-select-all").prop("checked", all_visible_selected);
	const selected_pages = get_selected_page_count(state);
	$body.find(".lx-report-selected-badge")
		.toggle(!!selected_count)
		.text(selected_count ? `${selected_count} selected${selected_pages > 1 ? ` across ${selected_pages} pages` : ""}` : "0 selected");
	$body.find(".lx-report-clear-selection-btn").toggle(!!selected_count);

	$body.find(".lx-report-primary-btn[data-action='print'] span")
		.text(selected_count ? `Print ${selected_count}` : "Print");
	$body.find(".lx-report-header-btn[data-action='export']")
		.attr("title", selected_count ? `Export ${selected_count} selected` : "Export");
}


function get_selected_page_count(state) {
	const pages = new Set();
	Object.values(state.selected_rows || {}).forEach((row) => {
		if (row && row.__page) pages.add(row.__page);
	});
	return pages.size;
}

function calculate_selected_summary(report, rows) {
	const sum = (key) => rows.reduce((total, row) => total + flt(row[key] || 0), 0);
	const count = rows.length;

	if (report.key === "sales") {
		const total_sales = sum("amount");
		return { total_sales, total_profit: sum("profit"), invoice_count: count, avg_order: count ? total_sales / count : 0 };
	}

	if (report.key === "purchases") {
		const total_purchases = sum("amount");
		return { total_purchases, suppliers: new Set(rows.map(row => row.supplier).filter(Boolean)).size, items_bought: sum("total_qty"), avg_purchase: count ? total_purchases / count : 0 };
	}

	if (report.key === "returns") {
		return { return_amount: sum("amount"), return_count: count, items_returned: sum("total_qty"), return_rate: 0 };
	}

	if (report.key === "stock") {
		return {
			in_qty: rows.filter(row => String(row.type || "").toLowerCase().includes("in")).reduce((total, row) => total + flt(row.quantity || 0), 0),
			out_qty: rows.filter(row => String(row.type || "").toLowerCase().includes("out")).reduce((total, row) => total + flt(row.quantity || 0), 0),
			adjustments: rows.filter(row => String(row.type || "").toLowerCase().includes("adjust")).length,
			stock_value: sum("amount") || sum("value")
		};
	}

	if (report.key === "inventory") {
		return {
			inventory_value: sum("inventory_value"),
			total_items: count,
			low_stock: rows.filter(row => String(row.stock_status || "").toLowerCase() === "low stock").length,
			out_of_stock: rows.filter(row => String(row.stock_status || "").toLowerCase() === "out of stock").length
		};
	}

	if (report.key === "item_full_cycle") {
		const active_rows = rows.filter(row => {
			const is_cancelled = String(row.lot_status || "").trim().toLowerCase() === "cancelled";
			return !is_cancelled;
		});
		const active_mother_rows = active_rows.filter(row =>
			String(row.row_type || "").trim().toLowerCase() === "mother"
		);
		const active_sum = (key) => active_rows.reduce((total, row) => total + flt(row[key] || 0), 0);
		const active_mother_sum = (key) => active_mother_rows.reduce((total, row) => total + flt(row[key] || 0), 0);

		return {
			purchased_qty: active_mother_sum("purchased_qty"),
			current_lot_qty: active_mother_sum("current_lot_qty"),
			sold_qty: active_sum("sold_qty") || active_sum("sale_qty"),
			returned_qty: active_sum("returned_qty") || active_sum("return_qty"),
			net_sold_qty: active_sum("net_sold_qty"),
			selling_amount: active_sum("selling_amount"),
			profit: active_sum("profit"),
			loss: active_sum("loss")
		};
	}

	if (report.key === "profit") {
		const revenue = sum("revenue");
		const gross_profit = sum("profit");
		return { gross_profit, profit_margin: revenue ? (gross_profit / revenue) * 100 : 0, best_item: rows[0] && rows[0].item || "-", avg_profit: count ? gross_profit / count : 0 };
	}

	if (["customers", "suppliers"].includes(report.key)) {
		return {
			receivable: sum("debit") - sum("credit"),
			payable: sum("credit") - sum("debit"),
			customers: new Set(rows.map(row => row.customer || row.party).filter(Boolean)).size || count,
			suppliers: new Set(rows.map(row => row.supplier || row.party).filter(Boolean)).size || count,
			invoices: count,
			purchases: count,
			balance: rows.length ? flt(rows[rows.length - 1].balance || 0) : 0
		};
	}

	return {};
}

// ============================================================
// DIALOGS
// ============================================================

function show_date_range_dialog(page, report_modules, state, scope="table") {
	const is_chart = scope === "chart";
	const dialog = new frappe.ui.Dialog({
		title: is_chart ? "Chart Date Range" : "Table Date Range",
		fields: [
			{
				fieldtype: "Select",
				fieldname: "preset",
				label: "Range",
				options: ["Today", "This Week", "This Month", "Last 30 Days", "All to Today", "Custom"].join("\n"),
				default: date_preset_to_label(is_chart ? state.chart_date_preset : state.table_date_preset)
			},
			{ fieldtype: "Date", fieldname: "from_date", label: "From Date", default: is_chart ? state.chart_from_date : state.table_from_date },
			{ fieldtype: "Date", fieldname: "to_date", label: "To Date", default: is_chart ? state.chart_to_date : state.table_to_date }
		],
		secondary_action_label: "All to Today",
		secondary_action() {
			const today = frappe.datetime.get_today();
			dialog.set_value("preset", "All to Today");
			dialog.set_value("from_date", "");
			dialog.set_value("to_date", today);
		},
		primary_action_label: "Apply",
		primary_action(values) {
			const range = get_range_from_preset(values.preset, values.from_date, values.to_date);

			if (is_chart) {
				state.chart_date_preset = range.preset;
				state.chart_from_date = range.from_date;
				state.chart_to_date = range.to_date;
				$(page.body).find(".lx-selected-range-label").text(get_date_range_label(state, "chart"));
				$(page.body).find(".lx-report-date-filter[data-scope='chart'] span").text(get_date_range_label(state, "chart"));
				dialog.hide();

				if (!state.analytics_collapsed) {
					load_chart_report(page, report_modules, state);
				}

				return;
			}

			state.table_date_preset = range.preset;
			state.table_from_date = range.from_date;
			state.table_to_date = range.to_date;
			state.page = 1;
			dialog.hide();
			load_table_report(page, report_modules, state);
		}
	});

	dialog.show();
}

function show_advanced_filter_dialog(page, report_modules, state, scope="table") {
	const report = get_active_report(report_modules, state);
	const is_chart = scope === "chart";
	const filters = Object.assign(get_empty_report_filters(), is_chart ? state.chart_filters : state.table_filters);
	const filter_meta = get_report_filter_meta(report);
	const selector_fieldname = filter_meta.selector_fieldname || "party";

	const fields = [
		{ fieldtype: "Select", fieldname: "status", label: filter_meta.status_label, options: filter_meta.status_options.join("\n"), default: filters.status || "" },
		{ fieldtype: "Select", fieldname: "type", label: filter_meta.type_label, options: filter_meta.type_options.join("\n"), default: filters.type || "" },
		{ fieldtype: filter_meta.party_fieldtype || "Data", fieldname: selector_fieldname, label: filter_meta.party_label, options: filter_meta.party_options || "", default: filters[selector_fieldname] || filters.party || "" },
		{ fieldtype: "Currency", fieldname: "min_amount", label: filter_meta.min_label, default: filters.min_amount || "" },
		{ fieldtype: "Currency", fieldname: "max_amount", label: filter_meta.max_label, default: filters.max_amount || "" }
	];

	const dialog = new frappe.ui.Dialog({
		title: is_chart ? "Chart Advanced Filters" : "Table Advanced Filters",
		fields,
		secondary_action_label: "Clear",
		secondary_action() {
			if (is_chart) {
				state.chart_filters = get_empty_report_filters();
				dialog.hide();
				update_report_filter_state_ui(page, state);
				if (!state.analytics_collapsed) load_chart_report(page, report_modules, state);
				return;
			}

			state.table_filters = get_empty_report_filters();
			state.page = 1;
			dialog.hide();
			update_report_filter_state_ui(page, state);
			load_table_report(page, report_modules, state);
		},
		primary_action_label: "Apply",
		primary_action(values) {
			const next_filters = {
				status: values.status || "",
				type: values.type || "",
				party: selector_fieldname === "party" ? (values.party || "").trim() : "",
				item: selector_fieldname === "item" ? (values.item || "").trim() : "",
				min_amount: values.min_amount || "",
				max_amount: values.max_amount || ""
			};

			if (is_chart) {
				state.chart_filters = next_filters;
				dialog.hide();
				update_report_filter_state_ui(page, state);
				if (!state.analytics_collapsed) load_chart_report(page, report_modules, state);
				return;
			}

			state.table_filters = next_filters;
			state.page = 1;
			dialog.hide();

			if (report && report.key === "item_full_cycle") {
				state.search = "";
				$(page.body).find(".lx-report-search input").val("");
				$(page.body).find(".lx-report-search-clear").removeClass("visible");
				hide_item_intelligence_search_picker(page);
			}

			update_report_filter_state_ui(page, state);
			load_table_report(page, report_modules, state);
		}
	});

	dialog.show();
}

function get_report_filter_meta(report) {
	const key = report && report.key;
	const base = {
		status_label: "Status",
		status_options: ["", "Submitted", "Draft", "Cancelled"],
		type_label: "Type / Payment",
		type_options: ["", "Cash", "Card", "Bank", "JazzCash", "EasyPaisa", "Credit"],
		party_label: "Party",
		min_label: "Min Amount",
		max_label: "Max Amount"
	};

	if (key === "inventory") {
		return Object.assign({}, base, {
			status_label: "Stock Status",
			status_options: ["", "In Stock", "Low Stock", "Out of Stock"],
			type_label: "Active State",
			type_options: ["", "Active", "Inactive"],
			party_label: "Category",
			min_label: "Min Inventory Value",
			max_label: "Max Inventory Value"
		});
	}

	if (key === "stock") {
		return Object.assign({}, base, {
			type_label: "Movement Type",
			type_options: ["", "IN", "OUT", "ADJUSTMENT"],
			party_label: "Reference / Item"
		});
	}

	if (key === "item_full_cycle") {
		return Object.assign({}, base, {
			status_label: "Cycle Status",
			status_options: ["", "Purchase", "Sale", "Partial Return", "Returned", "Return", "Cancel"],
			type_label: "View Mode",
			type_options: ["Strict Inventory", "Billing Only"],
			party_label: "Select Item",
			selector_fieldname: "item",
			party_fieldtype: "Link",
			party_options: "Ledgix Item",
			min_label: "Min Profit",
			max_label: "Max Profit"
		});
	}

	return base;
}


function show_report_preview_modal(report, row) {
	const dialog = new frappe.ui.Dialog({
		title: `${report.label} Preview`,
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "preview_html" }],
		primary_action_label: "Print",
		primary_action() {
			frappe.show_alert({ message: __("Print template will be connected next."), indicator: "blue" });
		}
	});

	dialog.fields_dict.preview_html.$wrapper.html(`
		<div class="lx-report-preview-modal">
			<div class="lx-preview-top">
				<div>
					<div class="lx-preview-label">${frappe.utils.escape_html(report.label)} Record</div>
					<h3>${frappe.utils.escape_html(row.invoice || row.purchase || row.return || row.movement || row.reference || row.name || report.title)}</h3>
					<p>${frappe.utils.escape_html(row.customer || row.supplier || row.item || row.date || "Selected report record")}</p>
				</div>
				${render_status_badge(row.status || "Ready")}
			</div>

			<div class="lx-preview-summary-grid">
				${report.columns.filter((col) => !col.is_action).slice(0, 4).map((column) => `
					<div class="lx-preview-summary-card">
						<span>${frappe.utils.escape_html(column.label)}</span>
						<strong>${format_report_value(row[column.key], column.type)}</strong>
					</div>
				`).join("")}
			</div>

			<div class="lx-preview-section">
				<div class="lx-preview-section-title">Details</div>
				<div class="lx-preview-detail-grid">
					${Object.keys(row).map((key) => `
						<div class="lx-preview-detail-row">
							<span>${frappe.utils.escape_html(to_title_case(key))}</span>
							<strong>${frappe.utils.escape_html(row[key] == null ? "-" : String(row[key]))}</strong>
						</div>
					`).join("")}
				</div>
			</div>
		</div>
	`);

	dialog.show();
}


function open_report_party_picker(page, report_modules, state) {
	const report = get_active_report(report_modules, state);
	const is_supplier = report.key === "suppliers";

	const dialog = new frappe.ui.Dialog({
		title: is_supplier ? "Select Supplier" : "Select Customer",
		size: "large",
		fields: [
			{ fieldtype: "Data", fieldname: "search", label: "Search", reqd: false },
			{ fieldtype: "HTML", fieldname: "results" }
		]
	});

	dialog.show();
	const $results = dialog.fields_dict.results.$wrapper;

	function load_parties(search_text="") {
		$results.html(`
			<div class="lx-party-picker-loading">
				<div></div>
				<span>Loading parties...</span>
			</div>
		`);

		frappe.call({
			method: "ledgix_saas.api.api.search_report_parties",
			args: {
				party_type: is_supplier ? "supplier" : "customer",
				search: search_text
			},
			callback(r) {
				const rows = r.message || [];

				if (!rows.length) {
					$results.html(`<div class="lx-party-picker-empty">No matching ${is_supplier ? "suppliers" : "customers"} found</div>`);
					return;
				}

				$results.html(`
					<div class="lx-party-picker-list">
						${rows.map(row => `
							<button type="button" class="lx-party-picker-item" data-party="${frappe.utils.escape_html(row.label)}">
								<i class="fa fa-user-circle-o"></i>
								<span>${frappe.utils.escape_html(row.label)}</span>
							</button>
						`).join("")}
					</div>
				`);
			}
		});
	}

	load_parties();
	dialog.fields_dict.search.$input.on("input", frappe.utils.debounce(function() {
		load_parties($(this).val().trim());
	}, 300));

	$results.on("click", ".lx-party-picker-item", function() {
		const party = $(this).data("party");
		state.table_filters.party = party;
		state.page = 1;
		update_report_filter_state_ui(page, state);
		dialog.hide();
		load_table_report(page, report_modules, state);
	});

}



function open_report_item_picker(page, report_modules, state) {
	const selected_item = get_item_filter_value(state.table_filters);

	const dialog = new frappe.ui.Dialog({
		title: "Select Item",
		size: "large",
		fields: [
			{
				fieldtype: "Link",
				fieldname: "item",
				label: "Item",
				options: "Ledgix Item",
				default: selected_item || "",
				reqd: true,
				description: "Choose the exact Ledgix Item. After applying, the table search will filter lifecycle rows."
			}
		],
		secondary_action_label: "Clear Item",
		secondary_action() {
			clear_item_intelligence_item(page, report_modules, state);
			dialog.hide();
		},
		primary_action_label: "Load Lifecycle",
		primary_action(values) {
			const item = String(values.item || "").trim();
			if (!item) return;

			dialog.hide();
			select_item_intelligence_item(page, report_modules, state, item);
		}
	});

	dialog.show();
}


// ============================================================
// ITEM INTELLIGENCE LINKED SELECTION
// ============================================================

function ensure_item_intelligence_search_picker(page) {
	const $search = $(page.body).find(".lx-report-search").first();
	if (!$search.length || $search.find(".lx-item-intel-search-picker").length) return;

	$search.css("position", "relative");
	$search.append(`<div class="lx-item-intel-search-picker" style="display:none;"></div>`);
}

function hide_item_intelligence_search_picker(page) {
	$(page.body).find(".lx-item-intel-search-picker").hide().empty();
}

function update_item_intelligence_selection_ui(page, state) {
	const item = get_item_filter_value(state.table_filters);
	const $body = $(page.body);
	const $btn = $body.find(".lx-report-table-party-btn[data-action='select-item']");

	if (!$btn.length) return;

	$btn.toggleClass("has-item", !!item)
		.attr("title", item ? `Selected item: ${item}` : "Select Item");

	$btn.find("span").text(item ? shorten_ledgix_label(item, 24) : "Select Item");
}

function shorten_ledgix_label(value, max_length) {
	const text = String(value || "").trim();
	const limit = cint(max_length || 24);
	if (!text || text.length <= limit) return text;
	return `${text.slice(0, Math.max(1, limit - 1))}…`;
}

function select_item_intelligence_item(page, report_modules, state, item) {
	const clean_item = String(item || "").trim();
	if (!clean_item) return;

	state.table_filters.item = clean_item;
	state.table_filters.party = "";
	state.chart_filters.item = clean_item;
	state.chart_filters.party = "";
	state.search = "";
	state.page = 1;

	const $body = $(page.body);
	$body.find(".lx-report-search input").val("").attr("placeholder", "Search lot, purchase, sale, return, supplier, or customer...");
	$body.find(".lx-report-search-clear").removeClass("visible");
	hide_item_intelligence_search_picker(page);
	update_report_filter_state_ui(page, state);
	update_item_intelligence_selection_ui(page, state);
	load_table_report(page, report_modules, state);
}

function clear_item_intelligence_item(page, report_modules, state) {
	state.table_filters.item = "";
	state.table_filters.party = "";
	state.chart_filters.item = "";
	state.chart_filters.party = "";
	state.search = "";
	state.page = 1;

	const report = get_active_report(report_modules, state);
	const $body = $(page.body);
	$body.find(".lx-report-search input").val("").attr("placeholder", report.search_placeholder || "Search report...");
	$body.find(".lx-report-search-clear").removeClass("visible");
	hide_item_intelligence_search_picker(page);
	update_report_filter_state_ui(page, state);
	update_item_intelligence_selection_ui(page, state);
	load_table_report(page, report_modules, state);
}

function load_item_intelligence_search_picker(page, report_modules, state, search_text) {
	ensure_item_intelligence_search_picker(page);

	const $picker = $(page.body).find(".lx-item-intel-search-picker").first();
	const query = String(search_text || "").trim();
	const request_id = ++state.item_search_request_id;

	if (!query) {
		$picker.html(`
			<div class="lx-item-intel-search-help">
				<strong>Search item first</strong>
				<span>Type item name, SKU, or barcode, then select the exact Ledgix Item.</span>
			</div>
		`).show();
		return;
	}

	$picker.html(`<div class="lx-item-intel-search-loading">Searching items...</div>`).show();

	const render_results = (rows) => {
		if (request_id !== state.item_search_request_id) return;

		const clean_rows = (rows || [])
			.map((row) => {
				if (typeof row === "string") return { value: row, label: row, description: "" };
				return {
					value: row.value || row.name || row.label || row.item || "",
					label: row.label || row.value || row.name || row.item || "",
					description: row.description || row.item_name || row.sku || row.barcode || ""
				};
			})
			.filter((row) => row.value)
			.slice(0, 8);

		if (!clean_rows.length) {
			$picker.html(`
				<div class="lx-item-intel-search-empty">
					<strong>No item found</strong>
					<span>Try exact item code, SKU, barcode, or item name.</span>
				</div>
			`).show();
			return;
		}

		$picker.html(`
			<div class="lx-item-intel-search-list">
				${clean_rows.map((row) => `
					<button type="button" class="lx-item-intel-search-option" data-item="${frappe.utils.escape_html(row.value)}">
						<i class="fa fa-cube"></i>
						<span>${frappe.utils.escape_html(row.label)}</span>
						${row.description ? `<small>${frappe.utils.escape_html(row.description)}</small>` : ""}
					</button>
				`).join("")}
			</div>
		`).show();
	};

	if (frappe.db && typeof frappe.db.get_link_options === "function") {
		frappe.db.get_link_options("Ledgix Item", query).then(render_results).catch(() => render_results([]));
		return;
	}

	frappe.call({
		method: "frappe.desk.search.search_link",
		args: {
			doctype: "Ledgix Item",
			txt: query,
			page_length: 8
		},
		callback(r) {
			render_results(r.message || []);
		},
		error() {
			render_results([]);
		}
	});
}


// ============================================================
// THEME
// ============================================================

function open_ledgix_report_theme_dialog(page) {
	const current =
		window.LedgixTheme?.get?.().primary_accent_color ||
		getComputedStyle(document.documentElement).getPropertyValue("--lx-accent").trim() ||
		"#0f766e";

	const dialog = new frappe.ui.Dialog({
		title: "Customize Reports Theme",
		fields: [
			{
				fieldtype: "Color",
				fieldname: "accent_color",
				label: "Primary Accent Color",
				default: normalize_report_hex(current) || "#0f766e",
				reqd: 1
			}
		],
		primary_action_label: "Save Theme",
		primary_action(values) {
			const color = normalize_report_hex(values.accent_color);

				if (!color) {
					frappe.msgprint("Please select a valid color");
					return;
				}

				if (!window.LedgixTheme?.save) {
					frappe.msgprint("Navigator theme service is not available. Please use Ledgix POS Theme Settings.");
					return;
				}

				dialog.disable_primary_action();
				window.LedgixTheme.save({ primary_accent_color: color })
					.then((theme) => {
						apply_ledgix_report_theme_settings(page, theme || { primary_accent_color: color });
						frappe.show_alert({ message: "Reports theme updated", indicator: "green" });
						dialog.hide();
					})
					.catch(() => {
						frappe.show_alert({ message: "Unable to save reports theme", indicator: "red" });
					})
					.finally(() => dialog.enable_primary_action());
			}
		});

	dialog.show();
}

function apply_ledgix_report_theme(page) {
	const bridge_theme = window.LedgixTheme?.get?.();
	if (bridge_theme && bridge_theme.primary_accent_color) {
		apply_ledgix_report_theme_settings(page, bridge_theme);
		$(page.body).find(".lx-reports-page").addClass("lx-theme-ready");
		return;
	}

	frappe.call({
		method: "ledgix_saas.api.api.get_pos_theme_settings",
		callback(r) {
			const settings = r.message || {};
			const primary = normalize_report_hex(settings.primary_accent_color);
			if (!settings.enable_custom_accent || !primary) {
				clear_report_theme_vars(page);
				$(page.body).find(".lx-reports-page").addClass("lx-theme-ready");
				return;
			}
			const generated = generate_report_accent_shades(primary);

			set_report_theme_vars(page, primary, {
				hover: settings.accent_hover || generated.hover,
				soft: settings.accent_soft || generated.soft,
				soft_2: settings.accent_soft_2 || generated.soft_2,
				border: settings.accent_border || generated.border
			});

			$(page.body).find(".lx-reports-page").addClass("lx-theme-ready");
		},
		error() {
			clear_report_theme_vars(page);
			$(page.body).find(".lx-reports-page").addClass("lx-theme-ready");
		}
	});
}

function apply_ledgix_report_theme_settings(page, settings) {
	const primary = normalize_report_hex(settings && settings.primary_accent_color);
	if (!settings || !settings.enable_custom_accent || !primary) {
		clear_report_theme_vars(page);
		return;
	}
	const generated = generate_report_accent_shades(primary);
	set_report_theme_vars(page, primary, {
		hover: settings.accent_hover || generated.hover,
		soft: settings.accent_soft || generated.soft,
		soft_2: settings.accent_soft_2 || generated.soft_2,
		border: settings.accent_border || generated.border,
		ring: settings.accent_ring || report_rgba(primary, 0.18),
		rgb: settings.accent_rgb
	});
}

function bind_ledgix_report_theme_updates(page, state) {
	const handler = function(e) {
		const theme =
			(e && e.detail && e.detail.theme) ||
			window.LedgixTheme?.get?.() ||
			window.ledgix_theme ||
			{};

		state.theme_settings = theme;

		apply_ledgix_report_theme_settings(page, theme);
	};

	if (window.__ledgix_reports_theme_handler) {
		window.removeEventListener("ledgix:theme-updated", window.__ledgix_reports_theme_handler);
		document.removeEventListener("ledgix:theme-updated", window.__ledgix_reports_theme_handler);
	}

	window.__ledgix_reports_theme_handler = handler;

	window.addEventListener("ledgix:theme-updated", handler);
	document.addEventListener("ledgix:theme-updated", handler);

	handler({
		detail: {
			theme:
				window.LedgixTheme?.get?.() ||
				window.ledgix_theme ||
				state.theme_settings ||
				{},
		},
	});
}


function set_report_theme_vars(page, primary, shades) {
	const clean_primary = normalize_report_hex(primary);
	if (!clean_primary) {
		clear_report_theme_vars(page);
		return;
	}
	const clean_shades = shades || generate_report_accent_shades(clean_primary);
	const local_roots = page && page.body ? Array.from($(page.body).find(".lx-reports-page")) : [];
	const all_roots = Array.from(document.querySelectorAll(".lx-reports-page"));
	const targets = [...local_roots, ...all_roots, document.documentElement, document.body]
		.filter(Boolean)
		.filter((target, index, list) => list.indexOf(target) === index);

	targets.forEach((target) => {
		target.style.setProperty("--lx-accent", clean_primary);
		target.style.setProperty("--accent", clean_primary);
		target.style.setProperty("--ledgix-accent", clean_primary);
		target.style.setProperty("--lx-accent-hover", clean_shades.hover);
		target.style.setProperty("--accent-hover", clean_shades.hover);
		target.style.setProperty("--lx-accent-soft", clean_shades.soft);
		target.style.setProperty("--accent-soft", clean_shades.soft);
		target.style.setProperty("--lx-accent-soft-2", clean_shades.soft_2);
		target.style.setProperty("--accent-soft-2", clean_shades.soft_2);
		target.style.setProperty("--lx-accent-border", clean_shades.border);
		target.style.setProperty("--accent-border", clean_shades.border);
		target.style.setProperty("--lx-accent-ring", clean_shades.ring || report_rgba(clean_primary, 0.18));
		target.style.setProperty("--accent-ring", clean_shades.ring || report_rgba(clean_primary, 0.18));
		target.style.setProperty("--lx-accent-rgb", clean_shades.rgb || report_rgb_string(clean_primary));
		target.style.setProperty("--ledgix-accent-rgb", clean_shades.rgb || report_rgb_string(clean_primary));
		target.style.setProperty("--accent-rgb", clean_shades.rgb || report_rgb_string(clean_primary));
		target.style.setProperty("--lx-accent-surface", report_rgba(clean_primary, 0.07));
		target.style.setProperty("--lx-accent-surface-strong", report_rgba(clean_primary, 0.12));
		target.style.setProperty("--lx-accent-shadow", report_rgba(clean_primary, 0.18));
		target.setAttribute("data-ledgix-theme", "enabled");
	});
}

function generate_report_accent_shades(hex) {
	const primary = normalize_report_hex(hex);
	if (!primary) return {};

	return {
		hover: darken_report_hex(primary, 18),
		soft: report_rgba(primary, 0.10),
		soft_2: report_rgba(primary, 0.16),
		border: report_rgba(primary, 0.28)
	};
}

function clear_report_theme_vars(page) {
	const local_roots = page && page.body ? Array.from($(page.body).find(".lx-reports-page")) : [];
	const all_roots = Array.from(document.querySelectorAll(".lx-reports-page"));
	const targets = [...local_roots, ...all_roots, document.documentElement, document.body]
		.filter(Boolean)
		.filter((target, index, list) => list.indexOf(target) === index);

	targets.forEach((target) => {
		LEDGIX_REPORT_THEME_VARS.forEach((name) => target.style.removeProperty(name));
		target.setAttribute("data-ledgix-theme", "disabled");
	});
}

// ============================================================
// FORMATTERS / HELPERS
// ============================================================

function format_report_value(value, type) {
	if (value === undefined || value === null || value === "") {
		if (type === "currency") return "PKR 0.00";
		if (type === "percent") return "0%";
		if (type === "number") return "0";
		return "-";
	}

	if (type === "currency") {
		return format_currency_safe(value);
	}

	if (type === "percent") {
		return `${flt(value).toFixed(2)}%`;
	}

	if (type === "number") {
		return format_number_safe(value);
	}

	return frappe.utils.escape_html(String(value));
}



function format_currency_safe(value) {
	const amount = flt(value || 0);
	return `PKR ${amount.toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2
	})}`;
}

function format_number_safe(value) {
	return flt(value || 0).toLocaleString(undefined, {
		maximumFractionDigits: 2
	});
}

function render_status_badge(status) {
	const clean = status || "-";
	const cls = String(clean).toLowerCase().replace(/\s+/g, "-");

	return `<span class="lx-status-badge lx-status-${frappe.utils.escape_html(cls)}">${frappe.utils.escape_html(clean)}</span>`;
}

function render_soft_badge(value) {
        const clean = String(value || "-").trim();
        const cls = clean.toLowerCase().replace(/\s+/g, "-");

        return `<span class="lx-soft-badge lx-status-${frappe.utils.escape_html(cls)}">${frappe.utils.escape_html(clean)}</span>`;
}

function render_impact_badge(value) {
	const clean = String(value || "-").trim().toUpperCase();
	const cls = clean.toLowerCase().replace(/\s+/g, "-");

	return `<span class="lx-impact-badge lx-impact-${frappe.utils.escape_html(cls)}">${frappe.utils.escape_html(clean)}</span>`;
}

function render_step_badge(value) {
	const clean = String(value || "-").trim();
	return `<span class="lx-step-badge">${frappe.utils.escape_html(clean)}</span>`;
}

function render_stock_flow_value(row) {
	const explicit = row && row.stock_flow;
	const before = row && (row.stock_before ?? row.before_stock);
	const after = row && (row.stock_after ?? row.running_stock ?? row.after_stock);
	const flow = explicit || ((before !== undefined && before !== null && after !== undefined && after !== null) ? `${format_number_safe(before)} → ${format_number_safe(after)}` : "-");

	return `<span class="lx-stock-flow-value">${frappe.utils.escape_html(String(flow))}</span>`;
}

function render_item_cycle_guide(page, report, state) {
	const $slot = $(page.body).find(".lx-item-cycle-guide-slot");
	if (!report || report.key !== "item_full_cycle") {
		$slot.empty().hide();
		return;
	}

	const open = !!state.item_cycle_guide_open;
	$slot.show().html(`
		<div class="lx-item-cycle-guide ${open ? "open" : "collapsed"}">
			<button class="lx-item-cycle-guide-bar" type="button" data-action="toggle-item-cycle-guide" aria-expanded="${open ? "true" : "false"}">
				<div class="lx-item-cycle-guide-title">
					<span class="lx-guide-icon"><i class="fa fa-map-signs"></i></span>
					<div>
						<strong>How Item Intelligence works</strong>
						<span>Follow one selected item through purchases, sales, returns, and remaining stock.</span>
					</div>
				</div>
				<div class="lx-item-cycle-guide-status">
					<span>Lifecycle Intelligence</span>
					<i class="fa ${open ? "fa-angle-up" : "fa-angle-down"}"></i>
				</div>
			</button>

			${open ? `
				<div class="lx-item-cycle-guide-body">
					<div class="lx-guide-card lx-guide-card-main">
						<span class="lx-guide-card-label">Purpose</span>
						<strong>Single-item lifecycle intelligence</strong>
						<p>Review lot movement, quantities, and margin for one selected item without mixing it with broader inventory reports.</p>
					</div>

					<div class="lx-guide-card">
						<span class="lx-guide-card-label">Lifecycle Flow</span>
						<strong>Purchased → Sold → Returned → Current</strong>
						<p>The flow summarizes the selected item's real movement quantities from backend report data.</p>
					</div>

					<div class="lx-guide-card">
						<span class="lx-guide-card-label">Margin</span>
						<strong>Profit and loss stay visible</strong>
						<p>Profit, loss, and selling amount are shown separately so lifecycle review does not hide financial impact.</p>
					</div>

					<div class="lx-guide-card">
						<span class="lx-guide-card-label">Review</span>
						<ol>
							<li>Select one item from filters.</li>
							<li>Compare lifecycle flow with table records.</li>
							<li>Investigate unusual returns, losses, or remaining quantities.</li>
						</ol>
					</div>
				</div>
			` : ""}
		</div>
	`);
}
function get_date_range_label(state, scope="chart") {
	const preset = scope === "table" ? state.table_date_preset : state.chart_date_preset;
	const from_date = scope === "table" ? state.table_from_date : state.chart_from_date;
	const to_date = scope === "table" ? state.table_to_date : state.chart_to_date;

	if (preset !== "custom") {
		return date_preset_to_label(preset);
	}

	return `${from_date || "-"} → ${to_date || "-"}`;
}

function date_preset_to_label(preset) {
	const map = {
		today: "Today",
		this_week: "This Week",
		this_month: "This Month",
		last_30_days: "Last 30 Days",
		all_to_today: "All to Today",
		custom: "Custom"
	};

	return map[preset] || preset || "This Month";
}

function label_to_date_preset(label) {
	const value = String(label || "").toLowerCase().replace(/\s+/g, "_");
	if (value === "last_30_days") return "last_30_days";
	if (value === "this_week") return "this_week";
	if (value === "this_month") return "this_month";
	if (value === "today") return "today";
	if (value === "all_to_today") return "all_to_today";
	return "custom";
}

function get_range_from_preset(label, from_date, to_date) {
	const preset = label_to_date_preset(label);
	const today = frappe.datetime.get_today();

	if (preset === "today") {
		return { preset, from_date: today, to_date: today };
	}

	if (preset === "this_week") {
		return {
			preset,
			from_date: frappe.datetime.week_start ? frappe.datetime.week_start() : frappe.datetime.add_days(today, -6),
			to_date: today
		};
	}

	if (preset === "this_month") {
		return {
			preset,
			from_date: frappe.datetime.month_start(),
			to_date: frappe.datetime.month_end()
		};
	}

	if (preset === "last_30_days") {
		return {
			preset,
			from_date: frappe.datetime.add_days(today, -29),
			to_date: today
		};
	}

	if (preset === "all_to_today") {
		return {
			preset,
			from_date: "",
			to_date: today
		};
	}

	return {
		preset: "custom",
		from_date: from_date || today,
		to_date: to_date || today
	};
}

function ledgix_debounce(fn, delay) {
	let timer = null;

	return function(...args) {
		clearTimeout(timer);
		timer = setTimeout(() => fn.apply(this, args), delay);
	};
}

function to_title_case(value) {
	return String(value || "")
		.replace(/_/g, " ")
		.replace(/\w\S*/g, (txt) => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase());
}

function darken_report_hex(hex, percent) {
	const rgb = report_hex_to_rgb(hex);
	if (!rgb) return hex;

	const factor = (100 - percent) / 100;

	return report_rgb_to_hex({
		r: Math.round(rgb.r * factor),
		g: Math.round(rgb.g * factor),
		b: Math.round(rgb.b * factor)
	});
}

function mix_report_hex(hex_a, hex_b, percent_b) {
	const a = report_hex_to_rgb(hex_a);
	const b = report_hex_to_rgb(hex_b);

	if (!a || !b) return hex_a;

	const p = percent_b / 100;

	return report_rgb_to_hex({
		r: Math.round(a.r * (1 - p) + b.r * p),
		g: Math.round(a.g * (1 - p) + b.g * p),
		b: Math.round(a.b * (1 - p) + b.b * p)
	});
}

function report_hex_to_rgb(hex) {
	if (!hex) return null;

	hex = hex.replace("#", "").trim();

	if (hex.length === 3) {
		hex = hex.split("").map((c) => c + c).join("");
	}

	if (hex.length !== 6) return null;

	return {
		r: parseInt(hex.substring(0, 2), 16),
		g: parseInt(hex.substring(2, 4), 16),
		b: parseInt(hex.substring(4, 6), 16)
	};
}

function report_rgb_to_hex({ r, g, b }) {
	return "#" + [r, g, b]
		.map((value) => Math.max(0, Math.min(255, value)).toString(16).padStart(2, "0"))
		.join("");
}

function normalize_report_hex(hex) {
	const rgb = report_hex_to_rgb(hex);
	return rgb ? report_rgb_to_hex(rgb) : null;
}

function report_rgba(hex, alpha) {
	const rgb = report_hex_to_rgb(hex);
	if (!rgb) return "";
	return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
}

function report_rgb_string(hex) {
	const rgb = report_hex_to_rgb(hex);
	if (!rgb) return "";
	return `${rgb.r}, ${rgb.g}, ${rgb.b}`;
}



// ============================================================
// REPORT PRINT / EXPORT ENGINE
// ============================================================

function print_active_ledgix_report(page, report_modules, state) {
	const report = get_active_report(report_modules, state);
	print_ledgix_report_rows(report, state.rows || [], state.summary || {}, report.title || report.label || "Ledgix Report");
}

function print_single_ledgix_report_row(page, report_modules, state, row_index) {
	const report = get_active_report(report_modules, state);
	const row = (state.rows || [])[row_index];

	if (!row) {
		frappe.show_alert({ message: "Row not found", indicator: "orange" });
		return;
	}

	print_ledgix_report_rows(report, [row], state.summary || {}, `${report.label} Record`);
}

function print_selected_ledgix_report_rows(page, report_modules, state) {
	const report = get_active_report(report_modules, state);
	const rows = get_selected_report_rows(state);

	if (!rows.length) {
		frappe.show_alert({ message: "Select at least one row to print", indicator: "orange" });
		return;
	}

	print_ledgix_report_rows(report, rows, state.summary || {}, `${report.label} Selected Rows`);
}

function print_ledgix_report_rows(report, rows, summary, title) {
	if (!report || !rows || !rows.length) {
		frappe.show_alert({ message: "No rows available to print", indicator: "orange" });
		return;
	}

	const html = build_ledgix_report_print_html(report, rows, summary, title);
	print_ledgix_report_html(html);
}

function build_ledgix_report_print_html(report, rows, summary, title) {
	const columns = (report.columns || []).filter(col => !col.is_action);
	const safe_title = frappe.utils.escape_html(title || "Ledgix Report");

	return `
		<html>
		<head>
			<title>${safe_title}</title>
			<style>
				@page { size: A4; margin: 18mm; }
				body { font-family: Inter, Arial, sans-serif; color: #0f172a; font-size: 12px; background: #ffffff; }
				.lx-print-title { font-size: 24px; font-weight: 800; margin-bottom: 4px; }
				.lx-print-sub { color: #64748b; font-size: 12px; }
				.lx-print-pill { border: 1px solid #e2e8f0; border-radius: 999px; padding: 7px 11px; color: #334155; font-weight: 700; white-space: nowrap; height: fit-content; }
				.lx-summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 18px; }
				.lx-summary-card { border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; background: #f8fafc; }
				.lx-summary-card span { display: block; font-size: 11px; color: #64748b; margin-bottom: 4px; }
				.lx-summary-card strong { font-size: 14px; }
				table { width: 100%; border-collapse: collapse; }
				thead th { background: #f8fafc; border: 1px solid #e2e8f0; padding: 9px; text-align: left; font-size: 11px; color: #475569; }
				tbody td { border: 1px solid #e2e8f0; padding: 8px; font-size: 11px; }
				.lx-right { text-align: right; }
				.lx-print-footer { margin-top: 14px; font-size: 11px; color: #94a3b8; text-align: right; }
			</style>
		</head>
		<body>
				<div>
					<div class="lx-print-title">${safe_title}</div>
					<div class="lx-print-sub">Generated: ${frappe.datetime.now_datetime()}</div>
				</div>
				<div class="lx-print-pill">${rows.length} row${rows.length === 1 ? "" : "s"}</div>
			</div>

			<div class="lx-summary-grid">
				${(report.summary || []).map(item => `
					<div class="lx-summary-card">
						<span>${frappe.utils.escape_html(item.label)}</span>
						<strong>${format_report_value(summary[item.key], item.type)}</strong>
					</div>
				`).join("")}
			</div>

			<table>
				<thead>
					<tr>
						${columns.map(col => `<th class="${col.align === "right" ? "lx-right" : ""}">${frappe.utils.escape_html(col.label)}</th>`).join("")}
					</tr>
				</thead>
				<tbody>
					${rows.map(row => `
						<tr>
							${columns.map(col => `<td class="${col.align === "right" ? "lx-right" : ""}">${format_report_value(row[col.key], col.type)}</td>`).join("")}
						</tr>
					`).join("")}
				</tbody>
			</table>

			<div class="lx-print-footer">Reports & Analytics</div>
		</body>
		</html>
	`;
}

function print_ledgix_report_html(html) {
	const old_frame = document.getElementById("lx-report-print-frame");
	if (old_frame) old_frame.remove();

	const iframe = document.createElement("iframe");
	iframe.id = "lx-report-print-frame";
	iframe.style.position = "fixed";
	iframe.style.right = "0";
	iframe.style.bottom = "0";
	iframe.style.width = "1px";
	iframe.style.height = "1px";
	iframe.style.border = "0";
	iframe.style.opacity = "0";
	document.body.appendChild(iframe);

	const frame_doc = iframe.contentWindow.document;
	frame_doc.open();
	frame_doc.write(html);
	frame_doc.close();

	setTimeout(() => {
		iframe.contentWindow.focus();
		iframe.contentWindow.print();
	}, 350);
}

function export_active_ledgix_report_csv(page, report_modules, state) {
	const report = get_active_report(report_modules, state);
	export_ledgix_report_rows_csv(report, state.rows || [], `${report.key}-report.csv`);
}

function export_single_ledgix_report_row_csv(page, report_modules, state, row_index) {
	const report = get_active_report(report_modules, state);
	const row = (state.rows || [])[row_index];

	if (!row) {
		frappe.show_alert({ message: "Row not found", indicator: "orange" });
		return;
	}

	export_ledgix_report_rows_csv(report, [row], `${report.key}-row.csv`);
}

function export_selected_ledgix_report_rows_csv(page, report_modules, state) {
	const report = get_active_report(report_modules, state);
	const rows = get_selected_report_rows(state);

	if (!rows.length) {
		frappe.show_alert({ message: "Select at least one row to export", indicator: "orange" });
		return;
	}

	export_ledgix_report_rows_csv(report, rows, `${report.key}-selected-rows.csv`);
}

function export_ledgix_report_rows_csv(report, rows, filename) {
	if (!report || !rows || !rows.length) {
		frappe.show_alert({ message: "No rows available to export", indicator: "orange" });
		return;
	}

	const columns = (report.columns || []).filter(col => !col.is_action);
	let csv = columns.map(col => csv_escape(col.label)).join(",") + "\n";

	rows.forEach(row => {
		csv += columns.map(col => csv_escape(row[col.key] == null ? "" : row[col.key])).join(",") + "\n";
	});

	const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
	const link = document.createElement("a");
	const url = URL.createObjectURL(blob);

	link.href = url;
	link.download = filename || `${report.key}-report.csv`;
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);
	URL.revokeObjectURL(url);

	frappe.show_alert({ message: "CSV export downloaded", indicator: "green" });
}

function csv_escape(value) {
	return `"${String(value).replace(/"/g, '""')}"`;
}

function get_empty_report_filters() {
	return {
		status: "",
		type: "",
		party: "",
		item: "",
		min_amount: "",
		max_amount: ""
	};
}

function update_report_filter_state_ui(page, state) {
	const has_chart_filters = Object.values(state.chart_filters || {}).some(value => value !== null && value !== undefined && String(value).trim() !== "");
	const has_table_filters = Object.values(state.table_filters || {}).some(value => value !== null && value !== undefined && String(value).trim() !== "");
	const has_table_controls = has_table_filters || !!state.search || !!state.sort_by || state.table_date_preset !== "this_month";

	$(page.body).find(".lx-report-filter-box[data-action='advanced-filters'][data-scope='chart']").toggleClass("has-filters", has_chart_filters);
	$(page.body).find(".lx-report-filter-box[data-action='advanced-filters'][data-scope='table']").toggleClass("has-filters", has_table_filters);
	$(page.body).find(".lx-report-clear-table-btn").toggleClass("has-filters", has_table_controls);
}


// ============================================================
// LEDGIX REPORTS UI POLISH HELPERS
// ============================================================

frappe.after_ajax(() => {
    setTimeout(() => {
        try {
            $(".lx-header-print, .lx-top-print-btn, .lx-main-print-btn").remove();

            const exportButtons = $(".lx-export-btn, .lx-print-btn");

            const tableHeaderControls =
                $(".lx-table-controls, .lx-report-controls").first();

            if (tableHeaderControls.length && exportButtons.length) {
                exportButtons.each(function () {
                    tableHeaderControls.append(this);
                });
            }

            exportButtons.addClass("lx-icon-btn");
        } catch (e) {
            console.log("Ledgix polish patch:", e);
        }
    }, 100);
});


function stabilize_report_chart_tooltip($chart_wrap) {
	const chart_el = $chart_wrap && $chart_wrap.get ? $chart_wrap.get(0) : null;
	if (!chart_el) return;

	function fix_tip() {
		const tip = chart_el.querySelector(".graph-svg-tip");
		if (!tip) return;

		const lines = (tip.innerText || "").split("\n").map(v => v.trim()).filter(Boolean);

		if (lines.length > 1) {
			const first_line = lines[0];
			const is_duplicate_title =
				/^\d{4}-\d{2}-\d{2}$/.test(first_line) ||
				/^\d{1,2}\s[A-Za-z]{3}$/.test(first_line) ||
				/^[A-Za-z]{3}$/.test(first_line);

			if (is_duplicate_title) {
				const candidates = Array.from(tip.children || []);
				const first = candidates.find(el => (el.innerText || "").trim() === first_line);
				if (first) first.remove();
			}
		}

		const chart_rect = chart_el.getBoundingClientRect();
		const tip_rect = tip.getBoundingClientRect();

		if (tip_rect.top < chart_rect.top + 10) {
			const current_top = parseFloat(tip.style.top || "0");
			if (!isNaN(current_top)) {
				tip.style.top = `${current_top + tip_rect.height + 32}px`;
			}
		}

		const adjusted_rect = tip.getBoundingClientRect();

		if (adjusted_rect.left < chart_rect.left + 10) {
			tip.style.left = "12px";
			tip.style.right = "auto";
			tip.style.transform = "translateX(0)";
		}

		if (adjusted_rect.right > chart_rect.right - 10) {
			tip.style.left = "auto";
			tip.style.right = "12px";
			tip.style.transform = "translateX(0)";
		}
	}

	const observer = new MutationObserver(() => {
		requestAnimationFrame(fix_tip);
	});

	observer.observe(chart_el, {
		childList: true,
		subtree: true,
		attributes: true,
		attributeFilter: ["style", "class"]
	});

	chart_el.addEventListener("mousemove", () => {
		requestAnimationFrame(fix_tip);
	});
}
