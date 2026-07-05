// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

frappe.query_reports["Ledgix Customer Statement"] = {
	filters: [
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Ledgix Customer",
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

		if (column.fieldname === "payment_status" && data && data.payment_status) {
			return ledgix_customer_statement_status_badge(data.payment_status);
		}

		if (column.fieldname === "reference_doctype" && data) {
			return ledgix_customer_statement_type_badge(data.reference_doctype);
		}

		if (column.fieldname === "debit" && data && flt(data.debit)) {
			return `<span class="lx-debit-text">${format_currency(data.debit)}</span>`;
		}

		if (column.fieldname === "credit" && data && flt(data.credit)) {
			return `<span class="lx-credit-text">${format_currency(data.credit)}</span>`;
		}

		if (column.fieldname === "balance" && data) {
			const cls = flt(data.balance) > 0 ? "lx-balance-due" : "lx-balance-clear";
			return `<span class="${cls}">${format_currency(data.balance || 0)}</span>`;
		}

		if (column.fieldname === "open_action" && data && data.reference_name && data.reference_doctype !== "Opening Balance") {
			return `
				<div class="lx-icon-action">
					<button class="lx-icon-btn" onclick="ledgix_customer_statement_open('${data.reference_doctype}', '${data.reference_name}')" title="Open Reference">
						<span class="lx-eye-icon"></span>
					</button>
				</div>
			`;
		}

		return value;
	},

	onload: function(report) {
		ledgix_customer_statement_apply_style();

		report.page.add_inner_button(__("Print Statement"), function() {
			ledgix_customer_statement_print(report);
		});

		report.page.add_inner_button(__("Download CSV"), function() {
			ledgix_customer_statement_download(report);
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

			ledgix_customer_statement_render_summary(report);
		};

		setTimeout(clean_report_ui, 300);
		setTimeout(clean_report_ui, 900);
		setTimeout(clean_report_ui, 1600);
	},

	after_datatable_render: function(report) {
		ledgix_customer_statement_render_summary(report);
	}
};


function ledgix_customer_statement_status_badge(status) {
	let color = "#344054";
	let bg = "#F2F4F7";

	if (status === "Paid") {
		color = "#027A48";
		bg = "#ECFDF3";
	}

	if (status === "Partial") {
		color = "#B54708";
		bg = "#FFFAEB";
	}

	if (status === "Unpaid") {
		color = "#B42318";
		bg = "#FEF3F2";
	}

	return `<span class="lx-status-pill" style="color:${color}; background:${bg};">${status || ""}</span>`;
}


function ledgix_customer_statement_type_badge(type) {
	let color = "#344054";
	let bg = "#F2F4F7";

	if (type === "Ledgix Sale") {
		color = "#175CD3";
		bg = "#EFF8FF";
	}

	if (type === "Ledgix Sales Return") {
		color = "#B42318";
		bg = "#FEF3F2";
	}

	if (type === "Opening Balance") {
		color = "#6941C6";
		bg = "#F4F3FF";
	}

	return `<span class="lx-status-pill" style="color:${color}; background:${bg};">${type || ""}</span>`;
}


function ledgix_customer_statement_apply_style() {
	if ($("#ledgix-customer-statement-style").length) return;

	$("head").append(`
		<style id="ledgix-customer-statement-style">
			.lx-status-pill {
				display:inline-flex;
				align-items:center;
				padding:3px 9px;
				border-radius:999px;
				font-size:12px;
				font-weight:650;
				white-space:nowrap;
			}

			.lx-debit-text {
				color:#B42318;
				font-weight:750;
			}

			.lx-credit-text {
				color:#027A48;
				font-weight:750;
			}

			.lx-balance-due {
				color:#B42318;
				font-weight:800;
			}

			.lx-balance-clear {
				color:#027A48;
				font-weight:800;
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
				grid-template-columns:repeat(4, minmax(120px, 1fr));
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

			.lx-total-wrap {
				display:flex;
				justify-content:flex-end;
				margin-top:16px;
			}

			.lx-total-box {
				width:330px;
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


function ledgix_customer_statement_rows(report) {
	if (!report || !report.data) return [];
	return report.data.filter(row => row && row.reference_doctype);
}


function ledgix_customer_statement_totals(rows) {
	const transaction_rows = rows.filter(row => !row.is_opening);
	const total_debit = transaction_rows.reduce((sum, row) => sum + flt(row.debit), 0);
	const total_credit = transaction_rows.reduce((sum, row) => sum + flt(row.credit), 0);
	const closing_balance = rows.length ? flt(rows[rows.length - 1].balance) : 0;

	return {
		transactions: transaction_rows.length,
		total_debit,
		total_credit,
		closing_balance
	};
}


function ledgix_customer_statement_render_summary(report) {
	const rows = ledgix_customer_statement_rows(report);
	$(".lx-selected-summary").remove();

	if (!rows.length) return;

	const totals = ledgix_customer_statement_totals(rows);

	const html = `
		<div class="lx-selected-summary">
			<div class="lx-selected-summary-title">Customer Statement Summary</div>
			<div class="lx-selected-summary-grid">
				<div class="lx-selected-card"><div class="label">Transactions</div><div class="value">${totals.transactions}</div></div>
				<div class="lx-selected-card"><div class="label">Debit</div><div class="value">${format_currency(totals.total_debit)}</div></div>
				<div class="lx-selected-card"><div class="label">Credit</div><div class="value">${format_currency(totals.total_credit)}</div></div>
				<div class="lx-selected-card"><div class="label">Closing Balance</div><div class="value">${format_currency(totals.closing_balance)}</div></div>
			</div>
		</div>
	`;

	$(".report-wrapper").before(html);
}


function ledgix_customer_statement_open(doctype, name) {
	if (!doctype || !name || doctype === "Opening Balance") return;
	frappe.set_route("Form", doctype, name);
}


function ledgix_customer_statement_print(report) {
	const rows = ledgix_customer_statement_rows(report);

	if (!rows.length) {
		frappe.msgprint("No statement data to print.");
		return;
	}

	const html = ledgix_customer_statement_html(report, rows);
	ledgix_customer_statement_print_html(html, "Customer Statement");
}


function ledgix_customer_statement_html(report, rows) {
	const customer = report.get_filter_value("customer") || "";
	const from_date = report.get_filter_value("from_date") || "";
	const to_date = report.get_filter_value("to_date") || "";
	const totals = ledgix_customer_statement_totals(rows);

	const table_rows = rows.map((row, index) => `
		<tr>
			<td>${index + 1}</td>
			<td>${row.posting_date || ""}</td>
			<td>${frappe.utils.escape_html(row.reference_doctype || "")}</td>
			<td>${frappe.utils.escape_html(row.reference_name || "-")}</td>
			<td>${frappe.utils.escape_html(row.invoice_number || "-")}</td>
			<td>${frappe.utils.escape_html(row.details || "")}</td>
			<td class="lx-text-right">${flt(row.debit) ? format_currency(row.debit) : "-"}</td>
			<td class="lx-text-right">${flt(row.credit) ? format_currency(row.credit) : "-"}</td>
			<td class="lx-text-right">${format_currency(row.balance || 0)}</td>
		</tr>
	`).join("");

	return `
		<div class="lx-print-doc">
			<div class="lx-doc-top">
				<div>
					<div class="lx-brand">LEDGIX</div>
					<div class="lx-subtitle">Customer Ledger Statement</div>
				</div>
				<div class="lx-doc-title">
					<div>Customer Statement</div>
					<span>${from_date || "-"} to ${to_date || "-"}</span>
				</div>
			</div>

			<div class="lx-info-grid">
				<div class="lx-info-box">
					<div class="lx-box-title">Customer</div>
					<div class="lx-info-row"><span>Customer</span><strong>${frappe.utils.escape_html(customer)}</strong></div>
					<div class="lx-info-row"><span>Period</span><strong>${from_date || "-"} to ${to_date || "-"}</strong></div>
				</div>

				<div class="lx-info-box">
					<div class="lx-box-title">Summary</div>
					<div class="lx-info-row"><span>Transactions</span><strong>${totals.transactions}</strong></div>
					<div class="lx-info-row"><span>Closing Balance</span><strong>${format_currency(totals.closing_balance)}</strong></div>
				</div>
			</div>

			<table class="lx-doc-table">
				<thead>
					<tr>
						<th style="width:35px;">#</th>
						<th>Date</th>
						<th>Type</th>
						<th>Reference</th>
						<th>Invoice</th>
						<th>Details</th>
						<th class="lx-text-right">Debit</th>
						<th class="lx-text-right">Credit</th>
						<th class="lx-text-right">Balance</th>
					</tr>
				</thead>
				<tbody>${table_rows}</tbody>
			</table>

			<div class="lx-total-wrap">
				<div class="lx-total-box">
					<div><span>Total Debit</span><strong>${format_currency(totals.total_debit)}</strong></div>
					<div><span>Total Credit</span><strong>${format_currency(totals.total_credit)}</strong></div>
					<div><span>Closing Balance</span><strong>${format_currency(totals.closing_balance)}</strong></div>
				</div>
			</div>

			<div class="lx-signatures">
				<div><span>Prepared By</span></div>
				<div><span>Checked By</span></div>
				<div><span>Customer Signature</span></div>
			</div>

			<div class="lx-footer-note">
				System generated customer statement. Positive balance indicates receivable/outstanding from customer.
			</div>
		</div>
	`;
}


function ledgix_customer_statement_download(report) {
	const rows = ledgix_customer_statement_rows(report);

	if (!rows.length) {
		frappe.msgprint("No statement data to download.");
		return;
	}

	const headers = [
		"Date",
		"Type",
		"Reference",
		"Invoice No",
		"Payment Status",
		"Details",
		"Debit",
		"Credit",
		"Balance"
	];

	const csv_rows = rows.map(row => [
		row.posting_date,
		row.reference_doctype,
		row.reference_name,
		row.invoice_number,
		row.payment_status,
		row.details,
		row.debit,
		row.credit,
		row.balance
	]);

	const csv = [headers, ...csv_rows]
		.map(row => row.map(value => `"${String(value || "").replace(/"/g, '""')}"`).join(","))
		.join("\n");

	const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
	const url = URL.createObjectURL(blob);

	const link = document.createElement("a");
	link.href = url;
	link.download = "ledgix-customer-statement.csv";
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);

	URL.revokeObjectURL(url);
}


function ledgix_customer_statement_print_html(html, title) {
	const print_window = window.open("", "_blank");

	if (!print_window) {
		frappe.msgprint("Please allow popups to print.");
		return;
	}

	const styles = $("#ledgix-customer-statement-style").html() || "";

	print_window.document.write(`
		<!doctype html>
		<html>
		<head>
			<title>${title}</title>
			<style>
				@page {
					size: A4 landscape;
					margin: 12mm;
				}

				body {
					font-family: Arial, sans-serif;
					color: #101828;
					background: #FFFFFF;
					font-size: 11px;
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
