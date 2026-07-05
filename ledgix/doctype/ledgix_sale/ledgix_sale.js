// Copyright (c) 2026, Ali and contributors
// For license information, please see license.txt

// ============================================================
// LEDGIX SALE FORM
// ============================================================

frappe.ui.form.on("Ledgix Sale", {
    refresh: function(frm) {

        if (frm.is_new() && !frm.doc.customer) {
            frm.set_value("customer", "Walk-in Customer");
        }

        if (frm.is_new() && !frm.doc.sale_date) {
            frm.set_value("sale_date", frappe.datetime.now_datetime());
        }

        load_active_shift(frm);
        add_default_cash_payment(frm);
        add_default_item_row(frm);

        if (frm.is_new()) {
            calculate_sale_totals(frm);
            calculate_payment_totals(frm);
        }
    },

    items_add: function(frm) {
        calculate_sale_totals(frm);
        calculate_payment_totals(frm);
    },

    items_remove: function(frm) {
        calculate_sale_totals(frm);
        calculate_payment_totals(frm);
    },

    payments_add: function(frm) {
        calculate_payment_totals(frm);
    },

    payments_remove: function(frm) {
        calculate_payment_totals(frm);
    }
});


// ============================================================
// ACTIVE SHIFT BANNER
// ============================================================

function load_active_shift(frm) {
    frappe.call({
        method: "ledgix_saas.api.api.get_active_shift_info",
        callback: function(r) {
            if (!r.message || !r.message.has_active_shift) {
                render_active_shift_banner(frm, null);

                if (frm.is_new()) {
                    frm.set_value("pos_shift", "");
                }

                return;
            }

            let shift = r.message;

            if (frm.is_new()) {
                frm.set_value("pos_shift", shift.shift_id);
            }

            render_active_shift_banner(frm, shift);
        }
    });
}


function render_active_shift_banner(frm, shift) {
    $(".ledgix-active-shift-banner").remove();

    let html = "";

    if (!shift) {
        html = `
            <div class="ledgix-active-shift-banner ledgix-shift-danger">
                <div>
                    <div class="ledgix-shift-title">No Active Shift</div>
                    <div class="ledgix-shift-subtitle">Open a POS shift before creating sales.</div>
                </div>
            </div>
        `;
    } else {
        html = `
            <div class="ledgix-active-shift-banner">
                <div>
                    <div class="ledgix-shift-title">Active Shift: ${shift.shift_id}</div>
                    <div class="ledgix-shift-subtitle">
                        Opening Cash: ${format_currency(shift.opening_cash)}
                        &nbsp;•&nbsp;
                        Expected Cash: ${format_currency(shift.expected_cash)}
                    </div>
                </div>
            </div>
        `;
    }

    $(frm.fields_dict.customer.wrapper)
    .closest(".form-section")
    .before(html);

    inject_active_shift_banner_css();
}


function inject_active_shift_banner_css() {
    if ($("#ledgix-active-shift-banner-css").length) {
        return;
    }

    $("head").append(`
        <style id="ledgix-active-shift-banner-css">
            .ledgix-active-shift-banner {
                margin: 0 0 16px 0;
                padding: 14px 18px;
                border-radius: 14px;
                background: linear-gradient(135deg, #111827, #1f2937);
                color: #ffffff;
                box-shadow: 0 10px 28px rgba(15, 23, 42, 0.16);
                border: 1px solid rgba(255, 255, 255, 0.08);
            }

            .ledgix-active-shift-banner.ledgix-shift-danger {
                background: linear-gradient(135deg, #7f1d1d, #991b1b);
            }

            .ledgix-shift-title {
                font-size: 14px;
                font-weight: 700;
                letter-spacing: 0.2px;
            }

            .ledgix-shift-subtitle {
                margin-top: 4px;
                font-size: 13px;
                opacity: 0.88;
            }
        </style>
    `);
}

// ============================================================
// DEFAULT ITEM ROW
// ============================================================

function add_default_item_row(frm) {
    if (!frm.is_new()) {
        return;
    }

    if ((frm.doc.items || []).length > 0) {
        return;
    }

    frm.add_child("items");
    frm.refresh_field("items");
}


// ============================================================
// DEFAULT CASH PAYMENT ROW
// ============================================================

function add_default_cash_payment(frm) {
    if (!frm.is_new()) {
        return;
    }

    if ((frm.doc.payments || []).length > 0) {
        return;
    }

    let row = frm.add_child("payments");
    row.payment_method = "Cash";
    row.is_cash_payment = 1;
    row.amount = 0;

    frm.refresh_field("payments");
    calculate_payment_totals(frm);
}


// ============================================================
// SALE ITEM CALCULATIONS
// ============================================================

frappe.ui.form.on("Ledgix Sale Item", {
    item: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.item) {
            frappe.db.get_value(
                "Ledgix Item",
                row.item,
                ["selling_price", "cost_price"]
            ).then(r => {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, "rate", r.message.selling_price || 0);
                    frappe.model.set_value(cdt, cdn, "cost_price", r.message.cost_price || 0);
                    calculate_sale_item(frm, cdt, cdn);
                }
            });
        }
    },

    quantity: function(frm, cdt, cdn) {
        calculate_sale_item(frm, cdt, cdn);
    },

    rate: function(frm, cdt, cdn) {
        calculate_sale_item(frm, cdt, cdn);
    },

    cost_price: function(frm, cdt, cdn) {
        calculate_sale_item(frm, cdt, cdn);
    }
});


// ============================================================
// PAYMENT CALCULATIONS
// ============================================================

frappe.ui.form.on("Ledgix Sale Payment", {
    payment_method: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        let is_cash_payment = 0;

        if (row.payment_method === "Cash") {
            is_cash_payment = 1;
        }

        frappe.model.set_value(cdt, cdn, "is_cash_payment", is_cash_payment);

        calculate_payment_totals(frm);
    },

    amount: function(frm) {
        calculate_payment_totals(frm);
    }
});


// ============================================================
// ITEM TOTALS
// ============================================================

function calculate_sale_item(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    let quantity = row.quantity || 0;
    let rate = row.rate || 0;
    let cost_price = row.cost_price || 0;

    let amount = quantity * rate;
    let profit_per_unit = rate - cost_price;
    let item_total_profit = profit_per_unit * quantity;

    frappe.model.set_value(cdt, cdn, "amount", amount);
    frappe.model.set_value(cdt, cdn, "profit_per_unit", profit_per_unit);
    frappe.model.set_value(cdt, cdn, "item_total_profit", item_total_profit);

    calculate_sale_totals(frm);
    calculate_payment_totals(frm);
}


function calculate_sale_totals(frm) {
    let total_amount = 0;
    let total_profit = 0;

    (frm.doc.items || []).forEach(row => {
        total_amount += row.amount || 0;
        total_profit += row.item_total_profit || 0;
    });

    frm.set_value("total_amount", total_amount);
    frm.set_value("total_profit", total_profit);

    update_sale_tax_preview(frm);
}   


// ============================================================
// PAYMENT TOTALS
// ============================================================

function calculate_payment_totals(frm) {
    let total_amount = frm.doc.grand_total || frm.doc.total_amount || 0;
    let paid_amount = 0;

    (frm.doc.payments || []).forEach(row => {
        paid_amount += row.amount || 0;
    });

    let remaining_amount = 0;
    let change_amount = 0;
    let payment_status = "Unpaid";

    if (paid_amount >= total_amount) {
        remaining_amount = 0;
        change_amount = paid_amount - total_amount;

        if (total_amount > 0) {
            payment_status = "Paid";
        }

    } else if (paid_amount > 0) {
        remaining_amount = total_amount - paid_amount;
        change_amount = 0;
        payment_status = "Partial";

    } else {
        remaining_amount = total_amount;
        change_amount = 0;
        payment_status = "Unpaid";
    }

    frm.set_value("paid_amount", paid_amount);
    frm.set_value("remaining_amount", remaining_amount);
    frm.set_value("change_amount", change_amount);
    frm.set_value("payment_status", payment_status);
}


// ============================================================
// SALE TAX PREVIEW
// ============================================================

function update_sale_tax_preview(frm) {
    let items = [];

    (frm.doc.items || []).forEach(row => {
        if (!row.item || !row.quantity) {
            return;
        }

        let quantity = row.quantity || 0;
        let rate = row.rate || 0;
        let amount = row.amount || (quantity * rate);

        items.push({
            item: row.item,
            quantity: quantity,
            rate: rate,
            amount: amount
        });
    });

    if (!items.length) {
        frm.set_value("tax_amount", 0);
        frm.set_value("grand_total", frm.doc.total_amount || 0);

        if (frm.fields_dict.tax_details) {
            frm.clear_table("tax_details");
            frm.refresh_field("tax_details");
        }

        calculate_payment_totals(frm);
        return;
    }

    frappe.call({
        method: "ledgix_saas.api.taxation.preview_sale_tax_for_form",
        args: {
            items: items,
            posting_date: frm.doc.sale_date
        },
        callback: function(r) {
            if (!r.message) {
                calculate_payment_totals(frm);
                return;
            }

            frm.set_value("tax_amount", r.message.tax_amount || 0);
            frm.set_value("grand_total", r.message.grand_total || frm.doc.total_amount || 0);

            if (frm.fields_dict.tax_details) {
                frm.clear_table("tax_details");

                (r.message.tax_details || []).forEach(tax_row => {
                    let row = frm.add_child("tax_details");

                    row.item = tax_row.item;
                    row.qty = tax_row.qty;
                    row.tax_category = tax_row.tax_category;
                    row.taxable_amount = tax_row.taxable_amount;
                    row.tax_rate = tax_row.tax_rate;
                    row.tax_amount = tax_row.tax_amount;
                    row.net_amount = tax_row.net_amount;
                    row.hs_code = tax_row.hs_code;
                    row.uom_for_fbr = tax_row.uom_for_fbr;
                    row.sales_type = tax_row.sales_type;
                    row.scenario_id = tax_row.scenario_id;
                    row.sro_schedule_number = tax_row.sro_schedule_number;
                    row.sro_item_serial_number = tax_row.sro_item_serial_number;
                });

                frm.refresh_field("tax_details");
            }

            calculate_payment_totals(frm);
        }
    });
}