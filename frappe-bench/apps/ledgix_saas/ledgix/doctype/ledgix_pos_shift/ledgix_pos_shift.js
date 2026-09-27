// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

// ============================================================
// LEDGIX POS SHIFT FORM
// ============================================================

frappe.ui.form.on("Ledgix POS Shift", {
	refresh: function(frm) {

		if (frm.is_new()) {
			frm.set_intro("Enter opening cash, then save. Submit when closing the shift.", "blue");
		}

		if (!frm.is_new() && frm.doc.status === "Open") {
			frm.set_intro("Shift is open. Enter actual cash before submitting to close.", "orange");
		}

		if (frm.doc.status === "Closed") {
			frm.set_intro("Shift is closed. Cash variance is final.", "green");
		}
	},

	actual_cash: function(frm) {
		calculate_cash_variance(frm);
	},

	expected_cash: function(frm) {
		calculate_cash_variance(frm);
	}
});

function calculate_cash_variance(frm) {
	let expected_cash = frm.doc.expected_cash || 0;
	let actual_cash = frm.doc.actual_cash || 0;

	frm.set_value("cash_variance", actual_cash - expected_cash);
}