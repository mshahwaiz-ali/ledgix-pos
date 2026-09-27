frappe.pages['fbr-v1-center'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({parent: wrapper, title: __('Federal FBR POS / IMS V1'), single_column: true});
    const body = $('<div class="fbr-v1-center p-4"></div>').appendTo(page.main);
    const esc = frappe.utils.escape_html;
    const company = page.add_field({fieldname: 'company', label: __('Company'), fieldtype: 'Link', options: 'Company', change: refresh});
    let busy = false;
    async function refresh() {
        if (busy) return;
        busy = true;
        try {
            const {message: data} = await frappe.call({method: 'fbr_v1.api.center.get_center_boot', args: {company: company.get_value()}});
            if (!company.get_value()) company.set_value(data.company);
            body.empty();
            $('<h3>').text(__('Overview')).appendTo(body);
            $('<p>').text(`${data.company} · ${data.readiness.mode}`).appendTo(body);
            $('<p class="text-muted">').text(__('Network cutover is disabled. Production QR verification and digital-signature contracts remain unresolved.')).appendTo(body);
            const links = [
                ['Integration Profiles', 'Ledgix FBR Integration Profile'], ['POS Devices', 'Ledgix FBR POS Device'],
                ['Item Mappings', 'Ledgix FBR Item Mapping'], ['Tax Component Mappings', 'Ledgix FBR Tax Component Mapping'],
                ['Payment Mapping', 'Mode of Payment'], ['Submission Logs', 'Ledgix FBR Submission Log'],
                ['Offline / Fiscal Events', 'Ledgix FBR Fiscal Event Log'], ['Fiscal Closings', 'Ledgix FBR Fiscal Closing']
            ];
            const controls = $('<div class="mb-4">').appendTo(body);
            links.forEach(([label, doctype]) => $('<button class="btn btn-default mr-2 mb-2">').text(__(label)).on('click', () => frappe.set_route('List', doctype)).appendTo(controls));
            $('<button class="btn btn-default mr-2">').text(__('Reconciliation')).on('click', () => frappe.set_route('List', 'Ledgix FBR Submission Log', {fbr_status: 'Reconciliation Required'})).appendTo(controls);
            $('<button class="btn btn-primary">').text(__('Invoice Readiness')).on('click', () => {
                const d = new frappe.ui.Dialog({title: __('Invoice Readiness'), fields: [
                    {fieldname: 'reference_doctype', label: __('Invoice Type'), fieldtype: 'Select', options: 'Sales Invoice\nPOS Invoice', reqd: 1},
                    {fieldname: 'reference_name', label: __('Invoice'), fieldtype: 'Dynamic Link', options: 'reference_doctype', reqd: 1}
                ], primary_action_label: __('Check'), primary_action: async values => {
                    const {message: r} = await frappe.call({method: 'fbr_v1.api.fiscalization.invoice_readiness', args: values});
                    frappe.msgprint({title: __('Readiness'), message: [...r.errors, ...r.network_blockers].map(esc).join('<br>') || __('Internal prerequisites ready')});
                    d.hide();
                }}); d.show();
            }).appendTo(controls);
            function actionDialog(title, fields, method, resultText) {
                const dialog = new frappe.ui.Dialog({title: __(title), fields,
                    primary_action_label: __(title), primary_action: async values => {
                        const {message: result} = await frappe.call({method, args: values});
                        frappe.msgprint(esc(resultText(result))); dialog.hide(); refresh();
                    }}); dialog.show();
            }
            $('<button class="btn btn-default mr-2">').text(__('Record Device Event')).on('click', () => actionDialog(
                'Record Device Event', [
                    {fieldname: 'pos_device', label: __('POS Device'), fieldtype: 'Link', options: 'Ledgix FBR POS Device', reqd: 1},
                    {fieldname: 'event_type', label: __('Event'), fieldtype: 'Select', options: 'Startup\nShutdown\nConnectivity Failure\nSoftware Failure\nPower Failure\nRestoration', reqd: 1}
                ], 'fbr_v1.api.fbr_offline.record_device_event', r => __('Event recorded: ') + r.event
            )).appendTo(controls);
            $('<button class="btn btn-default mr-2">').text(__('Generate Internal Closing')).on('click', () => actionDialog(
                'Generate Internal Closing', [
                    {fieldname: 'pos_device', label: __('POS Device'), fieldtype: 'Link', options: 'Ledgix FBR POS Device', reqd: 1},
                    {fieldname: 'period_type', label: __('Period'), fieldtype: 'Select', options: 'Daily\nWeekly\nMonthly', reqd: 1},
                    {fieldname: 'date', label: __('Date in completed period'), fieldtype: 'Date', reqd: 1}
                ], 'fbr_v1.services.fiscal_closing.generate_closing', r => __('Internal closing: ') + r.name
            )).appendTo(controls);
            $('<button class="btn btn-default mr-2">').text(__('Fiscalize Invoice')).on('click', () => actionDialog(
                'Fiscalize Invoice', [
                    {fieldname: 'reference_doctype', label: __('Invoice Type'), fieldtype: 'Select', options: 'Sales Invoice\nPOS Invoice', reqd: 1},
                    {fieldname: 'reference_name', label: __('Invoice'), fieldtype: 'Dynamic Link', options: 'reference_doctype', reqd: 1}
                ], 'fbr_v1.api.fiscalization.submit_invoice', r => [r.status, ...(r.errors || [])].join(' · ')
            )).appendTo(controls);
            $('<h4>').text(__('POS Devices')).appendTo(body);
            data.devices.forEach(device => $('<p>').text(`${device.display_label || device.name} · POSID ${device.pos_id || '—'} · ${device.environment} · ${device.operational_state}`).appendTo(body));
        } finally { busy = false; }
    }
    refresh();
};
