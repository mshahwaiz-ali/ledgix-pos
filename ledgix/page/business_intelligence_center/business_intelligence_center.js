/* global frappe */

frappe.pages["business-intelligence-center"].on_page_load = function (wrapper) {
	frappe.ledgix_inventory_intelligence = new LedgixInventoryIntelligence(wrapper);
};

class LedgixInventoryIntelligence {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: "Inventory Intelligence",
			single_column: true,
		});
		this.page.clear_actions_menu();
		this.method = "ledgix_saas.api.inventory_intelligence.get_inventory_intelligence_data";
		this.riskPreviewLimit = 8;
		this.timelinePageSize = 150;
		this.requestSerial = 0;
		this.suppressControlReload = false;
		this.state = {
			item: "",
			tracking_type: "All",
			from_date: "",
			to_date: "",
			search: "",
			loading: false,
			data: null,
			risks_expanded: false,
			timeline_limit: this.timelinePageSize,
		};
		this.searchTimer = null;
		this.render_shell();
		this.make_controls();
		this.bind_events();
		this.load_data();
	}

	async call(method, args = {}) {
		const response = await frappe.call({ method, args, freeze: false });
		return response.message || {};
	}

	escape(value) {
		return frappe.utils.escape_html(String(value ?? ""));
	}

	money(value) {
		return `Rs. ${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
	}

	number(value, digits = 0) {
		return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });
	}

	percent(value) {
		return `${this.number(value, 1)}%`;
	}

	render_shell() {
		this.$root = $(this.page.body).empty();
		this.$root.html(`
			<div class="lx-ii-v2">
				<section class="lx-ii-intro">
					<div>
						<div class="lx-ii-kicker">Manager investigation</div>
						<h2>Inventory Intelligence</h2>
						<p>Trace stock movement, realized margin, returns, lot/serial identity and inventory risks across submitted transactions.</p>
					</div>
					<div class="lx-ii-native-actions">
						<button class="btn btn-default btn-sm" data-route-list="Ledgix Item">Items</button>
						<button class="btn btn-default btn-sm" data-route-list="Ledgix Stock Movement">Stock Movements</button>
						<button class="btn btn-default btn-sm" data-route-report="Ledgix Current Stock">Current Stock</button>
					</div>
				</section>
				<section class="lx-ii-filter-card">
					<div class="lx-ii-control lx-ii-item-control"></div>
					<div class="lx-ii-control lx-ii-tracking-control"></div>
					<div class="lx-ii-control lx-ii-from-control"></div>
					<div class="lx-ii-control lx-ii-to-control"></div>
					<div class="lx-ii-search-wrap"><label>Search activity</label><input class="form-control lx-ii-search" placeholder="Sale, purchase, lot, serial, customer, supplier…"></div>
					<div class="lx-ii-filter-actions"><button class="btn btn-default lx-ii-reset">Reset</button><button class="btn btn-primary lx-ii-refresh">Refresh</button></div>
				</section>
				<div class="lx-ii-content"></div>
			</div>
		`);
	}

	make_controls() {
		this.itemControl = frappe.ui.form.make_control({
			parent: this.$root.find(".lx-ii-item-control")[0],
			df: { fieldname: "item", label: "Item", fieldtype: "Link", options: "Ledgix Item", placeholder: "All Items" },
			render_input: true,
		});
		this.trackingControl = frappe.ui.form.make_control({
			parent: this.$root.find(".lx-ii-tracking-control")[0],
			df: { fieldname: "tracking_type", label: "Tracking", fieldtype: "Select", options: "All\nNormal Stock\nLot Based\nSerial Based", default: "All" },
			render_input: true,
		});
		this.fromControl = frappe.ui.form.make_control({
			parent: this.$root.find(".lx-ii-from-control")[0],
			df: { fieldname: "from_date", label: "From", fieldtype: "Date" },
			render_input: true,
		});
		this.toControl = frappe.ui.form.make_control({
			parent: this.$root.find(".lx-ii-to-control")[0],
			df: { fieldname: "to_date", label: "To", fieldtype: "Date" },
			render_input: true,
		});
		[this.itemControl, this.trackingControl, this.fromControl, this.toControl].forEach(control => control?.$wrapper?.addClass("lx-ii-frappe-control"));
	}

	bind_events() {
		this.$root.on("click", ".lx-ii-refresh", () => this.load_data());
		this.$root.on("click", ".lx-ii-reset", () => this.reset_filters());
		this.$root.on("keydown", ".lx-ii-search", (event) => {
			if (event.key === "Enter") {
				event.preventDefault();
				clearTimeout(this.searchTimer);
				this.load_data();
			}
		});
		this.$root.on("input", ".lx-ii-search", (event) => {
			this.state.search = event.currentTarget.value || "";
			clearTimeout(this.searchTimer);
			this.searchTimer = setTimeout(() => this.load_data(), 350);
		});
		this.$root.on("click", ".lx-ii-risk-toggle", () => {
			this.state.risks_expanded = !this.state.risks_expanded;
			this.render_data();
		});
		this.$root.on("click", ".lx-ii-timeline-more", () => {
			const rows = this.current_timeline();
			this.state.timeline_limit = Math.min(this.state.timeline_limit + this.timelinePageSize, rows.length);
			this.render_data();
		});
		this.$root.on("click", ".lx-ii-timeline-less", () => {
			this.state.timeline_limit = this.timelinePageSize;
			this.render_data();
		});
		this.$root.on("click", "[data-route-list]", (event) => frappe.set_route("List", $(event.currentTarget).data("route-list"), "List"));
		this.$root.on("click", "[data-route-report]", (event) => frappe.set_route("query-report", $(event.currentTarget).data("route-report")));
		this.$root.on("click", "[data-route-doc]", (event) => this.open_reference($(event.currentTarget)));

		const reloadFromControl = () => {
			if (!this.suppressControlReload) this.load_data();
		};
		this.itemControl?.$input?.on("change", reloadFromControl);
		this.trackingControl?.$input?.on("change", reloadFromControl);
		this.fromControl?.$input?.on("change", reloadFromControl);
		this.toControl?.$input?.on("change", reloadFromControl);
	}

	async reset_filters() {
		clearTimeout(this.searchTimer);
		this.suppressControlReload = true;
		try {
			await this.itemControl.set_value("");
			await this.trackingControl.set_value("All");
			await this.fromControl.set_value("");
			await this.toControl.set_value("");
		} finally {
			this.suppressControlReload = false;
		}
		this.$root.find(".lx-ii-search").val("");
		this.state.search = "";
		await this.load_data();
	}

	get_filters() {
		return {
			item: this.itemControl.get_value() || "",
			tracking_type: this.trackingControl.get_value() || "All",
			from_date: this.fromControl.get_value() || "",
			to_date: this.toControl.get_value() || "",
			search: (this.$root.find(".lx-ii-search").val() || "").trim(),
			mode: "Overview",
		};
	}

	async load_data() {
		const requestId = ++this.requestSerial;
		const filters = this.get_filters();
		Object.assign(this.state, filters);
		this.set_loading(true);
		try {
			const data = await this.call(this.method, filters);
			if (requestId !== this.requestSerial) return;
			this.state.data = data;
			this.state.risks_expanded = false;
			this.state.timeline_limit = this.timelinePageSize;
			this.render_data();
		} catch (error) {
			if (requestId !== this.requestSerial) return;
			console.error("Inventory Intelligence load failed", error);
			this.render_error("Inventory Intelligence could not load. Check manager permissions and try again.");
		} finally {
			if (requestId === this.requestSerial) this.set_loading(false);
		}
	}

	set_loading(value) {
		this.state.loading = !!value;
		this.$root.toggleClass("is-loading", !!value);
		this.$root.find(".lx-ii-refresh").prop("disabled", !!value).text(value ? "Loading…" : "Refresh");
	}

	current_timeline() {
		const data = this.state.data || {};
		return data.cycle_rows || data.timeline || [];
	}

	render_data() {
		const data = this.state.data || {};
		const summary = data.summary || {};
		const story = data.story || {};
		const risks = data.risks || [];
		const timeline = this.current_timeline();
		const identities = data.lots || [];
		const meta = data.meta || {};
		this.$root.find(".lx-ii-content").html(`
			<section class="lx-ii-summary-grid">
				${this.metric("Current Qty", summary.current_qty, "qty")}
				${this.metric("Net Sold", summary.net_sold_qty, "qty")}
				${this.metric("Net Revenue", summary.net_revenue, "money")}
				${this.metric("Net Profit", summary.net_profit, "money", Number(summary.net_profit || 0) < 0 ? "danger" : "")}
				${this.metric("Margin", summary.margin_percent, "percent")}
				${this.metric("Return Rate", summary.return_rate_percent, "percent", Number(summary.return_rate_percent || 0) >= 30 ? "warning" : "")}
				${this.metric("Sell-through", summary.sell_through_percent, "percent")}
				${this.metric("Risk", summary.risk_level || "Low", "text", this.risk_tone(summary.risk_level))}
			</section>
			<section class="lx-ii-story-risk-grid" style="align-items: start;">
				<div class="lx-ii-card lx-ii-story ${this.escape(story.tone || "neutral")}">
					<div class="lx-ii-card-head"><div><h3>${this.escape(story.title || "Inventory story")}</h3><p>${this.escape(story.text || "No activity matched the current filters.")}</p></div></div>
					${(story.signals || []).length ? `<div class="lx-ii-signals">${story.signals.map(signal => `<span>${this.escape(signal)}</span>`).join("")}</div>` : ""}
				</div>
				<div class="lx-ii-card">
					<div class="lx-ii-card-head"><div><h3>Risk review</h3><p>${risks.length ? `${risks.length} signal(s) need attention.` : "No risk signals in the selected scope."}</p></div></div>
					${this.risks_html(risks)}
				</div>
			</section>
			<section class="lx-ii-card">
				<div class="lx-ii-card-head"><div><h3>Transaction timeline</h3><p>Submitted purchase, sale and return events in one traceable view.</p></div><span class="lx-ii-meta">${this.timeline_meta_label(timeline, meta)}</span></div>
				${this.timeline_html(timeline, meta)}
			</section>
			${identities.length ? `<section class="lx-ii-card"><div class="lx-ii-card-head"><div><h3>Lot performance</h3><p>Lot-level sell-through, margin and return behavior.</p></div><button class="btn btn-default btn-xs" data-route-list="Ledgix Stock Lot">Open Stock Lots</button></div>${this.identities_html(identities)}</section>` : ""}
		`);
	}

	metric(label, value, type, tone = "") {
		let display = value ?? 0;
		if (type === "money") display = this.money(value);
		if (type === "qty") display = this.number(value, 2);
		if (type === "percent") display = this.percent(value);
		return `<div class="lx-ii-metric ${tone ? `is-${tone}` : ""}"><span>${this.escape(label)}</span><strong>${this.escape(display)}</strong></div>`;
	}

	risk_tone(level) {
		return ({ Critical: "danger", High: "danger", Medium: "warning", Low: "good" })[level] || "";
	}

	risks_html(risks) {
		if (!risks.length) return '<div class="lx-ii-empty lx-ii-empty-small">No current risk signals.</div>';
		const expanded = this.state.risks_expanded;
		const visible = expanded ? risks : risks.slice(0, this.riskPreviewLimit);
		const cards = visible.map(risk => `<div class="lx-ii-risk"><span class="lx-ii-risk-level is-${this.escape(String(risk.severity || "Info").toLowerCase())}">${this.escape(risk.severity || "Info")}</span><div><strong>${this.escape(risk.title || "Risk")}</strong><p>${this.escape(risk.message || "")}</p>${risk.reference ? `<small>${this.escape(risk.reference)}</small>` : ""}</div></div>`).join("");
		let toggle = "";
		if (risks.length > this.riskPreviewLimit) {
			const remaining = risks.length - this.riskPreviewLimit;
			const label = expanded ? "Show less" : `Show all ${risks.length} · ${remaining} more`;
			toggle = `<div class="lx-ii-more"><button class="btn btn-default btn-xs lx-ii-risk-toggle" type="button">${this.escape(label)}</button></div>`;
		}
		return `<div class="lx-ii-risk-list">${cards}${toggle}</div>`;
	}

	timeline_meta_label(rows, meta) {
		const loaded = Number(meta.timeline_loaded_count ?? rows.length);
		return this.escape(`${loaded} loaded event${loaded === 1 ? "" : "s"}`);
	}

	timeline_html(rows, meta = {}) {
		if (!rows.length) return '<div class="lx-ii-empty">No inventory activity matched the current filters.</div>';
		const visibleCount = Math.min(Math.max(this.state.timeline_limit, this.timelinePageSize), rows.length);
		const visibleRows = rows.slice(0, visibleCount);
		const body = visibleRows.map(row => this.timeline_row_html(row)).join("");
		const remaining = rows.length - visibleCount;
		const actions = [];
		if (remaining > 0) {
			const nextCount = Math.min(this.timelinePageSize, remaining);
			actions.push(`<button class="btn btn-default btn-xs lx-ii-timeline-more" type="button">Load ${nextCount} more</button>`);
		}
		if (visibleCount > this.timelinePageSize) {
			actions.push(`<button class="btn btn-default btn-xs lx-ii-timeline-less" type="button">Show first ${this.timelinePageSize}</button>`);
		}
		const cap = Number(meta.timeline_result_cap || 500);
		const capNote = meta.timeline_cap_reached
			? ` Result cap reached at ${cap} loaded events; narrow the filters to investigate older or more specific activity.`
			: "";
		const note = (rows.length > this.timelinePageSize || meta.timeline_cap_reached)
			? `<div class="lx-ii-table-note"><span>Showing ${visibleCount} of ${rows.length} loaded events.${this.escape(capNote)}</span>${actions.length ? `<span class="lx-ii-table-note-actions">${actions.join("")}</span>` : ""}</div>`
			: "";
		return `<div class="lx-ii-table-wrap"><table class="lx-ii-table"><thead><tr><th>Date</th><th>Event</th><th>Item / Identity</th><th>Reference</th><th>Party</th><th>Qty</th><th>Running Qty</th><th>Rate</th><th>Profit</th></tr></thead><tbody>${body}</tbody></table>${note}</div>`;
	}

	timeline_row_html(row) {
		const event = row.cycle_status || row.event_type || "Activity";
		const identity = row.serial_no || row.lot_number || "";
		const isReturn = ["Return", "Partial Return"].includes(event);
		const reference = isReturn ? (row.sales_return || row.reference || row.sale || "") : (row.reference || row.sale || row.purchase || row.sales_return || "");
		let qty = Number(row.qty || 0);
		if (event === "Sale") qty = -Number(row.sale_qty || row.qty || 0);
		else if (isReturn) qty = Number(row.return_qty || row.qty || 0);
		else if (event === "Purchase") qty = Number(row.purchased_qty || row.qty || 0);
		else if (event === "Cancel") qty = Number(row.return_qty || 0);
		const rate = Number(row.sale_rate || 0) || Number(row.cost_rate || row.unit_cost || 0);
		const profit = Number(row.profit || row.profit_impact || 0) - Number(row.loss || 0);
		return `<tr><td>${this.escape(row.date || row.purchase_date || row.sale_date || row.return_date || "—")}</td><td><span class="lx-ii-event is-${this.escape(String(event).toLowerCase().replace(/\s+/g, "-"))}">${this.escape(event)}</span></td><td><strong>${this.escape(row.item_name || row.item || "—")}</strong><small>${this.escape(identity)}</small></td><td>${this.reference_button(event, reference)}</td><td>${this.escape(row.customer || row.supplier || "—")}</td><td>${this.number(qty, 2)}</td><td>${this.number(row.current_lot_qty ?? row.running_qty ?? 0, 2)}</td><td>${this.money(rate)}</td><td class="${profit < 0 ? "is-negative" : profit > 0 ? "is-positive" : ""}">${this.money(profit)}</td></tr>`;
	}

	reference_button(event, reference) {
		if (!reference) return "—";
		if (String(reference).includes(",")) return this.escape(reference);
		let doctype = "";
		if (event === "Purchase") doctype = "Ledgix Purchase";
		if (event === "Sale") doctype = "Ledgix Sale";
		if (["Return", "Partial Return"].includes(event)) doctype = "Ledgix Sales Return";
		if (!doctype) return this.escape(reference);
		return `<button class="lx-ii-link" data-route-doc="${this.escape(doctype)}" data-name="${this.escape(reference)}">${this.escape(reference)}</button>`;
	}

	open_reference($button) {
		const doctype = $button.data("route-doc");
		const name = $button.data("name");
		if (doctype && name) frappe.set_route("Form", doctype, name);
	}

	identities_html(rows) {
		return `<div class="lx-ii-table-wrap"><table class="lx-ii-table"><thead><tr><th>Lot</th><th>Item</th><th>Supplier</th><th>Purchased</th><th>Remaining</th><th>Sell-through</th><th>Return Rate</th><th>Profit</th><th>Status</th></tr></thead><tbody>${rows.slice(0, 100).map(row => `<tr><td><strong>${this.escape(row.lot_number || "—")}</strong><small>${this.escape(row.purchase_date || "")}</small></td><td>${this.escape(row.item_name || row.item || "—")}</td><td>${this.escape(row.supplier || "—")}</td><td>${this.number(row.purchased_qty, 2)}</td><td>${this.number(row.remaining_qty, 2)}</td><td>${this.percent(row.sell_through_percent)}</td><td>${this.percent(row.return_rate_percent)}</td><td class="${Number(row.profit || 0) < 0 ? "is-negative" : Number(row.profit || 0) > 0 ? "is-positive" : ""}">${this.money(row.profit)}</td><td><span class="lx-ii-lot-status">${this.escape(row.lot_status || row.source_status || "Open")}</span></td></tr>`).join("")}</tbody></table></div>`;
	}

	render_error(message) {
		this.$root.find(".lx-ii-content").html(`<div class="lx-ii-empty is-error">${this.escape(message)}</div>`);
	}
}
