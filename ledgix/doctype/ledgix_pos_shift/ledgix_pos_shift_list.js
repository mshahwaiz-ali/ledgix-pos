frappe.listview_settings["Ledgix POS Shift"] = {
	hide_name_filter: true,
	add_fields: ["status"],
	has_indicator_for_draft: true,
	has_indicator_for_cancelled: true,
	get_indicator(doc) {
		if (doc.docstatus === 2 || doc.status === "Cancelled") {
			return [__("Cancelled"), "red", "status,=,Cancelled"];
		}
		if (doc.status === "Closed") {
			return [__("Closed"), "green", "status,=,Closed"];
		}
		return [__("Open"), "orange", "status,=,Open"];
	},
};
