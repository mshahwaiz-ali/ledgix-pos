frappe.pages["ledgix-dashboard"].on_page_load = function(wrapper) {
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

	new LedgixCommandCenter(page, wrapper);
};

class LedgixCommandCenter {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = $(wrapper);
		this.state = {
			data: null,
			range: 7,
			from_date: null,
			to_date: null,
			mode: "Strict Inventory",
			loading: true
		};
		window.ledgix_dashboard_v2 = this;
		this.init();
	}

	init() {
		this.build_shell();
		this.bind_events();
		this.load_data();
	}

	build_shell() {
		this.page.main.empty();
		this.$root = $(`
			<div class="ledgix-dashboard-v2 lx-command-center">
				<section class="lx-dash-header"></section>
				<section class="lx-priority-strip">
					<div class="lx-actions-panel"></div>
					<div class="lx-payment-panel"></div>
				</section>
				<section class="lx-pulse-grid"></section>
				<section class="lx-command-grid">
					<div class="lx-command-main">
						<section class="lx-alerts-panel"></section>
						<section class="lx-trend-panel"></section>
						<section class="lx-fast-panel"></section>
					</div>
					<div class="lx-command-side">
						<section class="lx-shift-panel"></section>
						<section class="lx-inventory-panel"></section>
						<section class="lx-risk-panel"></section>
					</div>
				</section>
			</div>
		`);

		this.page.main.append(this.$root);
		window.LedgixNavigator?.mount?.({
			page: this.page,
			wrapper: this.wrapper,
			content: this.$root,
			active: "dashboard"
		});
		this.show_loading_state();
	}

	bind_events() {
		this.$root.on("click", "[data-lx-refresh]", () => this.load_data(true));
		this.$root.on("click", "[data-lx-range]", (event) => {
			const range = this.to_number($(event.currentTarget).attr("data-lx-range")) || 7;
			if (range === this.state.range && !this.state.from_date && !this.state.to_date) return;
			this.state.range = range;
			this.state.from_date = null;
			this.state.to_date = null;
			this.load_data(true);
		});
		this.$root.on("click", "[data-lx-custom-range-toggle]", () => {
			this.$root.find(".lx-date-popover").toggleClass("is-open");
		});
		this.$root.on("click", "[data-lx-apply-range]", () => {
			const from_date = this.$root.find("[data-lx-from-date]").val() || null;
			const to_date = this.$root.find("[data-lx-to-date]").val() || null;
			if (!from_date && !to_date) return;
			this.state.from_date = from_date;
			this.state.to_date = to_date;
			this.$root.find(".lx-date-popover").removeClass("is-open");
			this.load_data(true);
		});
		this.$root.on("click", "[data-lx-clear-range]", () => {
			this.state.from_date = null;
			this.state.to_date = null;
			this.$root.find("[data-lx-from-date], [data-lx-to-date]").val("");
			this.$root.find(".lx-date-popover").removeClass("is-open");
			this.load_data(true);
		});
		this.$root.on("click", "[data-lx-route]", (event) => {
			const $button = $(event.currentTarget);
			if ($button.prop("disabled") || $button.attr("aria-disabled") === "true") return;
			this.safe_route($button.attr("data-lx-route"));
		});
		window.addEventListener("ledgix:theme-updated", (event) => {
			this.apply_theme_settings(event.detail || {});
		});
	}

	load_data(is_refresh = false) {
		this.state.loading = true;
		this.$root.toggleClass("is-refreshing", Boolean(is_refresh));
		if (!this.state.data) this.show_loading_state();

		frappe.call({
			method: "ledgix_saas.ledgix.page.ledgix_dashboard.ledgix_dashboard.get_decision_dashboard_data",
			args: {
				days: this.state.range,
				from_date: this.state.from_date,
				to_date: this.state.to_date
			},
			callback: (response) => {
				this.state.loading = false;
				this.$root.removeClass("is-refreshing");
				const data = response.message || {};
				this.state.data = data;
				window.ledgix_dashboard_data = data;
				this.state.mode = this.get_value(data, "meta.stock_control_mode", "Strict Inventory");
				window.LedgixNavigator?.setMode?.(this.state.mode);
				this.apply_theme_variables(data);
				this.render();
			},
			error: () => {
				this.state.loading = false;
				this.$root.removeClass("is-refreshing");
				this.show_error_state();
			}
		});
	}

	render() {
		const data = this.state.data || {};
		this.render_header(data);
		this.render_pulse(data);
		this.render_alerts(data);
		this.render_trend(data);
		this.render_payment_distribution(data);
		this.render_shift(data);
		this.render_inventory(data);
		this.render_fast_moving(data);
		this.render_recent_activity(data);
		this.render_quick_actions(data);
	}

	// Header and business pulse
	render_header(data) {
		const meta = data.meta || {};
		const business_date = meta.business_date || frappe.datetime?.get_today?.() || "";
		this.$root.find(".lx-dash-header").html(`
			<div class="lx-header-copy">
				<div>
					<h1>Ledgix Dashboard</h1>
					<p>Business Command Center</p>
				</div>
				<div class="lx-header-meta">
					<span>${this.icon("calendar")} ${this.safe_text(this.format_date(business_date))}</span>
					<span>${this.icon("clock")} Updated ${this.safe_text(this.format_time(meta.last_updated))}</span>
				</div>
			</div>
			<button class="lx-icon-btn" type="button" data-lx-refresh aria-label="Refresh dashboard">
				${this.icon("refresh")}
			</button>
		`);
	}

	render_pulse(data) {
		const pulse = data.business_pulse || {};
		const cards = [
			{ label: "Net Sales Today", value: this.format_currency(pulse.net_sales), delta: pulse.sales_vs_yesterday_percent, icon: "sales", tone: "sales" },
			{ label: "Gross Profit Today", value: this.format_currency(pulse.gross_profit), delta: pulse.profit_vs_yesterday_percent, icon: "profit", tone: this.to_number(pulse.gross_profit) < 0 ? "danger" : "profit" },
			{ label: "Profit Margin", value: this.format_percent(pulse.profit_margin), delta: pulse.profit_vs_yesterday_percent, icon: "margin", tone: this.to_number(pulse.profit_margin) < 10 ? "warning" : "profit" },
			{ label: "Invoice Count", value: this.format_number(pulse.invoice_count), delta: null, icon: "invoice", tone: "invoice" },
			{ label: "Expected Cash", value: this.format_currency(pulse.expected_cash || pulse.cash_sales), delta: null, icon: "cash", tone: "cash", sub: `${this.format_currency(pulse.cash_sales)} cash` }
		];
		this.$root.find(".lx-pulse-grid").html(cards.map((card) => this.pulse_card(card)).join(""));
	}

	pulse_card(card) {
		return `
			<article class="lx-pulse-card is-${this.safe_attr(card.tone)}">
				<div class="lx-card-icon">${this.icon(card.icon)}</div>
				<div>
					<span>${this.safe_text(card.label)}</span>
					<strong>${this.safe_text(card.value)}</strong>
					<small>${card.delta === null || card.delta === undefined ? this.safe_text(card.sub || "Today") : this.delta_text(card.delta)}</small>
				</div>
			</article>
		`;
	}

	// Action panels
	render_alerts(data) {
		const alerts = (data.alerts || []).slice(0, 6);
		this.$root.find(".lx-alerts-panel").html(`
			${this.panel_head("Action Required", "Operational checks that need owner attention")}
			<div class="lx-alert-grid">
				${alerts.length ? alerts.map((alert) => this.alert_card(alert)).join("") : this.empty_state("No action required right now.")}
			</div>
		`);
	}

	alert_card(alert) {
		const disabled = alert.disabled || !alert.route;
		return `
			<article class="lx-alert-card is-${this.safe_attr(alert.severity || "info")}">
				<div class="lx-alert-top">
					<strong>${this.safe_text(alert.title)}</strong>
					<span>${this.format_alert_count(alert.count)}</span>
				</div>
				<p>${this.safe_text(alert.message)}</p>
				<button class="lx-soft-btn" type="button" ${disabled ? "disabled aria-disabled=\"true\"" : ""} data-lx-route="${this.safe_attr(alert.route || "")}">
					${this.safe_text(alert.action_label || "Open")}
				</button>
			</article>
		`;
	}

	render_trend(data) {
		const rows = (data.trend || []);
		this.$root.find(".lx-trend-panel").html(`
			<div class="lx-panel-head lx-panel-head-row">
				<div>
					<h2>Sales & Profit Trend</h2>
					<p>Revenue and profit over the selected range</p>
				</div>
				<div class="lx-trend-controls">
					<div class="lx-segmented" role="group" aria-label="Trend range">
						${[7, 15, 30].map((range) => `
							<button type="button" class="${range === this.state.range && !this.state.from_date && !this.state.to_date ? "is-active" : ""}" data-lx-range="${range}">${range}D</button>
						`).join("")}
					</div>
					<div class="lx-date-filter">
						<button type="button" class="${this.state.from_date || this.state.to_date ? "is-active" : ""}" data-lx-custom-range-toggle>${this.icon("calendar")} Range</button>
						<div class="lx-date-popover">
							<label>From<input type="date" data-lx-from-date value="${this.safe_attr(this.state.from_date || "")}"></label>
							<label>To<input type="date" data-lx-to-date value="${this.safe_attr(this.state.to_date || "")}"></label>
							<div><button type="button" data-lx-clear-range>Clear</button><button type="button" data-lx-apply-range>Apply</button></div>
						</div>
					</div>
				</div>
			</div>
			${this.line_chart(rows)}
		`);
	}

	render_payment_distribution(data) {
		const rows = (data.payment_distribution || [])
			.map((row) => ({
				label: this.normalize_payment_label(row.label || "Unknown"),
				value: this.to_number(row.value)
			}))
			.filter((row) => row.value > 0)
			.slice(0, 6);
		const total = rows.reduce((sum, row) => sum + row.value, 0);
		const cash = rows.filter((row) => /cash/i.test(row.label)).reduce((sum, row) => sum + row.value, 0);
		const non_cash = Math.max(0, total - cash);

		this.$root.find(".lx-payment-panel").html(`
			<div class="lx-panel-head lx-panel-head-row">
				<div>
					<h2>Collection Mix</h2>
					<p>Cash and digital collection split</p>
				</div>
				<strong class="lx-panel-total">${this.format_currency(total)}</strong>
			</div>
			${rows.length && total ? `
				<div class="lx-payment-summary">
					<div class="lx-payment-total-card">
						<span>Total Collection</span>
						<strong>${this.format_currency(total)}</strong>
						<small>${cash ? `Cash ${this.format_percent(cash / total * 100)}` : "Digital-first collection"}</small>
					</div>
					<div class="lx-payment-split-card">
						${this.metric_row("Cash", this.format_currency(cash), cash ? "success" : "muted")}
						${this.metric_row("Digital", this.format_currency(non_cash), non_cash ? "invoice" : "muted")}
					</div>
				</div>
				<div class="lx-payment-wrap">
					<div
						class="lx-donut"
						tabindex="0"
						style="${this.donut_style(rows, total)}"
						aria-label="${this.safe_attr(this.payment_tooltip_text(rows, total))}"
					>
						<span class="lx-donut-center">${this.format_currency(total)}</span>
						${this.payment_tooltip_html(rows, total)}
					</div>
					<div class="lx-payment-list">
						${rows.map((row, index) => {
							const percent = row.value / total * 100;
							return `
								<div class="lx-payment-row">
									<div class="lx-payment-row-main"><i style="background:${this.payment_color(row.label, index)}"></i><span>${this.safe_text(row.label)}</span></div>
									<strong>${this.format_currency(row.value)}</strong>
									<small>${this.format_percent(percent)}</small>
									<div class="lx-payment-bar"><span style="width:${Math.max(3, Math.min(100, percent))}%; background:${this.payment_color(row.label, index)}"></span></div>
								</div>
							`;
						}).join("")}
					</div>
				</div>
			` : this.empty_state("No payment collections in this range.")}
		`);
	}

	render_shift(data) {
		const shift = data.shift || {};
		const status = shift.status || "not_configured";
		const shift_route = "/app/ledgix_operations?module=pos-shifts";
		const helper_text = shift.opened_by
			? `Opened by ${this.safe_text(shift.opened_by)}`
			: "Open or close POS shifts";
		const action_label = status === "open" ? "Review Active Shift" : "Open Shift Control";

		this.$root.find(".lx-shift-panel").html(`
			${this.panel_head("Active Shift / Cash Control", "Dashboard summary")}
			<div class="lx-shift-status is-${this.safe_attr(status)}">
				<span>${this.icon("shift")}</span>
				<div>
					<strong>${this.safe_text(this.title_case(status.replace(/_/g, " ")))}</strong>
					<small>${helper_text}</small>
				</div>
			</div>
			<div class="lx-metric-list">
				${this.metric_row("Opening cash", this.format_currency(shift.opening_cash))}
				${this.metric_row("Cash sales", this.format_currency(shift.cash_sales))}
				${this.metric_row("Non-cash sales", this.format_currency(shift.non_cash_sales))}
				${this.metric_row("Expected cash", this.format_currency(shift.expected_cash))}
				${this.metric_row("Variance", this.format_currency(shift.variance), this.to_number(shift.variance) ? "danger" : "muted")}
			</div>
			<button class="lx-soft-btn lx-full-btn" type="button" data-lx-route="${this.safe_attr(shift_route)}">${this.safe_text(action_label)}</button>
		`);
	}

	render_inventory(data) {
		const inv = data.inventory || {};
		const total = Math.max(1, this.to_number(inv.total_items));
		const danger = this.to_number(inv.out_of_stock);
		const warning = this.to_number(inv.low_stock);
		const health = Math.max(0, Math.min(100, 100 - ((danger * 2 + warning) / total * 100)));
		this.$root.find(".lx-inventory-panel").html(`
			${this.panel_head("Inventory Health", "Stock risk summary")}
			<div class="lx-health-meter">
				<div><span style="width:${health}%"></span></div>
				<strong>${Math.round(health)}%</strong>
			</div>
			<div class="lx-metric-list">
				${this.metric_row("Inventory value", this.format_currency(inv.inventory_value))}
				${this.metric_row("Low stock", this.format_number(inv.low_stock), warning ? "warning" : "muted")}
				${this.metric_row("Out of stock", this.format_number(inv.out_of_stock), danger ? "danger" : "muted")}
				${this.metric_row("Total items", this.format_number(inv.total_items))}
				${this.metric_row("Tracked lots", this.format_number(inv.tracked_lots || inv.lot_count))}
				${this.metric_row("Tracked serials", this.format_number(inv.tracked_serials || inv.serial_count))}
			</div>
			<button class="lx-soft-btn lx-full-btn lx-serial-lot-link" type="button" data-lx-route="/app/business-intelligence-center">Review Serial/Lot Intelligence</button>
		`);
	}

	render_fast_moving(data) {
		const rows = (data.fast_moving_items || []).slice(0, 5);
		this.$root.find(".lx-fast-panel").html(`
			${this.panel_head("Fast Moving Items", "Top 5 by quantity sold")}
			${rows.length ? `
				<div class="lx-compact-table">
					${rows.map((row) => `
						<div class="lx-table-row">
							<strong>${this.safe_text(row.item)}</strong>
							<span>${this.format_number(row.quantity)} qty</span>
							<em>${this.format_currency(row.revenue)}</em>
						</div>
					`).join("")}
				</div>
			` : this.empty_state("No item sales in this range.")}
			<button class="lx-soft-btn lx-full-btn" type="button" data-lx-route="/app/business-intelligence-center">Open BI Center</button>
		`);
	}

	render_recent_activity(data) {
		const rows = (data.recent_activity || []).slice(0, 5);
		this.$root.find(".lx-risk-panel").html(`
			${this.panel_head("Recent Risk Activity", "Latest operational events")}
			${rows.length ? `
				<div class="lx-risk-list">
					${rows.map((row) => `
						<div class="lx-risk-row" role="button" tabindex="0" data-lx-route="${this.safe_attr(this.activity_route(row.type))}">
							<div>
								<strong>${this.safe_text(row.document)}</strong>
								<span>${this.safe_text(row.date)}</span>
							</div>
							<span class="lx-type-badge">${this.safe_text(row.type)}</span>
							<em>${row.amount === null || row.amount === undefined ? `${this.format_number(row.qty)} qty` : this.format_currency(row.amount)}</em>
							<span class="lx-risk-badge is-${this.safe_attr(row.risk || "normal")}">${this.safe_text(row.risk || "normal")}</span>
						</div>
					`).join("")}
				</div>
			` : this.empty_state("No recent risk activity found.")}
		`);
	}

	render_quick_actions(data) {
		const raw_actions = ((data.quick_actions && data.quick_actions.length) ? data.quick_actions : this.default_quick_actions()).slice(0, 6);
		const actions = raw_actions.map((action) => this.normalize_quick_action(action));

		this.$root.find(".lx-actions-panel").html(`
			<div class="lx-panel-head lx-panel-head-row">
				<div>
					<h2>Quick Actions</h2>
					<p>Start the most common Ledgix workflows</p>
				</div>
				<span class="lx-mini-badge">Owner shortcuts</span>
			</div>
			<div class="lx-action-grid">
				${actions.map((action) => `
					<button class="lx-action-btn ${action.label === "New Purchase" ? "is-primary" : ""}" type="button" ${action.disabled ? "disabled aria-disabled=\"true\"" : ""} data-lx-route="${this.safe_attr(action.route || "")}">
						<span class="lx-action-icon">${this.icon(action.icon)}</span>
						<span>${this.safe_text(action.disabled ? (action.disabled_label || action.label) : action.label)}</span>
					</button>
				`).join("")}
			</div>
		`);
	}

	normalize_quick_action(action) {
		const normalized = { ...(action || {}) };
		const label = String(normalized.label || "").toLowerCase();
		const is_shift_action = normalized.icon === "shift" || label.includes("shift") || label === "coming next";

		if (is_shift_action) {
			return {
				...normalized,
				label: "Review Shift",
				route: "/app/ledgix_operations?module=pos-shifts",
				icon: "shift",
				disabled: false,
				disabled_label: ""
			};
		}

		return normalized;
	}


	default_quick_actions() {
		return [
			{ label: "New Sale", route: "/app/ledgix-pos", icon: "sale", disabled: false },
			{ label: "New Purchase", route: "/app/ledgix_operations?module=purchases", icon: "purchase", disabled: false },
			{ label: "Add Item", route: "/app/ledgix_operations?module=products", icon: "item", disabled: false },
			{ label: "Reports", route: "/app/ledgix-reports", icon: "report", disabled: false },
			{ label: "Inventory Alerts", route: "/app/ledgix-reports?report=inventory", icon: "stock", disabled: false },
			{ label: "Review Shift", route: "/app/ledgix_operations?module=pos-shifts", icon: "shift", disabled: false }
		];
	}

	// Theme bridge
	apply_theme_variables(data) {
		this.apply_theme_settings(this.get_value(data, "meta.theme", {}));
	}

	apply_theme_settings(theme) {
		const normalized = theme || {};
		const enabled = Boolean(this.to_number(normalized.enable_custom_accent));
		if (!enabled) {
			this.clear_theme_variables([this.$root?.get(0), document.documentElement]);
			return;
		}

		const accent = this.normalize_theme_hex(normalized.primary_accent_color);
		if (!accent) {
			this.clear_theme_variables([this.$root?.get(0), document.documentElement]);
			return;
		}

		const targets = [this.$root?.get(0), document.documentElement].filter(Boolean);
		const rgb = this.theme_rgb_string(accent);
		const vars = {
			"--lx-accent": accent,
			"--lx-accent-hover": normalized.accent_hover || accent,
			"--lx-accent-soft": normalized.accent_soft || `rgba(${rgb}, 0.10)`,
			"--lx-accent-soft-2": normalized.accent_soft_2 || `rgba(${rgb}, 0.16)`,
			"--lx-accent-border": normalized.accent_border || `rgba(${rgb}, 0.28)`,
			"--lx-accent-ring": normalized.accent_ring || `rgba(${rgb}, 0.18)`,
			"--lx-accent-rgb": rgb
		};
		targets.forEach((target) => Object.entries(vars).forEach(([key, value]) => target.style.setProperty(key, value)));
	}

	clear_theme_variables(targets) {
		const vars = ["--lx-accent", "--lx-accent-hover", "--lx-accent-soft", "--lx-accent-soft-2", "--lx-accent-border", "--lx-accent-ring", "--lx-accent-rgb"];
		(targets || []).filter(Boolean).forEach((target) => vars.forEach((key) => target.style.removeProperty(key)));
	}

	// Templates and helpers
	show_loading_state() {
		this.$root.find(".lx-dash-header").html(`<div class="lx-skeleton lx-skeleton-header"></div>`);
		this.$root.find(".lx-pulse-grid").html(Array.from({ length: 5 }).map(() => `<div class="lx-skeleton lx-skeleton-card"></div>`).join(""));

		this.$root.find(".lx-alerts-panel,.lx-trend-panel,.lx-payment-panel,.lx-fast-panel,.lx-shift-panel,.lx-inventory-panel,.lx-risk-panel").html(
			`<div class="lx-skeleton lx-skeleton-panel"></div>`
		);

		this.render_quick_actions({
			quick_actions: this.default_quick_actions()
		});
	}

	show_error_state() {
		const message = this.empty_state("Dashboard data could not be loaded. Please try again.");
		const retry = `<button class="btn btn-primary btn-sm" type="button" data-lx-refresh>Retry</button>`;
		this.$root.find(".lx-dash-header").html(`
			<div class="lx-header-copy">
				<div>
					<h1>Ledgix Dashboard</h1>
					<p>Business Command Center</p>
				</div>
			</div>
		`);
		this.$root.find(".lx-pulse-grid,.lx-alerts-panel,.lx-trend-panel,.lx-payment-panel,.lx-fast-panel,.lx-shift-panel,.lx-inventory-panel,.lx-risk-panel").html(message);
		this.$root.find(".lx-actions-panel").html(retry);
	}

	panel_head(title, subtitle) {
		return `
			<div class="lx-panel-head">
				<h2>${this.safe_text(title)}</h2>
				<p>${this.safe_text(subtitle)}</p>
			</div>
		`;
	}

	empty_state(message) {
		return `<div class="lx-empty-state">${this.safe_text(message)}</div>`;
	}

	metric_row(label, value, tone = "muted") {
		return `<div class="lx-metric-row is-${this.safe_attr(tone)}"><span>${this.safe_text(label)}</span><strong>${this.safe_text(value)}</strong></div>`;
	}

	line_chart(rows) {
		if (!rows.length) return this.empty_state("No sales trend data available.");

		const width = 760;
		const height = 270;
		const pad = { left: 74, right: 24, top: 20, bottom: 38 };
		const values = rows.flatMap((row) => [this.to_number(row.sales), this.to_number(row.profit)]);
		const max = Math.max(1, ...values);
		const min = Math.min(0, ...values);
		const range = max - min || 1;
		const plot_width = width - pad.left - pad.right;
		const plot_height = height - pad.top - pad.bottom;
		const x = (index) => pad.left + (index * plot_width / Math.max(1, rows.length - 1));
		const y = (value) => pad.top + ((max - value) * plot_height / range);
		const path = (key) => rows.map((row, index) => `${index ? "L" : "M"} ${x(index).toFixed(1)} ${y(this.to_number(row[key])).toFixed(1)}`).join(" ");
		const ticks = this.chart_ticks(min, max, 4);
		const step_width = plot_width / Math.max(1, rows.length - 1);

		return `
			<div class="lx-line-chart">
				<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="Sales and profit trend with y-axis labels and point tooltips">
					<text class="lx-chart-y-title" x="15" y="${(pad.top + plot_height / 2).toFixed(1)}" transform="rotate(-90 15 ${(pad.top + plot_height / 2).toFixed(1)})">Amount</text>
					${ticks.map((tick) => {
						const tick_y = y(tick);
						return `
							<line class="lx-chart-grid" x1="${pad.left}" y1="${tick_y.toFixed(1)}" x2="${width - pad.right}" y2="${tick_y.toFixed(1)}"></line>
							<text class="lx-chart-y-label" x="${pad.left - 10}" y="${(tick_y + 4).toFixed(1)}" text-anchor="end">${this.safe_text(this.compact_currency(tick))}</text>
						`;
					}).join("")}
					<line class="lx-chart-axis" x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}"></line>
					<line class="lx-chart-axis" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
					<path class="lx-chart-area is-sales" d="${path("sales")} L ${x(rows.length - 1).toFixed(1)} ${height - pad.bottom} L ${pad.left} ${height - pad.bottom} Z"></path>
					<path class="lx-chart-line is-sales" d="${path("sales")}"></path>
					<path class="lx-chart-line is-profit" d="${path("profit")}"></path>
					${rows.map((row, index) => {
						const point_x = x(index);
						const sales_y = y(this.to_number(row.sales));
						const profit_y = y(this.to_number(row.profit));
						const hit_width = Math.max(26, step_width);
						const tooltip_width = 178;
						const tooltip_height = 72;
						const tooltip_x = Math.max(pad.left + 4, Math.min(width - pad.right - tooltip_width, point_x - tooltip_width / 2));
						const tooltip_y = Math.max(8, Math.min(sales_y, profit_y) - tooltip_height - 11);
						return `
							<g class="lx-chart-hit">
								<rect class="lx-chart-hover-zone" tabindex="0" x="${(point_x - hit_width / 2).toFixed(1)}" y="${pad.top}" width="${hit_width.toFixed(1)}" height="${plot_height}"></rect>
								<line class="lx-chart-crosshair" x1="${point_x.toFixed(1)}" y1="${pad.top}" x2="${point_x.toFixed(1)}" y2="${height - pad.bottom}"></line>
								<circle class="lx-chart-point is-sales" cx="${point_x.toFixed(1)}" cy="${sales_y.toFixed(1)}" r="3.5"></circle>
								<circle class="lx-chart-point is-profit" cx="${point_x.toFixed(1)}" cy="${profit_y.toFixed(1)}" r="3.5"></circle>
								<g class="lx-chart-popup" transform="translate(${tooltip_x.toFixed(1)} ${tooltip_y.toFixed(1)})">
									<rect width="${tooltip_width}" height="${tooltip_height}" rx="11"></rect>
									<text class="lx-chart-popup-date" x="11" y="18">${this.safe_text(this.short_date(row.date))}</text>
									<circle class="lx-chart-popup-dot is-sales" cx="13" cy="36" r="3.2"></circle>
									<text class="lx-chart-popup-label" x="22" y="40">Sales</text>
									<text class="lx-chart-popup-value" x="${tooltip_width - 11}" y="40" text-anchor="end">${this.safe_text(this.format_currency(row.sales))}</text>
									<circle class="lx-chart-popup-dot is-profit" cx="13" cy="56" r="3.2"></circle>
									<text class="lx-chart-popup-label" x="22" y="60">Profit</text>
									<text class="lx-chart-popup-value" x="${tooltip_width - 11}" y="60" text-anchor="end">${this.safe_text(this.format_currency(row.profit))}</text>
								</g>
							</g>
						`;
					}).join("")}
				</svg>
				<div class="lx-chart-labels">
					${rows.map((row, index) => {
						const step = Math.max(1, Math.ceil(rows.length / 6));
						const show = index === 0 || index === rows.length - 1 || index % step === 0;
						return show ? `<span>${this.safe_text(this.short_date(row.date))}</span>` : "";
					}).join("")}
				</div>
				<div class="lx-chart-legend"><span class="is-sales">Sales</span><span class="is-profit">Profit</span></div>
			</div>
		`;
	}

	chart_ticks(min, max, count = 4) {
		const low = this.to_number(min);
		const high = this.to_number(max);
		const range = high - low || 1;
		return Array.from({ length: count + 1 }, (_, index) => high - (range * index / count));
	}

	compact_currency(value) {
		const amount = this.to_number(value);
		const currency = frappe.boot?.sysdefaults?.currency || "PKR";
		const abs = Math.abs(amount);
		const sign = amount < 0 ? "-" : "";
		if (abs >= 10000000) return `${currency} ${sign}${(abs / 10000000).toLocaleString(undefined, { maximumFractionDigits: 1 })}Cr`;
		if (abs >= 100000) return `${currency} ${sign}${(abs / 100000).toLocaleString(undefined, { maximumFractionDigits: 1 })}L`;
		if (abs >= 1000) return `${currency} ${sign}${(abs / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })}K`;
		return `${currency} ${sign}${abs.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
	}

	donut_style(rows, total) {
		let start = 0;
		const segments = rows.map((row, index) => {
			const size = this.to_number(row.value) / total * 100;
			const end = start + size;
			const segment = `${this.payment_color(row.label, index)} ${start.toFixed(2)}% ${end.toFixed(2)}%`;
			start = end;
			return segment;
		});
		return `background: conic-gradient(${segments.join(", ")});`;
	}

	payment_tooltip_html(rows, total) {
		if (!rows.length || !total) return "";

		return `
			<div class="lx-payment-tooltip" role="tooltip">
				${rows.map((row, index) => {
					const percent = row.value / total * 100;
					return `
						<div class="lx-payment-tooltip-row">
							<span class="lx-payment-tooltip-main">
								<i style="background:${this.payment_color(row.label, index)}"></i>
								${this.safe_text(row.label)}
							</span>
							<strong>
								${this.format_currency(row.value)}
								<small>${this.format_percent(percent)}</small>
							</strong>
						</div>
					`;
				}).join("")}
			</div>
		`;
	}

	payment_tooltip_text(rows, total) {
		if (!rows.length || !total) return "No payment collections";
		const parts = rows.map((row) => {
			const percent = this.to_number(row.value) / total * 100;
			return `${row.label}: ${this.format_currency(row.value)} (${this.format_percent(percent)})`;
		});
		return `Total collection ${this.format_currency(total)}. ${parts.join(". ")}`;
	}


	normalize_payment_label(label) {
		const value = String(label || "").trim();
		if (/jazz\s*cash|jazzcash/i.test(value)) return "JazzCash";
		if (/easy\s*paisa|easypaisa/i.test(value)) return "EasyPaisa";
		if (/card|visa|master|debit|credit/i.test(value)) return "Card";
		if (/digital|online|bank|transfer|wallet/i.test(value)) return "Digital";
		if (/cash/i.test(value)) return "Cash";
		return value || "Unknown";
	}

	payment_color(label, index = 0) {
		const value = String(label || "").toLowerCase();

		if (value.includes("jazz")) return "#dc2626"; // JazzCash red
		if (value.includes("easy")) return "#16a34a"; // EasyPaisa green
		if (value.includes("card") || value.includes("visa") || value.includes("master") || value.includes("debit") || value.includes("credit")) return "#2563eb"; // Card blue
		if (value.includes("cash")) return "#d97706"; // Cash amber/gold
		if (value.includes("digital") || value.includes("online") || value.includes("bank") || value.includes("transfer") || value.includes("wallet")) return "#7c3aed"; // Other digital purple

		return ["#64748b", "#0891b2", "#9333ea"][index % 3];
	}

	activity_route(type) {
		const value = String(type || "").toLowerCase();

		if (value.includes("sale return") || value.includes("return")) {
			return "/app/ledgix_operations?module=returns";
		}

		if (value.includes("sale")) {
			return "/app/ledgix_operations?module=sales";
		}

		if (value.includes("purchase")) {
			return "/app/ledgix_operations?module=purchases";
		}

		if (value.includes("stock") || value.includes("inventory")) {
			return "/app/ledgix_operations?module=stock-movements";
		}

		if (value.includes("shift")) {
			return "/app/ledgix_operations?module=pos-shifts";
		}

		return "/app/business-intelligence-center";
	}


	safe_route(route) {
		if (!route || typeof route !== "string" || !route.startsWith("/app/")) return;
		window.location.href = route;
	}

	get_value(obj, path, fallback = "") {
		return String(path).split(".").reduce((current, key) => current && current[key] !== undefined ? current[key] : undefined, obj) ?? fallback;
	}

	format_currency(value) {
		const amount = this.to_number(value);
		return `${frappe.boot?.sysdefaults?.currency || "PKR"} ${amount.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
	}

	format_number(value) {
		return this.to_number(value).toLocaleString(undefined, { maximumFractionDigits: 1 });
	}

	format_percent(value) {
		return `${this.to_number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
	}

	format_alert_count(value) {
		if (typeof value === "number" && Math.abs(value) > 99) return this.format_number(value);
		return this.safe_text(value === null || value === undefined ? 0 : value);
	}

	delta_text(value) {
		const number = this.to_number(value);
		const prefix = number > 0 ? "+" : "";
		return `${prefix}${this.format_percent(number)} vs yesterday`;
	}

	format_date(value) {
		if (!value) return "Today";
		return window.moment ? window.moment(value).format("MMM D, YYYY") : value;
	}

	format_time(value) {
		if (!value) return "now";
		return window.moment ? window.moment(value).format("h:mm A") : value;
	}

	short_date(value) {
		return value && window.moment ? window.moment(value).format("MMM D") : value;
	}

	title_case(value) {
		return String(value || "").replace(/\b\w/g, (match) => match.toUpperCase());
	}

	to_number(value) {
		const number = Number(value);
		return Number.isFinite(number) ? number : 0;
	}

	normalize_theme_hex(value) {
		const raw = String(value || "").trim();
		if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw;
		return null;
	}

	theme_rgb_string(hex) {
		const color = this.normalize_theme_hex(hex);
		if (!color) return "17, 24, 39";
		return [parseInt(color.slice(1, 3), 16), parseInt(color.slice(3, 5), 16), parseInt(color.slice(5, 7), 16)].join(", ");
	}

	safe_text(value, fallback = "-") {
		const text = value === null || value === undefined || value === "" ? fallback : String(value);
		return text.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[char]));
	}

	safe_attr(value) {
		return this.safe_text(value, "");
	}

	icon(type) {
		const icons = {
			refresh: `<path d="M21 12a9 9 0 0 1-15.5 6.2"></path><path d="M3 12a9 9 0 0 1 15.5-6.2"></path><path d="M18 2v5h-5"></path><path d="M6 22v-5h5"></path>`,
			calendar: `<rect x="3" y="4" width="18" height="18" rx="3"></rect><path d="M8 2v4"></path><path d="M16 2v4"></path><path d="M3 10h18"></path>`,
			clock: `<circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path>`,
			sales: `<path d="M4 19V5"></path><path d="M4 19h16"></path><path d="M8 16v-5"></path><path d="M12 16V8"></path><path d="M16 16v-3"></path>`,
			profit: `<path d="M4 17l5-5 4 3 7-8"></path><path d="M15 7h5v5"></path>`,
			margin: `<path d="M19 5 5 19"></path><circle cx="7" cy="7" r="2"></circle><circle cx="17" cy="17" r="2"></circle>`,
			invoice: `<path d="M6 3h12v18l-3-2-3 2-3-2-3 2V3Z"></path><path d="M9 8h6"></path><path d="M9 12h6"></path>`,
			cash: `<rect x="3" y="6" width="18" height="12" rx="2"></rect><circle cx="12" cy="12" r="3"></circle>`,
			shift: `<path d="M4 12a8 8 0 1 0 8-8"></path><path d="M4 4v6h6"></path>`,
			purchase: `<path d="M6 3h12v18H6z"></path><path d="M9 8h6"></path><path d="M9 12h6"></path>`,
			item: `<path d="m21 8-9-5-9 5 9 5 9-5Z"></path><path d="M3 8v8l9 5 9-5V8"></path>`,
			report: `<path d="M4 19V5"></path><path d="M8 16v-4"></path><path d="M12 16V8"></path><path d="M16 16v-6"></path><path d="M4 19h16"></path>`,
			stock: `<path d="M5 7h14"></path><path d="M7 7v13h10V7"></path><path d="M9 4h6l2 3H7l2-3Z"></path>`,
			sale: `<path d="M5 12h14"></path><path d="M13 6l6 6-6 6"></path>`
		};
		return `<svg class="lx-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">${icons[type] || icons.sales}</svg>`;
	}
}
