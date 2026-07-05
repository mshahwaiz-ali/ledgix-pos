// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

frappe.query_reports["Item Intelligence Legacy"] = {
	filters: [
		{
			fieldname: "item",
			label: __("Item"),
			fieldtype: "Link",
			options: "Ledgix Item",
			reqd: 1
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1
		}
	],

	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (!data) return value;

		if (column.fieldname === "flow_step") {
			return `<span class="lx-cycle-step">${frappe.utils.escape_html(data.flow_step || "")}</span>`;
		}

		if (column.fieldname === "event_type") {
			return ledgix_item_cycle_event_badge(data.event_type);
		}

		if (column.fieldname === "stock_flow" && data.stock_flow) {
			return `<span class="lx-cycle-flow">${frappe.utils.escape_html(data.stock_flow || "")}</span>`;
		}

		if (column.fieldname === "impact_type") {
			return ledgix_item_cycle_impact_badge(data.impact_type);
		}

		if (column.fieldname === "lot_label" && data.lot_label) {
			return ledgix_item_cycle_lot_badge(data.lot_label);
		}

		if (column.fieldname === "qty_in" && flt(data.qty_in)) {
			return `<span class="lx-cycle-text-blue">${format_number(data.qty_in)}</span>`;
		}

		if (column.fieldname === "qty_out" && flt(data.qty_out)) {
			return `<span class="lx-cycle-text-green">${format_number(data.qty_out)}</span>`;
		}

		if (column.fieldname === "qty_returned" && flt(data.qty_returned)) {
			return `<span class="lx-cycle-text-red">${format_number(data.qty_returned)}</span>`;
		}

		if (column.fieldname === "profit" && flt(data.profit)) {
			const cls = flt(data.profit) < 0 ? "lx-cycle-text-red" : "lx-cycle-text-green";
			return `<span class="${cls}">${format_currency(data.profit)}</span>`;
		}

		if (column.fieldname === "open_action" && data.reference_name) {
			return `
				<div class="lx-cycle-action-wrap">
					<button class="lx-cycle-icon-btn" onclick="ledgix_item_cycle_open('${frappe.utils.escape_html(data.reference_doctype || "")}', '${frappe.utils.escape_html(data.reference_name || "")}')" title="Open Reference">
						<span class="lx-cycle-eye"></span>
					</button>
				</div>
			`;
		}

		return value;
	},

	onload: function(report) {
		ledgix_item_cycle_apply_style();

		report.page.add_inner_button(__("Print Report"), function() {
			ledgix_item_cycle_print(report);
		});

		report.page.add_inner_button(__("Download CSV"), function() {
			ledgix_item_cycle_download(report);
		});

		const refresh_clean_ui = () => ledgix_item_cycle_render_header(report);
		setTimeout(refresh_clean_ui, 250);
		setTimeout(refresh_clean_ui, 800);
	},

	after_datatable_render: function(report) {
		ledgix_item_cycle_render_header(report);
	}
};


// ============================================================
// REPORT UI STYLE
// ============================================================

function ledgix_item_cycle_apply_style() {
	if ($("#ledgix-item-cycle-clean-style").length) return;

	$("head").append(`
		<style id="ledgix-item-cycle-clean-style">
			.query-report .report-wrapper {
				border:1px solid #EAECF0;
				border-radius:14px;
				overflow:hidden;
				background:#FFFFFF;
			}

			.query-report .report-summary {
				display:none !important;
			}

			.lx-cycle-report-head {
				margin:10px 0 12px 0;
				border:1px solid #EAECF0;
				border-radius:14px;
				background:#FFFFFF;
				overflow:hidden;
				box-shadow:0 1px 2px rgba(16,24,40,0.04);
			}

			.lx-cycle-head-top {
				display:flex;
				justify-content:space-between;
				align-items:flex-start;
				gap:14px;
				padding:14px 16px;
				border-bottom:1px solid #F2F4F7;
			}

			.lx-cycle-title {
				font-size:17px;
				font-weight:800;
				color:#101828;
				line-height:1.25;
			}

			.lx-cycle-subtitle {
				margin-top:4px;
				font-size:12px;
				font-weight:600;
				color:#667085;
			}

			.lx-cycle-badge-row {
				display:flex;
				align-items:center;
				justify-content:flex-end;
				gap:7px;
				flex-wrap:wrap;
			}

			.lx-cycle-status-pill,
			.lx-cycle-mode-pill {
				display:inline-flex;
				align-items:center;
				padding:5px 9px;
				border-radius:999px;
				font-size:11px;
				font-weight:800;
				white-space:nowrap;
			}

			.lx-cycle-mode-pill {
				color:#344054;
				background:#F2F4F7;
				border:1px solid #EAECF0;
			}

			.lx-cycle-summary-grid {
				display:grid;
				grid-template-columns:repeat(6, minmax(120px, 1fr));
				gap:8px;
				padding:12px 16px 14px 16px;
			}

			.lx-cycle-card {
				border:1px solid #EAECF0;
				border-radius:12px;
				background:#FCFCFD;
				padding:10px 11px;
				min-height:66px;
			}

			.lx-cycle-card-label {
				font-size:10px;
				font-weight:800;
				color:#667085;
				text-transform:uppercase;
				letter-spacing:0.025em;
				margin-bottom:6px;
			}

			.lx-cycle-card-value {
				font-size:14px;
				font-weight:850;
				color:#101828;
				line-height:1.2;
			}

			.lx-cycle-warning-strip {
				margin:0 16px 14px 16px;
				border:1px solid #FEDF89;
				background:#FFFAEB;
				border-radius:11px;
				padding:9px 11px;
				font-size:12px;
				font-weight:700;
				color:#93370D;
			}

			.lx-cycle-step,
			.lx-cycle-flow,
			.lx-cycle-event,
			.lx-cycle-impact,
			.lx-cycle-lot {
				display:inline-flex;
				align-items:center;
				justify-content:center;
				border-radius:8px;
				padding:3px 7px;
				font-size:11px;
				font-weight:800;
				white-space:nowrap;
			}

			.lx-cycle-step,
			.lx-cycle-flow {
				color:#344054;
				background:#F9FAFB;
				border:1px solid #EAECF0;
			}

			.lx-cycle-lot {
				color:#5925DC;
				background:#F4F3FF;
				border:1px solid #D9D6FE;
			}

			.lx-cycle-text-blue { color:#175CD3; font-weight:800; }
			.lx-cycle-text-green { color:#027A48; font-weight:800; }
			.lx-cycle-text-red { color:#B42318; font-weight:800; }
			.lx-cycle-text-orange { color:#B54708; font-weight:800; }

			.lx-cycle-action-wrap {
				display:flex;
				align-items:center;
				justify-content:center;
			}

			.lx-cycle-icon-btn {
				width:24px;
				height:24px;
				min-width:24px;
				min-height:24px;
				padding:0;
				border-radius:8px;
				border:1px solid #D0D5DD;
				background:#FFFFFF;
				display:flex;
				align-items:center;
				justify-content:center;
				cursor:pointer;
				transition:0.15s ease;
			}

			.lx-cycle-icon-btn:hover {
				background:#F9FAFB;
				border-color:#98A2B3;
			}

			.lx-cycle-eye {
				width:13px;
				height:8px;
				border:1.6px solid #344054;
				border-radius:999px;
				position:relative;
				display:inline-block;
			}

			.lx-cycle-eye:after {
				content:"";
				width:4px;
				height:4px;
				background:#344054;
				border-radius:50%;
				position:absolute;
				top:50%;
				left:50%;
				transform:translate(-50%, -50%);
			}

			.dt-row-filter { display:none !important; }
			.dt-toast { display:none !important; }

			/* Keep the ERP report table comfortably visible.
			   Target: header + around 15 lifecycle rows before page footer. */
			.query-report .report-wrapper .datatable {
				min-height:590px !important;
			}

			.query-report .report-wrapper .dt-scrollable {
				min-height:552px !important;
			}

			.query-report .report-wrapper .dt-scrollable__body {
				min-height:516px !important;
			}

			.datatable .dt-row {
				min-height:34px;
			}

			.datatable .dt-cell__content {
				font-size:12px;
			}

			.datatable .dt-header .dt-cell__content {
				font-size:11px;
				font-weight:800;
				color:#475467;
				text-transform:uppercase;
				letter-spacing:0.02em;
			}

			.lx-print-doc {
				width:100%;
				color:#101828;
				font-family:Arial, sans-serif;
			}

			.lx-doc-top {
				display:flex;
				justify-content:space-between;
				align-items:flex-start;
				border-bottom:2px solid #101828;
				padding-bottom:13px;
				margin-bottom:14px;
			}

			.lx-brand {
				font-size:28px;
				font-weight:900;
				letter-spacing:2px;
				line-height:1;
			}

			.lx-doc-title {
				text-align:right;
				font-size:18px;
				font-weight:850;
			}

			.lx-doc-title span,
			.lx-doc-subtitle {
				display:block;
				font-size:11px;
				color:#667085;
				margin-top:5px;
				font-weight:600;
			}

			.lx-print-kpi-grid {
				display:grid;
				grid-template-columns:repeat(4, 1fr);
				gap:8px;
				margin:12px 0;
			}

			.lx-print-kpi {
				border:1px solid #D0D5DD;
				border-radius:10px;
				padding:9px;
				background:#F9FAFB;
			}

			.lx-print-kpi .label {
				font-size:10px;
				color:#667085;
				margin-bottom:5px;
			}

			.lx-print-kpi .value {
				font-size:13px;
				font-weight:850;
				color:#101828;
			}

			.lx-doc-table {
				width:100%;
				border-collapse:collapse;
				margin-top:10px;
				font-size:10.5px;
			}

			.lx-doc-table th {
				background:#F2F4F7;
				border:1px solid #D0D5DD;
				padding:7px;
				font-weight:850;
				color:#344054;
				text-align:left;
			}

			.lx-doc-table td {
				border:1px solid #EAECF0;
				padding:7px;
				color:#344054;
			}

			.lx-text-right { text-align:right; }

			@media (max-width: 1200px) {
				.lx-cycle-summary-grid { grid-template-columns:repeat(3, minmax(120px, 1fr)); }
			}

			@media (max-width: 700px) {
				.lx-cycle-head-top { flex-direction:column; }
				.lx-cycle-badge-row { justify-content:flex-start; }
				.lx-cycle-summary-grid { grid-template-columns:repeat(2, minmax(0, 1fr)); }
			}
		</style>
	`);
}


// ============================================================
// HEADER / SUMMARY
// ============================================================

function ledgix_item_cycle_render_header(report) {
	$(".lx-cycle-report-head").remove();
	$(".report-summary").hide();
	$(".dt-row-filter").remove();
	$(".dt-toast").hide();

	const rows = ledgix_item_cycle_rows(report);
	if (!rows.length) return;

	const s = ledgix_item_cycle_snapshot(rows);
	const warning = ledgix_item_cycle_warning_text(s, rows);
	const is_billing_only = s.mode === "Billing Only";

	const cards = is_billing_only ? [
		["Sold", format_number(s.total_sold), "lx-cycle-text-green"],
		["Returned", format_number(s.total_returned), "lx-cycle-text-red"],
		["Revenue", format_currency(s.total_revenue), ""],
		["Customers", format_number((s.context.customers || []).length), ""],
		["Events", format_number(rows.length), ""],
		["Mode", "Billing Only", ""]
	] : [
		["Current Stock", format_number(s.current_stock), s.current_stock <= 0 ? "lx-cycle-text-red" : ""],
		["Purchased", format_number(s.total_purchased), "lx-cycle-text-blue"],
		["Sold", format_number(s.total_sold), "lx-cycle-text-green"],
		["Returned", format_number(s.total_returned), "lx-cycle-text-red"],
		["Revenue", format_currency(s.total_revenue), ""],
		["Profit", format_currency(s.total_profit), s.total_profit < 0 ? "lx-cycle-text-red" : "lx-cycle-text-green"],
		["Margin", `${format_number(s.profit_margin, null, 2)}%`, s.profit_margin < 10 ? "lx-cycle-text-orange" : "lx-cycle-text-green"],
		["Avg Buy", format_currency(s.avg_buy_rate), ""],
		["Avg Sell", format_currency(s.avg_sell_rate), ""],
		["Open Lots", format_number(s.open_lots), ""],
		["Remaining Lot", format_number(s.remaining_lot_qty), ""],
		["Return Ratio", `${format_number(s.return_ratio, null, 2)}%`, s.return_ratio >= 20 ? "lx-cycle-text-red" : ""]
	];

	const html = `
		<div class="lx-cycle-report-head">
			<div class="lx-cycle-head-top">
				<div>
					<div class="lx-cycle-title">${frappe.utils.escape_html(s.item_name || s.item_code || "Item Intelligence")}</div>
					<div class="lx-cycle-subtitle">
						${frappe.utils.escape_html(s.item_code || "-")}
						${s.category ? ` • ${frappe.utils.escape_html(s.category)}` : ""}
						 • ${frappe.utils.escape_html(report.get_filter_value("from_date") || "-")} to ${frappe.utils.escape_html(report.get_filter_value("to_date") || "-")}
					</div>
				</div>
				<div class="lx-cycle-badge-row">
					<span class="lx-cycle-mode-pill">${frappe.utils.escape_html(s.mode || "Strict Inventory")}</span>
					${ledgix_item_cycle_health_badge(is_billing_only ? "Billing" : s.health_score)}
				</div>
			</div>
			<div class="lx-cycle-summary-grid">
				${cards.map(card => `
					<div class="lx-cycle-card">
						<div class="lx-cycle-card-label">${frappe.utils.escape_html(card[0])}</div>
						<div class="lx-cycle-card-value ${card[2] || ""}">${card[1]}</div>
					</div>
				`).join("")}
			</div>
			${warning ? `<div class="lx-cycle-warning-strip">${frappe.utils.escape_html(warning)}</div>` : ""}
		</div>
	`;

	$(".report-wrapper").before(html);
}

function ledgix_item_cycle_rows(report) {
	if (!report || !report.data) return [];
	return report.data.filter(row => row && row.event_type);
}

function ledgix_item_cycle_snapshot(rows) {
	if (!rows.length) return {};

	const row = rows[0];
	const context = ledgix_item_cycle_parse_json(row.intelligence_context);
	const sale_rows = rows.filter(r => r.event_type === "SALE");
	const return_rows = rows.filter(r => r.event_type === "RETURN");
	const purchase_rows = rows.filter(r => r.event_type === "PURCHASE");

	const fallback_sold = sale_rows.reduce((sum, r) => sum + flt(r.qty_out), 0);
	const fallback_returned = return_rows.reduce((sum, r) => sum + flt(r.qty_returned), 0);
	const fallback_purchased = purchase_rows.reduce((sum, r) => sum + flt(r.qty_in), 0);
	const fallback_revenue = sale_rows.reduce((sum, r) => sum + flt(r.amount), 0);
	const fallback_profit = rows.reduce((sum, r) => sum + flt(r.profit), 0);
	const fallback_margin = fallback_revenue ? (fallback_profit / fallback_revenue) * 100 : 0;

	return {
		mode: row.report_mode_snapshot || (context.mode || "Strict Inventory"),
		context: context,
		item_code: row.item_code_snapshot || row.item || "",
		item_name: row.item_name_snapshot || row.item_code_snapshot || row.item || "",
		category: row.category_snapshot || "",
		current_stock: flt(row.current_stock_snapshot),
		minimum_stock: flt(row.minimum_stock_snapshot),
		stock_status: row.stock_status_snapshot || "",
		total_purchased: flt(row.total_purchased_snapshot) || fallback_purchased,
		total_sold: flt(row.total_sold_snapshot) || fallback_sold,
		total_returned: flt(row.total_returned_snapshot) || fallback_returned,
		total_revenue: flt(row.total_revenue_snapshot) || fallback_revenue,
		total_profit: flt(row.total_profit_snapshot) || fallback_profit,
		profit_margin: flt(row.profit_margin_snapshot) || fallback_margin,
		avg_buy_rate: flt(row.avg_buy_rate_snapshot),
		avg_sell_rate: flt(row.avg_sell_rate_snapshot),
		return_ratio: flt(row.return_ratio_snapshot) || (fallback_sold ? (fallback_returned / fallback_sold) * 100 : 0),
		health_score: row.health_score_snapshot || row.stock_status_snapshot || "Healthy",
		remaining_lot_qty: flt(row.remaining_lot_qty_snapshot),
		open_lots: flt(row.open_lots_snapshot),
		adjustment_count: flt(row.adjustment_count_snapshot)
	};
}

function ledgix_item_cycle_parse_json(raw) {
	if (!raw) return {};
	if (typeof raw === "object") return raw;

	try {
		return JSON.parse(raw) || {};
	} catch (e) {
		return {};
	}
}


// ============================================================
// BADGES / ACTIONS
// ============================================================

function ledgix_item_cycle_event_badge(type) {
	const map = {
		"PURCHASE": ["#175CD3", "#EFF8FF", "#B2DDFF"],
		"SALE": ["#027A48", "#ECFDF3", "#ABEFC6"],
		"RETURN": ["#B42318", "#FEF3F2", "#FECDCA"],
		"ADJUSTMENT": ["#B54708", "#FFFAEB", "#FEDF89"]
	};

	const pair = map[type] || ["#344054", "#F2F4F7", "#EAECF0"];
	return `<span class="lx-cycle-event" style="color:${pair[0]}; background:${pair[1]}; border:1px solid ${pair[2]};">${frappe.utils.escape_html(type || "-")}</span>`;
}

function ledgix_item_cycle_impact_badge(type) {
	const map = {
		"INCREASE": ["#027A48", "#ECFDF3", "#ABEFC6"],
		"DECREASE": ["#B42318", "#FEF3F2", "#FECDCA"],
		"NEUTRAL": ["#B54708", "#FFFAEB", "#FEDF89"],
		"REVERSAL": ["#6941C6", "#F4F3FF", "#D9D6FE"]
	};

	const pair = map[type] || ["#344054", "#F2F4F7", "#EAECF0"];
	return `<span class="lx-cycle-impact" style="color:${pair[0]}; background:${pair[1]}; border:1px solid ${pair[2]};">${frappe.utils.escape_html(type || "-")}</span>`;
}

function ledgix_item_cycle_health_badge(status) {
	const map = {
		"Healthy": ["#027A48", "#ECFDF3", "#ABEFC6"],
		"Low Stock": ["#B54708", "#FFFAEB", "#FEDF89"],
		"Out of Stock": ["#B42318", "#FEF3F2", "#FECDCA"],
		"Negative Stock": ["#B42318", "#FEF3F2", "#FECDCA"],
		"Aging Inventory": ["#B54708", "#FFFAEB", "#FEDF89"],
		"High Return Item": ["#B42318", "#FEF3F2", "#FECDCA"],
		"Billing": ["#344054", "#F2F4F7", "#EAECF0"]
	};

	const pair = map[status] || ["#344054", "#F2F4F7", "#EAECF0"];
	return `<span class="lx-cycle-status-pill" style="color:${pair[0]}; background:${pair[1]}; border:1px solid ${pair[2]};">${frappe.utils.escape_html(status || "Healthy")}</span>`;
}

function ledgix_item_cycle_lot_badge(label) {
	return `<span class="lx-cycle-lot">${frappe.utils.escape_html(label || "-")}</span>`;
}

function ledgix_item_cycle_open(doctype, name) {
	if (!doctype || !name) return;
	frappe.set_route("Form", doctype, name);
}

function ledgix_item_cycle_warning_text(s, rows) {
	let warnings = [];
	const adjustment_count = rows.filter(row => row.event_type === "ADJUSTMENT").length || flt(s.adjustment_count);

	if (s.mode !== "Billing Only") {
		if (s.current_stock < 0) warnings.push("Negative stock detected.");
		else if (s.current_stock === 0) warnings.push("Item is currently out of stock.");
		if (s.minimum_stock && s.current_stock <= s.minimum_stock) warnings.push("Stock is at or below minimum threshold.");
		if (adjustment_count >= 3) warnings.push("Multiple stock adjustments found in this cycle.");
	}

	if (s.return_ratio >= 20) warnings.push("High return ratio detected.");
	if (s.total_revenue && s.profit_margin <= 0) warnings.push("Zero or negative margin detected.");

	return warnings.join(" ");
}


// ============================================================
// PRINT / EXPORT
// ============================================================

function ledgix_item_cycle_print(report) {
	const rows = ledgix_item_cycle_rows(report);

	if (!rows.length) {
		frappe.msgprint("No item cycle data to print.");
		return;
	}

	const html = ledgix_item_cycle_print_html_content(report, rows);
	ledgix_item_cycle_print_html(html, "Item Intelligence");
}

function ledgix_item_cycle_print_html_content(report, rows) {
	const s = ledgix_item_cycle_snapshot(rows);
	const from_date = report.get_filter_value("from_date") || "";
	const to_date = report.get_filter_value("to_date") || "";
	const is_billing_only = s.mode === "Billing Only";
	const warning = ledgix_item_cycle_warning_text(s, rows);

	const cards = is_billing_only ? [
		["Item", s.item_name || s.item_code || "-"],
		["Sold", format_number(s.total_sold)],
		["Returned", format_number(s.total_returned)],
		["Revenue", format_currency(s.total_revenue)]
	] : [
		["Item", s.item_name || s.item_code || "-"],
		["Current Stock", format_number(s.current_stock)],
		["Purchased", format_number(s.total_purchased)],
		["Sold", format_number(s.total_sold)],
		["Returned", format_number(s.total_returned)],
		["Revenue", format_currency(s.total_revenue)],
		["Profit", format_currency(s.total_profit)],
		["Margin", `${format_number(s.profit_margin, null, 2)}%`]
	];

	return `
		<div class="lx-print-doc">
			<div class="lx-doc-top">
				<div>
					<div class="lx-brand">LEDGIX</div>
					<span class="lx-doc-subtitle">Item lifecycle audit report</span>
				</div>
				<div class="lx-doc-title">
					<div>Item Intelligence</div>
					<span>${frappe.utils.escape_html(from_date || "-")} to ${frappe.utils.escape_html(to_date || "-")}</span>
				</div>
			</div>

			<div class="lx-print-kpi-grid">
				${cards.map(card => `
					<div class="lx-print-kpi">
						<div class="label">${frappe.utils.escape_html(card[0])}</div>
						<div class="value">${frappe.utils.escape_html(String(card[1] || "-"))}</div>
					</div>
				`).join("")}
			</div>

			${warning ? `<div class="lx-cycle-warning-strip">${frappe.utils.escape_html(warning)}</div>` : ""}
			${ledgix_item_cycle_print_table(rows, is_billing_only)}
		</div>
	`;
}

function ledgix_item_cycle_print_table(rows, is_billing_only) {
	const headers = is_billing_only
		? ["Step", "Date", "Event", "Reference", "Customer", "Qty Out", "Returned", "Amount"]
		: ["Step", "Date", "Event", "Reference", "Party", "Stock Flow", "Qty In", "Qty Out", "Returned", "Rate", "Amount", "Profit", "Impact"];

	const body = rows.map(row => {
		const values = is_billing_only
			? [row.flow_step, row.posting_date, row.event_type, row.reference_name, row.party, format_number(row.qty_out || 0), format_number(row.qty_returned || 0), format_currency(row.amount || 0)]
			: [row.flow_step, row.posting_date, row.event_type, row.reference_name, row.party, row.stock_flow, format_number(row.qty_in || 0), format_number(row.qty_out || 0), format_number(row.qty_returned || 0), format_currency(row.rate || 0), format_currency(row.amount || 0), format_currency(row.profit || 0), row.impact_type];

		return `<tr>${values.map(value => `<td>${frappe.utils.escape_html(String(value || "-"))}</td>`).join("")}</tr>`;
	}).join("");

	return `
		<table class="lx-doc-table">
			<thead><tr>${headers.map(header => `<th>${frappe.utils.escape_html(header)}</th>`).join("")}</tr></thead>
			<tbody>${body}</tbody>
		</table>
	`;
}

function ledgix_item_cycle_download(report) {
	const rows = ledgix_item_cycle_rows(report);

	if (!rows.length) {
		frappe.msgprint("No item cycle data to download.");
		return;
	}

	const is_billing_only = ledgix_item_cycle_snapshot(rows).mode === "Billing Only";
	const headers = is_billing_only
		? ["Step", "Date", "Event", "Reference", "Customer", "Qty Out", "Returned", "Amount"]
		: ["Step", "Date", "Event", "Reference", "Party", "Stock Flow", "Qty In", "Qty Out", "Returned", "Rate", "Amount", "Profit", "Impact", "Lot Snapshot"];

	const csv_rows = rows.map(row => is_billing_only
		? [row.flow_step, row.posting_date, row.event_type, row.reference_name, row.party, row.qty_out, row.qty_returned, row.amount]
		: [row.flow_step, row.posting_date, row.event_type, row.reference_name, row.party, row.stock_flow, row.qty_in, row.qty_out, row.qty_returned, row.rate, row.amount, row.profit, row.impact_type, row.lot_label]
	);

	const csv = [headers, ...csv_rows]
		.map(row => row.map(value => `"${String(value || "").replace(/"/g, '""')}"`).join(","))
		.join("\n");

	const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");

	link.href = url;
	link.download = "ledgix-item-full-cycle.csv";
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);
	URL.revokeObjectURL(url);
}

function ledgix_item_cycle_print_html(html, title) {
	const print_window = window.open("", "_blank");

	if (!print_window) {
		frappe.msgprint("Please allow popups to print.");
		return;
	}

	const styles = $("#ledgix-item-cycle-clean-style").html() || "";

	print_window.document.write(`
		<!doctype html>
		<html>
		<head>
			<title>${frappe.utils.escape_html(title || "Report")}</title>
			<style>
				@page { size: A4 landscape; margin: 10mm; }
				body { font-family: Arial, sans-serif; color:#101828; background:#FFFFFF; font-size:11px; }
				tr { page-break-inside: avoid; }
				${styles}
			</style>
		</head>
		<body>
			${html}
			<script>window.onload = function() { window.print(); };</script>
		</body>
		</html>
	`);

	print_window.document.close();
}
