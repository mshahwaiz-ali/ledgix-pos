frappe.pages['ledgix-pos'].on_page_load = function(wrapper) {

	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Ledgix POS',
		single_column: true
	});

	// ============================================================
	// POS PAGE SHELL CLEANUP
	// ============================================================
	$(wrapper)
		.closest('.page-container')
		.find('.page-head, .page-head-content, .page-title, .title-area')
		.hide();

	$(wrapper)
		.closest('.layout-main-section, .layout-main-section-wrapper, .page-body')
		.addClass('ledgix-pos-page-shell');

	let active_shift = null;
	let all_items = [];
	let categories = [];
	let payment_methods = [];
	let selected_category = 'All';
	let selected_payment_method = 'Cash';
	let cart = [];
	let visible_product_items = [];
	let discount_type = 'Amount';
	let split_payment_enabled = false;
	let split_payments = {};
	let split_payment_methods = ['Cash', 'Card', 'JazzCash', 'EasyPaisa', 'Bank Transfer'];
	let sale_processing = false;
	let pos_tax_preview = null;
	let current_tax_amount = 0;
	let current_grand_total = 0;
	let tax_preview_timer = null;
	let tax_preview_in_flight = false;
	let tax_preview_promise = null;
	let last_tax_preview_signature = '';
	let applied_tax_preview_signature = '';
	let recent_receipts_limit = 10;
	let recent_receipts_offset = 0;
	let recent_receipts_total = 0;
	let recent_receipts_loading = false;
	let selected_receipt_ids = {};
	let ledgix_pos_theme = 'light';
	let pos_stock_visibility = 'show';
	let stock_control_mode = 'Strict Inventory';
	let single_paid_amount = 0;
	let current_checkout_client_sale_id = '';
	

	$(page.body).html(`
		<div class="ledgix-pos-app">

			<div class="pos-shift-lock hidden">
				<div class="shift-lock-card">
					<div class="shift-lock-icon">
						<svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<rect x="3" y="11" width="18" height="10" rx="2"></rect>
							<path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
						</svg>
					</div>
					<div class="shift-lock-title">Open Shift Required</div>
					<div class="shift-lock-text">Start cashier shift before using POS.</div>
					<button class="shift-lock-open-btn">Open Shift</button>
				</div>
			</div>

			<div class="ledgix-pos-header-deck">

				<div class="shift-card ledgix-shift-status-bar pos-control-card pos-shift-card">
					<div class="pos-shift-main">
						<div class="shift-label">Active Shift</div>
						<div class="shift-value">Checking...</div>
					</div>

					<div class="pos-shift-badge-stack" style="visibility: hidden;">
						<div class="shift-badge warning">Required</div>
						<div class="pos-mode-badge inventory">Inventory Mode</div>
					</div>
				</div>

				<div class="pos-control-card ledgix-pos-brand pos-brand-card">
					<div class="brand-title">Ledgix POS</div>
					<div class="brand-subtitle">Retail Checkout</div>
				</div>

				<div class="pos-control-card ledgix-pos-top-actions pos-utility-card">
					<div class="shortcut-help-wrap">
						<button class="pos-top-btn pos-icon-btn shortcut-help-btn" type="button" title="Keyboard Shortcuts">
							<svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<rect x="3" y="6" width="18" height="12" rx="3"></rect>
								<path d="M7 10h.01"></path>
								<path d="M10 10h.01"></path>
								<path d="M13 10h.01"></path>
								<path d="M16 10h.01"></path>
								<path d="M8 14h8"></path>
							</svg>
						</button>
						<div class="shortcut-help-menu">
							<div class="shortcut-help-title">Keyboard Shortcuts</div>
							<div><kbd>Enter</kbd><span>Add / Search scanned item</span></div>
							<div><kbd>F4</kbd><span>Complete Sale</span></div>
							<div><kbd>F6</kbd><span>Hold Sale</span></div>
							<div><kbd>F7</kbd><span>Held Sales</span></div>
							<div><kbd>F8</kbd><span>Return</span></div>
							<div><kbd>Esc</kbd><span>Clear search</span></div>
						</div>
					</div>

					<button class="pos-top-btn pos-icon-btn recent-receipts-btn" type="button" title="Recent Receipts">
						<svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
							<path d="M4 3h16v18l-3-2-3 2-3-2-3 2-4-2V3z"></path>
							<path d="M8 7h8"></path>
							<path d="M8 11h8"></path>
							<path d="M8 15h5"></path>
						</svg>
					</button>

					<button class="pos-top-btn smart-shift-btn shift-open-btn" type="button">
						<span class="smart-shift-icon"></span>
						<span class="smart-shift-text">Open Shift</span>
					</button>
				</div>
			</div>

			<div class="ledgix-pos-operational-strip">

				<div class="pos-op-card ledgix-pos-search pos-search-card">
					<div class="ledgix-search-wrapper">
						<input type="text" placeholder="Scan barcode / SKU / Search item" class="ledgix-pos-search-input" autofocus />
						<button class="ledgix-search-clear-btn hidden" type="button" title="Clear search">×</button>

						<button class="ledgix-scan-btn" type="button" title="Scan / Camera barcode">
							<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M3 7V5a2 2 0 0 1 2-2h2"></path>
								<path d="M17 3h2a2 2 0 0 1 2 2v2"></path>
								<path d="M21 17v2a2 2 0 0 1-2 2h-2"></path>
								<path d="M7 21H5a2 2 0 0 1-2-2v-2"></path>
								<line x1="7" y1="12" x2="17" y2="12"></line>
							</svg>
						</button>
					</div>
				</div>

				<div class="pos-op-card pos-shift-metric-card">
					<div class="pos-metric-label">Shift Invoices</div>
					<div class="pos-metric-value shift-invoices-value">0</div>
				</div>

				<div class="pos-op-card pos-shift-metric-card">
					<div class="pos-metric-label">Shift Sales</div>
					<div class="pos-metric-value shift-sales-value">Rs. 0</div>
				</div>
			</div>


			<div class="ledgix-pos-layout">

				<div class="ledgix-pos-panel ledgix-pos-left">
					<div class="panel-header">
						<div>
							<div class="panel-title">Products Workspace</div>
							<div class="panel-subtitle">Search, scan, and add items directly</div>
						</div>
					</div>

					<div class="ledgix-pos-categories"></div>
					<div class="ledgix-product-grid"></div>
				</div>

				<div class="ledgix-pos-panel ledgix-pos-right ledgix-order-drawer">
					<div class="panel-header cart-header">
						<div>
							<div class="panel-title">Current Order</div>
							<div class="panel-subtitle order-context-line">
								<span class="order-shift-value">No active shift</span>
								<span class="order-cashier-value">${safe_text(frappe.session && frappe.session.user ? frappe.session.user : 'Cashier')}</span>
							</div>
						</div>

						<button class="clear-cart-btn">Clear</button>
					</div>

					<div class="cart-table-head">
						<div>Item</div>
						<div>Qty</div>
						<div>Rate</div>
						<div>Total</div>
						<div></div>
					</div>

					<div class="ledgix-cart-list"></div>

					<div class="order-drawer-bottom">
						<div class="summary-card">
							<div class="panel-title">Order Summary</div>

							<div class="summary-row">
								<span>Subtotal</span>
								<strong class="subtotal-value">Rs. 0</strong>
							</div>

							<div class="discount-box">
								<div class="discount-top">
									<span>Discount</span>
									<div class="discount-toggle">
										<button class="discount-type-btn active" data-type="Amount">Rs</button>
										<button class="discount-type-btn" data-type="Percent">%</button>
									</div>
								</div>
								<input type="number" class="discount-input" value="0" min="0" />
							</div>

							<div class="summary-row">
								<span>Tax</span>
								<strong class="tax-value">Rs. 0</strong>
							</div>

							<div class="summary-row grand-total">
								<span>Total</span>
								<strong class="total-value">Rs. 0</strong>
							</div>

							<div class="summary-row small">
								<span>Paid</span>
								<strong class="paid-value">Rs. 0</strong>
							</div>

							<div class="summary-row small">
								<span>Remaining</span>
								<strong class="remaining-value">Rs. 0</strong>
							</div>

							<div class="summary-row small">
								<span>Change</span>
								<strong class="change-value">Rs. 0</strong>
							</div>
						</div>

						<div class="pos-action-stack">
							<div class="pos-action-row">
								<button class="ledgix-hold-btn">Hold</button>
								<button class="ledgix-held-list-btn">Held Sales</button>
								<button class="ledgix-return-refund-btn">Return</button>
							</div>

							<button class="ledgix-checkout-btn">Make Payment</button>
						</div>
					</div>
				</div>

			</div>
		</div>
	`);

	const $ledgix_pos_app = $(page.body).find('.ledgix-pos-app').first();
	window.LedgixNavigator?.mount?.({
		page: page,
		wrapper: wrapper,
		content: $ledgix_pos_app,
		active: 'pos'
	});

	function money(value) {
		return 'Rs. ' + (flt(value) || 0).toLocaleString(undefined, {
			minimumFractionDigits: 0,
			maximumFractionDigits: 2
		});
	}

	function pos_svg_icon(name, size) {
		size = size || 18;

		const icons = {
			receipt: '<path d="M4 3h16v18l-3-2-3 2-3-2-3 2-4-2V3z"></path><path d="M8 7h8"></path><path d="M8 11h8"></path><path d="M8 15h5"></path>',
			search: '<circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.35-4.35"></path>',
			eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"></path><circle cx="12" cy="12" r="3"></circle>',
			print: '<path d="M6 9V3h12v6"></path><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><path d="M6 14h12v7H6z"></path>',
			x: '<path d="M18 6 6 18"></path><path d="m6 6 12 12"></path>',
			open_shift: '<path d="M9 11V7a3 3 0 0 1 6 0v4"></path><rect x="5" y="11" width="14" height="10" rx="2"></rect>',
			close_shift: '<rect x="5" y="11" width="14" height="10" rx="2"></rect><path d="M8 11V8a4 4 0 0 1 7.5-2"></path><path d="m17 4 3 3-3 3"></path>',
			chevron_left: '<path d="m15 18-6-6 6-6"></path>',
			chevron_right: '<path d="m9 18 6-6-6-6"></path>',
			keyboard: '<rect x="3" y="6" width="18" height="12" rx="3"></rect><path d="M7 10h.01"></path><path d="M10 10h.01"></path><path d="M13 10h.01"></path><path d="M16 10h.01"></path><path d="M8 14h8"></path>',
			sun: '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2"></path><path d="M12 20v2"></path><path d="m4.93 4.93 1.41 1.41"></path><path d="m17.66 17.66 1.41 1.41"></path><path d="M2 12h2"></path><path d="M20 12h2"></path><path d="m6.34 17.66-1.41 1.41"></path><path d="m19.07 4.93-1.41 1.41"></path>',
			moon: '<path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5 7 7 0 1 0 20.5 14.5z"></path>',
			cash: '<rect x="3" y="6" width="18" height="12" rx="2"></rect><circle cx="12" cy="12" r="3"></circle><path d="M6 10v4"></path><path d="M18 10v4"></path>',
			card: '<rect x="3" y="5" width="18" height="14" rx="2"></rect><path d="M3 10h18"></path><path d="M7 15h4"></path>',
			wallet: '<path d="M20 7H5a2 2 0 0 1 0-4h13v4"></path><path d="M5 7h15v14H5a2 2 0 0 1-2-2V5"></path><path d="M16 13h.01"></path>',
			bank: '<path d="M3 10h18"></path><path d="M5 10V8l7-4 7 4v2"></path><path d="M6 10v8"></path><path d="M10 10v8"></path><path d="M14 10v8"></path><path d="M18 10v8"></path><path d="M4 18h16"></path>',
			refresh: '<path d="M21 12a9 9 0 0 1-15.5 6.2"></path><path d="M3 12A9 9 0 0 1 18.5 5.8"></path><path d="M3 21v-6h6"></path><path d="M21 3v6h-6"></path>',
			cube: '<path d="m21 8-9-5-9 5 9 5 9-5z"></path><path d="m3 8 9 5 9-5"></path><path d="M12 13v8"></path><path d="M3 8v8l9 5 9-5V8"></path>',
			file_text: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><path d="M14 2v6h6"></path><path d="M16 13H8"></path><path d="M16 17H8"></path><path d="M10 9H8"></path>'
	};

		return `
			<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				${icons[name] || icons.receipt}
			</svg>
		`;
	}

	function safe_text(value) {
		return $('<div>').text(value || '').html();
	}

	function normalize_category_key(value) {
		return (value || '')
			.toString()
			.toLowerCase()
			.replace(/&/g, 'and')
			.replace(/[^a-z0-9]+/g, '_')
			.replace(/^_+|_+$/g, '');
	}

	function get_category_for_item(item) {
		let category_name = item.category || item.category_name || '';

		return categories.find(category => {
			return category.name === category_name || category.category_name === category_name;
		}) || {
			name: category_name,
			category_name: category_name,
			category_icon: category_name
		};
	}

	function get_category_accent(category) {
		let color = category && category.accent_color ? category.accent_color : '#64748b';
		return /^#([0-9A-F]{3}){1,2}$/i.test(color) ? color : '#64748b';
	}

	function get_category_icon_name(category) {
		let key = normalize_category_key(
			(category && category.category_icon) ||
			(category && category.category_name) ||
			(category && category.name) ||
			'Default'
		);

		const map = {
			drinks: 'bottle',
			snacks: 'chips',
			grocery: 'basket',
			bakery: 'bread',
			dairy: 'milk',
			frozen: 'snowflake',
			meat: 'meat',
			fruits: 'apple',
			vegetables: 'leaf',
			electronics: 'plug',
			mobile_accessories: 'phone',
			clothing: 'shirt',
			shoes: 'shoe',
			cosmetics: 'lipstick',
			pharmacy: 'medical',
			stationery: 'notebook',
			household: 'home',
			kitchen: 'pan',
			pet_supplies: 'paw',
			toys: 'toy',
			hardware: 'hammer',
			sports: 'dumbbell',
			books: 'book',
			jewellery: 'diamond',
			watches: 'watch',
			perfumes: 'perfume',
			cigarettes: 'cigarette',
			baby_products: 'baby_bottle',
			tea_and_coffee: 'cup',
			fast_food: 'burger',
			rice_and_grains: 'sack',
			spices: 'spice',
			cleaning: 'spray',
			beauty: 'sparkles',
			office_supplies: 'briefcase',
			gift_items: 'gift'
		};

		return map[key] || 'box';
	}

	function category_svg_icon(name, size) {
		size = size || 30;

		const icons = {
			bottle: '<path d="M10 2h4"></path><path d="M11 2v5l-2 3v10a2 2 0 0 0 2 2h2a2 2 0 0 0 2-2V10l-2-3V2"></path><path d="M9 14h6"></path>',
			chips: '<path d="M7 3h10l-1 18H8L7 3z"></path><path d="M9 7h6"></path><path d="M9 12h6"></path>',
			basket: '<path d="M5 10h14l-2 10H7L5 10z"></path><path d="M8 10l4-6 4 6"></path>',
			bread: '<path d="M5 10a7 7 0 0 1 14 0v9H5v-9z"></path><path d="M8 14h8"></path>',
			milk: '<path d="M8 2h8l-1 5 2 3v12H7V10l2-3-1-5z"></path><path d="M8 14h8"></path>',
			snowflake: '<path d="M12 2v20"></path><path d="M4 6l16 12"></path><path d="M20 6L4 18"></path>',
			meat: '<path d="M7 14a5 5 0 0 1 7-7l3 3a4 4 0 1 1-6 6l-4-2z"></path><circle cx="15" cy="14" r="1"></circle>',
			apple: '<path d="M12 7c2-3 5-2 6 1 2 5-2 12-6 12S4 13 6 8c1-3 4-4 6-1z"></path><path d="M12 7c0-2 1-4 3-5"></path>',
			leaf: '<path d="M5 20c9 0 14-5 14-14V4h-2C8 4 4 9 4 16c0 2 1 4 1 4z"></path><path d="M5 20L19 6"></path>',
			plug: '<path d="M9 2v6"></path><path d="M15 2v6"></path><path d="M7 8h10v4a5 5 0 0 1-10 0V8z"></path><path d="M12 17v5"></path>',
			phone: '<rect x="7" y="2" width="10" height="20" rx="2"></rect><path d="M11 18h2"></path>',
			shirt: '<path d="M8 4l4 2 4-2 4 4-3 3v9H7v-9L4 8l4-4z"></path>',
			shoe: '<path d="M4 15l5-7 4 5 5 1c2 1 2 4 0 4H5c-2 0-2-2-1-3z"></path>',
			lipstick: '<path d="M10 3h4v7h-4z"></path><path d="M9 10h6v11H9z"></path><path d="M10 3l2-2 2 2"></path>',
			medical: '<path d="M12 5v14"></path><path d="M5 12h14"></path><rect x="4" y="4" width="16" height="16" rx="4"></rect>',
			notebook: '<path d="M6 3h13v18H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"></path><path d="M8 7h7"></path><path d="M8 11h7"></path>',
			home: '<path d="M3 11l9-8 9 8"></path><path d="M5 10v11h14V10"></path>',
			pan: '<path d="M4 12h10a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z"></path><path d="M14 12h7"></path>',
			paw: '<circle cx="6" cy="8" r="2"></circle><circle cx="12" cy="6" r="2"></circle><circle cx="18" cy="8" r="2"></circle><path d="M7 17c1-4 9-4 10 0 1 3-2 4-5 2-3 2-6 1-5-2z"></path>',
			toy: '<rect x="5" y="8" width="14" height="10" rx="2"></rect><path d="M8 8V5h8v3"></path>',
			hammer: '<path d="M14 4l6 6"></path><path d="M12 6l6 6"></path><path d="M2 22l9-9"></path>',
			dumbbell: '<path d="M6 8v8"></path><path d="M18 8v8"></path><path d="M6 12h12"></path><path d="M3 10v4"></path><path d="M21 10v4"></path>',
			book: '<path d="M4 5a3 3 0 0 1 3-3h13v18H7a3 3 0 0 0-3 3V5z"></path>',
			diamond: '<path d="M6 3h12l4 6-10 12L2 9l4-6z"></path>',
			watch: '<circle cx="12" cy="12" r="5"></circle><path d="M9 2h6"></path><path d="M9 22h6"></path><path d="M12 9v3l2 2"></path>',
			perfume: '<path d="M10 2h4v4h-4z"></path><rect x="7" y="6" width="10" height="16" rx="3"></rect><path d="M9 12h6"></path>',
			cigarette: '<path d="M3 15h14v4H3z"></path><path d="M20 15v4"></path><path d="M18 8c2 1 2 3 0 4"></path>',
			baby_bottle: '<path d="M10 2h4v4h-4z"></path><path d="M9 6h6l1 4v10a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2V10l1-4z"></path>',
			cup: '<path d="M5 8h12v7a5 5 0 0 1-10 0V8z"></path><path d="M17 10h2a2 2 0 0 1 0 4h-2"></path>',
			burger: '<path d="M4 11a8 8 0 0 1 16 0H4z"></path><path d="M4 15h16"></path><path d="M5 19h14"></path>',
			sack: '<path d="M9 2h6l-2 5h-2L9 2z"></path><path d="M7 7h10l3 13H4L7 7z"></path>',
			spice: '<path d="M9 2h6v4H9z"></path><rect x="7" y="6" width="10" height="16" rx="2"></rect><path d="M9 11h6"></path>',
			spray: '<path d="M9 2h6v5H9z"></path><path d="M8 7h8l1 15H7L8 7z"></path><path d="M17 5h4"></path>',
			sparkles: '<path d="M12 2l2 6 6 2-6 2-2 6-2-6-6-2 6-2 2-6z"></path>',
			briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"></rect><path d="M9 7V5h6v2"></path>',
			gift: '<rect x="3" y="8" width="18" height="13"></rect><path d="M12 8v13"></path><path d="M3 12h18"></path><path d="M7 8c-2-3 3-5 5 0"></path><path d="M17 8c2-3-3-5-5 0"></path>',
			box: '<path d="m21 8-9-5-9 5 9 5 9-5z"></path><path d="M3 8v8l9 5 9-5V8"></path><path d="M12 13v8"></path>'
		};

		return `
			<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
				${icons[name] || icons.box}
			</svg>
		`;
	}

	function get_category_visual_html(category) {
		let custom_image = category && category.custom_icon_image ? category.custom_icon_image : '';

		if (custom_image) {
			return `<img src="${safe_text(custom_image)}" alt="" class="product-category-img" />`;
		}

		return category_svg_icon(get_category_icon_name(category), 30);
	}


	function can_override_pos_rate() {
		return !!(
			frappe.user &&
			frappe.user.has_role &&
			(
				frappe.user.has_role('System Manager') ||
				frappe.user.has_role('Ledgix Admin')
			)
		);
	}

	function get_cart_rate_floor(row) {
		return flt(row.original_rate || row.selling_price || row.rate);
	}

	function is_serial_based_row(row) {
		return (row && row.tracking_type) === 'Serial Based';
	}

	function parse_cart_serials(value) {
		return (value || '')
			.toString()
			.split(/[\n,;]+/)
			.map(serial => serial.trim())
			.filter(Boolean);
	}

	function get_cart_serials(row) {
		return parse_cart_serials(row && row.serial_numbers);
	}

	function write_cart_serials(row, serials) {
		row.serial_numbers = (serials || []).join('\n');
	}

	function clear_cart_serials(row) {
		if (!row) return;
		row.serial_numbers = '';
	}

	function reset_manual_serials_for_qty_change(row) {
		if (!is_serial_based_row(row)) return false;
		if (!get_cart_serials(row).length) return false;

		clear_cart_serials(row);
		frappe.show_alert({
			message: 'Serial selection reset because quantity changed.',
			indicator: 'orange'
		}, 4);
		return true;
	}

	function get_manually_selected_serials(exclude_index) {
		const selected = new Set();

		cart.forEach((row, index) => {
			if (index === exclude_index) return;
			get_cart_serials(row).forEach(serial => selected.add(serial));
		});

		return selected;
	}

	function get_serial_control_html(row, index) {
		if (!is_serial_based_row(row)) return '';

		const serials = get_cart_serials(row);
		const has_manual_serials = serials.length > 0;
		const status = has_manual_serials ? `${serials.length} selected` : 'Auto FIFO';
		const action = has_manual_serials ? 'Change' : 'Choose';

		return `
			<div class="cart-serial-control">
				<span>Serials: ${safe_text(status)}</span>
				<button type="button" class="btn btn-xs btn-default choose-serials-btn" data-index="${index}">${action}</button>
				${has_manual_serials ? `<button type="button" class="btn btn-xs btn-default serial-auto-btn" data-index="${index}">Auto</button>` : ''}
			</div>
		`;
	}

	function get_receipt_invoice_no(receipt) {
		receipt = receipt || {};

		return (
			receipt.invoice_number ||
			receipt.customer_invoice_number ||
			receipt.sale_invoice_number ||
			receipt.custom_invoice_number ||
			receipt.invoice_no ||
			receipt.pos_invoice_number ||
			''
		);
	}


	function apply_pos_stock_visibility() {
		pos_stock_visibility = stock_control_mode === 'Billing Only' ? 'hide' : 'show';

		$('.ledgix-pos-app')
			.toggleClass('pos-stock-hidden', pos_stock_visibility === 'hide');

		render_products(all_items);
	}

	function is_inventory_mode() {
		return stock_control_mode !== 'Billing Only';
	}

	function get_pos_item_key(item) {
		return (item && (item.name || item.item || item.item_code)) || '';
	}

	function get_backend_stock_for_item(item) {
		item = item || {};
		for (const key of ['current_stock', 'stock_qty', 'available_stock', 'stock']) {
			if (item[key] !== undefined && item[key] !== null && item[key] !== '') {
				return flt(item[key]);
			}
		}
		return 0;
	}

	function get_cart_item_qty(item_name) {
		return cart.reduce((total, row) => {
			const row_key = row.item || row.name || row.item_code;
			return row_key === item_name ? total + flt(row.qty) : total;
		}, 0);
	}

	function get_display_available_stock(item) {
		const backend_stock = get_backend_stock_for_item(item);
		const cart_qty = get_cart_item_qty(get_pos_item_key(item));
		return Math.max(backend_stock - cart_qty, 0);
	}

	function get_item_for_cart_row(row) {
		if (!row) return null;
		return all_items.find(item => item.name === row.item)
			|| visible_product_items.find(item => item.name === row.item)
			|| {
				name: row.item,
				item: row.item,
				item_code: row.item_code,
				current_stock: row.stock
			};
	}

	function refresh_visible_product_cards() {
		render_products(visible_product_items);
	}

	function is_item_out_of_stock(item) {
		return is_inventory_mode() && get_display_available_stock(item) <= 0;
	}

	function can_add_pos_item(item, show_message) {
		if (!item) return false;

		if (is_item_out_of_stock(item)) {
			play_pos_sound('error');
			if (show_message) {
				frappe.show_alert({
					message: 'Out of stock item cannot be added in Inventory Mode.',
					indicator: 'red'
				});
			}
			return false;
		}

		return true;
	}

	function focus_pos_search() {
		if ($('.modal:visible').length) return;
		let $input = $('.ledgix-pos-search-input');
		if ($input.length) {
			$input.trigger('focus');
		}
	}

	function update_pos_search_clear_state() {
		let has_value = !!($('.ledgix-pos-search-input').val() || '').trim();
		$('.ledgix-search-clear-btn').toggleClass('hidden', !has_value);
	}

	function update_shift_metrics(shift) {
		shift = shift || active_shift || {};

		let invoice_count = cint(
			shift.invoice_count ||
			shift.shift_invoice_count ||
			shift.total_invoices ||
			shift.sales_count ||
			shift.no_of_invoices ||
			0
		);

		let shift_sales = flt(
			shift.shift_sales ||
			shift.total_sales ||
			shift.sales_total ||
			shift.total_amount ||
			shift.net_sales ||
			0
		);

		$('.shift-invoices-value').text(invoice_count);
		$('.shift-sales-value').text(money(shift_sales));
	}

	function render_pos_mode_badge() {
		let is_billing_mode = stock_control_mode === 'Billing Only';

		$('.pos-mode-badge')
			.removeClass('inventory billing')
			.addClass(is_billing_mode ? 'billing' : 'inventory')
			.text(is_billing_mode ? 'Billing Mode' : 'Inventory Mode');
	}








// ============================================================
// POS THEME ENGINE
// ============================================================

	function apply_pos_theme(theme) {

		theme = theme || window.LedgixTheme?.get?.() || window.ledgix_theme || {};

		function get_theme_targets() {
			const targets = Array.from(document.querySelectorAll('.ledgix-pos-app'));
			targets.push(document.documentElement, document.body);
			return targets.filter(Boolean).filter((target, index, list) => list.indexOf(target) === index);
		}

		function set_theme_var(targets, name, value) {
			targets.forEach((target) => target.style.setProperty(name, value));
		}

		function clear_theme_vars(targets) {
			const vars = [
				'--lx-accent', '--accent', '--ledgix-accent', '--primary',
				'--ledgix-primary',
				'--lx-accent-hover', '--accent-hover', '--lx-accent-soft', '--accent-soft',
				'--lx-accent-soft-hover', '--lx-accent-soft-2', '--accent-soft-2',
				'--lx-accent-border', '--accent-border', '--lx-accent-border-strong',
				'--lx-accent-ring', '--accent-ring', '--lx-accent-rgb', '--ledgix-accent-rgb',
				'--accent-rgb', '--lx-accent-track-bg', '--lx-accent-track-border',
				'--lx-active-bg', '--lx-active-hover', '--lx-active-soft-bg',
				'--lx-active-soft-hover', '--lx-active-border', '--lx-category-active-bg',
				'--lx-payment-active-bg', '--lx-split-active-bg', '--lx-modal-primary-bg',
				'--lx-modal-primary-hover'
			];
			targets.forEach((target) => {
				vars.forEach((name) => target.style.removeProperty(name));
				target.setAttribute('data-ledgix-theme', 'disabled');
			});
		}

		function normalize_hex(value) {
			const text = String(value || '').trim();
			if (/^#[0-9a-fA-F]{6}$/.test(text)) return text;
			if (/^[0-9a-fA-F]{6}$/.test(text)) return `#${text}`;
			if (/^#[0-9a-fA-F]{3}$/.test(text)) {
				return `#${text.slice(1).split('').map((char) => char + char).join('')}`;
			}
			return '';
		}

		function rgb_string(hex) {
			const color = normalize_hex(hex);
			if (!color) return '';
			return [
				parseInt(color.slice(1, 3), 16),
				parseInt(color.slice(3, 5), 16),
				parseInt(color.slice(5, 7), 16)
			].join(', ');
		}

		const primary = normalize_hex(theme.primary_accent_color);
		const targets = get_theme_targets();
		if (!theme.enable_custom_accent || !primary) {
			clear_theme_vars(targets);
			return;
		}
		const rgb = theme.accent_rgb || rgb_string(primary);
		const hover = theme.accent_hover || `color-mix(in srgb, ${primary} 82%, black)`;
		const soft = theme.accent_soft || `rgba(${rgb}, 0.10)`;
		const softHover = theme.accent_soft_hover || `rgba(${rgb}, 0.12)`;
		const soft2 = theme.accent_soft_2 || `rgba(${rgb}, 0.16)`;
		const border = theme.accent_border || `rgba(${rgb}, 0.28)`;
		const borderStrong = theme.accent_border_strong || `rgba(${rgb}, 0.42)`;
		const ring = theme.accent_ring || `rgba(${rgb}, 0.18)`;
		const trackBg = theme.accent_track_bg || `rgba(${rgb}, 0.08)`;
		const trackBorder = theme.accent_track_border || `rgba(${rgb}, 0.30)`;

		targets.forEach((target) => target.setAttribute('data-ledgix-theme', 'enabled'));
		set_theme_var(targets, '--lx-accent', primary);
		set_theme_var(targets, '--accent', primary);
		set_theme_var(targets, '--ledgix-accent', primary);
		set_theme_var(targets, '--primary', primary);
		set_theme_var(targets, '--lx-accent-hover', hover);
		set_theme_var(targets, '--accent-hover', hover);
		set_theme_var(targets, '--lx-accent-soft', soft);
		set_theme_var(targets, '--accent-soft', soft);
		set_theme_var(targets, '--lx-accent-soft-hover', softHover);
		set_theme_var(targets, '--lx-accent-soft-2', soft2);
		set_theme_var(targets, '--accent-soft-2', soft2);
		set_theme_var(targets, '--lx-accent-border', border);
		set_theme_var(targets, '--accent-border', border);
		set_theme_var(targets, '--lx-accent-border-strong', borderStrong);
		set_theme_var(targets, '--lx-accent-ring', ring);
		set_theme_var(targets, '--accent-ring', ring);
		set_theme_var(targets, '--lx-accent-rgb', rgb);
		set_theme_var(targets, '--ledgix-accent-rgb', rgb);
		set_theme_var(targets, '--accent-rgb', rgb);
		set_theme_var(targets, '--lx-accent-track-bg', trackBg);
		set_theme_var(targets, '--lx-accent-track-border', trackBorder);
		set_theme_var(targets, '--lx-active-bg', primary);
		set_theme_var(targets, '--lx-active-hover', hover);
		set_theme_var(targets, '--lx-active-soft-bg', soft);
		set_theme_var(targets, '--lx-active-soft-hover', softHover);
		set_theme_var(targets, '--lx-active-border', border);
		set_theme_var(targets, '--lx-category-active-bg', primary);
		set_theme_var(targets, '--lx-payment-active-bg', primary);
		set_theme_var(targets, '--lx-split-active-bg', primary);
		set_theme_var(targets, '--lx-modal-primary-bg', primary);
		set_theme_var(targets, '--lx-modal-primary-hover', hover);
	}

	if (window.__ledgix_pos_theme_handler) {
		window.removeEventListener('ledgix:theme-updated', window.__ledgix_pos_theme_handler);
		document.removeEventListener('ledgix:theme-updated', window.__ledgix_pos_theme_handler);
	}

	window.__ledgix_pos_theme_handler = function(e) {
		const theme = (e.detail && e.detail.theme) || window.LedgixTheme?.get?.() || window.ledgix_theme || {};
		apply_pos_theme(theme);
	};

	window.addEventListener('ledgix:theme-updated', window.__ledgix_pos_theme_handler);
	document.addEventListener('ledgix:theme-updated', window.__ledgix_pos_theme_handler);
	apply_pos_theme(window.LedgixTheme?.get?.() || window.ledgix_theme || {});



	function play_pos_sound(type) {
		try {
			let AudioContext = window.AudioContext || window.webkitAudioContext;
			if (!AudioContext) return;

			let ctx = new AudioContext();
			let gain = ctx.createGain();
			gain.connect(ctx.destination);

			function tone(freq, start, duration, volume) {
				let osc = ctx.createOscillator();
				osc.type = 'sine';
				osc.frequency.value = freq;
				osc.connect(gain);
				gain.gain.setValueAtTime(volume || 0.08, ctx.currentTime + start);
				gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + duration);
				osc.start(ctx.currentTime + start);
				osc.stop(ctx.currentTime + start + duration);
			}

			if (type === 'success') {
				tone(880, 0, 0.08, 0.10);
				tone(1175, 0.08, 0.10, 0.08);
			} else if (type === 'error') {
				tone(220, 0, 0.16, 0.10);
			} else if (type === 'sale') {
				tone(740, 0, 0.07, 0.10);
				tone(988, 0.08, 0.08, 0.09);
				tone(1319, 0.17, 0.12, 0.08);
			} else {
				tone(660, 0, 0.08, 0.08);
			}
		} catch (e) {
			// Sound is optional. POS must never fail because of browser audio restrictions.
		}
	}

	function set_checkout_processing(is_processing) {
		sale_processing = is_processing;

		$('.ledgix-checkout-btn')
			.toggleClass('processing', is_processing)
			.prop('disabled', is_processing)
			.text(is_processing ? 'Processing...' : 'Make Payment');
	}

	function make_client_sale_id() {
		if (window.crypto && typeof window.crypto.randomUUID === 'function') {
			return window.crypto.randomUUID();
		}

		return `pos-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
	}

	function show_pos_notice(message, indicator) {
		frappe.show_alert({
			message: message || 'POS action could not be completed.',
			indicator: indicator || 'red'
		});
	}

	function get_frappe_error_message(r) {
		if (r && r.message && typeof r.message === 'string') return r.message;
		if (r && r._server_messages) {
			try {
				let messages = JSON.parse(r._server_messages);
				let parsed = JSON.parse(messages[0] || '{}');
				return parsed.message || '';
			} catch (e) {
				return '';
			}
		}
		if (r && r.responseJSON && r.responseJSON._server_messages) {
			try {
				let messages = JSON.parse(r.responseJSON._server_messages);
				let parsed = JSON.parse(messages[0] || '{}');
				return parsed.message || '';
			} catch (e) {
				return '';
			}
		}
		return '';
	}

	function set_pos_viewport_height() {
		let app = document.querySelector('.ledgix-pos-app');
		if (!app) return;

		let rect = app.getBoundingClientRect();
		let safe_height = Math.max(360, window.innerHeight - rect.top - 10);
		app.style.setProperty('--lx-pos-viewport-height', `${safe_height}px`);
	}

	function flash_scanner_state(type) {
		let $search = $('.ledgix-search-wrapper');
		$search.removeClass('scanner-success scanner-error scanner-searching');
		if (!type) return;

		$search.addClass(`scanner-${type}`);
		window.setTimeout(() => {
			$search.removeClass(`scanner-${type}`);
		}, type === 'searching' ? 550 : 900);
	}

	
	function build_receipt_snapshot(response, cart_snapshot, totals_snapshot, payments_snapshot) {
		return {
			sale_id: response.sale_id || response.sale || response.sale_name || 'SALE',
			invoice_number: response.invoice_number || response.customer_invoice_number || response.sale_invoice_number || response.custom_invoice_number || response.invoice_no || response.pos_invoice_number || '',
			date_time: frappe.datetime.now_datetime(),
			items: cart_snapshot || [],
			subtotal: flt(totals_snapshot.subtotal),
			discount: flt(totals_snapshot.discount),
			tax: flt(response.tax_amount || totals_snapshot.tax),
			total: flt(response.grand_total || response.total_amount || totals_snapshot.total),
			paid: flt(response.paid_amount || totals_snapshot.paid),
			remaining: flt(response.remaining_amount || totals_snapshot.remaining),
			change: flt(response.change_amount || totals_snapshot.change),
			payments: payments_snapshot || [],
			fbr_status: response.fbr_status || '',
			fbr_invoice_number: response.fbr_invoice_number || '',
			fbr_qr_code: response.fbr_qr_code || ''
		};
	}

	function get_fbr_qr_image_src(qr_code) {
		if (!qr_code) return '';
		const value = String(qr_code).trim();
		if (value.startsWith('data:image')) return value;
		if (value.startsWith('http://') || value.startsWith('https://')) return value;
		return `data:image/png;base64,${value}`;
	}

	function get_fbr_receipt_html(receipt) {
		const invoiceNo = receipt.fbr_invoice_number || '';
		const qrCode = receipt.fbr_qr_code || '';
		const status = receipt.fbr_status || '';
		if (!invoiceNo && !qrCode && !status) return '';

		const qrSrc = get_fbr_qr_image_src(qrCode);
		const qrHtml = qrSrc
			? `<div class="fbr-qr"><img src="${qrSrc}" alt="FBR QR Code" /></div>`
			: '';

		return `
			<div class="receipt-line"></div>
			<div class="fbr-block">
				<div class="section-title">FBR E-Invoice</div>
				${invoiceNo ? `<div class="summary-row"><span>FBR Invoice:</span><strong>${invoiceNo}</strong></div>` : ''}
				${status && !invoiceNo ? `<div class="summary-row"><span>FBR Status:</span><strong>${status}</strong></div>` : ''}
				${qrHtml}
				<div class="fbr-verify">Integrated with FBR • Verify at fbr.gov.pk</div>
			</div>
		`;
	}

	function get_receipt_items_html(receipt) {
		let html = '';

		(receipt.items || []).forEach(row => {
			let qty = flt(row.qty);
			let rate = flt(row.rate);
			let amount = qty * rate;

			html += `
				<div class="receipt-item-row">
					<div>
						<div class="receipt-item-name">${row.item_name || row.item || ''}</div>
						<div class="receipt-item-meta">${qty} x ${money(rate)}</div>
					</div>
					<strong>${money(amount)}</strong>
				</div>
			`;
		});

		return html || `<div class="receipt-empty">No item details available</div>`;
	}

	function get_receipt_text(receipt) {
		let lines = [];

		lines.push('Ledgix POS Receipt');
		lines.push('Invoice: ' + get_receipt_invoice_no(receipt));
		lines.push('Date: ' + frappe.datetime.str_to_user(receipt.date_time));
		lines.push('------------------------------');

		(receipt.items || []).forEach(row => {
			let qty = flt(row.qty);
			let rate = flt(row.rate);
			let amount = qty * rate;
			lines.push((row.item_name || row.item || 'Item') + ' x ' + qty + ' = Rs. ' + amount);
		});

		lines.push('------------------------------');
		lines.push('Subtotal: Rs. ' + receipt.subtotal);
		lines.push('Discount: Rs. ' + receipt.discount);
		lines.push('Tax: Rs. ' + flt(receipt.tax));
		lines.push('Total: Rs. ' + receipt.total);
		lines.push('Paid: Rs. ' + receipt.paid);
		lines.push('Change: Rs. ' + receipt.change);
		if (receipt.fbr_invoice_number) {
			lines.push('FBR Invoice: ' + receipt.fbr_invoice_number);
		} else if (receipt.fbr_status) {
			lines.push('FBR Status: ' + receipt.fbr_status);
		}
		lines.push('');
		lines.push('Thank you for shopping.');

		return lines.join('\n');
	}

	function normalize_whatsapp_number(number) {
		number = (number || '').toString().replace(/\D/g, '');

		if (!number) return '';

		if (number.startsWith('0')) {
			number = '92' + number.substring(1);
		}

		return number;
	}

	function open_whatsapp_receipt(receipt, raw_number) {
		let number = normalize_whatsapp_number(raw_number);

		if (!number) {
			play_pos_sound('error');
			frappe.msgprint('Please enter WhatsApp number first.');
			return;
		}

		let message = get_receipt_text(receipt);
		let url = 'https://wa.me/' + number + '?text=' + encodeURIComponent(message);

		window.open(url, '_blank');
	}

function print_receipt(receipt) {
	let items_html = '';
	let payments_html = '';

	(receipt.items || []).forEach(row => {
		let qty = flt(row.qty);
		let rate = flt(row.rate);
		let amount = qty * rate;

		items_html += `
			<tr>
				<td class="item-name">${row.item_name || row.item || 'Item'}</td>
				<td class="text-right">${qty}</td>
				<td class="text-right">${rate}</td>
				<td class="text-right">${amount}</td>
			</tr>
		`;
	});

	(receipt.payments || []).forEach(payment => {
		payments_html += `
			<div class="payment-row">
				<span>${payment.payment_method || 'Payment'}</span>
				<strong>Rs. ${flt(payment.amount)}</strong>
			</div>
		`;
	});

	if (!payments_html) {
		payments_html = `
			<div class="payment-row">
				<span>Payment</span>
				<strong>Rs. ${flt(receipt.paid)}</strong>
			</div>
		`;
	}

	let cashier = (frappe.session && frappe.session.user) ? frappe.session.user : '-';
	let shift_id = active_shift && active_shift.shift_id ? active_shift.shift_id : '-';

	let print_window = window.open('', '_blank', 'width=420,height=650');

	if (!print_window) {
		frappe.msgprint('Popup blocked. Please allow popups to print receipt.');
		return;
	}

	print_window.document.write(`
		<!doctype html>
		<html>
		<head>
			<title>Receipt ${get_receipt_invoice_no(receipt) || receipt.sale_id}</title>
			<style>
				@page {
					size: 80mm auto;
					margin: 3mm;
				}

				body {
					width: 72mm;
					margin: 0 auto;
					font-family: Arial, sans-serif;
					font-size: 11px;
					color: #000;
				}

				.receipt-header {
					text-align: center;
					margin-bottom: 6px;
				}

				.logo-box {
					font-size: 19px;
					font-weight: 900;
					letter-spacing: 1.5px;
					line-height: 1.2;
				}

				.shop-name {
					font-size: 12px;
					font-weight: 700;
					margin-top: 3px;
				}

				.shop-info {
					font-size: 10px;
					margin-top: 2px;
				}

				.receipt-label {
					font-size: 11px;
					font-weight: 700;
					margin-top: 5px;
					text-transform: uppercase;
				}

				.receipt-line {
					border-top: 1px dashed #000;
					margin: 6px 0;
				}

				.receipt-info div,
				.summary-row,
				.payment-row {
					display: flex;
					justify-content: space-between;
					gap: 8px;
					padding: 2px 0;
				}

				.receipt-info span,
				.summary-row span,
				.payment-row span {
					font-weight: 600;
				}

				.receipt-info strong,
				.summary-row strong,
				.payment-row strong {
					text-align: right;
					font-weight: 700;
				}

				table {
					width: 100%;
					border-collapse: collapse;
					font-size: 10.5px;
				}

				th {
					text-align: left;
					border-bottom: 1px dashed #000;
					padding: 3px 0;
					font-weight: 700;
				}

				td {
					padding: 3px 0;
					vertical-align: top;
				}

				.item-name {
					width: 42%;
					word-break: break-word;
				}

				.text-right {
					text-align: right;
				}

				.grand-total {
					font-size: 14px;
					font-weight: 900;
					padding: 4px 0;
				}

				.section-title {
					font-size: 11px;
					font-weight: 800;
					margin-bottom: 3px;
					text-transform: uppercase;
				}

				.receipt-footer {
					text-align: center;
					font-size: 10.5px;
					margin-top: 8px;
				}

				.thanks {
					font-weight: 800;
				}

				.powered {
					margin-top: 3px;
					font-size: 9.5px;
				}

				.fbr-block {
					margin-top: 4px;
				}

				.fbr-qr {
					text-align: center;
					margin: 6px 0;
				}

				.fbr-qr img {
					width: 25mm;
					height: 25mm;
					object-fit: contain;
				}

				.fbr-verify {
					text-align: center;
					font-size: 9px;
					margin-top: 4px;
				}

			</style>
		</head>

		<body>
			<div class="receipt-header">
				<div class="logo-box">LEDGIX</div>
				<div class="shop-name">Ledgix Retail Store</div>
				<div class="shop-info">Fast POS • Inventory • Profit Tracking</div>
				<div class="receipt-label">Sales Receipt</div>
			</div>

			<div class="receipt-line"></div>

			<div class="receipt-info">
				<div><span>Invoice:</span><strong>${get_receipt_invoice_no(receipt) || receipt.sale_id}</strong></div>
				<div><span>Date:</span><strong>${frappe.datetime.str_to_user(receipt.date_time)}</strong></div>
				<div><span>Cashier:</span><strong>${cashier}</strong></div>
				<div><span>Shift:</span><strong>${shift_id}</strong></div>
			</div>

			<div class="receipt-line"></div>

			<table>
				<thead>
					<tr>
						<th>Item</th>
						<th class="text-right">Qty</th>
						<th class="text-right">Rate</th>
						<th class="text-right">Total</th>
					</tr>
				</thead>
				<tbody>
					${items_html}
				</tbody>
			</table>

			<div class="receipt-line"></div>

			<div class="receipt-summary">
				<div class="summary-row"><span>Subtotal:</span><strong>Rs. ${flt(receipt.subtotal)}</strong></div>
				<div class="summary-row"><span>Discount:</span><strong>Rs. ${flt(receipt.discount)}</strong></div>
				<div class="summary-row"><span>Tax:</span><strong>Rs. ${flt(receipt.tax)}</strong></div>
				<div class="summary-row grand-total"><span>Total:</span><strong>Rs. ${flt(receipt.total)}</strong></div>
				<div class="summary-row"><span>Paid:</span><strong>Rs. ${flt(receipt.paid)}</strong></div>
				<div class="summary-row"><span>Change:</span><strong>Rs. ${flt(receipt.change)}</strong></div>
			</div>

			<div class="receipt-line"></div>

			<div class="payment-breakdown">
				<div class="section-title">Payment Breakdown</div>
				${payments_html}
			</div>

			<div class="receipt-line"></div>

			${get_fbr_receipt_html(receipt)}

			<div class="receipt-footer">
				<div class="thanks">Thank you for shopping with us</div>
				<div class="powered">Powered by Ledgix POS</div>
			</div>

			<script>
				window.onload = function() {
					window.focus();
					window.print();
				};
			</script>
		</body>
		</html>
	`);

	print_window.document.close();
}

	function show_receipt_dialog(receipt) {
		let countdown = 10;
		let timer = null;

		let dialog = new frappe.ui.Dialog({
			title: 'Sale Completed',
			size: 'large',
			fields: [
				{
					fieldname: 'receipt_html',
					fieldtype: 'HTML'
				}
			]
		});

		function close_and_focus() {
			if (timer) clearInterval(timer);
			dialog.hide();
			$('.ledgix-pos-search-input').focus();
		}

		dialog.show();
		dialog.$wrapper.addClass('ledgix-pos-themed-dialog ledgix-sale-complete-dialog');
        dialog.$wrapper.on('click keydown input change', function() {
            if (timer) {
                clearInterval(timer);
                timer = null;
            }

            dialog.$wrapper.find('.receipt-success-subtitle').html(
                'Choose Print OR New Sale'
            );
        });

		dialog.fields_dict.receipt_html.$wrapper.html(`
			<div class="receipt-modal-wrap">
				<div class="receipt-success-card">
					<div class="receipt-success-icon">✓</div>
					<div>
						<div class="receipt-success-title">Sale completed</div>
						<div class="receipt-success-subtitle">New sale will be ready in <strong class="receipt-countdown">${countdown}</strong>s</div>
					</div>
				</div>

				<div class="receipt-preview-card">
					<div class="receipt-preview-head">
						<div>
							<div class="receipt-preview-title">Receipt</div>
							<div class="receipt-preview-subtitle">${get_receipt_invoice_no(receipt) || receipt.sale_id}</div>
						</div>
						<div class="receipt-preview-total">${money(receipt.total)}</div>
					</div>

					<div class="receipt-preview-meta">
						<div><span>Paid</span><strong>${money(receipt.paid)}</strong></div>
						<div><span>Change</span><strong>${money(receipt.change)}</strong></div>
					</div>

					<div class="receipt-items-list">
						${get_receipt_items_html(receipt)}
					</div>
				</div>

				<div class="receipt-whatsapp-box">
					<label class="receipt-whatsapp-toggle">
						<input type="checkbox" class="receipt-whatsapp-check" />
						<span>Send receipt on WhatsApp</span>
					</label>

					<div class="receipt-whatsapp-fields hidden">
						<input type="text" class="receipt-whatsapp-number" placeholder="Customer WhatsApp number e.g. 03001234567" />
						<button class="receipt-whatsapp-send-btn">WhatsApp Receipt</button>
					</div>
				</div>

				<div class="receipt-actions">
					<button class="receipt-print-btn">Print Receipt</button>
					<button class="receipt-new-sale-btn">New Sale</button>
				</div>
			</div>
		`);

		dialog.$wrapper.on('change', '.receipt-whatsapp-check', function() {
			$('.receipt-whatsapp-fields').toggleClass('hidden', !$(this).is(':checked'));

			if ($(this).is(':checked')) {
				setTimeout(() => $('.receipt-whatsapp-number').focus(), 100);
			}
		});

		dialog.$wrapper.on('click', '.receipt-whatsapp-send-btn', function() {
			open_whatsapp_receipt(receipt, $('.receipt-whatsapp-number').val());
		});

		dialog.$wrapper.on('click', '.receipt-print-btn', function() {
			print_receipt(receipt);
		});

		dialog.$wrapper.on('click', '.receipt-new-sale-btn', function() {
			close_and_focus();
		});

		dialog.$wrapper.on('hidden.bs.modal', function() {
			if (timer) clearInterval(timer);
			$('.ledgix-pos-search-input').focus();
		});

		timer = setInterval(function() {
			countdown -= 1;
			dialog.$wrapper.find('.receipt-countdown').text(countdown);

			if (countdown <= 0) {
				close_and_focus();
			}
		}, 1000);
	}


function get_subtotal() {
		return cart.reduce((total, row) => {
			return total + (flt(row.qty) * flt(row.rate));
		}, 0);
	}

	function get_discount_amount(subtotal) {
		let value = flt($('.discount-input').val());

		if (discount_type === 'Percent') {
			if (value > 100) value = 100;
			return subtotal * value / 100;
		}

		if (value > subtotal) value = subtotal;
		return value;
	}

	function reset_tax_preview() {
		pos_tax_preview = null;
		current_tax_amount = 0;
		current_grand_total = 0;
		last_tax_preview_signature = '';
		applied_tax_preview_signature = '';

		if (tax_preview_timer) {
			clearTimeout(tax_preview_timer);
			tax_preview_timer = null;
		}
		tax_preview_promise = null;
	}

	function build_tax_preview_items() {
		let subtotal = get_subtotal();
		let discount = get_discount_amount(subtotal);
		let discount_ratio = subtotal > 0 && discount > 0 ? discount / subtotal : 0;

		return cart.map(row => {
			let qty = flt(row.qty);
			let gross_rate = flt(row.rate);
			let rate = gross_rate * (1 - discount_ratio);
			let amount = qty * rate;

			return {
				item: row.item,
				item_name: row.item_name,
				qty: qty,
				quantity: qty,
				rate: rate,
				amount: amount,
				taxable_amount: amount,
				discount_amount: qty * gross_rate * discount_ratio
			};
		});
	}

	function get_tax_preview_signature() {
		return JSON.stringify({
			sale_date: frappe.datetime.get_today(),
			discount_type: discount_type,
			discount_value: flt($('.discount-input').val()),
			items: build_tax_preview_items().map(row => ({
				item: row.item,
				qty: flt(row.qty),
				rate: flt(row.rate),
				amount: flt(row.amount)
			}))
		});
	}

	function schedule_tax_preview() {
		if (tax_preview_timer) {
			clearTimeout(tax_preview_timer);
			tax_preview_timer = null;
		}

		if (!cart.length) {
			reset_tax_preview();
			update_summary();
			return;
		}

		let signature = get_tax_preview_signature();

		if (signature === applied_tax_preview_signature || signature === last_tax_preview_signature) {
			return;
		}

		last_tax_preview_signature = signature;
		tax_preview_timer = setTimeout(function() {
			refresh_tax_preview(signature);
		}, 300);
	}

	function refresh_tax_preview(signature, reject_on_error) {
		if (!cart.length) {
			reset_tax_preview();
			update_summary();
			return Promise.resolve();
		}

		let current_signature = signature || get_tax_preview_signature();

		tax_preview_in_flight = true;
		tax_preview_promise = new Promise((resolve, reject) => {

		frappe.call({
			method: 'ledgix_saas.api.taxation.preview_sale_tax_for_form',
			args: {
				items: build_tax_preview_items(),
				posting_date: frappe.datetime.get_today(),
				sale_date: frappe.datetime.get_today(),
				customer: 'Walk-in Customer'
			},
			callback: function(r) {
				tax_preview_in_flight = false;
				tax_preview_promise = null;

				if (current_signature !== get_tax_preview_signature()) {
					resolve(refresh_tax_preview(get_tax_preview_signature(), reject_on_error));
					return;
				}

				let result = r.message || {};
				let payable = result.payable || {};
				let previous_total = get_totals().total;

				pos_tax_preview = result;
				current_tax_amount = flt(payable.total_tax_amount || result.tax_amount || 0);
				current_grand_total = flt(payable.payable_total || result.grand_total || 0);
				applied_tax_preview_signature = current_signature;

				if (!split_payment_enabled && (!single_paid_amount || Math.abs(flt(single_paid_amount) - flt(previous_total)) <= 0.01)) {
					single_paid_amount = current_grand_total || previous_total;
					$('.paid-input').val(single_paid_amount);
				}

				update_summary();
				resolve();
			},
				error: function() {
					tax_preview_in_flight = false;
					tax_preview_promise = null;
					current_tax_amount = 0;
					current_grand_total = 0;
					applied_tax_preview_signature = current_signature;
					update_summary();
					if (reject_on_error) {
						reject(new Error('Tax preview could not be calculated. Please try again before checkout.'));
						return;
					}
					resolve();
				}
			});
			});

		return tax_preview_promise;
	}

	function ensure_latest_tax_preview(force) {
		if (!cart.length) {
			reset_tax_preview();
			return Promise.resolve();
		}

		if (tax_preview_timer) {
			clearTimeout(tax_preview_timer);
			tax_preview_timer = null;
		}

		let signature = get_tax_preview_signature();

		if (!force && signature === applied_tax_preview_signature) {
			return Promise.resolve();
		}

		if (!force && tax_preview_promise && (signature === last_tax_preview_signature || tax_preview_in_flight)) {
			return tax_preview_promise;
		}

		last_tax_preview_signature = signature;
		return refresh_tax_preview(signature, !!force);
	}

	function get_payment_method_list() {
		let methods = payment_methods && payment_methods.length ? payment_methods : split_payment_methods;
		let clean_methods = [];

		methods.forEach(method => {
			if (method && clean_methods.indexOf(method) === -1) {
				clean_methods.push(method);
			}
		});

		return clean_methods.length ? clean_methods : split_payment_methods;
	}

	function get_total_paid() {
		if (!split_payment_enabled) {
			return flt(single_paid_amount);
		}

		return get_payment_method_list().reduce((total, method) => {
			return total + flt(split_payments[method]);
		}, 0);
	}

	function get_cash_paid() {
		if (!split_payment_enabled) {
			return selected_payment_method === 'Cash' ? flt(single_paid_amount) : 0;
		}

		return flt(split_payments['Cash']);
	}

	function get_totals() {
		let subtotal = get_subtotal();
		let discount = get_discount_amount(subtotal);
		let base_total = subtotal - discount;
		let signature = cart.length ? get_tax_preview_signature() : '';
		let has_current_tax = signature && signature === applied_tax_preview_signature;
		let tax = has_current_tax ? current_tax_amount : 0;
		let total = has_current_tax && current_grand_total > 0 ? current_grand_total : base_total + tax;
		let paid = get_total_paid();
		let cash_paid = get_cash_paid();
		let non_cash_paid = Math.max(paid - cash_paid, 0);
		let cash_due = Math.max(total - non_cash_paid, 0);
		let remaining = Math.max(total - paid, 0);
		let change = Math.max(cash_paid - cash_due, 0);

		return { subtotal, discount, tax, total, grand_total: total, paid, remaining, change };
	}

	function update_summary() {
		let totals = get_totals();

		$('.subtotal-value').text(money(totals.subtotal));
		$('.discount-value').text(money(totals.discount));
		$('.tax-value').text(money(totals.tax));
		$('.total-value').text(money(totals.total));
		$('.payment-modal-total-value').text(money(totals.total));
		$('.modal-subtotal-value').text(money(totals.subtotal));
		$('.modal-discount-value').text(money(totals.discount));
		$('.modal-tax-value').text(money(totals.tax));
		$('.paid-value').text(money(totals.paid));
		$('.remaining-value').text(money(totals.remaining));
		$('.change-value').text(money(totals.change));
		render_split_payment_state(totals);
		update_product_card_quantities();

		$('.ledgix-checkout-btn').toggleClass('disabled', cart.length === 0 || !active_shift || sale_processing);
	}

	function render_categories() {
		let html = `
			<button class="category-btn active" data-category="All">
				<span class="category-card-icon">${category_svg_icon('box', 20)}</span>
				<span>All</span>
			</button>
		`;

		categories.forEach(category => {
			html += `
				<button class="category-btn" data-category="${category.name}">
					<span class="category-card-icon">${get_category_visual_html(category)}</span>
					<span>${category.category_name || category.name}</span>
				</button>
			`;
		});

		$('.ledgix-pos-categories').html(html);
	}

	function update_product_card_quantities() {
		refresh_visible_product_cards();
	}

	function get_product_image(item) {
		return item.product_image || item.item_image || item.image || '';
	}

	function render_products(items) {
		if (!items || !items.length) {
			visible_product_items = [];
			$('.ledgix-product-grid').html(`<div class="empty-state">No products found</div>`);
			return;
		}

		visible_product_items = items;
		let hide_stock = pos_stock_visibility === 'hide';
		let html = '';

		items.forEach(item => {
			let stock = get_display_available_stock(item);
			let minimum_stock = flt(item.minimum_stock);
			let stock_class = '';
			let stock_label = `Stock: ${stock}`;
			let add_disabled = is_item_out_of_stock(item);
			let category = get_category_for_item(item);
			let category_label = category.category_name || category.name || item.category || 'Item';
			let accent_color = getComputedStyle(document.documentElement)
				.getPropertyValue('--lx-accent')
				.trim() || get_category_accent(category);
			let product_image = get_product_image(item);
			let image_html = product_image
				? `<div class="product-image-wrap"><img class="product-image" src="${safe_text(product_image)}" alt="" loading="lazy" /></div>`
				: `<div class="product-category-icon">${get_category_visual_html(category)}</div>`;
			let cart_qty = get_cart_item_qty(item.name);

			if (!hide_stock) {
				if (stock <= 0) {
					stock_class = 'out-of-stock';
					stock_label = 'Out of stock';
				} else if (minimum_stock > 0 && stock <= minimum_stock) {
					stock_class = 'low-stock';
					stock_label = `Low stock: ${stock}`;
				}
			}

			html += `
				<div class="ledgix-product-card premium-product-card ${stock_class} ${add_disabled ? 'is-disabled' : ''} ${product_image ? 'has-product-image' : 'has-accent-fill'} ${cart_qty > 0 ? 'is-in-cart' : ''}" data-item="${safe_text(item.name)}" style="--product-accent: ${accent_color};" aria-disabled="${add_disabled ? 'true' : 'false'}">
					<div class="product-card-accent"></div>
					<div class="product-qty-badge ${cart_qty > 0 ? 'is-visible' : ''}">${cart_qty > 0 ? cart_qty : ''}</div>

					<div class="product-card-main">
						${image_html}

						<div class="product-card-info">
							<div class="product-name">${safe_text(item.item_name || item.name)}</div>
							<div class="product-category-label">${safe_text(category_label)}</div>
							<div class="product-card-divider"></div>
						</div>
					</div>

					<div class="product-card-bottom">
						<div>
							<div class="product-price">${money(item.selling_price)}</div>
							${hide_stock ? '' : `<div class="product-meta">${safe_text(stock_label)}</div>`}
						</div>

						<button class="product-add-btn" type="button" title="${add_disabled ? 'Out of stock' : 'Add item'}" ${add_disabled ? 'disabled' : ''}>+</button>
					</div>

					${!hide_stock && stock_class === 'low-stock' ? `<div class="stock-pill ${stock_class}">LOW</div>` : ''}
				</div>
			`;
		});

		$('.ledgix-product-grid').html(html);
	}

	function get_payment_icon_name(method) {
		let key = (method || '').toLowerCase();

		if (key === 'cash') return 'cash';
		if (key === 'card') return 'card';
		if (key === 'bank transfer') return 'bank';
		if (key === 'jazzcash' || key === 'easypaisa') return 'wallet';

		return 'wallet';
	}

	function render_payment_methods() {
		let methods = get_payment_method_list();
		let html = '';

		methods.forEach(method => {
			let active = split_payment_enabled
				? flt(split_payments[method]) > 0
					? 'active'
					: ''
				: method === selected_payment_method
					? 'active'
					: '';
			let short_label = method === 'Bank Transfer' ? 'Bank' : method;
			let icon_name = get_payment_icon_name(method);

			html += `
				<button class="payment-method ${active}" data-method="${method}" ${split_payment_enabled ? 'disabled' : ''}>
					<span class="payment-method-icon">${pos_svg_icon(icon_name, 16)}</span>
					<span>${short_label}</span>
				</button>
			`;
		});

		$('.payment-methods').html(html);
	}

	function render_cart() {
		if (!cart.length) {
			$('.ledgix-cart-list').html(`<div class="empty-state">Cart is empty</div>`);
			reset_tax_preview();
			update_summary();
			return;
		}

		let html = '';

		cart.forEach((row, index) => {
			html += `
				<div class="ledgix-cart-row" data-index="${index}">
					<div class="cart-item-main">
						<div class="cart-item-name">${row.item_name}</div>
						${get_serial_control_html(row, index)}
					</div>

					<div class="cart-qty-control">
						<button class="qty-minus" data-index="${index}">-</button>
						<span>${row.qty}</span>
						<button class="qty-plus" data-index="${index}">+</button>
					</div>

					<input class="cart-rate-input" data-index="${index}" type="number" min="${get_cart_rate_floor(row)}" value="${flt(row.rate)}" />

					<div class="cart-total">${money(flt(row.qty) * flt(row.rate))}</div>

					<button class="cart-remove-btn" data-index="${index}" title="Remove item">×</button>
				</div>
			`;
		});

		$('.ledgix-cart-list').html(html);
		schedule_tax_preview();
		update_summary();
	}

	function show_serial_picker(index) {
		const row = cart[index];

		if (!row || !is_serial_based_row(row)) return;

		const required_qty = cint(row.qty);
		if (required_qty <= 0) {
			frappe.msgprint('Quantity must be greater than zero before choosing serials.');
			return;
		}

		const already_selected = get_manually_selected_serials(index);
		const selected = new Set(get_cart_serials(row));
		const dialog = new frappe.ui.Dialog({
			title: 'Choose Serials',
			size: 'large',
			fields: [
				{
					fieldname: 'serial_picker_html',
					fieldtype: 'HTML'
				}
			],
			primary_action_label: 'Apply',
			primary_action() {
				if (selected.size !== required_qty) return;
				write_cart_serials(row, Array.from(selected));
				render_cart();
				dialog.hide();
			}
		});

		function render_picker(serial_rows, filter_text) {
			const query = (filter_text || '').toLowerCase();
			const filtered = serial_rows.filter(serial => {
				return !query || (serial.serial_number || '').toLowerCase().includes(query);
			});
			const selected_count = selected.size;
			const disabled_apply = selected_count !== required_qty;
			const message = serial_rows.length < required_qty
				? `<div class="text-muted serial-picker-message">Only ${serial_rows.length} available serials found for this item. Backend validation remains final at submit.</div>`
				: '';

			const rows_html = filtered.length
				? filtered.map(serial => {
					const serial_no = serial.serial_number || '';
					const checked = selected.has(serial_no) ? 'checked' : '';
					return `
						<label class="serial-picker-row">
							<input type="checkbox" class="serial-picker-check" value="${safe_text(serial_no)}" ${checked} />
							<span>
								<strong>${safe_text(serial_no)}</strong>
								<small>${safe_text(serial.purchase || '')}${serial.purchase_date ? ` · ${safe_text(serial.purchase_date)}` : ''}</small>
							</span>
						</label>
					`;
				}).join('')
				: `<div class="text-muted serial-picker-empty">No matching available serials.</div>`;

			dialog.fields_dict.serial_picker_html.$wrapper.html(`
				<div class="serial-picker-shell">
					<div class="serial-picker-context">
						<div>
							<strong>${safe_text(row.item_name || row.item)}</strong>
							<div class="text-muted">${safe_text(row.item_code || row.item)}</div>
						</div>
						<div class="serial-picker-count">Selected ${selected_count} of ${required_qty}</div>
					</div>
					<div class="serial-picker-search-wrap">
						<input type="text" class="form-control serial-picker-search" placeholder="Search serial number" value="${safe_text(filter_text || '')}" />
					</div>
					${message}
					<div class="serial-picker-list">${rows_html}</div>
				</div>
			`);

			dialog.$wrapper.find('.modal-footer .btn-primary').prop('disabled', disabled_apply);
			dialog.$wrapper.find('.serial-picker-search').focus();
		}

		dialog.show();
		dialog.$wrapper.addClass('ledgix-pos-themed-dialog ledgix-serial-picker-dialog');
		dialog.$wrapper.find('.modal-footer .btn-primary').prop('disabled', true);
		dialog.fields_dict.serial_picker_html.$wrapper.html('<div class="text-muted">Loading available serials...</div>');

		frappe.call({
			method: 'ledgix_saas.api.pos.get_available_serials_for_pos',
			args: {
				item: row.item,
				limit: 100
			},
			callback(r) {
				const serial_rows = ((r.message && r.message.serials) || []).filter(serial => {
					const serial_no = serial.serial_number || '';
					return selected.has(serial_no) || !already_selected.has(serial_no);
				});

				render_picker(serial_rows, '');

				dialog.$wrapper
					.off('input.serial_picker')
					.on('input.serial_picker', '.serial-picker-search', frappe.utils.debounce(function() {
						render_picker(serial_rows, $(this).val());
					}, 120));

				dialog.$wrapper
					.off('change.serial_picker')
					.on('change.serial_picker', '.serial-picker-check', function() {
						const serial_no = $(this).val();

						if (this.checked) {
							if (selected.size >= required_qty) {
								this.checked = false;
								frappe.show_alert({
									message: `Select exactly ${required_qty} serial${required_qty === 1 ? '' : 's'}.`,
									indicator: 'orange'
								}, 3);
								return;
							}
							selected.add(serial_no);
						} else {
							selected.delete(serial_no);
						}

						render_picker(serial_rows, dialog.$wrapper.find('.serial-picker-search').val());
					});
			},
			error(r) {
				dialog.fields_dict.serial_picker_html.$wrapper.html(`<div class="text-danger">${safe_text(get_frappe_error_message(r) || 'Could not load available serials.')}</div>`);
			}
		});
	}

	function render_split_payment_state(totals) {
		if (split_payment_enabled) {
			$('.payment-mode-label').text('Split payment active');
			$('.split-payment-check').prop('checked', true);
			$('.payment-methods').removeClass('disabled');
			$('.single-paid-row').addClass('hidden');
			$('.split-payment-summary').removeClass('hidden');
			$('.split-paid-value').text(money(totals ? totals.paid : get_total_paid()));
		} else {
			$('.payment-mode-label').text('Single payment active');
			$('.split-payment-check').prop('checked', false);
			$('.payment-methods').removeClass('disabled');
			$('.single-paid-row').removeClass('hidden');
			$('.split-payment-summary').addClass('hidden');
		}

		render_payment_methods();
	}

	function get_payment_modal_html(totals) {
		return `
			<div class="payment-modal-shell">
				<div class="payment-modal-hero">
					<div>
						<div class="payment-modal-kicker">Collect Payment</div>
						<div class="payment-modal-title payment-modal-total-value">${money(totals.total)}</div>
						<div class="payment-modal-subtitle">Invoice ready for current order</div>
					</div>
					<div class="payment-modal-context">
						<span>Customer</span>
						<strong>Walk-in Customer</strong>
					</div>
				</div>

				<div class="payment-modal-grid">
					<div class="payment-modal-main">
						<div class="payment-section-title">Method</div>
						<div class="payment-methods payment-modal-methods"></div>

						<div class="split-payment-summary hidden">
							<div>
								<span>Split Payment</span>
								<strong class="split-paid-value">Rs. 0</strong>
							</div>
							<button class="edit-split-payment-btn">Edit</button>
						</div>

						<button class="payment-split-btn" type="button">Split Payment</button>

						<div class="payment-input-row single-paid-row">
							<span>Amount Paid</span>
							<input type="number" class="paid-input" value="${flt(single_paid_amount || totals.total)}" min="0" />
						</div>

						<div class="quick-cash-row">
							<button type="button" class="quick-cash-btn" data-amount="${totals.total}">Exact</button>
							<button type="button" class="quick-cash-btn" data-amount="500">Rs 500</button>
							<button type="button" class="quick-cash-btn" data-amount="1000">Rs 1000</button>
							<button type="button" class="quick-cash-btn" data-amount="5000">Rs 5000</button>
						</div>

						<div class="payment-keypad" aria-label="Payment keypad">
							${['1','2','3','4','5','6','7','8','9','00','0','.'].map(key => `<button type="button" class="payment-keypad-btn" data-key="${key}">${key}</button>`).join('')}
							<button type="button" class="payment-keypad-btn payment-keypad-clear" data-key="clear">Clear</button>
							<button type="button" class="payment-keypad-btn payment-keypad-back" data-key="back">Back</button>
						</div>
					</div>

					<div class="payment-modal-summary">
						<div class="summary-row"><span>Subtotal</span><strong class="modal-subtotal-value">${money(totals.subtotal)}</strong></div>
						<div class="summary-row"><span>Discount</span><strong class="modal-discount-value">${money(totals.discount)}</strong></div>
						<div class="summary-row"><span>Tax</span><strong class="modal-tax-value">${money(totals.tax)}</strong></div>
						<div class="summary-row grand-total"><span>Total</span><strong class="payment-modal-total-value">${money(totals.total)}</strong></div>
						<div class="summary-row small"><span>Paid</span><strong class="paid-value">${money(totals.paid)}</strong></div>
						<div class="summary-row small"><span>Due</span><strong class="remaining-value">${money(totals.remaining)}</strong></div>
						<div class="summary-row small"><span>Change</span><strong class="change-value">${money(totals.change)}</strong></div>
					</div>
				</div>
			</div>
		`;
	}

	async function show_payment_dialog() {
		if (sale_processing) return;

		if (!active_shift) {
			play_pos_sound('error');
			frappe.msgprint('Please open a POS shift first.');
			return;
		}

		if (!cart.length) {
			play_pos_sound('error');
			frappe.msgprint('Cart is empty.');
			return;
		}

		set_checkout_processing(true);
		try {
			await ensure_latest_tax_preview(true);
		} catch (error) {
			set_checkout_processing(false);
			play_pos_sound('error');
			frappe.msgprint(error.message || 'Tax preview could not be calculated. Please try again before checkout.');
			return;
		}
		set_checkout_processing(false);

		if (!split_payment_enabled && !single_paid_amount) {
			single_paid_amount = get_totals().total;
		}

		let dialog = new frappe.ui.Dialog({
			title: 'Collect Payment',
			size: 'large',
			fields: [
				{
					fieldname: 'payment_html',
					fieldtype: 'HTML'
				}
			],
			primary_action_label: 'Complete Sale',
			async primary_action() {
				let paid_input = dialog.$wrapper.find('.paid-input').val();
				single_paid_amount = flt(paid_input);
				update_summary();
				await complete_sale();
			}
		});

		dialog.show();
		dialog.$wrapper.addClass('ledgix-pos-themed-dialog ledgix-payment-dialog');
		dialog.fields_dict.payment_html.$wrapper.html(get_payment_modal_html(get_totals()));

		render_payment_methods();
		update_summary();

		setTimeout(() => {
			dialog.$wrapper.find('.paid-input').focus().select();
		}, 120);
	}

	function reset_payment_state() {
		split_payment_enabled = false;
		split_payments = {};
		selected_payment_method = 'Cash';
		single_paid_amount = 0;
		current_checkout_client_sale_id = '';
		$('.discount-input').val(0);
		$('.paid-input').val(0);
		$('.split-payment-check').prop('checked', false);
		reset_tax_preview();
		render_payment_methods();
		update_summary();
	}

	function build_payments_payload() {
		if (!split_payment_enabled) {
			return [
				{
					payment_method: selected_payment_method,
					amount: flt(single_paid_amount),
					reference_no: '',
					notes: ''
				}
			];
		}

		let payments = [];

		get_payment_method_list().forEach(method => {
			let amount = flt(split_payments[method]);

			if (amount > 0) {
				payments.push({
					payment_method: method,
					amount: amount,
					reference_no: '',
					notes: 'Split payment'
				});
			}
		});

		return payments;
	}

	function show_split_payment_dialog() {
		let dialog_applied = false;
		let totals = get_totals();
		let methods = get_payment_method_list();

		let fields = [];

		methods.forEach(method => {
			fields.push({
                fieldname: 'pay_' + frappe.scrub(method),
                label: method,
                fieldtype: 'Currency',
                default: split_payments[method] || '',
                description: ''
            });
		});

		fields.push({
			fieldname: 'split_summary_html',
			fieldtype: 'HTML'
		});

		let dialog = new frappe.ui.Dialog({
			title: 'Split Payment',
			fields: fields,
			primary_action_label: 'Apply Split Payment',
			primary_action(values) {
				let new_split_payments = {};

				methods.forEach(method => {
					new_split_payments[method] = flt(values['pay_' + frappe.scrub(method)]);
				});

				split_payments = new_split_payments;
				split_payment_enabled = true;

				selected_payment_method =
					methods.find(method => flt(split_payments[method]) > 0) || 'Cash';

				dialog_applied = true;

				single_paid_amount = get_total_paid();
				$('.paid-input').val(single_paid_amount);
				$('.split-payment-check').prop('checked', true);

				render_payment_methods();
				update_summary();

				dialog.hide();
			}
		});

		function update_dialog_summary() {
			let received = 0;
			let cash_received = 0;

			methods.forEach(method => {
				let fieldname = 'pay_' + frappe.scrub(method);
				let input = dialog.fields_dict[fieldname]?.$input;
				let amount = flt(input ? input.val() : 0);

				received += amount;

				if (method === 'Cash') {
					cash_received = amount;
				}
			});

			let non_cash_received = Math.max(received - cash_received, 0);
			let cash_due = Math.max(totals.total - non_cash_received, 0);
			let remaining = Math.max(totals.total - received, 0);
			let change = Math.max(cash_received - cash_due, 0);

			dialog.fields_dict.split_summary_html.$wrapper.html(`
				<div class="split-summary-box">
					<div>
						<span>Total Due</span>
						<strong>${money(totals.total)}</strong>
					</div>
					<div>
						<span>Received Amount</span>
						<strong>${money(received)}</strong>
					</div>
					<div>
						<span>Remaining</span>
						<strong>${money(remaining)}</strong>
					</div>
					<div>
						<span>Change</span>
						<strong>${money(change)}</strong>
					</div>
				</div>
			`);
		}

		dialog.show();
		dialog.$wrapper.addClass('ledgix-split-dialog ledgix-pos-themed-dialog');

		setTimeout(() => {
			update_dialog_summary();

			methods.forEach(method => {
                let fieldname = 'pay_' + frappe.scrub(method);
                let input = dialog.fields_dict[fieldname]?.$input;

                if (!input) return;

                input.attr('placeholder', '0.00');

                if (input.val() === '0' || input.val() === '0.00') {
                    input.val('');
                }
            });


			dialog.$wrapper.on('input change keyup blur', '.form-control', function() {
				update_dialog_summary();
			});

			dialog.$wrapper.on('hidden.bs.modal', function() {
				if (!dialog_applied) {
					split_payment_enabled = false;
					split_payments = {};
					$('.split-payment-check').prop('checked', false);
					single_paid_amount = 0;
					$('.paid-input').val(0);

					render_payment_methods();
					update_summary();
				}
			});
		}, 200);
	}

	function add_item_to_cart(item) {
		if (!item) return;
		if (!can_add_pos_item(item, true)) return;

		let existing = cart.find(row => row.item === item.name);

		if (existing) {
			existing.qty += 1;
			reset_manual_serials_for_qty_change(existing);
		} else {
			cart.push({
				item: item.name,
				item_name: item.item_name || item.name,
				item_code: item.item_code || '',
				sku: item.sku || '',
				barcode: item.barcode || '',
				tracking_type: item.tracking_type || 'Normal',
				serial_numbers: '',
				qty: 1,
				rate: flt(item.selling_price),
				original_rate: flt(item.selling_price),
				selling_price: flt(item.selling_price),
				stock: get_backend_stock_for_item(item)
			});
		}

		render_cart();
		play_pos_sound('success');
		$('.ledgix-pos-search-input').val('').focus();
	}

	function load_pos_boot_data() {
		$('.ledgix-product-grid').html(`<div class="empty-state pos-loading-state">Loading products...</div>`);

		frappe.call({
			method: 'ledgix_saas.api.api.get_pos_boot_data',
			callback: function(r) {
				if (!r.message) {
					$('.ledgix-product-grid').html(`<div class="empty-state pos-error-state">Unable to load POS data.</div>`);
					return;
				}

				categories = r.message.categories || [];
				all_items = r.message.items || [];
				payment_methods = r.message.payment_methods || [];
				stock_control_mode = r.message.stock_control_mode || 'Strict Inventory';
				apply_pos_theme(r.message.theme_settings || {});

				render_pos_mode_badge();
				apply_pos_stock_visibility();

				render_categories();
				render_payment_methods();
			},
			error: function(r) {
				play_pos_sound('error');
				$('.ledgix-product-grid').html(`<div class="empty-state pos-error-state">Unable to load products. Check connection and retry.</div>`);
				show_pos_notice(get_frappe_error_message(r) || 'Unable to load POS products.', 'red');
			}
		});
	}

	function search_items(query) {
		$('.ledgix-product-grid').addClass('is-searching');

		frappe.call({
			method: 'ledgix_saas.api.api.search_pos_items',
			args: {
				query: query || '',
				category: selected_category
			},
			callback: function(r) {
				$('.ledgix-product-grid').removeClass('is-searching');
				render_products((r.message && r.message.items) || []);
			},
			error: function(r) {
				$('.ledgix-product-grid').removeClass('is-searching');
				play_pos_sound('error');
				$('.ledgix-product-grid').html(`<div class="empty-state pos-error-state">Search failed. Products are still safe in the cart.</div>`);
				show_pos_notice(get_frappe_error_message(r) || 'Item search failed. Please retry.', 'red');
			}
		});
	}

	function scanner_lookup(code) {
		if (!code) return;

		flash_scanner_state('searching');

		frappe.call({
			method: 'ledgix_saas.api.api.get_item_by_barcode_or_sku',
			args: { code: code },
			callback: function(r) {
				if (r.message && r.message.found && r.message.item) {
					flash_scanner_state('success');
					add_item_to_cart(r.message.item);
				} else {
					play_pos_sound('error');
					flash_scanner_state('error');
					show_pos_notice('Barcode or SKU not found. Showing matching products.', 'orange');
					search_items(code);
				}
			},
			error: function(r) {
				play_pos_sound('error');
				flash_scanner_state('error');
				show_pos_notice(get_frappe_error_message(r) || 'Barcode lookup failed. Manual search still works.', 'red');
			}
		});
	}

	function open_scanner_dialog() {
		let stream = null;
		let scan_timer = null;
		let detector = null;
		let zxing_reader = null;

		function stop_camera() {
			if (scan_timer) {
				window.clearInterval(scan_timer);
				scan_timer = null;
			}

			if (zxing_reader && zxing_reader.reset) {
				try {
					zxing_reader.reset();
				} catch (e) {
					// ZXing reset support varies by bundled build.
				}
			}
			zxing_reader = null;

			if (stream) {
				stream.getTracks().forEach(track => track.stop());
				stream = null;
			}
		}

		function complete_detected_code(code) {
			code = (code || '').toString().trim();
			if (!code) return;

			play_pos_sound('success');
			stop_camera();
			dialog.hide();
			$('.ledgix-pos-search-input').val(code);
			scanner_lookup(code);
		}

		function get_zxing_reader_class() {
			let ZXingNS = window.ZXing || window.ZXingBrowser || null;
			return ZXingNS && (ZXingNS.BrowserMultiFormatReader || ZXingNS.BrowserBarcodeReader);
		}

		function load_zxing_asset(callback) {
			if (get_zxing_reader_class()) {
				callback();
				return;
			}

			let existing = document.querySelector('script[data-ledgix-zxing="1"]');
			if (existing) {
				existing.addEventListener('load', callback, { once: true });
				existing.addEventListener('error', callback, { once: true });
				return;
			}

			let script = document.createElement('script');
			script.src = '/assets/frappe/node_modules/html5-qrcode/third_party/zxing-js.umd.js';
			script.async = true;
			script.dataset.ledgixZxing = '1';
			script.onload = callback;
			script.onerror = callback;
			document.head.appendChild(script);
		}

		function start_zxing_decoder(video) {
			let ZXingReader = get_zxing_reader_class();

			if (!ZXingReader) {
				dialog.$wrapper.find('.scanner-state-text').text('Camera barcode engine unavailable. Manual and laser scanning still work.');
				return;
			}

			try {
				zxing_reader = new ZXingReader();

				if (zxing_reader.decodeFromVideoElement) {
					dialog.$wrapper.find('.scanner-state-text').text('Point camera at a barcode.');
					zxing_reader.decodeFromVideoElement(video, function(result) {
						if (result) {
							complete_detected_code(result.getText ? result.getText() : result.text);
						}
					});
					return;
				}
			} catch (e) {
				zxing_reader = null;
			}

			dialog.$wrapper.find('.scanner-state-text').text('Camera barcode engine unavailable. Manual and laser scanning still work.');
		}

		let dialog = new frappe.ui.Dialog({
			title: 'Scan Barcode',
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'scanner_html'
				}
			],
			primary_action_label: 'Use Code',
			primary_action: function() {
				let code = dialog.$wrapper.find('.scanner-manual-input').val().trim();
				if (!code) {
					dialog.$wrapper.find('.scanner-state-text').text('Enter barcode or SKU to continue.');
					return;
				}

				stop_camera();
				dialog.hide();
				$('.ledgix-pos-search-input').val(code);
				scanner_lookup(code);
			}
		});

		dialog.fields_dict.scanner_html.$wrapper.html(`
			<div class="scanner-modal-shell">
				<div class="scanner-camera-stage">
					<video class="scanner-camera-video" autoplay muted playsinline></video>
					<div class="scanner-camera-frame"></div>
				</div>
				<div class="scanner-state-text">Checking camera scanner support...</div>
				<div class="scanner-manual-row">
					<input class="scanner-manual-input" type="text" placeholder="Enter barcode / SKU manually" autocomplete="off" />
				</div>
			</div>
		`);

		dialog.$wrapper.addClass('ledgix-pos-themed-dialog ledgix-scanner-dialog');
		dialog.show();

		dialog.$wrapper.on('hidden.bs.modal', stop_camera);
		dialog.$wrapper.find('.scanner-manual-input').on('keydown', function(e) {
			if (e.key === 'Enter') {
				dialog.get_primary_btn().trigger('click');
			}
		});

		window.setTimeout(function() {
			dialog.$wrapper.find('.scanner-manual-input').focus();
		}, 120);

		if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
			dialog.$wrapper.find('.scanner-state-text').text('Camera scanning is unavailable on this device. Manual and laser scanning still work.');
			return;
		}

		navigator.mediaDevices.getUserMedia({
			video: {
				facingMode: { ideal: 'environment' }
			}
		}).then(function(camera_stream) {
			stream = camera_stream;
			let video = dialog.$wrapper.find('.scanner-camera-video').get(0);
			video.srcObject = stream;

			if (window.BarcodeDetector) {
				try {
					detector = new window.BarcodeDetector({
						formats: ['ean_13', 'ean_8', 'code_128', 'code_39', 'upc_a', 'upc_e', 'qr_code']
					});
				} catch (e) {
					detector = null;
				}
			}

			if (detector) {
				dialog.$wrapper.find('.scanner-state-text').text('Point camera at a barcode.');

				scan_timer = window.setInterval(function() {
					if (!video || video.readyState < 2 || !detector) return;

					detector.detect(video).then(function(codes) {
						if (!codes || !codes.length) return;
						complete_detected_code(codes[0].rawValue || '');
					}).catch(function() {
						dialog.$wrapper.find('.scanner-state-text').text('Camera scanner paused. Manual entry remains available.');
					});
				}, 350);
				return;
			}

			dialog.$wrapper.find('.scanner-state-text').text('Loading camera barcode engine...');
			load_zxing_asset(function() {
				start_zxing_decoder(video);
			});
		}).catch(function() {
			dialog.$wrapper.find('.scanner-state-text').text('Camera unavailable or permission denied. Manual and laser scanning still work.');
		});
	}

    function set_shift_open_state(shift) {
	active_shift = shift;
	$('.pos-shift-badge-stack').css('visibility', 'visible');

	$('.pos-shift-lock').addClass('hidden');
	$('.order-shift-value').text(shift.shift_id || 'Active Shift');

	$('.shift-label')
		.removeClass('closed')
		.addClass('open');

	$('.shift-value')
		.removeClass('closed')
		.addClass('active')
		.text(shift.shift_id || 'Active Shift');

	$('.shift-badge')
		.removeClass('warning')
		.addClass('success')
		.text('Open');

	$('.smart-shift-btn')
		.removeClass('shift-open-btn')
		.addClass('shift-close-btn is-open')
		.attr('title', 'End Shift');

	$('.smart-shift-icon').html(pos_svg_icon('close_shift', 17));
	$('.smart-shift-text').text('End Shift');

	update_shift_metrics(shift);
	update_summary();
	focus_pos_search();
}

function set_shift_closed_state() {
	active_shift = null;
	$('.pos-shift-badge-stack').css('visibility', 'visible');
	$('.order-shift-value').text('No active shift');

	$('.pos-shift-lock').removeClass('hidden');

	$('.shift-label')
		.removeClass('open')
		.addClass('closed');

	$('.shift-value')
		.removeClass('active')
		.addClass('closed')
		.text('Closed');

	$('.shift-badge')
		.removeClass('success')
		.addClass('warning')
		.text('Closed');

	$('.smart-shift-btn')
		.removeClass('shift-close-btn is-open')
		.addClass('shift-open-btn')
		.attr('title', 'Open Shift');

	$('.smart-shift-icon').html(pos_svg_icon('open_shift', 17));
	$('.smart-shift-text').text('Open Shift');

	update_shift_metrics({ invoice_count: 0, shift_sales: 0 });
	update_summary();
}

	function load_active_shift() {
		frappe.call({
			method: 'ledgix_saas.api.api.get_active_shift_info',
			callback: function(r) {
				if (r.message && r.message.has_active_shift) {
					set_shift_open_state(r.message);
				} else {
					set_shift_closed_state();
				}
			},
			error: function() {
				set_shift_closed_state();
				frappe.show_alert({
					message: 'Could not load POS shift status. Please refresh or open a new shift.',
					indicator: 'red'
				}, 5);
			}
		});
	}

// ============================================================
// KEYBOARD SHORTCUT MENU
// ============================================================

	$(document).on('click', '.shortcut-help-btn', function(e) {
		e.preventDefault();
		e.stopPropagation();

		$(this)
			.closest('.shortcut-help-wrap')
			.find('.shortcut-help-menu')
			.toggleClass('open');
	});

	$(document).on('mouseleave', '.shortcut-help-wrap', function() {
		$(this)
			.find('.shortcut-help-menu')
			.removeClass('open');
	});

	function show_open_shift_dialog() {
		let dialog = new frappe.ui.Dialog({
			title: 'Open POS Shift',
			fields: [
				{
					fieldname: 'opening_cash',
					label: 'Opening Cash',
					fieldtype: 'Currency',
					reqd: 1,
					default: 0
				},
				{
					fieldname: 'notes',
					label: 'Opening Notes',
					fieldtype: 'Small Text'
				}
			],
			primary_action_label: 'Start Shift',
			primary_action(values) {
				frappe.call({
					method: 'ledgix_saas.api.api.open_pos_shift',
					args: {
						opening_cash: values.opening_cash || 0,
						notes: values.notes || ''
					},
					freeze: true,
					freeze_message: 'Opening shift...',
					callback: function(r) {
						if (!r.message || !r.message.success) return;

						set_shift_open_state(r.message);

						frappe.show_alert({
							message: r.message.message || 'Shift opened successfully',
							indicator: 'green'
						});

						dialog.hide();
					}
				});
			}
		});

		dialog.show();
		dialog.$wrapper.addClass('ledgix-pos-themed-dialog ledgix-shift-dialog');
	}

	function show_close_shift_dialog() {
		frappe.call({
			method: 'ledgix_saas.api.api.get_active_shift_info',
			callback: function(r) {
				if (!r.message || !r.message.has_active_shift) {
					frappe.msgprint('No active shift found.');
					set_shift_closed_state();
					return;
				}

				let shift = r.message;

				let dialog = new frappe.ui.Dialog({
					title: 'Close POS Shift',
					fields: [
						{
							fieldname: 'expected_cash',
							label: 'Expected Cash',
							fieldtype: 'Currency',
							default: shift.expected_cash || 0,
							read_only: 1
						},
						{
							fieldname: 'actual_cash',
							label: 'Actual Cash',
							fieldtype: 'Currency',
							reqd: 1,
							default: shift.expected_cash || 0
						},
						{
							fieldname: 'closing_notes',
							label: 'Closing Notes',
							fieldtype: 'Small Text'
						}
					],
					primary_action_label: 'Close Shift',
					primary_action(values) {

						frappe.call({
							method: 'ledgix_saas.api.api.close_pos_shift',
							args: {
								actual_cash: values.actual_cash || 0,
								notes: values.closing_notes || ''
							},
							freeze: true,
							freeze_message: 'Closing shift.',
							callback: function(r) {
								if (!r.message || !r.message.success) return;

								set_shift_closed_state();

								frappe.show_alert({
									message: r.message.message || 'Shift closed successfully',
									indicator: 'green'
								});

								dialog.hide();
							}
						});
					}
				});

				dialog.show();
				dialog.$wrapper.addClass('ledgix-pos-themed-dialog ledgix-shift-dialog');
			}
		});
	}

	function get_receipt_row_html(sale) {
		sale = sale || {};

		let sale_id = sale.name || sale.sale_id || '';
		let date_value = sale.creation || sale.sale_date || '';
		let invoice = get_receipt_invoice_no(sale) || sale_id;

		let search_blob = [
			sale_id,
			invoice,
			sale.invoice_number,
			sale.customer_invoice_number,
			sale.sale_invoice_number,
			sale.custom_invoice_number,
			sale.invoice_no,
			sale.items_preview,
			sale.payment_methods,
			sale.total_amount,
			date_value
		].join(' ').toLowerCase();

		return `
			<div class="recent-receipt-row" data-sale-id="${safe_text(sale_id)}" data-search="${safe_text(search_blob)}">
				<div class="recent-receipt-main">
					<div class="recent-receipt-invoice">${safe_text(invoice)}</div>
					<div class="recent-receipt-date">${date_value ? frappe.datetime.str_to_user(date_value) : '-'}</div>
				</div>

				<div class="recent-receipt-preview">${safe_text(sale.items_preview || 'No item details')}</div>

				<div class="recent-receipt-payment">${safe_text(sale.payment_methods || 'Payment')}</div>

				<div class="recent-receipt-total">${money(sale.grand_total || sale.total_amount)}</div>

				<div class="recent-receipt-actions">
					<button class="receipt-row-icon-btn receipt-view-btn" data-sale-id="${safe_text(sale_id)}" title="View Receipt">
						${pos_svg_icon('eye', 18)}
					</button>
					<button class="receipt-row-icon-btn receipt-reprint-btn" data-sale-id="${safe_text(sale_id)}" title="Print Receipt">
						${pos_svg_icon('print', 18)}
					</button>
				</div>
			</div>
		`;
	}

	function filter_recent_receipts(dialog) {
		let query = (dialog.$wrapper.find('.recent-receipts-search-input').val() || '').toLowerCase().trim();
		let visible_count = 0;

		dialog.$wrapper.find('.recent-receipt-row').each(function() {
			let haystack = ($(this).attr('data-search') || '').toLowerCase();
			let is_match = !query || haystack.indexOf(query) !== -1;
			$(this).toggleClass('hidden-by-search', !is_match);
			if (is_match) visible_count += 1;
		});

		dialog.$wrapper.find('.recent-receipts-subtitle').text(
			query ? `${visible_count} matching receipts` : `Showing latest ${visible_count} receipts`
		);

		dialog.$wrapper.find('.recent-receipts-no-match').toggleClass('hidden', visible_count > 0);
	}

	function render_recent_receipts(dialog, sales) {
		let rows_html = '';

		(sales || []).forEach(sale => {
			rows_html += get_receipt_row_html(sale);
		});

		if (!rows_html) {
			rows_html = `
				<div class="recent-receipts-empty">
					<div class="recent-receipts-empty-icon">${pos_svg_icon('receipt', 28)}</div>
					<div>No recent receipts found</div>
				</div>
			`;
		}

		dialog.fields_dict.recent_receipts_html.$wrapper.html(`
			<div class="recent-receipts-shell">
				<div class="recent-receipts-toolbar">
					<div>
						<div class="recent-receipts-title">Recent Receipts</div>
						<div class="recent-receipts-subtitle">Showing latest ${(sales || []).length} receipts</div>
					</div>

					<div class="recent-receipts-controls compact">
						<button class="receipt-refresh-btn" title="Refresh">
							${pos_svg_icon('refresh', 17)}
						</button>
					</div>
				</div>

				<div class="recent-receipts-search-wrap">
					<div class="recent-receipts-search-shell">
						<span class="recent-receipts-search-icon">
							${pos_svg_icon('search', 15)}
						</span>
						<input type="text" class="recent-receipts-search-input has-clear-control" placeholder="Search invoice, item, payment, amount..." autocomplete="off" />
							<button class="modal-search-clear-btn hidden" type="button" data-target=".recent-receipts-search-input">×</button>
					</div>
				</div>

				<div class="recent-receipts-table">
					<div class="recent-receipt-head">
						<div>Invoice Number</div>
						<div>Items</div>
						<div>Payment</div>
						<div>Total</div>
						<div>Actions</div>
					</div>

					<div class="recent-receipts-list">
						${rows_html}
					</div>
					<div class="recent-receipts-no-match hidden">No matching receipts found.</div>
				</div>
			</div>
		`);

		setTimeout(() => {
			dialog.$wrapper.find('.recent-receipts-search-input').focus();
			filter_recent_receipts(dialog);
		}, 100);
	}

	function load_recent_receipts(dialog) {
		if (recent_receipts_loading) return;

		recent_receipts_loading = true;

		dialog.fields_dict.recent_receipts_html.$wrapper.html(`
			<div class="recent-receipts-loading">
				<div class="receipt-loader"></div>
				<div>Loading receipts...</div>
			</div>
		`);

		frappe.call({
			method: 'ledgix_saas.api.api.get_recent_pos_sales',
			args: {
				limit: 80,
				offset: 0
			},
			callback: function(r) {
				recent_receipts_loading = false;

				if (!r.message || !r.message.success) {
					play_pos_sound('error');
					dialog.fields_dict.recent_receipts_html.$wrapper.html(`
						<div class="recent-receipts-empty">Unable to load receipts.</div>
					`);
					return;
				}

				recent_receipts_total = cint(r.message.total_count || 0);
				render_recent_receipts(dialog, r.message.sales || []);
			},
			error: function() {
				recent_receipts_loading = false;
				play_pos_sound('error');
			}
		});
	}

	function fetch_receipt_data(sale_id, callback) {
		if (!sale_id) return;

		frappe.call({
			method: 'ledgix_saas.api.api.get_pos_sale_receipt_data',
			args: {
				sale_id: sale_id
			},
			freeze: true,
			freeze_message: 'Loading receipt...',
			callback: function(r) {
				if (!r.message || !r.message.success || !r.message.receipt) {
					play_pos_sound('error');
					frappe.msgprint('Receipt data not found.');
					return;
				}

				callback(r.message.receipt);
			},
			error: function() {
				play_pos_sound('error');
			}
		});
	}

	function show_receipt_preview_modal(receipt) {
		$('.receipt-preview-overlay').remove();

		let payments_html = '';
		(receipt.payments || []).forEach(payment => {
			payments_html += `
				<div class="receipt-preview-payment-row">
					<span>${safe_text(payment.payment_method || 'Payment')}</span>
					<strong>${money(payment.amount)}</strong>
				</div>
			`;
		});

		if (!payments_html) {
			payments_html = `
				<div class="receipt-preview-payment-row">
					<span>Payment</span>
					<strong>${money(receipt.paid)}</strong>
				</div>
			`;
		}

		let modal_html = `
			<div class="receipt-preview-overlay">
				<div class="receipt-preview-modal">
					<button class="receipt-preview-close-btn" title="Close">${pos_svg_icon('x', 20)}</button>

					<div class="receipt-preview-modal-head">
						<div>
							<div class="receipt-preview-modal-title">Receipt Preview</div>
							<div class="receipt-preview-modal-subtitle">${safe_text(get_receipt_invoice_no(receipt) || receipt.sale_id)}</div>
						</div>
						<button class="receipt-preview-print-btn" data-sale-id="${safe_text(receipt.sale_id)}">
							${pos_svg_icon('print', 17)}
							<span>Print</span>
						</button>
					</div>

					<div class="receipt-preview-paper">
						<div class="receipt-paper-brand">LEDGIX</div>
						<div class="receipt-paper-shop">Ledgix Retail Store</div>
						<div class="receipt-paper-sub">Fast POS • Inventory • Profit Tracking</div>
						<div class="receipt-paper-line"></div>

						<div class="receipt-paper-info">
							<div><span>Invoice</span><strong>${safe_text(get_receipt_invoice_no(receipt) || receipt.sale_id)}</strong></div>
							<div><span>Date</span><strong>${receipt.date_time ? frappe.datetime.str_to_user(receipt.date_time) : '-'}</strong></div>
							<div><span>Cashier</span><strong>${safe_text(receipt.cashier || '-')}</strong></div>
							<div><span>Shift</span><strong>${safe_text(receipt.shift_id || '-')}</strong></div>
						</div>

						<div class="receipt-paper-line"></div>

						<div class="receipt-items-list modal-receipt-items">
							${get_receipt_items_html(receipt)}
						</div>

						<div class="receipt-paper-line"></div>

							<div class="receipt-paper-summary">
								<div><span>Subtotal</span><strong>${money(receipt.subtotal)}</strong></div>
								<div><span>Discount</span><strong>${money(receipt.discount)}</strong></div>
								<div><span>Tax</span><strong>${money(receipt.tax)}</strong></div>
								<div class="grand"><span>Total</span><strong>${money(receipt.total)}</strong></div>
							<div><span>Paid</span><strong>${money(receipt.paid)}</strong></div>
							<div><span>Change</span><strong>${money(receipt.change)}</strong></div>
						</div>

						<div class="receipt-paper-line"></div>

						<div class="receipt-preview-payments">
							<div class="receipt-preview-payments-title">Payment Breakdown</div>
							${payments_html}
						</div>
					</div>
				</div>
			</div>
		`;

		$('body').append(modal_html);
	}

	function open_recent_receipts_dialog() {
		recent_receipts_offset = 0;
		selected_receipt_ids = {};

		let dialog = new frappe.ui.Dialog({
			title: '',
			size: 'extra-large',
			fields: [
				{
					fieldname: 'recent_receipts_html',
					fieldtype: 'HTML'
				}
			]
		});

		dialog.show();
		dialog.$wrapper.addClass('recent-receipts-dialog ledgix-pos-themed-dialog');

		load_recent_receipts(dialog);

		dialog.$wrapper.on('input', '.recent-receipts-search-input', frappe.utils.debounce(function() {
			filter_recent_receipts(dialog);
		}, 120));

		dialog.$wrapper.on('keydown', '.recent-receipts-search-input', function(e) {
			if (e.key === 'Escape') {
				$(this).val('');
				filter_recent_receipts(dialog);
			}
		});

		dialog.$wrapper.on('click', '.receipt-refresh-btn', function() {
			load_recent_receipts(dialog);
		});

		dialog.$wrapper.on('click', '.receipt-view-btn', function() {
			fetch_receipt_data($(this).data('sale-id'), show_receipt_preview_modal);
		});

		dialog.$wrapper.on('click', '.receipt-reprint-btn', function() {
			fetch_receipt_data($(this).data('sale-id'), print_receipt);
		});
	}

	$(document).off('click', '.smart-shift-btn, .shift-lock-open-btn').on('click', '.smart-shift-btn, .shift-lock-open-btn', function() {
		if (active_shift) {
			show_close_shift_dialog();
			return;
		}

		show_open_shift_dialog();
	});

	$(document).off('click', '.recent-receipts-btn').on('click', '.recent-receipts-btn', function() {
		open_recent_receipts_dialog();
	});

	$(document).off('click', '.ledgix-scan-btn').on('click', '.ledgix-scan-btn', function() {
		open_scanner_dialog();
	});


	$(document).off('click', '.category-btn').on('click', '.category-btn', function() {
		selected_category = $(this).data('category');

		$('.category-btn').removeClass('active');
		$(this).addClass('active');

		search_items($('.ledgix-pos-search-input').val());
	});

	$(document).off('click', '.ledgix-product-card').on('click', '.ledgix-product-card', function(e) {
		if ($(this).hasClass('is-disabled')) {
			e.preventDefault();
			return;
		}

		let item_name = $(this).data('item');
		let item = all_items.find(row => row.name === item_name);

		if (!item) {
			frappe.msgprint('Item not found in loaded products.');
			return;
		}

		add_item_to_cart(item);
	});

	$('.ledgix-pos-search-input').on('keydown', function(e) {
		if (e.key === 'Enter') {
			scanner_lookup($(this).val().trim());
		}
	});

	$('.ledgix-pos-search-input').on('input', function() {
		update_pos_search_clear_state();
	});

	$('.ledgix-pos-search-input').on('input', frappe.utils.debounce(function() {
		search_items($(this).val().trim());
	}, 300));

	$(document).off('click', '.ledgix-search-clear-btn').on('click', '.ledgix-search-clear-btn', function(e) {
		e.preventDefault();
		$('.ledgix-pos-search-input').val('').trigger('input').trigger('focus');
		search_items('');
	});

	$(document).off('click', '.qty-plus').on('click', '.qty-plus', function() {
		let index = cint($(this).data('index'));
		if (!cart[index]) return;

		let item = get_item_for_cart_row(cart[index]);
		if (is_item_out_of_stock(item)) {
			play_pos_sound('error');
			frappe.show_alert({
				message: 'Available stock is already in the current cart.',
				indicator: 'red'
			});
			return;
		}

		cart[index].qty += 1;
		reset_manual_serials_for_qty_change(cart[index]);
		render_cart();
	});

	$(document).off('click', '.qty-minus').on('click', '.qty-minus', function() {
		let index = cint($(this).data('index'));
		cart[index].qty -= 1;

		if (cart[index].qty <= 0) {
			cart.splice(index, 1);
		} else {
			reset_manual_serials_for_qty_change(cart[index]);
		}

		render_cart();
	});

	$(document).off('click', '.choose-serials-btn').on('click', '.choose-serials-btn', function() {
		let index = cint($(this).data('index'));
		show_serial_picker(index);
	});

	$(document).off('click', '.serial-auto-btn').on('click', '.serial-auto-btn', function() {
		let index = cint($(this).data('index'));

		if (cart[index]) {
			clear_cart_serials(cart[index]);
			render_cart();
			frappe.show_alert({
				message: 'Serials reset to Auto FIFO.',
				indicator: 'blue'
			}, 3);
		}
	});

	$(document).off('click', '.cart-remove-btn').on('click', '.cart-remove-btn', function() {
		let index = cint($(this).data('index'));

		if (cart[index]) {
			cart.splice(index, 1);
			render_cart();
			play_pos_sound('success');
		}
	});

	$(document).off('input', '.cart-rate-input').on('input', '.cart-rate-input', function() {
		let index = cint($(this).data('index'));
		if (!cart[index]) return;

		cart[index].rate = flt($(this).val());
		schedule_tax_preview();
		update_summary();
		$(this)
			.closest('.ledgix-cart-row')
			.find('.cart-total')
			.text(money(flt(cart[index].qty) * flt(cart[index].rate)));
	});

	$(document).off('blur', '.cart-rate-input').on('blur', '.cart-rate-input', function() {
		let index = cint($(this).data('index'));
		if (!cart[index]) return;

		let entered_rate = flt($(this).val());
		let minimum_rate = get_cart_rate_floor(cart[index]);

		if (entered_rate < minimum_rate && !can_override_pos_rate()) {
			cart[index].rate = minimum_rate;
			$(this).val(minimum_rate);
			play_pos_sound('error');

			frappe.show_alert({
				message: 'Rate cannot be lower than selling price without admin permission.',
				indicator: 'orange'
			}, 5);
		} else {
			cart[index].rate = entered_rate;
		}

		schedule_tax_preview();
		render_cart();
	});

	$('.clear-cart-btn').on('click', function() {
		cart = [];
		reset_payment_state();
		render_cart();
	});

	$(document).off('click', '.payment-method').on('click', '.payment-method', function() {
		selected_payment_method = $(this).data('method');

		$('.payment-method').removeClass('active');
		$(this).addClass('active');
	});

	$(document).off('click', '.discount-type-btn').on('click', '.discount-type-btn', function() {
		discount_type = $(this).data('type');

		$('.discount-type-btn').removeClass('active');
		$(this).addClass('active');

		schedule_tax_preview();
		update_summary();
	});

	$(document).off('input', '.discount-input, .paid-input').on('input', '.discount-input, .paid-input', function() {
		if ($(this).hasClass('paid-input')) {
			single_paid_amount = flt($(this).val());
		} else {
			schedule_tax_preview();
		}
		update_summary();
	});

    $(document).off('focus', '.paid-input, .discount-input')
    .on('focus', '.paid-input, .discount-input', function() {

        if ($(this).val() === '0' || $(this).val() === '0.00') {
            $(this).val('');
        }
    });

    $(document).off('blur', '.paid-input, .discount-input')
    .on('blur', '.paid-input, .discount-input', function() {

        if ($(this).val().trim() === '') {
            $(this).val(0);
        }

        if ($(this).hasClass('discount-input')) {
            schedule_tax_preview();
        }
        update_summary();
    });


$('.ledgix-hold-btn').on('click', function() {
	if (!active_shift) {
		frappe.msgprint('Please open a POS shift first.');
		return;
	}

	if (!cart.length) {
		frappe.msgprint('Cart is empty. Add items before holding a sale.');
		return;
	}

	frappe.call({
		method: 'ledgix_saas.api.api.hold_pos_sale',
		args: {
			cart_items: cart,
			discount_type: discount_type,
			discount_value: flt($('.discount-input').val()),
			notes: ''
		},
		freeze: true,
		freeze_message: 'Holding sale...',
		callback: function(r) {
			if (!r.message || !r.message.success) {
				play_pos_sound('error');
				show_pos_notice((r.message && r.message.message) || 'Unable to hold sale. Cart was preserved.', 'red');
				return;
			}

			frappe.show_alert({
				message: r.message.message,
				indicator: 'green'
			});

			cart = [];
			reset_payment_state();
			render_cart();

			$('.ledgix-pos-search-input').focus();
		},
		error: function(r) {
			play_pos_sound('error');
			show_pos_notice(get_frappe_error_message(r) || 'Hold sale failed. Cart was preserved.', 'red');
		}
	});
});

	$('.ledgix-held-list-btn').on('click', function() {

	frappe.call({
		method: 'ledgix_saas.api.api.get_held_pos_sales',
		freeze: true,
		freeze_message: 'Loading held sales...',
		callback: function(r) {

			let holds = (r.message && r.message.holds) || [];

			if (!holds.length) {
				frappe.msgprint('No held sales found.');
				return;
			}

			let html = `
				<div class="held-sales-list">
			`;

			holds.forEach(hold => {

				let time = frappe.datetime.str_to_user(hold.creation);

				html += `
					<div class="held-sale-card">

						<div class="held-sale-top">
							<div>
								<div class="held-sale-id">${hold.name}</div>
								<div class="held-sale-time">${time}</div>
							</div>

							<div class="held-sale-total">
								${money(hold.total)}
							</div>
						</div>

						<div class="held-sale-meta">
                            <div class="held-sale-item-count">${hold.item_count} Items</div>
                            <div class="held-sale-items-preview">
                                ${hold.items_preview || 'No item details'}
                            </div>
                        </div>

						<div class="held-sale-actions">
							<button class="resume-held-btn" data-hold="${hold.name}">
								Resume
							</button>

							<button class="delete-held-btn" data-hold="${hold.name}">
								Cancel
							</button>
						</div>

					</div>
				`;
			});

			html += `</div>`;

			let dialog = new frappe.ui.Dialog({
				title: 'Held Sales',
				size: 'large',
				fields: [
					{
						fieldname: 'held_sales_html',
						fieldtype: 'HTML'
					}
				]
			});

			dialog.show();
			dialog.$wrapper.addClass('ledgix-pos-themed-dialog ledgix-held-sales-dialog');

			dialog.fields_dict.held_sales_html.$wrapper.html(html);

			dialog.$wrapper.on('click', '.resume-held-btn', function() {

				let hold_id = $(this).data('hold');

				frappe.call({
					method: 'ledgix_saas.api.api.resume_held_pos_sale',
					args: {
						hold_id: hold_id
					},
					freeze: true,
					freeze_message: 'Restoring held sale...',
					callback: function(res) {

						if (!res.message || !res.message.success) return;

						cart = (res.message.cart_items || []).map(row => {
							row.original_rate = flt(row.original_rate || row.selling_price || row.rate);
							row.selling_price = flt(row.selling_price || row.original_rate || row.rate);
							return row;
						});

						discount_type = res.message.discount_type || 'Amount';

						$('.discount-input').val(
							res.message.discount_value || 0
						);

						render_cart();

						dialog.hide();

						frappe.show_alert({
							message: 'Held sale resumed',
							indicator: 'green'
			});
		},
		error: function(r) {
			play_pos_sound('error');
			show_pos_notice(get_frappe_error_message(r) || 'Unable to load held sales.', 'red');
		}
	});
});

			dialog.$wrapper.on('click', '.delete-held-btn', function() {

				let hold_id = $(this).data('hold');

				frappe.confirm(
					'Cancel this held sale?',
					function() {

						frappe.call({
							method: 'ledgix_saas.api.api.delete_held_pos_sale',
							args: {
								hold_id: hold_id
							},
							freeze: true,
							freeze_message: 'Cancelling hold...',
							callback: function(del) {

								if (!del.message || !del.message.success) return;

								dialog.hide();

								frappe.show_alert({
									message: del.message.message,
									indicator: 'orange'
								});
							}
						});

					}
				);

			});

		}
	});

});


function show_pos_return_dialog() {
	let return_sale = null;
	let return_processing = false;
	let return_search_timer = null;

	let return_candidates = [];
	let return_candidates_loading = false;
	let return_candidates_has_more = false;
	let return_candidates_total = 0;
	let return_request_id = 0;
	let return_visible_limit = 3;
	let return_active_index = -1;

	let dialog = new frappe.ui.Dialog({
		title: 'Return',
		size: 'large',
		fields: [
			{
				fieldname: 'return_html',
				fieldtype: 'HTML'
			}
		],
		primary_action_label: 'Process Return',
		primary_action: process_return_action
	});

	dialog.show();
	dialog.$wrapper.addClass('ledgix-pos-themed-dialog ledgix-return-dialog');

	render_return_shell();

	setTimeout(function() {
		dialog.$wrapper.find('.return-sale-search-input').focus();
	}, 120);

	function get_candidate_invoice(sale) {
		sale = sale || {};

		return (
			sale.invoice_number ||
			sale.customer_invoice_number ||
			sale.sale_invoice_number ||
			sale.name ||
			sale.sale_id ||
			''
		);
	}

	function render_return_shell() {
		let mode_label = stock_control_mode === 'Billing Only' ? 'Billing Mode' : 'Inventory Mode';

		dialog.fields_dict.return_html.$wrapper.html(`
			<div class="return-lookup-shell">
				<div class="return-lookup-head">
					<div>
						<label class="return-lookup-label">Original Invoice</label>
						<div class="return-search-hint">Only ${safe_text(mode_label)} invoices are shown.</div>
					</div>
					
				</div>

				<div class="return-combobox">
					<div class="return-lookup-box">
						<input type="text" class="return-sale-search-input has-clear-control" placeholder="Search invoice number or sale ID" autocomplete="off" />
					<button class="modal-search-clear-btn hidden" type="button" data-target=".return-sale-search-input">×</button>
						<button class="return-sale-toggle-btn" type="button" title="Show latest invoices">
							${pos_svg_icon('chevron_right', 17)}
						</button>
					</div>

					<div class="return-suggestions hidden"></div>
				</div>
			</div>

			<div class="return-loaded-area">
				<div class="return-empty-state">Select an invoice to load returnable items.</div>
			</div>
		`);
	}

	function open_return_dropdown() {
		dialog.$wrapper.find('.return-suggestions').removeClass('hidden');
	}

	function close_return_dropdown() {
		return_active_index = -1;

		dialog.$wrapper
			.find('.return-suggestions')
			.addClass('hidden')
			.empty();
	}

	function render_return_dropdown_state(message, state_class) {
		return_active_index = -1;

		dialog.$wrapper.find('.return-suggestions')
			.removeClass('hidden')
			.html(`
				<div class="return-suggestion-state ${state_class || ''}">
					${safe_text(message)}
				</div>
			`);
	}

	function render_return_candidates() {
		let visible_rows = return_candidates.slice(0, return_visible_limit);

		if (!visible_rows.length) {
			render_return_dropdown_state('No matching invoices found for current POS mode.', 'empty');
			return;
		}

		let html = `<div class="return-suggestion-list">`;

		visible_rows.forEach((sale, index) => {
			let sale_id = sale.name || sale.sale_id || '';
			let invoice = get_candidate_invoice(sale);
			let date_value = sale.creation || sale.sale_date || '';
			let active_class = index === return_active_index ? 'active' : '';

			html += `
				<button class="return-suggestion-row ${active_class}" type="button" data-sale-id="${safe_text(sale_id)}">
					<div class="return-suggestion-main">
						<strong>${safe_text(invoice)}</strong>
						<span>${date_value ? frappe.datetime.str_to_user(date_value) : '-'}</span>
					</div>

					<div class="return-suggestion-meta">
						<span>${safe_text(sale.items_preview || 'No item details')}</span>
						<b>${money(sale.grand_total || sale.total_amount)}</b>
					</div>
				</button>
			`;
		});

		html += `</div>`;

		let remaining_local = Math.max(return_candidates.length - return_visible_limit, 0);
		let remaining_total = Math.max(return_candidates_total - return_visible_limit, 0);

		if (remaining_local > 0 || return_candidates_has_more) {
			html += `
				<button class="return-see-more-btn" type="button">
					See more invoices (${remaining_total || remaining_local} more)
				</button>
			`;
		}

		dialog.$wrapper.find('.return-suggestions')
			.removeClass('hidden')
			.html(html);
	}

	function fetch_return_candidates(query, visible_limit, reset) {
		if (return_candidates_loading) return;

		query = (query || '').trim();
		visible_limit = visible_limit || 3;

		let request_id = ++return_request_id;
		let offset = reset ? 0 : return_candidates.length;

		if (reset) {
			return_candidates = [];
			return_candidates_has_more = false;
			return_candidates_total = 0;
			return_active_index = -1;
		}

		return_visible_limit = visible_limit;
		return_candidates_loading = true;

		render_return_dropdown_state('Loading invoices...', 'loading');

		frappe.call({
			method: 'ledgix_saas.api.api.get_recent_pos_sales',
			args: {
				limit: 50,
				offset: offset,
				query: query
			},
			callback: function(r) {
				if (request_id !== return_request_id) return;

				return_candidates_loading = false;

				if (!r.message || !r.message.success) {
					if (reset) return_candidates = [];
					render_return_dropdown_state('Unable to load invoices.', 'error');
					return;
				}

				let rows = r.message.sales || [];

				if (reset) {
					return_candidates = rows;
				} else {
					return_candidates = return_candidates.concat(rows);
				}

				return_candidates_total = cint(r.message.total_count || return_candidates.length);
				return_candidates_has_more = !!r.message.has_more;

				render_return_candidates();
			},
			error: function(r) {
				if (request_id !== return_request_id) return;

				return_candidates_loading = false;
				play_pos_sound('error');
				render_return_dropdown_state(get_frappe_error_message(r) || 'Unable to load recent invoices.', 'error');
			}
		});
	}

	function load_return_sale(sale_id) {
		if (!sale_id) return;

		hide_return_error();
		close_return_dropdown();

		dialog.$wrapper.find('.return-loaded-area').html(`
			<div class="return-loading-state">Loading invoice items...</div>
		`);

		frappe.call({
			method: 'ledgix_saas.api.api.get_pos_sale_for_return',
			args: {
				sale_id: sale_id
			},
			freeze: true,
			freeze_message: 'Loading sale...',
			callback: function(r) {
				if (!r.message || !r.message.success) {
					play_pos_sound('error');
					return_sale = null;

					show_return_error('Sale not found or not returnable in current POS mode.');

					dialog.$wrapper.find('.return-loaded-area').html(`
						<div class="return-empty-state">Select an invoice to load returnable items.</div>
					`);

					return;
				}

				return_sale = r.message;

				dialog.$wrapper
					.find('.return-sale-search-input')
					.val(return_sale.invoice_number || return_sale.sale_id);

				render_return_sale();
			},
			error: function(r) {
				play_pos_sound('error');
				return_sale = null;

				show_return_error(get_frappe_error_message(r) || 'Unable to load sale.');

				dialog.$wrapper.find('.return-loaded-area').html(`
					<div class="return-empty-state">Select an invoice to load returnable items.</div>
				`);
			}
		});
	}

	function render_return_sale() {
		if (!return_sale) return;

		if (!return_sale.items || !return_sale.items.length) {
			dialog.$wrapper.find('.return-loaded-area').html(`
				<div class="return-empty-state">All items from this invoice are already returned.</div>
			`);
			return;
		}

		let rows = '';

		return_sale.items.forEach((row, index) => {
			rows += `
				<div class="return-item-row" data-index="${index}">
					<div class="return-item-main">
						<div class="return-item-name">${safe_text(row.item_name || row.item)}</div>
						<div class="return-item-meta">
							Sold: ${flt(row.sold_qty)} · Returned: ${flt(row.already_returned_qty)} · Available: ${flt(row.returnable_qty)}
						</div>
					</div>

					<div class="return-item-rate">${money(row.rate)}</div>

					<input
						type="number"
						class="return-qty-input"
						data-index="${index}"
						min="0"
						max="${flt(row.returnable_qty)}"
						step="1"
						value="${flt(row.return_qty || 0)}"
					/>

					<div class="return-item-total">${money(0)}</div>
				</div>
			`;
		});

		dialog.$wrapper.find('.return-loaded-area').html(`
			<div class="return-sale-card">
				<div class="return-sale-head">
					<div>
						<div class="return-sale-title">${safe_text(return_sale.invoice_number || return_sale.sale_id)}</div>
						<div class="return-sale-subtitle">
							${safe_text(return_sale.customer || 'Walk-in Customer')} · ${return_sale.sale_date ? frappe.datetime.str_to_user(return_sale.sale_date) : '-'}
						</div>
					</div>

					<div class="return-sale-total">
						<span>Return Total</span>
						<strong class="return-total-value">${money(0)}</strong>
					</div>
				</div>

				<div class="return-items-head">
					<div>Item</div>
					<div>Rate</div>
					<div>Return Qty</div>
					<div>Total</div>
				</div>

				<div class="return-items-list">
					${rows}
				</div>
			</div>
		`);

		update_return_totals();
	}

	function update_return_totals() {
		if (!return_sale || !return_sale.items) return;

		let total = 0;

		dialog.$wrapper.find('.return-qty-input').each(function() {
			let index = cint($(this).data('index'));
			let row = return_sale.items[index];

			if (!row) return;

			let max_qty = flt(row.returnable_qty);
			let qty = flt($(this).val());

			if (qty < 0) qty = 0;
			if (qty > max_qty) qty = max_qty;

			$(this).val(qty);

			row.return_qty = qty;
			row.amount = qty * flt(row.rate);
			row.item_total_profit = qty * flt(row.profit_per_unit);

			total += row.amount;

			$(this)
				.closest('.return-item-row')
				.find('.return-item-total')
				.text(money(row.amount));
		});

		dialog.$wrapper.find('.return-total-value').text(money(total));
	}

	function process_return_action() {
		if (return_processing) return;

		hide_return_error();

		if (!return_sale) {
			play_pos_sound('error');
			show_return_error('Please select an invoice first.');
			return;
		}

		update_return_totals();

		let selected_items = (return_sale.items || []).filter(row => flt(row.return_qty) > 0);

		if (!selected_items.length) {
			play_pos_sound('error');
			show_return_error('Please enter return quantity for at least one item.');
			return;
		}

		set_return_processing(true);

		frappe.call({
			method: 'ledgix_saas.api.api.create_pos_sales_return',
			args: {
				original_sale: return_sale.sale_id,
				return_items: selected_items
			},
			freeze: true,
			freeze_message: 'Processing return...',
			callback: function(r) {
				if (!r.message || !r.message.success) {
					play_pos_sound('error');
					set_return_processing(false);
					show_return_error((r.message && r.message.message) || 'Return could not be completed.');
					return;
				}

				play_pos_sound('success');

				frappe.show_alert({
					message: r.message.message || 'Return completed successfully.',
					indicator: 'green'
				});

				dialog.hide();
				load_active_shift();
				$('.ledgix-pos-search-input').focus();
			},
			error: function(r) {
				play_pos_sound('error');
				set_return_processing(false);
				show_return_error(get_frappe_error_message(r) || 'Return failed due to a server validation error.');
			}
		});
	}

	function set_return_processing(is_processing) {
		return_processing = is_processing;

		dialog.set_primary_action(
			is_processing ? 'Processing...' : 'Process Return',
			is_processing ? function() {} : process_return_action
		);

		dialog.$wrapper
			.find('.modal-footer .btn-primary')
			.prop('disabled', is_processing)
			.toggleClass('disabled', is_processing);
	}

	function show_return_error(message) {
		dialog.$wrapper.find('.return-error-box').remove();

		dialog.fields_dict.return_html.$wrapper.prepend(`
			<div class="return-error-box">
				<div class="return-error-title">Return Failed</div>
				<div class="return-error-message">${safe_text(message || 'Unable to process return.')}</div>
			</div>
		`);
	}

	function hide_return_error() {
		dialog.$wrapper.find('.return-error-box').remove();
	}

	function move_return_active_row(direction) {
		let rows = dialog.$wrapper.find('.return-suggestion-row');

		if (!rows.length) return;

		return_active_index += direction;

		if (return_active_index < 0) {
			return_active_index = rows.length - 1;
		}

		if (return_active_index >= rows.length) {
			return_active_index = 0;
		}

		rows.removeClass('active');

		let active_row = rows.eq(return_active_index);
		active_row.addClass('active');

		let list = dialog.$wrapper.find('.return-suggestion-list');

		if (list.length && active_row.length) {
			active_row[0].scrollIntoView({
				block: 'nearest'
			});
		}
	}

	dialog.$wrapper.on('hidden.bs.modal', function() {
		return_processing = false;
		clearTimeout(return_search_timer);
		$('.ledgix-pos-search-input').focus();
	});

	dialog.$wrapper.on('input', '.return-sale-search-input', function() {
		let query = $(this).val().trim();

		hide_return_error();
		clearTimeout(return_search_timer);

		return_search_timer = setTimeout(function() {
			return_visible_limit = query ? 12 : 3;
			fetch_return_candidates(query, return_visible_limit, true);
		}, 180);
	});

	dialog.$wrapper.on('focus', '.return-sale-search-input', function() {
		let query = $(this).val().trim();

		if (!query) {
			close_return_dropdown();
			return;
		}

		return_visible_limit = 12;
		fetch_return_candidates(query, return_visible_limit, true);
	});

	dialog.$wrapper.on('keydown', '.return-sale-search-input', function(e) {
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			move_return_active_row(1);
			return;
		}

		if (e.key === 'ArrowUp') {
			e.preventDefault();
			move_return_active_row(-1);
			return;
		}

		if (e.key === 'Enter') {
			e.preventDefault();

			let active_row = dialog.$wrapper.find('.return-suggestion-row.active').first();
			let first_row = dialog.$wrapper.find('.return-suggestion-row:visible').first();
			let value = $(this).val().trim();

			if (active_row.length) {
				load_return_sale(active_row.data('sale-id'));
				return;
			}

			if (first_row.length) {
				load_return_sale(first_row.data('sale-id'));
				return;
			}

			if (value) {
				load_return_sale(value);
			}

			return;
		}

		if (e.key === 'Escape') {
			e.preventDefault();
			close_return_dropdown();
		}
	});

	dialog.$wrapper.on('click', '.return-sale-toggle-btn', function() {
		let query = dialog.$wrapper.find('.return-sale-search-input').val().trim();

		hide_return_error();

		if (!dialog.$wrapper.find('.return-suggestions').hasClass('hidden')) {
			close_return_dropdown();
			return;
		}

		return_visible_limit = 12;
		fetch_return_candidates(query, return_visible_limit, true);
	});

	dialog.$wrapper.on('click', '.return-suggestion-row', function() {
		let sale_id = $(this).data('sale-id');
		let invoice = $(this).find('strong').text().trim();

		clearTimeout(return_search_timer);

		dialog.$wrapper.find('.return-sale-search-input').val(invoice || sale_id);

		close_return_dropdown();

		setTimeout(function() {
			load_return_sale(sale_id);
		}, 0);
	});

	dialog.$wrapper.on('click', '.return-see-more-btn', function(e) {
		e.preventDefault();
		e.stopPropagation();

		let query = dialog.$wrapper.find('.return-sale-search-input').val().trim();

		return_visible_limit += 12;
		dialog.$wrapper.find('.return-suggestions').addClass('is-expanded');

		if (return_visible_limit > return_candidates.length && return_candidates_has_more) {
			fetch_return_candidates(query, return_visible_limit, false);
			return;
		}

		render_return_candidates();
	});

	dialog.$wrapper.on('input', '.return-qty-input', function() {
		hide_return_error();
		update_return_totals();
	});

	dialog.$wrapper.on('click', function(e) {
		if (!$(e.target).closest('.return-combobox').length) {
			close_return_dropdown();
		}
	});
}

	$(document).off('click', '.ledgix-return-refund-btn').on('click', '.ledgix-return-refund-btn', function() {
        show_pos_return_dialog();
    });

	$(document).off('change', '.split-payment-check').on('change', '.split-payment-check', function() {
		if ($(this).is(':checked')) {
			$(this).prop('checked', false);
			show_split_payment_dialog();
			return;
		}

		split_payment_enabled = false;
		split_payments = {};
		single_paid_amount = 0;
		$('.paid-input').val(0);

		render_payment_methods();
		update_summary();
	});

	$(document).off('click', '.payment-split-btn').on('click', '.payment-split-btn', function() {
		show_split_payment_dialog();
	});

	$(document).off('click', '.edit-split-payment-btn').on('click', '.edit-split-payment-btn', function() {
		show_split_payment_dialog();
	});

	$(document).off('click', '.quick-cash-btn').on('click', '.quick-cash-btn', function() {
		let amount = flt($(this).data('amount'));
		single_paid_amount = amount;
		$('.paid-input').val(amount);
		update_summary();
	});

	$(document).off('click', '.payment-keypad-btn').on('click', '.payment-keypad-btn', function() {
		let key = ($(this).data('key') || '').toString();
		let $input = $('.ledgix-payment-dialog .paid-input');
		let value = ($input.val() || '').toString();

		if (key === 'clear') {
			value = '';
		} else if (key === 'back') {
			value = value.slice(0, -1);
		} else if (key === '.' && value.indexOf('.') !== -1) {
			return;
		} else {
			value += key;
		}

		$input.val(value);
		single_paid_amount = flt(value);
		update_summary();
	});

	async function complete_sale() {
		if (sale_processing) return;

		if (!active_shift) {
			play_pos_sound('error');
			frappe.msgprint('Please open a POS shift first.');
			return;
		}

		if (!cart.length) {
			play_pos_sound('error');
			frappe.msgprint('Cart is empty.');
			return;
		}

		set_checkout_processing(true);
		try {
			await ensure_latest_tax_preview(true);
		} catch (error) {
			set_checkout_processing(false);
			play_pos_sound('error');
			frappe.msgprint(error.message || 'Tax preview could not be calculated. Please try again before checkout.');
			return;
		}

		if (!current_checkout_client_sale_id) {
			current_checkout_client_sale_id = make_client_sale_id();
		}

		let cart_snapshot = JSON.parse(JSON.stringify(cart));
		let totals_snapshot = get_totals();
		let payments = build_payments_payload();
		let payments_snapshot = JSON.parse(JSON.stringify(payments));
		let sale_cart_payload = cart.map(row => {
			const payload = { ...row };
			const serials = get_cart_serials(row);

			if (serials.length) {
				payload.serial_numbers = serials.join('\n');
			} else {
				delete payload.serial_numbers;
			}

			return payload;
		});

		frappe.call({
			method: 'ledgix_saas.api.api.create_pos_sale',
			args: {
				cart_items: sale_cart_payload,
				payments: payments,
				discount_type: discount_type,
				discount_value: flt($('.discount-input').val()),
				client_sale_id: current_checkout_client_sale_id
			},
			freeze: true,
			freeze_message: 'Completing sale...',
			callback: function(r) {
				if (!r.message || !r.message.success) {
					play_pos_sound('error');
					set_checkout_processing(false);
					show_pos_notice((r.message && r.message.message) || 'Sale could not be completed. Cart and payment values were preserved.', 'red');
					return;
				}

				play_pos_sound('sale');

				let receipt = build_receipt_snapshot(
					r.message,
					cart_snapshot,
					totals_snapshot,
					payments_snapshot
				);

				frappe.show_alert({
					message: r.message.message,
					indicator: 'green'
				});
				$('.ledgix-payment-dialog').modal('hide');

				if (active_shift) {
					active_shift.invoice_count = cint(active_shift.invoice_count || active_shift.shift_invoice_count || active_shift.total_invoices || 0) + 1;
					active_shift.shift_sales = flt(active_shift.shift_sales || active_shift.total_sales || active_shift.sales_total || 0) + flt(receipt.total);
					update_shift_metrics(active_shift);
				}

				cart = [];
				current_checkout_client_sale_id = '';
				reset_payment_state();

				render_cart();
				load_active_shift();
				search_items($('.ledgix-pos-search-input').val());

				set_checkout_processing(false);
				show_receipt_dialog(receipt);
			},
			error: function(r) {
				play_pos_sound('error');
				set_checkout_processing(false);
				show_pos_notice(get_frappe_error_message(r) || 'Checkout failed. Cart and payment values were preserved.', 'red');
			}
		});
	}

	$('.ledgix-checkout-btn').on('click', function() {
		show_payment_dialog();
	});

	$(document).off('input.ledgix_modal_search_clear', '.has-clear-control').on('input.ledgix_modal_search_clear', '.has-clear-control', function() {
		let has_value = !!($(this).val() || '').trim();
		$(this).siblings('.modal-search-clear-btn').toggleClass('hidden', !has_value);
	});

	$(document).off('click.ledgix_modal_search_clear', '.modal-search-clear-btn').on('click.ledgix_modal_search_clear', '.modal-search-clear-btn', function(e) {
		e.preventDefault();
		let target = $(this).data('target');
		let $input = $(this).siblings(target);
		$input.val('').trigger('input').trigger('keyup').trigger('focus');
		$(this).addClass('hidden');
	});

	$(document).off('keydown.ledgix_pos_scanner_focus').on('keydown.ledgix_pos_scanner_focus', function(e) {
		if (!$('.ledgix-pos-app').length || $('.modal:visible').length) return;
		if (e.ctrlKey || e.metaKey || e.altKey) return;

		let tag = (e.target && e.target.tagName || '').toLowerCase();
		let is_editing = tag === 'input' || tag === 'textarea' || tag === 'select' || $(e.target).is('[contenteditable="true"]');

		if (!is_editing && e.key && e.key.length === 1) {
			$('.ledgix-pos-search-input').trigger('focus');
		}
	});

	$(document).off('keydown.ledgix_pos_shortcuts').on('keydown.ledgix_pos_shortcuts', function(e) {
		let tag = (e.target && e.target.tagName || '').toLowerCase();
		let is_typing = tag === 'input' || tag === 'textarea' || tag === 'select';

		if (e.key === 'Escape') {
			$('.ledgix-pos-search-input').val('').focus();
			search_items('');
			return;
		}

		if (is_typing && e.key !== 'F4' && e.key !== 'F6' && e.key !== 'F7' && e.key !== 'F8') {
			return;
		}

		if (e.key === 'F4') {
			e.preventDefault();
			show_payment_dialog();
		}

		if (e.key === 'F6') {
			e.preventDefault();
			$('.ledgix-hold-btn').trigger('click');
		}

		if (e.key === 'F7') {
			e.preventDefault();
			$('.ledgix-held-list-btn').trigger('click');
		}

		if (e.key === 'F8') {
			e.preventDefault();
			$('.ledgix-return-refund-btn').trigger('click');
		}
	});

	$(document).off('click', '.receipt-preview-overlay').on('click', '.receipt-preview-overlay', function(e) {
		if ($(e.target).hasClass('receipt-preview-overlay')) {
			$('.receipt-preview-overlay').remove();
		}
	});

	$(document).off('click', '.receipt-preview-close-btn').on('click', '.receipt-preview-close-btn', function() {
		$('.receipt-preview-overlay').remove();
	});

	$(document).off('click', '.receipt-preview-print-btn').on('click', '.receipt-preview-print-btn', function() {
		let sale_id = $(this).data('sale-id');
		fetch_receipt_data(sale_id, print_receipt);
	});




	load_pos_boot_data();
	load_active_shift();
	render_cart();
	set_pos_viewport_height();

	$(window)
		.off('resize.ledgix_pos_viewport')
		.on('resize.ledgix_pos_viewport', frappe.utils.debounce(set_pos_viewport_height, 120));

	
};



// ============================================================
// POS THEME DIALOG
// ============================================================

function open_pos_theme_dialog() {

	const current_accent =
		window.LedgixTheme?.get?.().primary_accent_color ||
		getComputedStyle(document.documentElement)
			.getPropertyValue('--lx-accent')
			.trim() || '#0f766e';

	let dialog = new frappe.ui.Dialog({
		title: 'Customize POS Theme',
		fields: [
			{
				fieldtype: 'Color',
				fieldname: 'accent_color',
				label: 'Primary Accent Color',
				default: current_accent
			}
		],
		primary_action_label: 'Apply',

		primary_action(values) {
			if (!window.LedgixTheme?.save) {
				frappe.msgprint('Navigator theme service is not available. Please use Ledgix POS Theme Settings.');
				return;
			}

			dialog.disable_primary_action();
			window.LedgixTheme.save({ primary_accent_color: values.accent_color })
				.then(function(theme) {
					const normalizedTheme =
						theme ||
						window.LedgixTheme?.get?.() ||
						window.ledgix_theme ||
						{};

					window.LedgixTheme?.apply?.(normalizedTheme, { broadcast: true });
					apply_pos_theme(normalizedTheme);

					dialog.hide();

					frappe.show_alert({
						message: 'POS theme updated',
						indicator: 'green'
					});
				})
				.catch(function() {
					frappe.msgprint('Failed to update theme.');
				})
				.finally(function() {
					dialog.enable_primary_action();
				});
		}
	});

	dialog.show();
}
