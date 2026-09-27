frappe.query_reports["Ledgix Current Stock"] = {
    filters: [
        { fieldname: "item", label: __("Item"), fieldtype: "Link", options: "Item" },
        { fieldname: "category", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
        { fieldname: "stock_status", label: __("Stock Status"), fieldtype: "Select", options: "\nIn Stock\nLow Stock\nAt Minimum\nOut of Stock" }
    ]
};
