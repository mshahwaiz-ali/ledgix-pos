// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ledgix Sales Return", {

    setup: function(frm) {
        frm.set_query("original_sale", function() {
            return {
                filters: {
                    docstatus: 1
                }
            };
        });
    },

    original_sale: function(frm) {

        if (!frm.doc.original_sale) return;

        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Ledgix Sale",
                name: frm.doc.original_sale
            },
            callback: function(r) {

                if (!r.message) return;

                let sale = r.message;

                frm.clear_table("items");

                frm.set_value("customer", sale.customer);

                sale.items.forEach(function(item) {

                    let row = frm.add_child("items");

                    row.item = item.item;
                    row.quantity = item.quantity;

                    row.rate = item.rate;
                    row.amount = item.amount;

                    row.cost_price = item.cost_price;
                    row.profit_per_unit = item.profit_per_unit;
                    row.item_total_profit = item.item_total_profit;
                });

                frm.refresh_field("items");
            }
        });
    }
});