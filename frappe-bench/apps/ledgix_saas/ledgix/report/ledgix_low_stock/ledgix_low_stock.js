frappe.query_reports["Ledgix Low Stock"] = {
    filters: [
        { fieldname: "category", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
        { fieldname: "risk_status", label: __("Risk Status"), fieldtype: "Select", options: "\nOut of Stock\nLow Stock\nAt Minimum" }
    ]
};
