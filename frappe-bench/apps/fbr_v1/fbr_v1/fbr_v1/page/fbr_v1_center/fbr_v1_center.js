frappe.pages['fbr-v1-center'].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('FBR V1 Center'),
        single_column: true,
    });

    $(wrapper).addClass('lx-fbr-v1-wrapper');
    $(page.main).addClass('lx-fbr-page-shell');
    const body = $('<div class="lx-fbr-v1-center"></div>').appendTo(page.main);

    const iconUrl = '/assets/ledgix_saas/images/brand/fbr_v1.png';
    const canOperate = () => frappe.user.has_role('System Manager') || frappe.user.has_role('Accounts Manager');
    const canManageCutover = () => frappe.user.has_role('System Manager');

    const TABS = [
        ['overview', 'Overview'],
        ['sandbox', 'Sandbox'],
        ['setup', 'Setup'],
        ['evidence', 'Evidence'],
        ['production', 'Production'],
    ];

    const ICONS = {
        seller: '<path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/>',
        profile: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 8h10M7 12h6M7 16h4"/>',
        device: '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M9 6h6M10 18h4"/>',
        mapping: '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
        sandbox: '<path d="M4 5h16v14H4z"/><path d="M8 9l2 2-2 2M12 15h4"/>',
        production: '<path d="M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7l8-4z"/><path d="M9 12l2 2 4-4"/>',
        shield: '<path d="M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7l8-4z"/>',
        alert: '<path d="M12 3L2.8 19h18.4L12 3z"/><path d="M12 9v4M12 16h.01"/>',
        setup: '<path d="M14.7 6.3a4 4 0 0 0-5 5L4 17l3 3 5.7-5.7a4 4 0 0 0 5-5l-2.2 2.2-3-3 2.2-2.2z"/>',
        evidence: '<path d="M6 3h9l3 3v15H6z"/><path d="M14 3v4h4M9 12h6M9 16h6"/>',
        invoice: '<path d="M6 3h12v18H6z"/><path d="M9 8h6M9 12h6M9 16h4"/>',
        check: '<path d="M5 12l4 4L19 6"/>',
        lock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
        arrow: '<path d="M5 12h14M14 7l5 5-5 5"/>',
        activity: '<path d="M3 12h4l2-5 4 10 2-5h6"/>',
    };

    let busy = false;
    let activeTab = 'overview';
    let currentCompany = null;
    let lastData = null;
    let invoiceType = 'POS Invoice';
    let invoiceName = '';
    let sandboxActionResult = null;

    let productionInvoiceType = 'POS Invoice';
    let productionInvoiceName = '';
    let productionActionResult = null;

    const uniq = (rows) => [...new Set((rows || []).filter(Boolean))];
    const textOrDash = (value) => value === 0 ? '0' : (value || '—');
    const yesNo = (value) => value ? __('ON') : __('OFF');

    function iconNode(name, extraClass) {
        const paths = ICONS[name] || ICONS.activity;
        return $('<span class="lx-fbr-icon ' + (extraClass || '') + '" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' + paths + '</svg></span>');
    }

    function routeList(doctype, filters) {
        frappe.set_route('List', doctype, filters || {});
    }

    function makeButton(label, onClick, options) {
        options = options || {};
        const button = $('<button type="button" class="btn btn-sm lx-fbr-action-button"></button>')
            .addClass(options.primary ? 'btn-primary' : 'btn-default')
            .text(__(label));

        if (options.danger) button.addClass('lx-fbr-danger-action');

        if (options.disabled) {
            button.prop('disabled', true);
            if (options.reason) button.attr('title', options.reason);
        } else if (onClick) {
            button.on('click', onClick);
        }

        return button;
    }

    function badge(label, tone) {
        return $('<span class="lx-fbr-status-badge"></span>')
            .addClass('is-' + (tone || 'neutral'))
            .text(__(label));
    }

    function panel(parent, title, icon, options) {
        options = options || {};
        const node = $('<section class="lx-fbr-panel"></section>').appendTo(parent);
        if (options.className) node.addClass(options.className);

        const head = $('<div class="lx-fbr-panel-head"></div>').appendTo(node);
        const identity = $('<div class="lx-fbr-panel-title"></div>').appendTo(head);
        if (icon) iconNode(icon, 'is-panel').appendTo(identity);
        $('<h3></h3>').text(__(title)).appendTo(identity);

        if (options.badge) {
            badge(options.badge.label, options.badge.tone).appendTo(head);
        }

        return node;
    }

    function notice(parent, tone, title, detail) {
        const node = $('<div class="lx-fbr-notice"></div>').addClass('is-' + tone).appendTo(parent);
        iconNode(tone === 'good' ? 'check' : (tone === 'danger' ? 'lock' : 'alert'), 'is-notice').appendTo(node);
        const copy = $('<div></div>').appendTo(node);
        $('<strong></strong>').text(__(title)).appendTo(copy);
        if (detail) $('<span></span>').text(__(detail)).appendTo(copy);
        return node;
    }

    function factGrid(parent, rows) {
        const grid = $('<div class="lx-fbr-fact-grid"></div>').appendTo(parent);
        rows.filter((row) => row && row.value !== undefined).forEach((row) => {
            const item = $('<div class="lx-fbr-fact"></div>').appendTo(grid);
            $('<span></span>').text(__(row.label)).appendTo(item);
            const value = $('<strong></strong>').text(textOrDash(row.value)).appendTo(item);
            if (row.tone) value.addClass('is-' + row.tone);
        });
        return grid;
    }

    function buttonRow(parent, actions) {
        const row = $('<div class="lx-fbr-button-row"></div>').appendTo(parent);
        actions.forEach((action) => {
            makeButton(action.label, action.onClick, action).appendTo(row);
        });
        return row;
    }

    function actionTile(parent, config) {
        const tile = $('<button type="button" class="lx-fbr-action-tile"></button>')
            .on('click', config.onClick)
            .appendTo(parent);
        iconNode(config.icon || 'arrow', 'is-action-tile').appendTo(tile);
        const copy = $('<span class="lx-fbr-action-tile-copy"></span>').appendTo(tile);
        $('<strong></strong>').text(__(config.title)).appendTo(copy);
        if (config.meta) $('<span></span>').text(config.meta).appendTo(copy);
        if (config.status) badge(config.status, config.tone || 'neutral').appendTo(tile);
        iconNode('arrow', 'is-arrow').appendTo(tile);
        return tile;
    }

    function pickDevice(data, environment) {
        const devices = data.devices || [];
        const matching = environment ? devices.filter((row) => row.environment === environment) : devices;
        return matching.find((row) => row.active) || matching[0] || devices.find((row) => row.active) || devices[0] || null;
    }

    function deriveState(data) {
        const readiness = data.readiness || {};
        const profile = readiness.profile_state || {};
        const mapping = data.mapping_summary || {};
        const currentDevice = pickDevice(data, readiness.mode);
        const activeItems = Number(mapping.active_item_mappings || 0);
        const reviewedItems = Number(mapping.reviewed_item_mappings || 0);
        const mappingReady = activeItems > 0
            && reviewedItems === activeItems
            && Number(mapping.active_tax_component_mappings || 0) > 0
            && Number(mapping.payment_mappings || 0) > 0;

        // Overview is configuration-focused. An intentionally closed network
        // gate is a safe runtime state, not a setup blocker.
        const internalBlockers = uniq([
            ...(readiness.source_blockers || []),
            ...(readiness.setup_blockers || []),
        ]);

        return {
            readiness,
            profile,
            mapping,
            currentDevice,
            mappingReady,
            internalBlockers,
            externalBlockers: uniq(readiness.unresolved_contracts || []),
        };
    }

    function mountCompanyControl(parent, data) {
        const host = $('<div class="lx-fbr-company-field"></div>').appendTo(parent);
        const control = frappe.ui.form.make_control({
            parent: host,
            df: {
                fieldname: 'company',
                label: __('Company'),
                fieldtype: 'Link',
                options: 'Company',
                default: data.company,
            },
            render_input: true,
        });
        control.refresh();
        control.set_value(data.company);

        if (control.$input) {
            control.$input.on('change', () => {
                const value = control.get_value();
                if (value && value !== currentCompany) {
                    currentCompany = value;
                    refresh(value);
                }
            });
        }
    }

    function renderHeader(data, state) {
        const readiness = state.readiness;
        const profile = state.profile;
        const header = $('<header class="lx-fbr-console-header"></header>').appendTo(body);
        const top = $('<div class="lx-fbr-console-top"></div>').appendTo(header);

        const brand = $('<div class="lx-fbr-brand"></div>').appendTo(top);
        $('<div class="lx-fbr-logo-wrap"></div>')
            .append($('<img class="lx-fbr-logo" alt="">').attr('src', iconUrl))
            .appendTo(brand);

        const copy = $('<div class="lx-fbr-brand-copy"></div>').appendTo(brand);
        $('<span class="lx-fbr-eyebrow"></span>').text(__('Federal fiscal integration')).appendTo(copy);
        $('<h1></h1>').text(__('Federal FBR POS / IMS V1')).appendTo(copy);

        const controls = $('<div class="lx-fbr-header-controls"></div>').appendTo(top);
        mountCompanyControl(controls, data);

        const strip = $('<div class="lx-fbr-state-strip"></div>').appendTo(header);
        const mode = readiness.mode || 'Disabled';
        const modeTone = mode === 'Production' ? 'danger' : (mode === 'Sandbox' ? 'good' : 'neutral');
        badge(mode, modeTone).appendTo(strip);
        badge(readiness.network_cutover_active ? 'Sandbox Network ON' : 'Sandbox Network OFF', readiness.network_cutover_active ? 'warning' : 'good').appendTo(strip);
        badge(profile.submit_trigger === 'Manual' ? 'Manual Submit' : (profile.submit_trigger || 'Submit Not Configured'), profile.submit_trigger === 'Manual' ? 'neutral' : 'warning').appendTo(strip);

        const productionLocked = !readiness.production_cutover_active && !profile.production_post_armed;
        badge(
            productionLocked ? 'Production Locked' : 'Production Attention',
            productionLocked ? 'good' : 'danger'
        ).appendTo(strip);
    }

    function renderTabs(data) {
        const tabs = $('<nav class="lx-fbr-tabs" role="tablist"></nav>').appendTo(body);
        TABS.forEach(([key, label]) => {
            const button = $('<button type="button" class="lx-fbr-tab" role="tab"></button>')
                .toggleClass('is-active', activeTab === key)
                .attr('aria-selected', activeTab === key ? 'true' : 'false')
                .text(__(label))
                .on('click', () => {
                    if (activeTab === key) return;
                    activeTab = key;
                    render(data);
                })
                .appendTo(tabs);

            if (key === 'production') {
                iconNode('lock', 'is-tab-lock').prependTo(button);
            }
        });
    }

    function statusTile(parent, config) {
        const tile = $('<div class="lx-fbr-status-tile"></div>').appendTo(parent);
        const left = $('<div class="lx-fbr-status-tile-main"></div>').appendTo(tile);
        iconNode(config.icon, 'is-' + config.tone).appendTo(left);
        const copy = $('<div></div>').appendTo(left);
        $('<strong></strong>').text(__(config.title)).appendTo(copy);
        if (config.meta) $('<span></span>').text(config.meta).appendTo(copy);
        badge(config.status, config.tone).appendTo(tile);
        if (config.onClick) {
            tile.addClass('is-clickable').on('click', config.onClick);
        }
        return tile;
    }

    function renderBlockers(parent, state) {
        if (!state.internalBlockers.length) {
            notice(parent, 'good', 'Configuration ready', 'No current configuration blocker is reported.');
            return;
        }

        const blockers = $('<div class="lx-fbr-blockers"></div>').appendTo(parent);
        const group = $('<div class="lx-fbr-blocker-box"></div>').appendTo(blockers);
        $('<strong></strong>').text(__('{0} item(s) require attention', [state.internalBlockers.length])).appendTo(group);
        const list = $('<ul></ul>').appendTo(group);
        state.internalBlockers.forEach((message) => $('<li></li>').text(message).appendTo(list));
    }

    function renderOverview(data, state, workspace) {
        const readiness = state.readiness;
        const profile = state.profile;
        const seller = readiness.seller_identity || {};
        const device = state.currentDevice;

        const config = panel(workspace, 'Configuration', 'activity');
        const grid = $('<div class="lx-fbr-status-grid"></div>').appendTo(config);

        statusTile(grid, {
            icon: 'seller',
            title: 'Seller Identity',
            status: readiness.source_accounting_ready ? 'Ready' : 'Setup Required',
            tone: readiness.source_accounting_ready ? 'good' : 'warning',
            meta: [seller.business_name, seller.ntn_cnic, seller.province].filter(Boolean).join(' · ') || 'Not configured',
            onClick: () => frappe.set_route('Form', 'Company', data.company),
        });

        statusTile(grid, {
            icon: 'profile',
            title: 'Integration Profile',
            status: readiness.profile ? (readiness.enabled ? readiness.mode : 'Disabled') : 'Not Configured',
            tone: readiness.profile && readiness.enabled ? (readiness.mode === 'Production' ? 'danger' : 'good') : 'warning',
            meta: [profile.provider_type, profile.submit_trigger].filter(Boolean).join(' · ') || 'No active profile',
            onClick: () => readiness.profile
                ? frappe.set_route('Form', 'Ledgix FBR Integration Profile', readiness.profile)
                : routeList('Ledgix FBR Integration Profile', {company: data.company}),
        });

        statusTile(grid, {
            icon: 'device',
            title: 'POS Device / POSID',
            status: device && device.active ? (device.operational_state || 'Configured') : 'Setup Required',
            tone: device && device.active && device.operational_state === 'Operational' ? 'good' : 'warning',
            meta: device ? [device.display_label || device.name, device.pos_id ? 'POSID ' + device.pos_id : null, device.transport_topology].filter(Boolean).join(' · ') : 'No active device',
            onClick: () => routeList('Ledgix FBR POS Device', {company: data.company}),
        });

        statusTile(grid, {
            icon: 'mapping',
            title: 'Mappings',
            status: state.mappingReady ? 'Ready' : 'Setup Required',
            tone: state.mappingReady ? 'good' : 'warning',
            meta: __('{0}/{1} items reviewed · {2} tax · {3} payment', [
                state.mapping.reviewed_item_mappings || 0,
                state.mapping.active_item_mappings || 0,
                state.mapping.active_tax_component_mappings || 0,
                state.mapping.payment_mappings || 0,
            ]),
            onClick: () => routeList('Ledgix FBR Item Mapping', {company: data.company}),
        });

        const blockerPanel = panel(workspace, 'Readiness', 'check');
        renderBlockers(blockerPanel, state);
    }

    function toggleSandboxNetwork(data, state, button) {
        const readiness = state.readiness;
        const gateOn = Boolean(readiness.network_cutover_active);
        const enabling = !gateOn;
        const confirmMessage = enabling
            ? __('Enable REAL FBR Sandbox networking for this site? Production cutover cannot be enabled by this action.')
            : __('Disable FBR Sandbox networking for this site?');

        frappe.confirm(confirmMessage, async () => {
            button.prop('disabled', true);
            try {
                const {message: result} = await frappe.call({
                    method: 'fbr_v1.api.center.set_sandbox_network_cutover',
                    args: {
                        company: data.company,
                        enabled: enabling ? 1 : 0,
                    },
                });

                if (result.production_cutover_active) {
                    frappe.throw(__('Safety interlock violation: Production transport must remain OFF.'));
                }

                sandboxActionResult = {
                    tone: result.network_cutover_active ? 'warning' : 'good',
                    title: result.network_cutover_active ? 'Sandbox network is live' : 'Sandbox network is off',
                    lines: [result.network_cutover_active ? 'Production remains locked.' : 'No FBR network action is enabled.'],
                };
                await refresh();
            } finally {
                button.prop('disabled', false);
            }
        });
    }

    function renderSandboxNetwork(data, state, parent) {
        const readiness = state.readiness;
        const gateOn = Boolean(readiness.network_cutover_active);
        const sandboxMode = readiness.mode === 'Sandbox';
        const canToggle = canManageCutover() && (sandboxMode || gateOn);

        const network = panel(parent, 'Network', 'shield', {
            className: 'lx-fbr-sandbox-network-panel',
            badge: {
                label: gateOn ? 'Sandbox Network ON' : 'Sandbox Network OFF',
                tone: gateOn ? 'warning' : 'good',
            },
        });

        factGrid(network, [
            {label: 'Sandbox Network', value: yesNo(gateOn), tone: gateOn ? 'warning' : 'good'},
            {label: 'Production Gate', value: yesNo(readiness.production_cutover_active), tone: readiness.production_cutover_active ? 'danger' : 'good'},
            {label: 'Production Posting', value: state.profile.production_post_armed ? 'ARMED' : 'LOCKED', tone: state.profile.production_post_armed ? 'danger' : 'good'},
            {label: 'Submit Mode', value: state.profile.submit_trigger || 'Not configured'},
        ]);

        if (gateOn) {
            notice(network, 'warning', 'Sandbox network is live', 'Only explicitly authorized Sandbox actions should be performed.');
        }

        const reason = !canManageCutover()
            ? __('System Manager permission is required.')
            : (!sandboxMode && !gateOn ? __('The active FBR profile must be in Sandbox mode.') : '');

        const row = $('<div class="lx-fbr-button-row"></div>').appendTo(network);
        const button = makeButton(
            gateOn ? 'Disable Sandbox Network' : 'Enable Sandbox Network',
            null,
            {
                primary: !gateOn,
                danger: gateOn,
                disabled: !canToggle,
                reason,
            }
        ).appendTo(row);

        if (canToggle) {
            button.on('click', () => toggleSandboxNetwork(data, state, button));
        }
    }

    function mountInvoiceControls(parent, data) {
        const fields = $('<div class="lx-fbr-invoice-fields"></div>').appendTo(parent);

        const typeHost = $('<div></div>').appendTo(fields);
        const typeControl = frappe.ui.form.make_control({
            parent: typeHost,
            df: {
                fieldname: 'sandbox_invoice_type',
                label: __('Invoice Type'),
                fieldtype: 'Select',
                options: 'Sales Invoice\nPOS Invoice',
                default: invoiceType,
            },
            render_input: true,
        });
        typeControl.refresh();
        typeControl.set_value(invoiceType);

        const invoiceHost = $('<div></div>').appendTo(fields);
        const invoiceControl = frappe.ui.form.make_control({
            parent: invoiceHost,
            df: {
                fieldname: 'sandbox_invoice',
                label: __('Invoice'),
                fieldtype: 'Link',
                options: invoiceType,
                default: invoiceName,
            },
            render_input: true,
        });
        invoiceControl.refresh();
        if (invoiceName) invoiceControl.set_value(invoiceName);

        typeControl.df.change = () => {
            const value = typeControl.get_value() || 'POS Invoice';
            if (value !== invoiceType) {
                invoiceType = value;
                invoiceName = '';
                sandboxActionResult = null;
                render(data);
            }
        };

        invoiceControl.df.change = () => {
            const value = invoiceControl.get_value() || '';
            if (value !== invoiceName) {
                invoiceName = value;
                sandboxActionResult = null;
                render(data);
            }
        };
    }

    function renderSandboxActionResult(parent) {
        if (!sandboxActionResult) return;
        const result = $('<div class="lx-fbr-inline-result"></div>')
            .addClass('is-' + sandboxActionResult.tone)
            .appendTo(parent);
        $('<strong></strong>').text(__(sandboxActionResult.title)).appendTo(result);
        (sandboxActionResult.lines || []).forEach((line) => $('<span></span>').text(line).appendTo(result));
    }

    async function checkInvoiceReadiness(data, button) {
        if (!invoiceName) return;

        button.prop('disabled', true);
        try {
            const {message: result} = await frappe.call({
                method: 'fbr_v1.api.fiscalization.invoice_readiness',
                args: {
                    reference_doctype: invoiceType,
                    reference_name: invoiceName,
                },
            });

            const errors = uniq([...(result.errors || []), ...(result.network_blockers || [])]);
            sandboxActionResult = errors.length
                ? {
                    tone: 'warning',
                    title: 'Invoice not ready',
                    lines: errors,
                    ready_for_fiscalize: false,
                }
                : {
                    tone: 'good',
                    title: 'Invoice ready',
                    lines: ['Readiness passed. Sandbox fiscalization is available while all safety gates remain valid.'],
                    ready_for_fiscalize: true,
                };
            render(data);
        } finally {
            button.prop('disabled', false);
        }
    }

    function fiscalizeSandboxInvoice(data, state, button) {
        if (!invoiceName) return;

        frappe.confirm(
            __('This performs one REAL FBR Sandbox POST for the selected invoice. Production remains locked. Continue?'),
            async () => {
                button.prop('disabled', true);
                try {
                    const {message: result} = await frappe.call({
                        method: 'fbr_v1.api.fiscalization.submit_invoice',
                        args: {
                            reference_doctype: invoiceType,
                            reference_name: invoiceName,
                        },
                    });

                    const status = result.status || 'Completed';
                    const normalized = String(status).toLowerCase();
                    const tone = normalized.includes('fail') || normalized.includes('reject')
                        ? 'danger'
                        : (normalized.includes('reconciliation') || normalized.includes('ambiguous') ? 'warning' : 'good');

                    sandboxActionResult = {
                        tone,
                        title: status,
                        lines: result.errors || [],
                    };
                    await refresh();
                } finally {
                    button.prop('disabled', false);
                }
            }
        );
    }

    function mountProductionInvoiceControls(parent, data) {
        const fields = $('<div class="lx-fbr-invoice-fields"></div>').appendTo(parent);

        const typeHost = $('<div></div>').appendTo(fields);
        const typeControl = frappe.ui.form.make_control({
            parent: typeHost,
            df: {
                fieldname: 'production_invoice_type',
                label: __('Invoice Type'),
                fieldtype: 'Select',
                options: 'Sales Invoice\nPOS Invoice',
                default: productionInvoiceType,
            },
            render_input: true,
        });
        typeControl.refresh();
        typeControl.set_value(productionInvoiceType);

        const invoiceHost = $('<div></div>').appendTo(fields);
        const invoiceControl = frappe.ui.form.make_control({
            parent: invoiceHost,
            df: {
                fieldname: 'production_invoice',
                label: __('Invoice'),
                fieldtype: 'Link',
                options: productionInvoiceType,
                default: productionInvoiceName,
            },
            render_input: true,
        });
        invoiceControl.refresh();
        if (productionInvoiceName) {
            invoiceControl.set_value(productionInvoiceName);
        }

        typeControl.df.change = () => {
            const value = typeControl.get_value() || 'POS Invoice';
            if (value !== productionInvoiceType) {
                productionInvoiceType = value;
                productionInvoiceName = '';
                productionActionResult = null;
                render(data);
            }
        };

        invoiceControl.df.change = () => {
            const value = invoiceControl.get_value() || '';
            if (value !== productionInvoiceName) {
                productionInvoiceName = value;
                productionActionResult = null;
                render(data);
            }
        };
    }

    function renderProductionActionResult(parent) {
        if (!productionActionResult) return;

        const result = $('<div class="lx-fbr-inline-result"></div>')
            .addClass('is-' + productionActionResult.tone)
            .appendTo(parent);

        $('<strong></strong>')
            .text(__(productionActionResult.title))
            .appendTo(result);

        (productionActionResult.lines || []).forEach((line) => {
            $('<span></span>').text(line).appendTo(result);
        });
    }

    async function checkProductionInvoiceReadiness(data, button) {
        if (!productionInvoiceName) return;

        button.prop('disabled', true);
        try {
            const {message: result} = await frappe.call({
                method: 'fbr_v1.api.fiscalization.invoice_readiness',
                args: {
                    reference_doctype: productionInvoiceType,
                    reference_name: productionInvoiceName,
                },
            });

            const errors = uniq([
                ...(result.errors || []),
                ...(result.network_blockers || []),
            ]);

            productionActionResult = errors.length
                ? {
                    tone: 'warning',
                    title: 'Production invoice not ready',
                    lines: errors,
                    ready_for_fiscalize: false,
                }
                : {
                    tone: 'good',
                    title: 'Production invoice ready',
                    lines: [
                        'Invoice and all Production safety gates passed readiness.',
                        'Fiscalize Production Invoice is now available for one explicit POST.',
                    ],
                    ready_for_fiscalize: true,
                };

            render(data);
        } finally {
            button.prop('disabled', false);
        }
    }

    function fiscalizeProductionInvoice(data, state, button) {
        if (!productionInvoiceName) return;

        const reference = productionInvoiceType + ' ' + productionInvoiceName;

        frappe.confirm(
            __(
                'This performs one REAL FBR Production POST for {0}. '
                + 'Do not continue unless this exact invoice is authorized. Continue?',
                [reference]
            ),
            async () => {
                button.prop('disabled', true);

                try {
                    const {message: result} = await frappe.call({
                        method: 'fbr_v1.api.fiscalization.submit_invoice',
                        args: {
                            reference_doctype: productionInvoiceType,
                            reference_name: productionInvoiceName,
                        },
                    });

                    const status = result.status || 'Completed';
                    const normalized = String(status).toLowerCase();

                    const tone =
                        normalized.includes('fail')
                        || normalized.includes('reject')
                            ? 'danger'
                            : (
                                normalized.includes('reconciliation')
                                || normalized.includes('ambiguous')
                                    ? 'warning'
                                    : 'good'
                            );

                    const lines = [];

                    if (result.invoice_number) {
                        lines.push(
                            __('FBR Invoice Number: {0}', [result.invoice_number])
                        );
                    }

                    if (result.network_call === true) {
                        lines.push(__('FBR network call attempted.'));
                    } else if (result.network_call === false) {
                        lines.push(__('No FBR network call was made.'));
                    }

                    (result.errors || []).forEach((message) => {
                        lines.push(message);
                    });

                    productionActionResult = {
                        tone,
                        title: status,
                        lines,
                        ready_for_fiscalize: false,
                    };

                    await refresh();
                } finally {
                    button.prop('disabled', false);
                }
            }
        );
    }

    function renderLatestSubmission(parent, data) {
        const latest = data.latest_submission;
        const evidence = panel(parent, 'Latest Submission / Evidence', 'evidence', {
            className: 'lx-fbr-latest-evidence',
            badge: latest ? {label: latest.fbr_status || 'Unknown', tone: latest.reconciliation_required ? 'warning' : (latest.transport_outcome === 'Accepted' ? 'good' : 'neutral')} : null,
        });

        if (!latest) {
            notice(evidence, 'good', 'No submission evidence yet', 'No company device submission log is currently available.');
            buttonRow(evidence, [
                {label: 'Open Submission Logs', onClick: () => routeList('Ledgix FBR Submission Log')},
            ]);
            return;
        }

        factGrid(evidence, [
            {label: 'Reference', value: [latest.reference_doctype, latest.reference_name].filter(Boolean).join(' · ')},
            {label: 'FBR Status', value: latest.fbr_status},
            {label: 'FBR Invoice Number', value: latest.fbr_invoice_number},
            {label: 'Reconciliation', value: latest.reconciliation_required ? 'Required' : 'No', tone: latest.reconciliation_required ? 'warning' : 'good'},
        ]);

        const technical = $('<details class="lx-fbr-advanced lx-fbr-evidence-details"></details>').appendTo(evidence);
        $('<summary></summary>').text(__('Technical evidence')).appendTo(technical);
        const technicalContent = $('<div class="lx-fbr-advanced-content"></div>').appendTo(technical);
        factGrid(technicalContent, [
            {label: 'Transport Outcome', value: latest.transport_outcome},
            {label: 'Attempt ID', value: latest.attempt_id},
            {label: 'Transport Started', value: latest.transport_started_at},
            {label: 'Transport Finished', value: latest.transport_finished_at},
            {label: 'Request Hash', value: latest.request_hash},
            {label: 'Snapshot Hash', value: latest.source_snapshot_hash},
        ]);

        if (latest.error_code || latest.error_message) {
            notice(evidence, 'warning', latest.error_code || 'Submission issue', latest.error_message || '');
        }

        buttonRow(evidence, [
            {label: 'Open Submission Log', onClick: () => frappe.set_route('Form', 'Ledgix FBR Submission Log', latest.name)},
            {label: 'All Submission Logs', onClick: () => routeList('Ledgix FBR Submission Log')},
        ]);
    }

    function renderSandboxAdvanced(data, state, parent) {
        const localDevices = (data.devices || []).filter((device) => device.transport_topology === 'Local IMS - Server Reachable');
        if (!localDevices.length) return;

        const details = $('<details class="lx-fbr-advanced"></details>').appendTo(parent);
        $('<summary></summary>').text(__('Advanced diagnostics')).appendTo(details);
        const content = $('<div class="lx-fbr-advanced-content"></div>').appendTo(details);

        const canHealth = canOperate() && state.readiness.network_cutover_active;
        buttonRow(content, [
            {
                label: 'Local IMS Health',
                disabled: !canHealth,
                reason: !state.readiness.network_cutover_active ? __('Sandbox network is OFF.') : __('Accounts Manager permission is required.'),
                onClick: () => actionDialog(
                    'Local IMS Health',
                    [{
                        fieldname: 'pos_device',
                        label: __('POS Device'),
                        fieldtype: 'Link',
                        options: 'Ledgix FBR POS Device',
                        reqd: 1,
                        default: localDevices[0].name,
                    }],
                    'fbr_v1.api.center.test_local_ims_health',
                    (result) => result.ok ? __('Local IMS health check succeeded') : (result.error || __('Local IMS health check failed'))
                ),
            },
        ]);
    }

    function renderSandbox(data, state, workspace) {
        const readiness = state.readiness;
        const profile = state.profile;
        const device = pickDevice(data, 'Sandbox');

        const topGrid = $('<div class="lx-fbr-sandbox-top-grid"></div>').appendTo(workspace);
        const environment = panel(topGrid, 'Sandbox Environment', 'sandbox', {
            className: 'lx-fbr-sandbox-summary-panel',
            badge: {label: readiness.mode === 'Sandbox' ? 'Active' : 'Not Active', tone: readiness.mode === 'Sandbox' ? 'good' : 'warning'},
        });

        factGrid(environment, [
            {label: 'Device', value: device && (device.display_label || device.name)},
            {label: 'POSID', value: device && device.pos_id},
            {label: 'Topology', value: device && device.transport_topology},
            {label: 'Device State', value: device && device.operational_state},
        ]);

        if (readiness.mode !== 'Sandbox') {
            notice(environment, 'warning', 'Sandbox profile is not active', 'Sandbox network and submission controls remain unavailable until the active profile is Sandbox.');
        }

        renderSandboxNetwork(data, state, topGrid);

        const invoice = panel(workspace, 'Invoice Test', 'invoice', {
            className: 'lx-fbr-invoice-test-panel',
        });
        mountInvoiceControls(invoice, data);

        const productionSafe = !readiness.production_cutover_active && !profile.production_post_armed;
        const readinessPassed = Boolean(
            sandboxActionResult && sandboxActionResult.ready_for_fiscalize
        );
        const canFiscalize = canOperate()
            && readiness.enabled
            && readiness.mode === 'Sandbox'
            && readiness.sandbox_configuration_ready
            && Boolean(profile.transport_enabled)
            && readiness.network_cutover_active
            && productionSafe
            && readinessPassed
            && Boolean(invoiceName);

        const canCheck = Boolean(invoiceName);
        const actions = $('<div class="lx-fbr-button-row"></div>').appendTo(invoice);

        const readinessButton = makeButton(
            'Check Readiness',
            null,
            {
                primary: true,
                disabled: !canCheck,
                reason: canCheck ? '' : __('Select an invoice first.'),
            }
        ).appendTo(actions);
        if (canCheck) readinessButton.on('click', () => checkInvoiceReadiness(data, readinessButton));

        let fiscalizeReason = '';
        if (!invoiceName) {
            fiscalizeReason = __('Select an invoice first.');
        } else if (!canOperate()) {
            fiscalizeReason = __('Accounts Manager permission is required.');
        } else if (!readiness.enabled || readiness.mode !== 'Sandbox') {
            fiscalizeReason = __('The active FBR profile must be Sandbox.');
        } else if (!readiness.sandbox_configuration_ready || !profile.transport_enabled) {
            fiscalizeReason = __('Sandbox configuration is not ready.');
        } else if (!readiness.network_cutover_active) {
            fiscalizeReason = __('Sandbox network is OFF.');
        } else if (!productionSafe) {
            fiscalizeReason = __('Production must remain fully locked.');
        } else if (!readinessPassed) {
            fiscalizeReason = __('Run Check Readiness first.');
        }

        const fiscalizeButton = makeButton(
            'Fiscalize Invoice',
            null,
            {
                disabled: !canFiscalize,
                reason: fiscalizeReason,
            }
        ).appendTo(actions);
        if (canFiscalize) fiscalizeButton.on('click', () => fiscalizeSandboxInvoice(data, state, fiscalizeButton));

        renderSandboxActionResult(invoice);
        renderLatestSubmission(workspace, data);
        renderSandboxAdvanced(data, state, workspace);
    }

    function renderSetup(data, state, workspace) {
        const setup = panel(workspace, 'Setup', 'setup');
        const grid = $('<div class="lx-fbr-action-grid"></div>').appendTo(setup);

        actionTile(grid, {
            icon: 'profile',
            title: 'Integration Profile',
            meta: state.readiness.profile ? [state.profile.provider_type, state.readiness.mode].filter(Boolean).join(' · ') : 'Not configured',
            status: state.readiness.profile ? state.readiness.mode : 'Required',
            tone: state.readiness.profile ? (state.readiness.mode === 'Production' ? 'danger' : 'good') : 'warning',
            onClick: () => state.readiness.profile
                ? frappe.set_route('Form', 'Ledgix FBR Integration Profile', state.readiness.profile)
                : routeList('Ledgix FBR Integration Profile', {company: data.company}),
        });

        actionTile(grid, {
            icon: 'device',
            title: 'POS Devices',
            meta: __('{0} configured', [(data.devices || []).length]),
            onClick: () => routeList('Ledgix FBR POS Device', {company: data.company}),
        });

        actionTile(grid, {
            icon: 'mapping',
            title: 'Item Mapping',
            meta: __('{0}/{1} reviewed', [state.mapping.reviewed_item_mappings || 0, state.mapping.active_item_mappings || 0]),
            status: state.mappingReady ? 'Ready' : 'Review',
            tone: state.mappingReady ? 'good' : 'warning',
            onClick: () => routeList('Ledgix FBR Item Mapping', {company: data.company}),
        });

        actionTile(grid, {
            icon: 'mapping',
            title: 'Tax Component Mapping',
            meta: __('{0} active', [state.mapping.active_tax_component_mappings || 0]),
            onClick: () => routeList('Ledgix FBR Tax Component Mapping', {company: data.company}),
        });

        actionTile(grid, {
            icon: 'mapping',
            title: 'Payment Mapping',
            meta: __('{0} mapped', [state.mapping.payment_mappings || 0]),
            onClick: () => routeList('Mode of Payment'),
        });
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
                        frappe.msgprint({
                            title: __(title),
                            message: frappe.utils.escape_html(resultText(result)),
                        });
                        dialog.hide();
                        await refresh();
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

    function renderAdvancedEvidence(parent) {
        if (!canOperate()) return;

        const details = $('<details class="lx-fbr-advanced"></details>').appendTo(parent);
        $('<summary></summary>').text(__('Advanced evidence actions')).appendTo(details);
        const content = $('<div class="lx-fbr-advanced-content"></div>').appendTo(details);
        notice(content, 'warning', 'Audit / evidence writes', 'These actions create compliance evidence records but do not enable network or Production cutover.');

        const deviceField = () => ({
            fieldname: 'pos_device',
            label: __('POS Device'),
            fieldtype: 'Link',
            options: 'Ledgix FBR POS Device',
            reqd: 1,
        });
        const externalFields = () => [
            {fieldname: 'external_reference', label: __('Authoritative External Reference'), fieldtype: 'Data', reqd: 1},
            {fieldname: 'external_evidence', label: __('External Evidence'), fieldtype: 'Attach', reqd: 1},
        ];

        buttonRow(content, [
            {
                label: 'Record Device Event',
                onClick: () => actionDialog(
                    'Record Device Event',
                    [deviceField(), {fieldname: 'event_type', label: __('Event'), fieldtype: 'Select', options: 'Startup\nShutdown\nConnectivity Failure\nSoftware Failure\nPower Failure\nRestoration', reqd: 1}],
                    'fbr_v1.api.fbr_offline.record_device_event',
                    (result) => __('Event recorded: {0}', [result.event])
                ),
            },
            {
                label: 'Generate Internal Closing',
                onClick: () => actionDialog(
                    'Generate Internal Closing',
                    [deviceField(), {fieldname: 'period_type', label: __('Period'), fieldtype: 'Select', options: 'Daily\nWeekly\nMonthly', reqd: 1}, {fieldname: 'date', label: __('Date in completed period'), fieldtype: 'Date', reqd: 1}],
                    'fbr_v1.services.fiscal_closing.generate_closing',
                    (result) => __('Internal closing: {0}', [result.name])
                ),
            },
            {
                label: 'Record External Compliance Evidence',
                onClick: () => actionDialog(
                    'Record External Compliance Evidence',
                    [deviceField(), {fieldname: 'event_type', label: __('Event'), fieldtype: 'Select', options: 'Outage Report Filed\nAlert Report Filed\nOffline Upload Confirmed\nCorrection Filed\nCommissioner Approval Recorded', reqd: 1}, ...externalFields(), ...invoiceFields().map((field) => ({...field, reqd: 0, ...(field.fieldname === 'reference_doctype' ? {options: '\nSales Invoice\nPOS Invoice'} : {})})), {fieldname: 'occurred_at', label: __('External Event Time'), fieldtype: 'Datetime'}],
                    'fbr_v1.api.compliance_evidence.record_external_compliance_evidence',
                    (result) => __('Evidence recorded; invoice unchanged: {0}', [result.event])
                ),
            },
            {
                label: 'Record Offline Upload Confirmation',
                onClick: () => actionDialog(
                    'Record Offline Upload Confirmation',
                    [...invoiceFields(), ...externalFields(), {fieldname: 'fbr_invoice_number', label: __('Official FBR Invoice Number'), fieldtype: 'Data', reqd: 1}],
                    'fbr_v1.api.fbr_offline.record_offline_upload_confirmation',
                    (result) => result.status + ' · ' + (result.confirmed_after_deadline ? __('Recorded after deadline') : __('Recorded within deadline'))
                ),
            },
            {
                label: 'Create Correction Request',
                onClick: () => actionDialog(
                    'Create Correction Request',
                    [...invoiceFields(), {fieldname: 'action_type', label: __('Action'), fieldtype: 'Select', options: 'Cancel\nDelete\nEdit', reqd: 1}, {fieldname: 'reason', label: __('Bona-fide Reason'), fieldtype: 'Small Text', reqd: 1}, {fieldname: 'fbr_generated_at', label: __('Authoritative FBR Generation Time'), fieldtype: 'Datetime'}, {fieldname: 'generation_time_reference', label: __('Generation Time Authority Reference'), fieldtype: 'Data'}, {fieldname: 'generation_time_evidence', label: __('Generation Time Evidence'), fieldtype: 'Attach'}],
                    'fbr_v1.api.corrections.request_correction',
                    (result) => result.name + ' · ' + result.status
                ),
            },
            {
                label: 'Record Correction Result',
                onClick: () => actionDialog(
                    'Record Correction Result',
                    [{fieldname: 'correction_request', label: __('Correction Request'), fieldtype: 'Link', options: 'Ledgix FBR Correction Request', reqd: 1}, {fieldname: 'status', label: __('Externally Confirmed Result'), fieldtype: 'Select', options: 'Completed\nRejected', reqd: 1}, {fieldname: 'board_reference', label: __('Board / PRAL Reference'), fieldtype: 'Data', reqd: 1}, {fieldname: 'external_evidence', label: __('External Evidence'), fieldtype: 'Attach', reqd: 1}, {fieldname: 'commissioner_approval_reference', label: __('Commissioner Approval Reference'), fieldtype: 'Data'}],
                    'fbr_v1.api.corrections.record_correction_result',
                    (result) => result.name + ' · ' + result.status
                ),
            },
        ]);
    }

    function renderEvidence(data, state, workspace) {
        const evidence = panel(workspace, 'Evidence & Compliance', 'evidence');
        const grid = $('<div class="lx-fbr-action-grid"></div>').appendTo(evidence);

        actionTile(grid, {
            icon: 'evidence',
            title: 'Submission Logs',
            meta: data.latest_submission ? (data.latest_submission.reference_name || data.latest_submission.name) : 'No recent company-device log',
            onClick: () => routeList('Ledgix FBR Submission Log'),
        });
        actionTile(grid, {
            icon: 'activity',
            title: 'Fiscal Events',
            onClick: () => routeList('Ledgix FBR Fiscal Event Log'),
        });
        actionTile(grid, {
            icon: 'alert',
            title: 'Reconciliation',
            onClick: () => routeList('Ledgix FBR Submission Log', {fbr_status: 'Reconciliation Required'}),
        });
        actionTile(grid, {
            icon: 'evidence',
            title: 'Fiscal Closings',
            onClick: () => routeList('Ledgix FBR Fiscal Closing'),
        });
        actionTile(grid, {
            icon: 'evidence',
            title: 'Correction Requests',
            onClick: () => routeList('Ledgix FBR Correction Request'),
        });

        renderAdvancedEvidence(evidence);
    }

    function renderProduction(data, state, workspace) {
        const readiness = state.readiness;
        const profile = state.profile;
        const production = readiness.configuration && readiness.configuration.production
            ? readiness.configuration.production
            : {};

        const productionLive = Boolean(
            readiness.network_cutover_active
            && readiness.production_cutover_active
            && profile.production_post_armed
        );

        const locked = !productionLive;

        const productionPanel = panel(workspace, 'Production', 'production', {
            className: 'lx-fbr-production-panel',
            badge: {
                label: locked ? 'LOCKED' : 'LIVE',
                tone: locked ? 'good' : 'danger',
            },
        });

        notice(
            productionPanel,
            locked ? 'good' : 'danger',
            locked ? 'Production transport is locked' : 'REAL FBR Production transport is LIVE',
            locked
                ? 'Production cutover cannot be enabled from FBR V1 Center.'
                : 'Only the explicitly selected and authorized invoice should be fiscalized.'
        );

        factGrid(productionPanel, [
            {
                label: 'General Network',
                value: yesNo(readiness.network_cutover_active),
                tone: readiness.network_cutover_active ? 'danger' : 'good',
            },
            {
                label: 'Production Gate',
                value: yesNo(readiness.production_cutover_active),
                tone: readiness.production_cutover_active ? 'danger' : 'good',
            },
            {
                label: 'Posting Armed',
                value: yesNo(profile.production_post_armed),
                tone: profile.production_post_armed ? 'danger' : 'good',
            },
            {
                label: 'Current Profile',
                value: readiness.mode || 'Disabled',
            },
            {
                label: 'Configuration',
                value: readiness.production_configuration_ready ? 'Ready' : 'Not Ready',
            },
        ]);

        // Only actual Production configuration blockers belong here.
        // Unresolved optional/unsupported contracts are not presented as
        // client setup requirements.
        const productionBlockers = uniq(production.blockers || []);

        if (productionBlockers.length) {
            const requirements = $('<details class="lx-fbr-requirements"></details>')
                .appendTo(productionPanel);

            const summary = $('<summary></summary>').appendTo(requirements);

            $('<strong></strong>')
                .text(__('Production readiness requirements'))
                .appendTo(summary);

            badge(
                __('{0} open', [productionBlockers.length]),
                'warning'
            ).appendTo(summary);

            const list = $('<ul></ul>').appendTo(requirements);
            productionBlockers.forEach((message) => {
                $('<li></li>').text(message).appendTo(list);
            });
        }

        buttonRow(productionPanel, [
            {
                label: 'Integration Profile',
                onClick: () => readiness.profile
                    ? frappe.set_route(
                        'Form',
                        'Ledgix FBR Integration Profile',
                        readiness.profile
                    )
                    : routeList(
                        'Ledgix FBR Integration Profile',
                        {company: data.company}
                    ),
            },
            {
                label: 'Devices',
                onClick: () => routeList(
                    'Ledgix FBR POS Device',
                    {
                        company: data.company,
                        environment: 'Production',
                    }
                ),
            },
        ]);

        const invoice = panel(
            workspace,
            'Production Invoice',
            'invoice',
            {className: 'lx-fbr-invoice-test-panel'}
        );

        if (productionLive) {
            notice(
                invoice,
                'danger',
                'Production network is live',
                'Selecting an invoice does not send it. '
                + 'Only Fiscalize Production Invoice performs the explicit POST.'
            );
        } else {
            notice(
                invoice,
                'warning',
                'Production POST remains blocked',
                'The general network gate, Production gate, and posting arm '
                + 'must all be active before fiscalization.'
            );
        }

        mountProductionInvoiceControls(invoice, data);

        const readinessPassed = Boolean(
            productionActionResult
            && productionActionResult.ready_for_fiscalize
        );

        const canCheck = Boolean(productionInvoiceName)
            && readiness.mode === 'Production';

        const canFiscalize = Boolean(
            canOperate()
            && readiness.enabled
            && readiness.mode === 'Production'
            && readiness.production_configuration_ready
            && profile.transport_enabled
            && readiness.network_cutover_active
            && readiness.production_cutover_active
            && profile.production_post_armed
            && readinessPassed
            && productionInvoiceName
        );

        const actions = $('<div class="lx-fbr-button-row"></div>').appendTo(invoice);

        const readinessButton = makeButton(
            'Check Readiness',
            null,
            {
                primary: true,
                disabled: !canCheck,
                reason: canCheck
                    ? ''
                    : __('Select a Production invoice first.'),
            }
        ).appendTo(actions);

        if (canCheck) {
            readinessButton.on(
                'click',
                () => checkProductionInvoiceReadiness(
                    data,
                    readinessButton
                )
            );
        }

        let fiscalizeReason = '';

        if (!productionInvoiceName) {
            fiscalizeReason = __('Select an invoice first.');
        } else if (!canOperate()) {
            fiscalizeReason = __('Accounts Manager permission is required.');
        } else if (!readiness.enabled || readiness.mode !== 'Production') {
            fiscalizeReason = __('The active FBR profile must be Production.');
        } else if (
            !readiness.production_configuration_ready
            || !profile.transport_enabled
        ) {
            fiscalizeReason = __('Production configuration is not ready.');
        } else if (!readiness.network_cutover_active) {
            fiscalizeReason = __('General FBR network gate is OFF.');
        } else if (!readiness.production_cutover_active) {
            fiscalizeReason = __('Production network gate is OFF.');
        } else if (!profile.production_post_armed) {
            fiscalizeReason = __('Production posting is not armed.');
        } else if (!readinessPassed) {
            fiscalizeReason = __('Run Check Readiness first.');
        }

        const fiscalizeButton = makeButton(
            'Fiscalize Production Invoice',
            null,
            {
                danger: true,
                disabled: !canFiscalize,
                reason: fiscalizeReason,
            }
        ).appendTo(actions);

        if (canFiscalize) {
            fiscalizeButton.on(
                'click',
                () => fiscalizeProductionInvoice(
                    data,
                    state,
                    fiscalizeButton
                )
            );
        }

        renderProductionActionResult(invoice);
        renderLatestSubmission(workspace, data);
    }

    function renderWorkspace(data, state) {
        const workspace = $('<main class="lx-fbr-workspace" role="tabpanel"></main>').appendTo(body);

        if (activeTab === 'sandbox') renderSandbox(data, state, workspace);
        else if (activeTab === 'setup') renderSetup(data, state, workspace);
        else if (activeTab === 'evidence') renderEvidence(data, state, workspace);
        else if (activeTab === 'production') renderProduction(data, state, workspace);
        else renderOverview(data, state, workspace);
    }

    function render(data) {
        lastData = data;
        const state = deriveState(data);
        body.empty();
        renderHeader(data, state);
        renderTabs(data);
        renderWorkspace(data, state);
    }

    async function refresh(companyName) {
        if (busy) return;

        busy = true;
        body.addClass('is-loading');
        try {
            const {message: data} = await frappe.call({
                method: 'fbr_v1.api.center.get_center_boot',
                args: {company: companyName || currentCompany},
            });
            currentCompany = data.company;
            render(data);
        } finally {
            busy = false;
            body.removeClass('is-loading');
        }
    }

    $(wrapper).find('.page-head').attr('aria-hidden', 'true');
    refresh();
};
