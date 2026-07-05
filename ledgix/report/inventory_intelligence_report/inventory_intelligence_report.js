// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

const LEDGIX_IIR_EVENT = "ledgix_inventory_intelligence_updated";
const LEDGIX_IIR_RELEVANT_DOCTYPES = new Set([
	"Ledgix Purchase",
	"Ledgix Purchase Item",
	"Ledgix Sale",
	"Ledgix Sale Item",
	"Ledgix Sales Return",
	"Ledgix Sales Return Item",
	"Ledgix Stock Lot",
	"Ledgix Stock Lot Allocation",
	"Ledgix Stock Movement",
]);

const LEDGIX_IIR_NUMERIC_FIELDS = new Set([
	"purchased_qty",
	"current_lot_qty",
	"sale_qty",
	"return_qty",
	"net_sold_qty",
	"unit_cost",
	"total_cost",
	"selling_amount",
	"return_amount",
	"profit",
	"loss",
	"purchase_rate",
	"purchase_amount",
]);

const LEDGIX_IIR_MONEY_FIELDS = new Set([
	"unit_cost",
	"total_cost",
	"selling_amount",
	"return_amount",
	"profit",
	"loss",
	"purchase_rate",
	"purchase_amount",
]);

frappe.query_reports["Inventory Intelligence Report"] = {
	filters: [
		{
			fieldname: "item",
			label: __("Item"),
			fieldtype: "Link",
			options: "Ledgix Item",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "view_mode",
			label: __("View Mode"),
			fieldtype: "Select",
			options: "Strict Inventory\nBilling Only",
			default: "Strict Inventory",
		},
	],

	onload(report) {
		installInventoryIntelligenceStyles();
		installInventoryIntelligenceRealtime(report);
	},

	refresh(report) {
		installInventoryIntelligenceStyles();
		installInventoryIntelligenceRealtime(report);
		renderLiveStatus(report, "Live sync ready");
		setTimeout(() => renderInventoryIntelligenceSummary(report), 80);
	},

	formatter(value, row, column, data, default_formatter) {
		const fieldname = column.fieldname;
		const formatted = default_formatter(value, row, column, data);

		if (fieldname === "lot_status") {
			return lotStatusText(value || formatted);
		}

		if (fieldname === "cycle_status") {
			return cycleStatusText(value || formatted);
		}

		if (fieldname === "row_type") {
			return `<span class="ledgix-iir-plain-status">${frappe.utils.escape_html(value || "-")}</span>`;
		}

		if (LEDGIX_IIR_NUMERIC_FIELDS.has(fieldname)) {
			return formatInventoryNumber(value, formatted, fieldname, data);
		}

		return formatted || "-";
	},

	after_datatable_render(report) {
		renderInventoryIntelligenceSummary(report);
		decorateInventoryIntelligenceRows(report);
		hideReportColumnFilters(report);
	},
};

function installInventoryIntelligenceRealtime(report) {
	if (!report || report.__ledgixIIRRealtimeInstalled) return;
	report.__ledgixIIRRealtimeInstalled = true;
	report.__ledgixIIRRefreshTimer = null;
	report.__ledgixIIRPollTimer = null;
	report.__ledgixIIRLastRefreshAt = 0;
	report.__ledgixIIRRefreshing = false;

	const refreshReport = (payload = {}, options = {}) => {
		if (!isCurrentInventoryReport()) return;
		if (!isRelevantInventoryPayload(payload, report)) return;
		if (report.__ledgixIIRRefreshing) return;

		clearTimeout(report.__ledgixIIRRefreshTimer);
		report.__ledgixIIRRefreshTimer = setTimeout(() => {
			if (!isCurrentInventoryReport()) return;
			if (document.hidden) {
				report.__ledgixIIRNeedsRefresh = true;
				renderLiveStatus(report, "Update waiting");
				return;
			}

			const now = Date.now();
			const minGap = options.poll ? 4800 : 900;
			if (now - report.__ledgixIIRLastRefreshAt < minGap) return;
			report.__ledgixIIRLastRefreshAt = now;
			report.__ledgixIIRRefreshing = true;
			renderLiveStatus(report, options.poll ? "Auto checking…" : "Updating…");

			const scrollBody = getDatatableScrollBody(report);
			const scrollTop = scrollBody ? scrollBody.scrollTop : 0;
			const scrollLeft = scrollBody ? scrollBody.scrollLeft : 0;

			const refreshPromise = report.refresh ? report.refresh() : frappe.query_report.refresh();
			Promise.resolve(refreshPromise)
				.finally(() => {
					setTimeout(() => {
						const nextScrollBody = getDatatableScrollBody(report);
						if (nextScrollBody) {
							nextScrollBody.scrollTop = scrollTop;
							nextScrollBody.scrollLeft = scrollLeft;
						}
						renderInventoryIntelligenceSummary(report);
						renderLiveStatus(report, options.poll ? "Auto refreshed" : "Updated just now");
						report.__ledgixIIRRefreshing = false;
					}, 120);
				})
				.catch(() => {
					report.__ledgixIIRRefreshing = false;
					renderLiveStatus(report, "Refresh failed");
				});
		}, options.poll ? 0 : 180);
	};

	report.__ledgixIIRManualRefresh = refreshReport;
	frappe.realtime.on(LEDGIX_IIR_EVENT, refreshReport);
	frappe.realtime.on("doc_update", refreshReport);

	

	document.addEventListener("visibilitychange", () => {
		if (!document.hidden && report.__ledgixIIRNeedsRefresh && isCurrentInventoryReport()) {
			report.__ledgixIIRNeedsRefresh = false;
			refreshReport({ force: true });
		}
	});
}

function isCurrentInventoryReport() {
	return frappe.query_report && frappe.query_report.report_name === "Inventory Intelligence Report";
}

function isRelevantInventoryPayload(payload, report) {
	if (!payload || payload.force) return true;

	const doctype = payload.doctype || payload.ref_doctype;
	if (doctype && !LEDGIX_IIR_RELEVANT_DOCTYPES.has(doctype)) return false;

	const reportItem = report.get_filter_value ? report.get_filter_value("item") : null;
	const payloadItem = payload.item || payload.item_code;
	if (reportItem && payloadItem && reportItem !== payloadItem) return false;

	return true;
}

function renderLiveStatus(report, message) {
	const wrapper = report && report.wrapper && report.wrapper[0];
	if (!wrapper) return;

	let status = wrapper.querySelector(".ledgix-iir-live-status");
	if (!status) {
		status = document.createElement("div");
		status.className = "ledgix-iir-live-status";
		const actions = wrapper.querySelector(".page-actions") || wrapper.querySelector(".report-actions");
		if (actions) {
			actions.prepend(status);
		} else {
			wrapper.prepend(status);
		}
	}

	status.textContent = message || "Live sync ready";
}

function renderInventoryIntelligenceSummary(report) {
	const wrapper = report && report.wrapper && report.wrapper[0];
	if (!wrapper || !Array.isArray(report.data)) return;

	const summary = calculateInventorySummary(report.data);
	let panel = wrapper.querySelector(".ledgix-iir-summary-panel");
	if (!panel) {
		panel = document.createElement("div");
		panel.className = "ledgix-iir-summary-panel";
		const target = wrapper.querySelector(".report-wrapper") || wrapper.querySelector(".datatable") || wrapper;
		target.parentNode.insertBefore(panel, target);
	}

	panel.innerHTML = `
		<div class="ledgix-iir-health ${summary.healthTone}">
			<span>${summary.healthLabel}</span>
			<small>${summary.healthNote}</small>
		</div>
		<div class="ledgix-iir-card-grid">
			${summaryCard("Purchased Qty", "Original lot purchase", summary.purchasedQty, "qty purchase")}
			${summaryCard("Current Lot Qty", "Live remaining stock", summary.currentLotQty, "qty current")}
			${summaryCard("Sold Qty", "Gross outgoing qty", summary.soldQty, "qty sale")}
			${summaryCard("Returned Qty", "Qty added back", summary.returnedQty, "qty return")}
			${summaryCard("Net Sold Qty", "Sold after returns", summary.netSoldQty, "qty net")}
			${summaryCard("Gross Selling", "Before returns", summary.grossSelling, "money gross", true)}
			${summaryCard("Return Amount", "Reversed value", summary.returnAmount, "money return", true)}
			${summaryCard("Net Selling", "Final earned sale", summary.netSelling, "money net", true)}
			${summaryCard("Profit", "After return impact", summary.profit, "money profit", true)}
			${summaryCard("Loss", "Only if negative", summary.loss, "money loss", true)}
		</div>
	`;
}

function calculateInventorySummary(rows) {
	const motherRows = rows.filter((row) => row && row.row_type === "Mother");
	const saleRows = rows.filter((row) => row && ["Sale", "Partial Return", "Returned"].includes(String(row.cycle_status || "")));

	const purchasedQty = sumRows(motherRows, "purchased_qty");
	const currentLotQty = sumRows(motherRows, "current_lot_qty");
	const soldQty = sumRows(saleRows, "sale_qty");
	const returnedQty = sumRows(saleRows, "return_qty");
	const netSoldQty = sumRows(saleRows, "net_sold_qty");
	const grossSelling = sumRows(saleRows, "selling_amount") + sumRows(saleRows, "return_amount");
	const returnAmount = sumRows(saleRows, "return_amount");
	const netSelling = sumRows(saleRows, "selling_amount");
	const profit = sumRows(saleRows, "profit");
	const loss = sumRows(saleRows, "loss");
	const missingCount = countMissingExpectedValues(rows);
	const calcWarnings = countCalculationWarnings(saleRows);

	let healthTone = "ok";
	let healthLabel = "Data OK";
	let healthNote = "Cards and table are synced from visible report rows.";

	if (missingCount > 0) {
		healthTone = "error";
		healthLabel = "Backend Check";
		healthNote = `${missingCount} expected value${missingCount > 1 ? "s" : ""} missing from backend rows.`;
	} else if (calcWarnings > 0) {
		healthTone = "warn";
		healthLabel = "Calculation Warning";
		healthNote = `${calcWarnings} row${calcWarnings > 1 ? "s" : ""} need profit/return verification.`;
	}

	return {
		purchasedQty,
		currentLotQty,
		soldQty,
		returnedQty,
		netSoldQty,
		grossSelling,
		returnAmount,
		netSelling,
		profit,
		loss,
		healthTone,
		healthLabel,
		healthNote,
	};
}

function summaryCard(title, subtitle, value, tone, isMoney = false) {
	const hasRealValue = isFiniteNumber(value) && Math.abs(flt(value)) > 0;

	return `
		<div class="ledgix-iir-summary-card ${tone} ${tone === "loss" && hasRealValue ? "has-loss" : ""}">
			<div class="ledgix-iir-summary-title">${frappe.utils.escape_html(title)}</div>
			<div class="ledgix-iir-summary-value">${formatSummaryValue(value, isMoney)}</div>
			<div class="ledgix-iir-summary-subtitle">${frappe.utils.escape_html(subtitle)}</div>
		</div>
	`;
}

function formatSummaryValue(value, isMoney = false) {
	if (!isFiniteNumber(value) || Math.abs(flt(value)) === 0) return "-";
	if (isMoney) return formatCurrencyValue(value);
	return frappe.format(value, { fieldtype: "Float", precision: 3 });
}

function formatInventoryNumber(value, formatted, fieldname, data) {
	if (isMissingExpectedValue(value, fieldname, data)) {
		return `<span class="ledgix-iir-backend-check" title="Expected value is missing from backend row">Backend Check</span>`;
	}

	if (!isFiniteNumber(value) || Math.abs(flt(value)) === 0) {
		return `<span class="ledgix-iir-number muted">-</span>`;
	}

	const tone = getNumberTone(fieldname, data, value);
	const display = formatted || (LEDGIX_IIR_MONEY_FIELDS.has(fieldname) ? formatCurrencyValue(value) : frappe.format(value, { fieldtype: "Float", precision: 3 }));
	return `<span class="ledgix-iir-number ${tone}">${display}</span>`;
}

function getNumberTone(fieldname, data, value) {
	if (["purchased_qty", "current_lot_qty", "net_sold_qty"].includes(fieldname)) return "positive";
	if (["sale_qty", "return_amount", "loss"].includes(fieldname)) return "negative";
	if (fieldname === "return_qty") return "warning";
	if (["selling_amount", "profit", "purchase_amount", "total_cost"].includes(fieldname)) return flt(value) < 0 ? "negative" : "positive";
	return "neutral";
}

function isMissingExpectedValue(value, fieldname, data) {
	if (value !== undefined && value !== null && value !== "") return false;
	if (!data) return false;

	const status = String(data.cycle_status || "");
	const rowType = String(data.row_type || "");

	if (rowType === "Mother") {
		return ["purchased_qty", "current_lot_qty", "unit_cost", "total_cost"].includes(fieldname);
	}

	if (["Sale", "Partial Return", "Returned"].includes(status)) {
		return ["sale_qty", "net_sold_qty", "unit_cost", "total_cost", "selling_amount", "profit", "loss"].includes(fieldname);
	}

	if (["Return"].includes(status)) {
		return ["return_qty", "return_amount"].includes(fieldname);
	}

	return false;
}

function countMissingExpectedValues(rows) {
	let count = 0;
	(rows || []).forEach((row) => {
		LEDGIX_IIR_NUMERIC_FIELDS.forEach((fieldname) => {
			if (isMissingExpectedValue(row && row[fieldname], fieldname, row)) count += 1;
		});
	});
	return count;
}

function countCalculationWarnings(saleRows) {
	let count = 0;
	(saleRows || []).forEach((row) => {
		const saleQty = flt(row.sale_qty);
		const returnQty = flt(row.return_qty);
		const netSoldQty = flt(row.net_sold_qty);
		if (Math.abs((saleQty - returnQty) - netSoldQty) > 0.001) count += 1;
		if (returnQty > saleQty) count += 1;
	});
	return count;
}

function sumRows(rows, fieldname) {
	return (rows || []).reduce((total, row) => total + flt(row && row[fieldname]), 0);
}

function isFiniteNumber(value) {
	return value !== null && value !== undefined && value !== "" && Number.isFinite(flt(value));
}

function formatCurrencyValue(value) {
	return format_currency(flt(value), frappe.defaults.get_default("currency") || "PKR", 2);
}

function decorateInventoryIntelligenceRows(report) {
	const wrapper = report && report.wrapper && report.wrapper[0];
	if (!wrapper || !report.data || !report.datatable) return;

	wrapper.querySelectorAll(".dt-row").forEach((rowEl) => {
		const rowIndex = Number(rowEl.getAttribute("data-row-index"));
		const rowData = report.data[rowIndex];
		if (!rowData) return;

		rowEl.classList.toggle("ledgix-iir-mother-row", rowData.row_type === "Mother");
		rowEl.classList.toggle("ledgix-iir-child-row", rowData.row_type !== "Mother");
		rowEl.dataset.ledgixLotNo = rowData.lot_no || "";

		if (rowEl.dataset.ledgixIIRClickBound) return;
		rowEl.dataset.ledgixIIRClickBound = "1";
		rowEl.addEventListener("click", () => selectInventoryReportRow(wrapper, rowEl));
	});
}

function selectInventoryReportRow(wrapper, rowEl) {
	const lotNo = rowEl.dataset.ledgixLotNo;

	wrapper.querySelectorAll(".dt-row.ledgix-iir-selected-row").forEach((activeRow) => {
		activeRow.classList.remove("ledgix-iir-selected-row");
	});
	rowEl.classList.add("ledgix-iir-selected-row");

	wrapper.querySelectorAll(".dt-row.ledgix-iir-same-lot-row").forEach((sameLotRow) => {
		sameLotRow.classList.remove("ledgix-iir-same-lot-row");
	});

	if (lotNo) {
		wrapper.querySelectorAll(`.dt-row[data-ledgix-lot-no="${cssEscape(lotNo)}"]`).forEach((sameLotRow) => {
			sameLotRow.classList.add("ledgix-iir-same-lot-row");
		});
	}
}

function hideReportColumnFilters(report) {
	const wrapper = report && report.wrapper && report.wrapper[0];
	if (!wrapper) return;

	wrapper.querySelectorAll(".dt-filter, .dt-row-filter, .datatable .filter-row, .dt-header .dt-filter-input").forEach((el) => {
		el.style.display = "none";
	});
}

function getDatatableScrollBody(report) {
	const wrapper = report && report.wrapper && report.wrapper[0];
	if (!wrapper) return null;
	return wrapper.querySelector(".dt-scrollable") || wrapper.querySelector(".datatable .dt-scrollable") || null;
}

function lotStatusText(status) {
	const normalized = String(status || "N/A").trim();
	const safeStatus = frappe.utils.escape_html(normalized);
	const cssClass = normalized === "Open" ? "open" : normalized === "Closed" ? "closed" : "neutral";
	return `<span class="ledgix-iir-lot-status-text ${cssClass}">${safeStatus}</span>`;
}

function cycleStatusText(status) {
	const normalized = String(status || "N/A").trim();
	const safeStatus = frappe.utils.escape_html(normalized);
	const slug = normalized.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "neutral";
	return `<span class="ledgix-iir-cycle-status ${slug}">${safeStatus}</span>`;
}

function installInventoryIntelligenceStyles() {
	if (document.getElementById("ledgix-iir-report-styles")) return;

	const style = document.createElement("style");
	style.id = "ledgix-iir-report-styles";
	style.textContent = `
		.query-report[data-report-name="Inventory Intelligence Report"] .dt-row-filter,
		.query-report[data-report-name="Inventory Intelligence Report"] .dt-filter,
		.query-report[data-report-name="Inventory Intelligence Report"] .filter-row,
		.query-report[data-report-name="Inventory Intelligence Report"] .dt-header .dt-filter-input {
			display: none !important;
		}

		.ledgix-iir-live-status {
			display: inline-flex;
			align-items: center;
			gap: 6px;
			min-height: 28px;
			padding: 5px 10px;
			border: 1px solid rgba(16, 185, 129, 0.22);
			border-radius: 10px;
			background: rgba(16, 185, 129, 0.08);
			color: #047857;
			font-size: 12px;
			font-weight: 650;
			letter-spacing: -0.01em;
		}
		.ledgix-iir-live-status::before {
			content: "";
			width: 7px;
			height: 7px;
			border-radius: 999px;
			background: #10b981;
			box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.12);
		}

		.ledgix-iir-summary-panel {
			margin: 12px 0 16px;
			padding: 14px;
			border: 1px solid rgba(15, 23, 42, 0.08);
			border-radius: 18px;
			background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
			box-shadow: 0 16px 42px rgba(15, 23, 42, 0.07);
		}
		.ledgix-iir-card-grid {
			display: grid;
			grid-template-columns: repeat(5, minmax(130px, 1fr));
			gap: 10px;
		}
		.ledgix-iir-summary-card {
			min-height: 92px;
			padding: 13px 14px;
			border: 1px solid rgba(15, 23, 42, 0.08);
			border-radius: 16px;
			background: rgba(255, 255, 255, 0.92);
			box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
		}
		.ledgix-iir-summary-title {
			font-size: 12px;
			font-weight: 720;
			color: #334155;
			letter-spacing: -0.01em;
		}
		.ledgix-iir-summary-value {
			margin-top: 7px;
			font-size: 20px;
			font-weight: 820;
			line-height: 1.15;
			letter-spacing: -0.025em;
		}
		.ledgix-iir-summary-subtitle {
			margin-top: 7px;
			font-size: 11px;
			font-weight: 560;
			color: #64748b;
		}
		.ledgix-iir-summary-card.purchase .ledgix-iir-summary-value { color: #2563eb; }
		.ledgix-iir-summary-card.current .ledgix-iir-summary-value,
		.ledgix-iir-summary-card.net .ledgix-iir-summary-value,
		.ledgix-iir-summary-card.gross .ledgix-iir-summary-value,
		.ledgix-iir-summary-card.profit .ledgix-iir-summary-value { color: #059669; }
		.ledgix-iir-summary-card.sale .ledgix-iir-summary-value,
		.ledgix-iir-summary-card.return.money .ledgix-iir-summary-value {
			color: #dc2626;
		}

		.ledgix-iir-summary-card.loss .ledgix-iir-summary-value {
			color: #d97706;
		}

		.ledgix-iir-summary-card.loss.has-loss .ledgix-iir-summary-value {
			color: #dc2626;
		}
		.ledgix-iir-summary-card.return.qty .ledgix-iir-summary-value { color: #d97706; }

		.ledgix-iir-health {
			display: flex;
			align-items: center;
			justify-content: space-between;
			gap: 10px;
			margin-bottom: 12px;
			padding: 9px 11px;
			border-radius: 13px;
			font-size: 12px;
			font-weight: 760;
		}
		.ledgix-iir-health small {
			font-size: 11px;
			font-weight: 560;
		}
		.ledgix-iir-health.ok { background: rgba(16, 185, 129, 0.09); color: #047857; }
		.ledgix-iir-health.warn { background: rgba(245, 158, 11, 0.12); color: #b45309; }
		.ledgix-iir-health.error { background: rgba(220, 38, 38, 0.10); color: #b91c1c; }

		.ledgix-iir-lot-status-text,
		.ledgix-iir-cycle-status,
		.ledgix-iir-number,
		.ledgix-iir-plain-status {
			display: inline-flex;
			align-items: center;
			font-size: 12px;
			font-weight: 760;
			line-height: 1.2;
			letter-spacing: -0.01em;
		}
		.ledgix-iir-lot-status-text.open,
		.ledgix-iir-cycle-status.purchase,
		.ledgix-iir-number.positive { color: #047857; }
		.ledgix-iir-cycle-status.sale,
		.ledgix-iir-cycle-status.return,
		.ledgix-iir-cycle-status.returned,
		.ledgix-iir-cycle-status.cancel,
		.ledgix-iir-number.negative { color: #b91c1c; }
		.ledgix-iir-cycle-status.partial-return,
		.ledgix-iir-number.warning { color: #b45309; }
		.ledgix-iir-lot-status-text.closed { color: #374151; }
		.ledgix-iir-lot-status-text.neutral,
		.ledgix-iir-cycle-status.neutral,
		.ledgix-iir-number.neutral,
		.ledgix-iir-number.muted { color: #94a3b8; }
		.ledgix-iir-backend-check {
			display: inline-flex;
			align-items: center;
			padding: 3px 7px;
			border-radius: 8px;
			background: rgba(220, 38, 38, 0.10);
			color: #b91c1c;
			font-size: 11px;
			font-weight: 800;
		}

		.query-report[data-report-name="Inventory Intelligence Report"] .dt-header .dt-cell {
			position: sticky;
			top: 0;
			z-index: 3;
			background: #f8fafc !important;
			font-weight: 760;
			color: #334155;
		}
		

	
		.dt-row.ledgix-iir-child-row .dt-cell { background: #ffffff !important; }
		.dt-row.ledgix-iir-child-row:nth-child(even) .dt-cell { background: #f8fafc !important; }
		.dt-row.ledgix-iir-child-row:hover .dt-cell { background: #f1f5f9 !important; }
		.dt-row.ledgix-iir-same-lot-row .dt-cell { box-shadow: inset 3px 0 0 rgba(37, 99, 235, 0.38); }
		.dt-row.ledgix-iir-selected-row .dt-cell {
			background: rgba(37, 99, 235, 0.10) !important;
			box-shadow: inset 3px 0 0 #2563eb;
		}
		.dt-row.ledgix-iir-mother-row.ledgix-iir-selected-row .dt-cell {
			background: #0f172a !important;
			box-shadow: inset 3px 0 0 #60a5fa;
		}

		@media (max-width: 1200px) {
			.ledgix-iir-card-grid { grid-template-columns: repeat(3, minmax(130px, 1fr)); }
		}
		@media (max-width: 720px) {
			.ledgix-iir-card-grid { grid-template-columns: repeat(2, minmax(130px, 1fr)); }
			.ledgix-iir-health { align-items: flex-start; flex-direction: column; }
		}
	`;
	document.head.appendChild(style);
}

function cssEscape(value) {
	if (window.CSS && CSS.escape) return CSS.escape(value);
	return String(value).replace(/"/g, '\\"');
}
