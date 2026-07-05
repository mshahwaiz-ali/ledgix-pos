/* global frappe */

frappe.pages["ledgix-tax-center"].on_page_load = function (wrapper) {
	frappe.ledgix_tax_center = new LedgixTaxCenter(wrapper);
};

class LedgixTaxCenter {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({ parent: wrapper, title: "", single_column: true });
		this.page.set_title("");
		this.method_paths = {
			boot: "ledgix_saas.api.tax_center.get_tax_center_boot",
			profile: "ledgix_saas.api.tax_center.get_tax_profile_settings",
			save_profile: "ledgix_saas.api.tax_center.save_tax_profile_settings",
			preview: "ledgix_saas.api.tax_center.preview_tax_calculation",
			categories: "ledgix_saas.api.tax_center.get_tax_categories",
			save_category: "ledgix_saas.api.tax_center.save_tax_category",
			toggle_category: "ledgix_saas.api.tax_center.toggle_tax_category",
			rates: "ledgix_saas.api.tax_center.get_tax_rates",
			save_rate: "ledgix_saas.api.tax_center.save_tax_rate",
			close_rate: "ledgix_saas.api.tax_center.close_tax_rate",
			mappings: "ledgix_saas.api.tax_center.get_item_tax_mappings",
			category_tax: "ledgix_saas.api.tax_center.get_category_tax_mappings",
			save_category_tax: "ledgix_saas.api.tax_center.save_category_tax_defaults",
			apply_category_tax: "ledgix_saas.api.tax_center.apply_category_tax_to_items",
			preview_item_tax: "ledgix_saas.api.tax_center.preview_item_effective_tax",
			save_mapping: "ledgix_saas.api.tax_center.save_item_tax_mapping",
			mark_reviewed: "ledgix_saas.api.tax_center.mark_item_tax_reviewed",
			toggle_mapping: "ledgix_saas.api.tax_center.toggle_item_tax_mapping",
			invoices: "ledgix_saas.api.tax_center.get_invoice_tax_snapshots",
			returns: "ledgix_saas.api.tax_center.get_return_tax_snapshots",
			fbr: "ledgix_saas.api.tax_center.get_fbr_readiness",
			fbr_settings: "ledgix_saas.api.fbr_settings.get_fbr_settings",
			fbr_control_state: "ledgix_saas.api.fbr_settings.get_fbr_control_state",
			save_fbr_settings: "ledgix_saas.api.fbr_settings.save_fbr_settings",
			fbr_sale_preview: "ledgix_saas.api.fbr_preview.get_fbr_sale_preview",
			fbr_validate_sale: "ledgix_saas.api.fbr_submission.validate_sale_with_fbr",
			fbr_validate_sale_production: "ledgix_saas.api.fbr_submission.validate_sale_with_fbr_production",
			fbr_submit_sale: "ledgix_saas.api.fbr_submission.submit_sale_to_fbr",
			fbr_logs: "ledgix_saas.api.tax_center.get_fbr_submission_logs",
		};
		this.advanced_modules = new Set(["categories", "rates"]);
		this.modules = [
			{ key: "setup", slug: "setup", label: "Tax Setup" },
			{ key: "category_tax", slug: "category-tax", label: "Category Tax" },
			{ key: "item_mapping", slug: "item-mapping", label: "Item Mapping" },
			{ key: "invoice_snapshots", slug: "invoice-snapshots", label: "Invoice Snapshots" },
			{ key: "return_snapshots", slug: "return-snapshots", label: "Return Snapshots" },
			{ key: "fbr_control", slug: "fbr-control", label: "FBR Control" },
			{ key: "fbr_logs", slug: "fbr-logs", label: "FBR Logs" },
			{ key: "categories", slug: "categories", label: "Categories", group: "Advanced Tax Setup" },
			{ key: "rates", slug: "rates", label: "Rates", group: "Advanced Tax Setup" },
		];
		this.module_by_slug = Object.fromEntries(this.modules.map((module) => [module.slug, module.key]));
		this.module_by_slug["fbr-readiness"] = "fbr_control";
		this.state = {
			active_module: this.get_initial_module(),
			page_size: 15,
			load_request_id: 0,
			boot: {},
			profile: {},
			rows: {},
			timers: {},
			fbr: null,
			fbr_control: {
				settings: null,
				control_state: null,
				selected_sale: "",
				preview: null,
				validation_result: null,
				loading: false,
				saving: false,
				preview_loading: false,
				validate_loading: false,
				production_validate_loading: false,
				submit_loading: false,
			},
		};
		this.modules.forEach((module) => {
			this.state.rows[module.key] = {
				page: 1,
				search: "",
				filters: {},
				rows: [],
				total: 0,
				summary: {},
				selected_row: null,
				loading: false,
			};
		});
		this.prepare_page();
		this.make_shell();
		this.bind_events();
		this.mount_navigator();
		this.bootstrap();
	}

	prepare_page() {
		const $page_container = $(this.wrapper).closest(".page-container");
		$page_container.addClass("ledgix-page-no-frappe-head ledgix-tax-center-container");
		$page_container.find(".page-head, .page-head-content, .page-title, .title-area, .page-actions").hide();
		this.page.clear_actions_menu();
	}

	get_initial_module() {
		const params = new URLSearchParams(window.location.search || "");
		const from_url = this.module_by_slug[params.get("module") || ""];
		if (from_url) {
			localStorage.setItem("ledgix_tax_center_active_module", from_url);
			return from_url;
		}
		const saved = localStorage.getItem("ledgix_tax_center_active_module");
		return this.modules.some((module) => module.key === saved) ? saved : "setup";
	}

	make_shell() {
		this.$root = $(this.page.body).empty();
		this.$root.html(`
			<div class="ledgix-tax-center-page">
			<div class="lx-tax-shell">
				<section class="lx-tax-hero"></section>
				<section class="lx-tax-status-grid"></section>
				<section class="lx-tax-tabs"></section>
				<section class="lx-tax-workspace">
					<main class="lx-tax-main-panel"></main>
					<aside class="lx-tax-side-panel"></aside>
				</section>
			</div>
			</div>
		`);
		this.render_static_shell();
	}

	mount_navigator(retry = 0) {
		const $content = this.$root.find(".ledgix-tax-center-page").first();
		if ($content.closest(".ledgix-app-shell").length) return;
		if (!window.LedgixNavigator?.mount) {
			if (retry < 6) window.setTimeout(() => this.mount_navigator(retry + 1), 120);
			return;
		}
		window.LedgixNavigator.mount({
			page: this.page,
			wrapper: this.wrapper,
			content: $content,
			active: "tax_center",
		});
	}

	render_static_shell() {
		this.render_hero();
		this.render_tabs();
		this.render_status_cards();
		this.render_module();
	}

	render_hero() {
		const profile = this.state.profile || {};
		const pricing = cint(profile.price_includes_tax) ? "Inclusive" : "Exclusive";
		this.$root.find(".lx-tax-hero").html(`
			<div class="lx-tax-hero-copy">
				<div class="lx-tax-eyebrow">LEDGIX COMPLIANCE</div>
				<h1>Tax &amp; Compliance Center</h1>
				<p>Smart tax setup, item mapping, historical rates, and audit-safe invoice tax snapshots.</p>
			</div>
			<div class="lx-tax-hero-actions">
				<span class="lx-tax-badge">Tax Engine</span>
				<span class="lx-tax-badge">FBR Readiness</span>
				<span class="lx-tax-badge lx-tax-badge-strong">${this.escape(pricing)}</span>
				<button class="lx-tax-button lx-tax-button-soft lx-tax-icon-button" data-action="refresh" aria-label="Refresh Tax Center" title="Refresh Tax Center">${this.refresh_icon_svg()}</button>
			</div>
		`);
	}

	render_status_cards() {
		const boot = this.state.boot || {};
		const profile = this.state.profile || {};
		const counts = boot.counts || {};
		const fbr_control = boot.fbr_control_state || {};
		const cards = [
			["Tax Enabled", cint(profile.tax_enabled) ? "Enabled" : "Disabled", "Master tax engine switch"],
			["Pricing Mode", cint(profile.price_includes_tax) ? "Inclusive" : "Exclusive", "Customer price treatment"],
			["Default Category", profile.default_tax_category || "Not Set", "Fallback category"],
			["Items Need Review", counts.items_need_review || 0, "Active item mappings"],
			["FBR Control", fbr_control.reason || fbr_control.mode || "Disabled", "From FBR Settings"],
		];
		this.$root.find(".lx-tax-status-grid").html(cards.map(([label, value, hint]) => `
			<div class="lx-tax-status-card">
				<span>${this.escape(label)}</span>
				<strong>${this.escape(value)}</strong>
				<small>${this.escape(hint)}</small>
			</div>
		`).join(""));
	}

	render_tabs() {
		const primary_modules = this.modules.filter((module) => !module.group);
		const advanced_modules = this.modules.filter((module) => module.group);
		const button_html = (module) => `
			<button class="lx-tax-tab ${module.key === this.state.active_module ? "active" : ""}" data-module="${module.key}">
				${this.escape(module.label)}
			</button>
		`;
		this.$root.find(".lx-tax-tabs").html(`
			<div class="lx-tax-tab-group">${primary_modules.map(button_html).join("")}</div>
			<div class="lx-tax-tab-group lx-tax-tab-group-advanced">
				<span>Advanced Tax Setup</span>
				${advanced_modules.map(button_html).join("")}
			</div>
		`);
	}

	bind_events() {
		this.$root.on("click", "[data-action='refresh']", () => this.bootstrap(true));
		this.$root.on("click", ".lx-tax-tab", (event) => this.switch_module($(event.currentTarget).data("module")));
		this.$root.on("input", "[data-tax-search]", (event) => this.on_search(event));
		this.$root.on("click", "[data-clear-search]", (event) => this.clear_search(event));
		this.$root.on("change", "[data-tax-filter]", (event) => this.on_filter(event));
		this.$root.on("click", "[data-open-date-range]", (event) => this.show_date_range_dialog($(event.currentTarget).data("module")));
		this.$root.on("click", "[data-page-dir]", (event) => this.change_page($(event.currentTarget).data("page-dir")));
		this.$root.on("click", "[data-row-index]", (event) => this.select_row(event));
		this.$root.on("click", ".lx-tax-row-action", (event) => event.stopPropagation());
		this.$root.on("click", "[data-open-profile]", () => this.show_profile_dialog());
		this.$root.on("click", "[data-preview-tax]", () => this.show_preview_dialog());
		this.$root.on("click", "[data-add-category]", () => this.show_category_dialog());
		this.$root.on("click", "[data-edit-category]", (event) => this.show_category_dialog(this.get_row(event)));
		this.$root.on("click", "[data-toggle-category]", (event) => this.toggle_category(this.get_row(event)));
		this.$root.on("click", "[data-add-rate]", () => this.show_rate_dialog());
		this.$root.on("click", "[data-edit-rate]", (event) => this.show_rate_dialog(this.get_row(event)));
		this.$root.on("click", "[data-close-rate]", (event) => this.show_close_rate_dialog(this.get_row(event)));
		this.$root.on("click", "[data-add-mapping]", () => this.show_mapping_dialog());
		this.$root.on("click", "[data-add-category-tax]", () => this.show_category_tax_dialog());
		this.$root.on("click", "[data-edit-category-tax]", (event) => this.show_category_tax_dialog(this.get_row(event)));
		this.$root.on("click", "[data-apply-category-tax]", (event) => this.apply_category_tax(this.get_row(event)));
		this.$root.on("click", "[data-edit-mapping]", (event) => this.show_mapping_dialog(this.get_row(event)));
		this.$root.on("click", "[data-mark-reviewed]", (event) => this.mark_reviewed(this.get_row(event)));
		this.$root.on("click", "[data-toggle-mapping]", (event) => this.toggle_mapping(this.get_row(event)));
		this.$root.on("click", "[data-view-sale]", (event) => this.show_sale_snapshot_dialog(this.get_row(event)));
		this.$root.on("click", "[data-view-return]", (event) => this.show_return_snapshot_dialog(this.get_row(event)));
		this.$root.on("click", "[data-view-fbr-log]", (event) => this.show_fbr_log_dialog(this.get_row(event)));
		this.$root.on("click", "[data-export]", (event) => this.export_csv($(event.currentTarget).data("export")));
		this.$root.on("click", "[data-fbr-refresh]", () => this.load_module("fbr_control", true));
		this.$root.on("click", "[data-edit-fbr-settings]", () => this.show_fbr_settings_dialog());
		this.$root.on("click", "[data-preview-fbr-payload]", () => this.preview_fbr_payload());
		this.$root.on("click", "[data-validate-fbr-sandbox]", () => this.validate_fbr_sandbox());
		this.$root.on("click", "[data-validate-fbr-production]", () => this.validate_fbr_production());
		this.$root.on("click", "[data-submit-fbr-production]", () => this.submit_fbr_production());
		this.$root.on("click", "[data-copy-fbr-payload]", () => this.copy_fbr_payload());
		this.$root.on("input", "[data-fbr-sale-input]", (event) => {
			this.state.fbr_control.selected_sale = event.currentTarget.value || "";
			this.state.fbr_control.preview = null;
			this.state.fbr_control.validation_result = null;
		});
	}

	async bootstrap(force_active_reload = false) {
		try {
			const boot = await this.call(this.method_paths.boot);
			this.state.boot = boot || {};
			this.state.profile = this.state.boot.profile || {};
			this.render_hero();
			this.render_status_cards();
			await this.load_module(this.state.active_module, force_active_reload);
		} catch (error) {
			this.show_error("Tax Center could not load. Check your role permissions and try again.", error);
			this.$root.find(".lx-tax-main-panel").html(this.empty_html("Access unavailable", "You do not have permission to access this center, or the API could not load."));
		}
	}

	switch_module(module) {
		if (!this.modules.some((item) => item.key === module)) return;
		this.state.active_module = module;
		localStorage.setItem("ledgix_tax_center_active_module", module);
		const slug = this.modules.find((item) => item.key === module).slug;
		window.history.replaceState({}, "", `/app/ledgix-tax-center?module=${slug}`);
		window.LedgixNavigator?.updateActiveState?.();
		this.render_tabs();
		this.render_module();
		this.load_module(module);
	}

	render_module() {
		const module = this.state.active_module;
		if (module === "setup") this.render_setup();
		if (module === "category_tax") this.render_category_tax();
		if (module === "categories") this.render_categories();
		if (module === "rates") this.render_rates();
		if (module === "item_mapping") this.render_mappings();
		if (module === "invoice_snapshots") this.render_invoices();
		if (module === "return_snapshots") this.render_returns();
		if (module === "fbr_control") this.render_fbr_control();
		if (module === "fbr_logs") this.render_fbr_logs();
		this.render_side_panel();
	}

	async load_module(module = this.state.active_module, force_focus = false) {
		const focus_state = this.capture_focus_state(module, force_focus);
		const request_id = ++this.state.load_request_id;
		if (module === "setup") {
			this.state.profile = await this.call(this.method_paths.profile);
			if (request_id !== this.state.load_request_id || module !== this.state.active_module) return;
			this.render_hero();
			this.render_status_cards();
			this.render_setup();
			return;
		}
		if (module === "fbr_control") {
			const state = this.state.fbr_control;
			state.loading = true;
			this.render_fbr_control();
			try {
				const [settings, control_state, readiness_data] = await Promise.all([
					this.call(this.method_paths.fbr_settings),
					this.call(this.method_paths.fbr_control_state),
					this.call(this.method_paths.fbr),
				]);
				if (request_id !== this.state.load_request_id || module !== this.state.active_module) return;
				state.settings = settings || {};
				state.control_state = control_state || {};
				this.state.fbr = readiness_data || {};
			} catch (error) {
				if (request_id !== this.state.load_request_id || module !== this.state.active_module) return;
				this.show_error("Could not load FBR Control settings.", error);
			} finally {
				if (request_id !== this.state.load_request_id || module !== this.state.active_module) return;
				state.loading = false;
				this.render_fbr_control();
			}
			return;
		}
		const conf = this.module_request(module);
		if (!conf) return;
		const state = this.module_state(module);
		state.loading = true;
		this.render_module();
		this.restore_focus_state(focus_state);
		try {
			const response = await this.call(conf.method, conf.args(state));
			if (request_id !== this.state.load_request_id || module !== this.state.active_module) return;
			state.rows = response.rows || [];
			state.total = response.total || 0;
			state.page = response.page || state.page;
			state.summary = response.summary || {};
		} catch (error) {
			if (request_id !== this.state.load_request_id || module !== this.state.active_module) return;
			this.show_error("Could not load module data.", error);
		} finally {
			if (request_id !== this.state.load_request_id || module !== this.state.active_module) return;
			state.loading = false;
			this.render_module();
			this.restore_focus_state(focus_state);
		}
	}

	module_request(module) {
		const page_args = (state) => ({ page: state.page, page_size: this.state.page_size, search: state.search || "", ...state.filters });
		return {
			category_tax: { method: this.method_paths.category_tax, args: page_args },
			categories: { method: this.method_paths.categories, args: page_args },
			rates: { method: this.method_paths.rates, args: page_args },
			item_mapping: { method: this.method_paths.mappings, args: page_args },
			invoice_snapshots: { method: this.method_paths.invoices, args: page_args },
			return_snapshots: { method: this.method_paths.returns, args: page_args },
			fbr_logs: { method: this.method_paths.fbr_logs, args: page_args },
		}[module];
	}

	module_state(module = this.state.active_module) {
		return this.state.rows[module];
	}

	capture_focus_state(module, force_focus = false) {
		const active = document.activeElement;
		if (!active?.matches?.("[data-tax-search]")) return force_focus ? { module, selector: `[data-tax-search][data-module="${module}"]`, start: null, end: null } : null;
		if ($(active).data("module") !== module) return null;
		return {
			module,
			selector: `[data-tax-search][data-module="${module}"]`,
			start: active.selectionStart,
			end: active.selectionEnd,
		};
	}

	restore_focus_state(focus_state) {
		if (!focus_state) return;
		window.setTimeout(() => {
			const input = this.$root.find(focus_state.selector).get(0);
			if (!input) return;
			const length = input.value.length;
			const start = focus_state.start == null ? length : Math.min(focus_state.start, length);
			const end = focus_state.end == null ? start : Math.min(focus_state.end, length);
			input.focus({ preventScroll: true });
			if (input.setSelectionRange) input.setSelectionRange(start, end);
		}, 0);
	}

	render_setup() {
		const profile = this.state.profile || {};
		const can_edit = this.can("can_edit_setup");
		const groups = [
			["Business Identity / Receipt Identity", [["Business Name", profile.business_name], ["NTN", profile.ntn], ["STRN", profile.strn__sales_tax_registration_number], ["Province", profile.province], ["Business Type", profile.business_type], ["Branch / Outlet Name", profile.branch__outlet_name], ["Outlet Address", profile.outlet_address], ["POS Registration", profile.pos_registration_number]]],
			["Tax Behavior", [["Tax Enabled", this.yesno(profile.tax_enabled)], ["Price Includes Tax", this.yesno(profile.price_includes_tax)], ["Default Tax Category", profile.default_tax_category], ["Receipt Tax Display", this.yesno(profile.receipt_tax_display_enabled)]]],
			["Defaults", [["Default Sales Type", profile.default_sales_type], ["Default Buyer Type", profile.default_buyer_type]]],
		];
		this.$root.find(".lx-tax-main-panel").html(`
			${this.module_head("Tax Setup", "Single-source tax profile settings for Ledgix tax behavior.", `
				${can_edit ? `<button class="lx-tax-button lx-tax-button-primary" data-open-profile>Edit Tax Settings</button>` : ""}
				<button class="lx-tax-button lx-tax-button-soft" data-preview-tax>Preview Tax Calculation</button>
			`)}
			<div class="lx-tax-settings-grid">
				${groups.map(([title, rows]) => `
					<div class="lx-tax-setting-card">
						<h3>${this.escape(title)}</h3>
						${rows.map(([label, value]) => `<div class="lx-tax-kv"><span>${this.escape(label)}</span><strong>${this.escape(value || "Not Set")}</strong></div>`).join("")}
					</div>
				`).join("")}
			</div>
		`);
		this.render_side_panel();
	}

	render_categories() {
		const state = this.module_state("categories");
		this.$root.find(".lx-tax-main-panel").html(`
			${this.module_head("Tax Categories", "Maintain active tax category masters without deleting historical identity.", this.can("can_edit_masters") ? `<button class="lx-tax-button lx-tax-button-primary" data-add-category>Add Category</button>` : "")}
			${this.toolbar("categories", [
				["status", "Status", ["All", "Active", "Inactive"]],
				["tax_type", "Type", ["All", "Sales Tax", "Further Tax", "FED", "Other"]],
			])}
			${this.table_html(state, ["Category", "Type", "Default Rate", "Exempt", "Zero Rated", "Active", "Actions"], (row) => [
				row.category_name, row.tax_type, this.percent(row.default_rate), this.yesno(row.is_exempt), this.yesno(row.is_zero_rated), this.status(row.active),
				`${this.action("Edit", "edit-category", row, this.can("can_edit_masters"))}${this.action(cint(row.active) ? "Disable" : "Enable", "toggle-category", row, this.can("can_edit_masters"))}`,
			])}
		`);
		this.render_side_panel();
	}

	render_rates() {
		const state = this.module_state("rates");
		this.$root.find(".lx-tax-main-panel").html(`
			${this.module_head("Tax Rates / History", "Rates are historical. Prefer adding a new effective rate or closing an old rate instead of overwriting submitted tax history.", this.can("can_edit_masters") ? `<button class="lx-tax-button lx-tax-button-primary" data-add-rate>Add New Rate</button>` : "")}
			${this.toolbar("rates", [
				["active", "Status", ["All", "Active", "Inactive"]],
				["applies_to", "Applies To", ["All", "Sales", "Purchase", "Both"]],
			], true)}
			${this.table_html(state, ["Category", "Rate", "Applies To", "Province", "Effective From", "Effective To", "Active", "Actions"], (row) => [
				row.tax_category, this.percent(row.rate), row.applies_to, row.province, row.effective_from, row.effective_to || "Open", this.status(row.active),
				`${this.action("View", "edit-rate", row, true)}${this.action("Close", "close-rate", row, this.can("can_edit_masters") && cint(row.active))}`,
			])}
		`);
		this.render_side_panel();
	}

	render_category_tax() {
		const state = this.module_state("category_tax");
		const can_edit = this.can("can_edit_item_mapping");
		this.$root.find(".lx-tax-main-panel").html(`
			${this.module_head(
				"Category Tax",
				"Set default tax for product categories. Items inherit at sale time unless an Item Tax Profile override exists.",
				can_edit ? `<button class="lx-tax-button lx-tax-button-primary" data-add-category-tax>Configure Category Tax</button>` : "",
			)}
			${this.toolbar("category_tax", [
				["status", "Status", ["All", "Active", "Inactive"]],
				["tax_enabled", "Tax Defaults", ["All", "Enabled", "Disabled"]],
			])}
			${this.table_html(state, ["Category", "Tax Enabled", "Tax Category", "Rate", "Items", "Mapped", "Unmapped", "Active", "Actions"], (row) => [
				row.category_name || row.name,
				this.yesno(row.tax_defaults_enabled),
				row.default_tax_category || "Not Set",
				row.default_tax_category ? this.percent(row.default_tax_rate) : "—",
				row.item_count || 0,
				row.mapped_item_count || 0,
				row.unmapped_item_count || 0,
				this.status(row.is_active),
				`${this.action("Edit Tax", "edit-category-tax", row, can_edit)}${this.action("Apply to Unmapped", "apply-category-tax", row, can_edit && cint(row.tax_defaults_enabled) && cint(row.unmapped_item_count))}`,
			])}
		`);
		this.render_side_panel();
	}

	render_mappings() {
		const state = this.module_state("item_mapping");
		this.$root.find(".lx-tax-main-panel").html(`
			${this.module_head("Item Tax Mapping", "Map products to tax categories, HS codes, and FBR-facing attributes.", this.can("can_edit_item_mapping") ? `<button class="lx-tax-button lx-tax-button-primary" data-add-mapping>Map Item Tax</button>` : "")}
			${this.toolbar("item_mapping", [
				["filter_type", "Filter", ["All", "needs_review", "missing_hs_code", "taxable", "exempt"]],
				["active", "Status", ["All", "Active", "Inactive"]],
			])}
			${this.table_html(state, ["Item", "Item Name", "Product Category", "Tax Source", "Taxable", "Tax Category", "HS Code", "Sales Type", "Needs Review", "Active", "Actions"], (row) => [
				row.item, row.item_name, row.product_category || row.item_category || "—", row.tax_source_label || "Item Override", this.yesno(row.taxable), row.tax_category, row.hs_code || "Missing", row.sales_type, this.yesno(row.needs_review), this.status(row.active),
				`${this.action("Edit", "edit-mapping", row, this.can("can_edit_item_mapping"))}${this.action("Reviewed", "mark-reviewed", row, this.can("can_edit_item_mapping") && cint(row.needs_review))}${this.action(cint(row.active) ? "Disable" : "Enable", "toggle-mapping", row, this.can("can_edit_item_mapping"))}`,
			])}
		`);
		this.render_side_panel();
	}

	render_invoices() {
		const state = this.module_state("invoice_snapshots");
		this.$root.find(".lx-tax-main-panel").html(`
			${this.module_head("Invoice Tax Snapshots", "Read-only invoice tax audit trail captured from sale tax snapshots.", `<button class="lx-tax-button lx-tax-button-soft" data-export="invoice_snapshots">Export CSV</button>`)}
			${this.snapshot_toolbar("invoice_snapshots")}
			${this.table_html(state, ["Sale", "Item", "Qty", "Gross", "Discount", "Taxable", "Category", "Rate", "Tax", "Net", "Inclusive", "Actions"], (row) => [
				row.sale, row.item, row.qty, this.money(row.gross_amount), this.money(row.discount_amount), this.money(row.taxable_amount), row.tax_category, this.percent(row.tax_rate), this.money(row.tax_amount), this.money(row.net_amount), this.yesno(row.price_includes_tax),
				this.action("View Sale", "view-sale", row, true),
			])}
		`);
		this.render_side_panel();
	}

	render_returns() {
		const state = this.module_state("return_snapshots");
		this.$root.find(".lx-tax-main-panel").html(`
			${this.module_head("Return Tax Snapshots", "Read-only return reversal view based on original invoice snapshots, not current tax settings.", `<button class="lx-tax-button lx-tax-button-soft" data-export="return_snapshots">Export CSV</button>`)}
			${this.snapshot_toolbar("return_snapshots")}
			${this.table_html(state, ["Return", "Original Sale", "Item", "Returned Qty", "Rate", "Returned Taxable", "Returned Tax", "Gross", "Net", "Inclusive", "Actions"], (row) => [
				row.sales_return, row.original_sale, row.item, row.returned_qty, this.percent(row.original_tax_rate || row.tax_rate), this.money(row.returned_taxable_amount), this.money(row.returned_tax_amount), this.money(row.gross_amount), this.money(row.net_amount), this.yesno(row.price_includes_tax),
				`${this.action("View Return", "view-return", row, true)}${this.action("View Sale", "view-sale", row, true)}`,
			])}
		`);
		this.render_side_panel();
	}

	render_fbr_logs() {
		const state = this.module_state("fbr_logs");
		this.$root.find(".lx-tax-main-panel").html(`
			${this.module_head("FBR Logs", "Audit trail for FBR validation, production submission, and retry attempts. Tokens and raw payloads are not shown here.", "")}
			${this.fbr_log_toolbar()}
			${this.fbr_log_summary_html(state.summary || {})}
			${this.table_html(state, ["Log", "Reference", "Invoice Type", "Status", "Error Code", "Error Message", "Submitted By", "Submitted At", "Actions"], (row) => [
				row.name,
				`${this.escape(row.reference_doctype || "")}<br><strong>${this.escape(row.reference_name || "")}</strong>`,
				row.invoice_type,
				this.escape(row.fbr_status || ""),
				row.error_code,
				`<span class="lx-tax-truncate">${this.escape(row.error_message || "")}</span>`,
				row.submitted_by,
				row.submitted_at,
				this.action("View", "view-fbr-log", row, true),
			])}
		`);
		this.render_side_panel();
	}

	render_fbr_control() {
		const state = this.state.fbr_control;
		const settings = state.settings || {};
		const control = state.control_state || {};
		const preview = state.preview || {};
		const readiness = preview.readiness || {};
		const sale_summary = preview.sale_summary || {};
		const payload_json = preview.payload ? JSON.stringify(preview.payload, null, 2) : "";
		const selected_sale = String(state.selected_sale || "").trim();
		const readiness_data = this.state.fbr || {};
		const missing_readiness = (readiness_data.checks || []).some((check) => check.level === "missing" || (!check.ready && check.level !== "warning"));
		const can_validate = !!preview.can_validate_now && !!selected_sale && preview.sale_name === selected_sale && !missing_readiness && control.mode === "Sandbox" && !!settings.sandbox_token_configured;
		const can_production_validate = !!selected_sale && preview.sale_name === selected_sale && !!readiness.ready && control.mode === "Production" && !!settings.production_token_configured && !!control.can_manual_validate;
		const can_production_submit = !!preview.can_submit_now && !!selected_sale && preview.sale_name === selected_sale && !!readiness.ready && !!control.can_manual_submit;
		const status_cards = [
			["Mode", control.mode || settings.mode || "Disabled"],
			["Enabled", this.yesno(control.enabled)],
			["Submit Trigger", control.submit_trigger || settings.submit_trigger || "Manual"],
			["Sandbox Token", this.yesno(settings.sandbox_token_configured)],
			["Production Token", this.yesno(settings.production_token_configured)],
			["Production Post", control.production_post_connected ? "Connected" : "Not Active"],
			["Sandbox Validate", can_validate ? "Available" : "Not Ready"],
			["Safety State", control.reason || "Preview Only"],
		];
		const setting_groups = [
			["Seller", [
				["Seller NTN/CNIC", settings.seller_ntn_cnic],
				["Seller Business Name", settings.seller_business_name],
				["Seller Province", settings.seller_province],
				["Seller Address", settings.seller_address],
			]],
			["Tokens and Controls", [
				["Sandbox Token Configured", this.yesno(settings.sandbox_token_configured)],
				["Production Token Configured", this.yesno(settings.production_token_configured)],
				["Production Post Connected", this.yesno(control.production_post_connected)],
				["Auto Submit Active", this.yesno(control.auto_submit_active)],
				["Retry Worker Active", this.yesno(control.retry_worker_active)],
				["Offline Worker Active", this.yesno(control.offline_worker_active)],
				["Sandbox Post On Submit", this.yesno(settings.sandbox_post_on_submit)],
				["Block Sale If FBR Readiness Fails", this.yesno(settings.block_sale_if_fbr_fails)],
				["Retry Enabled", this.yesno(settings.retry_enabled)],
				["Offline Upload Window (Hours)", settings.offline_upload_hours || 24],
			]],
			["Pause and Sync", [
				["Paused At", settings.paused_at],
				["Paused By", settings.paused_by],
				["Pause Reason", settings.pause_reason],
				["Last Sync Status", settings.last_sync_status],
			]],
		];
		this.$root.find(".lx-tax-main-panel").html(`
			${this.module_head("FBR Control", "Safe FBR settings, read-only preview, manual validation, and gated production submit.", `
				<button class="lx-tax-button lx-tax-button-soft lx-tax-icon-button" data-fbr-refresh ${state.loading ? "disabled" : ""} aria-label="Refresh FBR Control" title="Refresh FBR Control">${this.refresh_icon_svg()}</button>
				<button class="lx-tax-button lx-tax-button-soft" data-edit-fbr-settings>Edit FBR Settings</button>
			`)}
			<div class="lx-fbr-safety-note">
				<strong>FBR safety state.</strong>
				<span>Production Submit is available only in Production mode with a configured token, valid readiness, and explicit confirmation. On-submit production work runs after sale commit.</span>
			</div>
			${state.loading ? `<div class="lx-tax-loading">Loading FBR Control...</div>` : `
				<div class="lx-fbr-control-grid">
					${status_cards.map(([label, value]) => `
						<div class="lx-fbr-card">
							<span>${this.escape(label)}</span>
							<strong>${this.escape(this.display_value(value))}</strong>
						</div>
					`).join("")}
				</div>
				<div class="lx-fbr-summary-grid">
					${setting_groups.map(([title, rows]) => `
						<div class="lx-tax-setting-card">
							<h3>${this.escape(title)}</h3>
							${rows.map(([label, value]) => `<div class="lx-tax-kv"><span>${this.escape(label)}</span><strong>${this.escape(this.display_value(value))}</strong></div>`).join("")}
						</div>
					`).join("")}
				</div>
				${this.fbr_readiness_compact_html(readiness_data)}
				<div class="lx-fbr-preview-panel">
					<div class="lx-fbr-sale-selector">
						<div>
							<h3>Submitted Sale Preview</h3>
							<p>Select a submitted Ledgix Sale and inspect the frozen payload source.</p>
						</div>
						<div class="lx-fbr-sale-control"></div>
						<div class="lx-fbr-action-stack">
							<button class="lx-tax-button lx-tax-button-primary" data-preview-fbr-payload ${state.preview_loading ? "disabled" : ""}>Preview FBR Payload</button>
							<button class="lx-tax-button lx-tax-button-soft" data-validate-fbr-sandbox ${can_validate && !state.validate_loading ? "" : "disabled"}>${state.validate_loading ? "Validating..." : "Validate with FBR Sandbox"}</button>
							<button class="lx-tax-button lx-tax-button-soft" data-validate-fbr-production ${can_production_validate && !state.production_validate_loading ? "" : "disabled"}>${state.production_validate_loading ? "Validating..." : "Production Validate"}</button>
							<button class="lx-tax-button lx-tax-button-primary" data-submit-fbr-production ${can_production_submit && !state.submit_loading ? "" : "disabled"}>${state.submit_loading ? "Submitting..." : "Production Submit"}</button>
						</div>
					</div>
					${state.preview_loading ? `<div class="lx-tax-loading">Preparing preview...</div>` : this.fbr_preview_html(preview, readiness, sale_summary, payload_json)}
				</div>
			`}
		`);
		this.mount_fbr_sale_control();
		this.render_side_panel();
	}

	fbr_readiness_compact_html(data = {}) {
		const checks = data.checks || [];
		if (!checks.length) return "";
		return `
			<div class="lx-tax-setting-card lx-fbr-readiness-compact">
				<h3>FBR Readiness</h3>
				<div class="lx-tax-kv"><span>Readiness Score</span><strong>${this.escape(data.ready_score || 0)}%</strong></div>
				<div class="lx-fbr-compact-checks">
					${checks.map((check) => `
						<div class="lx-tax-kv lx-fbr-check is-${this.escape(check.level || (check.ready ? "ready" : "missing"))}">
							<span>${this.escape(check.label)}</span>
							<strong>${this.escape(check.ready ? "Ready" : (check.level === "warning" ? "Attention" : "Missing"))}</strong>
						</div>
					`).join("")}
				</div>
			</div>
		`;
	}

	fbr_preview_html(preview, readiness, sale_summary, payload_json) {
		if (!preview || !Object.keys(preview).length) {
			return this.empty_html("No payload preview yet", "Choose a submitted sale, then preview the FBR payload.");
		}
		const errors = readiness.errors || [];
		const warnings = readiness.warnings || [];
		const control = preview.control_state || {};
		const sale_rows = [
			["Sale Name", preview.sale_name],
			["Customer", sale_summary.customer],
			["Posting / Sale Date", sale_summary.posting_date || sale_summary.sale_date],
			["Total Amount", this.money(sale_summary.total_amount)],
			["Tax Amount", this.money(sale_summary.tax_amount)],
			["Grand Total", this.money(sale_summary.grand_total)],
			["FBR Status", sale_summary.fbr_status],
			["Tax Detail Count", sale_summary.tax_detail_count ?? 0],
		];
		return `
			<div class="lx-fbr-preview-result">
				<div class="lx-fbr-readiness-row">
					<div class="lx-fbr-card ${readiness.ready ? "is-ready" : "is-missing"}">
						<span>Readiness Status</span>
						<strong>${readiness.ready ? "Ready" : "Not Ready"}</strong>
					</div>
					<div class="lx-fbr-card is-locked">
						<span>Production Post</span>
						<strong>${control.production_post_connected ? "Connected" : "Not Active"}</strong>
					</div>
					<div class="lx-fbr-card ${preview.can_validate_now ? "is-ready" : "is-locked"}">
						<span>Can Validate Now</span>
						<strong>${preview.can_validate_now ? "Yes" : "No"}</strong>
					</div>
				</div>
				<div class="lx-fbr-message-grid">
					${this.fbr_message_list("Errors", errors, "error")}
					${this.fbr_message_list("Warnings", warnings, "warning")}
				</div>
				<div class="lx-fbr-summary-grid">
					<div class="lx-tax-setting-card">
						<h3>Sale Summary</h3>
						${sale_rows.map(([label, value]) => `<div class="lx-tax-kv"><span>${this.escape(label)}</span><strong>${this.escape(this.display_value(value))}</strong></div>`).join("")}
					</div>
				</div>
				<div class="lx-fbr-copy-row">
					<h3>Payload JSON Preview</h3>
					<button class="lx-tax-button lx-tax-button-soft" data-copy-fbr-payload ${payload_json ? "" : "disabled"}>Copy Payload</button>
				</div>
				${payload_json ? `<pre class="lx-fbr-json-block"><code>${this.escape(payload_json)}</code></pre>` : this.empty_html("No payload available", "Readiness errors may prevent payload construction.")}
			</div>
		`;
	}

	fbr_message_list(title, messages, type) {
		return `
			<div class="lx-fbr-message-list is-${type}">
				<h3>${this.escape(title)}</h3>
				${messages.length ? `<ul>${messages.map((message) => `<li>${this.escape(message)}</li>`).join("")}</ul>` : `<p>No ${this.escape(title.toLowerCase())}.</p>`}
			</div>
		`;
	}

	fbr_log_toolbar() {
		const state = this.module_state("fbr_logs");
		return `
			<div class="lx-tax-toolbar">
				<label class="lx-tax-search">
					<input data-tax-search data-module="fbr_logs" value="${this.escape(state.search)}" placeholder="Search log, reference, status, error..." />
					<button data-clear-search data-module="fbr_logs" ${state.search ? "" : "hidden"}>x</button>
				</label>
				<select class="lx-tax-filter" data-tax-filter data-module="fbr_logs" data-filter="status">
					${["", "Pending", "Validated", "Submitted", "Failed", "Skipped", "Paused", "Not Required"].map((item) => `<option value="${item}" ${(state.filters.status || "") === item ? "selected" : ""}>${item || "Status"}</option>`).join("")}
				</select>
				${this.date_range_button("fbr_logs", "FBR Logs Date Range")}
			</div>
		`;
	}

	fbr_log_summary_html(summary = {}) {
		const entries = Object.entries(summary);
		if (!entries.length) return "";
		return `
			<div class="lx-fbr-log-summary">
				${entries.map(([status, total]) => `
					<div class="lx-fbr-log-chip">
						<span>${this.escape(status)}</span>
						<strong>${this.escape(total)}</strong>
					</div>
				`).join("")}
			</div>
		`;
	}

	mount_fbr_sale_control() {
		const $holder = this.$root.find(".lx-fbr-sale-control");
		if (!$holder.length || this.state.fbr_control.loading) return;
		$holder.empty();
		if (frappe.ui?.form?.make_control) {
			let control;
			control = frappe.ui.form.make_control({
				parent: $holder[0],
				df: {
					fieldname: "fbr_sale",
					label: "Ledgix Sale",
					fieldtype: "Link",
					options: "Ledgix Sale",
					placeholder: "SAL-00455",
					get_query: () => ({ filters: { docstatus: 1 } }),
					onchange: () => {
						this.state.fbr_control.selected_sale = control.get_value() || "";
						this.state.fbr_control.preview = null;
						this.state.fbr_control.validation_result = null;
					},
				},
				render_input: true,
			});
			control.set_value(this.state.fbr_control.selected_sale || "");
			return;
		}
		$holder.html(`<input class="lx-tax-filter" data-fbr-sale-input value="${this.escape(this.state.fbr_control.selected_sale)}" placeholder="SAL-00455" />`);
	}

	toolbar(module, filters, include_category = false) {
		const state = this.module_state(module);
		return `
			<div class="lx-tax-toolbar">
				<label class="lx-tax-search">
					<input data-tax-search data-module="${module}" value="${this.escape(state.search)}" placeholder="Search..." />
					<button data-clear-search data-module="${module}" ${state.search ? "" : "hidden"}>×</button>
				</label>
				${include_category ? `<input class="lx-tax-filter" data-tax-filter data-module="${module}" data-filter="tax_category" value="${this.escape(state.filters.tax_category || "")}" placeholder="Tax Category" />` : ""}
				${filters.map(([key, label, options]) => `
					<select class="lx-tax-filter" data-tax-filter data-module="${module}" data-filter="${key}" aria-label="${this.escape(label)}">
						${options.map((option) => `<option value="${option === "All" ? "" : this.escape(option)}" ${(state.filters[key] || "") === (option === "All" ? "" : option) ? "selected" : ""}>${this.escape(this.human(option))}</option>`).join("")}
					</select>
				`).join("")}
			</div>
		`;
	}

	snapshot_toolbar(module) {
		const state = this.module_state(module);
		return `
			<div class="lx-tax-toolbar">
				<label class="lx-tax-search">
					<input data-tax-search data-module="${module}" value="${this.escape(state.search)}" placeholder="Search sale, item, category, HS code..." />
					<button data-clear-search data-module="${module}" ${state.search ? "" : "hidden"}>×</button>
				</label>
				${this.date_range_button(module, "Snapshot Date Range")}
				<input class="lx-tax-filter" data-tax-filter data-module="${module}" data-filter="tax_category" value="${this.escape(state.filters.tax_category || "")}" placeholder="Tax Category" />
				<select class="lx-tax-filter" data-tax-filter data-module="${module}" data-filter="pricing_mode">
					${["", "Inclusive", "Exclusive"].map((item) => `<option value="${item}" ${(state.filters.pricing_mode || "") === item ? "selected" : ""}>${item || "Pricing Mode"}</option>`).join("")}
				</select>
			</div>
		`;
	}

	date_range_button(module, label = "Date Range") {
		const state = this.module_state(module);
		const from_date = state.filters.from_date || "";
		const to_date = state.filters.to_date || "";
		const active = from_date || to_date;
		const title = active ? `${label}: ${from_date || "Start"} to ${to_date || "Today"}` : label;
		return `
			<button class="lx-tax-button lx-tax-button-soft lx-tax-icon-button lx-tax-date-trigger ${active ? "is-active" : ""}" data-open-date-range data-module="${module}" aria-label="${this.escape(title)}" title="${this.escape(title)}">
				${this.calendar_icon_svg()}
			</button>
		`;
	}

	show_date_range_dialog(module) {
		if (!module || !this.state.rows[module]) return;
		const state = this.module_state(module);
		const current_from = state.filters.from_date || "";
		const current_to = state.filters.to_date || "";
		const today = frappe.datetime?.get_today?.() || this.iso_date(new Date());
		const month_start = this.month_start(today);
		const month_end = this.month_end(today);
		const default_range = this.infer_date_range(current_from, current_to, today, month_start, month_end);
		const default_from = current_from || (default_range === "All" ? "" : month_start);
		const default_to = current_to || (default_range === "All" ? "" : month_end);

		const dialog = new frappe.ui.Dialog({
			title: "Table Date Range",
			fields: [
				{
					fieldname: "range",
					label: "Range",
					fieldtype: "Select",
					options: "All\nToday\nThis Month\nLast 7 Days\nLast 30 Days\nCustom",
					default: default_range,
					onchange: () => {
						const range = dialog.get_value("range") || "Custom";
						this.apply_quick_range_to_dialog(dialog, range, today, month_start, month_end);
					},
				},
				{ fieldname: "from_date", label: "From Date", fieldtype: "Date", default: default_from },
				{ fieldname: "to_date", label: "To Date", fieldtype: "Date", default: default_to },
				{
					fieldname: "date_range_actions",
					fieldtype: "HTML",
					options: `
						<div class="lx-tax-date-dialog-actions">
							<button type="button" class="lx-tax-button lx-tax-button-soft" data-tax-date-all>All</button>
							<button type="button" class="lx-tax-button lx-tax-button-soft" data-tax-date-today>Today</button>
						</div>
					`,
				},
			],
			primary_action_label: "Apply",
			primary_action: (values) => {
				const range = values.range || "Custom";
				let resolved = this.resolve_date_range(range, values.from_date, values.to_date, today, month_start, month_end);
				if (!["All", "Custom"].includes(range)) {
					const quick = this.resolve_date_range(range, "", "", today, month_start, month_end);
					if ((values.from_date || "") !== quick.from_date || (values.to_date || "") !== quick.to_date) {
						resolved = this.resolve_date_range("Custom", values.from_date, values.to_date, today, month_start, month_end);
					}
				}
				if (resolved.from_date && resolved.to_date && resolved.from_date > resolved.to_date) {
					frappe.msgprint("From Date cannot be after To Date.");
					return;
				}
				state.filters.from_date = resolved.from_date || "";
				state.filters.to_date = resolved.to_date || "";
				state.page = 1;
				dialog.hide();
				this.load_module(module);
			},
		});

		this.theme_dialog(dialog);
		dialog.show();
		this.apply_quick_range_to_dialog(dialog, default_range, today, month_start, month_end, current_from, current_to);

		dialog.$wrapper.on("click", "[data-tax-date-all]", () => {
			dialog.set_value("range", "All");
			dialog.set_value("from_date", "");
			dialog.set_value("to_date", "");
		});
		dialog.$wrapper.on("click", "[data-tax-date-today]", () => {
			dialog.set_value("range", "Today");
			dialog.set_value("from_date", today);
			dialog.set_value("to_date", today);
		});
	}

	infer_date_range(from_date, to_date, today, month_start, month_end) {
		if (!from_date && !to_date) return "This Month";
		if (from_date === today && to_date === today) return "Today";
		if (from_date === month_start && to_date === month_end) return "This Month";
		return "Custom";
	}

	apply_quick_range_to_dialog(dialog, range, today, month_start, month_end, original_from = null, original_to = null) {
		const resolved = this.resolve_date_range(range, original_from, original_to, today, month_start, month_end);
		dialog.set_value("from_date", resolved.from_date || "");
		dialog.set_value("to_date", resolved.to_date || "");
	}

	resolve_date_range(range, from_date, to_date, today, month_start, month_end) {
		if (range === "All") return { from_date: "", to_date: "" };
		if (range === "Today") return { from_date: today, to_date: today };
		if (range === "This Month") return { from_date: month_start, to_date: month_end };
		if (range === "Last 7 Days") return { from_date: this.add_days(today, -6), to_date: today };
		if (range === "Last 30 Days") return { from_date: this.add_days(today, -29), to_date: today };
		return { from_date: from_date || "", to_date: to_date || "" };
	}

	table_html(state, headings, row_builder) {
		if (state.loading) return `<div class="lx-tax-loading">Loading...</div>`;
		if (!state.rows.length) return this.empty_html("No records found", "Try changing search or filters.");
		const start = ((state.page - 1) * this.state.page_size) + 1;
		const end = Math.min(state.page * this.state.page_size, state.total);
		return `
			<div class="lx-tax-table-wrap">
				<table class="lx-tax-table">
					<thead><tr>${headings.map((heading) => `<th>${this.escape(heading)}</th>`).join("")}</tr></thead>
					<tbody>
						${state.rows.map((row, index) => `<tr data-row-index="${index}">${row_builder(row).map((cell) => `<td>${cell || ""}</td>`).join("")}</tr>`).join("")}
					</tbody>
				</table>
			</div>
			<div class="lx-tax-pagination">
				<span>Showing ${start}-${end} of ${state.total}</span>
				<div>
					<button class="lx-tax-button lx-tax-button-soft" data-page-dir="prev" ${state.page <= 1 ? "disabled" : ""}>Previous</button>
					<strong>Page ${state.page}</strong>
					<button class="lx-tax-button lx-tax-button-soft" data-page-dir="next" ${end >= state.total ? "disabled" : ""}>Next</button>
				</div>
			</div>
		`;
	}

	render_side_panel() {
		const module = this.state.active_module;
		const state = this.module_state(module);
		const profile = this.state.profile || {};
		let selected = state?.selected_row;
		let guide = {
			setup: "Inclusive pricing treats the selling price as the customer-paid total. Exclusive pricing adds tax on top.",
			category_tax: "Category tax applies automatically at sale time. Use Item Mapping for per-item overrides and HS codes required for FBR.",
			categories: "Categories are master records. Disable unused categories instead of deleting them.",
			rates: "Rates are historical. Add new effective rows or close old rows for audit clarity.",
			item_mapping: "Review item mappings regularly so taxable products have the right category, HS code, and FBR fields.",
			invoice_snapshots: "Invoice snapshots are read-only and preserve tax details captured at sale time.",
			return_snapshots: "Return reversals use the original sale snapshot, not current tax setup.",
			fbr_control: "Validate Only checks payload readiness/validation without issuing a production invoice number.",
			fbr_logs: "FBR logs show safe audit metadata only. Raw payload and response JSON are kept out of table rows.",
		}[module];
		const mapping_summary = this.module_state("item_mapping").summary || {};
		const category_summary = this.module_state("category_tax").summary || {};
		this.$root.find(".lx-tax-side-panel").html(`
			<div class="lx-tax-insight-card">
				<h3>Compliance Health</h3>
				<div class="lx-tax-kv"><span>Tax Engine</span><strong>${cint(profile.tax_enabled) ? "Enabled" : "Disabled"}</strong></div>
				<div class="lx-tax-kv"><span>Pricing Mode</span><strong>${cint(profile.price_includes_tax) ? "Inclusive" : "Exclusive"}</strong></div>
				<div class="lx-tax-kv"><span>Default Category</span><strong>${this.escape(profile.default_tax_category || "Not Set")}</strong></div>
			</div>
			<div class="lx-tax-insight-card">
				<h3>Module Guide</h3>
				<p>${this.escape(guide)}</p>
			</div>
			${module === "category_tax" ? `
				<div class="lx-tax-insight-card">
					<h3>Category Tax Stats</h3>
					<div class="lx-tax-kv"><span>Total categories</span><strong>${category_summary.total_categories || 0}</strong></div>
					<div class="lx-tax-kv"><span>Tax enabled</span><strong>${category_summary.tax_enabled_categories || 0}</strong></div>
					<div class="lx-tax-kv"><span>Missing tax category</span><strong>${category_summary.categories_missing_tax_category || 0}</strong></div>
				</div>
			` : ""}
			${module === "item_mapping" ? `
				<div class="lx-tax-insight-card">
					<h3>Mapping Stats</h3>
					<div class="lx-tax-kv"><span>Total mappings</span><strong>${mapping_summary.total_mappings || 0}</strong></div>
					<div class="lx-tax-kv"><span>Needs review</span><strong>${mapping_summary.needs_review || 0}</strong></div>
					<div class="lx-tax-kv"><span>Missing HS code</span><strong>${mapping_summary.missing_hs_code || 0}</strong></div>
					<div class="lx-tax-kv"><span>Active taxable</span><strong>${mapping_summary.active_taxable || 0}</strong></div>
				</div>
			` : ""}
			${module === "fbr_control" ? `
				<div class="lx-tax-insight-card">
					<h3>Safety Facts</h3>
					<div class="lx-tax-kv"><span>Manual</span><strong>Admin controlled</strong></div>
					<div class="lx-tax-kv"><span>On Submit</span><strong>After commit</strong></div>
					<div class="lx-tax-kv"><span>Retry worker</span><strong>Pending/failed only</strong></div>
					<div class="lx-tax-kv"><span>Payload source</span><strong>Frozen sale tax_details</strong></div>
				</div>
			` : ""}
			${selected ? `
				<div class="lx-tax-insight-card">
					<h3>Selected Row Preview</h3>
					${Object.keys(selected).slice(0, 8).map((key) => `<div class="lx-tax-kv"><span>${this.escape(this.human(key))}</span><strong>${this.escape(selected[key] || "-")}</strong></div>`).join("")}
				</div>
			` : ""}
		`);
	}

	module_head(title, subtitle, actions = "") {
		return `
			<div class="lx-tax-module-head">
				<div>
					<h2>${this.escape(title)}</h2>
					<p>${this.escape(subtitle)}</p>
				</div>
				<div class="lx-tax-module-actions">${actions}</div>
			</div>
		`;
	}

	show_profile_dialog() {
		const p = this.state.profile || {};
		const booleans = ["tax_enabled", "price_includes_tax", "receipt_tax_display_enabled"];
		const dialog = new frappe.ui.Dialog({
			title: "Edit Tax Settings",
			fields: [
				{ fieldname: "business_section", label: "Business Identity", fieldtype: "Section Break" },
				{ fieldname: "business_name", label: "Business Name", fieldtype: "Data", default: p.business_name },
				{ fieldname: "province", label: "Province", fieldtype: "Select", options: "Punjab\nSindh\nKhyber Pakhtunkhwa\nBalochistan\nIslamabad Capital Territory\nGilgit-Baltistan\nAzad Jammu and Kashmir", default: p.province },
				{ fieldname: "business_type", label: "Business Type", fieldtype: "Select", options: "Retail\nWholesale\nRetail & Wholesale\nService\nOther", default: p.business_type },
				{ fieldname: "business_column", fieldtype: "Column Break" },
				{ fieldname: "branch__outlet_name", label: "Branch / Outlet Name", fieldtype: "Data", default: p.branch__outlet_name },
				{ fieldname: "outlet_address", label: "Outlet Address", fieldtype: "Small Text", default: p.outlet_address },
				{ fieldname: "tax_section", label: "Tax Behavior", fieldtype: "Section Break" },
				this.boolean_select("tax_enabled", "Tax Enabled", p.tax_enabled),
				this.boolean_select("price_includes_tax", "Price Includes Tax", p.price_includes_tax),
				{ fieldname: "default_tax_category", label: "Default Tax Category", fieldtype: "Link", options: "Ledgix Tax Category", default: p.default_tax_category },
				{ fieldname: "tax_column", fieldtype: "Column Break" },
				this.boolean_select("receipt_tax_display_enabled", "Receipt Tax Display Enabled", p.receipt_tax_display_enabled),
				{ fieldname: "default_sales_type", label: "Default Sales Type", fieldtype: "Data", default: p.default_sales_type },
				{ fieldname: "default_buyer_type", label: "Default Buyer Type", fieldtype: "Select", options: "Registered\nUnregistered\nConsumer", default: p.default_buyer_type },
				{ fieldname: "receipt_section", label: "Receipt Identity", fieldtype: "Section Break" },
				{ fieldname: "ntn", label: "NTN", fieldtype: "Data", default: p.ntn },
				{ fieldname: "receipt_column", fieldtype: "Column Break" },
				{ fieldname: "strn__sales_tax_registration_number", label: "STRN / Sales Tax Registration Number", fieldtype: "Data", default: p.strn__sales_tax_registration_number },
				{ fieldname: "pos_registration_number", label: "POS Registration Number", fieldtype: "Data", default: p.pos_registration_number },
			],
			primary_action_label: "Save Settings",
			primary_action: async (values) => {
				this.normalize_dialog_booleans(values, booleans);
				await this.call(this.method_paths.save_profile, { values });
				dialog.hide();
				frappe.show_alert({ message: "Tax settings saved.", indicator: "green" });
				await this.bootstrap(true);
			},
		});
		this.theme_dialog(dialog);
		dialog.show();
	}

	show_preview_dialog() {
		const p = this.state.profile || {};
		const dialog = new frappe.ui.Dialog({
			title: "Preview Tax Calculation",
			fields: [
				{ fieldname: "amount", label: "Amount", fieldtype: "Currency", reqd: 1 },
				{ fieldname: "tax_category", label: "Tax Category", fieldtype: "Link", options: "Ledgix Tax Category", default: p.default_tax_category },
				this.boolean_select("price_includes_tax", "Price Includes Tax", p.price_includes_tax),
				{ fieldname: "preview_html", fieldtype: "HTML" },
			],
			primary_action_label: "Preview",
			primary_action: async (values) => {
				if (!values.amount) {
					frappe.msgprint("Amount is required.");
					return;
				}
				this.normalize_dialog_booleans(values, ["price_includes_tax"]);
				const result = await this.call(this.method_paths.preview, values);
				dialog.fields_dict.preview_html.$wrapper.html(`
					<div class="lx-tax-preview-grid">
						${["gross_amount", "taxable_amount", "tax_rate", "tax_amount", "net_amount"].map((key) => `<div><span>${this.human(key)}</span><strong>${this.escape(result[key])}</strong></div>`).join("")}
						<div><span>Pricing Mode</span><strong>${cint(result.price_includes_tax) ? "Inclusive" : "Exclusive"}</strong></div>
					</div>
				`);
			},
		});
		this.theme_dialog(dialog);
		dialog.show();
	}

	show_category_dialog(row = {}) {
		const booleans = ["is_exempt", "is_zero_rated", "active"];
		const dialog = new frappe.ui.Dialog({
			title: row.name ? "Edit Category" : "Add Category",
			fields: [
				{ fieldname: "name", fieldtype: "Data", hidden: 1, default: row.name },
				{fieldname: "category_name",label: "Category Name",fieldtype: "Data",reqd: 1,read_only: row.name ? 1 : 0,default: row.category_name,description: row.name ? "Category name is locked after creation to protect tax history." : "",},
				{ fieldname: "tax_type", label: "Tax Type", fieldtype: "Select", options: "Sales Tax\nFurther Tax\nFED\nOther", default: row.tax_type },
				{ fieldname: "default_rate", label: "Default Rate %", fieldtype: "Percent", default: row.default_rate },
				this.boolean_select("is_exempt", "Is Exempt", row.is_exempt),
				this.boolean_select("is_zero_rated", "Is Zero Rated", row.is_zero_rated),
				this.boolean_select("active", "Active", row.name ? row.active : 1),
				{ fieldname: "description", label: "Description", fieldtype: "Small Text", default: row.description },
			],
			primary_action_label: "Save Category",
			primary_action: async (values) => this.save_dialog(dialog, this.method_paths.save_category, this.normalize_dialog_booleans(values, booleans), "Category saved.", "categories"),
		});
		this.theme_dialog(dialog);
		dialog.show();
	}

	show_rate_dialog(row = {}) {
		const is_existing = !!row.name;
		const booleans = ["active"];

		const dialog = new frappe.ui.Dialog({
			title: is_existing ? "View Rate" : "Add New Rate",
			fields: [
				{ fieldname: "name", fieldtype: "Data", hidden: 1, default: row.name },
				{ fieldname: "tax_category", label: "Tax Category", fieldtype: "Link", options: "Ledgix Tax Category", reqd: 1, default: row.tax_category, read_only: is_existing },
				{ fieldname: "rate", label: "Rate %", fieldtype: "Percent", reqd: 1, default: row.rate, read_only: is_existing },
				{ fieldname: "effective_from", label: "Effective From", fieldtype: "Date", reqd: 1, default: row.effective_from, read_only: is_existing },
				{ fieldname: "effective_to", label: "Effective To", fieldtype: "Date", default: row.effective_to, read_only: is_existing },
				{ fieldname: "applies_to", label: "Applies To", fieldtype: "Select", options: "Sales\nPurchase\nBoth", default: row.applies_to || "Sales", read_only: is_existing },
				{ fieldname: "province", label: "Province", fieldtype: "Select", options: "Punjab\nSindh\nKhyber Pakhtunkhwa\nBalochistan\nIslamabad Capital Territory\nGilgit-Baltistan\nAzad Jammu and Kashmir", default: row.province, read_only: is_existing },
				this.boolean_select("active", "Active", row.name ? row.active : 1, { read_only: is_existing }),
			],
			primary_action_label: is_existing ? "Done" : "Create Rate",
			primary_action: async (values) => {
				if (is_existing) {
					dialog.hide();
					return;
				}

				return this.save_dialog(dialog, this.method_paths.save_rate, this.normalize_dialog_booleans(values, booleans), "Rate saved.", "rates");
			},
		});
		this.theme_dialog(dialog);
		dialog.show();
	}

	show_close_rate_dialog(row) {
		const dialog = new frappe.ui.Dialog({
			title: "Close Existing Rate",
			fields: [
				{ fieldname: "effective_to", label: "Effective To", fieldtype: "Date", reqd: 1 },
				{ fieldname: "reason", label: "Reason", fieldtype: "Small Text" },
			],
			primary_action_label: "Close Rate",
			primary_action: async (values) => {
				await this.call(this.method_paths.close_rate, { name: row.name, ...values });
				dialog.hide();
				frappe.show_alert({ message: "Rate closed.", indicator: "green" });
				await this.load_module("rates");
			},
		});
		this.theme_dialog(dialog);
		dialog.show();
	}

	show_category_tax_dialog(row = {}) {
		const is_new = !row.name;
		const booleans = ["tax_defaults_enabled", "default_taxable"];
		const category_fields = is_new
			? [
				{
					fieldname: "category",
					label: "Product Category",
					fieldtype: "Link",
					options: "Ledgix Category",
					reqd: 1,
					description: "Choose a product category from Operations. New categories can be created under Operations → Categories first.",
				},
			]
			: [
				{ fieldname: "category_name", label: "Product Category", fieldtype: "Data", read_only: 1, default: row.category_name || row.name },
			];
		const dialog = new frappe.ui.Dialog({
			title: is_new ? "Configure Category Tax" : `Category Tax — ${row.category_name || row.name || ""}`,
			fields: [
				{ fieldname: "name", fieldtype: "Data", hidden: 1, default: row.name },
				...category_fields,
				this.boolean_select("tax_defaults_enabled", "Tax Defaults Enabled", row.tax_defaults_enabled ?? 1),
				{ fieldname: "default_tax_category", label: "Default Tax Category", fieldtype: "Link", options: "Ledgix Tax Category", default: row.default_tax_category },
				this.boolean_select("default_taxable", "Default Taxable", row.name ? row.default_taxable : 1),
				{ fieldname: "default_sales_type", label: "Default Sales Type", fieldtype: "Data", default: row.default_sales_type },
				{ fieldname: "default_uom_for_fbr", label: "Default UOM for FBR", fieldtype: "Data", default: row.default_uom_for_fbr },
				{ fieldname: "default_scenario_id", label: "Default Scenario ID", fieldtype: "Data", default: row.default_scenario_id },
			],
			primary_action_label: "Save Category Tax",
			primary_action: async (values) => {
				const payload = this.normalize_dialog_booleans(values, booleans);
				if (!payload.name && payload.category) {
					payload.name = payload.category;
				}
				return this.save_dialog(
					dialog,
					this.method_paths.save_category_tax,
					payload,
					"Category tax saved.",
					"category_tax",
				);
			},
		});
		this.theme_dialog(dialog);
		if (is_new) {
			const category_field = dialog.fields_dict.category;
			if (category_field?.$input) {
				category_field.$input.on("change", async () => {
					const category = category_field.get_value();
					if (!category) return;
					try {
						const doc = await frappe.db.get_doc("Ledgix Category", category);
						dialog.set_values({
							name: doc.name,
							tax_defaults_enabled: doc.tax_defaults_enabled ?? 1,
							default_tax_category: doc.default_tax_category || "",
							default_taxable: doc.default_taxable ?? 1,
							default_sales_type: doc.default_sales_type || "",
							default_uom_for_fbr: doc.default_uom_for_fbr || "",
							default_scenario_id: doc.default_scenario_id || "",
						});
					} catch (error) {
						console.error("Ledgix category tax preload failed:", error);
					}
				});
			}
		}
		dialog.show();
	}

	show_mapping_dialog(row = {}) {
		const booleans = ["taxable", "needs_review", "active"];
		const dialog = new frappe.ui.Dialog({
			title: row.name ? "Edit Item Tax Mapping" : "Map Item Tax",
			fields: [
				{ fieldname: "name", fieldtype: "Data", hidden: 1, default: row.name },
				{ fieldname: "item", label: "Item", fieldtype: "Link", options: "Ledgix Item", reqd: 1, default: row.item },
				this.boolean_select("taxable", "Taxable", row.name ? row.taxable : 1),
				{ fieldname: "tax_category", label: "Tax Category", fieldtype: "Link", options: "Ledgix Tax Category", reqd: 1, default: row.tax_category },
				{ fieldname: "hs_code", label: "HS Code", fieldtype: "Data", default: row.hs_code },
				{ fieldname: "uom_for_fbr", label: "UOM for FBR", fieldtype: "Data", default: row.uom_for_fbr },
				{ fieldname: "sales_type", label: "Sales Type", fieldtype: "Data", default: row.sales_type },
				{ fieldname: "scenario_id", label: "Scenario ID", fieldtype: "Data", default: row.scenario_id },
				{ fieldname: "sro_schedule_number", label: "SRO Schedule Number", fieldtype: "Data", default: row.sro_schedule_number },
				{ fieldname: "sro_item_serial_number", label: "SRO Item Serial Number", fieldtype: "Data", default: row.sro_item_serial_number },
				this.boolean_select("needs_review", "Needs Review", row.name ? row.needs_review : 1),
				this.boolean_select("active", "Active", row.name ? row.active : 1),
			],
			primary_action_label: "Save Mapping",
			primary_action: async (values) => this.save_dialog(dialog, this.method_paths.save_mapping, this.normalize_dialog_booleans(values, booleans), "Mapping saved.", "item_mapping"),
		});
		this.theme_dialog(dialog);
		dialog.show();
	}

	show_fbr_settings_dialog() {
		const p = this.state.fbr_control.settings || {};
		const token_description = "Leave blank to keep existing token. Token value is write-only and will not be displayed.";
		const booleans = ["enabled", "block_sale_if_fbr_fails", "sandbox_post_on_submit", "retry_enabled"];
		const dialog = new frappe.ui.Dialog({
			title: "Edit FBR Settings",
			fields: [
				{ fieldname: "control_section", label: "Control", fieldtype: "Section Break" },
				this.boolean_select("enabled", "Enabled", p.enabled),
				{ fieldname: "mode", label: "Mode", fieldtype: "Select", options: "Disabled\nSandbox\nProduction\nPaused\nManual Only", default: p.mode || "Disabled" },
				{ fieldname: "submit_trigger", label: "Submit Trigger", fieldtype: "Select", options: "Manual\nOn Submit\nValidate Only", default: p.submit_trigger || "Manual" },
				{ fieldname: "control_column", fieldtype: "Column Break" },
				this.boolean_select("block_sale_if_fbr_fails", "Block Sale If FBR Readiness Fails", p.block_sale_if_fbr_fails),
				this.boolean_select("sandbox_post_on_submit", "Sandbox Post On Submit", p.sandbox_post_on_submit),
				this.boolean_select("retry_enabled", "Retry Enabled", p.retry_enabled),
				{ fieldname: "max_retry_count", label: "Max Retry Count", fieldtype: "Int", default: p.max_retry_count || 0 },
				{ fieldname: "offline_upload_hours", label: "Offline Upload Window (Hours)", fieldtype: "Int", default: p.offline_upload_hours || 24 },
				{ fieldname: "control_help", fieldtype: "HTML", options: `<div class="lx-tax-dialog-note">Sandbox Post On Submit posts to FBR sandbox after sale commit. Without it, Sandbox + On Submit only validates. Offline upload window applies when production post fails due to network issues.</div>` },
				{ fieldname: "seller_section", label: "Seller Identity", fieldtype: "Section Break" },
				{ fieldname: "seller_ntn_cnic", label: "Seller NTN/CNIC", fieldtype: "Data", default: p.seller_ntn_cnic },
				{ fieldname: "seller_business_name", label: "Seller Business Name", fieldtype: "Data", default: p.seller_business_name },
				{ fieldname: "seller_column", fieldtype: "Column Break" },
				{ fieldname: "seller_province", label: "Seller Province", fieldtype: "Data", default: p.seller_province },
				{ fieldname: "seller_address", label: "Seller Address", fieldtype: "Small Text", default: p.seller_address },
				{ fieldname: "pause_section", label: "Pause / Safety", fieldtype: "Section Break" },
				{ fieldname: "pause_reason", label: "Pause Reason", fieldtype: "Small Text", default: p.pause_reason },
				{ fieldname: "token_section", label: "Tokens", fieldtype: "Section Break" },
				{ fieldname: "token_help", fieldtype: "HTML", options: `<div class="lx-tax-dialog-note">Validate Only checks payload readiness/validation without issuing a production invoice number. Production Submit can send the invoice to the live FBR system only in Production mode with explicit confirmation. Retry worker processes failed/pending production submissions only when retry is enabled and the sale has no FBR invoice number.</div>` },
				{ fieldname: "sandbox_token", label: "Sandbox Token", fieldtype: "Password", description: token_description },
				{ fieldname: "production_token", label: "Production Token", fieldtype: "Password", description: token_description },
			],
			primary_action_label: "Save FBR Settings",
			primary_action: async (values) => {
				try {
					this.state.fbr_control.saving = true;
					this.normalize_dialog_booleans(values, booleans);
					await this.call(this.method_paths.save_fbr_settings, { values });
					if (values) {
						values.sandbox_token = "";
						values.production_token = "";
					}
					dialog.hide();
					frappe.show_alert({ message: "FBR settings saved.", indicator: "green" });
					await this.load_module("fbr_control", true);
				} catch (error) {
					this.show_error("Could not save FBR settings. Check your permissions and values.", error);
				} finally {
					this.state.fbr_control.saving = false;
				}
			},
		});
		this.theme_dialog(dialog);
		dialog.show();
	}

	boolean_select(fieldname, label, value, overrides = {}) {
		return {
			fieldname,
			label,
			fieldtype: "Check",
			default: cint(value) ? 1 : 0,
			...overrides,
		};
	}

	normalize_dialog_booleans(values, fieldnames) {
		(fieldnames || []).forEach((fieldname) => {
			if (!values || !(fieldname in values)) return;
			values[fieldname] = values[fieldname] === "Yes" || values[fieldname] === 1 || values[fieldname] === true ? 1 : 0;
		});
		return values;
	}

	show_sale_snapshot_dialog(row = {}) {
		const sale = row.sale || row.original_sale || "";
		this.show_snapshot_dialog({
			title: "Sale Tax Snapshot",
			rows: [
				["Sale", sale],
				["Item", row.item],
				["Qty", row.qty ?? row.returned_qty],
				["Gross", this.money(row.gross_amount)],
				["Discount", this.money(row.discount_amount)],
				["Taxable", this.money(row.taxable_amount || row.returned_taxable_amount)],
				["Tax Category", row.tax_category],
				["Tax Rate", this.percent(row.tax_rate || row.original_tax_rate)],
				["Tax Amount", this.money(row.tax_amount || row.returned_tax_amount)],
				["Net", this.money(row.net_amount)],
				["Price Includes Tax", this.yesno(row.price_includes_tax)],
				["HS Code", row.hs_code],
				["UOM for FBR", row.uom_for_fbr],
				["Sales Type", row.sales_type],
				["Scenario ID", row.scenario_id],
				["SRO Schedule Number", row.sro_schedule_number],
				["SRO Item Serial Number", row.sro_item_serial_number],
			],
		});
	}

	show_return_snapshot_dialog(row = {}) {
		const sales_return = row.sales_return || "";
		this.show_snapshot_dialog({
			title: "Return Tax Snapshot",
			rows: [
				["Sales Return", sales_return],
				["Original Sale", row.original_sale],
				["Item", row.item],
				["Returned Qty", row.returned_qty],
				["Original Tax Rate", this.percent(row.original_tax_rate)],
				["Returned Taxable Amount", this.money(row.returned_taxable_amount)],
				["Returned Tax Amount", this.money(row.returned_tax_amount)],
				["Gross", this.money(row.gross_amount)],
				["Taxable", this.money(row.taxable_amount)],
				["Tax Rate", this.percent(row.tax_rate)],
				["Tax Amount", this.money(row.tax_amount)],
				["Net", this.money(row.net_amount)],
				["Price Includes Tax", this.yesno(row.price_includes_tax)],
				["Tax Category", row.tax_category],
				["HS Code", row.hs_code],
				["UOM for FBR", row.uom_for_fbr],
				["Sales Type", row.sales_type],
				["Scenario ID", row.scenario_id],
				["SRO Schedule Number", row.sro_schedule_number],
				["SRO Item Serial Number", row.sro_item_serial_number],
			],
		});
	}

	show_fbr_log_dialog(row = {}) {
		this.show_snapshot_dialog({
			title: "FBR Log Details",
			rows: [
				["Log", row.name],
				["Reference DocType", row.reference_doctype],
				["Reference Name", row.reference_name],
				["Invoice Type", row.invoice_type],
				["Status", row.fbr_status],
				["FBR Invoice Number", row.fbr_invoice_number],
				["Attempt Count", row.attempt_count],
				["Error Code", row.error_code],
				["Error Message", row.error_message],
				["Submitted By", row.submitted_by],
				["Submitted At", row.submitted_at],
				["Modified", row.modified],
			],
		});
	}

	show_snapshot_dialog({ title, rows, link_label, link_href }) {
		const details = (rows || []).map(([label, value]) => `
			<div class="lx-tax-snapshot-kv">
				<span>${this.escape(label)}</span>
				<strong>${this.escape(this.display_value(value))}</strong>
			</div>
		`).join("");
		const link = link_href ? `
			<a class="lx-tax-button lx-tax-button-soft lx-tax-modal-link" href="${this.escape(link_href)}" target="_blank" rel="noopener noreferrer">
				${this.escape(link_label)}
			</a>
		` : "";
		const dialog = new frappe.ui.Dialog({
			title,
			fields: [
				{
					fieldname: "snapshot_html",
					fieldtype: "HTML",
					options: `
						<div class="lx-tax-snapshot-modal">
							<div class="lx-tax-snapshot-grid">${details}</div>
							${link ? `<div class="lx-tax-snapshot-actions">${link}</div>` : ""}
						</div>
					`,
				},
			],
		});
		this.theme_dialog(dialog);
		dialog.show();
	}

	async preview_fbr_payload() {
		const state = this.state.fbr_control;
		const sale_name = String(state.selected_sale || "").trim();
		if (!sale_name) {
			frappe.msgprint("Select a submitted Ledgix Sale before previewing the FBR payload.");
			return;
		}
		state.preview_loading = true;
		this.render_fbr_control();
		try {
			state.preview = await this.call(this.method_paths.fbr_sale_preview, { sale_name });
			state.validation_result = null;
		} catch (error) {
			this.show_error("Could not preview the FBR payload.", error);
		} finally {
			state.preview_loading = false;
			this.render_fbr_control();
		}
	}

	async validate_fbr_sandbox() {
		const state = this.state.fbr_control;
		const sale_name = String(state.selected_sale || "").trim();
		if (!sale_name || !state.preview?.can_validate_now) {
			frappe.msgprint("Preview readiness must be ready before Sandbox validation.");
			return;
		}
		const confirmed = await new Promise((resolve) => {
			frappe.confirm(
				"This will send the selected invoice payload to FBR Sandbox Validate API. It will create an FBR Submission Log and update this Sale FBR status. It will not issue a final FBR invoice number.",
				() => resolve(true),
				() => resolve(false)
			);
		});
		if (!confirmed) return;

		state.validate_loading = true;
		this.render_fbr_control();
		try {
			const result = await this.call(this.method_paths.fbr_validate_sale, { sale_name });
			state.validation_result = result || {};
			this.show_fbr_validation_result(result || {});
			await this.load_module("fbr_control", true);
			if (sale_name) await this.preview_fbr_payload();
		} catch (error) {
			this.show_error("Could not validate with FBR Sandbox.", error);
		} finally {
			state.validate_loading = false;
			this.render_fbr_control();
		}
	}

	async validate_fbr_production() {
		const state = this.state.fbr_control;
		const sale_name = String(state.selected_sale || "").trim();
		if (!sale_name || !state.preview?.readiness?.ready) {
			frappe.msgprint("Preview readiness must be ready before Production validation.");
			return;
		}
		const confirmed = await new Promise((resolve) => {
			frappe.confirm(
				"This will send the selected invoice payload to FBR Production Validate API. It will not issue or save an FBR invoice number.",
				() => resolve(true),
				() => resolve(false)
			);
		});
		if (!confirmed) return;

		state.production_validate_loading = true;
		this.render_fbr_control();
		try {
			const result = await this.call(this.method_paths.fbr_validate_sale_production, { sale_name });
			state.validation_result = result || {};
			this.show_fbr_validation_result(result || {}, "FBR Production Validate Result");
			await this.load_module("fbr_control", true);
			if (sale_name) await this.preview_fbr_payload();
			await this.load_module("fbr_logs", true);
		} catch (error) {
			this.show_error("Could not validate with FBR Production.", error);
		} finally {
			state.production_validate_loading = false;
			this.render_fbr_control();
		}
	}

	async submit_fbr_production() {
		const state = this.state.fbr_control;
		const sale_name = String(state.selected_sale || "").trim();
		if (!sale_name || !state.preview?.can_submit_now) {
			frappe.msgprint("Production Submit is available only for a ready submitted sale when Production mode is active and manual submit is allowed.");
			return;
		}
		const confirmed = await new Promise((resolve) => {
			frappe.confirm(
				`Sale ${this.escape(sale_name)} is in Production mode. This may submit the invoice to the live FBR production system and may generate an official FBR invoice number.`,
				() => resolve(true),
				() => resolve(false)
			);
		});
		if (!confirmed) return;

		state.submit_loading = true;
		this.render_fbr_control();
		try {
			const result = await this.call(this.method_paths.fbr_submit_sale, { sale_name });
			state.validation_result = result || {};
			this.show_fbr_validation_result(result || {}, "FBR Production Submit Result");
			await this.load_module("fbr_control", true);
			if (sale_name) await this.preview_fbr_payload();
			await this.load_module("fbr_logs", true);
		} catch (error) {
			this.show_error("Could not submit to FBR Production.", error);
		} finally {
			state.submit_loading = false;
			this.render_fbr_control();
		}
	}

	show_fbr_validation_result(result = {}, title = "FBR Sandbox Validate Result") {
		const response = result.response || {};
		const summary = response.response?.validationResponse || {};
		const rows = [
			["Status", result.status],
			["Log Name", result.log_name],
			["Network Call", result.network_call ? "Yes" : "No"],
			["HTTP Status", response.http_status],
			["Error Code", result.error_code],
			["Error Message", result.error_message],
		];
		const dialog = new frappe.ui.Dialog({
			title,
			fields: [
				{
					fieldname: "result_html",
					fieldtype: "HTML",
					options: `
						<div class="lx-fbr-validation-result">
							<div class="lx-fbr-summary-grid">
								<div class="lx-tax-setting-card">
									<h3>Result</h3>
									${rows.map(([label, value]) => `<div class="lx-tax-kv"><span>${this.escape(label)}</span><strong>${this.escape(this.display_value(value))}</strong></div>`).join("")}
								</div>
								<div class="lx-tax-setting-card">
									<h3>FBR Response Summary</h3>
									<div class="lx-tax-kv"><span>Status</span><strong>${this.escape(this.display_value(summary.status))}</strong></div>
									<div class="lx-tax-kv"><span>Status Code</span><strong>${this.escape(this.display_value(summary.statusCode))}</strong></div>
									<div class="lx-tax-kv"><span>Message</span><strong>${this.escape(this.display_value(summary.message || summary.error))}</strong></div>
								</div>
							</div>
						</div>
					`,
				},
			],
		});
		this.theme_dialog(dialog);
		dialog.show();
	}

	async copy_fbr_payload() {
		const payload = this.state.fbr_control.preview?.payload;
		if (!payload) {
			frappe.msgprint("No payload is available to copy.");
			return;
		}
		const text = JSON.stringify(payload, null, 2);
		try {
			if (navigator.clipboard?.writeText) {
				await navigator.clipboard.writeText(text);
			} else {
				const textarea = document.createElement("textarea");
				textarea.value = text;
				textarea.setAttribute("readonly", "readonly");
				textarea.style.position = "fixed";
				textarea.style.opacity = "0";
				document.body.appendChild(textarea);
				textarea.select();
				document.execCommand("copy");
				document.body.removeChild(textarea);
			}
			frappe.show_alert({ message: "Payload copied.", indicator: "green" });
		} catch (error) {
			this.show_error("Could not copy payload.", error);
		}
	}

	async save_dialog(dialog, method, values, message, module) {
		await this.call(method, { values });
		dialog.hide();
		frappe.show_alert({ message, indicator: "green" });
		await this.load_module(module);
		await this.bootstrap(false);
	}

	async toggle_category(row) {
		await this.call(this.method_paths.toggle_category, { name: row.name, active: cint(row.active) ? 0 : 1 });
		frappe.show_alert({ message: "Category updated.", indicator: "green" });
		await this.load_module("categories");
	}

	async toggle_mapping(row) {
		await this.call(this.method_paths.toggle_mapping, { name: row.name, active: cint(row.active) ? 0 : 1 });
		frappe.show_alert({ message: "Mapping updated.", indicator: "green" });
		await this.load_module("item_mapping");
	}

	async apply_category_tax(row) {
		const category = row.name || row.category_name;
		const count = cint(row.unmapped_item_count);
		if (!count) {
			frappe.msgprint("No unmapped items in this category.");
			return;
		}
		frappe.confirm(
			`Create item tax profiles for ${count} unmapped item(s) in "${category}"? Each profile will be marked Needs Review until HS codes are filled.`,
			async () => {
				const result = await this.call(this.method_paths.apply_category_tax, { category, only_unmapped: 1 });
				frappe.msgprint(`Created ${result.created || 0} mapping(s). Skipped ${result.skipped || 0}.`);
				await this.load_module("category_tax");
				await this.bootstrap(false);
			},
		);
	}

	async mark_reviewed(row) {
		await this.call(this.method_paths.mark_reviewed, { name: row.name });
		frappe.show_alert({ message: "Mapping marked reviewed.", indicator: "green" });
		await this.load_module("item_mapping");
	}

	on_search(event) {
		const module = $(event.currentTarget).data("module");
		const state = this.module_state(module);
		state.search = event.currentTarget.value || "";
		state.page = 1;
		$(event.currentTarget).siblings("[data-clear-search]").prop("hidden", !state.search);
		clearTimeout(this.state.timers[module]);
		this.state.timers[module] = setTimeout(() => this.load_module(module, true), 250);
	}

	clear_search(event) {
		const module = $(event.currentTarget).data("module");
		const state = this.module_state(module);
		state.search = "";
		state.page = 1;
		const $input = this.$root.find(`[data-tax-search][data-module="${module}"]`);
		$input.val("").trigger("focus");
		$(event.currentTarget).prop("hidden", true);
		this.load_module(module, true);
	}

	on_filter(event) {
		const $field = $(event.currentTarget);
		const module = $field.data("module");
		const key = $field.data("filter");
		const state = this.module_state(module);
		state.filters[key] = $field.val();
		state.page = 1;
		this.load_module(module);
	}

	change_page(direction) {
		const state = this.module_state();
		const max_page = Math.max(Math.ceil(state.total / this.state.page_size), 1);
		state.page = direction === "next" ? Math.min(state.page + 1, max_page) : Math.max(state.page - 1, 1);
		this.load_module(this.state.active_module);
	}

	select_row(event) {
		const index = cint($(event.currentTarget).data("row-index"));
		this.module_state().selected_row = this.module_state().rows[index] || null;
		this.$root.find(".lx-tax-table tr").removeClass("is-selected");
		$(event.currentTarget).addClass("is-selected");
		this.render_side_panel();
	}

	get_row(event) {
		const index = cint($(event.currentTarget).closest("tr").data("row-index"));
		return this.module_state().rows[index] || {};
	}

	refresh_icon_svg() {
		return `
			<svg class="lx-tax-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
				<path d="M20 6.5v5h-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
				<path d="M19.1 11A7.1 7.1 0 0 0 6.4 7.2L4 9.6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
				<path d="M4 17.5v-5h5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
				<path d="M4.9 13A7.1 7.1 0 0 0 17.6 16.8L20 14.4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>
			</svg>
		`;
	}

	calendar_icon_svg() {
		return `
			<svg class="lx-tax-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
				<path d="M7 3.8v3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path>
				<path d="M17 3.8v3" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path>
				<rect x="4" y="5.5" width="16" height="15" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"></rect>
				<path d="M4.8 10h14.4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"></path>
				<path d="M8 13.4h.01M12 13.4h.01M16 13.4h.01M8 16.6h.01M12 16.6h.01" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"></path>
			</svg>
		`;
	}

	action(label, name, row, enabled) {
		if (!enabled) return "";
		return `<button class="lx-tax-row-action" data-${name}>${this.escape(label)}</button>`;
	}

	async call(method, args = {}) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method,
				args,
				callback: (r) => resolve(r.message || {}),
				error: (r) => reject(r),
			});
		});
	}

	export_csv(module) {
		const rows = this.module_state(module).rows || [];
		if (!rows.length) {
			frappe.msgprint("No rows available to export on the current page.");
			return;
		}
		const keys = Object.keys(rows[0]);
		const csv = [keys.join(",")].concat(rows.map((row) => keys.map((key) => `"${String(row[key] ?? "").replace(/"/g, '""')}"`).join(","))).join("\n");
		const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
		const link = document.createElement("a");
		link.href = URL.createObjectURL(blob);
		link.download = module === "return_snapshots" ? "ledgix_return_tax_snapshots.csv" : "ledgix_invoice_tax_snapshots.csv";
		link.click();
		URL.revokeObjectURL(link.href);
	}

	theme_dialog(dialog) {
		dialog.$wrapper.addClass("ledgix-tax-themed-dialog");
		const apply_theme = () => dialog.$wrapper.find(".modal-dialog").addClass("lx-tax-dialog");
		apply_theme();
		window.setTimeout(apply_theme, 0);
	}

	can(permission) {
		return !!((this.state.boot.permissions || {})[permission]);
	}

	fbr_setup_needed(profile) {
		return !profile.ntn || !profile.strn__sales_tax_registration_number || !profile.pos_registration_number || !profile.province;
	}

	empty_html(label, hint) {
		return `<div class="lx-tax-empty"><strong>${this.escape(label)}</strong><span>${this.escape(hint)}</span></div>`;
	}

	show_error(message, error) {
		console.warn(message, error);
		frappe.msgprint(message);
	}

	escape(value) {
		if (value === undefined || value === null) return "";
		const text = String(value);
		if (frappe.utils?.escape_html) return frappe.utils.escape_html(text);
		return text.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
	}

	iso_date(date) {
		const copy = new Date(date.getTime() - (date.getTimezoneOffset() * 60000));
		return copy.toISOString().slice(0, 10);
	}

	add_days(date_value, days) {
		const date = new Date(`${date_value}T00:00:00`);
		date.setDate(date.getDate() + days);
		return this.iso_date(date);
	}

	month_start(date_value) {
		const date = new Date(`${date_value}T00:00:00`);
		return this.iso_date(new Date(date.getFullYear(), date.getMonth(), 1));
	}

	month_end(date_value) {
		const date = new Date(`${date_value}T00:00:00`);
		return this.iso_date(new Date(date.getFullYear(), date.getMonth() + 1, 0));
	}

	human(value) {
		return String(value || "").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
	}

	yesno(value) {
		return cint(value) ? "Yes" : "No";
	}

	display_value(value) {
		if (value === undefined || value === null || value === "") return "Not Set";
		return value;
	}

	status(value) {
		return `<span class="lx-tax-status ${cint(value) ? "is-on" : "is-off"}">${cint(value) ? "Active" : "Inactive"}</span>`;
	}

	money(value) {
		return flt(value || 0, 2).toFixed(2);
	}

	percent(value) {
		return `${flt(value || 0, 2).toFixed(2)}%`;
	}
}
