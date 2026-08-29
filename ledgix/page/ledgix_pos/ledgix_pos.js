frappe.pages["ledgix-pos"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Ledgix POS",
		single_column: true,
	});

	new LedgixPOSV2(page, wrapper);
};

class LedgixPOSV2 {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = wrapper;
		this.state = {
			sale_channel: "Retail",
			customer: "",
			customer_context: null,
			price_list: "",
			categories: [],
			category: "All",
			items: [],
			cart: [],
			payment_methods: [],
			tenders: [],
			active_shift: null,
			stock_control_mode: "",
			can_b2b: false,
			can_discount: false,
			can_override_price: false,
			discount_type: "Amount",
			discount_value: 0,
			preview: null,
			loading: false,
		};
		this.search_timer = null;
		this.preview_timer = null;
		this.render_shell();
		this.bind_events();
		this.boot();
	}

	async call(method, args = {}) {
		const response = await frappe.call({ method, args, freeze: false });
		return response.message || {};
	}

	escape(value) {
		return frappe.utils.escape_html(String(value == null ? "" : value));
	}

	money(value) {
		return `Rs. ${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
	}

	render_shell() {
		$(this.page.body).html(`
			<div class="lx-pos-v2">
				<header class="lx-pos-topbar">
					<div class="lx-pos-brand-block">
						<div class="lx-pos-brand-mark">L</div>
						<div>
							<h1>Ledgix POS</h1>
							<div class="lx-pos-subtitle">Fast checkout · server-authoritative pricing</div>
						</div>
					</div>
					<div class="lx-pos-top-actions">
						<div class="lx-pos-shift-pill"><span class="lx-dot"></span><span class="lx-shift-text">Checking shift…</span></div>
						<button class="btn btn-default btn-sm lx-shift-action">Open Shift</button>
					</div>
				</header>

				<section class="lx-pos-contextbar">
					<div class="lx-channel-toggle">
						<button class="lx-channel active" data-channel="Retail">Retail</button>
						<button class="lx-channel" data-channel="B2B">B2B</button>
					</div>
					<div class="lx-customer-control"></div>
					<div class="lx-context-fact"><span>Price List</span><strong class="lx-price-list">—</strong></div>
					<div class="lx-context-fact lx-credit-fact hidden"><span>Available Credit</span><strong class="lx-credit-value">—</strong></div>
				</section>

				<div class="lx-pos-grid">
					<section class="lx-catalog-panel">
						<div class="lx-search-row">
							<div class="lx-search-box">
								<span class="lx-search-icon">⌕</span>
								<input class="lx-search-input" placeholder="Scan barcode or search item…" autocomplete="off" />
								<kbd>Enter</kbd>
							</div>
							<div class="lx-stock-mode"></div>
						</div>
						<div class="lx-categories"></div>
						<div class="lx-products"></div>
					</section>

					<aside class="lx-cart-panel">
						<div class="lx-cart-head">
							<div><h2>Current Sale</h2><span class="lx-cart-count">0 items</span></div>
							<button class="btn btn-default btn-xs lx-clear-cart">Clear</button>
						</div>
						<div class="lx-cart-lines"></div>
						<div class="lx-cart-footer">
							<button class="lx-discount-row" type="button"><span>Discount</span><strong class="lx-discount-value">Rs. 0</strong></button>
							<div class="lx-summary-row"><span>Subtotal</span><strong class="lx-subtotal">Rs. 0</strong></div>
							<div class="lx-summary-row"><span>Tax</span><strong class="lx-tax">Rs. 0</strong></div>
							<div class="lx-summary-row lx-total-row"><span>Total</span><strong class="lx-total">Rs. 0</strong></div>
							<div class="lx-summary-row lx-paid-row"><span>Paid</span><strong class="lx-paid">Rs. 0</strong></div>
							<div class="lx-summary-row lx-remaining-row"><span>Remaining</span><strong class="lx-remaining">Rs. 0</strong></div>
							<div class="lx-tenders"></div>
							<div class="lx-pos-actions">
								<button class="btn btn-default lx-hold-sale">Hold</button>
								<button class="btn btn-default lx-held-sales">Held</button>
								<button class="btn btn-primary lx-add-payment">Add Payment</button>
							</div>
							<button class="btn btn-primary btn-lg lx-complete-sale">Complete Sale</button>
						</div>
					</aside>
				</div>
			</div>
		`);

		this.$root = $(this.page.body).find(".lx-pos-v2");
		this.customer_control = frappe.ui.form.make_control({
			parent: this.$root.find(".lx-customer-control"),
			df: {
				fieldtype: "Link",
				options: "Ledgix Customer",
				fieldname: "customer",
				label: "Customer",
				placeholder: "Walk-in Customer",
			},
			render_input: true,
		});
		this.customer_control.$wrapper.addClass("lx-customer-link");
	}

	bind_events() {
		this.$root.on("click", ".lx-channel", (event) => this.switch_channel($(event.currentTarget).data("channel")));
		this.$root.on("input", ".lx-search-input", (event) => {
			clearTimeout(this.search_timer);
			this.search_timer = setTimeout(() => this.load_items($(event.currentTarget).val()), 180);
		});
		this.$root.on("keydown", ".lx-search-input", (event) => {
			if (event.key === "Enter") {
				event.preventDefault();
				this.add_first_visible_item();
			}
		});
		this.$root.on("click", ".lx-category", (event) => this.select_category($(event.currentTarget).data("category")));
		this.$root.on("click", ".lx-product", (event) => this.add_item($(event.currentTarget).data("item")));
		this.$root.on("click", ".lx-qty-minus", (event) => this.change_qty($(event.currentTarget).closest(".lx-cart-line").data("item"), -1));
		this.$root.on("click", ".lx-qty-plus", (event) => this.change_qty($(event.currentTarget).closest(".lx-cart-line").data("item"), 1));
		this.$root.on("click", ".lx-remove-line", (event) => this.remove_item($(event.currentTarget).closest(".lx-cart-line").data("item")));
		this.$root.on("click", ".lx-line-rate", (event) => this.override_price($(event.currentTarget).closest(".lx-cart-line").data("item")));
		this.$root.on("click", ".lx-clear-cart", () => this.clear_cart());
		this.$root.on("click", ".lx-discount-row", () => this.edit_discount());
		this.$root.on("click", ".lx-add-payment", () => this.add_payment());
		this.$root.on("click", ".lx-remove-tender", (event) => this.remove_tender(Number($(event.currentTarget).data("index"))));
		this.$root.on("click", ".lx-complete-sale", () => this.complete_sale());
		this.$root.on("click", ".lx-shift-action", () => this.toggle_shift());
		this.$root.on("click", ".lx-hold-sale", () => this.hold_sale());
		this.$root.on("click", ".lx-held-sales", () => this.show_held_sales());
		this.customer_control.$input.on("change", () => this.customer_changed());
	}

	async boot() {
		try {
			this.set_loading(true);
			const boot = await this.call("ledgix_saas.api.v2_pos.get_pos_v2_boot", { sale_channel: this.state.sale_channel });
			this.apply_boot(boot);
			await this.load_items();
		} catch (error) {
			this.handle_error(error);
		} finally {
			this.set_loading(false);
		}
	}

	apply_boot(boot) {
		Object.assign(this.state, {
			categories: boot.categories || [],
			payment_methods: boot.payment_methods || [],
			active_shift: boot.active_shift || null,
			stock_control_mode: boot.stock_control_mode || "",
			can_b2b: !!boot.can_b2b,
			can_discount: !!boot.can_discount,
			can_override_price: !!boot.can_override_price,
			price_list: boot.price_list || "",
			customer_context: boot.customer || null,
			customer: boot.customer?.name || "",
		});
		if (this.state.customer) this.customer_control.set_value(this.state.customer);
		this.$root.find('.lx-channel[data-channel="B2B"]').toggleClass("hidden", !this.state.can_b2b);
		this.render_context();
		this.render_categories();
		this.render_cart();
	}

	render_context() {
		const retail = this.state.sale_channel === "Retail";
		this.$root.find(".lx-channel").removeClass("active");
		this.$root.find(`.lx-channel[data-channel="${this.state.sale_channel}"]`).addClass("active");
		this.$root.find(".lx-price-list").text(this.state.price_list || "Legacy item price");
		this.$root.find(".lx-credit-fact").toggleClass("hidden", retail);
		this.$root.find(".lx-credit-value").text(this.money(this.state.customer_context?.available_credit || 0));
		this.$root.find(".lx-stock-mode").text(this.state.stock_control_mode || "Inventory");
		const open = !!this.state.active_shift;
		this.$root.find(".lx-pos-shift-pill").toggleClass("open", open);
		this.$root.find(".lx-shift-text").text(open ? `Shift ${this.state.active_shift}` : "No open shift");
		this.$root.find(".lx-shift-action").text(open ? "Close Shift" : "Open Shift");
		this.$root.find(".lx-complete-sale").text(this.state.sale_channel === "B2B" ? "Post B2B Sale" : "Complete Sale");
	}

	render_categories() {
		const rows = [{ name: "All", category_name: "All" }, ...this.state.categories];
		this.$root.find(".lx-categories").html(rows.map((row) => `
			<button class="lx-category ${row.name === this.state.category ? "active" : ""}" data-category="${this.escape(row.name)}">
				${this.escape(row.category_name || row.name)}
			</button>
		`).join(""));
	}

	async load_items(query = "") {
		try {
			const result = await this.call("ledgix_saas.api.v2_pos.search_pos_v2_items", {
				query,
				category: this.state.category,
				customer: this.state.customer,
				sale_channel: this.state.sale_channel,
				price_list: this.state.price_list,
			});
			this.state.items = result.items || [];
			this.state.price_list = result.price_list || this.state.price_list;
			this.render_products();
			this.render_context();
		} catch (error) {
			this.handle_error(error);
		}
	}

	render_products() {
		const $products = this.$root.find(".lx-products");
		if (!this.state.items.length) {
			$products.html(`<div class="lx-empty"><strong>No items found</strong><span>Try another barcode, item name or category.</span></div>`);
			return;
		}
		$products.html(this.state.items.map((item) => `
			<button class="lx-product" data-item="${this.escape(item.name)}">
				<div class="lx-product-code">${this.escape(item.sku || item.item_code || item.barcode || "ITEM")}</div>
				<div class="lx-product-name">${this.escape(item.item_name)}</div>
				<div class="lx-product-meta"><strong>${this.money(item.rate)}</strong><span>${this.escape(item.unit || "")}</span></div>
				<div class="lx-product-stock ${Number(item.current_stock || 0) <= 0 ? "empty" : ""}">${Number(item.current_stock || 0)} in stock</div>
			</button>
		`).join(""));
	}

	select_category(category) {
		this.state.category = category || "All";
		this.render_categories();
		this.load_items(this.$root.find(".lx-search-input").val());
	}

	add_first_visible_item() {
		if (this.state.items.length === 1) this.add_item(this.state.items[0].name);
	}

	add_item(item_name) {
		const item = this.state.items.find((row) => row.name === item_name);
		if (!item) return;
		const existing = this.state.cart.find((row) => row.item === item_name);
		if (existing) existing.qty += 1;
		else this.state.cart.push({ item: item.name, name: item.item_name, qty: 1, rate: Number(item.rate || 0), list_rate: Number(item.list_rate || item.rate || 0), override_rate: null, override_reason: "" });
		this.state.tenders = [];
		this.schedule_preview();
		this.render_cart();
		this.$root.find(".lx-search-input").val("").focus();
	}

	change_qty(item_name, delta) {
		const row = this.state.cart.find((item) => item.item === item_name);
		if (!row) return;
		row.qty = Math.max(0, Number(row.qty || 0) + delta);
		if (!row.qty) this.state.cart = this.state.cart.filter((item) => item.item !== item_name);
		this.state.tenders = [];
		this.schedule_preview();
		this.render_cart();
	}

	remove_item(item_name) {
		this.state.cart = this.state.cart.filter((row) => row.item !== item_name);
		this.state.tenders = [];
		this.schedule_preview();
		this.render_cart();
	}

	clear_cart() {
		this.state.cart = [];
		this.state.tenders = [];
		this.state.discount_value = 0;
		this.state.preview = null;
		this.render_cart();
	}

	async switch_channel(channel) {
		if (channel === this.state.sale_channel) return;
		if (channel === "B2B" && !this.state.can_b2b) return;
		this.state.sale_channel = channel;
		this.clear_cart();
		if (channel === "B2B") this.customer_control.set_value("");
		try {
			const boot = await this.call("ledgix_saas.api.v2_pos.get_pos_v2_boot", { sale_channel: channel, customer: this.customer_control.get_value() });
			this.apply_boot(boot);
			await this.load_items();
		} catch (error) {
			this.handle_error(error);
		}
	}

	async customer_changed() {
		const customer = this.customer_control.get_value();
		if (!customer && this.state.sale_channel === "B2B") return;
		try {
			const context = await this.call("ledgix_saas.api.v2_pos.get_pos_v2_customer_context", { customer, sale_channel: this.state.sale_channel });
			this.state.customer = customer;
			this.state.sale_channel = context.sale_channel || this.state.sale_channel;
			this.state.customer_context = context.customer || null;
			this.state.price_list = context.price_list || "";
			this.clear_cart();
			this.render_context();
			await this.load_items();
		} catch (error) {
			this.handle_error(error);
		}
	}

	cart_payload() {
		return this.state.cart.map((row) => ({
			item: row.item,
			qty: row.qty,
			override_rate: row.override_rate,
			override_reason: row.override_reason,
		}));
	}

	schedule_preview() {
		clearTimeout(this.preview_timer);
		if (!this.state.cart.length) {
			this.state.preview = null;
			this.render_cart();
			return;
		}
		this.preview_timer = setTimeout(() => this.preview(), 180);
	}

	async preview() {
		try {
			this.state.preview = await this.call("ledgix_saas.api.v2_pos.preview_pos_v2_checkout", {
				cart_items: this.cart_payload(),
				customer: this.state.customer,
				sale_channel: this.state.sale_channel,
				price_list: this.state.price_list,
				discount_type: this.state.discount_type,
				discount_value: this.state.discount_value,
			});
			this.render_cart();
		} catch (error) {
			this.handle_error(error);
		}
	}

	render_cart() {
		const $lines = this.$root.find(".lx-cart-lines");
		if (!this.state.cart.length) {
			$lines.html(`<div class="lx-empty lx-cart-empty"><strong>Cart is empty</strong><span>Scan a barcode or choose a product.</span></div>`);
		} else {
			$lines.html(this.state.cart.map((row) => `
				<div class="lx-cart-line" data-item="${this.escape(row.item)}">
					<div class="lx-line-main"><strong>${this.escape(row.name)}</strong><span>${this.escape(row.item)}</span></div>
					<div class="lx-qty"><button class="lx-qty-minus">−</button><strong>${Number(row.qty)}</strong><button class="lx-qty-plus">+</button></div>
					<button class="lx-line-rate" ${this.state.can_override_price ? "" : "disabled"}>${this.money(row.override_rate ?? row.rate)}</button>
					<strong class="lx-line-total">${this.money(Number(row.qty) * Number(row.override_rate ?? row.rate))}</strong>
					<button class="lx-remove-line">×</button>
				</div>
			`).join(""));
		}

		const preview = this.state.preview || {};
		const subtotal = Number(preview.subtotal ?? this.state.cart.reduce((sum, row) => sum + Number(row.qty) * Number(row.override_rate ?? row.rate), 0));
		const total = Number(preview.grand_total ?? subtotal);
		const paid = this.state.tenders.reduce((sum, row) => sum + Number(row.amount || 0), 0);
		const remaining = Math.max(total - paid, 0);
		this.$root.find(".lx-cart-count").text(`${this.state.cart.reduce((sum, row) => sum + Number(row.qty || 0), 0)} items`);
		this.$root.find(".lx-subtotal").text(this.money(subtotal));
		this.$root.find(".lx-discount-value").text(this.money(preview.discount_amount || 0));
		this.$root.find(".lx-tax").text(this.money(preview.tax_amount || 0));
		this.$root.find(".lx-total").text(this.money(total));
		this.$root.find(".lx-paid").text(this.money(paid));
		this.$root.find(".lx-remaining").text(this.money(remaining));
		this.render_tenders();
		this.$root.find(".lx-add-payment").prop("disabled", !this.state.cart.length || !this.state.payment_methods.length);
		this.$root.find(".lx-complete-sale").prop("disabled", !this.state.cart.length || (this.state.sale_channel === "Retail" && remaining > 0.005));
	}

	render_tenders() {
		this.$root.find(".lx-tenders").html(this.state.tenders.map((row, index) => `
			<div class="lx-tender"><span>${this.escape(row.payment_method)}${row.reference_number ? ` · ${this.escape(row.reference_number)}` : ""}</span><strong>${this.money(row.amount)}</strong><button class="lx-remove-tender" data-index="${index}">×</button></div>
		`).join(""));
	}

	edit_discount() {
		if (!this.state.can_discount) {
			frappe.show_alert({ message: "Discount requires Manager or Admin access", indicator: "orange" });
			return;
		}
		frappe.prompt([
			{ fieldname: "discount_type", fieldtype: "Select", label: "Discount Type", options: "Amount\nPercent", default: this.state.discount_type, reqd: 1 },
			{ fieldname: "discount_value", fieldtype: "Float", label: "Discount Value", default: this.state.discount_value, reqd: 1 },
		], (values) => {
			this.state.discount_type = values.discount_type;
			this.state.discount_value = Math.max(Number(values.discount_value || 0), 0);
			this.state.tenders = [];
			this.schedule_preview();
		}, "Sale Discount", "Apply");
	}

	override_price(item_name) {
		if (!this.state.can_override_price) return;
		const row = this.state.cart.find((item) => item.item === item_name);
		if (!row) return;
		frappe.prompt([
			{ fieldname: "rate", fieldtype: "Currency", label: "Override Rate", default: row.override_rate ?? row.rate, reqd: 1 },
			{ fieldname: "reason", fieldtype: "Data", label: "Reason", default: row.override_reason || "", reqd: 1 },
		], (values) => {
			row.override_rate = Number(values.rate || 0);
			row.override_reason = values.reason;
			this.state.tenders = [];
			this.schedule_preview();
			this.render_cart();
		}, "Authorized Price Override", "Apply");
	}

	add_payment() {
		if (!this.state.cart.length) return;
		const options = this.state.payment_methods.map((row) => row.name).join("\n");
		const total = Number(this.state.preview?.grand_total || 0);
		const paid = this.state.tenders.reduce((sum, row) => sum + Number(row.amount || 0), 0);
		const due = Math.max(total - paid, 0);
		frappe.prompt([
			{ fieldname: "payment_method", fieldtype: "Select", label: "Payment Method", options, default: this.state.payment_methods[0]?.name || "", reqd: 1 },
			{ fieldname: "amount", fieldtype: "Currency", label: "Amount Tendered", default: due, reqd: 1 },
			{ fieldname: "reference_number", fieldtype: "Data", label: "Reference Number" },
		], (values) => {
			if (Number(values.amount || 0) <= 0) return;
			this.state.tenders.push({ payment_method: values.payment_method, amount: Number(values.amount), reference_number: values.reference_number || "" });
			this.render_cart();
		}, "Add Payment", "Add");
	}

	remove_tender(index) {
		this.state.tenders.splice(index, 1);
		this.render_cart();
	}

	async complete_sale() {
		if (!this.state.cart.length || this.state.loading) return;
		try {
			this.set_loading(true);
			const result = await this.call("ledgix_saas.api.v2_pos.complete_pos_v2_sale", {
				cart_items: this.cart_payload(),
				tenders: this.state.tenders,
				customer: this.state.customer,
				sale_channel: this.state.sale_channel,
				price_list: this.state.price_list,
				discount_type: this.state.discount_type,
				discount_value: this.state.discount_value,
				client_sale_id: (window.crypto && crypto.randomUUID ? crypto.randomUUID() : `pos-${Date.now()}-${Math.random()}`),
			});
			frappe.show_alert({ message: `Sale ${result.invoice_number || result.sale} completed`, indicator: "green" }, 5);
			this.clear_cart();
			if (result.sale) this.offer_print(result.sale, result.print_mode);
			await this.refresh_context();
			await this.load_items();
		} catch (error) {
			this.handle_error(error);
		} finally {
			this.set_loading(false);
		}
	}

	offer_print(sale, mode) {
		const format = mode === "A4" ? "Ledgix B2B Invoice" : "Ledgix Thermal Receipt";
		frappe.confirm(`Print ${mode === "A4" ? "A4 invoice" : "receipt"}?`, () => {
			window.open(`/printview?doctype=Ledgix%20Sale&name=${encodeURIComponent(sale)}&format=${encodeURIComponent(format)}&no_letterhead=0`, "_blank");
		});
	}

	async toggle_shift() {
		if (this.state.active_shift) {
			frappe.prompt([{ fieldname: "actual_cash", fieldtype: "Currency", label: "Actual Closing Cash", reqd: 1 }], async (values) => {
				try {
					await this.call("ledgix_saas.api.api.close_pos_shift", { actual_cash: values.actual_cash, shift_name: this.state.active_shift });
					await this.refresh_context();
				} catch (error) { this.handle_error(error); }
			}, "Close Shift", "Close");
			return;
		}
		frappe.prompt([{ fieldname: "opening_cash", fieldtype: "Currency", label: "Opening Cash", default: 0, reqd: 1 }], async (values) => {
			try {
				await this.call("ledgix_saas.api.api.open_pos_shift", { opening_cash: values.opening_cash });
				await this.refresh_context();
			} catch (error) { this.handle_error(error); }
		}, "Open Shift", "Open");
	}

	async refresh_context() {
		const boot = await this.call("ledgix_saas.api.v2_pos.get_pos_v2_boot", { customer: this.state.customer, sale_channel: this.state.sale_channel });
		this.apply_boot(boot);
	}

	async hold_sale() {
		if (!this.state.cart.length) return;
		try {
			const rows = this.state.cart.map((row) => ({ item: row.item, qty: row.qty, rate: row.override_rate ?? row.rate }));
			const result = await this.call("ledgix_saas.api.pos.hold_pos_sale", { cart_items: rows, discount_type: this.state.discount_type, discount_value: this.state.discount_value });
			frappe.show_alert({ message: `Sale held: ${result.hold_id}`, indicator: "blue" });
			this.clear_cart();
		} catch (error) { this.handle_error(error); }
	}

	async show_held_sales() {
		try {
			const result = await this.call("ledgix_saas.api.pos.get_held_pos_sales");
			const rows = result.holds || result.sales || [];
			const dialog = new frappe.ui.Dialog({ title: "Held Sales", fields: [{ fieldname: "list", fieldtype: "HTML" }] });
			const html = rows.length ? rows.map((row) => `<button class="lx-held-row" data-hold="${this.escape(row.name)}"><strong>${this.escape(row.name)}</strong><span>${this.money(row.total || 0)}</span></button>`).join("") : `<div class="lx-empty">No held sales</div>`;
			dialog.fields_dict.list.$wrapper.html(`<div class="lx-held-list">${html}</div>`);
			dialog.fields_dict.list.$wrapper.on("click", ".lx-held-row", async (event) => {
				const hold = $(event.currentTarget).data("hold");
				try {
					const resumed = await this.call("ledgix_saas.api.pos.resume_held_pos_sale", { hold_id: hold });
					const items = resumed.items || resumed.cart_items || [];
					this.state.cart = items.map((item) => ({ item: item.item, name: item.item_name || item.item, qty: Number(item.quantity || item.qty || 1), rate: Number(item.rate || 0), list_rate: Number(item.rate || 0), override_rate: null, override_reason: "" }));
					this.state.discount_type = resumed.discount_type || "Amount";
					this.state.discount_value = Number(resumed.discount_value || 0);
					this.state.tenders = [];
					dialog.hide();
					this.schedule_preview();
					this.render_cart();
				} catch (error) { this.handle_error(error); }
			});
			dialog.show();
		} catch (error) { this.handle_error(error); }
	}

	set_loading(loading) {
		this.state.loading = !!loading;
		this.$root.toggleClass("is-loading", !!loading);
		this.$root.find("button, input").prop("disabled", !!loading);
		if (!loading) {
			this.$root.find(".lx-search-input").prop("disabled", false);
			this.render_cart();
		}
	}

	handle_error(error) {
		console.error(error);
		const message = error?.message || error?.exc || "Ledgix POS request failed.";
		frappe.msgprint({ title: "Ledgix POS", message, indicator: "red" });
	}
}
