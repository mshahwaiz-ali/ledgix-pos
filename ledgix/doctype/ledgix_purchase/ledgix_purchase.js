// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Ledgix Purchase", {
// 	refresh(frm) {

// 	},
// });


frappe.ui.form.on("Ledgix Purchase", {
	refresh(frm) {
		if (frm.is_new() && (!frm.doc.items || frm.doc.items.length === 0)) {
			frm.add_child("items");
			frm.refresh_field("items");
		}
	}
});


