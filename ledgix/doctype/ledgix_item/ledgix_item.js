// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ledgix Item", {
	refresh(frm) {
		const existing = !frm.is_new();
		frm.set_df_property("current_stock", "read_only", 1);
		frm.set_df_property("opening_stock", "read_only", existing ? 1 : 0);
		frm.set_df_property("cost_price", "read_only", existing ? 1 : 0);

		if (existing && can_adjust_stock()) {
			frm.add_custom_button(__("Adjust Stock"), () => show_stock_adjustment_dialog(frm), __("Inventory"));
			frm.add_custom_button(__("Stock Movements"), () => {
				frappe.set_route("List", "Ledgix Stock Movement", "List", { item: frm.doc.name });
			}, __("Inventory"));
		}
	},
});

function can_adjust_stock() {
	const roles = new Set(frappe.user_roles || []);
	return ["System Manager", "Ledgix Admin", "Ledgix Manager"].some(role => roles.has(role));
}

function show_stock_adjustment_dialog(frm) {
	const serial_based = frm.doc.tracking_type === "Serial Based";
	const action_options = serial_based ? "Add Stock" : "Add Stock\nRemove Stock";
	const dialog = new frappe.ui.Dialog({
		title: __("Adjust Stock — {0}", [frm.doc.item_name || frm.doc.name]),
		fields: [
			{
				fieldname: "current_stock_info",
				fieldtype: "HTML",
				options: `<div class="text-muted small mb-3">${__("Current Stock")}: <strong>${frappe.utils.escape_html(String(frm.doc.current_stock || 0))}</strong></div>`,
			},
			{
				fieldname: "action",
				fieldtype: "Select",
				label: __("Action"),
				options: action_options,
				default: "Add Stock",
				reqd: 1,
			},
			{
				fieldname: "quantity",
				fieldtype: "Float",
				label: __("Quantity"),
				reqd: 1,
			},
			{
				fieldname: "serial_numbers",
				fieldtype: "Small Text",
				label: __("Serial Numbers"),
				description: __("For Serial Based stock-in: one serial per line or comma-separated. Leave blank to auto-generate."),
				depends_on: "eval:doc.action=='Add Stock'",
				hidden: serial_based ? 0 : 1,
			},
			{
				fieldname: "note",
				fieldtype: "Small Text",
				label: __("Reason / Note"),
				reqd: 1,
				description: __("Explain why this manual inventory adjustment is required."),
			},
		],
		primary_action_label: __("Post Adjustment"),
		primary_action: async values => {
			const quantity = flt(values.quantity);
			if (quantity <= 0) {
				frappe.msgprint(__("Quantity must be greater than zero."));
				return;
			}

			dialog.get_primary_btn().prop("disabled", true);
			try {
				const result = await frappe.call({
					method: "ledgix_saas.api.stock_ops.manual_stock_entry",
					args: {
						item: frm.doc.name,
						qty_in: values.action === "Add Stock" ? quantity : 0,
						qty_out: values.action === "Remove Stock" ? quantity : 0,
						serial_numbers: values.serial_numbers || "",
						note: values.note || "",
					},
				});
				dialog.hide();
				await frm.reload_doc();
				frappe.show_alert({
					message: __("Stock adjustment posted. Current stock: {0}", [result.message?.current_stock ?? frm.doc.current_stock]),
					indicator: "green",
				}, 5);
			} catch (error) {
				frappe.msgprint({
					title: __("Stock adjustment failed"),
					message: error?.message || error?.exc || String(error),
					indicator: "red",
				});
			} finally {
				dialog.get_primary_btn().prop("disabled", false);
			}
		},
	});
	dialog.show();
}
