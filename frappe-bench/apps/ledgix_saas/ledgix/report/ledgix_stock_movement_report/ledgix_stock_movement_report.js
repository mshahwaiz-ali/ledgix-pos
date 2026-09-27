frappe.query_reports["Ledgix Stock Movement Report"] = {
    filters: [
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start() },
        { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
        { fieldname: "item", label: __("Item"), fieldtype: "Link", options: "Item" },
        { fieldname: "warehouse", label: __("Warehouse"), fieldtype: "Link", options: "Warehouse" },
        { fieldname: "movement_type", label: __("Flow"), fieldtype: "Select", options: "\nIN\nOUT\nADJUSTMENT" },
        { fieldname: "reference_doctype", label: __("Reference Type"), fieldtype: "Link", options: "DocType" },
        { fieldname: "reference_name", label: __("Reference"), fieldtype: "Data" }
    ]
};
