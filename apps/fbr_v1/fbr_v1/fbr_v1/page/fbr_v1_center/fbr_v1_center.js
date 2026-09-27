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
            const readiness = data.readiness;
            const states = [
                ['Source/accounting setup', readiness.source_accounting_ready],
                ['FBR V1 setup', readiness.setup_ready],
                ['Sandbox configuration', readiness.sandbox_configuration_ready],
                ['Production configuration', readiness.production_configuration_ready],
                ['General network cutover', readiness.network_cutover_active],
                ['Production network cutover', readiness.production_cutover_active]
            ];
            states.forEach(([label, ready]) => $('<p>').text(`${__(label)}: ${ready ? __('Ready / enabled') : __('Not ready / disabled')}`).appendTo(body));
            $('<p class="text-muted">').text(__('Each invoice requires its own immutable-snapshot, payment and accounting reconciliation checks. Internal closings do not imply FBR acceptance.')).appendTo(body);
            [...new Set([...(readiness.setup_blockers || []), ...(readiness.blockers || [])])].forEach(message => $('<p class="text-warning">').text(message).appendTo(body));
            const contracts = $('<details class="mb-3">').appendTo(body);
            $('<summary>').text(__('Unresolved external machine contracts')).appendTo(contracts);
            readiness.unresolved_contracts.forEach(message => $('<p>').text(message).appendTo(contracts));
            const links = [
                ['Integration Profiles', 'Ledgix FBR Integration Profile'], ['POS Devices', 'Ledgix FBR POS Device'],
                ['Item Mappings', 'Ledgix FBR Item Mapping'], ['Tax Component Mappings', 'Ledgix FBR Tax Component Mapping'],
                ['Payment Mapping', 'Mode of Payment'], ['Submission Logs', 'Ledgix FBR Submission Log'],
                ['Offline / Fiscal Events', 'Ledgix FBR Fiscal Event Log'], ['Fiscal Closings', 'Ledgix FBR Fiscal Closing'],
                ['Correction Requests', 'Ledgix FBR Correction Request'], ['Sales Invoice', 'Sales Invoice'], ['POS Invoice', 'POS Invoice']
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
            const invoiceFields = () => [
                {fieldname: 'reference_doctype', label: __('Invoice Type'), fieldtype: 'Select', options: 'Sales Invoice\nPOS Invoice', reqd: 1},
                {fieldname: 'reference_name', label: __('Invoice'), fieldtype: 'Dynamic Link', options: 'reference_doctype', reqd: 1}
            ];
            const externalFields = () => [
                {fieldname: 'external_reference', label: __('Authoritative External Reference'), fieldtype: 'Data', reqd: 1},
                {fieldname: 'external_evidence', label: __('External Evidence'), fieldtype: 'Attach', reqd: 1}
            ];
            const deviceField = () => ({fieldname: 'pos_device', label: __('POS Device'), fieldtype: 'Link', options: 'Ledgix FBR POS Device', reqd: 1});
            function addAction(title, fields, method, resultText) {
                $('<button class="btn btn-default mr-2 mb-2">').text(__(title)).on('click', () =>
                    actionDialog(title, fields(), method, resultText)).appendTo(controls);
            }
            addAction('Record External Compliance Evidence', () => [deviceField(),
                {fieldname: 'event_type', label: __('Event'), fieldtype: 'Select', options: 'Outage Report Filed\nAlert Report Filed\nOffline Upload Confirmed\nCorrection Filed\nCommissioner Approval Recorded', reqd: 1},
                ...externalFields(), ...invoiceFields().map(f => ({...f, reqd: 0, ...(f.fieldname === 'reference_doctype' ? {options: '\nSales Invoice\nPOS Invoice'} : {})})),
                {fieldname: 'occurred_at', label: __('External Event Time'), fieldtype: 'Datetime'}
            ], 'fbr_v1.api.compliance_evidence.record_external_compliance_evidence', r => __('Evidence recorded; invoice unchanged: ') + r.event);
            addAction('Record Offline Upload Confirmation', () => [...invoiceFields(), ...externalFields(),
                {fieldname: 'fbr_invoice_number', label: __('Official FBR Invoice Number'), fieldtype: 'Data', reqd: 1}
            ], 'fbr_v1.api.fbr_offline.record_offline_upload_confirmation', r => `${r.status} · ${r.confirmed_after_deadline ? __('Recorded after deadline') : __('Recorded within deadline')}`);
            addAction('Create Correction Request', () => [...invoiceFields(),
                {fieldname: 'action_type', label: __('Action'), fieldtype: 'Select', options: 'Cancel\nDelete\nEdit', reqd: 1},
                {fieldname: 'reason', label: __('Bona-fide Reason'), fieldtype: 'Small Text', reqd: 1},
                {fieldname: 'fbr_generated_at', label: __('Authoritative FBR Generation Time'), fieldtype: 'Datetime', description: __('Required with reference and evidence if the source has no official generation time.')},
                {fieldname: 'generation_time_reference', label: __('Generation Time Authority Reference'), fieldtype: 'Data'},
                {fieldname: 'generation_time_evidence', label: __('Generation Time Evidence'), fieldtype: 'Attach'}
            ], 'fbr_v1.api.corrections.request_correction', r => `${r.name} · ${r.status}`);
            addAction('Record Correction Result', () => [
                {fieldname: 'correction_request', label: __('Correction Request'), fieldtype: 'Link', options: 'Ledgix FBR Correction Request', reqd: 1},
                {fieldname: 'status', label: __('Externally Confirmed Result'), fieldtype: 'Select', options: 'Completed\nRejected', reqd: 1},
                {fieldname: 'board_reference', label: __('Board / PRAL Reference'), fieldtype: 'Data', reqd: 1},
                {fieldname: 'external_evidence', label: __('External Evidence'), fieldtype: 'Attach', reqd: 1},
                {fieldname: 'commissioner_approval_reference', label: __('Commissioner Approval Reference'), fieldtype: 'Data', description: __('Required for completion after the 72-hour deadline.')}
            ], 'fbr_v1.api.corrections.record_correction_result', r => `${r.name} · ${r.status}`);
            addAction('Test Local IMS Health', () => [deviceField()], 'fbr_v1.api.center.test_local_ims_health',
                r => r.ok ? __('Local IMS health check succeeded') : (r.error || __('Local IMS health check failed')));
            $('<h4>').text(__('POS Devices')).appendTo(body);
            data.devices.forEach(device => $('<p>').text(`${device.display_label || device.name} · POSID ${device.pos_id || '—'} · ${device.environment} · ${device.operational_state}`).appendTo(body));
        } finally { busy = false; }
    }
    refresh();
};
