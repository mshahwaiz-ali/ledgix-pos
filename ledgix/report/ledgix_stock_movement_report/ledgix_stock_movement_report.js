// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

frappe.query_reports["Ledgix Stock Movement Report"] = {
	filters: [
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
		},
		{
			fieldname: "item",
			label: __("Item"),
			fieldtype: "Link",
			options: "Ledgix Item",
			placeholder: __("Select Item")
		},
		{
			fieldname: "movement_type",
			label: __("Movement Type"),
			fieldtype: "Select",
			options: "\nIN\nOUT\nADJUSTMENT"
		},
		{
			fieldname: "reference_doctype",
			label: __("Reference Type"),
			fieldtype: "Data",
			placeholder: __("Reference Doctype")
		},
		{
			fieldname: "reference_name",
			label: __("Reference ID"),
			fieldtype: "Data",
			placeholder: __("Reference Name")
		},
		{
			fieldname: "docstatus",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nSubmitted\nDraft\nCancelled",
			default: "Submitted"
		}
	],

	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "status" && data) {
			return ledgix_stock_status_badge(data.status);
		}

		if (column.fieldname === "movement_type" && data) {
			return ledgix_stock_movement_badge(data.movement_type);
		}

		if (column.fieldname === "view_action" && data) {
			return `
				<div class="lx-icon-action">
					<button class="lx-icon-btn" onclick="ledgix_stock_preview('${frappe.utils.escape_html(data.movement)}')" title="View Movement">
						<span class="lx-eye-icon"></span>
					</button>
				</div>
			`;
		}

		if (column.fieldname === "print_action" && data) {
			return `
				<div class="lx-icon-action">
					<button class="lx-icon-btn" onclick="ledgix_stock_print_single('${frappe.utils.escape_html(data.movement)}')" title="Print Movement">
						<span class="lx-print-icon"></span>
					</button>
				</div>
			`;
		}

		return value;
	},

	get_datatable_options(options) {
		return Object.assign(options, {
			checkboxColumn: true
		});
	},

	onload: function(report) {
		ledgix_stock_apply_style();

		report.page.add_inner_button(__("View Selected"), function() {
			ledgix_stock_view_selected(report);
		});

		report.page.add_inner_button(__("Download Selected"), function() {
			ledgix_stock_download_selected(report);
		});

		report.page.add_inner_button(__("Print Selected"), function() {
			ledgix_stock_print_selected(report);
		});

		const analytics_btn = report.page.add_inner_button(__("Show Analytics"), function() {
			const summary = $(".report-summary");

			if (summary.is(":visible")) {
				summary.hide();
				$(analytics_btn).text("Show Analytics");
			} else {
				summary.show();
				$(analytics_btn).text("Hide Analytics");
			}
		});

		const clean_report_ui = () => {
			$(".dt-row-filter").remove();
			$(".dt-toast").hide();
			$(".report-summary").hide();

			$(".dt-scrollable .dt-row").each(function () {
				const text = $(this).text().trim();
				const has_filter_inputs = $(this).find(".dt-filter, input, .awesomplete").length > 0;

				if (has_filter_inputs && !text) {
					$(this).remove();
				}
			});

			$(".query-report .report-wrapper").css({
				"border-radius": "14px",
				"overflow": "hidden"
			});

			ledgix_stock_render_selected_summary(report);
		};

		setTimeout(clean_report_ui, 300);
		setTimeout(clean_report_ui, 900);
		setTimeout(clean_report_ui, 1600);

		$(document).off("change.ledgix_stock_report");
		$(document).on("change.ledgix_stock_report", ".dt-cell__content input[type='checkbox'], .dt-checkbox", function() {
			setTimeout(() => ledgix_stock_render_selected_summary(report), 150);
		});
	}
};


function ledgix_stock_escape(value) {
	return frappe.utils.escape_html(String(value || ""));
}


function ledgix_stock_format_date(value) {
	if (!value) return "-";

	try {
		return frappe.datetime.str_to_user(value);
	} catch (e) {
		return value;
	}
}


function ledgix_stock_status_badge(status) {
	let color = "#344054";
	let bg = "#F2F4F7";

	if (status === "Submitted") {
		color = "#027A48";
		bg = "#ECFDF3";
	}

	if (status === "Draft") {
		color = "#B54708";
		bg = "#FFFAEB";
	}

	if (status === "Cancelled") {
		color = "#B42318";
		bg = "#FEF3F2";
	}

	return `<span class="lx-status-pill" style="color:${color}; background:${bg};">${ledgix_stock_escape(status)}</span>`;
}


function ledgix_stock_movement_badge(type) {
	let color = "#344054";
	let bg = "#F2F4F7";

	if (type === "IN") {
		color = "#027A48";
		bg = "#ECFDF3";
	}

	if (type === "OUT") {
		color = "#B42318";
		bg = "#FEF3F2";
	}

	if (type === "ADJUSTMENT") {
		color = "#6941C6";
		bg = "#F4F3FF";
	}

	return `<span class="lx-status-pill" style="color:${color}; background:${bg};">${ledgix_stock_escape(type)}</span>`;
}


function ledgix_stock_apply_style() {
	if ($("#ledgix-stock-report-style").length) return;

	$("head").append(`
		<style id="ledgix-stock-report-style">
			.lx-status-pill {
				display:inline-flex;
				align-items:center;
				padding:3px 9px;
				border-radius:999px;
				font-size:12px;
				font-weight:650;
				white-space:nowrap;
			}

			.lx-icon-action {
				display:flex;
				align-items:center;
				justify-content:center;
				padding:1px 0;
			}

			.lx-icon-btn {
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
				line-height:1;
				transition:0.15s ease;
				box-shadow:none;
			}

			.lx-icon-btn:hover {
				background:#F9FAFB;
				border-color:#98A2B3;
			}

			.lx-eye-icon {
				width:13px;
				height:8px;
				border:1.6px solid #344054;
				border-radius:999px;
				position:relative;
				display:inline-block;
			}

			.lx-eye-icon:after {
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

			.lx-print-icon {
				width:13px;
				height:11px;
				border:1.6px solid #344054;
				border-radius:2px;
				position:relative;
				display:inline-block;
			}

			.lx-print-icon:before {
				content:"";
				position:absolute;
				left:2px;
				right:2px;
				top:-5px;
				height:5px;
				border:1.6px solid #344054;
				border-bottom:0;
				background:#FFFFFF;
			}

			.lx-print-icon:after {
				content:"";
				position:absolute;
				left:3px;
				right:3px;
				bottom:-4px;
				height:5px;
				border:1.6px solid #344054;
				background:#FFFFFF;
			}

			.lx-selected-summary {
				margin:10px 0 12px 0;
				padding:12px;
				border:1px solid #EAECF0;
				border-radius:14px;
				background:#FFFFFF;
				box-shadow:0 1px 2px rgba(16, 24, 40, 0.04);
			}

			.lx-selected-summary-title {
				font-size:12px;
				font-weight:700;
				color:#475467;
				margin-bottom:8px;
				text-transform:uppercase;
				letter-spacing:0.03em;
			}

			.lx-selected-summary-grid {
				display:grid;
				grid-template-columns:repeat(5, minmax(110px, 1fr));
				gap:8px;
			}

			.lx-selected-card {
				border:1px solid #EAECF0;
				border-radius:12px;
				padding:10px;
				background:#F9FAFB;
			}

			.lx-selected-card .label {
				font-size:11px;
				color:#667085;
				margin-bottom:4px;
			}

			.lx-selected-card .value {
				font-size:14px;
				font-weight:750;
				color:#101828;
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
				padding-bottom:14px;
				margin-bottom:18px;
			}

			.lx-brand {
				font-size:30px;
				font-weight:900;
				letter-spacing:2px;
				line-height:1;
			}

			.lx-subtitle {
				font-size:12px;
				color:#667085;
				margin-top:6px;
			}

			.lx-doc-title {
				text-align:right;
				font-size:18px;
				font-weight:800;
			}

			.lx-doc-title span {
				display:block;
				font-size:12px;
				color:#667085;
				margin-top:5px;
				font-weight:600;
			}

			.lx-info-grid {
				display:grid;
				grid-template-columns:1fr 1fr;
				gap:12px;
				margin-bottom:18px;
			}

			.lx-info-box {
				border:1px solid #D0D5DD;
				border-radius:10px;
				padding:12px;
				background:#FFFFFF;
			}

			.lx-box-title {
				font-size:11px;
				font-weight:800;
				color:#475467;
				text-transform:uppercase;
				margin-bottom:10px;
			}

			.lx-info-row {
				display:flex;
				justify-content:space-between;
				gap:12px;
				padding:4px 0;
				font-size:12px;
			}

			.lx-info-row span {
				color:#667085;
			}

			.lx-info-row strong {
				color:#101828;
				text-align:right;
				word-break:break-word;
			}

			.lx-doc-table {
				width:100%;
				border-collapse:collapse;
				margin-top:8px;
				font-size:12px;
			}

			.lx-doc-table th {
				background:#F2F4F7;
				border:1px solid #D0D5DD;
				padding:9px;
				font-weight:800;
				color:#344054;
			}

			.lx-doc-table td {
				border:1px solid #EAECF0;
				padding:9px;
				color:#344054;
				vertical-align:top;
			}

			.lx-text-right {
				text-align:right;
			}

			.lx-empty-row {
				text-align:center;
				color:#667085;
				padding:20px;
			}

			.lx-total-wrap {
				display:flex;
				justify-content:flex-end;
				margin-top:16px;
			}

			.lx-total-box {
				width:300px;
				border:1px solid #D0D5DD;
				border-radius:10px;
				padding:12px;
				background:#F9FAFB;
			}

			.lx-total-box div {
				display:flex;
				justify-content:space-between;
				gap:12px;
				padding:5px 0;
				font-size:12px;
			}

			.lx-total-box div:last-child {
				border-top:1px solid #D0D5DD;
				margin-top:6px;
				padding-top:10px;
			}

			.lx-note-box {
				border:1px solid #EAECF0;
				border-radius:10px;
				padding:12px;
				background:#FCFCFD;
				margin-top:12px;
				font-size:12px;
				color:#344054;
				line-height:1.55;
			}

			.lx-note-box strong {
				display:block;
				font-size:11px;
				color:#475467;
				text-transform:uppercase;
				margin-bottom:6px;
			}

			.lx-signatures {
				display:grid;
				grid-template-columns:1fr 1fr 1fr;
				gap:38px;
				margin-top:70px;
			}

			.lx-signatures div {
				border-top:1px solid #98A2B3;
				padding-top:8px;
				color:#667085;
				font-size:11px;
			}

			.lx-signatures div:nth-child(2) {
				text-align:center;
			}

			.lx-signatures div:nth-child(3) {
				text-align:right;
			}

			.lx-footer-note {
				margin-top:34px;
				border-top:1px solid #EAECF0;
				padding-top:10px;
				font-size:10px;
				color:#98A2B3;
				text-align:center;
			}
		</style>
	`);
}


function ledgix_stock_get_selected_rows(report) {
	if (!report || !report.datatable || !report.data) return [];

	let selected_indexes = [];

	try {
		selected_indexes = report.datatable.rowmanager.getCheckedRows() || [];
	} catch (e) {
		selected_indexes = [];
	}

	return selected_indexes
		.map(index => report.data[index])
		.filter(row => row && row.movement);
}


function ledgix_stock_totals(rows) {
	const total_movements = rows.length;

	const total_in = rows
		.filter(row => row.movement_type === "IN")
		.reduce((sum, row) => sum + flt(row.quantity), 0);

	const total_out = rows
		.filter(row => row.movement_type === "OUT")
		.reduce((sum, row) => sum + flt(row.quantity), 0);

	const total_adjustments = rows
		.filter(row => row.movement_type === "ADJUSTMENT")
		.reduce((sum, row) => sum + flt(row.quantity), 0);

	const net_qty = total_in - total_out;

	return {
		total_movements,
		total_in,
		total_out,
		total_adjustments,
		net_qty
	};
}


function ledgix_stock_render_selected_summary(report) {
	const rows = ledgix_stock_get_selected_rows(report);
	$(".lx-selected-summary").remove();

	if (!rows.length) return;

	const totals = ledgix_stock_totals(rows);

	const html = `
		<div class="lx-selected-summary">
			<div class="lx-selected-summary-title">Selected Stock Movements Summary</div>

			<div class="lx-selected-summary-grid">
				<div class="lx-selected-card">
					<div class="label">Movements</div>
					<div class="value">${totals.total_movements}</div>
				</div>

				<div class="lx-selected-card">
					<div class="label">Total IN</div>
					<div class="value">${format_number(totals.total_in)}</div>
				</div>

				<div class="lx-selected-card">
					<div class="label">Total OUT</div>
					<div class="value">${format_number(totals.total_out)}</div>
				</div>

				<div class="lx-selected-card">
					<div class="label">Adjustments</div>
					<div class="value">${format_number(totals.total_adjustments)}</div>
				</div>

				<div class="lx-selected-card">
					<div class="label">Net Qty</div>
					<div class="value">${format_number(totals.net_qty)}</div>
				</div>
			</div>
		</div>
	`;

	$(".report-wrapper").before(html);
}


function ledgix_stock_preview(movement_name) {
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Ledgix Stock Movement",
			name: movement_name
		},
		callback: function(r) {
			if (!r.message) {
				frappe.msgprint("Stock Movement not found.");
				return;
			}

			const doc = r.message;
			const html = ledgix_stock_preview_html(doc);

			const dialog = new frappe.ui.Dialog({
				title: `Stock Movement Preview - ${doc.name}`,
				size: "extra-large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "preview_html",
						options: html
					}
				],
				primary_action_label: "Print",
				primary_action: function() {
					ledgix_stock_print_html(html, `Stock Movement ${doc.name}`);
				},
				secondary_action_label: "Open",
				secondary_action: function() {
					frappe.set_route("Form", "Ledgix Stock Movement", doc.name);
				}
			});

			dialog.show();
		}
	});
}


function ledgix_stock_preview_html(doc) {
	const movement_type = doc.movement_type || "-";
	const status = doc.docstatus === 0 ? "Draft" : doc.docstatus === 1 ? "Submitted" : doc.docstatus === 2 ? "Cancelled" : "-";
	const reference = doc.reference_doctype && doc.reference_name
		? `${doc.reference_doctype} / ${doc.reference_name}`
		: "-";

	return `
		<div class="lx-print-doc">
			<div class="lx-doc-top">
				<div>
					<div class="lx-brand">LEDGIX</div>
					<div class="lx-subtitle">Stock Movement Voucher</div>
				</div>
				<div class="lx-doc-title">
					<div>Stock Movement Report</div>
					<span>${ledgix_stock_escape(doc.name || "-")}</span>
				</div>
			</div>

			<div class="lx-info-grid">
				<div class="lx-info-box">
					<div class="lx-box-title">Movement Details</div>
					<div class="lx-info-row"><span>Movement ID</span><strong>${ledgix_stock_escape(doc.name || "-")}</strong></div>
					<div class="lx-info-row"><span>Date</span><strong>${ledgix_stock_escape(ledgix_stock_format_date(doc.movement_date))}</strong></div>
					<div class="lx-info-row"><span>Status</span><strong>${ledgix_stock_escape(status)}</strong></div>
				</div>

				<div class="lx-info-box">
					<div class="lx-box-title">Stock Details</div>
					<div class="lx-info-row"><span>Item</span><strong>${ledgix_stock_escape(doc.item || "-")}</strong></div>
					<div class="lx-info-row"><span>Movement Type</span><strong>${ledgix_stock_escape(movement_type)}</strong></div>
					<div class="lx-info-row"><span>Quantity</span><strong>${format_number(flt(doc.quantity))}</strong></div>
				</div>
			</div>

			<div class="lx-info-grid">
				<div class="lx-info-box">
					<div class="lx-box-title">Reference Details</div>
					<div class="lx-info-row"><span>Reference Type</span><strong>${ledgix_stock_escape(doc.reference_doctype || "-")}</strong></div>
					<div class="lx-info-row"><span>Reference ID</span><strong>${ledgix_stock_escape(doc.reference_name || "-")}</strong></div>
					<div class="lx-info-row"><span>Combined Ref</span><strong>${ledgix_stock_escape(reference)}</strong></div>
				</div>

				<div class="lx-info-box">
					<div class="lx-box-title">Audit Details</div>
					<div class="lx-info-row"><span>Created By</span><strong>${ledgix_stock_escape(doc.owner || "-")}</strong></div>
					<div class="lx-info-row"><span>Series</span><strong>${ledgix_stock_escape(doc.series || "-")}</strong></div>
				</div>
			</div>

			<div class="lx-note-box">
				<strong>Reference Note</strong>
				${ledgix_stock_escape(doc.reference_note || "No reference note provided.")}
			</div>

			<table class="lx-doc-table">
				<thead>
					<tr>
						<th>Item</th>
						<th>Movement Type</th>
						<th class="lx-text-right">Qty</th>
						<th>Reference Type</th>
						<th>Reference ID</th>
					</tr>
				</thead>
				<tbody>
					<tr>
						<td>${ledgix_stock_escape(doc.item || "-")}</td>
						<td>${ledgix_stock_escape(movement_type)}</td>
						<td class="lx-text-right">${format_number(flt(doc.quantity))}</td>
						<td>${ledgix_stock_escape(doc.reference_doctype || "-")}</td>
						<td>${ledgix_stock_escape(doc.reference_name || "-")}</td>
					</tr>
				</tbody>
			</table>

			<div class="lx-total-wrap">
				<div class="lx-total-box">
					<div><span>Movement Type</span><strong>${ledgix_stock_escape(movement_type)}</strong></div>
					<div><span>Quantity</span><strong>${format_number(flt(doc.quantity))}</strong></div>
					<div><span>Status</span><strong>${ledgix_stock_escape(status)}</strong></div>
				</div>
			</div>

			<div class="lx-signatures">
				<div><span>Prepared By</span></div>
				<div><span>Checked By</span></div>
				<div><span>Approved By</span></div>
			</div>

			<div class="lx-footer-note">
				System generated stock movement report. This voucher reflects inventory movement only.
			</div>
		</div>
	`;
}


function ledgix_stock_print_single(movement_name) {
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Ledgix Stock Movement",
			name: movement_name
		},
		callback: function(r) {
			if (!r.message) {
				frappe.msgprint("Stock Movement not found.");
				return;
			}

			const html = ledgix_stock_preview_html(r.message);
			ledgix_stock_print_html(html, `Stock Movement ${movement_name}`);
		}
	});
}


function ledgix_stock_selected_html(rows, mode) {
	const totals = ledgix_stock_totals(rows);

	const table_rows = rows.map((row, index) => `
		<tr>
			<td>${index + 1}</td>
			<td>${ledgix_stock_escape(row.movement || "")}</td>
			<td>${ledgix_stock_escape(ledgix_stock_format_date(row.movement_date))}</td>
			<td>${ledgix_stock_escape(row.item || "")}</td>
			<td>${ledgix_stock_escape(row.movement_type || "")}</td>
			<td class="lx-text-right">${format_number(row.quantity || 0)}</td>
			<td>${ledgix_stock_escape(row.reference_doctype || "-")}</td>
			<td>${ledgix_stock_escape(row.reference_name || "-")}</td>
			<td>${ledgix_stock_escape(row.status || "")}</td>
		</tr>
	`).join("");

	return `
		<div class="lx-print-doc">
			<div class="lx-doc-top">
				<div>
					<div class="lx-brand">LEDGIX</div>
					<div class="lx-subtitle">${mode === "preview" ? "Selected Stock Movements Preview" : "Selected Stock Movements Summary"}</div>
				</div>
				<div class="lx-doc-title">
					<div>${mode === "preview" ? "Stock Movement Combined View" : "Stock Movement Summary"}</div>
					<span>${rows.length} movement(s)</span>
				</div>
			</div>

			<table class="lx-doc-table">
				<thead>
					<tr>
						<th style="width:38px;">#</th>
						<th>Movement</th>
						<th>Date</th>
						<th>Item</th>
						<th>Type</th>
						<th class="lx-text-right">Qty</th>
						<th>Reference Type</th>
						<th>Reference ID</th>
						<th>Status</th>
					</tr>
				</thead>
				<tbody>
					${table_rows || `<tr><td colspan="9" class="lx-empty-row">No movements selected.</td></tr>`}
				</tbody>
			</table>

			<div class="lx-total-wrap">
				<div class="lx-total-box">
					<div><span>Movements</span><strong>${totals.total_movements}</strong></div>
					<div><span>Total IN</span><strong>${format_number(totals.total_in)}</strong></div>
					<div><span>Total OUT</span><strong>${format_number(totals.total_out)}</strong></div>
					<div><span>Adjustments</span><strong>${format_number(totals.total_adjustments)}</strong></div>
					<div><span>Net Qty</span><strong>${format_number(totals.net_qty)}</strong></div>
				</div>
			</div>

			<div class="lx-footer-note">
				System generated selected stock movement ${mode === "preview" ? "combined preview" : "summary"}.
			</div>
		</div>
	`;
}


function ledgix_stock_view_selected(report) {
	const rows = ledgix_stock_get_selected_rows(report);

	if (!rows.length) {
		frappe.msgprint("Please select at least one movement.");
		return;
	}

	const html = ledgix_stock_selected_html(rows, "preview");

	const dialog = new frappe.ui.Dialog({
		title: `Selected Stock Movements Preview - ${rows.length} movement(s)`,
		size: "extra-large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "preview_html",
				options: html
			}
		],
		primary_action_label: "Print",
		primary_action: function() {
			ledgix_stock_print_html(html, "Selected Stock Movements Preview");
		}
	});

	dialog.show();
}


function ledgix_stock_print_selected(report) {
	const rows = ledgix_stock_get_selected_rows(report);

	if (!rows.length) {
		frappe.msgprint("Please select at least one movement.");
		return;
	}

	const html = ledgix_stock_selected_html(rows, "print");
	ledgix_stock_print_html(html, "Selected Stock Movements");
}


function ledgix_stock_download_selected(report) {
	const rows = ledgix_stock_get_selected_rows(report);

	if (!rows.length) {
		frappe.msgprint("Please select at least one movement.");
		return;
	}

	const headers = [
		"Movement ID",
		"Date",
		"Item",
		"Movement Type",
		"Quantity",
		"Reference Doctype",
		"Reference Name",
		"Reference Note",
		"Status",
		"Created By"
	];

	const csv_rows = rows.map(row => [
		row.movement,
		row.movement_date,
		row.item,
		row.movement_type,
		row.quantity,
		row.reference_doctype,
		row.reference_name,
		row.reference_note,
		row.status,
		row.owner
	]);

	const csv = [headers, ...csv_rows]
		.map(row => row.map(value => `"${String(value || "").replace(/"/g, '""')}"`).join(","))
		.join("\n");

	const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
	const url = URL.createObjectURL(blob);

	const link = document.createElement("a");
	link.href = url;
	link.download = "ledgix-stock-movements.csv";

	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);

	URL.revokeObjectURL(url);
}


function ledgix_stock_print_html(html, title) {
	const print_window = window.open("", "_blank");

	if (!print_window) {
		frappe.msgprint("Please allow popups to print.");
		return;
	}

	const styles = $("#ledgix-stock-report-style").html() || "";

	print_window.document.write(`
		<!doctype html>
		<html>
		<head>
			<title>${title}</title>
			<style>
				@page {
					size: A4;
					margin: 16mm;
				}

				body {
					font-family: Arial, sans-serif;
					color: #101828;
					background: #FFFFFF;
					font-size: 12px;
				}

				tr {
					page-break-inside: avoid;
				}

				${styles}
			</style>
		</head>
		<body>
			${html}
			<script>
				window.onload = function() {
					window.print();
				};
			</script>
		</body>
		</html>
	`);

	print_window.document.close();
}
