/* global frappe, $ */

frappe.pages["ledgix-tax-center"].on_page_load = function (wrapper) {
	frappe.ledgix_tax_center = new LedgixFBRV2Center(wrapper);
};

class LedgixFBRV2Center {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: "Tax & FBR Center",
			single_column: true,
		});
		this.page.clear_actions_menu();

		this.methods = {
			boot: "ledgix_saas.api.fbr_v2_center.get_v2_center_boot",
			mappings: "ledgix_saas.api.fbr_v2_center.get_v2_item_mappings",
			syncCore: "ledgix_saas.api.fbr_reference_v2.sync_core_reference_data",
			readiness: "ledgix_saas.api.fbr_v2_center.evaluate_v2_invoice_readiness",
		};

		this.areas = [
			{ key: "overview", label: "Overview" },
			{ key: "tax", label: "ERPNext Tax Setup" },
			{ key: "fbr", label: "FBR Integration" },
			{ key: "products", label: "Product Compliance" },
			{ key: "certification", label: "Certification & Readiness" },
		];

		this.state = {
			area: this.get_initial_area(),
			loading: false,
			boot: {},
			selectedProfile: "",
			mappingPage: 1,
			mappingSearch: "",
			mappingReview: "All",
			mappings: { rows: [], total: 0 },
			referenceDoctype: "Sales Invoice",
			referenceName: "",
			readiness: null,
		};

		this.pageSize = 20;
		this.searchTimer = null;
		this.render_shell();
		this.bind_events();
		this.bootstrap();
	}

	get_initial_area() {
		const params = new URLSearchParams(window.location.search || "");
		const requested = params.get("area");
		return this.areas.some(row => row.key === requested) ? requested : "overview";
	}

	async call(method, args = {}) {
		const response = await frappe.call({ method, args, freeze: false });
		return response.message || {};
	}

	escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
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
						<div class="lx-tax-kicker">ERPNext-native compliance workspace</div>
						<h2>Tax & FBR Center</h2>
						<p>ERPNext owns monetary tax and accounting. Ledgix manages FBR classification, reference data, certification and readiness.</p>
					</div>
					<button class="btn btn-default btn-sm lx-tax-refresh" type="button">Refresh</button>
				</div>
				<div class="lx-tax-nav" role="tablist"></div>
				<div class="lx-tax-content"></div>
			</div>
		`);
		this.render_nav();
	}

	render_nav() {
		this.$root.find(".lx-tax-nav").html(
			this.areas.map(area => `
				<button class="lx-tax-nav-item ${area.key === this.state.area ? "active" : ""}" data-area="${area.key}" type="button">
					${this.escape(area.label)}
				</button>
			`).join(""),
		);
	}

	bind_events() {
		this.$root.on("click", ".lx-tax-nav-item", event => this.switch_area($(event.currentTarget).data("area")));
		this.$root.on("click", ".lx-tax-refresh", () => this.bootstrap(true));
		this.$root.on("click", "[data-native-list]", event => this.open_list($(event.currentTarget).data("native-list")));
		this.$root.on("click", "[data-native-form]", event => this.open_form($(event.currentTarget).data("native-form"), $(event.currentTarget).data("name")));
		this.$root.on("click", "[data-new-doc]", event => frappe.new_doc($(event.currentTarget).data("new-doc")));
		this.$root.on("change", ".lx-v2-profile", event => {
			this.state.selectedProfile = event.currentTarget.value || "";
		});
		this.$root.on("click", ".lx-v2-sync-core", () => this.sync_core_references());
		this.$root.on("input", ".lx-v2-map-search", event => {
			this.state.mappingSearch = event.currentTarget.value || "";
			this.state.mappingPage = 1;
			clearTimeout(this.searchTimer);
			this.searchTimer = setTimeout(() => this.load_mappings(), 250);
		});
		this.$root.on("change", ".lx-v2-map-review", event => {
			this.state.mappingReview = event.currentTarget.value || "All";
			this.state.mappingPage = 1;
			this.load_mappings();
		});
		this.$root.on("click", "[data-map-page]", event => {
			const direction = $(event.currentTarget).data("map-page");
			this.state.mappingPage = Math.max(1, this.state.mappingPage + (direction === "next" ? 1 : -1));
			this.load_mappings();
		});
		this.$root.on("change", ".lx-v2-readiness-doctype", event => {
			this.state.referenceDoctype = event.currentTarget.value || "Sales Invoice";
			this.state.referenceName = "";
			this.state.readiness = null;
			this.mount_invoice_control();
		});
		this.$root.on("click", ".lx-v2-check-readiness", () => this.check_readiness());
	}

	open_list(doctype) {
		if (doctype) frappe.set_route("List", doctype, "List");
	}

	open_form(doctype, name) {
		if (doctype && name) frappe.set_route("Form", doctype, name);
	}

	async bootstrap() {
		try {
			this.set_loading(true);
			this.state.boot = await this.call(this.methods.boot);
			const profiles = this.state.boot.profiles || [];
			if (!profiles.some(row => row.name === this.state.selectedProfile)) {
				this.state.selectedProfile = profiles[0]?.name || "";
			}
			await this.load_area();
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

	async load_area() {
		if (this.state.area === "overview") return this.render_overview();
		if (this.state.area === "tax") return this.render_tax_setup();
		if (this.state.area === "fbr") return this.render_fbr_integration();
		if (this.state.area === "products") return this.load_mappings();
		if (this.state.area === "certification") return this.render_certification();
	}

	metric(label, value, tone = "neutral") {
		return `<div class="lx-tax-metric is-${tone}"><span>${this.escape(label)}</span><strong>${this.escape(value)}</strong></div>`;
	}

	native_link(title, hint, doctype, action = "list") {
		const attr = action === "new" ? "data-new-doc" : "data-native-list";
		return `
			<button class="lx-native-link" type="button" ${attr}="${this.escape(doctype)}">
				<strong>${this.escape(title)}</strong>
				<span>${this.escape(hint)}</span>
				<b>${action === "new" ? "Create →" : "Open →"}</b>
			</button>
		`;
	}

	render_overview() {
		const boot = this.state.boot || {};
		const mapping = boot.mapping || {};
		const refs = boot.reference_totals || {};
		const cert = boot.certification || {};
		const safety = boot.production_safety || {};
		const profiles = boot.profiles || [];

		const cards = [
			["Architecture", boot.architecture || "ERPNext Native + FBR V2", "good"],
			["FBR company profiles", profiles.length, profiles.length ? "good" : "warn"],
			["Mappings needing review", mapping.needs_review || 0, Number(mapping.needs_review) ? "warn" : "good"],
			["Current FBR reference rows", refs.current || 0, Number(refs.current) ? "good" : "warn"],
			["Completed certifications", cert.complete || 0, Number(cert.complete) ? "good" : "neutral"],
			["Production armed profiles", safety.armed_profiles || 0, Number(safety.armed_profiles) ? "warn" : "good"],
		];

		this.$root.find(".lx-tax-content").html(`
			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div>
						<h3>Architecture status</h3>
						<p>One monetary authority: ERPNext. This center contains no Production invoice-submit action.</p>
					</div>
				</div>
				<div class="lx-tax-metrics">${cards.map(([label, value, tone]) => this.metric(label, value, tone)).join("")}</div>
			</section>

			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div>
						<h3>Setup flow</h3>
						<p>Configure native ERPNext tax first, then FBR integration, product classification and Sandbox certification.</p>
					</div>
				</div>
				<div class="lx-native-grid">
					${this.native_link("ERPNext Tax Setup", "Tax Categories, Tax Rules, Sales Tax Templates and Item Tax Templates", "Tax Rule")}
					${this.native_link("FBR Integration Profiles", "Company-scoped credentials, provider, onboarding and safety controls", "Ledgix FBR Integration Profile")}
					${this.native_link("FBR Item Mappings", "HS Code, UOM, Sale Type, rate reference and regulatory metadata only", "Ledgix FBR Item Mapping")}
					${this.native_link("Sandbox Certification", "Business Nature/Sector scenario evidence and certification lifecycle", "Ledgix FBR Sandbox Certification")}
				</div>
			</section>
		`);
	}

	render_tax_setup() {
		const tax = this.state.boot.erpnext_tax || {};
		const cards = [
			["Tax Categories", tax.tax_categories || 0],
			["Tax Rules", tax.tax_rules || 0],
			["Sales Tax Templates", tax.sales_tax_templates || 0],
			["Item Tax Templates", tax.item_tax_templates || 0],
		];

		this.$root.find(".lx-tax-content").html(`
			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div>
						<h3>ERPNext monetary tax authority</h3>
						<p>Rates, tax calculation, invoice totals and GL remain in standard ERPNext masters.</p>
					</div>
				</div>
				<div class="lx-tax-metrics">${cards.map(([label, value]) => this.metric(label, value)).join("")}</div>
			</section>

			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div><h3>Native tax masters</h3><p>Ledgix does not duplicate these monetary authorities.</p></div>
				</div>
				<div class="lx-native-grid">
					${this.native_link("Tax Categories", "Customer/transaction tax categorization", "Tax Category")}
					${this.native_link("Tax Rules", "Select tax templates by Company, Customer, Item and Tax Category", "Tax Rule")}
					${this.native_link("Sales Taxes and Charges Templates", "Authoritative sales tax rows/accounts/calculation types", "Sales Taxes and Charges Template")}
					${this.native_link("Item Tax Templates", "Item-specific native ERPNext tax treatment", "Item Tax Template")}
					${this.native_link("Accounts", "Tax liability and other authoritative ledger accounts", "Account")}
				</div>
			</section>
		`);
	}

	profile_options() {
		const profiles = this.state.boot.profiles || [];
		if (!profiles.length) return '<option value="">No V2 profile configured</option>';
		return profiles.map(row => `
			<option value="${this.escape(row.name)}" ${row.name === this.state.selectedProfile ? "selected" : ""}>
				${this.escape(row.company)} · ${this.escape(row.mode || "Disabled")}
			</option>
		`).join("");
	}

	render_fbr_integration() {
		const boot = this.state.boot || {};
		const profiles = boot.profiles || [];
		const refs = boot.references || [];
		const canAdmin = Boolean(boot.is_admin);

		this.$root.find(".lx-tax-content").html(`
			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div>
						<h3>Company-scoped FBR integration</h3>
						<p>Credentials, LI/PRAL provider, onboarding, Business Nature/Sector and safety controls live in the V2 profile.</p>
					</div>
					<div class="lx-tax-actions">
						<button class="btn btn-default btn-sm" data-native-list="Ledgix FBR Integration Profile">Open profiles</button>
						${canAdmin ? '<button class="btn btn-primary btn-sm" data-new-doc="Ledgix FBR Integration Profile">New profile</button>' : ""}
					</div>
				</div>
				${this.profile_table(profiles)}
			</section>

			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div>
						<h3>Official FBR reference data</h3>
						<p>Core reference sync is GET-only. It cannot validate or submit an invoice and cannot arm Production.</p>
					</div>
					<div class="lx-tax-actions">
						<select class="form-control lx-v2-profile">${this.profile_options()}</select>
						${canAdmin ? '<button class="btn btn-primary btn-sm lx-v2-sync-core" type="button">Sync core references</button>' : ""}
						<button class="btn btn-default btn-sm" data-native-list="Ledgix FBR Reference Data">Open cache</button>
					</div>
				</div>
				${this.reference_table(refs)}
			</section>
		`);
	}

	profile_table(rows) {
		if (!rows.length) return this.empty("No V2 FBR Integration Profile exists yet.");
		return `
			<div class="lx-tax-table-wrap">
				<table class="lx-tax-table">
					<thead><tr><th>Company</th><th>Mode</th><th>Provider</th><th>Onboarding</th><th>References</th><th>Production arm</th><th></th></tr></thead>
					<tbody>
						${rows.map(row => `
							<tr>
								<td><strong>${this.escape(row.company)}</strong><small>${this.escape(row.name)}</small></td>
								<td>${this.escape(row.mode || "Disabled")}${Number(row.enabled) ? "" : " · Disabled"}</td>
								<td>${this.escape(row.provider_type || "—")}${row.licensed_integrator_name ? `<small>${this.escape(row.licensed_integrator_name)}</small>` : ""}</td>
								<td>${this.escape(row.onboarding_status || "Not Started")}</td>
								<td>${this.escape(row.reference_sync_status || "Never Synced")}</td>
								<td>${Number(row.production_post_armed) ? '<span class="lx-status is-warn">Armed</span>' : '<span class="lx-status is-good">Not armed</span>'}</td>
								<td><button class="btn btn-xs btn-default" data-native-form="Ledgix FBR Integration Profile" data-name="${this.escape(row.name)}">Open</button></td>
							</tr>
						`).join("")}
					</tbody>
				</table>
			</div>
		`;
	}

	reference_table(rows) {
		if (!rows.length) return this.empty("Reference cache is empty. Configure a Sandbox/Production profile token, then sync core references.");
		return `
			<div class="lx-tax-table-wrap">
				<table class="lx-tax-table">
					<thead><tr><th>Reference family</th><th>Current</th><th>Stale history</th><th>Total retained</th></tr></thead>
					<tbody>
						${rows.map(row => `
							<tr>
								<td><strong>${this.escape(row.reference_type)}</strong></td>
								<td>${this.escape(row.current_total || 0)}</td>
								<td>${this.escape(row.stale_total || 0)}</td>
								<td>${this.escape(row.total || 0)}</td>
							</tr>
						`).join("")}
					</tbody>
				</table>
			</div>
		`;
	}

	async sync_core_references() {
		const profileName = (this.state.selectedProfile || "").trim();
		if (!profileName) return frappe.msgprint("Select a V2 FBR Integration Profile first.");

		try {
			this.set_loading(true);
			const result = await this.call(this.methods.syncCore, { profile_name: profileName });
			const failed = (result.errors || []).length;
			frappe.msgprint({
				title: failed ? "Reference sync completed with errors" : "Reference sync complete",
				message: failed
					? `${failed} reference family/families failed. Open the profile/cache for details.`
					: "Province, Document Type, Transaction Type and UOM were synchronized.",
				indicator: failed ? "orange" : "green",
			});
			await this.bootstrap(true);
		} catch (error) {
			this.show_error("Official FBR reference sync failed.", error);
		} finally {
			this.set_loading(false);
		}
	}

	async load_mappings() {
		try {
			this.render_loading("Loading V2 product compliance mappings…");
			this.state.mappings = await this.call(this.methods.mappings, {
				page: this.state.mappingPage,
				page_size: this.pageSize,
				search: this.state.mappingSearch,
				needs_review: this.state.mappingReview,
			});
			this.render_products();
		} catch (error) {
			this.show_error("FBR product mappings could not load.", error);
		}
	}

	render_products() {
		const data = this.state.mappings || { rows: [], total: 0 };
		const summary = this.state.boot.mapping || {};
		this.$root.find(".lx-tax-content").html(`
			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div>
						<h3>FBR product classification</h3>
						<p>Classification only. Monetary tax rates and amounts do not belong in this mapping.</p>
					</div>
					<div class="lx-tax-actions">
						<button class="btn btn-default btn-sm" data-native-list="Ledgix FBR Item Mapping">Open all mappings</button>
						<button class="btn btn-primary btn-sm" data-new-doc="Ledgix FBR Item Mapping">New mapping</button>
					</div>
				</div>
				<div class="lx-tax-metrics lx-tax-metrics-compact">
					${this.metric("Active mappings", summary.active || 0)}
					${this.metric("Needs review", summary.needs_review || 0, Number(summary.needs_review) ? "warn" : "good")}
					${this.metric("Missing HS Code", summary.missing_hs_code || 0, Number(summary.missing_hs_code) ? "warn" : "good")}
					${this.metric("Missing FBR UOM", summary.missing_fbr_uom || 0, Number(summary.missing_fbr_uom) ? "warn" : "good")}
					${this.metric("Tax component mappings", summary.component_mappings || 0)}
				</div>
				<div class="lx-tax-toolbar">
					<input class="form-control lx-v2-map-search" value="${this.escape(this.state.mappingSearch)}" placeholder="Search Item, HS Code, Sale Type or FBR Rate">
					<select class="form-control lx-v2-map-review">
						<option value="All" ${this.state.mappingReview === "All" ? "selected" : ""}>All mappings</option>
						<option value="1" ${this.state.mappingReview === "1" ? "selected" : ""}>Needs review</option>
						<option value="0" ${this.state.mappingReview === "0" ? "selected" : ""}>Reviewed</option>
					</select>
				</div>
				${this.mapping_table(data.rows || [])}
				${this.pagination(this.state.mappingPage, data.total || 0)}
			</section>

			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div><h3>ERPNext tax row → FBR component mapping</h3><p>Labels native ERPNext tax Accounts for FBR semantics; it never stores a rate or amount.</p></div>
					<button class="btn btn-default btn-sm" data-native-list="Ledgix FBR Tax Component Mapping">Open component mappings</button>
				</div>
			</section>
		`);
	}

	mapping_table(rows) {
		if (!rows.length) return this.empty("No V2 FBR Item Mappings match the current filter.");
		return `
			<div class="lx-tax-table-wrap">
				<table class="lx-tax-table">
					<thead><tr><th>Item</th><th>Company</th><th>HS Code</th><th>FBR UOM</th><th>Sale Type</th><th>Rate reference</th><th>Review</th><th></th></tr></thead>
					<tbody>
						${rows.map(row => `
							<tr>
								<td><strong>${this.escape(row.erpnext_item)}</strong></td>
								<td>${this.escape(row.company)}</td>
								<td>${this.escape(row.hs_code || "Missing")}</td>
								<td>${this.escape(row.fbr_uom || "Missing")}</td>
								<td>${this.escape(row.sales_type || "Missing")}</td>
								<td>${this.escape(row.fbr_rate_description || "Missing")}</td>
								<td>${Number(row.needs_review) ? '<span class="lx-status is-warn">Needs review</span>' : '<span class="lx-status is-good">Reviewed</span>'}</td>
								<td><button class="btn btn-xs btn-default" data-native-form="Ledgix FBR Item Mapping" data-name="${this.escape(row.name)}">Open</button></td>
							</tr>
						`).join("")}
					</tbody>
				</table>
			</div>
		`;
	}

	render_certification() {
		const cert = this.state.boot.certification || {};
		this.$root.find(".lx-tax-content").html(`
			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div>
						<h3>Sandbox certification</h3>
						<p>Scenario evidence belongs here, not on Item master mappings.</p>
					</div>
					<div class="lx-tax-actions">
						<button class="btn btn-default btn-sm" data-native-list="Ledgix FBR Sandbox Certification">Open certifications</button>
						<button class="btn btn-primary btn-sm" data-new-doc="Ledgix FBR Sandbox Certification">New certification</button>
					</div>
				</div>
				<div class="lx-tax-metrics lx-tax-metrics-compact">
					${this.metric("Total", cert.total || 0)}
					${this.metric("In progress", cert.in_progress || 0)}
					${this.metric("Complete", cert.complete || 0, Number(cert.complete) ? "good" : "neutral")}
					${this.metric("Real evidence complete", cert.evidence_complete || 0, Number(cert.evidence_complete) ? "good" : "neutral")}
					${this.metric("Failed", cert.failed || 0, Number(cert.failed) ? "warn" : "good")}
				</div>
			</section>

			<section class="lx-tax-section">
				<div class="lx-tax-section-head">
					<div>
						<h3>Invoice payload-input readiness</h3>
						<p>Read-only check of ERPNext identity, native tax evidence, V2 mappings and official reference cache. No FBR network call.</p>
					</div>
				</div>
				<div class="lx-tax-toolbar">
					<select class="form-control lx-v2-readiness-doctype">
						<option value="Sales Invoice" ${this.state.referenceDoctype === "Sales Invoice" ? "selected" : ""}>Sales Invoice</option>
						<option value="POS Invoice" ${this.state.referenceDoctype === "POS Invoice" ? "selected" : ""}>POS Invoice</option>
					</select>
					<div class="lx-v2-readiness-link"></div>
					<button class="btn btn-primary btn-sm lx-v2-check-readiness" type="button">Check readiness</button>
				</div>
				<div class="lx-v2-readiness-result">${this.readiness_html()}</div>
			</section>

			<section class="lx-tax-section">
				<div class="lx-tax-section-head"><div><h3>Compliance audit records</h3><p>Historical submission/correction evidence remains available separately from setup.</p></div></div>
				<div class="lx-native-grid">
					${this.native_link("FBR Submission Logs", "Submission evidence and reconciliation history", "Ledgix FBR Submission Log")}
					${this.native_link("FBR Correction Requests", "72-hour correction / Commissioner-approval tracking", "Ledgix FBR Correction Request")}
				</div>
			</section>
		`);
		this.mount_invoice_control();
	}

	mount_invoice_control() {
		const $holder = this.$root.find(".lx-v2-readiness-link");
		if (!$holder.length) return;
		$holder.empty();

		let control;
		control = frappe.ui.form.make_control({
			parent: $holder[0],
			df: {
				fieldname: "v2_readiness_invoice",
				label: "ERPNext Invoice",
				fieldtype: "Link",
				options: this.state.referenceDoctype,
				get_query: () => ({ filters: { docstatus: ["!=", 2] } }),
				onchange: () => {
					this.state.referenceName = control.get_value() || "";
					this.state.readiness = null;
					this.$root.find(".lx-v2-readiness-result").html(this.readiness_html());
				},
			},
			render_input: true,
		});
		control.set_value(this.state.referenceName || "");
	}

	async check_readiness() {
		const referenceName = (this.state.referenceName || "").trim();
		if (!referenceName) return frappe.msgprint("Select an ERPNext invoice first.");

		try {
			this.set_loading(true);
			this.state.readiness = await this.call(this.methods.readiness, {
				reference_doctype: this.state.referenceDoctype,
				reference_name: referenceName,
			});
			this.$root.find(".lx-v2-readiness-result").html(this.readiness_html());
		} catch (error) {
			this.show_error("V2 readiness check failed.", error);
		} finally {
			this.set_loading(false);
		}
	}

	readiness_html() {
		const result = this.state.readiness;
		if (!result) return '<div class="lx-tax-empty">Select an invoice and run the read-only readiness check.</div>';

		const errors = result.errors || [];
		const warnings = result.warnings || [];
		const profile = result.profile || {};

		return `
			<div class="lx-tax-metrics lx-tax-metrics-compact">
				${this.metric("Payload inputs", result.payload_input_ready ? "Ready" : "Blocked", result.payload_input_ready ? "good" : "warn")}
				${this.metric("Sandbox transport", result.sandbox_transport_ready ? "Ready" : "Not ready", result.sandbox_transport_ready ? "good" : "neutral")}
				${this.metric("Production transport", result.production_transport_ready ? "Ready" : "Not ready", result.production_transport_ready ? "warn" : "good")}
				${this.metric("Profile mode", profile.mode || "Disabled")}
			</div>
			${errors.length ? `
				<div class="lx-tax-note is-warn">
					<strong>Blocking gaps</strong>
					<ul>${errors.map(row => `<li>${this.escape(row)}</li>`).join("")}</ul>
				</div>
			` : '<div class="lx-tax-note"><strong>No payload-input blockers detected by the current V2 readiness checks.</strong></div>'}
			${warnings.length ? `
				<div class="lx-tax-note">
					<strong>Warnings</strong>
					<ul>${warnings.map(row => `<li>${this.escape(row)}</li>`).join("")}</ul>
				</div>
			` : ""}
			<div class="lx-tax-note">
				<strong>Safety:</strong> this check builds no FBR payload, performs no FBR network call and changes no invoice.
			</div>
		`;
	}

	pagination(page, total) {
		const hasPrev = page > 1;
		const hasNext = page * this.pageSize < Number(total || 0);
		return `
			<div class="lx-tax-pagination">
				<button class="btn btn-default btn-sm" data-map-page="prev" ${hasPrev ? "" : "disabled"}>Previous</button>
				<span>Page ${this.escape(page)} · ${this.escape(total || 0)} record(s)</span>
				<button class="btn btn-default btn-sm" data-map-page="next" ${hasNext ? "" : "disabled"}>Next</button>
			</div>
		`;
	}

	empty(message) {
		return `<div class="lx-tax-empty">${this.escape(message)}</div>`;
	}

	render_loading(message) {
		this.$root.find(".lx-tax-content").html(`<div class="lx-tax-empty">${this.escape(message)}</div>`);
	}

	set_loading(flag) {
		this.state.loading = Boolean(flag);
		this.$root.toggleClass("is-loading", this.state.loading);
		this.$root.find("button").prop("disabled", this.state.loading);
	}

	show_error(title, error) {
		const message = error?.message || error?.exc || String(error || "Unknown error");
		frappe.msgprint({
			title,
			message: this.escape(message),
			indicator: "red",
		});
	}
}
