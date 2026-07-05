// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

frappe.query_reports["Ledgix Sales Return Report"] = {
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
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Ledgix Customer",
			placeholder: __("Select Customer")
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
			return ledgix_return_status_badge(data.status);
		}

		if (column.fieldname === "view_action" && data) {
			return `
				<div class="lx-icon-action">
					<button class="lx-icon-btn" onclick="ledgix_return_preview('${data.sales_return}')" title="View Return">
						<span class="lx-eye-icon"></span>
					</button>
				</div>
			`;
		}

		if (column.fieldname === "print_action" && data) {
			return `
				<div class="lx-icon-action">
					<button class="lx-icon-btn" onclick="ledgix_return_print_single('${data.sales_return}')" title="Print Return">
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
		ledgix_return_apply_style();

		report.page.add_inner_button(__("View Selected"), function() {
			ledgix_return_view_selected(report);
		});

		report.page.add_inner_button(__("Download Selected"), function() {
			ledgix_return_download_selected(report);
		});

		report.page.add_inner_button(__("Print Selected"), function() {
			ledgix_return_print_selected(report);
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

			ledgix_return_render_selected_summary(report);
		};

		setTimeout(clean_report_ui, 300);
		setTimeout(clean_report_ui, 900);
		setTimeout(clean_report_ui, 1600);

		$(document).off("change.ledgix_return_report");
		$(document).on("change.ledgix_return_report", ".dt-cell__content input[type='checkbox'], .dt-checkbox", function() {
			setTimeout(() => ledgix_return_render_selected_summary(report), 150);
		});
	}
};


function ledgix_return_status_badge(status) {
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

	return `<span class="lx-status-pill" style="color:${color}; background:${bg};">${status || ""}</span>`;
}


function ledgix_return_apply_style() {
	if ($("#ledgix-return-report-style").length) return;

	$("head").append(`
		<style id="ledgix-return-report-style">
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
				width:320px;
				border:1px solid #D0D5DD;
				border-radius:10px;
				padding:12px;
				background:#F9FAFB;
			}

			.lx-total-box div {
				display:flex;
				justify-content:space-between;
				padding:5px 0;
				font-size:12px;
			}

			.lx-total-box div:last-child {
				border-top:1px solid #D0D5DD;
				margin-top:6px;
				padding-top:10px;
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


function ledgix_return_get_selected_rows(report) {
	if (!report || !report.datatable || !report.data) return [];

	let selected_indexes = [];

	try {
		selected_indexes = report.datatable.rowmanager.getCheckedRows() || [];
	} catch (e) {
		selected_indexes = [];
	}

	return selected_indexes
		.map(index => report.data[index])
		.filter(row => row && row.sales_return);
}


function ledgix_return_render_selected_summary(report) {
	const rows = ledgix_return_get_selected_rows(report);
	$(".lx-selected-summary").remove();

	if (!rows.length) return;

	const total_returns = rows.length;
	const total_items = rows.reduce((sum, row) => sum + flt(row.items_count), 0);
	const total_qty = rows.reduce((sum, row) => sum + flt(row.total_qty), 0);
	const return_amount = rows.reduce((sum, row) => sum + flt(row.return_amount), 0);
	const total_profit_reversal = rows.reduce((sum, row) => sum + flt(row.total_profit_reversal), 0);
	const avg_return_value = total_returns ? return_amount / total_returns : 0;

	const html = `
		<div class="lx-selected-summary">
			<div class="lx-selected-summary-title">Selected Sales Returns Summary</div>
			<div class="lx-selected-summary-grid">
				<div class="lx-selected-card"><div class="label">Returns</div><div class="value">${total_returns}</div></div>
				<div class="lx-selected-card"><div class="label">Line Items</div><div class="value">${total_items}</div></div>
				<div class="lx-selected-card"><div class="label">Return Qty</div><div class="value">${format_number(total_qty)}</div></div>
				<div class="lx-selected-card"><div class="label">Return Amount</div><div class="value">${format_currency(return_amount)}</div></div>
				<div class="lx-selected-card"><div class="label">Profit Reversal</div><div class="value">${format_currency(total_profit_reversal)}</div></div>
				<div class="lx-selected-card"><div class="label">Avg Return Value</div><div class="value">${format_currency(avg_return_value)}</div></div>
			</div>
		</div>
	`;

	$(".report-wrapper").before(html);
}


function ledgix_return_preview(return_name) {
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Ledgix Sales Return",
			name: return_name
		},
		callback: function(r) {
			if (!r.message) {
				frappe.msgprint("Sales Return not found.");
				return;
			}

			const doc = r.message;
			const html = ledgix_return_preview_html(doc);

			const dialog = new frappe.ui.Dialog({
				title: `Sales Return Preview - ${doc.name}`,
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
					ledgix_return_print_html(html, `Sales Return ${doc.name}`);
				},
				secondary_action_label: "Open",
				secondary_action: function() {
					frappe.set_route("Form", "Ledgix Sales Return", doc.name);
				}
			});

			dialog.show();
		}
	});
}


function ledgix_return_preview_html(doc) {
	const items = doc.items || [];
	let total_qty = 0;
	let total_amount = 0;

	const rows = items.map((item, index) => {
		const qty = flt(item.quantity || item.return_quantity);
		const rate = flt(item.rate || item.selling_price || item.price);
		const amount = flt(item.amount);

		total_qty += qty;
		total_amount += amount;

		return `
			<tr>
				<td>${index + 1}</td>
				<td>${frappe.utils.escape_html(item.item || "")}</td>
				<td>${frappe.utils.escape_html(item.unit || "-")}</td>
				<td class="lx-text-right">${format_number(qty)}</td>
				<td class="lx-text-right">${format_currency(rate)}</td>
				<td class="lx-text-right">${format_currency(amount)}</td>
			</tr>
		`;
	}).join("");

	const return_amount = flt(doc.total_amount || total_amount);
	const total_profit_reversal = flt(doc.total_profit_reversal || 0);

	return `
		<div class="lx-print-doc">
			<div class="lx-doc-top">
				<div>
					<div class="lx-brand">LEDGIX</div>
					<div class="lx-subtitle">Sales Return Voucher</div>
				</div>
				<div class="lx-doc-title">
					<div>Sales Return Report</div>
					<span>${doc.name || "-"}</span>
				</div>
			</div>

			<div class="lx-info-grid">
				<div class="lx-info-box">
					<div class="lx-box-title">Customer Details</div>
					<div class="lx-info-row"><span>Customer</span><strong>${doc.customer || "Walk-in Customer"}</strong></div>
					<div class="lx-info-row"><span>Original Sale</span><strong>${doc.original_sale || doc.sale || "-"}</strong></div>
				</div>

				<div class="lx-info-box">
					<div class="lx-box-title">Return Details</div>
					<div class="lx-info-row"><span>Return ID</span><strong>${doc.name || "-"}</strong></div>
					<div class="lx-info-row"><span>Date</span><strong>${doc.return_date || doc.sales_return_date || doc.posting_date || "-"}</strong></div>
				</div>
			</div>

			<table class="lx-doc-table">
				<thead>
					<tr>
						<th style="width:40px;">#</th>
						<th>Item</th>
						<th>Unit</th>
						<th class="lx-text-right">Return Qty</th>
						<th class="lx-text-right">Rate</th>
						<th class="lx-text-right">Amount</th>
					</tr>
				</thead>
				<tbody>
					${rows || `<tr><td colspan="6" class="lx-empty-row">No items found.</td></tr>`}
				</tbody>
			</table>

			<div class="lx-total-wrap">
				<div class="lx-total-box">
					<div><span>Return Qty</span><strong>${format_number(total_qty)}</strong></div>
					<div><span>Return Amount</span><strong>${format_currency(return_amount)}</strong></div>
					<div><span>Profit Reversal</span><strong>${format_currency(total_profit_reversal)}</strong></div>
				</div>
			</div>

			<div class="lx-signatures">
				<div><span>Prepared By</span></div>
				<div><span>Checked By</span></div>
				<div><span>Customer Signature</span></div>
			</div>

			<div class="lx-footer-note">
				System generated sales return report. Please verify original sale and returned quantities before filing.
			</div>
		</div>
	`;
}


function ledgix_return_view_selected(report) {
	const rows = ledgix_return_get_selected_rows(report);

	if (!rows.length) {
		frappe.msgprint("Please select at least one sales return.");
		return;
	}

	const html = ledgix_return_selected_html(rows, "Sales Return Combined View", "Selected Sales Returns Preview");

	const dialog = new frappe.ui.Dialog({
		title: `Selected Sales Returns Preview - ${rows.length} return(s)`,
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
			ledgix_return_print_html(html, "Selected Sales Returns Preview");
		}
	});

	dialog.show();
}


function ledgix_return_print_single(return_name) {
	frappe.call({
		method: "frappe.client.get",
		args: {
			doctype: "Ledgix Sales Return",
			name: return_name
		},
		callback: function(r) {
			if (!r.message) {
				frappe.msgprint("Sales Return not found.");
				return;
			}

			const html = ledgix_return_preview_html(r.message);
			ledgix_return_print_html(html, `Sales Return ${return_name}`);
		}
	});
}


function ledgix_return_print_selected(report) {
	const rows = ledgix_return_get_selected_rows(report);

	if (!rows.length) {
		frappe.msgprint("Please select at least one sales return.");
		return;
	}

	const html = ledgix_return_selected_html(rows, "Sales Return Summary", "Selected Sales Returns Summary");
	ledgix_return_print_html(html, "Selected Sales Returns");
}


function ledgix_return_selected_html(rows, title, subtitle) {
	const total_qty = rows.reduce((sum, row) => sum + flt(row.total_qty), 0);
	const return_amount = rows.reduce((sum, row) => sum + flt(row.return_amount), 0);
	const total_profit_reversal = rows.reduce((sum, row) => sum + flt(row.total_profit_reversal), 0);
	const avg_return_value = rows.length ? return_amount / rows.length : 0;

	const table_rows = rows.map((row, index) => `
		<tr>
			<td>${index + 1}</td>
			<td>${row.sales_return || ""}</td>
			<td>${row.original_sale || "-"}</td>
			<td>${row.return_date || ""}</td>
			<td>${row.customer || ""}</td>
			<td>${row.status || ""}</td>
			<td class="lx-text-right">${format_number(row.total_qty || 0)}</td>
			<td class="lx-text-right">${format_currency(row.return_amount || 0)}</td>
		</tr>
	`).join("");

	return `
		<div class="lx-print-doc">
			<div class="lx-doc-top">
				<div>
					<div class="lx-brand">LEDGIX</div>
					<div class="lx-subtitle">${subtitle}</div>
				</div>
				<div class="lx-doc-title">
					<div>${title}</div>
					<span>${rows.length} return(s)</span>
				</div>
			</div>

			<table class="lx-doc-table">
				<thead>
					<tr>
						<th style="width:40px;">#</th>
						<th>Return</th>
						<th>Original Sale</th>
						<th>Date</th>
						<th>Customer</th>
						<th>Status</th>
						<th class="lx-text-right">Qty</th>
						<th class="lx-text-right">Amount</th>
					</tr>
				</thead>
				<tbody>${table_rows}</tbody>
			</table>

			<div class="lx-total-wrap">
				<div class="lx-total-box">
					<div><span>Returns</span><strong>${rows.length}</strong></div>
					<div><span>Return Qty</span><strong>${format_number(total_qty)}</strong></div>
					<div><span>Return Amount</span><strong>${format_currency(return_amount)}</strong></div>
					<div><span>Profit Reversal</span><strong>${format_currency(total_profit_reversal)}</strong></div>
					<div><span>Avg Return Value</span><strong>${format_currency(avg_return_value)}</strong></div>
				</div>
			</div>

			<div class="lx-footer-note">
				System generated selected sales returns report.
			</div>
		</div>
	`;
}


function ledgix_return_download_selected(report) {
	const rows = ledgix_return_get_selected_rows(report);

	if (!rows.length) {
		frappe.msgprint("Please select at least one sales return.");
		return;
	}

	const headers = [
		"Return ID",
		"Original Sale",
		"Date",
		"Customer",
		"Status",
		"Items",
		"Return Qty",
		"Return Amount",
		"Avg Return Value"
	];

	const csv_rows = rows.map(row => [
		row.sales_return,
		row.original_sale,
		row.return_date,
		row.customer,
		row.status,
		row.items_count,
		row.total_qty,
		row.return_amount,
		row.avg_return_value
	]);

	const csv = [headers, ...csv_rows]
		.map(row => row.map(value => `"${String(value || "").replace(/"/g, '""')}"`).join(","))
		.join("\n");

	const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
	const url = URL.createObjectURL(blob);

	const link = document.createElement("a");
	link.href = url;
	link.download = "ledgix-selected-sales-returns.csv";
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);

	URL.revokeObjectURL(url);
}


function ledgix_return_print_html(html, title) {
	const print_window = window.open("", "_blank");

	if (!print_window) {
		frappe.msgprint("Please allow popups to print.");
		return;
	}

	const styles = $("#ledgix-return-report-style").html() || "";

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