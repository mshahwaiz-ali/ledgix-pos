/* global frappe */

// ============================================================
// LEDGIX OPERATIONS CENTER V2
// ============================================================

frappe.pages["ledgix_operations"].on_page_load = function (wrapper) {
	frappe.ledgix_operations = new LedgixOperationsCenter(wrapper);
};

class LedgixOperationsCenter {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: "",
			single_column: true,
		});
		this.page.set_title("");

		const $page_container = $(wrapper).closest(".page-container");
		$page_container.addClass("ledgix-page-no-frappe-head");

		$page_container
			.find(".page-head, .page-head-content, .page-title, .title-area, .page-actions")
			.hide();

		this.active_module = this.get_initial_module();
		this.page_size = 10;
		this.meta_cache = {};
		this.option_cache = {};
		this.boot = {
			stock_control_mode: "Strict Inventory",
			theme_settings: null,
		};
		this.load_request_id = 0;
		this.method_paths = {
			pos_boot: "ledgix_saas.api.api.get_pos_boot_data",
		};
		this.state = this.get_default_state();
		this.modules = this.get_module_config();
		this.transaction_modules = ["purchases", "sales", "returns"];
		this.readonly_print_modules = ["stock"];

		this.make_page_actions();
		this.make_shell();
		this.bind_events();
		this.bootstrap();
	}

	is_ledgix_admin() {
		return !!(
			(frappe.session && frappe.session.user === "Administrator") ||
			(
				frappe.user &&
				frappe.user.has_role &&
				(frappe.user.has_role("System Manager") || frappe.user.has_role("Ledgix Admin"))
			)
		);
	}

	is_sales_read_only() {
		return !this.is_ledgix_admin();
	}

	can_cancel_transaction(module_key) {
		if (module_key === "sales" || module_key === "returns") {
			return this.is_ledgix_admin();
		}
		return true;
	}

	can_delete_transaction(module_key) {
		if (module_key === "sales") {
			return this.is_ledgix_admin();
		}
		return true;
	}

	get_initial_module() {
		const requested = this.get_url_module();
		const saved = localStorage.getItem("ledgix_operations_active_module");
		const allowed = ["products", "categories", "purchases", "sales", "returns", "stock", "shifts"];

		if (requested && allowed.includes(requested)) {
			localStorage.setItem("ledgix_operations_active_module", requested);
			return requested;
		}

		if (saved && allowed.includes(saved)) {
			return saved;
		}

		return "products";
	}


	// ============================================================
	// DEFAULT STATE
	// ============================================================

	get_default_state() {
		return {
			products: { page: 1, search: "", filters: { category: "", stock_status: "", sort_by: "Popular" }, rows: [], total: 0, loaded_total: 0, sort: { key: "", direction: "" }, selected_row: null },
			categories: { page: 1, search: "", filters: { is_active: "", tax_enabled: "" }, rows: [], total: 0, loaded_total: 0, sort: { key: "", direction: "" }, selected_row: null },
			purchases: { page: 1, search: "", filters: { supplier: "", status: "", from_date: "", to_date: "" }, rows: [], total: 0, loaded_total: 0, sort: { key: "", direction: "" }, selected_row: null },
			sales: { page: 1, search: "", filters: { cashier: "", payment_status: "", status: "", from_date: "", to_date: "" }, rows: [], total: 0, loaded_total: 0, sort: { key: "", direction: "" }, selected_row: null },
			returns: { page: 1, search: "", filters: { status: "", from_date: "", to_date: "" }, rows: [], total: 0, loaded_total: 0, sort: { key: "", direction: "" }, selected_row: null },
			stock: { page: 1, search: "", filters: { movement_type: "", movement_source: "", user: "", from_date: "", to_date: "" }, rows: [], total: 0, loaded_total: 0, sort: { key: "", direction: "" }, selected_row: null },
			shifts: { page: 1, search: "", filters: { status: "", cashier: "", from_date: "", to_date: "" }, rows: [], total: 0, loaded_total: 0, sort: { key: "", direction: "" }, selected_row: null },
		};
	}

	// ============================================================
	// MODULE CONFIG
	// ============================================================

	get_module_config() {
		return {
			products: {
				label: "Products",
				short_label: "Products",
				doctype: "Ledgix Item",
				search_fields: ["item_code", "item_name", "barcode", "sku"],
				order_by: "modified desc",
				fields: ["item_code", "item_name", "category", "tracking_type", "barcode", "sku", "selling_price", "cost_price", "current_stock", "stock_status", "active", "modified"],
				columns: [
					{ label: "", key: "selector", type: "selector" },
					{ label: "Item Code", key: "item_code", type: "strong" },
					{ label: "Item Name", key: "item_name" },
					{ label: "Category", key: "category", type: "badge" },
					{ label: "Tracking", key: "tracking_type", type: "badge" },
					{ label: "Barcode / SKU", key: "barcode_sku", formatter: (row) => this.join_values([row.barcode, row.sku]) },
					{ label: "Selling", key: "selling_price", type: "currency" },
					{ label: "Cost", key: "cost_price", type: "currency" },
					{ label: "Stock", key: "current_stock", type: "number" },
					{ label: "Status", key: "stock_status", type: "status" },
					{ label: "Actions", key: "actions", type: "actions" },
				],
			},
			categories: {
				label: "Categories",
				short_label: "Categories",
				doctype: "Ledgix Category",
				search_fields: ["category_name", "description", "name"],
				order_by: "category_name asc",
				fields: [
					"category_name",
					"description",
					"category_icon",
					"accent_color",
					"is_active",
					"tax_defaults_enabled",
					"default_tax_category",
					"default_taxable",
					"modified",
				],
				columns: [
					{ label: "", key: "selector", type: "selector" },
					{ label: "Category", key: "category_name", type: "strong" },
					{ label: "Description", key: "description" },
					{ label: "Items", key: "_item_count", type: "number" },
					{ label: "Tax Defaults", key: "tax_defaults_enabled", formatter: (row) => (cint(row.tax_defaults_enabled) ? "Enabled" : "Off") },
					{ label: "Tax Category", key: "default_tax_category", formatter: (row) => row.default_tax_category || "—" },
					{ label: "Active", key: "is_active", type: "status", formatter: (row) => (cint(row.is_active) ? "Active" : "Inactive") },
					{ label: "Actions", key: "actions", type: "actions" },
				],
			},
			purchases: {
				label: "Purchases",
				short_label: "Purchases",
				doctype: "Ledgix Purchase",
				child_doctype: "Ledgix Purchase Item",
				search_fields: ["name", "supplier"],
				order_by: "modified desc",
				fields: ["supplier", "purchase_date", "date", "posting_date", "total_qty", "total_quantity", "total_amount", "grand_total", "status", "docstatus", "modified"],
				columns: [
					{ label: "", key: "selector", type: "selector" },
					{ label: "Purchase ID", key: "name", type: "strong" },
					{ label: "Date", key: "purchase_date", formatter: (row) => this.first_value(row, ["purchase_date", "date", "posting_date", "modified"], true) },
					{ label: "Supplier", key: "supplier" },
					{ label: "Items", key: "_items_count", type: "number" },
					{ label: "Total Qty", key: "_total_qty", formatter: (row) => this.first_value(row, ["_total_qty", "total_qty", "total_quantity"]) },
					{ label: "Total", key: "_total_amount", formatter: (row) => this.format_currency(row._total_amount) },
					{ label: "Status", key: "status", type: "status", formatter: (row) => this.format_docstatus(row) },
					{ label: "Actions", key: "actions", type: "actions" },
				],
			},
			sales: {
				label: "Sales",
				short_label: "Sales",
				doctype: "Ledgix Sale",
				child_doctype: "Ledgix Sale Item",
				search_fields: ["name", "invoice_number", "customer"],
				order_by: "modified desc",
				fields: ["invoice_number", "customer", "sale_date", "total_amount", "total_profit", "paid_amount", "payment_status", "status", "docstatus", "pos_shift", "owner", "modified"],
				columns: [
					{ label: "", key: "selector", type: "selector" },
					{ label: "Invoice No", key: "invoice_number", type: "strong" },
					{ label: "Sale ID", key: "name" },
					{ label: "Date", key: "sale_date", type: "date" },
					{ label: "Customer", key: "customer" },
					{ label: "Cashier", key: "owner" },
					{ label: "Items", key: "_items_count", type: "number" },
					{ label: "Payment", key: "payment_status", type: "badge" },
					{ label: "Total", key: "total_amount", type: "currency" },
					{ label: "Profit", key: "total_profit", type: "currency" },
					{ label: "Status", key: "status", type: "status", formatter: (row) => this.format_docstatus(row) },
					{ label: "Actions", key: "actions", type: "actions" },
				],
			},
			returns: {
				label: "Returns",
				short_label: "Returns",
				doctype: "Ledgix Sales Return",
				child_doctype: "Ledgix Sales Return Item",
				search_fields: ["name", "original_sale", "customer"],
				order_by: "modified desc",
				fields: ["original_sale", "customer", "total_amount", "total_profit_reversal", "docstatus", "modified", "owner"],
				columns: [
					{ label: "", key: "selector", type: "selector" },
					{ label: "Return ID", key: "name", type: "strong" },
					{ label: "Original Invoice", key: "original_sale" },
					{ label: "Date", key: "modified", type: "datetime" },
					{ label: "Customer", key: "customer" },
					{ label: "Returned Items", key: "_items_count", type: "number" },
					{ label: "Refund Amount", key: "total_amount", type: "currency" },
					{ label: "Cashier", key: "owner" },
					{ label: "Status", key: "status", type: "status", formatter: (row) => this.format_docstatus(row) },
					{ label: "Actions", key: "actions", type: "actions" },
				],
			},
			stock: {
				label: "Stock Movements",
				short_label: "Stock",
				doctype: "Ledgix Stock Movement",
				search_fields: ["name", "item", "reference_name", "reference_doctype"],
				order_by: "movement_date desc",
				fields: ["item", "movement_type", "movement_source", "quantity", "movement_date", "reference_doctype", "reference_name", "reference_note", "owner", "docstatus", "modified", "rate", "amount", "total_amount", "stock_value", "valuation_rate"],
				columns: [
					{ label: "Movement ID", key: "name", type: "strong" },
					{ label: "Date / Time", key: "movement_date", type: "datetime" },
					{ label: "Item", key: "item" },
					{ label: "Type", key: "movement_type", type: "status" },
					{ label: "Source", key: "movement_source", type: "badge", formatter: (row) => row.movement_source || this.infer_movement_source(row) },
					{ label: "Qty", key: "quantity", type: "number" },
					{ label: "Source Doc", key: "source_doc", formatter: (row) => this.join_values([row.reference_doctype, row.reference_name]) },
					{ label: "User", key: "owner" },
					{ label: "Remarks", key: "reference_note" },
					{ label: "Actions", key: "actions", type: "actions" },
				],
			},
			shifts: {
				label: "Shifts",
				short_label: "Shifts",
				doctype: "Ledgix POS Shift",
				search_fields: ["name", "opened_by", "closed_by", "status"],
				order_by: "opening_time desc",
				fields: [
					"opening_time",
					"closing_time",
					"opened_by",
					"closed_by",
					"status",
					"opening_cash",
					"expected_cash",
					"actual_cash",
					"cash_variance",
					"cash_sales",
					"non_cash_sales",
					"total_sales",
					"invoice_count",
					"modified"
				],
				columns: [
					{ label: "", key: "selector", type: "selector" },
					{ label: "Shift ID", key: "name", type: "strong" },
					{ label: "Status", key: "status", type: "status" },
					{ label: "Opened By", key: "opened_by" },
					{ label: "Opening Time", key: "opening_time", type: "datetime" },
					{ label: "Closing Time", key: "closing_time", type: "datetime" },
					{ label: "Opening Cash", key: "opening_cash", type: "currency" },
					{ label: "Cash Sales", key: "cash_sales", type: "currency" },
					{ label: "Non Cash", key: "non_cash_sales", type: "currency" },
					{ label: "Expected Cash", key: "expected_cash", type: "currency" },
					{ label: "Actual Cash", key: "actual_cash", type: "currency" },
					{ label: "Variance", key: "cash_variance", type: "currency" },
					{ label: "Invoices", key: "invoice_count", type: "number" },
					{ label: "Actions", key: "actions", type: "actions" }
				],
			},
		};
	}

	// ============================================================
	// PAGE ACTIONS
	// ============================================================

	make_page_actions() {
		this.page.clear_actions_menu();
		this.page.set_title("");
	}

	// ============================================================
	// SHELL
	// ============================================================

	make_shell() {
		this.$root = $(this.page.body).empty();

		this.$root.html(`
			<div class="ledgix-operations-page">
			<div class="lx-ops-shell">
				<section class="lx-ops-hero">
					<div class="lx-ops-hero-copy">
						<div class="lx-eyebrow">Operations Center</div>
						<h2>Ledgix Operations Center</h2>
						<p>Daily business operations workspace for products, categories, purchases, sales, returns, stock activity and POS shifts.</p>
					</div>

					<div class="lx-ops-hero-actions">
						<div class="lx-mode-badge lx-mode-inventory" title="Current Ledgix stock mode">
							<span class="lx-mode-badge-dot"></span>
							<span class="lx-mode-badge-label">Strict Inventory</span>
						</div>
					</div>
				</section>
				

				<nav class="lx-ops-tabs" role="tablist">
					${Object.entries(this.modules).map(([key, mod]) => `
						<button class="lx-ops-tab ${key === this.active_module ? "is-active" : ""}" data-module="${key}" type="button">
							<span>${this.safe_text(mod.short_label || mod.label)}</span>
						</button>
					`).join("")}
				</nav>

				<section class="lx-ops-workspace">
					<div class="lx-ops-main-panel">
						<div class="lx-module-head"></div>
						<div class="lx-module-controls"></div>
						<div class="lx-table-wrap"></div>
						<div class="lx-pagination-wrap"></div>
					</div>
					<aside class="lx-ops-side-panel"></aside>
				</section>

				
			</div>
			</div>
		`);

		this.setup_responsive_layout();

		window.LedgixNavigator?.mount?.({
			page: this.page,
			wrapper: this.wrapper,
			content: this.$root.find(".ledgix-operations-page").first(),
			active: "operations"
		});
	}

	setup_responsive_layout() {
		const update = () => {
			if (!this.$root || !this.$root.length) return;

			const shell = this.$root.find(".lx-ops-shell").get(0);
			const workspace = this.$root.find(".lx-ops-workspace").get(0);
			const width = shell ? shell.getBoundingClientRect().width : (workspace ? workspace.getBoundingClientRect().width : 0);
			const tight_width = width > 0 && width < 1220;

			this.$root.toggleClass("lx-ops-compact-density", width > 0 && width < 1420);
			this.$root.toggleClass("lx-ops-compact-summary", tight_width);
		};

		if (this.ops_layout_observer) {
			this.ops_layout_observer.disconnect();
		}


		if (window.ResizeObserver) {
			this.ops_layout_observer = new ResizeObserver(() => window.requestAnimationFrame(update));
			this.ops_layout_observer.observe(this.$root.find(".lx-ops-shell").get(0) || this.$root[0]);
		}


		window.addEventListener("resize", update);
		window.requestAnimationFrame(update);
	}


	


	// ============================================================
	// EVENTS
	// ============================================================

	bind_events() {
		this.theme_update_handler = (e) => {
			const theme =
				(e && e.detail && e.detail.theme) ||
				window.LedgixTheme?.get?.() ||
				window.ledgix_theme ||
				{};

			this.boot.theme_settings = theme;
			this.apply_theme_variables(theme);
		};

		if (window.__ledgix_operations_theme_handler) {
			window.removeEventListener("ledgix:theme-updated", window.__ledgix_operations_theme_handler);
			document.removeEventListener("ledgix:theme-updated", window.__ledgix_operations_theme_handler);
		}

		window.__ledgix_operations_theme_handler = this.theme_update_handler;

		window.addEventListener("ledgix:theme-updated", this.theme_update_handler);
		document.addEventListener("ledgix:theme-updated", this.theme_update_handler);

		this.theme_update_handler({
			detail: {
				theme: window.LedgixTheme?.get?.() || window.ledgix_theme || this.boot.theme_settings || {},
			},
		});

		this.$root.on("click", ".lx-ops-tab", (e) => {
			const module_key = $(e.currentTarget).data("module");
			this.set_active_module(module_key);
		});

		this.$root.on("click", ".lx-js-refresh", () => this.refresh_active_module());
		this.$root.on("click", ".lx-js-add-product", () => this.show_product_dialog());
		this.$root.on("click", ".lx-js-add-category", () => this.show_category_dialog());
		this.$root.on("click", ".lx-js-new-purchase", () => this.show_purchase_dialog());
		this.$root.on("click", ".lx-js-open-shift", () => this.show_open_shift_dialog());
		this.$root.on("click", ".lx-js-close-shift", () => this.show_close_shift_dialog());
		this.$root.on("click", ".lx-js-clear-filters", () => this.clear_active_filters());
			window.addEventListener("popstate", () => this.sync_module_from_url());
			frappe.router.on("change", () => this.sync_module_from_url());

		this.$root.on("input", ".lx-filter-input", frappe.utils.debounce((e) => {
			const $input = $(e.currentTarget);
			const module_key = this.active_module;
			this.state[module_key].search = $input.val().trim();
			this.state[module_key].page = 1;
			$input.closest(".lx-search-box").toggleClass("has-value", Boolean($input.val().trim()));
			this.load_module(module_key);
		}, 250));

		this.$root.on("click", ".lx-clear-search", (e) => {
			const $box = $(e.currentTarget).closest(".lx-search-box");
			const $input = $box.find(".lx-filter-input");
			$input.val("").trigger("input").focus();
		});

		this.$root.on("change", ".lx-filter-select, .lx-filter-date", (e) => {
			const $field = $(e.currentTarget);
			const filter_key = $field.data("filter");
			this.state[this.active_module].filters[filter_key] = $field.val();
			this.state[this.active_module].page = 1;
			this.load_module(this.active_module);
		});

		this.$root.on("click", ".lx-date-range-trigger", () => this.show_date_range_dialog());

		this.$root.on("click", ".lx-page-prev", () => this.change_page(-1));
		this.$root.on("click", ".lx-page-next", () => this.change_page(1));

		this.$root.on("click", ".lx-sortable-th", (e) => {
			const key = $(e.currentTarget).data("sortKey");
			this.toggle_sort(key);
		});

		this.$root.on("click", ".lx-row-view", (e) => {
			const name = $(e.currentTarget).data("name");
			this.show_record_preview(this.active_module, name);
		});

		this.$root.on("click", ".lx-row-print", (e) => {
			const name = $(e.currentTarget).data("name");
			this.print_record(this.active_module, name);
		});

		this.$root.on("click", ".lx-row-selector", (e) => {
			e.stopPropagation();
			const name = $(e.currentTarget).data("name");
			this.select_table_row(this.active_module, name);
		});

		this.$root.on("click", ".lx-ops-table tbody tr", (e) => {
			if ($(e.target).closest("button, a, input, select, textarea").length) return;
			const name = $(e.currentTarget).data("name");
			this.select_table_row(this.active_module, name);
		});

		this.$root.on("click", ".lx-selection-clear", () => this.clear_selected_row(this.active_module, true));
		this.$root.on("click", ".lx-actions-trigger", (e) => {
			e.stopPropagation();
			const $group = $(e.currentTarget).closest(".lx-selected-actions");
			this.$root.find(".lx-selected-actions").not($group).removeClass("is-open");
			$group.toggleClass("is-open");
		});

		this.$root.on("click", ".lx-selected-actions-menu", (e) => {
			e.stopPropagation();
		});

		$(document).on("click.ledgix_operations_actions", () => {
			if (this.$root) {
				this.$root.find(".lx-selected-actions").removeClass("is-open");
			}
		});
		this.$root.on("click", ".lx-selected-view", () => this.run_selected_action("view"));
		this.$root.on("click", ".lx-selected-edit", () => this.run_selected_action("edit"));
		this.$root.on("click", ".lx-selected-print", () => this.run_selected_action("print"));
		this.$root.on("click", ".lx-selected-submit", () => this.run_selected_action("submit"));
		this.$root.on("click", ".lx-selected-cancel", () => this.run_selected_action("cancel"));
		this.$root.on("click", ".lx-selected-delete", () => this.run_selected_action("delete"));
		this.$root.on("click", ".lx-selected-close-shift", () => this.run_selected_action("close_shift"));

		this.$root.on("click", ".lx-row-source", (e) => {
			e.preventDefault();
			frappe.msgprint({
				title: "Backend form blocked",
				message: "Operations Center keeps users inside Ledgix UI. Use View, Print or the available action buttons here.",
				indicator: "orange"
			});
		});


	}

	// ============================================================
	// BOOTSTRAP
	// ============================================================

	async bootstrap() {
		this.render_module(this.active_module, true);
		await this.load_boot_data();
		this.apply_mode_classes();
		this.apply_theme_variables(this.boot.theme_settings);
		await this.load_static_options();
		this.render_module(this.active_module, true);
		await this.load_module(this.active_module);
	}

	async load_boot_data() {
		try {
			const r = await this.call_method(this.method_paths.pos_boot, {});
			const data = r || {};
			this.boot.stock_control_mode = data.stock_control_mode || this.boot.stock_control_mode;
			this.boot.theme_settings = data.theme_settings || data.theme || null;
			window.LedgixNavigator?.setMode?.(this.boot.stock_control_mode);
		} catch (e) {
			console.warn("Ledgix boot data unavailable. Using safe defaults.", e);
			window.LedgixNavigator?.setMode?.(this.boot.stock_control_mode);
		}
	}

	async load_static_options() {
		this.option_cache.categories = await this.safe_get_list("Ledgix Category", ["name", "category_name"], {}, "category_name asc", 100);
		this.option_cache.suppliers = await this.safe_get_list("Ledgix Supplier", ["name", "supplier_name"], {}, "supplier_name asc", 100);
		this.option_cache.users = await this.safe_get_list("User", ["name", "full_name"], { enabled: 1 }, "full_name asc", 100);
	}

	// ============================================================
	// MODE / THEME
	// ============================================================

	is_billing_mode() {
		return String(this.boot.stock_control_mode || "").toLowerCase().includes("billing");
	}

	apply_mode_classes() {
		const billing = this.is_billing_mode();
		this.$root
			.toggleClass("lx-stock-mode-inventory", !billing)
			.toggleClass("lx-stock-mode-billing", billing);

		this.$root.find(".lx-mode-badge")
			.removeClass("lx-mode-inventory lx-mode-billing")
			.addClass(billing ? "lx-mode-billing" : "lx-mode-inventory")
			.find(".lx-mode-badge-label")
			.text(billing ? "Billing Only" : "Strict Inventory");

	}

		build_theme_palette(primary) {
			const color = primary || "#64748b";

			const mix = (hex, target, weight) => {
				const clean = String(hex || "").replace("#", "");
				const base = clean.length === 3
					? clean.split("").map((c) => c + c).join("")
					: clean;

				const a = {
					r: parseInt(base.slice(0, 2), 16),
					g: parseInt(base.slice(2, 4), 16),
					b: parseInt(base.slice(4, 6), 16),
				};

				const t = target === "black"
					? { r: 0, g: 0, b: 0 }
					: { r: 255, g: 255, b: 255 };

				const p = weight / 100;
				const out = {
					r: Math.round(a.r * p + t.r * (1 - p)),
					g: Math.round(a.g * p + t.g * (1 - p)),
					b: Math.round(a.b * p + t.b * (1 - p)),
				};

				return `#${[out.r, out.g, out.b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
			};

			return {
				enable_custom_accent: 1,
				auto_generate_shades: 1,
				primary_accent_color: color,
				accent_hover: mix(color, "black", 82),
				accent_soft: mix(color, "white", 10),
				accent_soft_2: mix(color, "white", 16),
				accent_border: mix(color, "white", 28),
			};
		}


	apply_theme_variables(theme) {
		const page_roots = Array.from(document.querySelectorAll(".ledgix-operations-page"));
		const targets = [this.$root && this.$root[0], ...page_roots, document.documentElement, document.body]
			.filter(Boolean)
			.filter((target, index, list) => list.indexOf(target) === index);
		const primary = this.normalize_theme_hex(theme && theme.primary_accent_color);
		const enabled = theme && theme.enable_custom_accent && primary;

		if (!enabled) {
			this.clear_theme_variables(targets);
			return;
		}

		const rgb = theme.accent_rgb || this.theme_rgb_string(primary);
		const vars = {
			"--lx-accent": primary,
			"--accent": primary,
			"--ledgix-accent": primary,
			"--lx-accent-hover": theme.accent_hover || `color-mix(in srgb, ${primary} 82%, black)`,
			"--accent-hover": theme.accent_hover || `color-mix(in srgb, ${primary} 82%, black)`,
			"--lx-accent-soft": theme.accent_soft || `color-mix(in srgb, ${primary} 10%, white)`,
			"--accent-soft": theme.accent_soft || `color-mix(in srgb, ${primary} 10%, white)`,
			"--lx-accent-soft-2": theme.accent_soft_2 || `color-mix(in srgb, ${primary} 15%, white)`,
			"--accent-soft-2": theme.accent_soft_2 || `color-mix(in srgb, ${primary} 15%, white)`,
			"--lx-accent-border": theme.accent_border || `color-mix(in srgb, ${primary} 32%, white)`,
			"--accent-border": theme.accent_border || `color-mix(in srgb, ${primary} 32%, white)`,
			"--lx-accent-ring": `color-mix(in srgb, ${primary} 22%, transparent)`,
			"--accent-ring": theme.accent_ring || `color-mix(in srgb, ${primary} 22%, transparent)`,
			"--lx-accent-surface": `color-mix(in srgb, ${primary} 7%, #ffffff 93%)`,
			"--lx-accent-shadow": `color-mix(in srgb, ${primary} 20%, transparent)`,
				"--lx-accent-rgb": rgb,
				"--ledgix-accent-rgb": rgb,
				"--accent-rgb": rgb,
			};

		targets.forEach((root) => {
			root.setAttribute("data-ledgix-theme", "enabled");
			Object.entries(vars).forEach(([key, value]) => root.style.setProperty(key, value));
		});
	}

	normalize_theme_hex(value) {
		const text = String(value || "").trim();
		if (/^#[0-9a-fA-F]{6}$/.test(text)) return text;
		if (/^[0-9a-fA-F]{6}$/.test(text)) return `#${text}`;
		if (/^#[0-9a-fA-F]{3}$/.test(text)) {
			return `#${text.slice(1).split("").map((char) => char + char).join("")}`;
		}
		return "";
	}

	theme_rgb_string(hex) {
		const color = this.normalize_theme_hex(hex);
		if (!color) return "";
		return [
			parseInt(color.slice(1, 3), 16),
			parseInt(color.slice(3, 5), 16),
			parseInt(color.slice(5, 7), 16),
		].join(", ");
	}

	clear_theme_variables(targets) {
		const vars = [
			"--lx-accent", "--accent", "--ledgix-accent", "--ledgix-primary", "--primary",
			"--lx-page-accent", "--lx-accent-hover", "--accent-hover",
			"--lx-accent-soft", "--accent-soft", "--lx-accent-soft-2", "--accent-soft-2",
			"--lx-accent-border", "--accent-border", "--lx-accent-ring", "--accent-ring",
			"--lx-accent-surface", "--lx-accent-shadow", "--lx-accent-rgb",
			"--ledgix-accent-rgb", "--accent-rgb"
		];

		targets.forEach((root) => {
			vars.forEach((key) => root.style.removeProperty(key));
			root.setAttribute("data-ledgix-theme", "disabled");
		});
	}

	// ============================================================
	// MODULE RENDERING
	// ============================================================

	
	get_url_module() {
		const params = new URLSearchParams(window.location.search || "");
		const requested = params.get("module");

		const aliases = {
			products: "products",
			categories: "categories",
			"product-categories": "categories",
			purchases: "purchases",
			sales: "sales",
			returns: "returns",
			"sales-returns": "returns",
			stock: "stock",
			"stock-movements": "stock",
			shifts: "shifts",
			"pos-shifts": "shifts"
		};

		return aliases[requested] || "";
	}

	sync_module_from_url() {
		const module_key = this.get_url_module();

		if (!module_key || !this.modules[module_key]) return;
		if (module_key === this.active_module) return;

		this.set_active_module(module_key);
	}

	update_url_for_module(module_key) {
		const aliases = {
			products: "products",
			categories: "categories",
			purchases: "purchases",
			sales: "sales",
			returns: "sales-returns",
			stock: "stock-movements",
			shifts: "pos-shifts"
		};

		const public_key = aliases[module_key] || module_key;

		const next_url = `/app/ledgix_operations?module=${public_key}`;

		window.history.replaceState({}, "", next_url);
		window.LedgixNavigator?.updateActiveState?.();
	}




	set_active_module(module_key) {
		if (!this.modules[module_key]) return;

		if (this.active_module === module_key) {
			localStorage.setItem("ledgix_operations_active_module", module_key);
			return;
		}

		this.clear_selected_row(this.active_module, false);
		this.active_module = module_key;
		this.update_url_for_module(module_key);
		localStorage.setItem("ledgix_operations_active_module", module_key);
		this.$root.find(".lx-ops-tab").removeClass("is-active");
		this.$root.find(`.lx-ops-tab[data-module="${module_key}"]`).addClass("is-active");
		this.render_module(module_key, true);
		this.load_module(module_key);
	}

	render_module(module_key, loading = false) {
		const mod = this.modules[module_key];
		this.$root.find(".lx-module-head").html(`
			<div class="lx-module-title-block">
				<div class="lx-module-icon">${this.icon_svg(this.get_module_icon(module_key))}</div>
				<div>
					<h3>${this.safe_text(mod.label)}</h3>
					<p>${this.get_module_subtitle(module_key)}</p>
				</div>
			</div>
			<div class="lx-module-head-actions">
				${this.module_action_html(module_key)}
			</div>
		`);

		this.render_controls(module_key);
		this.render_table(module_key, loading ? null : []);
		this.render_side_panel(module_key, []);
		this.render_pagination(module_key);
		
	}

	get_module_icon(module_key) {
		return {
			products: "package",
			categories: "tag",
			purchases: "bill",
			sales: "sales-trend",
			returns: "return",
			stock: "warehouse",
			shifts: "wallet",
		}[module_key] || "analytics";
	}

	module_action_html(module_key) {
		const base_actions = [];

		if (module_key === "products") {
			base_actions.push(`<button class="btn btn-sm btn-primary lx-module-action lx-js-add-product" type="button">${this.icon_svg("plus")}<span>Add Product</span></button>`);
		}

		if (module_key === "categories") {
			base_actions.push(`<button class="btn btn-sm btn-primary lx-module-action lx-js-add-category" type="button">${this.icon_svg("plus")}<span>Add Category</span></button>`);
		}

		if (module_key === "purchases") {
			base_actions.push(`<button class="btn btn-sm btn-primary lx-module-action lx-js-new-purchase" type="button">${this.icon_svg("plus")}<span>New Purchase</span></button>`);
		}

		if (module_key === "shifts") {
			base_actions.push(`<button class="btn btn-sm btn-primary lx-module-action lx-js-open-shift" type="button">${this.icon_svg("plus")}<span>Open Shift</span></button>`);
			base_actions.push(`<button class="btn btn-sm btn-default lx-module-action lx-js-close-shift" type="button">${this.icon_svg("wallet")}<span>Close Shift</span></button>`);
		}

		return `
			<div class="lx-module-action-group lx-module-base-actions">${base_actions.join("")}</div>
			<div class="lx-module-action-group lx-selected-actions">${this.selected_action_html(module_key)}</div>
		`;
	}

	selected_action_html(module_key) {
		const state = this.state[module_key] || {};
		const row = state.selected_row;

		if (!row) {
			return `
				<button class="lx-actions-trigger is-disabled" type="button" disabled aria-disabled="true" title="Select a row first">
					<span>Actions</span>
					${this.icon_svg("chevron-down")}
				</button>
			`;
		}

		const buttons = this.get_selected_actions(module_key, row).map((action) => `
			<button class="lx-selected-action ${action.className || ""}" type="button" data-action="${this.safe_attr(action.key)}">
				${this.icon_svg(action.icon)}<span>${this.safe_text(action.label)}</span>
			</button>
		`).join("");

		return `
			<button class="lx-actions-trigger" type="button" aria-haspopup="menu" aria-expanded="false">
				<span>Actions</span>
				${this.icon_svg("chevron-down")}
			</button>
			<div class="lx-selected-actions-menu" role="menu">
				${buttons}
				<button class="lx-selection-clear" type="button">
					${this.icon_svg("x-circle")}<span>Clear Selection</span>
				</button>
			</div>
		`;
	}

	get_selected_actions(module_key, row) {
		const docstatus = this.to_number(row.docstatus);

		if (module_key === "shifts") {
			const status = String(row.status || "").trim();

			if (docstatus === 2 || status === "Cancelled") {
				return [{ key: "view", label: "View", icon: "eye", className: "lx-selected-view" }];
			}

			if (status === "Open" && docstatus === 0) {
				return [
					{ key: "view", label: "View", icon: "eye", className: "lx-selected-view" },
					{ key: "close_shift", label: "Close Shift", icon: "wallet", className: "lx-selected-close-shift is-warning" },
				];
			}

			if (status === "Closed" && docstatus === 0) {
				return [
					{ key: "view", label: "View", icon: "eye", className: "lx-selected-view" },
					{ key: "submit", label: "Submit Shift", icon: "check", className: "lx-selected-submit is-success" },
				];
			}

			if (status === "Closed" && docstatus === 1) {
				return [
					{ key: "view", label: "View", icon: "eye", className: "lx-selected-view" },
					{ key: "print", label: "Print", icon: "printer", className: "lx-selected-print" },
				];
			}

			return [{ key: "view", label: "View", icon: "eye", className: "lx-selected-view" }];
		}

		if (this.transaction_modules.includes(module_key)) {
			if (docstatus === 0) {
				const actions = [
					{ key: "view", label: "View", icon: "eye", className: "lx-selected-view" },
				];

				if (!(module_key === "sales" && this.is_sales_read_only())) {
					actions.push(
						{ key: "edit", label: "Edit", icon: "edit", className: "lx-selected-edit" },
						{ key: "submit", label: "Submit", icon: "check", className: "lx-selected-submit is-success" },
					);
				}

				if (this.can_delete_transaction(module_key)) {
					actions.push({ key: "delete", label: "Delete", icon: "trash", className: "lx-selected-delete is-danger" });
				}

				return actions;
			}

			if (docstatus === 1) {
				const actions = [
					{ key: "view", label: "View", icon: "eye", className: "lx-selected-view" },
					{ key: "print", label: "Print", icon: "printer", className: "lx-selected-print" },
				];

				if (this.can_cancel_transaction(module_key)) {
					actions.push({ key: "cancel", label: "Cancel", icon: "x-circle", className: "lx-selected-cancel is-danger" });
				}

				return actions;
			}

			return [{ key: "view", label: "View", icon: "eye", className: "lx-selected-view" }];
		}

		if (this.readonly_print_modules.includes(module_key)) {
			return [
				{ key: "view", label: "View", icon: "eye", className: "lx-selected-view" },
				{ key: "print", label: "Print", icon: "printer", className: "lx-selected-print" },
			];
		}

		return [
			{ key: "view", label: "View", icon: "eye", className: "lx-selected-view" },
			{ key: "edit", label: "Edit", icon: "edit", className: "lx-selected-edit" },
		];
	}

	get_module_subtitle(module_key) {
		const billing = this.is_billing_mode();
		const subtitles = {
			products: billing ? "Maintain billing items and product master data." : "Create, review and maintain product master data.",
			categories: "Group products for POS, filters, and optional category tax defaults.",
			purchases: billing ? "Purchases are inventory workflows; use only when stock is being managed." : "Track purchase entries, supplier buying and stock intake flow.",
			sales: billing ? "Review billing-only invoices without submitted stock movements." : "Review inventory-connected POS sales safely.",
			returns: billing ? "Review returns linked to billing-only invoices where applicable." : "Control returns, refund value and linked original invoices.",
			stock: billing ? "Stock movements are hidden from daily billing-only workflow." : "Audit stock IN, OUT and adjustment movements.",
			shifts: "Open and close POS shifts, review cash variance and shift register totals.",
		};
		return subtitles[module_key] || "Manage operational records.";
	}

	// ============================================================
	// CONTROLS
	// ============================================================

	render_controls(module_key) {
		const state = this.state[module_key];
		const search_placeholder = this.get_search_placeholder(module_key);
		const filters = this.get_filters_html(module_key, state.filters);

		this.$root.find(".lx-module-controls").html(`
			<div class="lx-control-row">
				<div class="lx-search-box ${state.search ? "has-value" : ""}">
					<span class="lx-search-icon">${this.icon_svg("search")}</span>
					<input class="lx-filter-input" type="text" placeholder="${this.safe_attr(search_placeholder)}" value="${this.safe_attr(state.search || "")}">
					<button class="lx-clear-search" type="button" aria-label="Clear search">×</button>
				</div>
				${filters}
				<div class="lx-control-actions">
					<button class="lx-filter-clear-action lx-js-clear-filters" type="button" title="Clear all filters" aria-label="Clear all filters">
						${this.icon_svg("filter-x")}<span>Clear All</span>
					</button>
					<button class="lx-icon-action lx-filter-refresh lx-js-refresh" type="button" title="Refresh ${this.safe_attr(this.modules[module_key].label)}" aria-label="Refresh ${this.safe_attr(this.modules[module_key].label)}">${this.icon_svg("refresh")}</button>
				</div>
			</div>
		`);
	}

	get_search_placeholder(module_key) {
		return {
			products: "Search item, barcode or SKU...",
			categories: "Search category name or description...",
			purchases: "Search purchase or supplier...",
			sales: "Search invoice, sale or customer...",
			returns: "Search return, invoice or customer...",
			stock: "Search item, movement or source...",
			shifts: "Search shift, user or status...",
		}[module_key] || "Search...";
	}

	get_filters_html(module_key, filters) {
		const date_range = this.date_range_html(filters);

		if (module_key === "products") {
			return `${this.select_html("category", "All Category", this.option_cache.categories || [], filters.category, "category_name")}${this.simple_select_html("stock_status", "All Stock", ["In Stock", "Low Stock", "Out of Stock"], filters.stock_status)}${this.simple_select_html("sort_by", "Sort By", ["Popular", "Cost", "Stock", "Selling Price"], filters.sort_by || "Popular")}`;
		}

		if (module_key === "categories") {
			return `${this.simple_select_html("is_active", "All Status", ["Active", "Inactive"], filters.is_active)}${this.simple_select_html("tax_enabled", "Tax Defaults", ["Enabled", "Disabled"], filters.tax_enabled)}`;
		}

		if (module_key === "purchases") {
			return `${this.select_html("supplier", "All Suppliers", this.option_cache.suppliers || [], filters.supplier, "supplier_name")}${this.simple_select_html("status", "All Status", ["Draft", "Submitted", "Cancelled"], filters.status)}${date_range}`;
		}

		if (module_key === "sales") {
			return `${this.select_html("cashier", "All Cashiers", this.option_cache.users || [], filters.cashier, "full_name")}${this.simple_select_html("payment_status", "All Payments", ["Unpaid", "Partial", "Paid"], filters.payment_status)}${this.simple_select_html("status", "All Status", ["Draft", "Submitted", "Cancelled"], filters.status)}${date_range}`;
		}

		if (module_key === "returns") {
			return `${this.simple_select_html("status", "All Status", ["Draft", "Submitted", "Cancelled"], filters.status)}${date_range}`;
		}

		if (module_key === "stock") {
			return `${this.simple_select_html("movement_type", "All Types", ["IN", "OUT", "ADJUSTMENT"], filters.movement_type)}${this.simple_select_html("movement_source", "All Sources", ["Purchase", "Sale", "Return", "Opening", "Manual IN", "Manual OUT", "Adjustment"], filters.movement_source)}${this.select_html("user", "All Users", this.option_cache.users || [], filters.user, "full_name")}${date_range}`;
		}

		if (module_key === "shifts") {
			return `${this.select_html("cashier", "All Cashiers", this.option_cache.users || [], filters.cashier, "full_name")}${this.simple_select_html("status", "All Status", ["Open", "Closed", "Cancelled"], filters.status)}${date_range}`;
		}

		return "";
	}

	select_html(filter_key, placeholder, rows, value, label_key) {
		const options = rows.map((row) => {
			const option_value = row.name;
			const label = row[label_key] || row.name;
			return `<option value="${this.safe_attr(option_value)}" ${value === option_value ? "selected" : ""}>${this.safe_text(label)}</option>`;
		}).join("");

		return `<select class="lx-filter-select" data-filter="${this.safe_attr(filter_key)}"><option value="">${this.safe_text(placeholder)}</option>${options}</select>`;
	}

	simple_select_html(filter_key, placeholder, values, value) {
		return `<select class="lx-filter-select" data-filter="${this.safe_attr(filter_key)}"><option value="">${this.safe_text(placeholder)}</option>${values.map((v) => `<option value="${this.safe_attr(v)}" ${value === v ? "selected" : ""}>${this.safe_text(v)}</option>`).join("")}</select>`;
	}

	date_html(filter_key, value, placeholder) {
		return `<input class="lx-filter-date" data-filter="${this.safe_attr(filter_key)}" type="date" value="${this.safe_attr(value || "")}" title="${this.safe_attr(placeholder)}">`;
	}

	date_range_html(filters) {
		const label = this.get_date_range_label(filters);
		return `
			<button class="lx-date-range-trigger" type="button" title="Select date range">
				<span class="lx-date-range-icon">${this.icon_svg("calendar")}</span>
				<span>${this.safe_text(label)}</span>
			</button>
		`;
	}

	get_date_range_label(filters) {
		const from_date = filters.from_date || "";
		const to_date = filters.to_date || "";
		if (from_date && to_date) return `${frappe.datetime.str_to_user(from_date)} — ${frappe.datetime.str_to_user(to_date)}`;
		if (from_date) return frappe.datetime.str_to_user(from_date);
		if (to_date) return frappe.datetime.str_to_user(to_date);
		return "Date Range";
	}

	show_date_range_dialog() {
		const state = this.state[this.active_module];
		const dialog = new frappe.ui.Dialog({
			title: "Select Date Range",
			fields: [
				{ fieldname: "from_date", label: "From Date", fieldtype: "Date", default: state.filters.from_date || "" },
				{ fieldname: "to_date", label: "To Date", fieldtype: "Date", default: state.filters.to_date || "" },
				{ fieldtype: "HTML", options: `<div class="lx-dialog-note"><strong>Single date also works.</strong>Use only From Date for records from that date onward, only To Date for records up to that date, or both for a range.</div>` },
			],
			primary_action_label: "Apply",
			primary_action: (values) => {
				state.filters.from_date = values.from_date || "";
				state.filters.to_date = values.to_date || "";
				state.page = 1;
				dialog.hide();
				this.render_controls(this.active_module);
				this.load_module(this.active_module);
			},
		});

		dialog.set_secondary_action(() => {
			state.filters.from_date = "";
			state.filters.to_date = "";
			dialog.hide();
			this.render_controls(this.active_module);
			this.load_module(this.active_module);
		});
		dialog.set_secondary_action_label("Reset");
		dialog.show();
	}

	clear_active_filters() {
		const state = this.state[this.active_module];
		state.search = "";
		Object.keys(state.filters || {}).forEach((key) => { state.filters[key] = ""; });
		state.page = 1;
		this.clear_selected_row(this.active_module, false);
		this.render_controls(this.active_module);
		this.load_module(this.active_module);
	}

	// ============================================================
	// DATA LOADING
	// ============================================================

	async load_module(module_key) {
		const mod = this.modules[module_key];
		const state = this.state[module_key];
		const request_id = ++this.load_request_id;

		this.clear_selected_row(module_key, false);
		this.render_table(module_key, null);
		this.$root.find(".lx-js-refresh").addClass("is-loading").prop("disabled", true);

		try {
			await this.ensure_meta(mod.doctype);
			const filters = await this.build_filters(module_key);
			const or_filters = this.build_or_filters(module_key);
			const fields = this.get_safe_fields(mod.doctype, ["name", "docstatus", "owner", "creation", "modified", ...(mod.fields || [])]);

			const total = await frappe.db.count(mod.doctype, { filters });
			if (request_id !== this.load_request_id || module_key !== this.active_module) return;

			const rows = await frappe.db.get_list(mod.doctype, {
				fields,
				filters,
				or_filters,
				order_by: this.get_module_order_by(module_key),
				limit_start: (state.page - 1) * this.page_size,
				limit_page_length: this.page_size,
			});
			if (request_id !== this.load_request_id || module_key !== this.active_module) return;

			let enriched_rows = await this.enrich_rows(module_key, rows || []);
			if (request_id !== this.load_request_id || module_key !== this.active_module) return;

			enriched_rows = await this.apply_stock_mode_to_rows(module_key, enriched_rows);
			if (request_id !== this.load_request_id || module_key !== this.active_module) return;

			state.rows = enriched_rows;
			state.loaded_total = total || 0;
			state.total = this.is_client_filtered_module(module_key) ? enriched_rows.length : (total || 0);

			this.render_table(module_key, enriched_rows);
			this.render_side_panel(module_key, enriched_rows);
			this.render_pagination(module_key);
			
			this.update_count(module_key);
		} catch (error) {
			if (request_id !== this.load_request_id || module_key !== this.active_module) return;
			console.error("Ledgix Operations load error:", error);
			this.render_error(module_key, error);
		} finally {
			if (request_id === this.load_request_id && module_key === this.active_module) {
				this.$root.find(".lx-js-refresh").removeClass("is-loading").prop("disabled", false);
			}
		}
	}

	async build_filters(module_key) {
		const state = this.state[module_key];
		const mod = this.modules[module_key];
		const filters = {};
		const doctype = mod.doctype;

		await this.ensure_meta(doctype);

		if (module_key === "products") {
			if (state.filters.category && this.has_field(doctype, "category")) filters.category = state.filters.category;
			if (state.filters.stock_status && this.has_field(doctype, "stock_status")) filters.stock_status = state.filters.stock_status;
		}

		if (module_key === "categories") {
			if (state.filters.is_active === "Active") filters.is_active = 1;
			if (state.filters.is_active === "Inactive") filters.is_active = 0;
			if (state.filters.tax_enabled === "Enabled") filters.tax_defaults_enabled = 1;
			if (state.filters.tax_enabled === "Disabled") filters.tax_defaults_enabled = 0;
		}

		if (module_key === "purchases") {
			if (state.filters.supplier && this.has_field(doctype, "supplier")) filters.supplier = state.filters.supplier;
			this.apply_status_filter(filters, state.filters.status);
			this.apply_date_filters(filters, doctype, ["purchase_date", "date", "posting_date", "modified"], state.filters);
		}

		if (module_key === "sales") {
			if (state.filters.cashier) filters.owner = state.filters.cashier;
			if (state.filters.payment_status && this.has_field(doctype, "payment_status")) filters.payment_status = state.filters.payment_status;
			this.apply_status_filter(filters, state.filters.status);
			this.apply_date_filters(filters, doctype, ["sale_date", "modified"], state.filters);
		}

		if (module_key === "returns") {
			this.apply_status_filter(filters, state.filters.status);
			this.apply_date_filters(filters, doctype, ["modified"], state.filters);
		}

		if (module_key === "stock") {
			if (state.filters.movement_type && this.has_field(doctype, "movement_type")) filters.movement_type = this.normalize_stock_movement_type(state.filters.movement_type);
			if (state.filters.movement_source && this.has_field(doctype, "movement_source")) filters.movement_source = state.filters.movement_source;
			if (state.filters.user) filters.owner = state.filters.user;
			this.apply_date_filters(filters, doctype, ["movement_date", "modified"], state.filters);
		}

		if (module_key === "shifts") {
			if (state.filters.cashier && this.has_field(doctype, "opened_by")) filters.opened_by = state.filters.cashier;
			if (state.filters.status && this.has_field(doctype, "status")) filters.status = state.filters.status;
			this.apply_date_filters(filters, doctype, ["opening_time", "modified"], state.filters);
		}

		return filters;
	}

	get_module_order_by(module_key) {
		const mod = this.modules[module_key];
		const state = this.state[module_key] || {};
		const sort = state.sort || {};
		if (sort.key && sort.direction) {
			const column = (mod.columns || []).find((col) => col.key === sort.key);
			const fieldname = column && (column.sort_field || column.key);
			if (fieldname && this.has_field(mod.doctype, fieldname)) {
				return this.get_safe_order_by(mod.doctype, `${fieldname} ${sort.direction}`);
			}
		}

		if (module_key === "products") {
			const sort_by = state.filters && state.filters.sort_by;
			const product_orders = {
				"Cost": "cost_price desc",
				"Stock": "current_stock desc",
				"Selling Price": "selling_price desc",
				"Popular": mod.order_by,
			};
			return this.get_safe_order_by(mod.doctype, product_orders[sort_by] || mod.order_by);
		}

		return this.get_safe_order_by(mod.doctype, mod.order_by);
	}

	toggle_sort(key) {
		const state = this.state[this.active_module];
		if (!state.sort) state.sort = { key: "", direction: "" };
		if (state.sort.key !== key) {
			state.sort = { key, direction: "asc" };
		} else if (state.sort.direction === "asc") {
			state.sort.direction = "desc";
		} else {
			state.sort = { key: "", direction: "" };
		}
		state.page = 1;
		this.load_module(this.active_module);
	}

	can_sort_column(module_key, col) {
		if (!col || col.type === "actions") return false;
		const mod = this.modules[module_key];
		const fieldname = col.sort_field || col.key;
		return Boolean(fieldname && (fieldname === "name" || this.has_field(mod.doctype, fieldname)));
	}

	build_or_filters(module_key) {
		const mod = this.modules[module_key];
		const state = this.state[module_key];
		const search = (state.search || "").trim();
		if (!search) return [];

		return (mod.search_fields || [])
			.filter((fieldname) => fieldname === "name" || this.has_field(mod.doctype, fieldname))
			.map((fieldname) => [fieldname, "like", `%${search}%`]);
	}

	apply_status_filter(filters, status) {
		if (!status) return;
		const docstatus_map = { Draft: 0, Submitted: 1, Cancelled: 2 };
		if (docstatus_map[status] !== undefined) filters.docstatus = docstatus_map[status];
	}

	apply_date_filters(filters, doctype, candidates, values) {
		const fieldname = candidates.find((field) => field === "modified" || this.has_field(doctype, field));
		if (!fieldname) return;

		if (values.from_date && values.to_date) {
			filters[fieldname] = ["between", [values.from_date, values.to_date]];
		} else if (values.from_date) {
			filters[fieldname] = [">=", values.from_date];
		} else if (values.to_date) {
			filters[fieldname] = ["<=", values.to_date];
		}
	}

	async enrich_rows(module_key, rows) {
		const mod = this.modules[module_key];
		if (!rows.length) return rows;

		if (module_key === "categories") {
			return Promise.all(rows.map(async (row) => {
				try {
					row._item_count = await frappe.db.count("Ledgix Item", {
						filters: { category: row.name, active: 1 },
					});
				} catch (e) {
					row._item_count = "—";
				}
				return row;
			}));
		}

		if (!mod.child_doctype) return rows;

		await this.ensure_meta(mod.child_doctype);
		return Promise.all(rows.map(async (row) => {
			try {
				row._items_count = await frappe.db.count(mod.child_doctype, { filters: { parent: row.name } });

				if (module_key === "purchases") {
					const purchase_doc = await frappe.db.get_doc(mod.doctype, row.name);
					const child_rows = purchase_doc.items || [];

					row._items_count = child_rows.length;

					row._total_qty = child_rows.reduce((sum, item) => {
						return sum + this.to_number(item.quantity);
					}, 0);

					row._total_amount = child_rows.reduce((sum, item) => {
						const amount = this.to_number(item.amount);
						if (amount) return sum + amount;

						return sum + (
							this.to_number(item.quantity) *
							this.to_number(item.rate)
						);
					}, 0);
				}
			} catch (e) {
				row._items_count = "—";
				if (module_key === "purchases") row._items_qty = "—";
			}
			return row;
		}));
	}

	async get_child_quantity_total(child_doctype, parent_name) {
		try {
			await this.ensure_meta(child_doctype);
			const qty_field = ["quantity", "qty", "stock_qty"].find((fieldname) => this.has_field(child_doctype, fieldname));
			if (!qty_field) return "—";

			const rows = await frappe.db.get_list(child_doctype, {
				fields: [qty_field],
				filters: { parent: parent_name },
				limit_page_length: 500,
			});

			return (rows || []).reduce((sum, row) => sum + this.to_number(row[qty_field]), 0);
		} catch (e) {
			console.warn("Could not calculate purchase quantity.", e);
			return "—";
		}
	}

	is_client_filtered_module(module_key) {
		return ["sales", "returns", "stock", "purchases"].includes(module_key) && this.is_billing_mode();
	}

	async apply_stock_mode_to_rows(module_key, rows) {
		if (!rows.length) return rows;

		const billing = this.is_billing_mode();

		if (module_key === "stock") {
			return billing ? [] : rows;
		}

		if (module_key === "purchases") {
			return billing ? [] : rows;
		}

		if (!["sales", "returns"].includes(module_key)) {
			return rows;
		}

		const sale_names = module_key === "sales"
			? rows.map((row) => row.name).filter(Boolean)
			: rows.map((row) => row.original_sale).filter(Boolean);

		if (!sale_names.length) return rows;

		try {
			await this.ensure_meta("Ledgix Stock Movement");
			const movements = await frappe.db.get_list("Ledgix Stock Movement", {
				fields: ["reference_name"],
				filters: {
					reference_doctype: "Ledgix Sale",
					reference_name: ["in", [...new Set(sale_names)]],
					docstatus: 1,
				},
				limit_page_length: Math.max(100, sale_names.length * 3),
			});

			const stock_linked = new Set((movements || []).map((row) => row.reference_name));
			return rows.filter((row) => {
				const sale_name = module_key === "sales" ? row.name : row.original_sale;
				const has_movement = stock_linked.has(sale_name);
				return billing ? !has_movement : has_movement;
			});
		} catch (e) {
			console.warn("Could not apply stock mode filter. Showing unfiltered rows.", e);
			return rows;
		}
	}

	// ============================================================
	// TABLE
	// ============================================================

	render_table(module_key, rows) {
		const mod = this.modules[module_key];
		const $wrap = this.$root.find(".lx-table-wrap");

		if (rows === null) {
			$wrap.html(this.loading_html());
			return;
		}

		if (!rows.length) {
			$wrap.html(this.empty_html(mod.label, module_key));
			return;
		}

		$wrap.html(`
			<div class="lx-table-scroll">
				<table class="lx-ops-table">
					<thead>
						<tr>${mod.columns.map((col) => this.table_header_html(module_key, col)).join("")}</tr>
					</thead>
					<tbody>
						${rows.map((row) => this.row_html(module_key, row)).join("")}
					</tbody>
				</table>
			</div>
		`);
	}

	table_header_html(module_key, col) {
		const state = this.state[module_key] || {};
		const sort = state.sort || {};
		const active = sort.key === col.key && sort.direction;
		if (!this.can_sort_column(module_key, col)) {
			return `<th>${this.safe_text(col.label)}</th>`;
		}
		return `<th><button class="lx-sortable-th ${active ? "is-sorted" : ""}" data-sort-key="${this.safe_attr(col.key)}" type="button" title="Sort ${this.safe_attr(col.label)}"><span>${this.safe_text(col.label)}</span></button></th>`;
	}

	row_html(module_key, row) {
		const mod = this.modules[module_key];
		const selected = (this.state[module_key] && this.state[module_key].selected_row && this.state[module_key].selected_row.name === row.name);
		return `<tr class="${selected ? "is-selected" : ""}" data-name="${this.safe_attr(row.name)}" data-docstatus="${this.safe_attr(row.docstatus)}">${mod.columns.map((col) => `<td>${this.cell_html(module_key, row, col)}</td>`).join("")}</tr>`;
	}

	cell_html(module_key, row, col) {
		if (col.type === "selector") {
			return `<button class="lx-row-selector" data-name="${this.safe_attr(row.name)}" type="button" title="Select row">${this.icon_svg("check")}</button>`;
		}

		if (col.type === "actions") return this.actions_html(module_key, row);

		const raw_value = col.formatter ? col.formatter(row) : row[col.key];
		if (col.type === "currency") return this.format_currency(raw_value);
		if (col.type === "date") return this.format_date(raw_value);
		if (col.type === "datetime") return this.format_datetime(raw_value);
		if (col.type === "number") return this.format_number(raw_value);
		if (col.type === "badge") return this.badge_html(raw_value);
		if (col.type === "status") return this.status_html(raw_value);
		if (col.type === "strong") return `<strong>${this.safe_text(raw_value)}</strong>`;

		return this.safe_text(raw_value);
	}

	actions_html(module_key, row) {
		const can_print = this.can_print_record(module_key, row);
		return `
			<div class="lx-row-actions">
				<button class="lx-icon-action lx-row-view" data-name="${this.safe_attr(row.name)}" type="button" title="View ${this.safe_attr(this.modules[module_key].label)}">${this.icon_svg("eye")}</button>
				${can_print ? `<span class="lx-action-separator"></span><button class="lx-icon-action lx-row-print" data-name="${this.safe_attr(row.name)}" type="button" title="Print ${this.safe_attr(this.modules[module_key].label)}">${this.icon_svg("printer")}</button>` : ""}
			</div>
		`;
	}

	can_print_record(module_key, row) {
		return module_key === "stock" ||
			(module_key === "shifts" && row.status === "Closed") ||
			(["purchases", "sales", "returns"].includes(module_key) && this.to_number(row.docstatus) === 1);
	}


	// ============================================================
	// ROW SELECTION + TRANSACTION ACTIONS
	// ============================================================

	select_table_row(module_key, name) {
		const state = this.state[module_key];
		if (!state || !name) return;

		if (state.selected_row && state.selected_row.name === name) {
			this.clear_selected_row(module_key, true);
			return;
		}

		const row = (state.rows || []).find((item) => item.name === name);
		if (!row) return;

		state.selected_row = row;
		this.$root.find(".lx-ops-table tbody tr").removeClass("is-selected");
		this.$root.find(`.lx-ops-table tbody tr[data-name="${this.css_escape(name)}"]`).addClass("is-selected");
		this.update_module_actions(module_key);
		this.render_side_panel(module_key, state.rows || []);
	}

	clear_selected_row(module_key, render = true) {
		const state = this.state[module_key];
		if (!state) return;
		state.selected_row = null;
		if (!render || !this.$root) return;
		this.$root.find(".lx-ops-table tbody tr").removeClass("is-selected");
		this.update_module_actions(module_key);
		this.render_side_panel(module_key, state.rows || []);
	}

	update_module_actions(module_key) {
		if (!this.$root) return;
		this.$root.find(".lx-selected-actions").html(this.selected_action_html(module_key));
	}

	async run_selected_action(action) {
		const module_key = this.active_module;
		const mod = this.modules[module_key];
		const row = this.state[module_key] && this.state[module_key].selected_row;
		if (!mod || !row) return;

		if (action === "view") {
			this.show_record_preview(module_key, row.name);
			return;
		}

		if (action === "edit") {
			if (this.transaction_modules.includes(module_key) && this.to_number(row.docstatus) !== 0) {
				frappe.msgprint({ title: "Edit blocked", message: "Submitted and cancelled documents cannot be edited from Operations Center.", indicator: "orange" });
				return;
			}

			if (module_key === "products") {
				await this.show_product_dialog(row.name);
				return;
			}

			if (module_key === "categories") {
				await this.show_category_dialog(row.name);
				return;
			}

			frappe.msgprint({
				title: "Edit modal pending",
				message: "Draft transaction editing will stay inside Operations Center. This patch blocks Frappe form routing; the full transaction edit modal should be added in the next focused pass.",
				indicator: "orange"
			});
			return;
		}

		if (action === "print") {
			this.print_record(module_key, row.name);
			return;
		}

		if (module_key === "shifts" && action === "close_shift") {
			this.show_close_shift_dialog(row);
			return;
		}

		if (!["submit", "cancel", "delete"].includes(action)) return;

		const mutation_allowed = this.transaction_modules.includes(module_key) || module_key === "shifts";
		if (!mutation_allowed) {
			frappe.msgprint({ title: "Action blocked", message: "This action is not available for this module.", indicator: "orange" });
			return;
		}

		await this.run_transaction_mutation(action, mod.doctype, row);
	}

	async run_transaction_mutation(action, doctype, row) {
		const docstatus = this.to_number(row.docstatus);

		if (action === "submit" && docstatus !== 0) {
			frappe.msgprint({ title: "Submit blocked", message: "Only draft documents can be submitted.", indicator: "orange" });
			return;
		}

		if (action === "cancel" && docstatus !== 1) {
			frappe.msgprint({ title: "Cancel blocked", message: "Only submitted documents can be cancelled.", indicator: "orange" });
			return;
		}

		if (action === "delete" && docstatus !== 0) {
			frappe.msgprint({ title: "Delete blocked", message: "Only draft documents can be deleted.", indicator: "orange" });
			return;
		}

		const labels = { submit: "Submit", cancel: "Cancel", delete: "Delete" };
		const message = `${labels[action]} ${doctype} ${row.name}?`;

		frappe.confirm(message, async () => {
			try {
				this.$root.find(".lx-selected-action, .lx-selection-clear").prop("disabled", true);

				if (action === "submit") {
					const doc = await frappe.db.get_doc(doctype, row.name);
					await this.submit_doc(doc);
				}

				if (action === "cancel") {
					await this.client_cancel(doctype, row.name);
				}

				if (action === "delete") {
					await this.client_delete(doctype, row.name);
				}

				frappe.show_alert({ message: `${doctype} ${labels[action].toLowerCase()}d`, indicator: "green" });
				this.clear_selected_row(this.active_module, true);
				await this.load_module(this.active_module);
			} catch (error) {
				console.error(error);
				frappe.msgprint({ title: `${labels[action]} failed`, message: error.message || String(error), indicator: "red" });
			} finally {
				this.$root.find(".lx-selected-action, .lx-selection-clear").prop("disabled", false);
			}
		});
	}

	client_cancel(doctype, name) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: "frappe.client.cancel",
				args: { doctype, name },
				callback: (r) => resolve(r.message),
				error: (r) => reject(r),
			});
		});
	}

	client_delete(doctype, name) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: "frappe.client.delete",
				args: { doctype, name },
				callback: (r) => resolve(r.message),
				error: (r) => reject(r),
			});
		});
	}

	css_escape(value) {
		if (window.CSS && window.CSS.escape) return window.CSS.escape(String(value));
		return String(value).replace(/"/g, '\\"');
	}

	// ============================================================
	// SIDE PANEL
	// ============================================================

	render_side_panel(module_key, rows) {
		const state = this.state[module_key] || {};
		const selected_row = state.selected_row;
		const has_selection = Boolean(selected_row && selected_row.name);
		const cards = has_selection
			? this.get_selected_side_cards(module_key, selected_row)
			: this.get_side_cards(module_key, rows, state.total);

		this.$root.find(".lx-ops-side-panel").html(`
			<div class="lx-side-title ${has_selection ? "is-selected-context" : ""}">
				<div class="lx-side-title-icon">${this.icon_svg(has_selection ? "check" : this.get_module_icon(module_key))}</div>
				<div>
					<h4>${has_selection ? "Selected Row" : `${this.safe_text(this.modules[module_key].label)} Summary`}</h4>
					<p>${has_selection ? this.safe_text(selected_row.name) : "Live snapshot for current filters."}</p>
				</div>
				${has_selection ? `<button class="lx-side-clear lx-selection-clear" type="button" title="Clear selection">${this.icon_svg("x-circle")}</button>` : ""}
			</div>
			<div class="lx-side-cards ${has_selection ? "is-detail-mode" : ""}">
				${cards.map((card) => this.side_card_html(card)).join("")}
			</div>
		`);
	}

	side_card_html(card) {
		return `
			<div class="lx-side-card ${card.tone || ""}">
				<div class="lx-side-card-icon">${this.icon_svg(card.icon || "cube")}</div>
				<div class="lx-side-card-copy">
					<span>${this.safe_text(card.label)}</span>
					<em>${this.safe_text(card.hint || "")}</em>
				</div>
				<strong>${this.safe_text(String(card.value))}</strong>
			</div>
		`;
	}

	get_selected_side_cards(module_key, row) {
		const docstatus = this.to_number(row.docstatus);
		const docstatus_label = this.format_docstatus(row);

		if (module_key === "products") {
			return [
				{ label: "Item Code", hint: "Selected product", value: row.item_code || row.name, icon: "cube", tone: "is-accent" },
				{ label: "Item Name", hint: "Product display name", value: row.item_name || "—", icon: "tag" },
				{ label: "Category", hint: "Product category", value: row.category || "—", icon: "tag" },
				{ label: "Tracking", hint: "Stock identity mode", value: row.tracking_type || "Normal", icon: "layers" },
				{ label: "Current Stock", hint: "Available quantity", value: this.format_number(row.current_stock), icon: "warehouse", tone: this.to_number(row.current_stock) <= 0 ? "is-danger" : "is-success" },
				{ label: "Selling Price", hint: "Retail price", value: this.format_currency(row.selling_price), icon: "coin" },
			];
		}

		if (module_key === "categories") {
			return [
				{ label: "Category", hint: "Selected category", value: row.category_name || row.name, icon: "tag", tone: "is-accent" },
				{ label: "Items", hint: "Active products in category", value: this.format_number(row._item_count), icon: "cube" },
				{ label: "Tax Defaults", hint: "Category tax inheritance", value: cint(row.tax_defaults_enabled) ? "Enabled" : "Disabled", icon: "layers" },
				{ label: "Tax Category", hint: "Default tax category", value: row.default_tax_category || "—", icon: "receipt" },
				{ label: "Status", hint: "Category visibility", value: cint(row.is_active) ? "Active" : "Inactive", icon: cint(row.is_active) ? "check" : "x-circle", tone: cint(row.is_active) ? "is-success" : "is-danger" },
			];
		}

		if (module_key === "purchases") {
			return [
				{ label: "Purchase ID", hint: "Selected purchase", value: row.name, icon: "bill", tone: "is-accent" },
				{ label: "Supplier", hint: "Buying party", value: row.supplier || "—", icon: "tag" },
				{ label: "Date", hint: "Purchase date", value: this.first_value(row, ["purchase_date", "date", "posting_date", "modified"], true), icon: "calendar" },
				{ label: "Items", hint: "Line items", value: this.format_number(row._items_count), icon: "layers" },
				{ label: "Total", hint: "Visible purchase value", value: this.format_currency(row._total_amount), icon: "wallet", tone: "is-accent" },
				{ label: "Status", hint: "Document status", value: docstatus_label, icon: docstatus === 1 ? "check" : "edit", tone: docstatus === 1 ? "is-success" : (docstatus === 2 ? "is-danger" : "is-warning") },
			];
		}

		if (module_key === "sales") {
			return [
				{ label: "Invoice No", hint: "Customer invoice", value: row.invoice_number || row.name, icon: "receipt", tone: "is-accent" },
				{ label: "Sale ID", hint: "System reference", value: row.name, icon: "database" },
				{ label: "Customer", hint: "Customer name", value: row.customer || "Walk-in Customer", icon: "tag" },
				{ label: "Total", hint: "Invoice value", value: this.format_currency(row.total_amount), icon: "coin", tone: "is-accent" },
				{ label: "Profit", hint: "Gross profit", value: this.format_currency(row.total_profit), icon: "trend-up", tone: "is-success" },
				{ label: "Status", hint: "Document status", value: docstatus_label, icon: docstatus === 1 ? "check" : "edit", tone: docstatus === 1 ? "is-success" : (docstatus === 2 ? "is-danger" : "is-warning") },
			];
		}

		if (module_key === "returns") {
			return [
				{ label: "Return ID", hint: "Selected return", value: row.name, icon: "return", tone: "is-accent" },
				{ label: "Original Sale", hint: "Linked invoice", value: row.original_sale || "—", icon: "receipt" },
				{ label: "Customer", hint: "Return customer", value: row.customer || "—", icon: "tag" },
				{ label: "Refund Amount", hint: "Return value", value: this.format_currency(row.total_amount), icon: "refund", tone: "is-warning" },
				{ label: "Returned Items", hint: "Line items", value: this.format_number(row._items_count), icon: "layers" },
				{ label: "Status", hint: "Document status", value: docstatus_label, icon: docstatus === 1 ? "check" : "edit", tone: docstatus === 1 ? "is-success" : (docstatus === 2 ? "is-danger" : "is-warning") },
			];
		}

		if (module_key === "stock") {
			const type = this.normalize_stock_movement_type(row.movement_type);
			const source = row.movement_source || this.infer_movement_source(row);
			return [
				{ label: "Movement ID", hint: "Selected movement", value: row.name, icon: "warehouse", tone: "is-accent" },
				{ label: "Item", hint: "Moved item", value: row.item || "—", icon: "cube" },
				{ label: "Type", hint: "Movement direction", value: type || "—", icon: type === "OUT" ? "arrow-up" : "arrow-down", tone: type === "OUT" ? "is-danger" : (type === "IN" ? "is-success" : "is-warning") },
				{ label: "Source", hint: "Movement origin", value: source || "—", icon: "database" },
				{ label: "Quantity", hint: "Moved quantity", value: this.format_number(row.quantity), icon: "layers" },
				{ label: "Source", hint: "Reference document", value: this.join_values([row.reference_doctype, row.reference_name]), icon: "database" },
				{ label: "Value", hint: "Estimated movement value", value: this.format_currency(this.get_stock_row_value(row)), icon: "coin" },
			];
		}

		if (module_key === "shifts") {
			const variance = this.to_number(row.cash_variance);
			return [
				{ label: "Shift ID", hint: "Selected register", value: row.name, icon: "wallet", tone: "is-accent" },
				{ label: "Status", hint: "Shift state", value: row.status || docstatus_label, icon: row.status === "Closed" ? "check" : "edit", tone: row.status === "Closed" ? "is-success" : (row.status === "Open" ? "is-warning" : "is-danger") },
				{ label: "Opened By", hint: "Cashier/user", value: row.opened_by || "—", icon: "tag" },
				{ label: "Expected Cash", hint: "Opening + cash sales", value: this.format_currency(row.expected_cash), icon: "coin" },
				{ label: "Actual Cash", hint: "Cash counted", value: this.format_currency(row.actual_cash), icon: "wallet" },
				{ label: "Variance", hint: "Actual minus expected", value: this.format_currency(variance), icon: "warning", tone: variance === 0 ? "is-success" : "is-danger" },
			];
		}

		return [
			{ label: "Selected Record", hint: "Current row", value: row.name, icon: "database", tone: "is-accent" },
			{ label: "Status", hint: "Document status", value: docstatus_label, icon: "check" },
		];
	}

	get_side_cards(module_key, rows, total) {
		if (module_key === "products") {
			const total_categories = this.get_total_categories(rows);
			const inventory_value = rows.reduce((sum, r) => {
				return sum + this.to_number(r.current_stock) * this.to_number(r.selling_price);
			}, 0);

			return [
				{ label: "Total Items", hint: "All items in the system", value: total, icon: "cube" },
				{ label: "Total Categories", hint: "Unique item categories", value: total_categories, icon: "tag" },
				{ label: "Low Stock Items", hint: "Items below min. stock", value: rows.filter((r) => r.stock_status === "Low Stock").length, tone: "is-warning", icon: "warning" },
				{ label: "Out of Stock Items", hint: "Items with zero stock", value: rows.filter((r) => r.stock_status === "Out of Stock").length, tone: "is-danger", icon: "x-circle" },
				{ label: "Total Inventory Value", hint: "Based on selling price", value: this.format_currency(inventory_value), tone: "is-accent", icon: "layers" },
			];
		}

		if (module_key === "categories") {
			return [
				{ label: "Visible Categories", value: rows.length, icon: "tag" },
				{ label: "Total Categories", value: total, icon: "database" },
				{ label: "Tax Enabled", value: rows.filter((r) => cint(r.tax_defaults_enabled)).length, icon: "receipt", tone: "is-accent" },
				{ label: "Active", value: rows.filter((r) => cint(r.is_active)).length, icon: "check", tone: "is-success" },
				{ label: "Linked Items", value: rows.reduce((sum, r) => sum + this.to_number(r._item_count), 0), icon: "cube" },
			];
		}

		if (module_key === "purchases") {
			return [
				{ label: "Visible Purchases", value: rows.length, icon: "bill" },
				{ label: "Total Records", value: total, icon: "database" },
				{ label: "Visible Value", value: this.format_currency(rows.reduce((sum, r) => sum + this.to_number(r._total_amount), 0)), icon: "wallet", tone: "is-accent" },
				{ label: "Submitted Visible", value: rows.filter((r) => r.docstatus === 1).length, icon: "check", tone: "is-success" },
				{ label: "Draft Visible", value: rows.filter((r) => r.docstatus === 0).length, icon: "edit", tone: "is-warning" },
			];
		}

		if (module_key === "sales") {
			const total_sales = rows.reduce((sum, r) => sum + this.to_number(r.total_amount), 0);
			return [
				{ label: "Visible Sales", value: rows.length, icon: "sales-trend" },
				{ label: "Mode Records", value: total, icon: "database" },
				{ label: "Visible Revenue", value: this.format_currency(total_sales), icon: "coin", tone: "is-accent" },
				{ label: "Visible Profit", value: this.format_currency(rows.reduce((sum, r) => sum + this.to_number(r.total_profit), 0)), icon: "trend-up", tone: "is-success" },
				{ label: "Average Bill", value: this.format_currency(rows.length ? total_sales / rows.length : 0), icon: "receipt" },
			];
		}

		if (module_key === "returns") {
			return [
				{ label: "Visible Returns", value: rows.length, icon: "return" },
				{ label: "Mode Records", value: total, icon: "database" },
				{ label: "Refund Value", value: this.format_currency(rows.reduce((sum, r) => sum + this.to_number(r.total_amount), 0)), tone: "is-warning", icon: "refund" },
				{ label: "Submitted Visible", value: rows.filter((r) => r.docstatus === 1).length, icon: "check", tone: "is-success" },
				{ label: "Cancelled Visible", value: rows.filter((r) => r.docstatus === 2).length, icon: "x-circle", tone: "is-danger" },
			];
		}

		if (module_key === "stock") {
			const in_rows = rows.filter((r) => this.normalize_stock_movement_type(r.movement_type) === "IN");
			const out_rows = rows.filter((r) => this.normalize_stock_movement_type(r.movement_type) === "OUT");
			const adjustment_rows = rows.filter((r) => this.normalize_stock_movement_type(r.movement_type) === "ADJUSTMENT");
			const manual_in = rows.filter((r) => (r.movement_source || this.infer_movement_source(r)) === "Manual IN").length;
			const manual_out = rows.filter((r) => (r.movement_source || this.infer_movement_source(r)) === "Manual OUT").length;
			const in_qty = in_rows.reduce((sum, r) => sum + this.to_number(r.quantity), 0);
			const out_qty = out_rows.reduce((sum, r) => sum + this.to_number(r.quantity), 0);
			const in_value = in_rows.reduce((sum, r) => sum + this.get_stock_row_value(r), 0);
			const out_value = out_rows.reduce((sum, r) => sum + this.get_stock_row_value(r), 0);

			return [
				{ label: "Total Movements", hint: "Visible stock records", value: rows.length, icon: "warehouse" },
				{ label: "IN Quantity", hint: `Value ${this.format_currency(in_value)}`, value: this.format_number(in_qty), icon: "arrow-down", tone: "is-success" },
				{ label: "OUT Quantity", hint: `Value ${this.format_currency(out_value)}`, value: this.format_number(out_qty), icon: "arrow-up", tone: "is-danger" },
				{ label: "Manual IN / OUT", hint: "Direct item stock changes", value: `${manual_in} / ${manual_out}`, icon: "sliders", tone: "is-accent" },
				{ label: "Net Movement Effect", hint: "IN qty minus OUT qty", value: this.format_number(in_qty - out_qty), icon: "layers", tone: in_qty >= out_qty ? "is-success" : "is-warning" },
			];
		}

		if (module_key === "shifts") {
			const cash_sales = rows.reduce((sum, r) => sum + this.to_number(r.cash_sales), 0);
			const variance = rows.reduce((sum, r) => sum + this.to_number(r.cash_variance), 0);
			const variance_tone = variance === 0 ? "is-success" : (Math.abs(variance) > 0 ? "is-danger" : "is-warning");

			return [
				{ label: "Visible Shifts", value: rows.length, icon: "wallet" },
				{ label: "Total Records", value: total, icon: "database" },
				{ label: "Open Visible", value: rows.filter((r) => r.status === "Open").length, icon: "edit", tone: "is-warning" },
				{ label: "Closed Visible", value: rows.filter((r) => r.status === "Closed").length, icon: "check", tone: "is-success" },
				{ label: "Visible Cash Sales", value: this.format_currency(cash_sales), icon: "coin", tone: "is-accent" },
				{ label: "Visible Variance", value: this.format_currency(variance), icon: "warning", tone: variance_tone },
			];
		}

		return [];
	}

	get_stock_row_value(row) {
		const direct = this.first_value(row, ["amount", "total_amount", "stock_value"]);
		if (direct !== "—") return this.to_number(direct);
		const rate = this.first_value(row, ["rate", "valuation_rate"]);
		return rate === "—" ? 0 : this.to_number(row.quantity) * this.to_number(rate);
	}


	// ============================================================
	// PAGINATION
	// ============================================================

	render_pagination(module_key) {
		const state = this.state[module_key];
		const total_pages = Math.max(1, Math.ceil((state.total || 0) / this.page_size));
		const is_first = state.page <= 1;
		const is_last = state.page >= total_pages;
		const visible = state.rows ? state.rows.length : 0;

		this.$root.find(".lx-pagination-wrap").html(`
			<div class="lx-pagination">
				<span class="lx-page-count">Showing ${this.safe_text(visible)} of ${this.safe_text(state.total || 0)}</span>
				<div class="lx-page-control" aria-label="Pagination controls">
					<button class="lx-page-btn lx-page-prev" ${is_first ? "disabled" : ""} type="button" aria-label="Previous page">‹</button>
					<strong>${state.page} of ${total_pages}</strong>
					<button class="lx-page-btn lx-page-next" ${is_last ? "disabled" : ""} type="button" aria-label="Next page">›</button>
				</div>
			</div>
		`);
	}

	change_page(direction) {
		const state = this.state[this.active_module];
		const total_pages = Math.max(1, Math.ceil((state.total || 0) / this.page_size));
		const next_page = state.page + direction;
		if (next_page < 1 || next_page > total_pages) return;

		state.page = next_page;
		this.load_module(this.active_module);
	}

	update_count(module_key) {
		// Count is intentionally shown only in the compact footer.
	}

	refresh_active_module() {
		this.load_boot_data().then(() => {
			this.apply_mode_classes();
			this.apply_theme_variables(this.boot.theme_settings);
			this.load_module(this.active_module);
		});
	}

	// ============================================================
	// PREVIEW / PRINT
	// ============================================================

	async show_record_preview(module_key, name) {
		const mod = this.modules[module_key];
		try {
			const doc = await frappe.db.get_doc(mod.doctype, name);
			const dialog_options = {
				title: `${mod.label} Preview`,
				size: "large",
				fields: [{ fieldtype: "HTML", fieldname: "preview" }],
			};

			if (this.can_print_record(module_key, doc)) {
				dialog_options.primary_action_label = "Print";
				dialog_options.primary_action = () => this.print_record(module_key, name);
			}

			const dialog = new frappe.ui.Dialog(dialog_options);

			dialog.fields_dict.preview.$wrapper.html(this.record_preview_html(module_key, doc));
			dialog.show();
		} catch (error) {
			frappe.msgprint({ title: "Preview unavailable", message: this.safe_text(error.message || error), indicator: "red" });
		}
	}

	record_preview_html(module_key, doc) {

		if (module_key === "purchases") {
			return this.purchase_preview_html(doc);
		}

		const mod = this.modules[module_key];
		const rows = (mod.columns || [])
			.filter((col) => col.type !== "actions")
			.map((col) => {
				const raw = col.formatter ? col.formatter(doc) : doc[col.key];
				let value = raw;
				if (col.type === "currency") value = this.format_currency(raw);
				if (col.type === "date") value = this.format_date(raw);
				if (col.type === "datetime") value = this.format_datetime(raw);
				if (col.type === "number") value = this.format_number(raw);
				return `<div class="lx-preview-field"><span>${this.safe_text(col.label)}</span><strong>${this.safe_text(value)}</strong></div>`;
			})
			.join("");

		return `
			<div class="lx-record-preview">
				<div class="lx-record-preview-head">
					<div class="lx-module-icon">${this.icon_svg(this.get_module_icon(module_key))}</div>
					<div>
						<h3>${this.safe_text(doc.name)}</h3>
						<p>${this.safe_text(mod.label)} quick preview. Use Open Form only when editing/auditing is needed.</p>
					</div>
				</div>
				<div class="lx-preview-grid">${rows}</div>
			</div>
		`;
	}

	purchase_preview_html(doc) {
		const items = doc.items || [];
		const total_qty = items.reduce((sum, row) => sum + this.to_number(row.quantity), 0);
		const total_amount = items.reduce((sum, row) => sum + this.to_number(row.amount || (this.to_number(row.quantity) * this.to_number(row.rate))), 0);
		const total_profit = items.reduce((sum, row) => sum + this.to_number(row.total_profit || row.item_total_profit), 0);

		return `
			<div class="lx-record-preview">
				<div class="lx-record-preview-head">
					<div class="lx-module-icon">${this.icon_svg("bill")}</div>
					<div>
						<h3>${this.safe_text(doc.name)}</h3>
						<p>Purchase invoice summary with item-level details.</p>
					</div>
				</div>

				<div class="lx-preview-grid">
					<div class="lx-preview-field"><span>Supplier</span><strong>${this.safe_text(doc.supplier)}</strong></div>
					<div class="lx-preview-field"><span>Purchase Date</span><strong>${this.safe_text(this.format_date(doc.purchase_date))}</strong></div>
					<div class="lx-preview-field"><span>Status</span><strong>${this.safe_text(this.format_docstatus(doc))}</strong></div>
					<div class="lx-preview-field"><span>Total Qty</span><strong>${this.format_plain_number(total_qty)}</strong></div>
					<div class="lx-preview-field"><span>Total Amount</span><strong>${this.safe_text(this.format_currency(total_amount))}</strong></div>
					<div class="lx-preview-field"><span>Total Profit</span><strong>${this.safe_text(this.format_currency(total_profit))}</strong></div>
				</div>

				<div class="lx-preview-items">
					<h4>Purchase Items</h4>
					<table class="lx-ops-table">
						<thead>
							<tr>
								<th>Item</th>
								<th>Qty</th>
								<th>Rate</th>
								<th>Amount</th>
								<th>Profit</th>
							</tr>
						</thead>
						<tbody>
							${items.map((row) => `
								<tr>
									<td>${this.safe_text(row.item)}</td>
									<td>${this.format_plain_number(row.quantity)}</td>
									<td>${this.safe_text(this.format_currency(row.rate))}</td>
									<td>${this.safe_text(this.format_currency(row.amount || this.to_number(row.quantity) * this.to_number(row.rate)))}</td>
									<td>${this.safe_text(this.format_currency(row.total_profit || row.item_total_profit))}</td>
								</tr>
							`).join("")}
						</tbody>
					</table>
				</div>
			</div>
		`;
	}


	print_record(module_key, name) {
		const mod = this.modules[module_key];
		const url = `/printview?doctype=${encodeURIComponent(mod.doctype)}&name=${encodeURIComponent(name)}&trigger_print=1`;
		window.open(url, "_blank", "noopener,noreferrer");
	}

	// ============================================================
	// DIALOGS
	// ============================================================

	async show_product_dialog(name = null) {
		const is_edit = Boolean(name);
		let existing = null;

		if (is_edit) {
			existing = await frappe.db.get_doc("Ledgix Item", name);
		}

		const dialog = new frappe.ui.Dialog({
			title: is_edit ? `Edit Product: ${name}` : "Add Product",
			fields: [
				{ fieldname: "item_name", label: "Item Name", fieldtype: "Data", reqd: 1 },
				{ fieldname: "item_code", label: "Item Code", fieldtype: "Data", reqd: 1, read_only: is_edit ? 1 : 0 },
				{ fieldname: "category", label: "Category", fieldtype: "Link", options: "Ledgix Category" },
				{ fieldname: "barcode", label: "Barcode", fieldtype: "Data" },
				{ fieldname: "sku", label: "SKU", fieldtype: "Data" },
				{ fieldname: "unit", label: "Unit", fieldtype: "Select", options: "Piece\nKg\nGram\nLiter\nPack", default: "Piece" },
				{ fieldname: "tracking_type", label: "Tracking Type", fieldtype: "Select", options: "Normal\nLot Based\nSerial Based", default: "Normal" },
				{ fieldname: "cost_price", label: "Cost Price", fieldtype: "Currency", default: 0 },
				{ fieldname: "selling_price", label: "Selling Price", fieldtype: "Currency", default: 0 },
				{ fieldname: "stock_section", fieldtype: "Section Break", label: "Stock" },
				{ fieldname: "current_stock", label: "Current Stock", fieldtype: "Float", read_only: 1, depends_on: "eval:doc.__is_edit" },
				{ fieldname: "opening_stock", label: "Opening Stock", fieldtype: "Float", default: 0, depends_on: "eval:!doc.__is_edit" },
				{ fieldname: "stock_in_qty", label: "Add Stock (+)", fieldtype: "Float", default: 0, depends_on: "eval:doc.__is_edit" },
				{ fieldname: "stock_out_qty", label: "Remove Stock (-)", fieldtype: "Float", default: 0, depends_on: "eval:doc.__is_edit" },
				{
					fieldname: "serial_numbers",
					label: "Serial Numbers",
					fieldtype: "Small Text",
					depends_on: "eval:doc.__is_edit && doc.tracking_type=='Serial Based' && doc.stock_in_qty > 0",
					description: "One per line or comma-separated. Leave empty to auto-generate.",
				},
				{
					fieldname: "opening_serial_numbers",
					label: "Serial Numbers",
					fieldtype: "Small Text",
					depends_on: "eval:!doc.__is_edit && doc.tracking_type=='Serial Based' && doc.opening_stock > 0",
					description: "One per line or comma-separated. Leave empty to auto-generate.",
				},
				{ fieldname: "minimum_stock", label: "Minimum Stock", fieldtype: "Float", default: 10 },
				{ fieldname: "active", label: "Active", fieldtype: "Check", default: 1 },
			],
			primary_action_label: is_edit ? "Update Product" : "Save Product",
			primary_action: async (values) => {
				try {
					dialog.disable_primary_action();

					const stock_in_qty = this.to_number(values.stock_in_qty);
					const stock_out_qty = this.to_number(values.stock_out_qty);

					if (is_edit) {
						await frappe.db.set_value("Ledgix Item", name, {
							item_name: values.item_name,
							category: values.category,
							barcode: values.barcode,
							sku: values.sku,
							unit: values.unit,
							tracking_type: values.tracking_type || "Normal",
							cost_price: values.cost_price,
							selling_price: values.selling_price,
							minimum_stock: values.minimum_stock,
							active: values.active,
						});

						if (stock_in_qty > 0 || stock_out_qty > 0) {
							await frappe.call({
								method: "ledgix_saas.api.stock_ops.manual_stock_entry",
								args: {
									item: name,
									qty_in: stock_in_qty,
									qty_out: stock_out_qty,
									serial_numbers: values.serial_numbers,
								},
							});
						}

						frappe.show_alert({ message: "Product updated", indicator: "green" });
					} else {
						const opening = this.to_number(values.opening_stock);
						const use_serial_opening = values.tracking_type === "Serial Based" && opening > 0;
						const {
							stock_in_qty: _in,
							stock_out_qty: _out,
							serial_numbers: _serial,
							opening_serial_numbers,
							current_stock: _cs,
							__is_edit: _edit,
							...insert_values
						} = values;

						if (use_serial_opening) {
							insert_values.opening_stock = 0;
						}

						const doc = await frappe.db.insert({ doctype: "Ledgix Item", ...insert_values });

						if (use_serial_opening) {
							await frappe.call({
								method: "ledgix_saas.api.stock_ops.record_opening_stock",
								args: {
									item: doc.name,
									qty: opening,
									serial_numbers: opening_serial_numbers,
								},
							});
							await frappe.db.set_value("Ledgix Item", doc.name, "opening_stock", opening);
						}

						frappe.show_alert({ message: "Product added", indicator: "green" });
					}

					dialog.hide();
					if (!is_edit) this.state.products.page = 1;
					this.clear_selected_row("products", false);
					await this.load_static_options();
					await this.load_module("products");
				} catch (error) {
					console.error(error);
					frappe.msgprint({ title: is_edit ? "Could not update product" : "Could not save product", message: error.message || String(error), indicator: "red" });
				} finally {
					dialog.enable_primary_action();
				}
			},
		});

		if (dialog.$wrapper) dialog.$wrapper.addClass("lx-operations-dialog");

		dialog.show();

		dialog.set_value("__is_edit", is_edit ? 1 : 0);

		if (existing) {
			dialog.set_values({
				item_name: existing.item_name,
				item_code: existing.item_code,
				category: existing.category,
				barcode: existing.barcode,
				sku: existing.sku,
				unit: existing.unit || "Piece",
				tracking_type: existing.tracking_type || "Normal",
				cost_price: existing.cost_price || 0,
				selling_price: existing.selling_price || 0,
				current_stock: existing.current_stock || 0,
				minimum_stock: existing.minimum_stock || 0,
				active: existing.active ? 1 : 0,
				stock_in_qty: 0,
				stock_out_qty: 0,
				serial_numbers: "",
			});
		}
	}

	async show_category_dialog(name = null) {
		const is_edit = Boolean(name);
		let existing = null;

		if (is_edit) {
			existing = await frappe.db.get_doc("Ledgix Category", name);
		}

		const dialog = new frappe.ui.Dialog({
			title: is_edit ? `Edit Category: ${existing?.category_name || name}` : "Add Category",
			fields: [
				{ fieldname: "category_name", label: "Category Name", fieldtype: "Data", reqd: 1, read_only: is_edit ? 1 : 0 },
				{ fieldname: "description", label: "Description", fieldtype: "Small Text" },
				{ fieldname: "category_icon", label: "Category Icon", fieldtype: "Data" },
				{ fieldname: "accent_color", label: "Accent Color", fieldtype: "Color" },
				{ fieldname: "is_active", label: "Active", fieldtype: "Check", default: 1 },
				{ fieldname: "tax_section", fieldtype: "Section Break", label: "Tax Defaults", collapsible: 1, collapsed: 1 },
				{
					fieldname: "tax_defaults_enabled",
					label: "Tax Defaults Enabled",
					fieldtype: "Check",
					description: "Items in this category inherit this tax setup unless an Item Tax Profile override exists.",
				},
				{
					fieldname: "default_tax_category",
					label: "Default Tax Category",
					fieldtype: "Link",
					options: "Ledgix Tax Category",
					depends_on: "eval:doc.tax_defaults_enabled",
				},
				{ fieldname: "default_taxable", label: "Default Taxable", fieldtype: "Check", default: 1, depends_on: "eval:doc.tax_defaults_enabled" },
				{ fieldname: "default_sales_type", label: "Default Sales Type", fieldtype: "Data", depends_on: "eval:doc.tax_defaults_enabled" },
				{ fieldname: "default_uom_for_fbr", label: "Default UOM for FBR", fieldtype: "Data", depends_on: "eval:doc.tax_defaults_enabled" },
				{ fieldname: "default_scenario_id", label: "Default Scenario ID", fieldtype: "Data", depends_on: "eval:doc.tax_defaults_enabled" },
				{
					fieldname: "tax_hint",
					fieldtype: "HTML",
					options: `<p class="text-muted small">Tax rates and bulk category tools are also available in <strong>Tax Center → Category Tax</strong>.</p>`,
				},
			],
			primary_action_label: is_edit ? "Update Category" : "Save Category",
			primary_action: async (values) => {
				try {
					dialog.disable_primary_action();

					if (cint(values.tax_defaults_enabled) && !values.default_tax_category) {
						frappe.throw("Default Tax Category is required when tax defaults are enabled.");
					}

					const payload = {
						category_name: values.category_name,
						description: values.description,
						category_icon: values.category_icon,
						accent_color: values.accent_color,
						is_active: cint(values.is_active),
						tax_defaults_enabled: cint(values.tax_defaults_enabled),
						default_tax_category: values.default_tax_category,
						default_taxable: cint(values.default_taxable),
						default_sales_type: values.default_sales_type,
						default_uom_for_fbr: values.default_uom_for_fbr,
						default_scenario_id: values.default_scenario_id,
					};

					if (is_edit) {
						await frappe.db.set_value("Ledgix Category", name, payload);
						frappe.show_alert({ message: "Category updated", indicator: "green" });
					} else {
						await frappe.db.insert({ doctype: "Ledgix Category", ...payload });
						frappe.show_alert({ message: "Category added", indicator: "green" });
					}

					dialog.hide();
					if (!is_edit) this.state.categories.page = 1;
					this.clear_selected_row("categories", false);
					await this.load_static_options();
					await this.load_module("categories");
				} catch (error) {
					console.error(error);
					frappe.msgprint({
						title: is_edit ? "Could not update category" : "Could not save category",
						message: error.message || String(error),
						indicator: "red",
					});
				} finally {
					dialog.enable_primary_action();
				}
			},
		});

		if (dialog.$wrapper) dialog.$wrapper.addClass("lx-operations-dialog");

		dialog.show();

		if (existing) {
			dialog.set_values({
				category_name: existing.category_name,
				description: existing.description,
				category_icon: existing.category_icon,
				accent_color: existing.accent_color,
				is_active: existing.is_active ? 1 : 0,
				tax_defaults_enabled: existing.tax_defaults_enabled ? 1 : 0,
				default_tax_category: existing.default_tax_category,
				default_taxable: cint(existing.default_taxable) !== 0 ? 1 : 0,
				default_sales_type: existing.default_sales_type,
				default_uom_for_fbr: existing.default_uom_for_fbr,
				default_scenario_id: existing.default_scenario_id,
			});
		}
	}

	async show_purchase_dialog() {
		const purchase_meta = await this.ensure_meta("Ledgix Purchase");
		const child_field = this.get_child_table_field(purchase_meta, "Ledgix Purchase Item");

		const dialog = new frappe.ui.Dialog({
			title: "New Purchase",
			size: "extra-large",
			fields: [
				{ fieldname: "supplier", label: "Supplier", fieldtype: "Link", options: "Ledgix Supplier" },
				{ fieldname: "supplier_invoice_no", label: "Supplier Invoice No", fieldtype: "Data" },
				{ fieldname: "purchase_date", label: "Purchase Date", fieldtype: "Date", default: frappe.datetime.get_today() },
				{ fieldname: "section_items", fieldtype: "Section Break" },
				{
					fieldname: "items",
					label: "Purchase Items",
					fieldtype: "Table",
					data: [{ quantity: 1, rate: 0, amount: 0 }],
					cannot_add_rows: false,
					in_place_edit: true,
					fields: [
						{ fieldname: "item", label: "Item", fieldtype: "Link", options: "Ledgix Item", in_list_view: 1, columns: 3 },
						{ fieldname: "quantity", label: "Qty", fieldtype: "Float", in_list_view: 1, default: 1, columns: 1 },
						{
							fieldname: "serial_numbers",
							label: "Serial Numbers",
							fieldtype: "Small Text",
							in_list_view: 1,
							columns: 3,
							description: "Optional for Serial Based items. Leave empty to auto-generate. Use one serial per line or comma-separated if entering manually.",
						},
						{ fieldname: "rate", label: "Rate", fieldtype: "Currency", in_list_view: 1, default: 0, columns: 1 },
						{ fieldname: "amount", label: "Amount", fieldtype: "Currency", in_list_view: 1, read_only: 1, columns: 2 },
					],
				},
				{ fieldname: "section_options", fieldtype: "Section Break" },
				{ fieldname: "submit_after_save", label: "Submit after save", fieldtype: "Check", default: 0 },
				{ fieldname: "summary", fieldtype: "HTML", options: `<div class="lx-purchase-live-summary"><strong>Total:</strong> PKR 0.00</div>` },
			],
			primary_action_label: "Save Purchase",
			primary_action: async (values) => {
				try {
					dialog.disable_primary_action();
					const payload = await this.build_purchase_payload(values, child_field);
					let inserted = await frappe.db.insert(payload);

					if (values.submit_after_save) {
						inserted = await this.submit_doc(inserted);
					}

					frappe.show_alert({ message: values.submit_after_save ? "Purchase saved and submitted" : "Purchase saved", indicator: "green" });
					dialog.hide();
					this.state.purchases.page = 1;
					await this.load_module("purchases");
				} catch (error) {
					console.error(error);
					frappe.msgprint({ title: "Could not save purchase", message: error.message || String(error), indicator: "red" });
				} finally {
					dialog.enable_primary_action();
				}
			},
		});

		dialog.show();
		if (dialog.$wrapper) dialog.$wrapper.addClass("lx-operations-dialog lx-purchase-dialog");
		this.ensure_purchase_dialog_default_row(dialog);
		this.bind_purchase_dialog_totals(dialog);
		this.bind_purchase_dialog_tracking_fields(dialog);
	}

	ensure_purchase_dialog_default_row(dialog) {
		const field = dialog.fields_dict && dialog.fields_dict.items;
		if (!field || !field.df) return;

		const data = field.df.data || [];
		if (!data.length) {
			field.df.data = [{ quantity: 1, rate: 0, amount: 0 }];
		}

		if (field.grid && field.grid.refresh) {
			field.grid.refresh();
		}
	}

	bind_purchase_dialog_totals(dialog) {
		const update = () => {
			const field = dialog.fields_dict && dialog.fields_dict.items;
			const grid_data = field && field.df ? (field.df.data || []) : [];
			const values = dialog.get_values() || {};
			const rows = values.items || grid_data || [];
			const total = rows.reduce((sum, row) => {
				row.amount = this.to_number(row.quantity) * this.to_number(row.rate);
				return sum + row.amount;
			}, 0);
			dialog.fields_dict.summary.$wrapper.html(`<div class="lx-purchase-live-summary"><strong>Total:</strong> ${this.format_currency(total)}</div>`);
		};

		dialog.fields_dict.items.grid.wrapper.on("change keyup", "input, select, textarea", frappe.utils.debounce(update, 120));
		dialog.fields_dict.items.grid.wrapper.on("click", ".grid-add-row, .grid-remove-rows, .grid-delete-row", frappe.utils.debounce(update, 160));
		update();
	}

	bind_purchase_dialog_tracking_fields(dialog) {
		const field = dialog.fields_dict && dialog.fields_dict.items;
		if (!field || !field.grid) return;

		const grid = field.grid;
		const tracking_cache = dialog.__item_tracking_cache || (dialog.__item_tracking_cache = {});

		const get_tracking = async (item) => {
			if (!item) return "";
			if (tracking_cache[item]) return tracking_cache[item];
			const response = await frappe.db.get_value("Ledgix Item", item, "tracking_type");
			const tracking = response?.message?.tracking_type || response?.tracking_type || "Normal";
			tracking_cache[item] = tracking;
			return tracking;
		};

		const sync_row_serial_visibility = async (grid_row) => {
			if (!grid_row || !grid_row.row) return;
			const item = grid_row.doc && grid_row.doc.item;
			const tracking = await get_tracking(item);
			const show_serial = tracking === "Serial Based";
			const $row = $(grid_row.row);
			$row.toggleClass("lx-show-serial", show_serial);
			if (!show_serial && grid_row.doc) {
				grid_row.doc.serial_numbers = "";
			}
		};

		const sync_all_rows = () => {
			(grid.grid_rows || []).forEach((grid_row) => sync_row_serial_visibility(grid_row));
			this.sync_purchase_serial_column_header(grid);
		};

		grid.wrapper.on("change", '[data-fieldname="item"]', (event) => {
			const $row = $(event.target).closest(".grid-row");
			const grid_row = (grid.grid_rows || []).find((row) => row.row === $row[0]);
			sync_row_serial_visibility(grid_row);
			this.sync_purchase_serial_column_header(grid);
		});

		grid.wrapper.on("click", ".grid-add-row, .grid-remove-rows, .grid-delete-row", () => {
			window.setTimeout(sync_all_rows, 100);
		});

		if (grid.refresh && !grid.__lx_tracking_refresh_wrapped) {
			const original_refresh = grid.refresh.bind(grid);
			grid.refresh = (...args) => {
				const result = original_refresh(...args);
				window.setTimeout(sync_all_rows, 50);
				return result;
			};
			grid.__lx_tracking_refresh_wrapped = true;
		}

		window.setTimeout(sync_all_rows, 150);
	}

	sync_purchase_serial_column_header(grid) {
		if (!grid || !grid.wrapper) return;
		const has_serial_row = (grid.grid_rows || []).some((row) => $(row.row).hasClass("lx-show-serial"));
		grid.wrapper.find('.grid-heading-row [data-fieldname="serial_numbers"]').toggle(has_serial_row);
	}

	infer_movement_source(row) {
		const note = String(row.reference_note || "").trim();
		if (note.startsWith("Manual IN")) return "Manual IN";
		if (note.startsWith("Manual OUT")) return "Manual OUT";
		if (note.startsWith("Opening Stock")) return "Opening";

		const ref = String(row.reference_doctype || "").trim();
		if (ref === "Ledgix Purchase") return "Purchase";
		if (ref === "Ledgix Sale") return "Sale";
		if (ref === "Ledgix Sales Return") return "Return";
		if (this.normalize_stock_movement_type(row.movement_type) === "ADJUSTMENT") return "Adjustment";
		return "";
	}

	async build_purchase_payload(values, child_field) {
		if (!child_field) throw new Error("Could not find Ledgix Purchase Item child table field in Ledgix Purchase.");

		const parent_meta = await this.ensure_meta("Ledgix Purchase");
		const child_meta = await this.ensure_meta("Ledgix Purchase Item");
		const raw_rows = values.items || [];
		const rows = raw_rows.filter((row) => row.item || this.to_number(row.quantity) || this.to_number(row.rate) || row.serial_numbers);
		const missing = [];

		if (!values.supplier) missing.push("Supplier");
		if (!values.purchase_date) missing.push("Purchase Date");
		if (!rows.length) missing.push("At least one purchase item");

		rows.forEach((row, index) => {
			const row_no = index + 1;
			if (!row.item) missing.push(`Row ${row_no}: Item`);
			if (this.to_number(row.quantity) <= 0) missing.push(`Row ${row_no}: Qty greater than 0`);
			if (this.to_number(row.rate) <= 0) missing.push(`Row ${row_no}: Rate greater than 0`);
		});

		if (missing.length) {
			throw new Error(`Please complete: ${missing.join(", ")}.`);
		}

		const doc = { doctype: "Ledgix Purchase" };
		this.set_if_field(doc, parent_meta, "supplier", values.supplier);
		this.set_first_existing_field(doc, parent_meta, ["supplier_invoice_no", "invoice_number", "bill_no", "purchase_invoice_no"], values.supplier_invoice_no);
		this.set_first_existing_field(doc, parent_meta, ["purchase_date", "date", "posting_date"], values.purchase_date || frappe.datetime.get_today());
		doc[child_field] = rows.map((row) => {
			const amount = this.to_number(row.quantity) * this.to_number(row.rate);
			const child = {};
			this.set_if_field(child, child_meta, "item", row.item);
			this.set_first_existing_field(child, child_meta, ["quantity", "qty", "purchase_qty"], this.to_number(row.quantity));
			this.set_if_field(child, child_meta, "serial_numbers", row.serial_numbers);
			this.set_first_existing_field(child, child_meta, ["rate", "cost_price", "purchase_rate"], this.to_number(row.rate));
			this.set_first_existing_field(child, child_meta, ["amount", "total", "total_amount"], amount);
			return child;
		});

		const total_qty = rows.reduce((sum, row) => sum + this.to_number(row.quantity), 0);
		const total_amount = rows.reduce((sum, row) => sum + this.to_number(row.quantity) * this.to_number(row.rate), 0);
		this.set_first_existing_field(doc, parent_meta, ["total_qty", "total_quantity"], total_qty);
		this.set_first_existing_field(doc, parent_meta, ["total_amount", "grand_total"], total_amount);

		return doc;
	}

	get_child_table_field(meta, child_doctype) {
		const field = (meta.fields || []).find((df) => df.fieldtype === "Table" && df.options === child_doctype);
		return field && field.fieldname;
	}

	set_if_field(target, meta, fieldname, value) {
		if (!fieldname || value === undefined || value === null || value === "") return;
		if ((meta.fields || []).some((df) => df.fieldname === fieldname)) target[fieldname] = value;
	}

	set_first_existing_field(target, meta, fields, value) {
		const fieldname = fields.find((field) => (meta.fields || []).some((df) => df.fieldname === field));
		this.set_if_field(target, meta, fieldname, value);
	}

	submit_doc(doc) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method: "frappe.client.submit",
				args: { doc },
				callback: (r) => resolve(r.message),
				error: (r) => reject(r),
			});
		});
	}

	async show_open_shift_dialog() {
		const dialog = new frappe.ui.Dialog({
			title: "Open POS Shift",
			fields: [
				{ fieldname: "opening_cash", label: "Opening Cash", fieldtype: "Currency", reqd: 1, default: 0 },
				{ fieldname: "notes", label: "Notes", fieldtype: "Small Text" },
			],
			primary_action_label: "Open Shift",
			primary_action: async (values) => {
				try {
					dialog.disable_primary_action();
					await this.call_method("ledgix_saas.api.api.open_pos_shift", {
						opening_cash: values.opening_cash || 0,
						notes: values.notes || "",
					});
					frappe.show_alert({ message: "POS shift opened", indicator: "green" });
					dialog.hide();
					await this.reload_shifts_after_mutation();
				} catch (error) {
					console.error(error);
					frappe.msgprint({ title: "Could not open shift", message: error.message || String(error), indicator: "red" });
				} finally {
					dialog.enable_primary_action();
				}
			},
		});

		dialog.show();
		if (dialog.$wrapper) dialog.$wrapper.addClass("lx-operations-dialog lx-shift-open-dialog");
	}

	async show_close_shift_dialog(row = null) {
		try {
			const shift = await this.call_method("ledgix_saas.api.api.get_active_shift_info", {});

			if (!shift || !shift.has_active_shift) {
				frappe.msgprint({ title: "No active shift", message: "There is no open POS shift to close.", indicator: "orange" });
				await this.reload_shifts_after_mutation();
				return;
			}

			const shift_name = row && row.status === "Open" ? row.name : shift.shift_id;
			const expected_cash = this.to_number(shift.expected_cash);
			const cash_sales = this.to_number(shift.cash_sales);
			const non_cash_sales = this.to_number(shift.non_cash_sales);
			const total_sales = this.to_number(shift.total_sales);
			const invoice_count = this.to_number(shift.invoice_count);

			const dialog = new frappe.ui.Dialog({
				title: "Close POS Shift",
				size: "large",
				fields: [
					{ fieldname: "shift_id", label: "Shift ID", fieldtype: "Data", read_only: 1, default: shift_name },
					{ fieldname: "summary_html", fieldtype: "HTML", options: this.shift_close_summary_html({ expected_cash, cash_sales, non_cash_sales, total_sales, invoice_count, actual_cash: expected_cash }) },
					{ fieldname: "expected_cash", label: "Expected Cash", fieldtype: "Currency", read_only: 1, default: expected_cash },
					{ fieldname: "actual_cash", label: "Actual Cash Counted", fieldtype: "Currency", default: expected_cash },
					{ fieldname: "closing_notes", label: "Closing Notes", fieldtype: "Small Text" },
				],
				primary_action_label: "Close Shift",
				primary_action: async (values) => {
					try {
						const actual_cash = this.to_number(values.actual_cash);
						if (values.actual_cash === null || values.actual_cash === undefined || values.actual_cash === "") {
							throw new Error("Enter actual cash before closing the shift.");
						}

						dialog.disable_primary_action();
						await this.call_method("ledgix_saas.api.api.close_pos_shift", {
							actual_cash,
							closing_notes: values.closing_notes || "",
							shift_name,
						});
						frappe.show_alert({ message: "POS shift closed. Submit it from Actions after review.", indicator: "green" });
						dialog.hide();
						await this.reload_shifts_after_mutation();
					} catch (error) {
						console.error(error);
						frappe.msgprint({ title: "Could not close shift", message: error.message || String(error), indicator: "red" });
					} finally {
						dialog.enable_primary_action();
					}
				},
			});

			dialog.show();
			if (dialog.$wrapper) dialog.$wrapper.addClass("lx-operations-dialog lx-shift-close-dialog");

			const update_summary = () => {
				const actual_cash = this.to_number(dialog.get_value("actual_cash"));
				dialog.fields_dict.summary_html.$wrapper.html(this.shift_close_summary_html({
					expected_cash,
					cash_sales,
					non_cash_sales,
					total_sales,
					invoice_count,
					actual_cash,
				}));
			};

			dialog.fields_dict.actual_cash.$input.on("input change", frappe.utils.debounce(update_summary, 80));
			update_summary();
		} catch (error) {
			console.error(error);
			frappe.msgprint({ title: "Could not load active shift", message: error.message || String(error), indicator: "red" });
		}
	}

	shift_close_summary_html(values) {
		const variance = this.to_number(values.actual_cash) - this.to_number(values.expected_cash);
		const variance_class = variance === 0 ? "is-balanced" : (variance > 0 ? "is-over" : "is-short");
		return `
			<div class="lx-shift-close-summary">
				<div class="lx-shift-close-card"><span>Cash Sales</span><strong>${this.format_currency(values.cash_sales)}</strong></div>
				<div class="lx-shift-close-card"><span>Non-Cash Sales</span><strong>${this.format_currency(values.non_cash_sales)}</strong></div>
				<div class="lx-shift-close-card"><span>Total Sales</span><strong>${this.format_currency(values.total_sales)}</strong></div>
				<div class="lx-shift-close-card"><span>Invoices</span><strong>${this.format_number(values.invoice_count)}</strong></div>
				<div class="lx-shift-close-card is-expected"><span>Expected Cash</span><strong>${this.format_currency(values.expected_cash)}</strong></div>
				<div class="lx-shift-close-card ${variance_class}"><span>Live Variance</span><strong>${this.format_currency(variance)}</strong></div>
			</div>
		`;
	}

	async reload_shifts_after_mutation() {
		this.clear_selected_row("shifts", false);
		if (this.active_module === "shifts") {
			await this.load_module("shifts");
		} else if (this.state.shifts) {
			this.state.shifts.page = 1;
			this.state.shifts.rows = [];
			this.state.shifts.total = 0;
			this.state.shifts.loaded_total = 0;
		}
	}

	show_theme_dialog() {
		const current = this.normalize_theme_hex(this.boot.theme_settings && this.boot.theme_settings.primary_accent_color) || "#0f766e";
		const dialog = new frappe.ui.Dialog({
			title: "Ledgix Theme Accent",
			fields: [
				{
					fieldname: "intro",
					fieldtype: "HTML",
					options: `<div class="lx-dialog-note"><strong>Theme changes use Ledgix POS Theme Settings.</strong><br>This updates the shared accent token used by POS, Dashboard and Operations UI.</div>`,
				},
				{ fieldname: "primary_accent_color", label: "Accent Color", fieldtype: "Color", default: current, reqd: 1 },
			],
			primary_action_label: "Apply Theme",
				primary_action: async (values) => {
					try {
						if (!window.LedgixTheme?.save) {
							frappe.msgprint({ title: "Theme service unavailable", message: "Please use Ledgix POS Theme Settings.", indicator: "red" });
							return;
						}

						dialog.disable_primary_action();
						this.boot.theme_settings = await window.LedgixTheme.save({
							primary_accent_color: values.primary_accent_color
						});
						this.apply_theme_variables(this.boot.theme_settings);
						frappe.show_alert({ message: "Theme applied", indicator: "green" });
						dialog.hide();
				} catch (error) {
					console.error(error);
					frappe.msgprint({ title: "Could not save theme", message: error.message || String(error), indicator: "red" });
				} finally {
					dialog.enable_primary_action();
				}
			},
		});

		dialog.show();
	}

	// ============================================================
	// META / API HELPERS
	// ============================================================

	call_method(method, args = {}) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method,
				args,
				callback: (r) => resolve(r.message),
				error: (r) => reject(r),
			});
		});
	}

	async ensure_meta(doctype) {
		if (this.meta_cache[doctype]) return this.meta_cache[doctype];

		await frappe.model.with_doctype(doctype);
		const meta = frappe.get_meta(doctype);
		this.meta_cache[doctype] = meta;
		return meta;
	}

	has_field(doctype, fieldname) {
		if (["name", "owner", "creation", "modified", "docstatus"].includes(fieldname)) return true;
		const meta = this.meta_cache[doctype] || frappe.get_meta(doctype);
		return Boolean((meta.fields || []).find((field) => field.fieldname === fieldname));
	}

	get_safe_fields(doctype, fields) {
		const unique = [...new Set(fields.filter(Boolean))];
		return unique.filter((fieldname) => this.has_field(doctype, fieldname));
	}

	get_safe_order_by(doctype, order_by) {
		const fieldname = String(order_by || "modified desc").split(" ")[0];
		return this.has_field(doctype, fieldname) ? order_by : "modified desc";
	}

	async safe_get_list(doctype, fields, filters, order_by, limit) {
		try {
			await this.ensure_meta(doctype);
			return await frappe.db.get_list(doctype, {
				fields: this.get_safe_fields(doctype, fields),
				filters,
				order_by,
				limit_page_length: limit || 50,
			});
		} catch (e) {
			console.warn(`Could not load ${doctype}`, e);
			return [];
		}
	}

	// ============================================================
	// FORMATTERS
	// ============================================================

	format_docstatus(row) {
		const map = { 0: "Draft", 1: "Submitted", 2: "Cancelled" };
		return map[row.docstatus] || row.status || "Draft";
	}

	format_currency(value) {
		const number = this.to_number(value);
		const formatted = new Intl.NumberFormat(undefined, {
			minimumFractionDigits: 2,
			maximumFractionDigits: 2,
		}).format(number);
		return `PKR ${formatted}`;
	}

	format_number(value) {
		if (value === null || value === undefined || value === "") return "—";

		const number = this.to_number(value);
		return new Intl.NumberFormat(undefined, {
			minimumFractionDigits: 0,
			maximumFractionDigits: 2,
		}).format(number);
	}

	format_plain_number(value) {
	if (value === null || value === undefined || value === "") return "—";

	const number = this.to_number(value);
		return new Intl.NumberFormat(undefined, {
			minimumFractionDigits: 0,
			maximumFractionDigits: 2,
		}).format(number);
	}


	format_date(value) {
		if (!value) return "—";
		return frappe.datetime.str_to_user(value);
	}

	format_datetime(value) {
		if (!value) return "—";
		return frappe.datetime.str_to_user(value);
	}

	badge_html(value) {
		return `<span class="lx-badge">${this.safe_text(value)}</span>`;
	}

	status_html(value) {
		const status = this.normalize_status_label(value || "—");
		const slug = String(status).toLowerCase().replace(/[^a-z0-9]+/g, "-");
		return `<span class="lx-status lx-status-${this.safe_attr(slug)}">${this.safe_text(status)}</span>`;
	}

	normalize_status_label(value) {
		const normalized = this.normalize_stock_movement_type(value);
		return normalized || value;
	}

	normalize_stock_movement_type(value) {
		const key = String(value || "").trim().toUpperCase().replace(/[\s-]+/g, "_");
		const map = {
			IN: "IN",
			OUT: "OUT",
			ADJUSTMENT: "ADJUSTMENT",
			ADJUST: "ADJUSTMENT",
		};
		return map[key] || value;
	}

	safe_text(value) {
		if (value === null || value === undefined || value === "") return "—";
		return frappe.utils.escape_html(String(value));
	}

	safe_attr(value) {
		if (value === null || value === undefined) return "";
		return frappe.utils.escape_html(String(value));
	}

	get_total_categories(rows) {
		const master_categories = this.option_cache.categories || [];
		if (master_categories.length) return master_categories.length;

		return new Set((rows || []).map((row) => row.category).filter(Boolean)).size;
	}

	icon_svg(name) {
		const icons = {
			eye: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"></path><circle cx="12" cy="12" r="3"></circle></svg>',
			analytics: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19V9"></path><path d="M10 19V5"></path><path d="M16 19v-7"></path><path d="M22 19V3"></path></svg>',
			cube: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21 16-9 5-9-5V8l9-5 9 5v8z"></path><path d="m3.3 7.7 8.7 5 8.7-5"></path><path d="M12 22V12"></path></svg>',
			tag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.6 13.3 13.3 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.5a2 2 0 0 1 0 2.8z"></path><circle cx="7.5" cy="7.5" r=".8"></circle></svg>',
			warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"></path><path d="M12 9v4"></path><path d="M12 17h.01"></path></svg>',
			"x-circle": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="m15 9-6 6"></path><path d="m9 9 6 6"></path></svg>',

			search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"></circle><path d="m21 21-4.3-4.3"></path></svg>',
			refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 1-15.5 6.2"></path><path d="M3 12A9 9 0 0 1 18.5 5.8"></path><path d="M3 19v-5h5"></path><path d="M21 5v5h-5"></path></svg>',
			theme: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.9 4.9 1.4 1.4"></path><path d="m17.7 17.7 1.4 1.4"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m4.9 19.1 1.4-1.4"></path><path d="m17.7 6.3 1.4-1.4"></path></svg>',
			palette: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22a10 10 0 1 1 10-10c0 1.7-1 3-2.7 3h-1.5a1.8 1.8 0 0 0-1.8 1.8v.7A4.5 4.5 0 0 1 11.5 22H12Z"></path><circle cx="7.5" cy="10" r=".8"></circle><circle cx="10" cy="6.8" r=".8"></circle><circle cx="14" cy="6.8" r=".8"></circle><circle cx="16.5" cy="10" r=".8"></circle></svg>',
			eraser: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 21-4-4L14 6a2.8 2.8 0 0 1 4 0l1 1a2.8 2.8 0 0 1 0 4L9 21H7Z"></path><path d="M12 8l4 4"></path><path d="M3 21h18"></path></svg>',
			"filter-x": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.05" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4h18l-7 8v5l-4 2v-7L3 4Z"></path><path d="m16.5 16.5 4 4"></path><path d="m20.5 16.5-4 4"></path></svg>',
			plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"></path><path d="M5 12h14"></path></svg>',
			calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 2v4"></path><path d="M16 2v4"></path><rect x="3" y="5" width="18" height="16" rx="3"></rect><path d="M3 10h18"></path></svg>',
			package: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21 8-9-5-9 5 9 5 9-5Z"></path><path d="M3 8v8l9 5 9-5V8"></path><path d="M12 13v8"></path></svg>',
			bill: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"></path><path d="M9 8h6"></path><path d="M9 12h6"></path><path d="M9 16h3"></path></svg>',
			"sales-trend": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7" cy="17" r="3"></circle><path d="M11 16 21 6"></path><path d="M15 6h6v6"></path><path d="M3 7h7"></path></svg>',
			return: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 14 4 9l5-5"></path><path d="M4 9h11a5 5 0 0 1 0 10H9"></path></svg>',
			refund: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10h18"></path><path d="M7 15h3"></path><rect x="3" y="6" width="18" height="12" rx="3"></rect><path d="m8 4-4 4 4 4"></path></svg>',
			warehouse: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21V8l9-5 9 5v13"></path><path d="M7 21v-8h10v8"></path><path d="M9 17h6"></path><path d="M9 13h6"></path></svg>',
			database: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="8" ry="3"></ellipse><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5"></path><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"></path></svg>',
			wallet: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h15a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h13"></path><path d="M16 13h.01"></path></svg>',
			check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m20 6-11 11-5-5"></path></svg>',
			edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"></path></svg>',
			coin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"></circle><path d="M12 8v8"></path><path d="M9.5 10.5c0-1.4 5-1.4 5 0 0 2-5 1-5 3 0 1.4 5 1.4 5 0"></path></svg>',
			"trend-up": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17 9 11l4 4 8-8"></path><path d="M14 7h7v7"></path></svg>',
			receipt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12v18l-2-1-2 1-2-1-2 1-2-1-2 1V3Z"></path><path d="M9 8h6"></path><path d="M9 12h6"></path><path d="M9 16h4"></path></svg>',
			"arrow-down": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"></path><path d="m19 12-7 7-7-7"></path></svg>',
			"arrow-up": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"></path><path d="m5 12 7-7 7 7"></path></svg>',
			sliders: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 21v-7"></path><path d="M4 10V3"></path><path d="M12 21v-9"></path><path d="M12 8V3"></path><path d="M20 21v-5"></path><path d="M20 12V3"></path><path d="M2 14h4"></path><path d="M10 8h4"></path><path d="M18 16h4"></path></svg>',
			printer: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9V3h12v6"></path><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><path d="M6 14h12v7H6z"></path><path d="M8 17h8"></path></svg>',
			"chevron-down": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"></path></svg>',
			layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 2 9 5-9 5-9-5 9-5z"></path><path d="m3 12 9 5 9-5"></path><path d="m3 17 9 5 9-5"></path></svg>',
		};

		return icons[name] || icons.cube;
	}

	first_value(row, keys, prefer_date = false) {
		for (const key of keys) {
			if (row[key] !== null && row[key] !== undefined && row[key] !== "") {
				return prefer_date ? this.format_date(row[key]) : row[key];
			}
		}
		return "—";
	}

	join_values(values) {
		const clean = values.filter((value) => value !== null && value !== undefined && value !== "");
		return clean.length ? clean.join(" / ") : "—";
	}

	to_number(value) {
		const number = Number(value || 0);
		return Number.isFinite(number) ? number : 0;
	}

	// ============================================================
	// EMPTY / ERROR STATES
	// ============================================================

	loading_html() {
		return `<div class="lx-table-state is-loading"><div class="lx-loader"></div><strong>Loading records...</strong><p>Please wait while Ledgix fetches operational data.</p></div>`;
	}

	empty_html(label, module_key) {
		let helper = "Try clearing filters or add a new record.";
		if (this.is_billing_mode() && ["purchases", "stock"].includes(module_key)) {
			helper = "Billing Only mode hides stock-connected workflows here. Switch to Strict Inventory mode to manage this module.";
		}
		return `<div class="lx-table-state"><strong>No ${this.safe_text(label)} found</strong><p>${this.safe_text(helper)}</p></div>`;
	}

	render_error(module_key, error) {
		this.$root.find(".lx-table-wrap").html(`
			<div class="lx-table-state is-error">
				<strong>Could not load ${this.safe_text(this.modules[module_key].label)}</strong>
				<p>${this.safe_text(error.message || String(error))}</p>
			</div>
		`);
	}
}

