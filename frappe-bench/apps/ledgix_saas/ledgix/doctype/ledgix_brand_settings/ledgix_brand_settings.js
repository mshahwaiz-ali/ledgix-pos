// Copyright (c) 2026, Ledgix and contributors
// License: MIT

frappe.ui.form.on("Ledgix Brand Settings", {
	refresh(frm) {
		frm.set_intro(
			"Brand color and logo assets drive Ledgix-owned surfaces such as POS, custom workflow pages, Desk branding, login and favicon. Empty logo fields use the bundled Ledgix identity.",
			"blue"
		);
	},

	after_save() {
		if (!window.LedgixBrand?.refresh) return;

		window.LedgixBrand.refresh()
			.then(() => {
				frappe.show_alert({ message: __("Ledgix branding applied"), indicator: "green" }, 4);
			})
			.catch(() => {
				frappe.show_alert({ message: __("Brand saved. Reload to refresh branding."), indicator: "orange" }, 5);
			});
	},
});
