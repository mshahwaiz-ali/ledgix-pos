/* global frappe */

frappe.pages["ledgix-tax-center"].on_page_load = function (wrapper) {
	frappe.ledgix_tax_center = new LedgixTaxCenter(wrapper);
};

class LedgixTaxCenter {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: "Tax & FBR Center",
			single_column: true,
		});
		this.page.clear_actions_menu();
		this.methods = {
			boot: "ledgix_saas.api.tax_center.get_tax_center_boot",
			mappings: "ledgix_saas.api.tax_center.get_item_tax_mappings",
			categoryMappings: "ledgix_saas.api.tax_center.get_category_tax_mappings",
			applyCategory: "ledgix_saas.api.tax_center.apply_category_tax_to_items",
			markReviewed: "ledgix_saas.api.tax_center.mark_item_tax_reviewed",
			invoices: "ledgix_saas.api.tax_center.get_invoice_tax_snapshots",
			returns: "ledgix_saas.api.tax_center.get_return_tax_snapshots",
			fbrReadiness: "ledgix_saas.api.tax_center.get_fbr_readiness",
			fbrSettings: "ledgix_saas.api.fbr_settings.get_fbr_settings",
			fbrControl: "ledgix_saas.api.fbr_settings.get_fbr_control_state",
			fbrPreview: "ledgix_saas.api.fbr_preview.get_fbr_sale_preview",
			fbrValidateSandbox: "ledgix_saas.api.fbr_submission.validate_sale_with_fbr",
			fbrValidateProduction: "ledgix_saas.api.fbr_submission.validate_sale_with_fbr_production",
			fbrSubmitProduction: "ledgix_saas.api.fbr_submission.submit_sale_to_fbr",
			fbrLogs: "ledgix_saas.api.tax_center.get_fbr_submission_logs",
			fbrRegistrationStatus: "ledgix_saas.api.fbr_reference.get_sales_tax_registration_status",
			fbrRegistrationType: "ledgix_saas.api.fbr_reference.get_registration_type",
		};
		this.areas = [
			{ key: "overview", label: "Overview" },
			{ key: "mapping", label: "Tax Mapping" },
			{ key: "audit", label: "Invoice Audit" },
			{ key: "fbr", label: "FBR Operations" },
		];
		this.state = {
			area: this.get_initial_area(),
			loading: false,
			boot: {},
			mappingPage: 1,
			categoryPage: 1,
			mappingFilter: "",
			mappingSearch: "",
			mappings: { rows: [], total: 0, summary: {} },
			categories: { rows: [], total: 0, summary: {} },
			auditType: "sales",
			auditPage: 1,
			auditSearch: "",
			audit: { rows: [], total: 0 },
			fbr: {
				settings: {},
				control: {},
				readiness: {},
				preview: null,
				sale: "",
				logs: { rows: [], total: 0 },
				logPage: 1,
				registrationNo: "",
				registrationDate: frappe.datetime.get_today(),
				registrationStatus: null,
				registrationType: null,
			},
		};
		this.pageSize = 15;
		this.searchTimer = null;
		this.render_shell();
		this.bind_events();
		this.bootstrap();
	}

	get_initial_area() {
		const params = new URLSearchParams(window.location.search || "");
		const requested = params.get("area");
		return ["overview", "mapping", "audit", "fbr"].includes(requested) ? requested : "overview";
	}

	async call(method, args = {}) {
		const response = await frappe.call({ method, args, freeze: false });
		return response.message || {};
	}

	escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	money(value) {
		return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
	}

	yesno(value) {
		return Number(value || 0) ? "Yes" : "No";
	}

	render_shell() {
		this.$root = $(this.page.body).empty();
		this.$root.html(`
			<div class="lx-tax-v2">
				<div class="lx-tax-intro">
					<div>
						<div class="lx-tax-kicker">Compliance workspace</div>
						<h2>Tax & FBR Center</h2>
						<p>Bulk tax mapping, immutable invoice audit and controlled FBR operations. Standard master setup stays in native Frappe.</p>
					</div>
					<button class="btn btn-default btn-sm lx-tax-refresh">Refresh</button>
				</div>
				<div class="lx-tax-nav" role="tablist"></div>
				<div class="lx-tax-content"></div>
			</div>
		`);
		this.render_nav();
	}

	render_nav() {
		this.$root.find(".lx-tax-nav").html(this.areas.map(area => `
			<button class="lx-tax-nav-item ${area.key === this.state.area ? "active" : ""}" data-area="${area.key}" type="button">
				${this.escape(area.label)}
			</button>
		`).join(""));
	}

	bind_events() {
		this.$root.on("click", ".lx-tax-nav-item", (event) => this.switch_area($(event.currentTarget).data("area")));
		this.$root.on("click", ".lx-tax-refresh", () => this.bootstrap(true));
		this.$root.on("click", "[data-native-list]", (event) => this.open_list($(event.currentTarget).data("native-list")));
		this.$root.on("click", "[data-native-single]", (event) => this.open_single($(event.currentTarget).data("native-single")));
		this.$root.on("click", "[data-native-form]", (event) => this.open_form($(event.currentTarget).data("native-form"), $(event.currentTarget).data("name")));
		this.$root.on("click", "[data-new-doc]", (event) => frappe.new_doc($(event.currentTarget).data("new-doc")));
		this.$root.on("click", "[data-mark-reviewed]", (event) => this.mark_reviewed($(event.currentTarget).data("mark-reviewed")));
		this.$root.on("click", "[data-apply-category]", (event) => this.apply_category($(event.currentTarget).data("apply-category"), Number($(event.currentTarget).data("count") || 0)));
		this.$root.on("click", "[data-map-page]", (event) => this.change_mapping_page($(event.currentTarget).data("map-page")));
		this.$root.on("click", "[data-category-page]", (event) => this.change_category_page($(event.currentTarget).data("category-page")));
		this.$root.on("change", ".lx-map-filter", (event) => { this.state.mappingFilter = event.currentTarget.value || ""; this.state.mappingPage = 1; this.load_mapping(); });
		this.$root.on("input", ".lx-map-search", (event) => {
			this.state.mappingSearch = event.currentTarget.value || "";
			this.state.mappingPage = 1;
			clearTimeout(this.searchTimer);
			this.searchTimer = setTimeout(() => this.load_mapping(), 250);
		});
		this.$root.on("click", "[data-audit-type]", (event) => { this.state.auditType = $(event.currentTarget).data("audit-type"); this.state.auditPage = 1; this.load_audit(); });
		this.$root.on("input", ".lx-audit-search", (event) => {
			this.state.auditSearch = event.currentTarget.value || "";
			this.state.auditPage = 1;
			clearTimeout(this.searchTimer);
			this.searchTimer = setTimeout(() => this.load_audit(), 250);
		});
		this.$root.on("click", "[data-audit-page]", (event) => this.change_audit_page($(event.currentTarget).data("audit-page")));
		this.$root.on("click", ".lx-fbr-preview", () => this.preview_fbr());
		this.$root.on("click", ".lx-fbr-validate-sandbox", () => this.validate_fbr("sandbox"));
		this.$root.on("click", ".lx-fbr-validate-production", () => this.validate_fbr("production"));
		this.$root.on("click", ".lx-fbr-submit-production", () => this.submit_fbr());
		this.$root.on("click", ".lx-fbr-new-correction", () => this.start_fbr_correction());
		this.$root.on("input", ".lx-fbr-reg-no", (event) => { this.state.fbr.registrationNo = event.currentTarget.value || ""; });
		this.$root.on("change", ".lx-fbr-reg-date", (event) => { this.state.fbr.registrationDate = event.currentTarget.value || ""; });
		this.$root.on("click", ".lx-fbr-check-status", () => this.check_fbr_registration("status"));
		this.$root.on("click", ".lx-fbr-check-type", () => this.check_fbr_registration("type"));
		this.$root.on("click", "[data-fbr-log-page]", (event) => { this.state.fbr.logPage += $(event.currentTarget).data("fbr-log-page") === "next" ? 1 : -1; this.state.fbr.logPage = Math.max(this.state.fbr.logPage, 1); this.load_fbr_logs(); });
	}

	open_list(doctype) {
		if (doctype) frappe.set_route("List", doctype, "List");
	}

	open_single(doctype) {
		if (doctype) frappe.set_route("Form", doctype);
	}

	open_form(doctype, name) {
		if (doctype && name) frappe.set_route("Form", doctype, name);
	}

	async bootstrap(force = false) {
		try {
			this.set_loading(true);
			this.state.boot = await this.call(this.methods.boot);
			await this.load_area(force);
		} catch (error) {
			this.show_error("Tax & FBR Center could not load.", error);
		} finally {
			this.set_loading(false);
		}
	}

	async switch_area(area) {
		if (!this.areas.some(row => row.key === area) || area === this.state.area) return;
		this.state.area = area;
		window.history.replaceState({}, "", `/app/ledgix-tax-center?area=${area}`);
		this.render_nav();
		await this.load_area();
	}

	async load_area(force = false) {
		if (this.state.area === "overview") return this.render_overview();
		if (this.state.area === "mapping") return this.load_mapping(force);
		if (this.state.area === "audit") return this.load_audit(force);
		if (this.state.area === "fbr") return this.load_fbr(force);
	}

	render_overview() {
		const boot = this.state.boot || {};
		const profile = boot.profile || {};
		const counts = boot.counts || {};
		const control = boot.fbr_control_state || {};
		const cards = [
			["Tax engine", Number(profile.tax_enabled) ? "Enabled" : "Disabled", Number(profile.tax_enabled) ? "good" : "muted"],
			["Pricing", Number(profile.price_includes_tax) ? "Inclusive" : "Exclusive", "neutral"],
			["Mappings to review", counts.items_need_review || 0, Number(counts.items_need_review) ? "warn" : "good"],
			["Missing HS codes", counts.missing_hs_code || 0, Number(counts.missing_hs_code) ? "warn" : "good"],
			["FBR mode", control.mode || "Disabled", control.enabled ? "neutral" : "muted"],
		];
		const links = [
			["Tax Profile", "Business identity, defaults and tax behavior", "single", "Ledgix Tax Profile"],
			["Tax Categories", "Tax category master records", "list", "Ledgix Tax Category"],
			["Tax Rates", "Effective-dated tax rate history", "list", "Ledgix Tax Rate"],
			["Item Tax Profiles", "Per-item FBR and tax mapping", "list", "Ledgix Item Tax Profile"],
			["FBR Settings", "Credentials, mode and submission controls", "single", "Ledgix FBR Settings"],
			["FBR Submission Logs", "Submission and retry audit trail", "list", "Ledgix FBR Submission Log"],
			["FBR Correction Requests", "72-hour Board correction and Commissioner-approval tracking", "list", "Ledgix FBR Correction Request"],
		];
		this.$root.find(".lx-tax-content").html(`
			<section class="lx-tax-section">
				<div class="lx-tax-section-head"><div><h3>Compliance overview</h3><p>Live status from the tax profile and FBR controls.</p></div></div>
				<div class="lx-tax-metrics">${cards.map(([label, value, tone]) => this.metric(label, value, tone)).join("")}</div>
			</section>
			<section class="lx-tax-section">
				<div class="lx-tax-section-head"><div><h3>Native Frappe setup</h3><p>Standard masters stay in normal Frappe Forms and Lists instead of duplicate custom CRUD.</p></div></div>
				<div class="lx-native-grid">${links.map(([title, hint, kind, doctype]) => `
					<button class="lx-native-link" type="button" data-native-${kind}="${this.escape(doctype)}">
						<strong>${this.escape(title)}</strong><span>${this.escape(hint)}</span><b>Open →</b>
					</button>
				`).join("")}</div>
			</section>
		`);
	}

	metric(label, value, tone = "neutral") {
		return `<div class="lx-tax-metric is-${tone}"><span>${this.escape(label)}</span><strong>${this.escape(value)}</strong></div>`;
	}

	async load_mapping() {
		try {
			this.render_loading("Loading tax mapping…");
			const [mappings, categories] = await Promise.all([
				this.call(this.methods.mappings, { page: this.state.mappingPage, page_size: this.pageSize, search: this.state.mappingSearch, filter_type: this.state.mappingFilter }),
				this.call(this.methods.categoryMappings, { page: this.state.categoryPage, page_size: 8 }),
			]);
			this.state.mappings = mappings || { rows: [], total: 0, summary: {} };
			this.state.categories = categories || { rows: [], total: 0, summary: {} };
			this.render_mapping();
		} catch (error) { this.show_error("Tax mapping could not load.", error); }
	}

	render_mapping() {
		const mapping = this.state.mappings || {};
		const summary = mapping.summary || {};
		const categories = this.state.categories || {};
		this.$root.find(".lx-tax-content").html(`
			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div><h3>Tax mapping</h3><p>Review exceptions here; edit individual records in native Frappe forms.</p></div>
					<div class="lx-tax-actions"><button class="btn btn-default btn-sm" data-native-list="Ledgix Item Tax Profile">Open all profiles</button><button class="btn btn-primary btn-sm" data-new-doc="Ledgix Item Tax Profile">New mapping</button></div>
				</div>
				<div class="lx-tax-metrics lx-tax-metrics-compact">
					${this.metric("Profiles", summary.total_mappings || 0)}${this.metric("Needs review", summary.needs_review || 0, Number(summary.needs_review) ? "warn" : "good")}${this.metric("Missing HS code", summary.missing_hs_code || 0, Number(summary.missing_hs_code) ? "warn" : "good")}${this.metric("Active taxable", summary.active_taxable || 0)}
				</div>
				<div class="lx-tax-toolbar"><input class="form-control lx-map-search" value="${this.escape(this.state.mappingSearch)}" placeholder="Search item, tax category or HS code"><select class="form-control lx-map-filter"><option value="" ${!this.state.mappingFilter ? "selected" : ""}>All profiles</option><option value="needs_review" ${this.state.mappingFilter === "needs_review" ? "selected" : ""}>Needs review</option><option value="missing_hs_code" ${this.state.mappingFilter === "missing_hs_code" ? "selected" : ""}>Missing HS code</option><option value="taxable" ${this.state.mappingFilter === "taxable" ? "selected" : ""}>Taxable</option><option value="exempt" ${this.state.mappingFilter === "exempt" ? "selected" : ""}>Exempt</option></select></div>
				${this.mapping_table(mapping.rows || [])}
				${this.pagination(this.state.mappingPage, mapping.total || 0, "map")}
			</section>
			<section class="lx-tax-section">
				<div class="lx-tax-section-head"><div><h3>Category rollout</h3><p>Apply configured category defaults only to currently unmapped active items.</p></div><button class="btn btn-default btn-sm" data-native-list="Ledgix Category">Open categories</button></div>
				${this.category_table(categories.rows || [])}
				${this.pagination(this.state.categoryPage, categories.total || 0, "category", 8)}
			</section>
		`);
	}

	mapping_table(rows) {
		if (!rows.length) return this.empty("No item tax profiles match the current filter.");
		return `<div class="lx-tax-table-wrap"><table class="lx-tax-table"><thead><tr><th>Item</th><th>Source</th><th>Tax Category</th><th>HS Code</th><th>Sales Type</th><th>Review</th><th></th></tr></thead><tbody>${rows.map(row => `<tr>
			<td><strong>${this.escape(row.item_name || row.item)}</strong><small>${this.escape(row.item)}</small></td>
			<td>${this.escape(row.tax_source_label || "Item Override")}</td>
			<td>${this.escape(row.tax_category || "—")}</td>
			<td>${this.escape(row.hs_code || "Missing")}</td>
			<td>${this.escape(row.sales_type || "—")}</td>
			<td>${Number(row.needs_review) ? '<span class="lx-status is-warn">Needs review</span>' : '<span class="lx-status is-good">Reviewed</span>'}</td>
			<td class="lx-row-actions"><button class="btn btn-xs btn-default" data-native-form="Ledgix Item Tax Profile" data-name="${this.escape(row.name)}">Open</button>${Number(row.needs_review) ? `<button class="btn btn-xs btn-default" data-mark-reviewed="${this.escape(row.name)}">Mark reviewed</button>` : ""}</td>
		</tr>`).join("")}</tbody></table></div>`;
	}

	category_table(rows) {
		if (!rows.length) return this.empty("No product categories found.");
		return `<div class="lx-tax-table-wrap"><table class="lx-tax-table"><thead><tr><th>Category</th><th>Tax defaults</th><th>Tax category</th><th>Items</th><th>Unmapped</th><th></th></tr></thead><tbody>${rows.map(row => `<tr>
			<td><strong>${this.escape(row.category_name || row.name)}</strong></td>
			<td>${Number(row.tax_defaults_enabled) ? '<span class="lx-status is-good">Enabled</span>' : '<span class="lx-status">Off</span>'}</td>
			<td>${this.escape(row.default_tax_category || "—")}</td>
			<td>${this.escape(row.item_count || 0)}</td>
			<td>${this.escape(row.unmapped_item_count || 0)}</td>
			<td class="lx-row-actions"><button class="btn btn-xs btn-default" data-native-form="Ledgix Category" data-name="${this.escape(row.name)}">Open</button>${Number(row.tax_defaults_enabled) && Number(row.unmapped_item_count) ? `<button class="btn btn-xs btn-primary" data-apply-category="${this.escape(row.name)}" data-count="${Number(row.unmapped_item_count)}">Apply to unmapped</button>` : ""}</td>
		</tr>`).join("")}</tbody></table></div>`;
	}

	async mark_reviewed(name) {
		try { await this.call(this.methods.markReviewed, { name }); frappe.show_alert({ message: "Mapping marked reviewed", indicator: "green" }); await this.load_mapping(); }
		catch (error) { this.show_error("Could not mark mapping reviewed.", error); }
	}

	apply_category(category, count) {
		frappe.confirm(`Create tax profiles for ${count} unmapped item(s) in ${this.escape(category)}?`, async () => {
			try {
				const result = await this.call(this.methods.applyCategory, { category, only_unmapped: 1 });
				frappe.show_alert({ message: `Created ${result.created || 0} mapping(s)`, indicator: "green" }, 5);
				await this.load_mapping();
			} catch (error) { this.show_error("Could not apply category tax defaults.", error); }
		});
	}

	change_mapping_page(direction) {
		this.state.mappingPage = Math.max(1, this.state.mappingPage + (direction === "next" ? 1 : -1));
		this.load_mapping();
	}

	change_category_page(direction) {
		this.state.categoryPage = Math.max(1, this.state.categoryPage + (direction === "next" ? 1 : -1));
		this.load_mapping();
	}

	async load_audit() {
		try {
			this.render_loading("Loading immutable tax snapshots…");
			const method = this.state.auditType === "returns" ? this.methods.returns : this.methods.invoices;
			this.state.audit = await this.call(method, { page: this.state.auditPage, page_size: this.pageSize, search: this.state.auditSearch });
			this.render_audit();
		} catch (error) { this.show_error("Invoice audit could not load.", error); }
	}

	render_audit() {
		const data = this.state.audit || {};
		const isReturns = this.state.auditType === "returns";
		this.$root.find(".lx-tax-content").html(`
			<section class="lx-tax-section">
				<div class="lx-tax-section-head"><div><h3>Invoice audit</h3><p>Read-only tax snapshots captured at transaction time. Current tax masters cannot rewrite history.</p></div></div>
				<div class="lx-tax-toolbar lx-audit-toolbar"><div class="lx-segment"><button class="${!isReturns ? "active" : ""}" data-audit-type="sales">Sales</button><button class="${isReturns ? "active" : ""}" data-audit-type="returns">Returns</button></div><input class="form-control lx-audit-search" value="${this.escape(this.state.auditSearch)}" placeholder="Search sale, return, item, tax category or HS code"></div>
				${this.audit_table(data.rows || [], isReturns)}
				${this.pagination(this.state.auditPage, data.total || 0, "audit")}
			</section>
		`);
	}

	audit_table(rows, isReturns) {
		if (!rows.length) return this.empty("No tax snapshots match the current search.");
		return `<div class="lx-tax-table-wrap"><table class="lx-tax-table"><thead><tr><th>${isReturns ? "Return / Sale" : "Sale"}</th><th>Item</th><th>Qty</th><th>Taxable</th><th>Tax</th><th>Net</th><th>Category / Rate</th><th>FBR</th></tr></thead><tbody>${rows.map(row => `<tr>
			<td>${isReturns ? `<strong>${this.escape(row.sales_return)}</strong><small>${this.escape(row.original_sale || "")}</small>` : `<strong>${this.escape(row.sale)}</strong>`}</td>
			<td>${this.escape(row.item)}</td>
			<td>${this.escape(isReturns ? row.returned_qty : row.qty)}</td>
			<td>${this.money(row.taxable_amount || row.returned_taxable_amount)}</td>
			<td>${this.money(row.tax_amount || row.returned_tax_amount)}</td>
			<td>${this.money(row.net_amount)}</td>
			<td><strong>${this.escape(row.tax_category || "—")}</strong><small>${this.escape(row.tax_rate || row.original_tax_rate || 0)}%</small></td>
			<td><span>${this.escape(row.hs_code || "No HS")}</span><small>${this.escape(row.sales_type || "")}</small></td>
		</tr>`).join("")}</tbody></table></div>`;
	}

	change_audit_page(direction) {
		this.state.auditPage = Math.max(1, this.state.auditPage + (direction === "next" ? 1 : -1));
		this.load_audit();
	}

	async load_fbr() {
		try {
			this.render_loading("Loading FBR controls…");
			const [settings, control, readiness, logs] = await Promise.all([
				this.call(this.methods.fbrSettings),
				this.call(this.methods.fbrControl),
				this.call(this.methods.fbrReadiness),
				this.call(this.methods.fbrLogs, { page: this.state.fbr.logPage, page_size: 10 }),
			]);
			Object.assign(this.state.fbr, { settings: settings || {}, control: control || {}, readiness: readiness || {}, logs: logs || { rows: [], total: 0 } });
			this.render_fbr();
		} catch (error) { this.show_error("FBR operations could not load.", error); }
	}

	async load_fbr_logs() {
		try {
			this.state.fbr.logs = await this.call(this.methods.fbrLogs, { page: this.state.fbr.logPage, page_size: 10 });
			this.render_fbr();
		} catch (error) { this.show_error("FBR logs could not load.", error); }
	}

	render_fbr() {
		const fbr = this.state.fbr;
		const settings = fbr.settings || {};
		const control = fbr.control || {};
		const readiness = fbr.readiness || {};
		const preview = fbr.preview || null;
		const previewReady = !!preview?.readiness?.ready;
		const referenceReady = !!control.enabled && ["Sandbox", "Production"].includes(control.mode || settings.mode);
		this.$root.find(".lx-tax-content").html(`
			<section class="lx-tax-section">
				<div class="lx-tax-section-head"><div><h3>FBR operations</h3><p>Preview and validate from frozen sale snapshots; live production submission remains explicitly gated.</p></div><div class="lx-tax-actions"><button class="btn btn-default btn-sm" data-native-single="Ledgix FBR Settings">FBR Settings</button><button class="btn btn-default btn-sm" data-native-list="Ledgix FBR Submission Log">All logs</button><button class="btn btn-default btn-sm" data-native-list="Ledgix FBR Correction Request">Correction requests</button></div></div>
				<div class="lx-tax-metrics lx-tax-metrics-compact">
					${this.metric("Mode", control.mode || settings.mode || "Disabled")}${this.metric("Enabled", control.enabled ? "Yes" : "No", control.enabled ? "good" : "muted")}${this.metric("Submit trigger", control.submit_trigger || settings.submit_trigger || "Manual")}${this.metric("Readiness", `${readiness.ready_score || 0}%`, Number(readiness.ready_score || 0) >= 100 ? "good" : "warn")}
				</div>
				${this.readiness_html(readiness)}
			</section>
			<section class="lx-tax-section">
				<div class="lx-tax-section-head"><div><h3>Official registration check</h3><p>Read-only FBR STATL and Get_Reg_Type lookups. The raw FBR response is shown without client-side reinterpretation.</p></div></div>
				<div class="lx-tax-toolbar">
					<input class="form-control lx-fbr-reg-no" value="${this.escape(fbr.registrationNo || "")}" placeholder="NTN / registration number">
					<input type="date" class="form-control lx-fbr-reg-date" value="${this.escape(fbr.registrationDate || frappe.datetime.get_today())}">
				</div>
				<div class="lx-fbr-actions">
					<button class="btn btn-default lx-fbr-check-status" ${referenceReady ? "" : "disabled"}>Check STATL Status</button>
					<button class="btn btn-default lx-fbr-check-type" ${referenceReady ? "" : "disabled"}>Check Registration Type</button>
				</div>
				${referenceReady ? "" : '<div class="lx-callout is-warning"><strong>Reference API unavailable</strong><p>Enable FBR in Sandbox or Production mode and configure the active token first.</p></div>'}
				${this.fbr_reference_results_html(fbr.registrationStatus, fbr.registrationType)}
			</section>
			<section class="lx-tax-section">
				<div class="lx-tax-section-head"><div><h3>Sale payload</h3><p>Select a submitted sale, inspect the frozen payload, then validate or submit only when the configured mode permits it.</p></div></div>
				<div class="lx-fbr-sale-row"><div class="lx-fbr-sale-control"></div><button class="btn btn-primary lx-fbr-preview">Preview payload</button></div>
				${preview ? this.fbr_preview_html(preview) : this.empty("No sale preview loaded.")}
				<div class="lx-fbr-actions">
					<button class="btn btn-default lx-fbr-validate-sandbox" ${preview?.can_validate_now ? "" : "disabled"}>Validate Sandbox</button>
					<button class="btn btn-default lx-fbr-validate-production" ${previewReady && control.can_manual_validate && control.mode === "Production" ? "" : "disabled"}>Production Validate</button>
					<button class="btn btn-danger lx-fbr-submit-production" ${preview?.can_submit_now ? "" : "disabled"}>Production Submit</button>
				</div>
			</section>
			<section class="lx-tax-section">
				<div class="lx-tax-section-head"><div><h3>Invoice correction tracking</h3><p>Track bona fide FBR invoice Cancel, Delete or Edit actions against the official 72-hour window.</p></div><div class="lx-tax-actions"><button class="btn btn-primary btn-sm lx-fbr-new-correction">New for selected sale</button><button class="btn btn-default btn-sm" data-native-list="Ledgix FBR Correction Request">Open requests</button></div></div>
				<div class="lx-callout is-warning"><strong>Tracking only</strong><p>Ledgix does not call or imitate an undocumented FBR Board correction/cancellation API. Complete the actual action through the Board/PRAL process and record its reference here. After 72 hours, Commissioner approval must be tracked before completion.</p></div>
			</section>
			<section class="lx-tax-section">
				<div class="lx-tax-section-head"><div><h3>Recent FBR activity</h3><p>Safe operational metadata; credentials are never displayed here.</p></div></div>
				${this.fbr_logs_table((fbr.logs || {}).rows || [])}
				${this.pagination(fbr.logPage, (fbr.logs || {}).total || 0, "fbr-log", 10)}
			</section>
		`);
		this.mount_fbr_sale_control();
	}

	readiness_html(data) {
		const checks = data.checks || [];
		if (!checks.length) return "";
		return `<div class="lx-readiness-grid">${checks.map(check => `<div class="lx-readiness-row"><span>${this.escape(check.label)}</span><strong class="${check.ready ? "is-ready" : (check.level === "warning" ? "is-warning" : "is-missing")}">${check.ready ? "Ready" : (check.level === "warning" ? "Attention" : "Missing")}</strong></div>`).join("")}</div>`;
	}

	mount_fbr_sale_control() {
		const $holder = this.$root.find(".lx-fbr-sale-control");
		if (!$holder.length) return;
		let control;
		control = frappe.ui.form.make_control({
			parent: $holder[0],
			df: {
				fieldname: "fbr_sale",
				label: "Submitted Sale",
				fieldtype: "Link",
				options: "Ledgix Sale",
				get_query: () => ({ filters: { docstatus: 1 } }),
				onchange: () => { this.state.fbr.sale = control.get_value() || ""; this.state.fbr.preview = null; },
			},
			render_input: true,
		});
		control.set_value(this.state.fbr.sale || "");
	}

	fbr_reference_results_html(statusResult, typeResult) {
		const blocks = [];
		if (statusResult) blocks.push(this.fbr_reference_result_html("STATL status response", statusResult));
		if (typeResult) blocks.push(this.fbr_reference_result_html("Registration type response", typeResult));
		return blocks.length ? blocks.join("") : this.empty("No official registration lookup performed yet.");
	}

	fbr_reference_result_html(title, result) {
		const payload = JSON.stringify(result?.data ?? result ?? {}, null, 2);
		return `<div class="lx-fbr-preview-card"><details class="lx-payload" open><summary>${this.escape(title)}</summary><pre>${this.escape(payload)}</pre></details></div>`;
	}

	async check_fbr_registration(kind) {
		const registrationNo = (this.state.fbr.registrationNo || "").trim();
		const postingDate = (this.state.fbr.registrationDate || "").trim();
		if (!registrationNo) return frappe.msgprint("Enter an NTN / registration number first.");
		if (kind === "status" && !postingDate) return frappe.msgprint("Select the STATL lookup date first.");
		try {
			const method = kind === "status" ? this.methods.fbrRegistrationStatus : this.methods.fbrRegistrationType;
			const args = kind === "status" ? { registration_no: registrationNo, posting_date: postingDate } : { registration_no: registrationNo };
			const result = await this.call(method, args);
			if (kind === "status") this.state.fbr.registrationStatus = result;
			else this.state.fbr.registrationType = result;
			this.render_fbr();
			frappe.show_alert({ message: "Official FBR registration lookup completed", indicator: "green" }, 4);
		} catch (error) {
			this.show_error("FBR registration lookup failed.", error);
		}
	}

	start_fbr_correction() {
		const sale = (this.state.fbr.sale || "").trim();
		if (!sale) return frappe.msgprint("Select a submitted FBR sale first.");
		frappe.new_doc("Ledgix FBR Correction Request", { sale });
	}

	fbr_preview_html(preview) {
		const readiness = preview.readiness || {};
		const sale = preview.sale_summary || {};
		const errors = readiness.errors || [];
		const warnings = readiness.warnings || [];
		const payload = preview.payload ? JSON.stringify(preview.payload, null, 2) : "";
		return `<div class="lx-fbr-preview-card">
			<div class="lx-fbr-preview-summary"><div><span>Sale</span><strong>${this.escape(preview.sale_name || sale.name || "—")}</strong></div><div><span>Customer</span><strong>${this.escape(sale.customer || "—")}</strong></div><div><span>Grand total</span><strong>${this.money(sale.grand_total || sale.total_amount)}</strong></div><div><span>Readiness</span><strong>${readiness.ready ? "Ready" : "Not ready"}</strong></div></div>
			${errors.length ? `<div class="lx-callout is-error"><strong>Errors</strong><ul>${errors.map(item => `<li>${this.escape(item)}</li>`).join("")}</ul></div>` : ""}
			${warnings.length ? `<div class="lx-callout is-warning"><strong>Warnings</strong><ul>${warnings.map(item => `<li>${this.escape(item)}</li>`).join("")}</ul></div>` : ""}
			${payload ? `<details class="lx-payload"><summary>Payload JSON</summary><pre>${this.escape(payload)}</pre></details>` : ""}
		</div>`;
	}

	async preview_fbr() {
		const sale = (this.state.fbr.sale || "").trim();
		if (!sale) return frappe.msgprint("Select a submitted sale first.");
		try { this.state.fbr.preview = await this.call(this.methods.fbrPreview, { sale_name: sale }); this.render_fbr(); }
		catch (error) { this.show_error("Could not preview FBR payload.", error); }
	}

	validate_fbr(environment) {
		const sale = (this.state.fbr.sale || "").trim();
		if (!sale || !this.state.fbr.preview) return frappe.msgprint("Preview the sale first.");
		const production = environment === "production";
		frappe.confirm(production ? "Send this frozen payload to the FBR Production Validate API? This does not issue a final invoice number." : "Send this frozen payload to FBR Sandbox Validate?", async () => {
			try {
				const method = production ? this.methods.fbrValidateProduction : this.methods.fbrValidateSandbox;
				const result = await this.call(method, { sale_name: sale });
				frappe.msgprint({ title: production ? "Production validation" : "Sandbox validation", message: this.escape(result.error_message || result.status || "Validation completed."), indicator: result.status === "Failed" ? "red" : "green" });
				await this.load_fbr();
				this.state.fbr.sale = sale;
				await this.preview_fbr();
			} catch (error) { this.show_error("FBR validation failed.", error); }
		});
	}

	submit_fbr() {
		const sale = (this.state.fbr.sale || "").trim();
		if (!sale || !this.state.fbr.preview?.can_submit_now) return frappe.msgprint("This sale is not currently eligible for Production Submit.");
		frappe.confirm(`Submit ${this.escape(sale)} to the LIVE FBR production system? This may issue an official FBR invoice number.`, async () => {
			try {
				const result = await this.call(this.methods.fbrSubmitProduction, { sale_name: sale });
				frappe.msgprint({ title: "FBR Production Submit", message: this.escape(result.error_message || result.status || "Submission completed."), indicator: result.status === "Failed" ? "red" : "green" });
				await this.load_fbr();
			} catch (error) { this.show_error("FBR production submission failed.", error); }
		});
	}

	fbr_logs_table(rows) {
		if (!rows.length) return this.empty("No FBR submission activity found.");
		return `<div class="lx-tax-table-wrap"><table class="lx-tax-table"><thead><tr><th>Reference</th><th>Type</th><th>Status</th><th>Attempts</th><th>Error</th><th>Submitted</th></tr></thead><tbody>${rows.map(row => `<tr><td><strong>${this.escape(row.reference_name || "—")}</strong><small>${this.escape(row.reference_doctype || "")}</small></td><td>${this.escape(row.invoice_type || "—")}</td><td>${this.escape(row.fbr_status || "—")}</td><td>${this.escape(row.attempt_count || 0)}</td><td>${this.escape(row.error_message || row.error_code || "—")}</td><td>${this.escape(row.submitted_at || "—")}</td></tr>`).join("")}</tbody></table></div>`;
	}

	pagination(page, total, prefix, pageSize = this.pageSize) {
		const pages = Math.max(Math.ceil(Number(total || 0) / pageSize), 1);
		if (pages <= 1) return "";
		const attr = prefix === "map" ? "data-map-page" : prefix === "category" ? "data-category-page" : prefix === "audit" ? "data-audit-page" : "data-fbr-log-page";
		return `<div class="lx-tax-pagination"><span>Page ${page} of ${pages} · ${total} records</span><div><button class="btn btn-xs btn-default" ${attr}="prev" ${page <= 1 ? "disabled" : ""}>Previous</button><button class="btn btn-xs btn-default" ${attr}="next" ${page >= pages ? "disabled" : ""}>Next</button></div></div>`;
	}

	render_loading(message) {
		this.$root.find(".lx-tax-content").html(`<div class="lx-tax-loading">${this.escape(message)}</div>`);
	}

	empty(message) {
		return `<div class="lx-tax-empty">${this.escape(message)}</div>`;
	}

	set_loading(value) {
		this.state.loading = !!value;
		this.$root.toggleClass("is-loading", !!value);
	}

	show_error(message, error) {
		console.error(message, error);
		frappe.msgprint({ title: "Tax & FBR Center", message, indicator: "red" });
	}
}
