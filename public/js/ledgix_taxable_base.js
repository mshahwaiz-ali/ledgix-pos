// ERPNext-native taxable-base mirror for Ledgix FBR special tax treatment.
// Server calculation is authoritative; this mirrors an already-stamped line base.

frappe.provide("erpnext.taxable_base_resolvers");

erpnext.taxable_base_resolvers["On Notified Retail Price"] = function (calc, item, tax) {
	if (item.custom_ledgix_fbr_tax_basis !== "Notified Retail Price") {
		return flt(item.net_amount);
	}

	const notified = flt(item.custom_ledgix_fbr_notified_retail_price);
	if (notified <= 0) {
		frappe.throw(__("Third Schedule row is missing its stamped Notified Retail Price."));
	}

	return notified * flt(item.qty);
};
