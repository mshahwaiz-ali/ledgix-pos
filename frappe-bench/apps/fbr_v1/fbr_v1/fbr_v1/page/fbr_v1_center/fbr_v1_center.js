frappe.pages['fbr-v1-center'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('FBR V1 Center'),
        single_column: true,
    });
    $(page.main).addClass('lx-fbr-page-shell');
    const body = $('<div class="lx-fbr-v1-center"></div>').appendTo(page.main);
    const company = page.add_field({
        fieldname: 'company',
        label: __('Company'),
        fieldtype: 'Link',
        options: 'Company',
        change: refresh,
    });
    if (company.$wrapper) company.$wrapper.addClass('lx-fbr-company-selector');
    const iconUrl = '/assets/ledgix_saas/images/brand/fbr_v1.png';
    const canOperate = () => frappe.user.has_role('System Manager') || frappe.user.has_role('Accounts Manager');
    const canManageCutover = () => frappe.user.has_role('System Manager');
    let busy = false;

    const uniq = (rows) => [...new Set((rows || []).filter(Boolean))];
    const without = (rows, excluded) => {
        const omit = new Set(excluded || []);
        return uniq(rows).filter((row) => !omit.has(row));
    };
    const yesNo = (value) => value ? __('ON') : __('OFF');
    const textOrDash = (value) => value === 0 ? '0' : (value || '—');

    const ICONS = {
        seller: '<path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/>',
        profile: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 8h10M7 12h6M7 16h4"/>',
        device: '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M9 6h6M10 18h4"/>',
        mapping: '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
        sandbox: '<path d="M4 5h16v14H4z"/><path d="M8 9l2 2-2 2M12 15h4"/>',
        production: '<path d="M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7l8-4z"/><path d="M9 12l2 2 4-4"/>',
        shield: '<path d="M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7l8-4z"/>',
        alert: '<path d="M12 3L2.8 19h18.4L12 3z"/><path d="M12 9v4M12 16h.01"/>',
        operations: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
        setup: '<path d="M14.7 6.3a4 4 0 0 0-5 5L4 17l3 3 5.7-5.7a4 4 0 0 0 5-5l-2.2 2.2-3-3 2.2-2.2z"/>',
        evidence: '<path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
        transaction: '<path d="M4 7h16M6 3h12v18H6z"/><path d="M9 12h6M9 16h4"/>',
        test: '<path d="M9 3h6M10 3v5l-5 9a3 3 0 0 0 2.6 4.5h8.8A3 3 0 0 0 19 17l-5-9V3"/><path d="M8 16h8"/>',
        arrow: '<path d="M5 12h14M14 7l5 5-5 5"/>',
        check: '<path d="M5 12l4 4L19 6"/>',
        lock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
    };

    const CARD_META = {
        'Seller Identity': {icon: 'seller', step: '01'},
        'Integration Profile': {icon: 'profile', step: '02'},
        'POS Device / POSID': {icon: 'device', step: '03'},
        'Item & Tax Mapping': {icon: 'mapping', step: '04'},
        'Sandbox': {icon: 'sandbox', step: '05'},
        'Production': {icon: 'production', step: '06'},
    };

    const SECTION_META = {
        'Safety & Transport': 'shield',
        'Readiness Blockers': 'alert',
        'Operations': 'operations',
        'POS Devices': 'device',
    };

    function iconNode(name, extraClass = '') {
        const paths = ICONS[name] || ICONS.operations;
        return $(`<span class="lx-fbr-icon ${extraClass}" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${paths}</svg></span>`);
    }

    function routeList(doctype, filters) {
        frappe.set_route('List', doctype, filters || {});
    }

    function makeButton(label, onClick, options = {}) {
        const button = $('<button type="button" class="btn btn-sm lx-fbr-action-button"></button>')
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
        iconNode('alert', 'is-warning').appendTo(wrap);
        const copy = $('<div class="lx-fbr-card-blocker-copy"></div>').appendTo(wrap);
        $('<strong></strong>').text(rows[0]).appendTo(copy);
        if (rows.length > 1) {
            $('<span></span>').text(__('{0} additional blocker(s)', [rows.length - 1])).appendTo(copy);
        }
    }

    function statusCard({title, status, tone, detail, blockers, actionLabel, action}) {
        const meta = CARD_META[title] || {icon: 'operations', step: ''};
        const card = $('<section class="lx-fbr-status-card"></section>').addClass(`is-${tone}`);
        const head = $('<div class="lx-fbr-card-head"></div>').appendTo(card);
        const identity = $('<div class="lx-fbr-card-identity"></div>').appendTo(head);
        iconNode(meta.icon, `is-${tone}`).appendTo(identity);
        const titleWrap = $('<div class="lx-fbr-card-title"></div>').appendTo(identity);
        if (meta.step) $('<span class="lx-fbr-card-step"></span>').text(meta.step).appendTo(titleWrap);
        $('<strong></strong>').text(__(title)).appendTo(titleWrap);
        badge(status, tone).appendTo(head);

        if (detail && detail.length) {
            const detailWrap = $('<div class="lx-fbr-card-detail"></div>').appendTo(card);
            detail.filter((row) => row && row.value !== undefined).forEach((row) => {
                const line = $('<div class="lx-fbr-detail-row"></div>').appendTo(detailWrap);
                $('<span></span>').text(__(row.label)).appendTo(line);
                $('<strong></strong>').text(textOrDash(row.value)).appendTo(line);
            });
        }

        cardBlockers(card, blockers);
        if (actionLabel && action) {
            const footer = $('<div class="lx-fbr-card-action"></div>').appendTo(card);
            const button = makeButton(actionLabel, action).addClass('lx-fbr-card-link');
            iconNode('arrow', 'is-arrow').appendTo(button);
            button.appendTo(footer);
        }
        return card;
    }

    function section(title, description) {
        const node = $('<section class="lx-fbr-section"></section>');
        const head = $('<div class="lx-fbr-section-head"></div>').appendTo(node);
        const heading = $('<div class="lx-fbr-section-heading"></div>').appendTo(head);
        iconNode(SECTION_META[title] || 'operations', 'is-section').appendTo(heading);
        const copy = $('<div></div>').appendTo(heading);
        $('<h3></h3>').text(__(title)).appendTo(copy);
        if (description) $('<p></p>').text(__(description)).appendTo(copy);
        return node;
    }

    function actionGroup(parent, title, description, actions) {
        const iconMap = {Setup: 'setup', 'Evidence / Operations': 'evidence', Transactions: 'transaction', Testing: 'test'};
        const group = $('<div class="lx-fbr-action-group"></div>').appendTo(parent);
        const head = $('<div class="lx-fbr-action-group-head"></div>').appendTo(group);
        iconNode(iconMap[title] || 'operations', 'is-action').appendTo(head);
        const copy = $('<div></div>').appendTo(head);
        $('<h4></h4>').text(__(title)).appendTo(copy);
        if (description) $('<p></p>').text(__(description)).appendTo(copy);
        const buttons = $('<div class="lx-fbr-action-buttons"></div>').appendTo(group);
        actions.forEach((action) => makeButton(action.label, action.onClick, action).appendTo(buttons));
    }

    function blockerGroup(parent, title, blockers, open = false) {
        const rows = uniq(blockers);
        const details = $('<details class="lx-fbr-blocker-group"></details>')
            .addClass(rows.length ? 'has-blockers' : 'is-clear')
            .prop('open', open && rows.length > 0)
            .appendTo(parent);
        const summary = $('<summary></summary>').appendTo(details);
        const left = $('<div class="lx-fbr-blocker-summary"></div>').appendTo(summary);
        iconNode(rows.length ? 'alert' : 'check', rows.length ? 'is-warning' : 'is-good').appendTo(left);
        const copy = $('<div></div>').appendTo(left);
        $('<strong></strong>').text(__(title)).appendTo(copy);
        $('<span></span>').text(rows.length ? __('Needs attention') : __('No blockers')).appendTo(copy);
        badge(rows.length ? __('{0}', [rows.length]) : __('Clear'), rows.length ? 'warning' : 'good').appendTo(summary);
        if (!rows.length) return;
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
        const main = $('<div class="lx-fbr-hero-main"></div>').appendTo(hero);
        const brand = $('<div class="lx-fbr-hero-brand"></div>').appendTo(main);
        $('<div class="lx-fbr-hero-icon-wrap"></div>')
            .append($('<img class="lx-fbr-hero-icon" alt="">').attr('src', iconUrl))
            .appendTo(brand);

        const copy = $('<div class="lx-fbr-hero-copy"></div>').appendTo(brand);
        $('<div class="lx-fbr-kicker"></div>').text(__('Federal fiscal integration')).appendTo(copy);
        $('<h2></h2>').text(__('Federal FBR POS / IMS V1')).appendTo(copy);
        $('<p></p>').text(__('ERPNext-native configuration, fiscal readiness and guarded operations.')).appendTo(copy);

        const chips = $('<div class="lx-fbr-hero-chips"></div>').appendTo(copy);
        $('<span class="lx-fbr-meta-chip"></span>').text(data.company).appendTo(chips);
        $('<span class="lx-fbr-meta-chip"></span>').text(__('Mode: {0}', [readiness.mode || 'Disabled'])).appendTo(chips);
        $('<span class="lx-fbr-meta-chip"></span>').text(readiness.profile ? __('Profile linked') : __('No profile yet')).appendTo(chips);

        const [label, tone] = overallState(readiness, profile);
        const state = $('<aside class="lx-fbr-hero-state"></aside>').addClass(`is-${tone}`).appendTo(hero);
        const stateTop = $('<div class="lx-fbr-hero-state-top"></div>').appendTo(state);
        const stateCopy = $('<div></div>').appendTo(stateTop);
        $('<span></span>').text(__('Overall state')).appendTo(stateCopy);
        $('<strong></strong>').text(__(label)).appendTo(stateCopy);
        badge(label, tone).appendTo(stateTop);

        const mini = $('<div class="lx-fbr-hero-state-grid"></div>').appendTo(state);
        [
            ['Network gate', yesNo(readiness.network_cutover_active), readiness.network_cutover_active ? 'warning' : 'good'],
            ['Production gate', yesNo(readiness.production_cutover_active), readiness.production_cutover_active ? 'danger' : 'good'],
        ].forEach(([name, value, stateTone]) => {
            const item = $('<div class="lx-fbr-hero-mini"></div>').appendTo(mini);
            $('<span></span>').text(__(name)).appendTo(item);
            $('<strong></strong>').addClass(`is-${stateTone}`).text(__(value)).appendTo(item);
        });

        $('<div class="lx-fbr-hero-safe-note"></div>')
            .append(iconNode('lock', 'is-small'))
            .append($('<span></span>').text(__('This Center never switches cutover gates.')))
            .appendTo(state);
    }


    function renderStatusCards(data, readiness, profile) {
        const shell = $('<section class="lx-fbr-readiness-wrap"></section>').appendTo(body);
        const readinessHead = $('<div class="lx-fbr-readiness-head"></div>').appendTo(shell);
        const readinessCopy = $('<div></div>').appendTo(readinessHead);
        $('<div class="lx-fbr-kicker"></div>').text(__('Configuration path')).appendTo(readinessCopy);
        $('<h3></h3>').text(__('Readiness Overview')).appendTo(readinessCopy);
        $('<p></p>').text(__('Complete the shared ERPNext setup first, then validate Sandbox before Production.')).appendTo(readinessCopy);
        const sharedCount = uniq(readiness.setup_blockers || []).length;
        badge(sharedCount ? __('{0} shared blocker(s)', [sharedCount]) : __('Shared setup clear'), sharedCount ? 'warning' : 'good').appendTo(readinessHead);

        const cards = $('<div class="lx-fbr-status-grid"></div>').appendTo(shell);
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

        const profileBlockers = readiness.profile
            ? uniq((readiness.setup_blockers || []).filter((message) => /profile/i.test(message)))
            : ['Create a Federal V1 Integration Profile for this company.'];
        statusCard({
            title: 'Integration Profile',
            status: readiness.profile ? (readiness.enabled ? readiness.mode : 'Disabled') : 'Not Configured',
            tone: readiness.enabled ? (readiness.mode === 'Production' ? 'danger' : 'good') : 'warning',
            detail: [
                {label: 'Provider', value: profile.provider_type},
                {label: 'Submit trigger', value: profile.submit_trigger},
                {label: 'Transport', value: readiness.profile ? yesNo(profile.transport_enabled) : 'Not configured'},
            ],
            blockers: profileBlockers,
            actionLabel: readiness.profile ? 'Open Profile' : 'Create / Open Profiles',
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
            actionLabel: 'Open POS Devices',
            action: () => routeList('Ledgix FBR POS Device', {company: data.company}),
        }).appendTo(cards);

        statusCard({
            title: 'Item & Tax Mapping',
            status: mappingReady ? 'Configured' : 'Setup Required',
            tone: mappingReady ? 'good' : 'warning',
            detail: [
                {label: 'Reviewed items', value: mapping.reviewed_item_mappings || 0},
                {label: 'Tax components', value: mapping.active_tax_component_mappings || 0},
                {label: 'Payment mappings', value: mapping.payment_mappings || 0},
            ],
            blockers: mappingBlockers,
            actionLabel: 'Open Item Mappings',
            action: () => routeList('Ledgix FBR Item Mapping', {company: data.company}),
        }).appendTo(cards);

        const sandbox = readiness.configuration?.sandbox || {};
        const sandboxBlockers = without(sandbox.blockers || [], readiness.setup_blockers || []);
        if (!readiness.setup_ready) sandboxBlockers.unshift('Complete the shared setup prerequisites first.');
        statusCard({
            title: 'Sandbox',
            status: readiness.sandbox_configuration_ready ? 'Configuration Ready' : 'Setup Required',
            tone: readiness.sandbox_configuration_ready ? 'good' : 'warning',
            detail: [
                {label: 'Configured devices', value: (sandbox.devices || []).length},
                {label: 'Network gate', value: yesNo(readiness.network_cutover_active)},
                {label: 'Mode', value: readiness.mode === 'Sandbox' ? 'Active mode' : 'Available for setup'},
            ],
            blockers: uniq(sandboxBlockers),
            actionLabel: 'Open Sandbox Devices',
            action: () => routeList('Ledgix FBR POS Device', {company: data.company, environment: 'Sandbox'}),
        }).appendTo(cards);

        const production = readiness.configuration?.production || {};
        const productionBlockers = without(production.blockers || [], readiness.setup_blockers || []);
        if (!readiness.setup_ready) productionBlockers.unshift('Complete shared setup and Sandbox validation before Production.');
        statusCard({
            title: 'Production',
            status: readiness.production_ready ? 'Ready' : (readiness.production_configuration_ready ? 'Configuration Ready' : 'Locked'),
            tone: readiness.production_ready ? 'danger' : (readiness.production_configuration_ready ? 'warning' : 'neutral'),
            detail: [
                {label: 'Configured devices', value: (production.devices || []).length},
                {label: 'Production gate', value: yesNo(readiness.production_cutover_active)},
                {label: 'Posting armed', value: readiness.profile ? yesNo(profile.production_post_armed) : 'Not configured'},
            ],
            blockers: uniq(productionBlockers),
            actionLabel: 'Open Production Devices',
            action: () => routeList('Ledgix FBR POS Device', {company: data.company, environment: 'Production'}),
        }).appendTo(cards);
    }


    function renderSafety(data, readiness, profile) {
        const node = section(
            'Safety & Transport',
            'Sandbox networking can be controlled here by System Manager; Production cutover remains externally controlled.'
        ).appendTo(body);

        const banner = $('<div class="lx-fbr-safety-banner"></div>').appendTo(node);
        iconNode('shield', 'is-safety').appendTo(banner);
        const bannerCopy = $('<div></div>').appendTo(banner);
        $('<strong></strong>').text(__('Fail-closed by design')).appendTo(bannerCopy);
        $('<span></span>').text(__('Sandbox networking requires an explicit operator action. Production cutover cannot be enabled from this Center.')).appendTo(bannerCopy);
        badge(readiness.production_cutover_active ? 'Production gate ON' : 'Production locked', readiness.production_cutover_active ? 'danger' : 'good').appendTo(banner);

        const grid = $('<div class="lx-fbr-safety-grid"></div>').appendTo(node);
        const hasProfile = Boolean(readiness.profile);
        const rows = [
            ['General Network Cutover', yesNo(readiness.network_cutover_active), readiness.network_cutover_active ? 'warning' : 'good'],
            ['Production Cutover', yesNo(readiness.production_cutover_active), readiness.production_cutover_active ? 'danger' : 'good'],
            ['Transport Enabled', hasProfile ? yesNo(profile.transport_enabled) : 'Not configured', !hasProfile ? 'neutral' : (profile.transport_enabled ? 'warning' : 'good')],
            ['Production Posting Armed', hasProfile ? yesNo(profile.production_post_armed) : 'Not configured', !hasProfile ? 'neutral' : (profile.production_post_armed ? 'danger' : 'good')],
            ['Submit Trigger', profile.submit_trigger || 'Not configured', profile.submit_trigger === 'On Submit' ? 'warning' : 'neutral'],
            ['Offline Policy', profile.offline_policy || 'Not configured', profile.offline_policy === 'Operator Confirmed' ? 'warning' : 'neutral'],
        ];
        rows.forEach(([label, value, tone]) => {
            const item = $('<div class="lx-fbr-safety-item"></div>').addClass(`is-${tone}`).appendTo(grid);
            const top = $('<div class="lx-fbr-safety-item-top"></div>').appendTo(item);
            $('<span></span>').text(__(label)).appendTo(top);
            $('<i class="lx-fbr-state-dot"></i>').addClass(`is-${tone}`).appendTo(top);
            $('<strong></strong>').text(__(value)).appendTo(item);
        });

        const gateOn = Boolean(readiness.network_cutover_active);
        const sandboxMode = readiness.mode === 'Sandbox';
        const canToggle = canManageCutover() && (sandboxMode || gateOn);
        const controls = $('<div class="lx-fbr-action-buttons"></div>').appendTo(node);

        const toggleLabel = gateOn
            ? 'Disable Sandbox Network'
            : 'Enable Sandbox Network';

        const toggleReason = !canManageCutover()
            ? __('System Manager permission is required.')
            : (!sandboxMode && !gateOn
                ? __('The active FBR profile must be in Sandbox mode.')
                : '');

        const toggleButton = makeButton(
            toggleLabel,
            () => {
                const enabling = !gateOn;
                const confirmMessage = enabling
                    ? __('Enable REAL FBR Sandbox networking for this site? Production cutover cannot be enabled by this action.')
                    : __('Disable FBR Sandbox networking for this site?');

                frappe.confirm(confirmMessage, async () => {
                    toggleButton.prop('disabled', true);
                    try {
                        const {message: result} = await frappe.call({
                            method: 'fbr_v1.api.center.set_sandbox_network_cutover',
                            args: {
                                company: data.company,
                                enabled: enabling ? 1 : 0,
                            },
                        });

                        if (result.production_cutover_active) {
                            frappe.throw(
                                __('Safety interlock violation: Production transport must remain OFF.')
                            );
                        }

                        frappe.msgprint({
                            title: __('Sandbox Network'),
                            message: result.network_cutover_active
                                ? __('Sandbox network gate is ON. Production remains OFF.')
                                : __('Sandbox network gate is OFF.'),
                            indicator: result.network_cutover_active ? 'orange' : 'green',
                        });

                        await refresh();
                    } finally {
                        toggleButton.prop('disabled', false);
                    }
                });
            },
            {
                primary: !gateOn,
                disabled: !canToggle,
                reason: toggleReason,
            }
        );

        toggleButton.appendTo(controls);
    }


    function renderBlockers(readiness) {
        const node = section('Readiness Blockers', 'Resolve internal prerequisites first; external authority contracts remain isolated and clearly labelled.').appendTo(body);
        const source = uniq(readiness.source_blockers || []);
        const setup = without(readiness.setup_blockers || [], source);
        const transport = without(readiness.blockers || [], [...source, ...setup]);
        const external = uniq(readiness.unresolved_contracts || []);
        const totalInternal = source.length + setup.length + transport.length;

        const summary = $('<div class="lx-fbr-blocker-overview"></div>').appendTo(node);
        const summaryCopy = $('<div></div>').appendTo(summary);
        $('<strong></strong>').text(totalInternal ? __('{0} internal blocker(s)', [totalInternal]) : __('Internal readiness clear')).appendTo(summaryCopy);
        $('<span></span>').text(totalInternal ? __('Work through the open groups below in order.') : __('No current internal blocker is reported for the selected company and mode.')).appendTo(summaryCopy);
        badge(totalInternal ? 'Action required' : 'Clear', totalInternal ? 'warning' : 'good').appendTo(summary);

        const grid = $('<div class="lx-fbr-blocker-grid"></div>').appendTo(node);
        blockerGroup(grid, 'Seller identity', source, true);
        blockerGroup(grid, 'Internal setup & mappings', setup, true);
        blockerGroup(grid, 'Current mode / transport', transport, transport.length > 0);
        blockerGroup(grid, 'External / authority contracts', external, false);
    }

    function renderOperations(data, readiness, profile) {
        const node = section('Operations', 'Open authoritative records, evidence and guarded diagnostics from one place.').appendTo(body);
        const groups = $('<div class="lx-fbr-operation-grid"></div>').appendTo(node);
        actionGroup(groups, 'Setup', 'Configure the ERPNext and Federal V1 records used by fiscalization.', [
            {label: 'Integration Profile', onClick: () => readiness.profile ? frappe.set_route('Form', 'Ledgix FBR Integration Profile', readiness.profile) : routeList('Ledgix FBR Integration Profile', {company: data.company})},
            {label: 'POS Devices', onClick: () => routeList('Ledgix FBR POS Device', {company: data.company})},
            {label: 'Item Mappings', onClick: () => routeList('Ledgix FBR Item Mapping', {company: data.company})},
            {label: 'Tax Component Mappings', onClick: () => routeList('Ledgix FBR Tax Component Mapping', {company: data.company})},
            {label: 'Payment Mapping', onClick: () => routeList('Mode of Payment')},
        ]);
        actionGroup(groups, 'Evidence / Operations', 'Review immutable evidence, fiscal events and reconciliation work.', [
            {label: 'Submission Logs', onClick: () => routeList('Ledgix FBR Submission Log')},
            {label: 'Fiscal Events', onClick: () => routeList('Ledgix FBR Fiscal Event Log')},
            {label: 'Fiscal Closings', onClick: () => routeList('Ledgix FBR Fiscal Closing')},
            {label: 'Correction Requests', onClick: () => routeList('Ledgix FBR Correction Request')},
            {label: 'Reconciliation', onClick: () => routeList('Ledgix FBR Submission Log', {fbr_status: 'Reconciliation Required'})},
        ]);
        actionGroup(groups, 'Transactions', 'Open native ERPNext transaction lists without bypassing invoice-level checks.', [
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
        actionGroup(groups, 'Testing', 'Invoice readiness is read-only. Network actions remain disabled until their gates are explicitly enabled.', testing);

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
        const node = section('POS Devices', 'Current company device inventory. Open a card to inspect or edit the authoritative device record.').appendTo(body);
        const grid = $('<div class="lx-fbr-device-grid"></div>').appendTo(node);
        data.devices.forEach((device) => {
            const card = $('<button type="button" class="lx-fbr-device-card"></button>')
                .on('click', () => frappe.set_route('Form', 'Ledgix FBR POS Device', device.name))
                .appendTo(grid);
            const top = $('<div class="lx-fbr-device-top"></div>').appendTo(card);
            const identity = $('<div class="lx-fbr-device-identity"></div>').appendTo(top);
            iconNode('device', device.active ? 'is-good' : 'is-neutral').appendTo(identity);
            const copy = $('<div></div>').appendTo(identity);
            $('<strong></strong>').text(device.display_label || device.name).appendTo(copy);
            $('<span></span>').text(device.pos_id ? __('POSID {0}', [device.pos_id]) : __('POSID not assigned')).appendTo(copy);
            badge(device.environment || 'Unknown', device.environment === 'Production' ? 'danger' : 'neutral').appendTo(top);

            const meta = $('<div class="lx-fbr-device-meta"></div>').appendTo(card);
            $('<span></span>').text(device.transport_topology || '—').appendTo(meta);
            $('<span></span>').text(device.operational_state || '—').appendTo(meta);
            $('<span></span>').text(device.active ? __('Active') : __('Inactive')).appendTo(meta);
        });
    }

    function render(data) {
        const readiness = data.readiness || {};
        const profile = readiness.profile_state || {};
        body.empty();
        renderHero(data, readiness, profile);
        renderStatusCards(data, readiness, profile);
        renderSafety(data, readiness, profile);
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
