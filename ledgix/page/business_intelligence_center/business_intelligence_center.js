/* global frappe */

frappe.pages["business-intelligence-center"].on_page_load = function (wrapper) {
	frappe.ledgix_business_intelligence = new LedgixBusinessIntelligenceCenter(wrapper);
};

class LedgixBusinessIntelligenceCenter {
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

		this.method = "ledgix_saas.api.business_intelligence.get_business_intelligence_data";
		this.search_method = "ledgix_saas.api.business_intelligence.search_business_intelligence_entities";
		this.timeline_page_size = 8;
		this.lot_page_size = 8;
		this.current_request_id = 0;
		this.search_debounce = null;
		this.search_request_id = 0;

		this.state = {
			item: "",
			from_date: "",
			to_date: "",
			mode: "Overview",
			tracking_type: "All",
			entity_type: "",
			entity_value: "",
			selected_entity: null,
			search: "",
			smart_results: [],
			search_loading: false,
			search_open: false,
			search_api_available: null,
			backend_smart_supported: null,
			loading: false,
			error: null,
			data: null,
			timeline_page: 1,
			timeline_sort_key: "purchase_date",
			timeline_sort_direction: "desc",
			lot_page: 1,
			expanded_lots: new Set(),
			last_loaded_at: null,
		};

		this.make_shell();
		this.make_item_control();
		this.bind_events();
		this.apply_theme_bridge();
		this.load_data();
	}

	// ============================================================
	// SHELL / DOM
	// ============================================================

	make_shell() {
		this.page.clear_actions_menu();
		this.page.set_title("");
		this.$root = $(this.page.body).empty();

		this.$root.html(`
			<div class="lx-bi-page">
			<div class="lx-bi-shell" data-mode="overview">
				<section class="lx-bi-header" aria-label="Business Intelligence Header">
					<div class="lx-bi-title">
						<div class="lx-bi-title-row">
							<span class="lx-bi-title-icon" aria-hidden="true">${this.icon("analytics")}</span>
							<div>
								<h2>Business Intelligence Center</h2>
								<p>Inventory health, profit, returns, stock flow, lot activity, and audit truth in one clean view.</p>
							</div>
						</div>
					</div>

					<div class="lx-bi-controls" aria-label="Business Intelligence Filters">
						<div class="lx-bi-smart-search" role="search">
							<label for="lx-bi-smart-search-input">Smart Search</label>
							<div class="lx-bi-smart-search-box">
								<span class="lx-bi-search-icon" aria-hidden="true">${this.icon("search")}</span>
								<input id="lx-bi-smart-search-input" class="lx-bi-input lx-js-smart-search" type="text" placeholder="Search item, lot, serial, purchase, or sale..." autocomplete="off" aria-label="Search item, lot, serial, purchase, or sale">
								<button class="lx-bi-clear-search lx-js-clear-smart-search" type="button" aria-label="Clear smart search">&times;</button>
							</div>
							<div class="lx-bi-smart-results" role="listbox" aria-label="Smart search results"></div>
						</div>

						<button class="lx-bi-field lx-bi-date-trigger" type="button" aria-label="Select date range">
							<label>Date Range</label>
							<span class="lx-bi-date-label">All Dates</span>
						</button>

						<div class="lx-bi-actions">
							<button class="lx-bi-action lx-js-refresh" type="button" title="Refresh" aria-label="Refresh intelligence data">${this.icon("refresh")}<span>Refresh</span></button>
							<button class="lx-bi-action lx-js-export" type="button" title="Export CSV" aria-label="Export CSV">${this.icon("download")}<span>Export</span></button>
							<button class="lx-bi-action lx-js-print" type="button" title="Print" aria-label="Print report">${this.icon("print")}<span>Print</span></button>
						</div>

						<div class="lx-bi-tracking-row" aria-label="Tracking type filters">
							<span class="lx-bi-tracking-label">Tracking</span>
							<button class="lx-bi-tracking-chip lx-js-tracking is-active" type="button" data-tracking="All">All</button>
							<button class="lx-bi-tracking-chip lx-js-tracking" type="button" data-tracking="Normal Stock">Normal Stock</button>
							<button class="lx-bi-tracking-chip lx-js-tracking" type="button" data-tracking="Lot Based">Lot Based</button>
							<button class="lx-bi-tracking-chip lx-js-tracking" type="button" data-tracking="Serial Based">Serial Based</button>
						</div>

						<div class="lx-bi-selected-entity" aria-live="polite"></div>
					</div>
				</section>

				<div class="lx-bi-state" aria-live="polite"></div>
				<section class="lx-bi-summary" aria-label="KPI Summary"></section>
				<section class="lx-bi-timeline" aria-label="Truth Timeline"></section>

				<section class="lx-bi-insight-grid" aria-label="Story and Risk Intelligence">
					<div class="lx-bi-story"></div>
					<aside class="lx-bi-risks"></aside>
				</section>

				<section class="lx-bi-lots" aria-label="Lot Intelligence"></section>
				<div class="lx-bi-footer"></div>
			</div>
			</div>
		`);

		this.mount_navigator();
	}

	mount_navigator(retry = 0) {
		const $content = this.$root.find(".lx-bi-page").first();
		if ($content.closest(".ledgix-app-shell").length) return;

		if (!window.LedgixNavigator?.mount) {
			if (retry < 6) {
				window.setTimeout(() => this.mount_navigator(retry + 1), 120);
			}
			return;
		}

		window.LedgixNavigator.mount({
			page: this.page,
			wrapper: this.wrapper,
			content: $content,
			active: "business_intelligence",
		});
	}

	make_item_control() {
		const $mount = this.$root.find(".lx-bi-item-control");
		if (!$mount.length) return;
		const field = frappe.ui.form.make_control({
			parent: $mount,
			df: {
				fieldtype: "Link",
				options: "Ledgix Item",
				fieldname: "item",
				placeholder: "All Items",
				only_select: true,
				change: () => {
					this.state.item = field.get_value() || "";
					this.reset_pages();
					this.load_data();
				},
			},
			render_input: true,
		});
		this.item_control = field;
	}

	bind_events() {
		this.theme_update_handler = () => {
			this.apply_theme_bridge();
		};

		if (window.__ledgix_bi_theme_handler) {
			window.removeEventListener("ledgix:theme-updated", window.__ledgix_bi_theme_handler);
			document.removeEventListener("ledgix:theme-updated", window.__ledgix_bi_theme_handler);
		}

		window.__ledgix_bi_theme_handler = this.theme_update_handler;

		window.addEventListener("ledgix:theme-updated", this.theme_update_handler);
		document.addEventListener("ledgix:theme-updated", this.theme_update_handler);

		this.apply_theme_bridge();

		this.$root.on("click", ".lx-js-refresh", () => this.load_data({ force: true }));
		this.$root.on("click", ".lx-bi-date-trigger", () => this.show_date_dialog());

		this.$root.on("input", ".lx-js-smart-search", (e) => {
			this.state.search = e.currentTarget.value.trim();
			this.$root.find(".lx-bi-smart-search").toggleClass("has-value", Boolean(this.state.search));
			window.clearTimeout(this.search_debounce);
			this.search_debounce = window.setTimeout(() => this.fetch_smart_results(this.state.search), 180);
		});

		this.$root.on("focus", ".lx-js-smart-search", () => {
			if (this.state.search || this.state.smart_results.length) {
				this.state.search_open = true;
				this.render_smart_results();
			}
		});

		this.$root.on("keydown", ".lx-js-smart-search", (e) => {
			if (e.key === "Escape") {
				this.state.search_open = false;
				this.render_smart_results();
				return;
			}
			if (e.key === "Enter" && this.state.smart_results.length) {
				e.preventDefault();
				this.select_smart_result(0);
			}
		});

		this.$root.on("click", ".lx-js-smart-result", (e) => {
			const index = Number($(e.currentTarget).data("index"));
			this.select_smart_result(index);
		});

		this.$root.on("click", ".lx-js-clear-smart-search", () => this.clear_smart_search({ reload: true }));
		this.$root.on("click", ".lx-js-clear-selected", () => this.clear_selected_entity({ reload: true, focus: true }));

		this.$root.on("click", ".lx-js-tracking", (e) => {
			const tracking = String($(e.currentTarget).data("tracking") || "All");
			this.apply_tracking_filter(tracking);
		});

		$(document).off("mousedown.ledgix_bi_smart_search").on("mousedown.ledgix_bi_smart_search", (event) => {
			if (!this.$root || !this.$root.length) return;
			if ($(event.target).closest(this.$root.find(".lx-bi-smart-search")).length) return;
			if (!this.state.search_open) return;
			this.state.search_open = false;
			this.render_smart_results();
		});

		this.$root.on("click", ".lx-js-toggle-lot", (e) => {
			const lot = String($(e.currentTarget).data("lot") || "");
			if (!lot) return;
			if (this.state.expanded_lots.has(lot)) {
				this.state.expanded_lots.delete(lot);
			} else {
				this.state.expanded_lots.add(lot);
			}
			this.render_lots();
		});

		this.$root.on("click", ".lx-js-risk-modal", () => this.show_risk_dialog());
		this.$root.on("click", ".lx-js-full-table", () => this.show_full_table_dialog());

		this.$root.on("click", ".lx-js-timeline-sort", (e) => {
			const key = String($(e.currentTarget).data("sort") || "purchase_date");
			if (this.state.timeline_sort_key === key) {
				this.state.timeline_sort_direction = this.state.timeline_sort_direction === "asc" ? "desc" : "asc";
			} else {
				this.state.timeline_sort_key = key;
				this.state.timeline_sort_direction = key.includes("date") ? "desc" : "asc";
			}
			this.state.timeline_page = 1;
			this.render_timeline();
		});

		this.$root.on("click", ".lx-js-timeline-page", (e) => {
			const direction = $(e.currentTarget).data("direction");
			const total = this.get_total_pages("timeline");
			this.state.timeline_page += direction === "next" ? 1 : -1;
			this.state.timeline_page = Math.max(1, Math.min(total, this.state.timeline_page));
			this.render_timeline();
		});

		this.$root.on("click", ".lx-js-lot-page", (e) => {
			const direction = $(e.currentTarget).data("direction");
			const total = this.get_total_pages("lots");
			this.state.lot_page += direction === "next" ? 1 : -1;
			this.state.lot_page = Math.max(1, Math.min(total, this.state.lot_page));
			this.render_lots();
		});

		this.$root.on("click", ".lx-js-export", () => this.export_csv());
		this.$root.on("click", ".lx-js-print", () => this.print_report());
	}

	// ============================================================
	// DATA LOADING
	// ============================================================

	async load_data(options = {}) {
		const request_id = ++this.current_request_id;
		this.state.loading = true;
		this.state.error = null;
		this.render_state();
		this.render_selected_entity();
		this.set_busy(true);

		try {
			let data;
			if (this.state.backend_smart_supported === false) {
				data = await this.call_method(this.method, this.legacy_data_args());
			} else {
				try {
					data = await this.call_method(this.method, this.smart_data_args());
					this.state.backend_smart_supported = true;
				} catch (smart_error) {
					if (request_id !== this.current_request_id) return;
					console.warn("Business Intelligence smart args failed; retrying legacy payload.", smart_error);
					this.state.backend_smart_supported = false;
					data = await this.call_method(this.method, this.legacy_data_args());
				}
			}

			if (request_id !== this.current_request_id) return;

			this.state.data = this.normalize_data(data || {});
			this.state.loading = false;
			this.state.error = null;
			this.state.last_loaded_at = frappe.datetime.now_datetime();
			this.clamp_pages();
			this.render();
			if (options.force) {
				this.show_alert("Business Intelligence data refreshed.", "green");
			}
		} catch (error) {
			if (request_id !== this.current_request_id) return;
			console.error("Business Intelligence Center load error:", error);
			this.state.loading = false;
			this.state.error = error;
			this.render();
		} finally {
			if (request_id === this.current_request_id) {
				this.set_busy(false);
			}
		}
	}

	smart_data_args() {
		return {
			item: this.state.item || null,
			tracking_type: this.normalize_tracking_label(this.state.tracking_type || "All"),
			entity_type: this.state.entity_type || null,
			entity_value: this.state.entity_value || null,
			from_date: this.state.from_date || null,
			to_date: this.state.to_date || null,
			mode: this.mode_for_entity(),
			search: null,
		};
	}

	legacy_data_args() {
		return {
			item: this.state.item || null,
			from_date: this.state.from_date || null,
			to_date: this.state.to_date || null,
			mode: this.mode_for_entity(),
			search: this.state.entity_value || this.state.search || null,
		};
	}

	mode_for_entity() {
		const type = String(this.state.entity_type || "").toLowerCase();
		if (type === "item") return "Item Intelligence";
		if (["lot", "serial"].includes(type)) return "Lot Intelligence";
		return "Overview";
	}

	async fetch_smart_results(query) {
		const normalized_query = String(query || "").trim();
		const request_id = ++this.search_request_id;

		if (!normalized_query) {
			this.state.smart_results = [];
			this.state.search_loading = false;
			this.state.search_open = false;
			this.render_smart_results();
			return;
		}

		this.state.search_loading = true;
		this.state.search_open = true;
		this.render_smart_results();

		let results = [];
		if (this.state.search_api_available !== false) {
			try {
				const response = await this.call_method(this.search_method, {
					query: normalized_query,
					tracking_type: this.normalize_tracking_label(this.state.tracking_type || "All"),
				});
				results = this.normalize_search_results(response);
				this.state.search_api_available = true;
			} catch (error) {
				console.warn("Business Intelligence smart search API unavailable; using local fallback results.", error);
				this.state.search_api_available = false;
				results = this.build_local_search_results(normalized_query);
			}
		} else {
			results = this.build_local_search_results(normalized_query);
		}

		if (request_id !== this.search_request_id) return;
		this.state.smart_results = results;
		this.state.search_loading = false;
		this.state.search_open = true;
		this.render_smart_results();
	}

	normalize_search_results(response) {
		const raw = Array.isArray(response) ? response : (response && Array.isArray(response.results) ? response.results : []);
		const seen = new Set();
		return raw.map((row) => ({
			label: row.label || row.entity_value || row.name || "Result",
			subtitle: row.subtitle || row.description || "",
			entity_type: String(row.entity_type || "item").toLowerCase(),
			entity_value: row.entity_value || row.value || row.name || row.label || "",
			tracking_type: this.normalize_tracking_label(row.tracking_type || ""),
			status: row.status || row.status_hint || row.hint || "",
			value_hint: row.value_hint || row.amount_hint || "",
		})).filter((row) => {
			if (!row.entity_value) return false;
			if (!this.tracking_matches(row.tracking_type)) return false;
			const key = `${row.entity_type}:${row.entity_value}`;
			if (seen.has(key)) return false;
			seen.add(key);
			return true;
		}).slice(0, 12);
	}

	build_local_search_results(query) {
		const q = String(query || "").trim().toLowerCase();
		if (!q) return [];

		const data = this.get_data();
		const results = [];
		const push = (candidate) => {
			if (!candidate || !candidate.entity_value) return;
			const haystack = [candidate.label, candidate.subtitle, candidate.entity_value, candidate.status, candidate.value_hint]
				.filter(Boolean)
				.join(" ")
				.toLowerCase();
			if (!haystack.includes(q)) return;
			if (!this.tracking_matches(candidate.tracking_type)) return;
			const key = `${candidate.entity_type}:${candidate.entity_value}`;
			if (results.some((row) => `${row.entity_type}:${row.entity_value}` === key)) return;
			results.push(candidate);
		};

		(data.lots || []).forEach((lot) => {
			const lot_value = lot.lot_number || lot.name || lot.lot || "";
			const item_value = lot.item || lot.item_code || lot.item_name || "";
			push({
				label: lot.item_name || item_value || "Item",
				subtitle: [lot.item, lot.supplier, lot.tracking_type].filter(Boolean).join(" • "),
				entity_type: "item",
				entity_value: item_value,
				tracking_type: this.normalize_tracking_label(lot.tracking_type || "Lot Based"),
				status: lot.lot_status || "",
			});
			push({
				label: lot_value,
				subtitle: [lot.item_name || lot.item, lot.supplier, lot.purchase].filter(Boolean).join(" • "),
				entity_type: "lot",
				entity_value: lot_value,
				tracking_type: this.normalize_tracking_label(lot.tracking_type || "Lot Based"),
				status: lot.lot_status || "",
				value_hint: this.format_optional_number(lot.remaining_qty),
			});
		});

		const rows = [...(data.timeline || []), ...(data.cycle_rows || [])];
		rows.forEach((row) => {
			const tracking = this.normalize_tracking_label(row.tracking_type || row.item_tracking_type || "");
			const item_value = row.item || row.item_code || row.item_name || "";
			const serial_value = row.serial_number || row.serial_no || row.stock_serial || row.serial || row.stock_serial_number || "";
			const lot_value = this.row_lot(row);
			push({ label: row.item_name || item_value, subtitle: [row.item, tracking, row.reference_status].filter(Boolean).join(" • "), entity_type: "item", entity_value: item_value, tracking_type: tracking, status: row.reference_status || "" });
			push({ label: lot_value, subtitle: [row.item_name || row.item, row.purchase, row.sale].filter(Boolean).join(" • "), entity_type: "lot", entity_value: lot_value, tracking_type: tracking || "Lot Based", status: row.lot_status || row.cycle_status || "" });
			push({ label: serial_value, subtitle: [row.item_name || row.item, row.purchase, row.sale].filter(Boolean).join(" • "), entity_type: "serial", entity_value: serial_value, tracking_type: tracking || "Serial Based", status: row.serial_status || row.reference_status || row.cycle_status || "" });
			push({ label: row.purchase, subtitle: [row.purchase_invoice, row.supplier, row.item_name || row.item].filter(Boolean).join(" • "), entity_type: "purchase", entity_value: row.purchase, tracking_type: tracking, status: row.reference_status || row.cycle_status || "" });
			push({ label: row.sale, subtitle: [row.sale_invoice, row.customer, row.item_name || row.item].filter(Boolean).join(" • "), entity_type: "sale", entity_value: row.sale, tracking_type: tracking, status: row.reference_status || row.cycle_status || "" });
		});

		return results.slice(0, 12);
	}

	tracking_matches(candidate_tracking) {
		const active = this.normalize_tracking_label(this.state.tracking_type || "All");
		if (active === "All") return true;
		const candidate = this.normalize_tracking_label(candidate_tracking || "");
		return !candidate || candidate === active;
	}

	render_smart_results() {
		const $results = this.$root.find(".lx-bi-smart-results");
		const $search = this.$root.find(".lx-bi-smart-search");
		$search.toggleClass("is-open", Boolean(this.state.search_open));
		$search.toggleClass("is-loading", Boolean(this.state.search_loading));
		$search.toggleClass("has-value", Boolean(this.state.search || this.state.selected_entity));

		if (!this.state.search_open) {
			$results.empty();
			return;
		}

		if (this.state.search_loading) {
			$results.html(`<div class="lx-bi-smart-empty"><span class="lx-bi-loader" aria-hidden="true"></span><strong>Searching intelligence records...</strong></div>`);
			return;
		}

		if (!this.state.smart_results.length) {
			$results.html(`<div class="lx-bi-smart-empty"><strong>No smart match found</strong><span>Try item name, lot number, serial number, purchase number, or sale number.</span></div>`);
			return;
		}

		$results.html(this.state.smart_results.map((result, index) => `
			<button class="lx-bi-smart-result lx-js-smart-result" type="button" data-index="${index}" role="option">
				<span class="lx-bi-result-type is-${this.safe_attr(result.entity_type)}">${this.safe(this.entity_type_label(result.entity_type))}</span>
				<span class="lx-bi-result-main">
					<strong>${this.safe(result.label)}</strong>
					<small>${this.safe(result.subtitle || result.entity_value)}</small>
				</span>
				<span class="lx-bi-result-meta">
					${result.tracking_type ? `<em>${this.safe(this.normalize_tracking_label(result.tracking_type))}</em>` : ""}
					${result.status ? `<i>${this.safe(result.status)}</i>` : ""}
				</span>
			</button>
		`).join(""));
	}

	select_smart_result(index) {
		const result = this.state.smart_results[index];
		if (!result || !result.entity_value) return;

		result.tracking_type = this.normalize_tracking_label(result.tracking_type || "");
		this.state.selected_entity = result;
		this.state.entity_type = String(result.entity_type || "item").toLowerCase();
		this.state.entity_value = result.entity_value;
		this.state.item = this.state.entity_type === "item" ? result.entity_value : "";
		this.state.search = result.label || result.entity_value;
		this.state.search_open = false;
		this.state.smart_results = [];
		this.state.mode = this.mode_for_entity();
		this.reset_pages();
		this.$root.find(".lx-js-smart-search").val(this.state.search);
		this.render_smart_results();
		this.render_selected_entity();
		this.load_data();
	}

	clear_smart_search(options = {}) {
		window.clearTimeout(this.search_debounce);
		this.state.search = "";
		this.state.smart_results = [];
		this.state.search_loading = false;
		this.state.search_open = false;
		this.$root.find(".lx-js-smart-search").val("");
		this.render_smart_results();
		if (this.state.selected_entity) {
			this.clear_selected_entity(options);
		} else if (options.reload) {
			this.reset_pages();
			this.load_data();
		}
	}

	clear_selected_entity(options = {}) {
		this.state.selected_entity = null;
		this.state.entity_type = "";
		this.state.entity_value = "";
		this.state.item = "";
		this.state.mode = "Overview";
		this.reset_pages();
		this.$root.find(".lx-js-smart-search").val("");
		this.state.search = "";
		this.render_selected_entity();
		this.render_smart_results();
		if (options.focus) this.$root.find(".lx-js-smart-search").trigger("focus");
		if (options.reload) this.load_data();
	}

	apply_tracking_filter(tracking) {
		const allowed = ["All", "Normal Stock", "Item Based", "Normal", "Lot Based", "Serial Based"];
		const next = allowed.includes(tracking) ? this.normalize_tracking_label(tracking) : "All";
		if (this.state.tracking_type === next) return;
		this.state.tracking_type = next;
		this.$root.find(".lx-js-tracking").removeClass("is-active");
		this.$root.find(`.lx-js-tracking[data-tracking="${this.safe_attr(next)}"]`).addClass("is-active");

		if (this.state.selected_entity && !this.tracking_matches(this.state.selected_entity.tracking_type)) {
			this.clear_selected_entity({ reload: false });
		}

		this.reset_pages();
		this.load_data();
		if (this.state.search) this.fetch_smart_results(this.state.search);
	}

	render_selected_entity() {
		const $target = this.$root.find(".lx-bi-selected-entity");
		if (!$target.length) return;
		const selected = this.state.selected_entity;
		if (!selected) {
			$target.html(`
				<div class="lx-bi-context-pill is-global">
					<span>${this.icon("spark")}</span>
					<strong>Global Overview</strong>
					<small>${this.safe(this.normalize_tracking_label(this.state.tracking_type || "All"))} intelligence across available records</small>
				</div>
			`);
			return;
		}

		$target.html(`
			<div class="lx-bi-context-pill is-selected">
				<span class="lx-bi-result-type is-${this.safe_attr(selected.entity_type)}">${this.safe(this.entity_type_label(selected.entity_type))}</span>
				<strong>${this.safe(selected.label || selected.entity_value)}</strong>
				<small>${this.safe([selected.subtitle, this.normalize_tracking_label(selected.tracking_type), selected.status].filter(Boolean).join(" • "))}</small>
				<button class="lx-bi-selected-clear lx-js-clear-selected" type="button" aria-label="Clear selected intelligence entity">&times;</button>
			</div>
		`);
	}

	entity_type_label(type) {
		const labels = { item: "Item", lot: "Lot", serial: "Serial", purchase: "Purchase", sale: "Sale" };
		return labels[String(type || "").toLowerCase()] || "Result";
	}

	call_method(method, args = {}) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method,
				args,
				callback: (r) => {
					if (r && r.exc) {
						reject(r);
						return;
					}
					resolve(r ? r.message : null);
				},
				error: (r) => reject(r),
			});
		});
	}

	normalize_data(data) {
		return {
			summary: data.summary || {},
			story: data.story || {},
			lots: Array.isArray(data.lots) ? data.lots : [],
			timeline: Array.isArray(data.timeline) ? data.timeline : [],
			cycle_rows: Array.isArray(data.cycle_rows) ? data.cycle_rows : [],
			risks: Array.isArray(data.risks) ? data.risks : [],
			meta: data.meta || {},
		};
	}

	// ============================================================
	// RENDERING
	// ============================================================

	render() {
		this.update_mode_class();
		this.render_state();
		this.render_selected_entity();
		this.render_summary();
		this.render_timeline();
		this.render_story();
		this.render_risks();
		this.render_lots();
		this.render_footer();
	}

	render_state() {
		const $state = this.$root.find(".lx-bi-state");
		if (this.state.loading) {
			$state.html(`
				<div class="lx-bi-notice">
					<span class="lx-bi-loader" aria-hidden="true"></span>
					<strong>Loading intelligence data</strong>
					<p>Reading stock lots, allocations, submitted references, and audit signals.</p>
				</div>
			`);
			return;
		}

		if (this.state.error) {
			$state.html(`
				<div class="lx-bi-notice is-error">
					<strong>Unable to load Business Intelligence data.</strong>
					<p>This is a backend/API error, not an empty data state. Check Frappe logs for the method below.</p>
					<code>${this.safe(this.method)}</code>
				</div>
			`);
			return;
		}

		$state.empty();
	}

	render_summary() {
		const summary = this.get_data().summary || {};
		const panels = [
			{
				title: "Inventory Health",
				tone: "green",
				icon: "box",
				items: [
					["Current Qty", summary.current_qty, "number"],
					["Purchased Qty", summary.purchased_qty, "number"],
					["Remaining Qty", summary.remaining_qty, "number"],
					["Sell-through", summary.sell_through_percent, "percent"],
				],
			},
			{
				title: "Revenue & Profit",
				tone: "blue",
				icon: "trend",
				items: [
					["Gross Revenue", summary.gross_revenue, "currency"],
					["Net Revenue", summary.net_revenue, "currency"],
					["Profit", summary.net_profit, "currency"],
					["Margin", summary.margin_percent, "percent"],
				],
			},
			{
				title: "Return & Risk",
				tone: "orange",
				icon: "warning",
				items: [
					["Returned Qty", summary.returned_qty, "number"],
					["Return Amount", summary.return_amount, "currency"],
					["Return Rate", summary.return_rate_percent, "percent"],
					["Risk Level", summary.risk_level, "text"],
				],
			},
			{
				title: "Stock Flow",
				tone: "purple",
				icon: "flow",
				items: [
					["Purchased", summary.purchased_qty, "number"],
					["Sold", summary.sold_qty, "number"],
					["Returned", summary.returned_qty, "number"],
					["Net Sold", summary.net_sold_qty, "number"],
				],
			},
		];

		this.$root.find(".lx-bi-summary").html(panels.map((panel) => `
			<div class="lx-bi-panel is-${panel.tone}">
				<div class="lx-bi-panel-head">
					<span aria-hidden="true">${this.icon(panel.icon)}</span>
					<strong>${this.safe(panel.title)}</strong>
				</div>
				<div class="lx-bi-panel-grid">
					${panel.items.map(([label, value, type]) => `
						<div>
							<span>${this.safe(label)}</span>
							<strong class="${this.value_class(value, type)}">${this.format_value(value, type)}</strong>
						</div>
					`).join("")}
				</div>
			</div>
		`).join(""));
	}

	render_timeline() {
		const timeline = this.get_timeline_rows();
		const total_pages = this.get_total_pages("timeline");
		const page = Math.max(1, Math.min(this.state.timeline_page, total_pages));
		const start = (page - 1) * this.timeline_page_size;
		const rows = timeline.slice(start, start + this.timeline_page_size);
		const count_label = this.record_label(timeline.length, "record");
		const page_label = `Page ${page} of ${total_pages}`;

		this.$root.find(".lx-bi-timeline").html(`
			<div class="lx-bi-section lx-bi-timeline-section">
				<div class="lx-bi-section-head">
					<div><span aria-hidden="true">${this.icon("timeline")}</span><h3>Truth Timeline</h3></div>
					<div class="lx-bi-page-controls" aria-label="Truth Timeline pagination">
						<span class="lx-bi-count-badge lx-bi-total-badge">${this.safe(count_label)}</span>
						<span class="lx-bi-count-badge lx-bi-page-indicator">${this.safe(page_label)}</span>
						<button class="lx-js-timeline-page" type="button" data-direction="prev" ${page <= 1 ? "disabled" : ""} aria-label="Previous timeline page">${this.icon("left")}</button>
						<button class="lx-js-timeline-page" type="button" data-direction="next" ${page >= total_pages ? "disabled" : ""} aria-label="Next timeline page">${this.icon("right")}</button>
						<button class="lx-bi-full-table-btn lx-js-full-table" type="button">${this.icon("table")}<span>See Full Table</span></button>
					</div>
				</div>
				${rows.length ? this.timeline_table(rows) : this.empty_html("No timeline activity matched the current filters.")}
			</div>
		`);
	}

	timeline_table(rows) {
		const columns = [
			["purchase_date", "Purchase Date"],
			["status", "Status/Event"],
			["lot", this.identity_label()],
			["item", "Item"],
			["reference", "Reference"],
			["current_qty", "Current Qty"],
			["sold_qty", "Sold Qty"],
			["return_qty", "Returned Qty"],
			["cost_price", "Cost Price"],
			["selling_price", "Selling Price"],
			["profit_loss", "Profit/Loss"],
			["sell_date", "Sell Date"],
		];

		return `
			<div class="lx-bi-table-scroll">
				<table class="lx-bi-table lx-bi-timeline-table">
					<thead>
						<tr>
							${columns.map(([key, label]) => `
								<th aria-sort="${this.sort_aria(key)}">
									<button class="lx-bi-sort-head lx-js-timeline-sort ${this.state.timeline_sort_key === key ? "is-active" : ""}" type="button" data-sort="${this.safe_attr(key)}" title="Sort by ${this.safe_attr(label)}">${this.safe(label)}</button>
								</th>
							`).join("")}
						</tr>
					</thead>
					<tbody>
						${rows.map((row) => `
							<tr class="${this.row_class(row)}">
								<td>${this.safe(this.format_date(this.row_purchase_date(row)))}</td>
								<td><span class="lx-bi-chip ${this.event_class(row.event_type || row.cycle_status)}">${this.safe(row.cycle_status || row.event_type || "Activity")}</span></td>
								<td>${this.safe(this.row_lot(row))}</td>
								<td>${this.safe(row.item_name || row.item)}</td>
								<td>${this.safe(this.row_reference(row))}</td>
								<td>${this.format_number(row.current_lot_qty ?? row.running_qty)}</td>
								<td>${this.format_optional_number(row.sale_qty)}</td>
								<td>${this.format_optional_number(row.return_qty)}</td>
								<td>${this.format_currency(this.row_cost_price(row))}</td>
								<td>${this.format_currency(this.row_selling_price(row))}</td>
								<td class="${this.profit_loss_class(row)}">${this.format_profit_loss(row)}</td>
								<td>${this.safe(this.format_date(this.row_sell_date(row)))}</td>
							</tr>
						`).join("")}
					</tbody>
				</table>
			</div>
		`;
	}

	render_story() {
		const story = this.get_data().story || {};
		const signals = Array.isArray(story.signals) ? story.signals : [];

		this.$root.find(".lx-bi-story").html(`
			<div class="lx-bi-section lx-bi-story-card is-${this.safe_attr(story.tone || "neutral")}">
				<div class="lx-bi-section-head">
					<div><span aria-hidden="true">${this.icon("spark")}</span><h3>Business Story</h3></div>
				</div>
				<p>${this.safe(story.text || "No stock lot activity matched the current filters.")}</p>
				${signals.length ? `<div class="lx-bi-signal-row">${signals.map((signal) => `<span>${this.safe(signal)}</span>`).join("")}</div>` : ""}
			</div>
		`);
	}

	render_risks() {
		const risks = this.get_data().risks || [];
		const highest = this.get_highest_risk(risks);
		const summary = risks.length
			? `${risks.length} warning${risks.length === 1 ? "" : "s"} detected`
			: "No audit risks found";

		this.$root.find(".lx-bi-risks").html(`
			<div class="lx-bi-section lx-bi-risk-section is-${this.safe_attr(highest)}">
				<button class="lx-bi-section-head lx-bi-risk-toggle lx-js-risk-modal" type="button" aria-label="Open Audit and Risk warnings">
					<div><span aria-hidden="true">${this.icon("shield")}</span><h3>Audit & Risk</h3></div>
					<span class="lx-bi-risk-count">${this.record_label(risks.length, "warning")}</span>
				</button>
				<div class="lx-bi-risk-collapsed">
					<strong>${this.safe(summary)}</strong>
					<p>${risks.length ? "Click to review actionable warnings and audit signals." : "Current filters do not show risk signals."}</p>
				</div>
			</div>
		`);
	}

	render_lots() {
		const lots = this.get_data().lots || [];
		const tracking = this.normalize_tracking_label(this.state.tracking_type || "All");
		const total_pages = this.get_total_pages("lots");
		const page = Math.max(1, Math.min(this.state.lot_page, total_pages));
		const start = (page - 1) * this.lot_page_size;
		const visible = lots.slice(start, start + this.lot_page_size);
		const title = tracking === "Normal Stock" ? "Normal Stock Identity" : "Lot Intelligence";
		const empty_message = tracking === "Normal Stock"
			? "Normal Stock uses quantity-only tracking, so it has no lot or serial identity rows. Use the Truth Timeline above for purchases, sales, and returns."
			: "No lots match the current filters.";
		const body = visible.length ? visible.map((lot) => this.lot_card(lot)).join("") : this.empty_html(empty_message);

		this.$root.find(".lx-bi-lots").html(`
			<div class="lx-bi-section lx-bi-lot-section">
				<div class="lx-bi-section-head">
					<div><span aria-hidden="true">${this.icon("cube")}</span><h3>${this.safe(title)}</h3></div>
					<div class="lx-bi-page-controls" aria-label="Lot pagination">
						<span class="lx-bi-count-badge lx-bi-total-badge">${this.record_label(lots.length, "record")}</span>
						<span class="lx-bi-count-badge lx-bi-page-indicator">Page ${page} of ${total_pages}</span>
						<button class="lx-js-lot-page" type="button" data-direction="prev" ${page <= 1 ? "disabled" : ""} aria-label="Previous lots page">${this.icon("left")}</button>
						<button class="lx-js-lot-page" type="button" data-direction="next" ${page >= total_pages ? "disabled" : ""} aria-label="Next lots page">${this.icon("right")}</button>
					</div>
				</div>
				<div class="lx-bi-lot-list">${body}</div>
			</div>
		`);
	}

	lot_card(lot) {
		const lot_number = String(lot.lot_number || lot.name || "");
		const open = this.state.expanded_lots.has(lot_number);
		const detail = [
			["Purchase", lot.purchase],
			["Supplier", lot.supplier],
			["Purchase Date", this.format_date(lot.purchase_date)],
			["Cost Rate", this.format_currency(lot.cost_rate)],
			["Total Cost", this.format_currency(lot.total_cost)],
			["Gross Revenue", this.format_currency(lot.gross_revenue)],
			["Return Impact", this.format_currency(lot.return_profit_impact)],
			["Net Revenue", this.format_currency(lot.net_revenue)],
			["Profit", this.format_currency(lot.profit)],
			["Margin", this.format_percent(lot.margin_percent)],
			["Sell-through", this.format_percent(lot.sell_through_percent)],
		];

		return `
			<article class="lx-bi-lot-card ${open ? "is-open" : ""}">
				<button class="lx-bi-lot-main lx-js-toggle-lot" type="button" data-lot="${this.safe_attr(lot_number)}" aria-expanded="${open ? "true" : "false"}">
					<div class="lx-bi-lot-id">
						<strong>${this.safe(lot_number || "Lot")}</strong>
						<span>${this.safe(lot.item_name || lot.item)}</span>
					</div>
					<div class="lx-bi-lot-metrics">
						${this.metric("Supplier", lot.supplier, "text")}
						${this.metric("Purchased", lot.purchased_qty, "number")}
						${this.metric("Sold", lot.sold_qty, "number")}
						${this.metric("Returned", lot.returned_qty, "number")}
						${this.metric("Remaining", lot.remaining_qty, "number")}
						${this.metric("Net Revenue", lot.net_revenue, "currency")}
						${this.metric("Profit", lot.profit, "currency")}
					</div>
					<span class="lx-bi-chip ${this.status_class(lot.lot_status)}">${this.safe(lot.lot_status || "Open")}</span>
				</button>
				${open ? `<div class="lx-bi-lot-detail">${detail.map(([label, value]) => `<div><span>${this.safe(label)}</span><strong>${this.safe(value)}</strong></div>`).join("")}</div>` : ""}
			</article>
		`;
	}

	metric(label, value, type) {
		return `<div><span>${this.safe(label)}</span><strong class="${this.value_class(value, type)}">${this.format_value(value, type)}</strong></div>`;
	}

	render_footer() {
		const meta = this.get_data().meta || {};
		const generated = meta.generated_at || this.state.last_loaded_at;
		const selected = this.state.selected_entity;
		const filters = [
			selected ? `${this.entity_type_label(selected.entity_type)}: ${selected.entity_value}` : "Global overview",
			`Tracking: ${this.normalize_tracking_label(this.state.tracking_type || "All")}`,
			this.state.from_date || this.state.to_date ? this.$root.find(".lx-bi-date-label").text() : "All dates",
			this.state.backend_smart_supported === false ? "Legacy backend fallback" : "Smart intelligence",
		].join(" • ");
		this.$root.find(".lx-bi-footer").html(`Data as of ${this.safe(this.format_datetime(generated))} <span>${this.safe(filters)}</span>`);
	}

	// ============================================================
	// DIALOGS / ACTIONS
	// ============================================================

	show_date_dialog() {
		const dialog = new frappe.ui.Dialog({
			title: "Date Range",
			fields: [
				{ fieldname: "from_date", label: "From Date", fieldtype: "Date", default: this.state.from_date },
				{ fieldname: "to_date", label: "To Date", fieldtype: "Date", default: this.state.to_date },
			],
			primary_action_label: "Apply",
			primary_action: (values) => {
				const from_date = values.from_date || "";
				const to_date = values.to_date || "";
				if (from_date && to_date && from_date > to_date) {
					frappe.msgprint({
						title: "Invalid Date Range",
						indicator: "orange",
						message: "From Date cannot be after To Date.",
					});
					return;
				}
				this.state.from_date = from_date;
				this.state.to_date = to_date;
				this.reset_pages();
				this.update_date_label();
				dialog.hide();
				this.load_data();
			},
			secondary_action_label: "Clear",
			secondary_action: () => {
				this.state.from_date = "";
				this.state.to_date = "";
				this.reset_pages();
				this.update_date_label();
				dialog.hide();
				this.load_data();
			},
		});
		dialog.show();
	}

	show_risk_dialog() {
		const risks = this.get_data().risks || [];
		const body = risks.length
			? risks.map((risk) => `
				<div class="lx-bi-risk-row is-dialog-row">
					<span class="lx-bi-chip ${this.severity_class(risk.severity)}">${this.safe(risk.severity || "Info")}</span>
					<div>
						<strong>${this.safe(risk.title || "Audit warning")}</strong>
						<p>${this.safe(risk.message || "No details provided.")}</p>
						${risk.reference ? `<small>${this.safe(risk.reference)}</small>` : ""}
					</div>
				</div>
			`).join("")
			: this.empty_html("No audit risks found for current filters.");

		const dialog = new frappe.ui.Dialog({
			title: "Audit & Risk Warnings",
			fields: [{ fieldtype: "HTML", fieldname: "risk_html" }],
			primary_action_label: "Close",
			primary_action: () => dialog.hide(),
		});
		dialog.fields_dict.risk_html.$wrapper.html(`<div class="lx-bi-risk-dialog">${body}</div>`);
		dialog.show();
	}

	show_full_table_dialog() {
		if (this.state.error) {
			frappe.msgprint({
				title: "Business Intelligence Error",
				indicator: "red",
				message: "The detailed table cannot be shown because the latest API request failed.",
			});
			return;
		}

		const rows = this.get_timeline_rows();
		const body = rows.length ? this.full_table(rows) : this.empty_html("No detailed timeline rows matched the current filters.");
		const dialog = new frappe.ui.Dialog({
			title: "Truth Timeline - Full Table",
			size: "extra-large",
			fields: [{ fieldtype: "HTML", fieldname: "full_table_html" }],
			primary_action_label: "Close",
			primary_action: () => dialog.hide(),
		});
		dialog.fields_dict.full_table_html.$wrapper.html(`<div class="lx-bi-full-dialog">${body}</div>`);
		dialog.show();
	}

	full_table(rows) {
		const columns = [
			["Purchase Date", (row) => this.format_date(this.row_purchase_date(row))],
			["Sell Date", (row) => this.format_date(this.row_sell_date(row))],
			["Return Date", (row) => this.format_date(row.return_date)],
			["Row Type", (row) => row.row_type],
			["Status/Event", (row) => row.event_type || row.cycle_status],
			["Lot No", (row) => this.row_lot(row)],
			["Item", (row) => row.item_name || row.item],
			["Reference", (row) => this.row_reference(row)],
			["Purchase No", (row) => row.purchase],
			["Purchase Invoice", (row) => row.purchase_invoice],
			["Sale No", (row) => row.sale],
			["Sale Invoice", (row) => row.sale_invoice],
			["Sales Return", (row) => row.sales_return],
			["Supplier", (row) => row.supplier],
			["Customer", (row) => row.customer],
			["Purchased Qty", (row) => this.format_optional_number(row.purchased_qty)],
			["Current Qty", (row) => this.format_number(row.current_lot_qty ?? row.running_qty)],
			["Sold Qty", (row) => this.format_optional_number(row.sale_qty)],
			["Returned Qty", (row) => this.format_optional_number(row.return_qty)],
			["Net Sold Qty", (row) => this.format_optional_number(row.net_sold_qty)],
			["Cost Price", (row) => this.format_currency(this.row_cost_price(row))],
			["Selling Price", (row) => this.format_currency(this.row_selling_price(row))],
			["Total Cost", (row) => this.format_currency(row.total_cost)],
			["Selling Amount", (row) => this.format_currency(row.selling_amount)],
			["Return Amount", (row) => this.format_currency(row.return_amount)],
			["Profit", (row) => this.format_currency(row.profit ?? row.profit_impact)],
			["Loss", (row) => this.format_currency(row.loss)],
			["Status / Severity", (row) => row.reference_status || row.lot_status || row.cycle_status],
		];

		return `
			<div class="lx-bi-dialog-table-wrap">
				<table class="lx-bi-dialog-table">
					<thead>
						<tr>${columns.map(([label]) => `<th>${this.safe(label)}</th>`).join("")}</tr>
					</thead>
					<tbody>
						${rows.map((row) => `
							<tr class="${this.row_class(row)}">
								${columns.map(([, getter]) => `<td>${this.safe(getter(row))}</td>`).join("")}
							</tr>
						`).join("")}
					</tbody>
				</table>
			</div>
		`;
	}

	export_csv() {
		const timeline = this.get_timeline_rows();
		const rows = [];
		rows.push(["Section", "Purchase Date", "Sell Date", "Return Date", "Row Type", "Event", "Lot", "Item", "Reference", "Purchase No", "Sale No", "Sales Return", "Supplier", "Customer", "Purchased Qty", "Current Qty", "Sold Qty", "Returned Qty", "Net Sold Qty", "Cost Price", "Selling Price", "Total Cost", "Selling Amount", "Return Amount", "Profit", "Loss", "Status"]);
		timeline.forEach((row) => {
			rows.push([
				"Truth Timeline",
				this.format_date(this.row_purchase_date(row)),
				this.format_date(this.row_sell_date(row)),
				this.format_date(row.return_date),
				row.row_type || "",
				row.cycle_status || row.event_type || "",
				this.row_lot(row),
				row.item_name || row.item || "",
				this.row_reference(row),
				row.purchase || "",
				row.sale || "",
				row.sales_return || "",
				row.supplier || "",
				row.customer || "",
				this.raw_number(row.purchased_qty),
				this.raw_number(row.current_lot_qty ?? row.running_qty),
				this.raw_number(row.sale_qty),
				this.raw_number(row.return_qty),
				this.raw_number(row.net_sold_qty),
				this.raw_number(this.row_cost_price(row)),
				this.raw_number(this.row_selling_price(row)),
				this.raw_number(row.total_cost),
				this.raw_number(row.selling_amount),
				this.raw_number(row.return_amount),
				this.raw_number(row.profit ?? row.profit_impact),
				this.raw_number(row.loss),
				row.reference_status || row.lot_status || "",
			]);
		});

		const csv = rows.map((row) => row.map((cell) => `"${String(cell ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
		const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
		const url = URL.createObjectURL(blob);
		const link = document.createElement("a");
		link.href = url;
		link.download = `ledgix-business-intelligence-${frappe.datetime.now_date()}.csv`;
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(url);
		this.show_alert("Business Intelligence CSV exported.", "green");
	}

	print_report() {
		window.print();
	}

	// ============================================================
	// STATE HELPERS
	// ============================================================

	normalize_tracking_label(value) {
		const tracking = String(value || "").trim();
		if (["Normal", "Item Based", "Normal Stock"].includes(tracking)) return "Normal Stock";
		if (["All", "Lot Based", "Serial Based"].includes(tracking)) return tracking;
		return tracking;
	}

	get_data() {
		return this.state.data || { summary: {}, story: {}, lots: [], timeline: [], cycle_rows: [], risks: [], meta: {} };
	}

	get_timeline_rows() {
		const data = this.get_data();
		const rows = (data.cycle_rows && data.cycle_rows.length) ? data.cycle_rows : (data.timeline || []);
		return this.sort_timeline_groups(rows);
	}

	sort_timeline_groups(rows) {
		const groups = [];
		const group_map = new Map();
		(rows || []).forEach((row, index) => {
			const lot = this.row_lot(row) || `__row_${index}`;
			if (!group_map.has(lot)) {
				const group = { lot, rows: [], index };
				group_map.set(lot, group);
				groups.push(group);
			}
			group_map.get(lot).rows.push(row);
		});

		groups.forEach((group) => {
			group.rows.sort((a, b) => {
				const a_rank = this.timeline_row_rank(a);
				const b_rank = this.timeline_row_rank(b);
				if (a_rank !== b_rank) return a_rank - b_rank;
				return this.compare_values(this.row_activity_date(a), this.row_activity_date(b), "asc");
			});
			group.sort_value = this.timeline_group_sort_value(group.rows, this.state.timeline_sort_key);
		});

		const direction = this.state.timeline_sort_direction || "desc";
		groups.sort((a, b) => {
			const compared = this.compare_values(a.sort_value, b.sort_value, direction);
			return compared || (a.index - b.index);
		});

		return groups.flatMap((group) => group.rows);
	}

	timeline_group_sort_value(rows, key) {
		const mother = rows.find((row) => this.timeline_row_rank(row) === 0) || rows[0] || {};
		const children = rows.filter((row) => this.timeline_row_rank(row) !== 0);
		const nums = (getter) => rows.map(getter).filter((value) => !this.is_empty(value));
		if (key === "purchase_date") return this.row_purchase_date(mother);
		if (key === "status") return mother.cycle_status || mother.event_type || "";
		if (key === "lot") return this.row_lot(mother);
		if (key === "item") return mother.item_name || mother.item || "";
		if (key === "reference") return this.row_reference(mother);
		if (key === "current_qty") return this.max_numeric(nums((row) => row.current_lot_qty ?? row.running_qty));
		if (key === "sold_qty") return this.max_numeric(nums((row) => row.sale_qty));
		if (key === "return_qty") return this.max_numeric(nums((row) => row.return_qty));
		if (key === "cost_price") return this.max_numeric(nums((row) => this.row_cost_price(row)));
		if (key === "selling_price") return this.max_numeric(nums((row) => this.row_selling_price(row)));
		if (key === "profit_loss") return this.max_numeric(nums((row) => Number(row.profit || row.profit_impact || 0) - Number(row.loss || 0)));
		if (key === "sell_date") return this.max_date(children.map((row) => this.row_sell_date(row)));
		return this.row_purchase_date(mother);
	}

	timeline_row_rank(row) {
		const type = String(row.row_type || "").toLowerCase();
		const event = String(row.cycle_status || row.event_type || "").toLowerCase();
		if (type === "mother" || event === "purchase") return 0;
		if (event.includes("sale") || event.includes("return")) return 1;
		return 2;
	}

	compare_values(a, b, direction = "asc") {
		const multiplier = direction === "desc" ? -1 : 1;
		if (this.is_empty(a) && this.is_empty(b)) return 0;
		if (this.is_empty(a)) return 1;
		if (this.is_empty(b)) return -1;
		const a_date = this.to_time(a);
		const b_date = this.to_time(b);
		if (a_date !== null && b_date !== null) return (a_date - b_date) * multiplier;
		const a_num = Number(a);
		const b_num = Number(b);
		if (Number.isFinite(a_num) && Number.isFinite(b_num)) return (a_num - b_num) * multiplier;
		return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" }) * multiplier;
	}

	to_time(value) {
		if (!value || typeof value !== "string") return null;
		const parsed = Date.parse(value);
		return Number.isNaN(parsed) ? null : parsed;
	}

	max_numeric(values) {
		const numbers = values.map((value) => Number(value)).filter((value) => Number.isFinite(value));
		return numbers.length ? Math.max(...numbers) : "";
	}

	max_date(values) {
		return (values || []).filter(Boolean).sort((a, b) => this.compare_values(a, b, "desc"))[0] || "";
	}

	sort_aria(key) {
		if (this.state.timeline_sort_key !== key) return "none";
		return this.state.timeline_sort_direction === "asc" ? "ascending" : "descending";
	}

	identity_label() {
		const tracking = this.normalize_tracking_label(this.state.tracking_type || "All");
		if (tracking === "Serial Based") return "Serial";
		if (tracking === "Lot Based") return "Lot";
		if (tracking === "Normal Stock") return "Item";
		return "Item / Lot / Serial";
	}

	row_lot(row) {
		return row.lot_number || row.lot_no || row.lot || "";
	}

	row_reference(row) {
		return row.reference || row.purchase || row.sale || row.sales_return || "";
	}

	row_purchase_date(row) {
		if (row.purchase_date) return row.purchase_date;
		const event = String(row.cycle_status || row.event_type || "").toLowerCase();
		return event === "purchase" ? row.date : "";
	}

	row_sell_date(row) {
		if (row.sale_date) return row.sale_date;
		const event = String(row.cycle_status || row.event_type || "").toLowerCase();
		return event.includes("sale") || event.includes("return") ? row.date : "";
	}

	row_activity_date(row) {
		return row.date || row.sale_date || row.return_date || row.purchase_date || "";
	}

	row_cost_price(row) {
		return row.cost_rate ?? row.unit_cost ?? row.purchase_rate;
	}

	row_selling_price(row) {
		return row.sale_rate ?? row.selling_rate;
	}

	reset_pages() {
		this.state.timeline_page = 1;
		this.state.lot_page = 1;
	}

	clamp_pages() {
		this.state.timeline_page = Math.max(1, Math.min(this.state.timeline_page, this.get_total_pages("timeline")));
		this.state.lot_page = Math.max(1, Math.min(this.state.lot_page, this.get_total_pages("lots")));
	}

	get_total_pages(type) {
		const data = this.get_data();
		const count = type === "lots" ? (data.lots || []).length : this.get_timeline_rows().length;
		const size = type === "lots" ? this.lot_page_size : this.timeline_page_size;
		return Math.max(1, Math.ceil(count / size));
	}

	update_date_label() {
		let label = "All Dates";
		if (this.state.from_date && this.state.to_date) {
			label = `${frappe.datetime.str_to_user(this.state.from_date)} - ${frappe.datetime.str_to_user(this.state.to_date)}`;
		} else if (this.state.from_date) {
			label = `From ${frappe.datetime.str_to_user(this.state.from_date)}`;
		} else if (this.state.to_date) {
			label = `Until ${frappe.datetime.str_to_user(this.state.to_date)}`;
		}
		this.$root.find(".lx-bi-date-label").text(label);
	}

	update_mode_class() {
		const mode = String(this.mode_for_entity() || "overview").toLowerCase().replace(/\s+/g, "-");
		const entity_type = String(this.state.entity_type || "global").toLowerCase();
		this.$root.find(".lx-bi-shell")
			.attr("data-mode", mode)
			.attr("data-entity-type", entity_type)
			.attr("data-tracking-type", this.normalize_tracking_label(this.state.tracking_type || "All").toLowerCase().replace(/\s+/g, "-"));
	}

	set_busy(is_busy) {
		this.$root.toggleClass("is-loading", Boolean(is_busy));
		this.$root.find(".lx-js-refresh, .lx-js-export, .lx-js-print").prop("disabled", Boolean(is_busy));
	}

	apply_theme_bridge() {
		const theme = window.LedgixTheme?.get?.() || window.LedgixTheme?.current || window.ledgix_theme || {};
		const theme_enabled = Boolean(theme && theme.enable_custom_accent && theme.primary_accent_color);
		const styles = getComputedStyle(document.documentElement);
		const accent =
			(theme_enabled ? theme.primary_accent_color : "") ||
			(theme_enabled ? window.LedgixTheme?.accent : "") ||
			(theme_enabled ? window.ledgix_theme?.accent : "") ||
			(theme_enabled ? styles.getPropertyValue("--ledgix-accent").trim() : "") ||
			(theme_enabled ? styles.getPropertyValue("--lx-accent").trim() : "") ||
			(theme_enabled ? styles.getPropertyValue("--accent").trim() : "") ||
			null;
		const rgb =
			(theme_enabled ? theme.accent_rgb : "") ||
			(theme_enabled ? window.LedgixTheme?.rgb : "") ||
			(theme_enabled ? window.ledgix_theme?.rgb : "") ||
			(theme_enabled ? styles.getPropertyValue("--ledgix-accent-rgb").trim() : "") ||
			(theme_enabled ? styles.getPropertyValue("--lx-accent-rgb").trim() : "") ||
			"";
		const local_root = this.$root && this.$root.get(0);
			const targets = [local_root, ...Array.from(document.querySelectorAll(".ledgix-app-shell, .lx-bi-page, .lx-bi-shell")), document.documentElement, document.body]
			.filter(Boolean)
			.filter((target, index, list) => list.indexOf(target) === index);

		targets.forEach((target) => {
			if (accent) {
				target.style.setProperty("--bi-accent", accent);
				target.style.setProperty("--lx-accent", accent);
				target.style.setProperty("--ledgix-accent", accent);
				target.setAttribute("data-ledgix-theme", "enabled");
			} else {
				target.style.removeProperty("--bi-accent");
				target.style.removeProperty("--lx-accent");
				target.style.removeProperty("--ledgix-accent");
				target.style.removeProperty("--ledgix-primary");
				target.style.removeProperty("--primary");
				target.style.removeProperty("--accent");
				target.style.removeProperty("--lx-page-accent");
				target.style.removeProperty("--lx-accent-rgb");
				target.style.removeProperty("--ledgix-accent-rgb");
				target.style.removeProperty("--accent-rgb");
				target.setAttribute("data-ledgix-theme", "disabled");
				return;
			}
				target.style.setProperty("--lx-accent-rgb", rgb);
				target.style.setProperty("--ledgix-accent-rgb", rgb);
				target.style.setProperty("--accent-rgb", rgb);
			});
		}

	show_alert(message, indicator = "blue") {
		if (frappe.show_alert) {
			frappe.show_alert({ message, indicator });
		}
	}

	// ============================================================
	// FORMATTERS
	// ============================================================

	empty_html(message) {
		return `<div class="lx-bi-empty"><strong>No data</strong><p>${this.safe(message)}</p></div>`;
	}

	format_value(value, type) {
		if (type === "currency") return this.format_currency(value);
		if (type === "percent") return this.format_percent(value);
		if (type === "number") return this.format_number(value);
		return this.safe(value);
	}

	format_currency(value) {
		if (this.is_empty(value)) return "-";
		return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value) || 0);
	}

	format_percent(value) {
		if (this.is_empty(value)) return "-";
		return `${new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value) || 0)}%`;
	}

	format_number(value) {
		if (this.is_empty(value)) return "-";
		const number = Number(value) || 0;
		return new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(number);
	}

	format_optional_number(value) {
		if (this.is_empty(value)) return "-";
		const number = Number(value) || 0;
		if (number === 0) return "-";
		return new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 }).format(number);
	}

	format_date(value) {
		if (!value) return "-";
		return frappe.datetime.str_to_user(String(value).slice(0, 10));
	}

	format_datetime(value) {
		if (!value) return "-";
		return frappe.datetime.str_to_user(value);
	}

	raw_number(value) {
		if (this.is_empty(value)) return "";
		return Number(value) || 0;
	}

	is_empty(value) {
		return value === null || value === undefined || value === "";
	}

	value_class(value, type) {
		if (!["currency", "percent", "number-delta"].includes(type)) return "";
		if (this.is_empty(value)) return "is-empty";
		const number = Number(value) || 0;
		if (number > 0) return "is-positive";
		if (number < 0) return "is-negative";
		return "is-neutral";
	}

	row_qty(row) {
		if (!this.is_empty(row.sale_qty) || !this.is_empty(row.return_qty)) {
			const event = String(row.event_type || row.cycle_status || "").toLowerCase();
			if (event.includes("return")) return Number(row.return_qty) || 0;
			if (event.includes("purchase")) return Number(row.purchased_qty) || 0;
			return Number(row.sale_qty) || Number(row.net_sold_qty) || 0;
		}
		return row.qty;
	}

	primary_qty(row) {
		const event = String(row.event_type || row.cycle_status || "").toLowerCase();
		if (event.includes("purchase")) return row.purchased_qty ?? row.qty;
		if (!this.is_empty(row.qty)) return row.qty;
		return "";
	}

	format_profit_loss(row) {
		const loss = Number(row.loss) || 0;
		const profit = Number(row.profit ?? row.profit_impact) || 0;
		if (loss > 0) return this.format_currency(loss);
		if (profit > 0) return this.format_currency(profit);
		return "-";
	}

	profit_loss_class(row) {
		const loss = Number(row.loss) || 0;
		const profit = Number(row.profit ?? row.profit_impact) || 0;
		if (loss > 0) return "is-negative";
		if (profit > 0) return "is-positive";
		return "is-neutral";
	}

	row_class(row) {
		const type = String(row.row_type || "").toLowerCase();
		const event = String(row.event_type || row.cycle_status || "activity").toLowerCase().replace(/\s+/g, "-");
		return `is-row-${type || "activity"} is-event-row-${event}`;
	}

	status_class(status) {
		return `is-status-${String(status || "open").toLowerCase().replace(/\s+/g, "-")}`;
	}

	event_class(event) {
		return `is-event-${String(event || "activity").toLowerCase().replace(/\s+/g, "-")}`;
	}

	severity_class(severity) {
		return `is-severity-${String(severity || "info").toLowerCase().replace(/\s+/g, "-")}`;
	}

	get_highest_risk(risks) {
		const order = ["critical", "high", "danger", "warning", "medium", "low", "info"];
		const values = (risks || []).map((risk) => String(risk.severity || "info").toLowerCase());
		return order.find((key) => values.includes(key)) || "clear";
	}

	record_label(count, singular) {
		const safe_count = Number(count) || 0;
		return `${safe_count} ${singular}${safe_count === 1 ? "" : "s"}`;
	}

	safe(value) {
		if (this.is_empty(value)) return "-";
		return frappe.utils.escape_html(String(value));
	}

	safe_attr(value) {
		if (value === null || value === undefined) return "";
		return frappe.utils.escape_html(String(value));
	}

	// ============================================================
	// ICONS
	// ============================================================

	icon(name) {
		const icons = {
			analytics: '<svg viewBox="0 0 24 24"><path d="M4 19V5"/><path d="M4 19h16"/><path d="M8 16V9"/><path d="M12 16V6"/><path d="M16 16v-4"/><path d="M20 16V8"/></svg>',
			search: '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m16 16 4 4"/></svg>',
			refresh: '<svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v6h-6"/></svg>',
			download: '<svg viewBox="0 0 24 24"><path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/></svg>',
			print: '<svg viewBox="0 0 24 24"><path d="M7 9V3h10v6"/><path d="M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><path d="M7 14h10v7H7z"/></svg>',
			box: '<svg viewBox="0 0 24 24"><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="M4 7.5 12 12l8-4.5"/><path d="M12 12v9"/></svg>',
			trend: '<svg viewBox="0 0 24 24"><path d="M4 17 10 11l4 4 6-8"/><path d="M14 7h6v6"/></svg>',
			warning: '<svg viewBox="0 0 24 24"><path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5"/><path d="M12 17h.01"/></svg>',
			flow: '<svg viewBox="0 0 24 24"><path d="M4 7h11"/><path d="m12 4 3 3-3 3"/><path d="M20 17H9"/><path d="m12 14-3 3 3 3"/></svg>',
			spark: '<svg viewBox="0 0 24 24"><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3Z"/><path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z"/></svg>',
			cube: '<svg viewBox="0 0 24 24"><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="M3 7v10l9 5 9-5V7"/><path d="M12 12v10"/></svg>',
			timeline: '<svg viewBox="0 0 24 24"><path d="M12 5v14"/><circle cx="12" cy="6" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="18" r="2"/><path d="M14 6h5"/><path d="M5 12h5"/><path d="M14 18h5"/></svg>',
			shield: '<svg viewBox="0 0 24 24"><path d="M12 3 20 6v6c0 5-3.4 8-8 9-4.6-1-8-4-8-9V6l8-3Z"/><path d="m9 12 2 2 4-5"/></svg>',
			filter: '<svg viewBox="0 0 24 24"><path d="M4 5h16"/><path d="M7 12h10"/><path d="M10 19h4"/></svg>',
			table: '<svg viewBox="0 0 24 24"><path d="M4 5h16v14H4z"/><path d="M4 10h16"/><path d="M9 5v14"/><path d="M15 5v14"/></svg>',
			left: '<svg viewBox="0 0 24 24"><path d="m15 18-6-6 6-6"/></svg>',
			right: '<svg viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></svg>',
		};
		return icons[name] || icons.analytics;
	}
}
