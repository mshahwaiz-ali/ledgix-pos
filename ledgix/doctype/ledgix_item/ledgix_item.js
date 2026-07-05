// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ledgix Item", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.set_df_property("current_stock", "read_only", 1);
		}
	},

	before_save(frm) {
		const stock_in = flt(frm.doc.stock_in_qty);
		const stock_out = flt(frm.doc.stock_out_qty);
		if (stock_in > 0 && stock_out > 0) {
			frappe.throw(__("Enter either Add Stock or Remove Stock, not both."));
		}
	},

	async after_save(frm) {
		const stock_in = flt(frm.doc.stock_in_qty);
		const stock_out = flt(frm.doc.stock_out_qty);
		if (!stock_in && !stock_out) {
			return;
		}

		try {
			await frappe.call({
				method: "ledgix_saas.api.stock_ops.manual_stock_entry",
				args: {
					item: frm.doc.name,
					qty_in: stock_in,
					qty_out: stock_out,
					serial_numbers: frm.doc.stock_serial_numbers,
				},
			});
			frm.set_value("stock_in_qty", 0);
			frm.set_value("stock_out_qty", 0);
			frm.set_value("stock_serial_numbers", "");
			await frm.reload_doc();
			frappe.show_alert({ message: __("Stock updated"), indicator: "green" });
		} catch (error) {
			frappe.msgprint({
				title: __("Stock update failed"),
				message: error.message || String(error),
				indicator: "red",
			});
		}
	},
});
