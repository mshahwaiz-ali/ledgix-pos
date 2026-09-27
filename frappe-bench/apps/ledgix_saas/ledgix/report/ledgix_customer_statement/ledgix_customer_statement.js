frappe.query_reports["Ledgix Customer Statement"] = {
    filters: [
        { fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer", reqd: 1 },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
        { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 }
    ]
};
