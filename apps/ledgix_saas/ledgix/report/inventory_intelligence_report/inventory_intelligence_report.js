frappe.query_reports["Inventory Intelligence Report"] = {
    filters: [
        { fieldname: "item", label: __("Item"), fieldtype: "Link", options: "Item", reqd: 1 },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.add_months(frappe.datetime.get_today(), -1) },
        { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
        { fieldname: "tracking_type", label: __("Tracking"), fieldtype: "Select", options: "All\nNormal Stock\nLot Based\nSerial Based", default: "All" }
    ]
};
