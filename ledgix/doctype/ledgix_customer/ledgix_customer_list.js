frappe.listview_settings["Ledgix Customer"] = {
	hide_name_filter: true,
	hide_name_column: true,
	add_fields: ["is_active"],
	get_indicator(doc) {
		if (doc.is_active) {
			return [__("Active"), "green", "is_active,=,1"];
		}
		return [__("Inactive"), "gray", "is_active,=,0"];
	},
};
