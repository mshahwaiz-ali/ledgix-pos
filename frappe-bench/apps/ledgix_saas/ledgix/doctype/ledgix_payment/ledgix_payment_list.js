/* global frappe */

frappe.listview_settings["Ledgix Payment"] = {
	formatters: {
		payment_date(value) {
			if (!value) return "";
			const date = String(value).trim().split(" ")[0];
			return frappe.datetime.str_to_user(date);
		},
	},
};
