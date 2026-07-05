// Copyright (c) 2026, Ledgix and contributors
// License: MIT

frappe.ui.form.on("Ledgix Brand Settings", {
	refresh(frm) {
		frm.set_intro(
			"Upload symbol and full logos here once. Login page, desk header, navigator, and favicon update automatically.",
			"blue"
		);
	},
});
