// ============================================================
// LEDGIX MAINTENANCE TOOL
// ============================================================

frappe.ui.form.on("Ledgix Maintenance Tool", {
    refresh(frm) {
        frm.disable_save();

        frm.set_intro(
            "Maintenance actions are protected. Take a backup, type RESET LEDGIX, enter your password, then run the required action.",
            "orange"
        );

        style_maintenance_buttons(frm);
    },

    numbering_reset(frm) {
        run_maintenance_action({
            frm,
            title: "Numbering Reset",
            indicator: "orange",
            warning: "This will reset Ledgix numbering counters only. Existing documents will not be deleted.",
            method: "ledgix_saas.api.maintenance.run_numbering_reset",
            freeze_message: "Running Numbering Reset...",
            success_title: "Numbering Reset Complete",
        });
    },

    transaction_reset(frm) {
        run_maintenance_action({
            frm,
            title: "Transaction Reset",
            indicator: "red",
            warning: "This will delete Ledgix transactions, stock movements, lots, serials, shifts, and held sales. Items, customers, suppliers, categories, theme settings, and mode settings will remain.",
            method: "ledgix_saas.api.maintenance.run_transaction_reset",
            freeze_message: "Running Transaction Reset...",
            success_title: "Transaction Reset Complete",
        });
    },

    prepare_fresh_tenant(frm) {
        run_maintenance_action({
            frm,
            title: "Prepare Fresh Tenant",
            indicator: "red",
            warning: "This will prepare the site for a new shop/customer by deleting transactions and business masters: items, categories, customers, suppliers, and Ledgix user profiles. Frappe users, roles, theme settings, and POS mode settings will remain.",
            method: "ledgix_saas.api.maintenance.run_prepare_fresh_tenant",
            freeze_message: "Preparing Fresh Tenant...",
            success_title: "Fresh Tenant Ready",
        });
    },
});


function style_maintenance_buttons(frm) {
    const numbering_btn = frm.fields_dict.numbering_reset?.$input;
    const transaction_btn = frm.fields_dict.transaction_reset?.$input;
    const fresh_tenant_btn = frm.fields_dict.prepare_fresh_tenant?.$input;

    if (numbering_btn) {
        numbering_btn
            .removeClass("btn-default")
            .addClass("btn-warning");
    }

    if (transaction_btn) {
        transaction_btn
            .removeClass("btn-default btn-secondary")
            .addClass("btn-danger");
    }

    if (fresh_tenant_btn) {
        fresh_tenant_btn
            .removeClass("btn-default btn-secondary")
            .addClass("btn-danger");
    }
}


function get_safety_args(frm) {
    return {
        backup_confirmed: frm.doc.backup_confirmed ? 1 : 0,
        confirmation_text: frm.doc.confirmation_text,
        admin_password: frm.doc.admin_password,
    };
}


function validate_safety_inputs(frm) {
    if (!frm.doc.backup_confirmed) {
        frappe.msgprint({
            title: "Backup Required",
            indicator: "orange",
            message: "Please confirm that a backup has been taken before running this action.",
        });
        return false;
    }

    if ((frm.doc.confirmation_text || "").trim() !== "RESET LEDGIX") {
        frappe.msgprint({
            title: "Confirmation Required",
            indicator: "orange",
            message: "Type RESET LEDGIX exactly in Confirmation Text.",
        });
        return false;
    }

    if (!frm.doc.admin_password) {
        frappe.msgprint({
            title: "Password Required",
            indicator: "orange",
            message: "Enter your current admin password before running this action.",
        });
        return false;
    }

    return true;
}


function run_maintenance_action({ frm, title, indicator, warning, method, freeze_message, success_title }) {
    if (!validate_safety_inputs(frm)) {
        return;
    }

    const message = `
        <div>
            <p><b>${frappe.utils.escape_html(title)}</b></p>
            <p>${frappe.utils.escape_html(warning)}</p>
            <p class="text-danger"><b>This action cannot be undone from the UI. Continue?</b></p>
        </div>
    `;

    frappe.confirm(message, () => {
        frappe.call({
            method,
            freeze: true,
            freeze_message,
            args: get_safety_args(frm),
            callback(r) {
                if (!r.exc && r.message) {
                    show_success_message(success_title, indicator === "red" ? "green" : "green", r.message);
                    frm.set_value("admin_password", "");
                }
            },
        });
    });
}


function show_success_message(title, indicator, data) {
    const restored = data.restored_series || [];
    const cleared = data.cleared || [];
    const masters_cleared = data.masters_cleared || [];
    const transaction_result = data.transaction_result || null;

    let html = `
        <div>
            <p>${frappe.utils.escape_html(data.message || "Done.")}</p>
            <p><b>Deleted series counters:</b> ${frappe.utils.escape_html(String(data.deleted_series_count || 0))}</p>
    `;

    if (cleared.length) {
        html += render_clear_summary("Cleared transaction tables", cleared);
    }

    if (transaction_result && transaction_result.cleared) {
        html += render_clear_summary("Cleared transaction tables", transaction_result.cleared);
    }

    if (masters_cleared.length) {
        html += render_clear_summary("Cleared master tables", masters_cleared);
    }

    if (restored.length) {
        html += render_restored_series(restored);
    }

    if (transaction_result && transaction_result.restored_series && transaction_result.restored_series.length) {
        html += render_restored_series(transaction_result.restored_series);
    }

    html += "</div>";

    frappe.msgprint({
        title,
        indicator,
        message: html,
    });
}


function render_clear_summary(title, rows) {
    const cleared = rows.filter(row => row.status === "cleared");
    const skipped = rows.filter(row => row.status === "skipped");

    let html = `<hr><p><b>${frappe.utils.escape_html(title)}:</b></p>`;

    if (cleared.length) {
        html += "<ul>";
        html += cleared.map(row => `
            <li>
                ${frappe.utils.escape_html(row.doctype)}:
                ${frappe.utils.escape_html(String(row.count || 0))} removed
            </li>
        `).join("");
        html += "</ul>";
    }

    if (skipped.length) {
        html += `<p class="text-muted">Skipped missing DocTypes: ${frappe.utils.escape_html(String(skipped.length))}</p>`;
    }

    return html;
}


function render_restored_series(restored) {
    return `
        <hr>
        <p><b>Protected existing records:</b></p>
        <ul>
            ${restored.map(row => `
                <li>
                    ${frappe.utils.escape_html(row.name)} kept at
                    ${frappe.utils.escape_html(String(row.current))}
                </li>
            `).join("")}
        </ul>
    `;
}
