frappe.pages["ledgix-pos"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: "Ledgix POS", single_column: true });
	new LedgixPOSV2(page, wrapper);
};

class LedgixPOSV2 {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = wrapper;
		this.state = {
			sale_channel: "Retail", customer: "", customer_context: null, price_list: "",
			categories: [], category: "All", items: [], cart: [], payment_methods: [], tenders: [],
			active_shift: null, can_b2b: false, can_discount: false, can_override_price: false,
			discount_type: "Amount", discount_value: 0, preview: null, loading: false,
			client_sale_id: "",
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

	escape(value) { return frappe.utils.escape_html(String(value == null ? "" : value)); }
	money(value) { return `Rs. ${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`; }
	payment_method_meta(name) { return this.state.payment_methods.find(row => row.name === name) || null; }
	current_total() { return Number(this.state.preview?.grand_total ?? this.state.cart.reduce((sum, row) => sum + Number(row.qty) * Number(row.override_rate ?? row.rate), 0)); }
	tendered_total() { return this.state.tenders.reduce((sum, row) => sum + Number(row.amount || 0), 0); }
	ensure_client_sale_id() {
		if (!this.state.client_sale_id) {
			this.state.client_sale_id = window.crypto && crypto.randomUUID
				? crypto.randomUUID()
				: `pos-${Date.now()}-${Math.random().toString(36).slice(2)}`;
		}
		return this.state.client_sale_id;
	}

	render_shell() {
		$(this.page.body).html(`
		<div class="lx-pos-v2">
			<header class="lx-pos-topbar">
				<div class="lx-pos-brand-block"><div class="lx-pos-brand-mark">L</div><div><h1>Ledgix POS</h1><div class="lx-pos-subtitle">Fast checkout · server-authoritative pricing</div></div></div>
				<div class="lx-pos-top-actions"><div class="lx-pos-shift-pill"><span class="lx-dot"></span><span class="lx-shift-text">Checking shift…</span></div><button class="btn btn-default btn-sm lx-return-sale">Return</button><button class="btn btn-default btn-sm lx-shift-action">Open Shift</button></div>
			</header>
			<section class="lx-pos-contextbar">
				<div class="lx-channel-toggle"><button class="lx-channel active" data-channel="Retail">Retail</button><button class="lx-channel" data-channel="B2B">B2B</button></div>
				<div class="lx-customer-control"></div>
				<div class="lx-context-fact"><span>Price List</span><strong class="lx-price-list">—</strong></div>
				<div class="lx-context-fact lx-credit-fact hidden"><span>Available Credit</span><strong class="lx-credit-value">—</strong></div>
			</section>
			<div class="lx-pos-grid">
				<section class="lx-catalog-panel">
					<div class="lx-search-row"><div class="lx-search-box"><span class="lx-search-icon">⌕</span><input class="lx-search-input" placeholder="Scan barcode or search item…" autocomplete="off"><kbd>Enter</kbd></div><div class="lx-stock-mode">Live Inventory</div></div>
					<div class="lx-categories"></div><div class="lx-products"></div>
				</section>
				<aside class="lx-cart-panel">
					<div class="lx-cart-head"><div><h2>Current Sale</h2><span class="lx-cart-count">0 items</span></div><button class="btn btn-default btn-xs lx-clear-cart">Clear</button></div>
					<div class="lx-cart-lines"></div>
					<div class="lx-cart-footer">
						<button class="lx-discount-row" type="button"><span>Discount</span><strong class="lx-discount-value">Rs. 0</strong></button>
						<div class="lx-summary-row"><span>Subtotal</span><strong class="lx-subtotal">Rs. 0</strong></div><div class="lx-summary-row"><span>Tax</span><strong class="lx-tax">Rs. 0</strong></div>
						<div class="lx-summary-row lx-total-row"><span>Total</span><strong class="lx-total">Rs. 0</strong></div><div class="lx-summary-row lx-paid-row"><span>Tendered</span><strong class="lx-paid">Rs. 0</strong></div><div class="lx-summary-row lx-remaining-row"><span>Remaining</span><strong class="lx-remaining">Rs. 0</strong></div><div class="lx-summary-row lx-change-row hidden"><span>Change</span><strong class="lx-change">Rs. 0</strong></div>
						<div class="lx-tenders"></div><div class="lx-pos-actions"><button class="btn btn-default lx-hold-sale">Hold</button><button class="btn btn-default lx-held-sales">Held</button><button class="btn btn-primary lx-add-payment">Add Payment</button></div>
						<button class="btn btn-primary btn-lg lx-complete-sale">Complete Sale</button>
					</div>
				</aside>
			</div>
		</div>`);
		this.$root = $(this.page.body).find(".lx-pos-v2");
		this.customer_control = frappe.ui.form.make_control({ parent: this.$root.find(".lx-customer-control"), df: { fieldtype: "Link", options: "Ledgix Customer", fieldname: "customer", label: "Customer", placeholder: "Walk-in Customer" }, render_input: true });
		this.customer_control.$wrapper.addClass("lx-customer-link");
	}

	bind_events() {
		this.$root.on("click", ".lx-channel", e => this.switch_channel($(e.currentTarget).data("channel")));
		this.$root.on("input", ".lx-search-input", e => { clearTimeout(this.search_timer); this.search_timer = setTimeout(() => this.load_items($(e.currentTarget).val()), 180); });
		this.$root.on("keydown", ".lx-search-input", e => { if (e.key === "Enter") { e.preventDefault(); this.add_first_visible_item(); } });
		this.$root.on("click", ".lx-category", e => this.select_category($(e.currentTarget).data("category")));
		this.$root.on("click", ".lx-product", e => this.add_item($(e.currentTarget).data("item")));
		this.$root.on("click", ".lx-qty-minus", e => this.change_qty($(e.currentTarget).closest(".lx-cart-line").data("item"), -1));
		this.$root.on("click", ".lx-qty-plus", e => this.change_qty($(e.currentTarget).closest(".lx-cart-line").data("item"), 1));
		this.$root.on("click", ".lx-remove-line", e => this.remove_item($(e.currentTarget).closest(".lx-cart-line").data("item")));
		this.$root.on("click", ".lx-line-rate", e => this.override_price($(e.currentTarget).closest(".lx-cart-line").data("item")));
		this.$root.on("click", ".lx-clear-cart", () => this.clear_cart());
		this.$root.on("click", ".lx-discount-row", () => this.edit_discount());
		this.$root.on("click", ".lx-add-payment", () => this.add_payment());
		this.$root.on("click", ".lx-remove-tender", e => this.remove_tender(Number($(e.currentTarget).data("index"))));
		this.$root.on("click", ".lx-complete-sale", () => this.complete_sale());
		this.$root.on("click", ".lx-shift-action", () => this.toggle_shift());
		this.$root.on("click", ".lx-return-sale", () => this.start_return());
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
		} catch (error) { this.handle_error(error); }
		finally { this.set_loading(false); }
	}

	apply_boot(boot) {
		Object.assign(this.state, { categories: boot.categories || [], payment_methods: boot.payment_methods || [], active_shift: boot.active_shift || null, can_b2b: !!boot.can_b2b, can_discount: !!boot.can_discount, can_override_price: !!boot.can_override_price, price_list: boot.price_list || "", customer_context: boot.customer || null, customer: boot.customer?.name || "" });
		if (this.state.customer) this.customer_control.set_value(this.state.customer);
		this.$root.find('.lx-channel[data-channel="B2B"]').toggleClass("hidden", !this.state.can_b2b);
		this.render_context(); this.render_categories(); this.render_cart();
	}

	render_context() {
		const retail = this.state.sale_channel === "Retail";
		this.$root.find(".lx-channel").removeClass("active"); this.$root.find(`.lx-channel[data-channel="${this.state.sale_channel}"]`).addClass("active");
		this.$root.find(".lx-price-list").text(this.state.price_list || "Select customer");
		this.$root.find(".lx-credit-fact").toggleClass("hidden", retail); this.$root.find(".lx-credit-value").text(this.money(this.state.customer_context?.available_credit || 0));
		const open = !!this.state.active_shift; this.$root.find(".lx-pos-shift-pill").toggleClass("open", open); this.$root.find(".lx-shift-text").text(open ? `Shift ${this.state.active_shift}` : "No open shift"); this.$root.find(".lx-shift-action").text(open ? "Close Shift" : "Open Shift");
		this.$root.find(".lx-complete-sale").text(retail ? "Complete Sale" : "Post B2B Sale");
	}

	render_categories() {
		const rows = [{ name: "All", category_name: "All" }, ...this.state.categories];
		this.$root.find(".lx-categories").html(rows.map(row => `<button class="lx-category ${row.name === this.state.category ? "active" : ""}" data-category="${this.escape(row.name)}">${this.escape(row.category_name || row.name)}</button>`).join(""));
	}

	async load_items(query = "") {
		if (this.state.sale_channel === "B2B" && !this.state.customer) { this.state.items = []; this.render_products("Select a business customer to load pricing."); return; }
		try {
			const result = await this.call("ledgix_saas.api.v2_pos.search_pos_v2_items", { query, category: this.state.category, customer: this.state.customer, sale_channel: this.state.sale_channel, price_list: this.state.price_list });
			this.state.items = result.items || []; this.state.price_list = result.price_list || this.state.price_list; this.render_products(); this.render_context();
		} catch (error) { this.handle_error(error); }
	}

	render_products(empty_message = "Try another barcode, item name or category.") {
		const $products = this.$root.find(".lx-products");
		if (!this.state.items.length) { $products.html(`<div class="lx-empty"><strong>No items loaded</strong><span>${this.escape(empty_message)}</span></div>`); return; }
		$products.html(this.state.items.map(item => `<button class="lx-product" data-item="${this.escape(item.name)}"><div class="lx-product-code">${this.escape(item.sku || item.item_code || item.barcode || "ITEM")}</div><div class="lx-product-name">${this.escape(item.item_name)}</div><div class="lx-product-meta"><strong>${this.money(item.rate)}</strong><span>${this.escape(item.unit || "")}</span></div><div class="lx-product-stock ${Number(item.current_stock || 0) <= 0 ? "empty" : ""}">${Number(item.current_stock || 0)} in stock</div></button>`).join(""));
	}

	select_category(category) { this.state.category = category || "All"; this.render_categories(); this.load_items(this.$root.find(".lx-search-input").val()); }
	add_first_visible_item() { if (this.state.items.length === 1) this.add_item(this.state.items[0].name); }
	add_item(name) { const item = this.state.items.find(row => row.name === name); if (!item) return; const row = this.state.cart.find(x => x.item === name); if (row) row.qty += 1; else this.state.cart.push({ item: item.name, name: item.item_name, tracking_type: item.tracking_type || "Normal", serial_numbers: "", qty: 1, rate: Number(item.rate || 0), list_rate: Number(item.list_rate || item.rate || 0), override_rate: null, override_reason: "" }); this.state.tenders = []; this.schedule_preview(); this.render_cart(); this.$root.find(".lx-search-input").val("").focus(); }
	change_qty(name, delta) { const row = this.state.cart.find(x => x.item === name); if (!row) return; row.qty = Math.max(0, Number(row.qty || 0) + delta); if (!row.qty) this.state.cart = this.state.cart.filter(x => x.item !== name); this.state.tenders = []; this.schedule_preview(); this.render_cart(); }
	remove_item(name) { this.state.cart = this.state.cart.filter(x => x.item !== name); this.state.tenders = []; this.schedule_preview(); this.render_cart(); }
	clear_cart() { this.state.cart = []; this.state.tenders = []; this.state.discount_value = 0; this.state.preview = null; this.state.client_sale_id = ""; this.render_cart(); }

	async switch_channel(channel) {
		if (channel === this.state.sale_channel || (channel === "B2B" && !this.state.can_b2b)) return;
		this.state.sale_channel = channel; this.clear_cart();
		if (channel === "B2B") { this.state.customer = ""; this.state.customer_context = null; this.customer_control.set_value(""); }
		try { const boot = await this.call("ledgix_saas.api.v2_pos.get_pos_v2_boot", { sale_channel: channel, customer: this.state.customer }); this.apply_boot(boot); if (channel === "Retail" || this.state.customer) await this.load_items(); else this.render_products("Select a business customer to load pricing."); }
		catch (error) { this.handle_error(error); }
	}

	async customer_changed() {
		const customer = this.customer_control.get_value(); if (!customer && this.state.sale_channel === "B2B") { this.state.customer = ""; this.state.items = []; this.render_products("Select a business customer to load pricing."); return; }
		try { const context = await this.call("ledgix_saas.api.v2_pos.get_pos_v2_customer_context", { customer, sale_channel: this.state.sale_channel }); this.state.customer = customer; this.state.sale_channel = context.sale_channel || this.state.sale_channel; this.state.customer_context = context.customer || null; this.state.price_list = context.price_list || ""; this.clear_cart(); this.render_context(); await this.load_items(); }
		catch (error) { this.handle_error(error); }
	}

	cart_payload() { return this.state.cart.map(row => ({ item: row.item, qty: row.qty, serial_numbers: row.serial_numbers || "", override_rate: row.override_rate, override_reason: row.override_reason })); }
	schedule_preview() { clearTimeout(this.preview_timer); if (!this.state.cart.length) { this.state.preview = null; this.render_cart(); return; } this.preview_timer = setTimeout(() => this.preview(), 180); }
	async preview() { try { this.state.preview = await this.call("ledgix_saas.api.v2_pos.preview_pos_v2_checkout", { cart_items: this.cart_payload(), customer: this.state.customer, sale_channel: this.state.sale_channel, price_list: this.state.price_list, discount_type: this.state.discount_type, discount_value: this.state.discount_value }); this.render_cart(); } catch (error) { this.handle_error(error); } }

	render_cart() {
		const $lines = this.$root.find(".lx-cart-lines");
		if (!this.state.cart.length) $lines.html('<div class="lx-empty lx-cart-empty"><strong>Cart is empty</strong><span>Scan a barcode or choose a product.</span></div>');
		else $lines.html(this.state.cart.map(row => `<div class="lx-cart-line" data-item="${this.escape(row.item)}"><div class="lx-line-main"><strong>${this.escape(row.name)}</strong><span>${this.escape(row.item)}</span></div><div class="lx-qty"><button class="lx-qty-minus">−</button><strong>${Number(row.qty)}</strong><button class="lx-qty-plus">+</button></div><button class="lx-line-rate" ${this.state.can_override_price ? "" : "disabled"}>${this.money(row.override_rate ?? row.rate)}</button><strong class="lx-line-total">${this.money(Number(row.qty) * Number(row.override_rate ?? row.rate))}</strong><button class="lx-remove-line">×</button></div>`).join(""));
		const preview = this.state.preview || {}; const subtotal = Number(preview.subtotal ?? this.state.cart.reduce((s, r) => s + Number(r.qty) * Number(r.override_rate ?? r.rate), 0)); const total = Number(preview.grand_total ?? subtotal); const tendered = this.tendered_total(); const remaining = Math.max(total - tendered, 0); const change = this.state.sale_channel === "Retail" ? Math.max(tendered - total, 0) : 0;
		this.$root.find(".lx-cart-count").text(`${this.state.cart.reduce((s, r) => s + Number(r.qty || 0), 0)} items`); this.$root.find(".lx-subtotal").text(this.money(subtotal)); this.$root.find(".lx-discount-value").text(this.money(preview.discount_amount || 0)); this.$root.find(".lx-tax").text(this.money(preview.tax_amount || 0)); this.$root.find(".lx-total").text(this.money(total)); this.$root.find(".lx-paid").text(this.money(tendered)); this.$root.find(".lx-remaining").text(this.money(remaining)); this.$root.find(".lx-change").text(this.money(change)); this.$root.find(".lx-change-row").toggleClass("hidden", change <= 0.005); this.render_tenders();
		this.$root.find(".lx-add-payment").prop("disabled", !this.state.cart.length || !this.state.payment_methods.length || remaining <= 0.005); this.$root.find(".lx-complete-sale").prop("disabled", !this.state.cart.length || (this.state.sale_channel === "Retail" && remaining > 0.005));
	}

	render_tenders() { this.$root.find(".lx-tenders").html(this.state.tenders.map((row, i) => `<div class="lx-tender"><span>${this.escape(row.payment_method)}${row.reference_number ? ` · ${this.escape(row.reference_number)}` : ""}</span><strong>${this.money(row.amount)}</strong><button class="lx-remove-tender" data-index="${i}">×</button></div>`).join("")); }
	edit_discount() { if (!this.state.can_discount) return frappe.show_alert({ message: "Discount requires Manager or Admin access", indicator: "orange" }); frappe.prompt([{ fieldname:"discount_type",fieldtype:"Select",label:"Discount Type",options:"Amount\nPercent",default:this.state.discount_type,reqd:1 },{ fieldname:"discount_value",fieldtype:"Float",label:"Discount Value",default:this.state.discount_value,reqd:1 }], v => { this.state.discount_type=v.discount_type; this.state.discount_value=Math.max(Number(v.discount_value||0),0); this.state.tenders=[]; this.schedule_preview(); }, "Sale Discount", "Apply"); }
	override_price(name) { if (!this.state.can_override_price) return; const row=this.state.cart.find(x=>x.item===name); if(!row)return; frappe.prompt([{fieldname:"rate",fieldtype:"Currency",label:"Override Rate",default:row.override_rate??row.rate,reqd:1},{fieldname:"reason",fieldtype:"Data",label:"Reason",default:row.override_reason||"",reqd:1}],v=>{row.override_rate=Number(v.rate||0);row.override_reason=v.reason;this.state.tenders=[];this.schedule_preview();this.render_cart();},"Authorized Price Override","Apply"); }

	add_payment() {
		if (!this.state.cart.length) return;
		const total = this.current_total();
		const due = Math.max(total - this.tendered_total(), 0);
		if (due <= 0.005) return frappe.show_alert({ message: "Sale is fully tendered", indicator: "blue" });
		const options = this.state.payment_methods.map(row => row.name).join("\n");
		const dialog = new frappe.ui.Dialog({
			title: "Add Payment",
			fields: [
				{ fieldname: "payment_method", fieldtype: "Select", label: "Payment Method", options, default: this.state.payment_methods[0]?.name || "", reqd: 1 },
				{ fieldname: "amount", fieldtype: "Currency", label: "Amount", default: due, reqd: 1 },
				{ fieldname: "reference_number", fieldtype: "Data", label: "Transaction Reference" },
				{ fieldname: "payment_hint", fieldtype: "HTML" },
			],
		});
		const refresh_hint = () => {
			const method = this.payment_method_meta(dialog.get_value("payment_method"));
			const amount = Number(dialog.get_value("amount") || 0);
			const is_cash = method?.method_type === "Cash";
			const can_change = this.state.sale_channel === "Retail" && is_cash && !!method?.allow_change;
			const change = can_change ? Math.max(amount - due, 0) : 0;
			const reference_field = dialog.fields_dict.reference_number;
			const show_reference = !!method && !is_cash;
			const reference_required = show_reference && !!method?.requires_reference;
			reference_field.df.reqd = reference_required ? 1 : 0;
			reference_field.$wrapper.toggle(show_reference);
			reference_field.$input.attr("placeholder", "Bank / terminal / wallet transaction ID");
			if (!show_reference && dialog.get_value("reference_number")) dialog.set_value("reference_number", "");
			let policy;
			if (is_cash) {
				policy = can_change
					? `Cash payment · Change ${this.money(change)}`
					: `Cash payment · Maximum ${this.money(due)}`;
			} else {
				const reference = reference_required ? "Transaction reference required" : "Reference optional";
				policy = `${reference} · Maximum ${this.money(due)}`;
			}
			dialog.fields_dict.payment_hint.$wrapper.html(`<div class="text-muted small">${this.escape(policy)}</div>`);
		};
		dialog.fields_dict.payment_method.$input.on("change", refresh_hint);
		dialog.fields_dict.amount.$input.on("input", refresh_hint);
		dialog.set_primary_action("Add", () => {
			const values = dialog.get_values();
			if (!values) return;
			const method = this.payment_method_meta(values.payment_method);
			const amount = Number(values.amount || 0);
			const reference = String(values.reference_number || "").trim();
			if (!method) return frappe.msgprint("Select a configured payment method.");
			if (amount <= 0) return frappe.msgprint("Payment amount must be greater than zero.");
			if (method.requires_reference && !reference) return frappe.msgprint(`${this.escape(method.name)} requires a transaction reference.`);
			const can_change = this.state.sale_channel === "Retail" && method.method_type === "Cash" && !!method.allow_change;
			if (amount - due > 0.005 && !can_change) return frappe.msgprint(`Payment cannot exceed the remaining amount of ${this.money(due)}.`);
			this.state.tenders.push({ payment_method: values.payment_method, amount, reference_number: reference });
			dialog.hide();
			this.render_cart();
		});
		dialog.show();
		refresh_hint();
	}
	remove_tender(index) { this.state.tenders.splice(index,1); this.render_cart(); }

	async complete_sale() {
		if (!this.state.cart.length || this.state.loading) return;
		try {
			this.set_loading(true);
			const result = await this.call("ledgix_saas.api.v2_pos.complete_pos_v2_sale", {
				cart_items: this.cart_payload(), tenders: this.state.tenders, customer: this.state.customer,
				sale_channel: this.state.sale_channel, price_list: this.state.price_list,
				discount_type: this.state.discount_type, discount_value: this.state.discount_value,
				client_sale_id: this.ensure_client_sale_id(),
			});
			frappe.show_alert({ message: `Sale ${result.invoice_number || result.sale} completed`, indicator: "green" }, 5);
			this.clear_cart();
			if (result.sale) this.handle_post_sale_print(result.sale, result.print_mode);
			await this.refresh_context();
			await this.load_items();
		} catch (error) {
			this.handle_error(error);
		} finally {
			this.set_loading(false);
		}
	}

	print_url(sale, mode) {
		const format = mode === "A4" ? "Ledgix B2B Invoice" : "Ledgix Thermal Receipt";
		return `/printview?doctype=Ledgix%20Sale&name=${encodeURIComponent(sale)}&format=${encodeURIComponent(format)}&no_letterhead=0`;
	}

	handle_post_sale_print(sale, mode) {
		const url = this.print_url(sale, mode);
		if (mode === "A4") {
			frappe.confirm("Open A4 invoice?", () => window.open(url, "_blank"));
			return;
		}
		this.auto_print_retail_receipt(url);
	}

	auto_print_retail_receipt(url) {
		const frame = document.createElement("iframe");
		frame.setAttribute("aria-hidden", "true");
		frame.style.cssText = "position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0;pointer-events:none";
		document.body.appendChild(frame);

		let removed = false;
		const cleanup = () => {
			if (removed) return;
			removed = true;
			frame.remove();
		};

		frame.onload = () => {
			try {
				const target = frame.contentWindow;
				target.addEventListener("afterprint", cleanup, { once: true });
				setTimeout(() => {
					target.focus();
					target.print();
				}, 80);
				setTimeout(cleanup, 120000);
			} catch (error) {
				cleanup();
				const opened = window.open(url, "_blank");
				if (!opened) frappe.show_alert({ message: "Receipt is ready. Allow printing/pop-ups or reprint it from Sales.", indicator: "orange" }, 7);
			}
		};
		frame.src = url;
	}

	async toggle_shift(){if(this.state.active_shift){frappe.prompt([{fieldname:"actual_cash",fieldtype:"Currency",label:"Actual Closing Cash",reqd:1}],async v=>{try{await this.call("ledgix_saas.api.api.close_pos_shift",{actual_cash:v.actual_cash,shift_name:this.state.active_shift});await this.refresh_context();}catch(e){this.handle_error(e);}},"Close Shift","Close");return;}frappe.prompt([{fieldname:"opening_cash",fieldtype:"Currency",label:"Opening Cash",default:0,reqd:1}],async v=>{try{await this.call("ledgix_saas.api.api.open_pos_shift",{opening_cash:v.opening_cash});await this.refresh_context();}catch(e){this.handle_error(e);}},"Open Shift","Open");}
	async refresh_context(){const boot=await this.call("ledgix_saas.api.v2_pos.get_pos_v2_boot",{customer:this.state.customer,sale_channel:this.state.sale_channel});this.apply_boot(boot);}
	start_return(){frappe.prompt([{fieldname:"sale_id",fieldtype:"Data",label:"Sale / Invoice",reqd:1},{fieldname:"reason",fieldtype:"Small Text",label:"Return Reason",reqd:1}],async v=>{try{const sale=await this.call("ledgix_saas.api.v2_returns.get_pos_v2_return_context",{sale_id:v.sale_id});this.show_return_dialog(sale,v.reason);}catch(e){this.handle_error(e);}},"Return / Refund","Load Sale");}
	show_return_dialog(sale,reason){const rows=sale.items||[];const dialog=new frappe.ui.Dialog({title:`Return ${this.escape(sale.invoice_number||sale.sale_id)}`,size:"large",fields:[{fieldname:"items_html",fieldtype:"HTML"}]});dialog.fields_dict.items_html.$wrapper.html(`<div class="lx-return-list">${rows.map((row,i)=>`<div class="lx-return-row"><div><strong>${this.escape(row.item_name||row.item)}</strong><small>Sold ${row.sold_qty} · Already returned ${row.already_returned_qty||0} · Available ${row.returnable_qty||0}</small></div><input type="number" min="0" max="${Number(row.returnable_qty||0)}" step="0.001" value="0" data-return-index="${i}"></div>`).join("")}</div>`);dialog.set_primary_action("Create Return",async()=>{const items=[];dialog.$wrapper.find("[data-return-index]").each((_,el)=>{const i=Number($(el).data("return-index"));const qty=Number($(el).val()||0);if(qty>0)items.push({item:rows[i].item,original_sale_item_row:rows[i].original_sale_item_row,qty});});if(!items.length)return frappe.msgprint("Enter at least one return quantity.");try{const result=await this.call("ledgix_saas.api.v2_returns.create_pos_v2_return",{original_sale:sale.sale_id,return_items:items,reason});dialog.hide();frappe.show_alert({message:`Return ${result.return_id} posted`,indicator:"green"},5);await this.refresh_context();await this.load_items();}catch(e){this.handle_error(e);}});dialog.show();}

	async hold_sale(){
		if(!this.state.cart.length)return;
		try{
			const rows=this.state.cart.map(r=>({item:r.item,qty:r.qty,rate:r.override_rate??r.rate,serial_numbers:r.serial_numbers||""}));
			const result=await this.call("ledgix_saas.api.v2_holds.hold_pos_v2_sale",{cart_items:rows,sale_channel:this.state.sale_channel,customer:this.state.customer,price_list:this.state.price_list,discount_type:this.state.discount_type,discount_value:this.state.discount_value});
			frappe.show_alert({message:`Sale held: ${result.hold_id}`,indicator:"blue"});
			this.clear_cart();
		}catch(e){this.handle_error(e);}
	}

	async restore_hold(resumed,dialog){
		const channel=resumed.sale_channel||"Retail";
		const customer=resumed.customer||"";
		const boot=await this.call("ledgix_saas.api.v2_pos.get_pos_v2_boot",{sale_channel:channel,customer});
		this.state.sale_channel=channel;
		this.apply_boot(boot);
		this.state.sale_channel=channel;
		this.state.customer=customer;
		this.state.price_list=resumed.price_list||boot.price_list||"";
		await this.customer_control.set_value(customer);
		const items=resumed.cart_items||[];
		this.state.cart=items.map(x=>({item:x.item,name:x.item_name||x.item,tracking_type:x.tracking_type||"Normal",serial_numbers:x.serial_numbers||"",qty:Number(x.qty||1),rate:Number(x.rate||0),list_rate:Number(x.rate||0),override_rate:null,override_reason:""}));
		this.state.discount_type=resumed.discount_type||"Amount";
		this.state.discount_value=Number(resumed.discount_value||0);
		this.state.tenders=[];
		this.state.client_sale_id="";
		this.state.preview=null;
		dialog?.hide();
		this.render_context();
		await this.load_items();
		this.schedule_preview();
		this.render_cart();
	}

	async show_held_sales(){
		try{
			const result=await this.call("ledgix_saas.api.v2_holds.get_pos_v2_holds");
			const rows=result.holds||[];
			const d=new frappe.ui.Dialog({title:"Held Sales",size:"large",fields:[{fieldname:"list",fieldtype:"HTML"}]});
			d.fields_dict.list.$wrapper.html(`<div class="lx-held-list">${rows.length?rows.map(r=>`<div class="lx-held-row"><div><strong>${this.escape(r.name)}</strong><small>${this.escape(r.sale_channel||"Retail")}${r.customer?` · ${this.escape(r.customer)}`:""}${r.items_preview?` · ${this.escape(r.items_preview)}`:""}</small></div><span>${this.money(r.total||0)}</span><div class="lx-held-actions"><button class="btn btn-xs btn-primary" data-resume-hold="${this.escape(r.name)}">Resume</button><button class="btn btn-xs btn-default" data-cancel-hold="${this.escape(r.name)}">Cancel</button></div></div>`).join(""):'<div class="lx-empty">No held sales</div>'}</div>`);
			d.fields_dict.list.$wrapper.on("click","[data-resume-hold]",async e=>{try{const resumed=await this.call("ledgix_saas.api.v2_holds.resume_pos_v2_hold",{hold_id:$(e.currentTarget).data("resume-hold")});await this.restore_hold(resumed,d);}catch(err){this.handle_error(err);}});
			d.fields_dict.list.$wrapper.on("click","[data-cancel-hold]",async e=>{try{await this.call("ledgix_saas.api.v2_holds.cancel_pos_v2_hold",{hold_id:$(e.currentTarget).data("cancel-hold")});frappe.show_alert({message:"Held sale cancelled",indicator:"blue"});d.hide();await this.show_held_sales();}catch(err){this.handle_error(err);}});
			d.show();
		}catch(e){this.handle_error(e);}
	}

	set_loading(loading){this.state.loading=!!loading;this.$root.toggleClass("is-loading",!!loading);this.$root.find("button,input").prop("disabled",!!loading);if(!loading){this.$root.find("button,input").prop("disabled",false);this.$root.find('.lx-channel[data-channel="B2B"]').prop("disabled",!this.state.can_b2b);this.render_cart();}}
	handle_error(error){console.error(error);frappe.msgprint({title:"Ledgix POS",message:error?.message||error?.exc||"Ledgix POS request failed.",indicator:"red"});}
}
