frappe.pages['fbr-v1-center'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('FBR V1 Center'),
        single_column: true,
    });
    const body = $('<div class="lx-fbr-v1-center"></div>').appendTo(page.main);
    const company = page.add_field({
        fieldname: 'company',
        label: __('Company'),
        fieldtype: 'Link',
        options: 'Company',
        change: refresh,
    });
    const iconUrl = '/assets/ledgix_saas/images/brand/fbr_v1.png';
    const canOperate = () => frappe.user.has_role('System Manager') || frappe.user.has_role('Accounts Manager');
    let busy = false;

    const uniq = (rows) => [...new Set((rows || []).filter(Boolean))];
    const without = (rows, excluded) => {
        const omit = new Set(excluded || []);
        return uniq(rows).filter((row) => !omit.has(row));
    };
    const yesNo = (value) => value ? __('ON') : __('OFF');
    const textOrDash = (value) => value || '—';

    function routeList(doctype, filters) {
        frappe.set_route('List', doctype, filters || {});
    }

    function makeButton(label, onClick, options = {}) {
        const button = $('<button type="button" class="btn btn-sm"></button>')
            .addClass(options.primary ? 'btn-primary' : 'btn-default')
            .text(__(label));
        if (options.danger) button.addClass('lx-fbr-danger-action');
        if (options.disabled) {
            button.prop('disabled', true);
            if (options.reason) button.attr('title', options.reason);
        } else {
            button.on('click', onClick);
        }
        return button;
    }

    function badge(label, tone = 'neutral') {
        return $('<span class="lx-fbr-status-badge"></span>')
            .addClass(`is-${tone}`)
            .text(__(label));
    }

    function overallState(readiness, profile) {
        if (!readiness.enabled || readiness.mode === 'Disabled') return ['Disabled', 'neutral'];
        if (readiness.mode === 'Paused') return ['Paused', 'warning'];
        if (!readiness.source_accounting_ready || !readiness.setup_ready) return ['Setup Required', 'warning'];
        if (readiness.mode === 'Sandbox') {
            return readiness.sandbox_configuration_ready
                ? [readiness.network_cutover_active && profile.transport_enabled ? 'Sandbox Ready' : 'Sandbox Configured', 'good']
                : ['Sandbox Setup Required', 'warning'];
        }
        if (readiness.mode === 'Production') {
            return readiness.production_ready && profile.transport_enabled && profile.production_post_armed
                ? ['Production Ready', 'danger']
                : ['Production Setup Required', 'warning'];
        }
        return [readiness.mode || 'Unknown', 'neutral'];
    }

    function cardBlockers(card, blockers) {
        const rows = uniq(blockers);
        if (!rows.length) return;
        const wrap = $('<div class="lx-fbr-card-blockers"></div>').appendTo(card);
        rows.slice(0, 2).forEach((message) => $('<div></div>').text(message).appendTo(wrap));
        if (rows.length > 2) {
            $('<div class="lx-fbr-more"></div>').text(__('+ {0} more blocker(s)', [rows.length - 2])).appendTo(wrap);
        }
    }

    function statusCard({title, status, tone, detail, blockers, actionLabel, action}) {
        const card = $('<section class="lx-fbr-status-card"></section>');
        const head = $('<div class="lx-fbr-card-head"></div>').appendTo(card);
        $('<div class="lx-fbr-card-title"></div>').append($('<span class="lx-fbr-dot"></span>').addClass(`is-${tone}`), $('<strong></strong>').text(__(title))).appendTo(head);
        badge(status, tone).appendTo(head);
        if (detail && detail.length) {
            const detailWrap = $('<div class="lx-fbr-card-detail"></div>').appendTo(card);
            detail.filter((row) => row && row.value !== undefined).forEach((row) => {
                const line = $('<div></div>').appendTo(detailWrap);
                $('<span></span>').text(__(row.label)).appendTo(line);
                $('<strong></strong>').text(textOrDash(row.value)).appendTo(line);
            });
        }
        cardBlockers(card, blockers);
        if (actionLabel && action) {
            $('<div class="lx-fbr-card-action"></div>').append(makeButton(actionLabel, action)).appendTo(card);
        }
        return card;
    }

    function section(title, description) {
        const node = $('<section class="lx-fbr-section"></section>');
        const head = $('<div class="lx-fbr-section-head"></div>').appendTo(node);
        $('<h3></h3>').text(__(title)).appendTo(head);
        if (description) $('<p></p>').text(__(description)).appendTo(head);
        return node;
    }

    function actionGroup(parent, title, description, actions) {
        const group = $('<div class="lx-fbr-action-group"></div>').appendTo(parent);
        $('<h4></h4>').text(__(title)).appendTo(group);
        if (description) $('<p></p>').text(__(description)).appendTo(group);
        const buttons = $('<div class="lx-fbr-action-buttons"></div>').appendTo(group);
        actions.forEach((action) => makeButton(action.label, action.onClick, action).appendTo(buttons));
    }

    function blockerGroup(parent, title, blockers, open = false) {
        const rows = uniq(blockers);
        const details = $('<details class="lx-fbr-blocker-group"></details>').prop('open', open && rows.length > 0).appendTo(parent);
        const summary = $('<summary></summary>').appendTo(details);
        $('<strong></strong>').text(__(title)).appendTo(summary);
        badge(rows.length ? __('{0} blocker(s)', [rows.length]) : __('Clear'), rows.length ? 'warning' : 'good').appendTo(summary);
        if (!rows.length) {
            $('<p class="lx-fbr-empty-note"></p>').text(__('No blockers in this category.')).appendTo(details);
            return;
        }
        const list = $('<ul></ul>').appendTo(details);
        rows.forEach((message) => $('<li></li>').text(message).appendTo(list));
    }

    function invoiceFields() {
        return [
            {fieldname: 'reference_doctype', label: __('Invoice Type'), fieldtype: 'Select', options: 'Sales Invoice\nPOS Invoice', reqd: 1},
            {fieldname: 'reference_name', label: __('Invoice'), fieldtype: 'Dynamic Link', options: 'reference_doctype', reqd: 1},
        ];
    }

    function actionDialog(title, fields, method, resultText, confirmMessage) {
        const dialog = new frappe.ui.Dialog({
            title: __(title),
            fields,
            primary_action_label: __(title),
            primary_action: (values) => {
                const run = async () => {
                    dialog.get_primary_btn().prop('disabled', true);
                    try {
                        const {message: result} = await frappe.call({method, args: values});
                        frappe.msgprint({title: __(title), message: frappe.utils.escape_html(resultText(result))});
                        dialog.hide();
                        refresh();
                    } finally {
                        dialog.get_primary_btn().prop('disabled', false);
                    }
                };
                if (confirmMessage) frappe.confirm(__(confirmMessage), run);
                else run();
            },
        });
        dialog.show();
    }

    function openInvoiceReadiness() {
        const dialog = new frappe.ui.Dialog({
            title: __('Invoice Readiness'),
            fields: invoiceFields(),
            primary_action_label: __('Check'),
            primary_action: async (values) => {
                const {message: result} = await frappe.call({
                    method: 'fbr_v1.api.fiscalization.invoice_readiness',
                    args: values,
                });
                const errors = uniq([...(result.errors || []), ...(result.network_blockers || [])]);
                const content = $('<div></div>');
                if (!errors.length) {
                    $('<p></p>').text(__('Internal prerequisites and current transport readiness are clear for this invoice.')).appendTo(content);
                } else {
                    const list = $('<ul class="lx-fbr-dialog-list"></ul>').appendTo(content);
                    errors.forEach((message) => $('<li></li>').text(message).appendTo(list));
                }
                frappe.msgprint({
                    title: __('Invoice Readiness'),
                    message: content.prop('outerHTML'),
                    indicator: errors.length ? 'orange' : 'green',
                });
                dialog.hide();
            },
        });
        dialog.show();
    }

    function renderHero(data, readiness, profile) {
        const hero = $('<section class="lx-fbr-hero"></section>').appendTo(body);
        const identity = $('<div class="lx-fbr-hero-identity"></div>').appendTo(hero);
        $('<img class="lx-fbr-hero-icon" alt="">').attr('src', iconUrl).appendTo(identity);
        const copy = $('<div></div>').appendTo(identity);
        $('<div class="lx-fbr-kicker"></div>').text(__('Federal fiscal integration')).appendTo(copy);
        $('<h2></h2>').text(__('Federal FBR POS / IMS V1')).appendTo(copy);
        $('<p></p>').text(data.company).appendTo(copy);
        const [label, tone] = overallState(readiness, profile);
        const state = $('<div class="lx-fbr-overall"></div>').appendTo(hero);
        $('<span></span>').text(__('Overall state')).appendTo(state);
        badge(label, tone).appendTo(state);
    }

    function renderStatusCards(data, readiness, profile) {
        const cards = $('<div class="lx-fbr-status-grid"></div>').appendTo(body);
        const seller = readiness.seller_identity || {};
        const sourceBlockers = readiness.source_blockers || [];
        const currentState = readiness.configuration?.[String(readiness.mode || '').toLowerCase()] || {};
        const currentDeviceChecks = currentState.devices || [];
        const modeDevices = (data.devices || []).filter((device) => device.environment === readiness.mode);
        const device = modeDevices.find((row) => row.active) || modeDevices[0] || (data.devices || []).find((row) => row.active) || (data.devices || [])[0];
        const deviceBlockers = uniq(currentDeviceChecks.flatMap((row) => row.blockers || []).filter((message) => /device|posid|topology/i.test(message)));
        const mapping = data.mapping_summary || {};
        const mappingReady = Number(mapping.reviewed_item_mappings || 0) > 0
            && Number(mapping.active_tax_component_mappings || 0) > 0
            && Number(mapping.payment_mappings || 0) > 0;
        const mappingBlockers = uniq((readiness.setup_blockers || []).filter((message) => /mapping/i.test(message)));

        statusCard({
            title: 'Seller Identity',
            status: readiness.source_accounting_ready ? 'Ready' : 'Setup Required',
            tone: readiness.source_accounting_ready ? 'good' : 'warning',
            detail: [
                {label: 'Legal name', value: seller.business_name},
                {label: 'NTN / CNIC', value: seller.ntn_cnic},
                {label: 'Province', value: seller.province},
            ],
            blockers: sourceBlockers,
            actionLabel: 'Open Company',
            action: () => frappe.set_route('Form', 'Company', data.company),
        }).appendTo(cards);

        statusCard({
            title: 'Integration Profile',
            status: readiness.profile ? (readiness.enabled ? readiness.mode : 'Disabled') : 'Not Configured',
            tone: readiness.enabled ? (readiness.mode === 'Production' ? 'danger' : 'good') : 'warning',
            detail: [
                {label: 'Provider', value: profile.provider_type},
                {label: 'Submit trigger', value: profile.submit_trigger},
            ],
            blockers: readiness.enabled
                ? []
                : uniq((readiness.setup_blockers || []).filter((message) => /profile/i.test(message))).concat(
                    readiness.profile ? [] : ['Create one Federal V1 Integration Profile for this company.']
                ),
            actionLabel: readiness.profile ? 'Open Profile' : 'Integration Profiles',
            action: () => readiness.profile
                ? frappe.set_route('Form', 'Ledgix FBR Integration Profile', readiness.profile)
                : routeList('Ledgix FBR Integration Profile', {company: data.company}),
        }).appendTo(cards);

        statusCard({
            title: 'POS Device / POSID',
            status: device && device.active ? (device.operational_state || 'Configured') : 'Setup Required',
            tone: device && device.active && device.operational_state === 'Operational' ? 'good' : 'warning',
            detail: [
                {label: 'Device', value: device && (device.display_label || device.name)},
                {label: 'POSID', value: device && device.pos_id},
                {label: 'Topology', value: device && device.transport_topology},
            ],
            blockers: device ? deviceBlockers : ['Configure an active Federal V1 POS device for this company.'],
            actionLabel: 'POS Devices',
            action: () => routeList('Ledgix FBR POS Device', {company: data.company}),
        }).appendTo(cards);

        statusCard({
            title: 'Item & Tax Mapping',
            status: mappingReady ? 'Configured' : 'Setup Required',
            tone: mappingReady ? 'good' : 'warning',
            detail: [
                {label: 'Reviewed item mappings', value: mapping.reviewed_item_mappings || 0},
                {label: 'Tax component mappings', value: mapping.active_tax_component_mappings || 0},
                {label: 'Payment mappings', value: mapping.payment_mappings || 0},
            ],
            blockers: mappingBlockers,
            actionLabel: 'Item Mappings',
            action: () => routeList('Ledgix FBR Item Mapping', {company: data.company}),
        }).appendTo(cards);

        const sandbox = readiness.configuration?.sandbox || {};
        statusCard({
            title: 'Sandbox',
            status: readiness.sandbox_configuration_ready ? 'Configuration Ready' : 'Setup Required',
            tone: readiness.sandbox_configuration_ready ? 'good' : 'warning',
            detail: [
                {label: 'Configured devices', value: (sandbox.devices || []).length},
                {label: 'General network cutover', value: yesNo(readiness.network_cutover_active)},
            ],
            blockers: sandbox.blockers,
            actionLabel: 'Sandbox Device',
            action: () => routeList('Ledgix FBR POS Device', {company: data.company, environment: 'Sandbox'}),
        }).appendTo(cards);

        const production = readiness.configuration?.production || {};
        statusCard({
            title: 'Production',
            status: readiness.production_configuration_ready ? (readiness.production_ready ? 'Ready' : 'Configuration Ready') : 'Locked / Setup Required',
            tone: readiness.production_ready ? 'danger' : (readiness.production_configuration_ready ? 'warning' : 'neutral'),
            detail: [
                {label: 'Configured devices', value: (production.devices || []).length},
                {label: 'Production cutover', value: yesNo(readiness.production_cutover_active)},
            ],
            blockers: production.blockers,
            actionLabel: 'Production Device',
            action: () => routeList('Ledgix FBR POS Device', {company: data.company, environment: 'Production'}),
        }).appendTo(cards);
    }

    function renderSafety(readiness, profile) {
        const node = section('Safety & Transport', 'Status only. This dashboard does not switch network or production gates.').appendTo(body);
        const grid = $('<div class="lx-fbr-safety-grid"></div>').appendTo(node);
        const rows = [
            ['General Network Cutover', yesNo(readiness.network_cutover_active), readiness.network_cutover_active ? 'warning' : 'good'],
            ['Production Cutover', yesNo(readiness.production_cutover_active), readiness.production_cutover_active ? 'danger' : 'good'],
            ['Transport Enabled', yesNo(profile.transport_enabled), profile.transport_enabled ? 'warning' : 'neutral'],
            ['Production Posting Armed', yesNo(profile.production_post_armed), profile.production_post_armed ? 'danger' : 'good'],
            ['Submit Trigger', profile.submit_trigger || 'Not configured', profile.submit_trigger === 'On Submit' ? 'warning' : 'neutral'],
            ['Offline Policy', profile.offline_policy || 'Not configured', profile.offline_policy === 'Operator Confirmed' ? 'warning' : 'neutral'],
        ];
        rows.forEach(([label, value, tone]) => {
            const item = $('<div class="lx-fbr-safety-item"></div>').addClass(`is-${tone}`).appendTo(grid);
            $('<span></span>').text(__(label)).appendTo(item);
            $('<strong></strong>').text(__(value)).appendTo(item);
        });
        $('<div class="lx-fbr-safety-note"></div>')
            .text(__('Production controls are intentionally fail-closed and must be changed outside this status dashboard.'))
            .appendTo(node);
    }

    function renderBlockers(readiness) {
        const node = section('Readiness Blockers', 'Grouped so internal setup issues stay separate from unresolved external authority contracts.').appendTo(body);
        const source = uniq(readiness.source_blockers || []);
        const setup = without(readiness.setup_blockers || [], source);
        const transport = without(readiness.blockers || [], [...source, ...setup]);
        blockerGroup(node, 'Seller identity', source, true);
        blockerGroup(node, 'Internal setup & mappings', setup, true);
        blockerGroup(node, 'Current mode / transport', transport, transport.length > 0);
        blockerGroup(node, 'External / authority contracts', readiness.unresolved_contracts || [], false);
    }

    function renderOperations(data, readiness, profile) {
        const node = section('Operations', 'Open authoritative records and run guarded diagnostics from one place.').appendTo(body);
        actionGroup(node, 'Setup', null, [
            {label: 'Integration Profile', onClick: () => readiness.profile ? frappe.set_route('Form', 'Ledgix FBR Integration Profile', readiness.profile) : routeList('Ledgix FBR Integration Profile', {company: data.company})},
            {label: 'POS Devices', onClick: () => routeList('Ledgix FBR POS Device', {company: data.company})},
            {label: 'Item Mappings', onClick: () => routeList('Ledgix FBR Item Mapping', {company: data.company})},
            {label: 'Tax Component Mappings', onClick: () => routeList('Ledgix FBR Tax Component Mapping', {company: data.company})},
            {label: 'Payment Mapping', onClick: () => routeList('Mode of Payment')},
        ]);
        actionGroup(node, 'Evidence / Operations', null, [
            {label: 'Submission Logs', onClick: () => routeList('Ledgix FBR Submission Log')},
            {label: 'Fiscal Events', onClick: () => routeList('Ledgix FBR Fiscal Event Log')},
            {label: 'Fiscal Closings', onClick: () => routeList('Ledgix FBR Fiscal Closing')},
            {label: 'Correction Requests', onClick: () => routeList('Ledgix FBR Correction Request')},
            {label: 'Reconciliation', onClick: () => routeList('Ledgix FBR Submission Log', {fbr_status: 'Reconciliation Required'})},
        ]);
        actionGroup(node, 'Transactions', null, [
            {label: 'Sales Invoice', onClick: () => routeList('Sales Invoice')},
            {label: 'POS Invoice', onClick: () => routeList('POS Invoice')},
        ]);

        const modeReady = readiness.mode === 'Sandbox'
            ? readiness.sandbox_configuration_ready
            : readiness.mode === 'Production' && readiness.production_configuration_ready;
        const productionSafe = readiness.mode !== 'Production'
            || (readiness.production_cutover_active && profile.production_post_armed);
        const canFiscalize = canOperate()
            && readiness.enabled
            && modeReady
            && Boolean(profile.transport_enabled)
            && readiness.network_cutover_active
            && productionSafe;
        const localDevices = (data.devices || []).filter((device) => device.transport_topology === 'Local IMS - Server Reachable');
        const canHealth = canOperate() && localDevices.length > 0 && readiness.network_cutover_active;

        const testing = [
            {label: 'Invoice Readiness', primary: true, onClick: openInvoiceReadiness},
        ];
        if (localDevices.length) {
            testing.push({
                label: 'Local IMS Health',
                disabled: !canHealth,
                reason: !readiness.network_cutover_active ? __('General network cutover is OFF.') : __('Accounts Manager permission is required.'),
                onClick: () => actionDialog(
                    'Local IMS Health',
                    [{fieldname: 'pos_device', label: __('POS Device'), fieldtype: 'Link', options: 'Ledgix FBR POS Device', reqd: 1, default: localDevices[0].name}],
                    'fbr_v1.api.center.test_local_ims_health',
                    (result) => result.ok ? __('Local IMS health check succeeded') : (result.error || __('Local IMS health check failed'))
                ),
            });
        }
        testing.push({
            label: readiness.mode === 'Production' ? 'Fiscalize Invoice - Production' : 'Fiscalize Invoice',
            danger: readiness.mode === 'Production',
            disabled: !canFiscalize,
            reason: !canOperate()
                ? __('Accounts Manager permission is required.')
                : __('Requires a ready active mode, Transport Enabled, and the applicable network cutover gate.'),
            onClick: () => actionDialog(
                'Fiscalize Invoice',
                invoiceFields(),
                'fbr_v1.api.fiscalization.submit_invoice',
                (result) => [result.status, ...(result.errors || [])].join(' · '),
                readiness.mode === 'Production'
                    ? 'This may perform a REAL PRODUCTION FBR POST. Continue only with explicit production authorization.'
                    : 'This may perform a real FBR Sandbox POST. Continue only when Sandbox submission is explicitly authorized.'
            ),
        });
        actionGroup(node, 'Testing', 'Invoice readiness is read-only. Network actions remain disabled until their gates are explicitly enabled.', testing);

        if (canOperate()) renderAdvancedOperations(node);
    }

    function renderAdvancedOperations(parent) {
        const details = $('<details class="lx-fbr-advanced"></details>').appendTo(parent);
        $('<summary></summary>').text(__('Advanced operator evidence actions')).appendTo(details);
        $('<p></p>').text(__('These actions write audit/evidence records but do not enable network or production cutover gates.')).appendTo(details);
        const buttons = $('<div class="lx-fbr-action-buttons"></div>').appendTo(details);
        const deviceField = () => ({fieldname: 'pos_device', label: __('POS Device'), fieldtype: 'Link', options: 'Ledgix FBR POS Device', reqd: 1});
        const externalFields = () => [
            {fieldname: 'external_reference', label: __('Authoritative External Reference'), fieldtype: 'Data', reqd: 1},
            {fieldname: 'external_evidence', label: __('External Evidence'), fieldtype: 'Attach', reqd: 1},
        ];
        const add = (label, fn) => makeButton(label, fn).appendTo(buttons);

        add('Record Device Event', () => actionDialog(
            'Record Device Event',
            [deviceField(), {fieldname: 'event_type', label: __('Event'), fieldtype: 'Select', options: 'Startup\nShutdown\nConnectivity Failure\nSoftware Failure\nPower Failure\nRestoration', reqd: 1}],
            'fbr_v1.api.fbr_offline.record_device_event',
            (result) => __('Event recorded: {0}', [result.event])
        ));
        add('Generate Internal Closing', () => actionDialog(
            'Generate Internal Closing',
            [deviceField(), {fieldname: 'period_type', label: __('Period'), fieldtype: 'Select', options: 'Daily\nWeekly\nMonthly', reqd: 1}, {fieldname: 'date', label: __('Date in completed period'), fieldtype: 'Date', reqd: 1}],
            'fbr_v1.services.fiscal_closing.generate_closing',
            (result) => __('Internal closing: {0}', [result.name])
        ));
        add('Record External Compliance Evidence', () => actionDialog(
            'Record External Compliance Evidence',
            [deviceField(), {fieldname: 'event_type', label: __('Event'), fieldtype: 'Select', options: 'Outage Report Filed\nAlert Report Filed\nOffline Upload Confirmed\nCorrection Filed\nCommissioner Approval Recorded', reqd: 1}, ...externalFields(), ...invoiceFields().map((field) => ({...field, reqd: 0, ...(field.fieldname === 'reference_doctype' ? {options: '\nSales Invoice\nPOS Invoice'} : {})})), {fieldname: 'occurred_at', label: __('External Event Time'), fieldtype: 'Datetime'}],
            'fbr_v1.api.compliance_evidence.record_external_compliance_evidence',
            (result) => __('Evidence recorded; invoice unchanged: {0}', [result.event])
        ));
        add('Record Offline Upload Confirmation', () => actionDialog(
            'Record Offline Upload Confirmation',
            [...invoiceFields(), ...externalFields(), {fieldname: 'fbr_invoice_number', label: __('Official FBR Invoice Number'), fieldtype: 'Data', reqd: 1}],
            'fbr_v1.api.fbr_offline.record_offline_upload_confirmation',
            (result) => `${result.status} · ${result.confirmed_after_deadline ? __('Recorded after deadline') : __('Recorded within deadline')}`
        ));
        add('Create Correction Request', () => actionDialog(
            'Create Correction Request',
            [...invoiceFields(), {fieldname: 'action_type', label: __('Action'), fieldtype: 'Select', options: 'Cancel\nDelete\nEdit', reqd: 1}, {fieldname: 'reason', label: __('Bona-fide Reason'), fieldtype: 'Small Text', reqd: 1}, {fieldname: 'fbr_generated_at', label: __('Authoritative FBR Generation Time'), fieldtype: 'Datetime'}, {fieldname: 'generation_time_reference', label: __('Generation Time Authority Reference'), fieldtype: 'Data'}, {fieldname: 'generation_time_evidence', label: __('Generation Time Evidence'), fieldtype: 'Attach'}],
            'fbr_v1.api.corrections.request_correction',
            (result) => `${result.name} · ${result.status}`
        ));
        add('Record Correction Result', () => actionDialog(
            'Record Correction Result',
            [{fieldname: 'correction_request', label: __('Correction Request'), fieldtype: 'Link', options: 'Ledgix FBR Correction Request', reqd: 1}, {fieldname: 'status', label: __('Externally Confirmed Result'), fieldtype: 'Select', options: 'Completed\nRejected', reqd: 1}, {fieldname: 'board_reference', label: __('Board / PRAL Reference'), fieldtype: 'Data', reqd: 1}, {fieldname: 'external_evidence', label: __('External Evidence'), fieldtype: 'Attach', reqd: 1}, {fieldname: 'commissioner_approval_reference', label: __('Commissioner Approval Reference'), fieldtype: 'Data'}],
            'fbr_v1.api.corrections.record_correction_result',
            (result) => `${result.name} · ${result.status}`
        ));
    }

    function renderDevices(data) {
        if (!(data.devices || []).length) return;
        const node = section('POS Devices', 'Current company device inventory. Open the authoritative device record to edit configuration.').appendTo(body);
        const grid = $('<div class="lx-fbr-device-grid"></div>').appendTo(node);
        data.devices.forEach((device) => {
            const card = $('<button type="button" class="lx-fbr-device-card"></button>')
                .on('click', () => frappe.set_route('Form', 'Ledgix FBR POS Device', device.name))
                .appendTo(grid);
            const head = $('<div></div>').appendTo(card);
            $('<strong></strong>').text(device.display_label || device.name).appendTo(head);
            badge(device.environment || 'Unknown', device.environment === 'Production' ? 'danger' : 'neutral').appendTo(head);
            $('<span></span>').text(__('POSID {0}', [device.pos_id || '—'])).appendTo(card);
            $('<small></small>').text(`${device.transport_topology || '—'} · ${device.operational_state || '—'}`).appendTo(card);
        });
    }

    function render(data) {
        const readiness = data.readiness || {};
        const profile = readiness.profile_state || {};
        body.empty();
        renderHero(data, readiness, profile);
        renderStatusCards(data, readiness, profile);
        renderSafety(readiness, profile);
        renderBlockers(readiness);
        renderOperations(data, readiness, profile);
        renderDevices(data);
        $('<p class="lx-fbr-footnote"></p>')
            .text(__('Each invoice still requires immutable-snapshot, payment, accounting and reconciliation checks. Internal closings do not imply FBR acceptance.'))
            .appendTo(body);
    }

    async function refresh() {
        if (busy) return;
        busy = true;
        body.addClass('is-loading');
        try {
            const {message: data} = await frappe.call({
                method: 'fbr_v1.api.center.get_center_boot',
                args: {company: company.get_value()},
            });
            if (!company.get_value() && data.company) company.set_value(data.company);
            render(data);
        } finally {
            busy = false;
            body.removeClass('is-loading');
        }
    }

    refresh();
};
