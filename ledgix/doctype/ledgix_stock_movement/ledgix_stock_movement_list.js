/* global frappe, __ */

frappe.listview_settings["Ledgix Stock Movement"] = {
	formatters: {
		movement_type(value) {
			const movement = String(value || "").toUpperCase();
			const color = {
				IN: "green",
				OUT: "red",
				ADJUSTMENT: "orange",
			}[movement] || "gray";
			const label = frappe.utils.escape_html(__(movement || "—"));
			return `<span class="indicator-pill ${color}">${label}</span>`;
		},

		movement_date(value) {
			if (!value) return "";
			const date = String(value).trim().split(" ")[0];
			return frappe.datetime.str_to_user(date);
		},
	},
};
