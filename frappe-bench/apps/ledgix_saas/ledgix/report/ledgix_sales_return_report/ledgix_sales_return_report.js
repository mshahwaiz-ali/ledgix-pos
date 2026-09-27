frappe.query_reports["Ledgix Sales Return Report"] = {
    filters: [
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
        { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
        { fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
        { fieldname: "docstatus", label: __("Status"), fieldtype: "Select", options: "\nSubmitted\nDraft\nCancelled", default: "Submitted" }
    ]
};
