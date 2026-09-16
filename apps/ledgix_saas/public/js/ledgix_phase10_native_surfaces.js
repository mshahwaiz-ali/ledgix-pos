/* global frappe, $, LedgixPOSV2 */

(() => {
    "use strict";

    function patch_pos_printing() {
        if (typeof LedgixPOSV2 === "undefined" || LedgixPOSV2.prototype.__ledgix_phase10_print) return false;
        const proto = LedgixPOSV2.prototype;
        proto.__ledgix_phase10_print = true;

        proto.print_url = function (result) {
            const doctype = result?.print_doctype || result?.doctype;
            const name = result?.native_document;
            const format = result?.print_format;
            if (!doctype || !name || !format) return "";
            return `/printview?doctype=${encodeURIComponent(doctype)}&name=${encodeURIComponent(name)}&format=${encodeURIComponent(format)}&no_letterhead=1`;
        };

        proto.handle_post_sale_print = function (result) {
            const url = this.print_url(result);
            if (!url) return frappe.show_alert({ message: "Native invoice posted; print target was unavailable.", indicator: "orange" }, 6);
            if (result.print_mode === "A4") {
                frappe.confirm("Open Ledgix A4 invoice?", () => window.open(url, "_blank"));
                return;
            }
            this.auto_print_retail_receipt(url);
        };

        proto.complete_sale = async function () {
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
                    client_sale_id: this.ensure_client_sale_id(),
                });
                const reference = result.native_document || result.invoice_number || result.invoice || "ERPNext invoice";
                frappe.show_alert({ message: `${reference} completed`, indicator: "green" }, 5);
                this.clear_cart();
                if (!result.print_deferred && result.native_document) this.handle_post_sale_print(result);
                await this.refresh_context();
                await this.load_items();
            } catch (error) {
                this.handle_error(error);
            } finally {
                this.set_loading(false);
            }
        };
        return true;
    }

    function native_bi_timeline_row(center, row) {
        const event = row.cycle_status || row.event_type || "Activity";
        const identity = row.serial_no || row.batch_no || row.lot_number || "";
        const referenceDoctype = row.reference_doctype || "";
        const reference = row.reference_name || row.reference || row.sale || row.purchase || row.sales_return || "";
        let qty = Number(row.qty || 0);
        if (event === "Sale") qty = -Number(row.sale_qty || Math.abs(row.qty || 0));
        else if (event === "Return") qty = Number(row.return_qty || Math.abs(row.qty || 0));
        else if (event === "Purchase") qty = Number(row.purchased_qty || row.qty || 0);
        const rate = Number(row.sale_rate || 0) || Number(row.cost_rate || row.valuation_rate || 0);
        const profit = Number(row.profit || 0) - Number(row.loss || 0);
        const ref = referenceDoctype && reference
            ? `<button class="lx-ii-link" data-route-doc="${center.escape(referenceDoctype)}" data-name="${center.escape(reference)}">${center.escape(reference)}</button>`
            : center.escape(reference || "—");
        return `<tr><td>${center.escape(row.date || row.posting_date || "—")}</td><td><span class="lx-ii-event is-${center.escape(String(event).toLowerCase().replace(/\s+/g, "-"))}">${center.escape(event)}</span></td><td><strong>${center.escape(row.item_name || row.item || "—")}</strong><small>${center.escape(identity)}</small></td><td>${ref}</td><td>${center.escape(row.customer || row.supplier || row.warehouse || "—")}</td><td>${center.number(qty, 2)}</td><td>${center.number(row.running_qty ?? row.qty_after_transaction ?? 0, 2)}</td><td>${center.money(rate)}</td><td class="${profit < 0 ? "is-negative" : profit > 0 ? "is-positive" : ""}">${center.money(profit)}</td></tr>`;
    }

    function patch_inventory_intelligence() {
        const center = frappe?.ledgix_inventory_intelligence;
        if (!center || center.__ledgix_phase10_native) return false;
        center.__ledgix_phase10_native = true;

        const holder = center.$root.find(".lx-ii-item-control");
        if (holder.length) {
            const current = center.itemControl?.get_value?.() || center.state.item || "";
            center.itemControl?.$input?.off("change");
            holder.empty();
            center.itemControl = frappe.ui.form.make_control({
                parent: holder[0],
                df: { fieldname: "item", label: "Item", fieldtype: "Link", options: "Item", placeholder: "All Items" },
                render_input: true,
            });
            center.itemControl?.$wrapper?.addClass("lx-ii-frappe-control");
            center.itemControl.set_value(current);
            center.itemControl?.$input?.on("change", () => {
                if (!center.suppressControlReload) center.load_data();
            });
        }

        center.timeline_row_html = function (row) {
            return native_bi_timeline_row(this, row);
        };

        const rewriteRoutes = () => {
            const $root = center.$root;
            $root.find('[data-route-list="Ledgix Item"]').attr("data-route-list", "Item");
            $root.find('[data-route-list="Ledgix Stock Movement"]').removeAttr("data-route-list").attr("data-route-report", "Stock Ledger");
            $root.find('[data-route-report="Ledgix Current Stock"]').attr("data-route-report", "Stock Balance");
            $root.find('[data-route-list="Ledgix Stock Lot"]').removeAttr("data-route-list").attr("data-route-list", "Batch").text("Open Batches");
        };

        const originalRender = center.render_data.bind(center);
        center.render_data = function () {
            originalRender();
            rewriteRoutes();
        };
        rewriteRoutes();
        center.load_data();
        return true;
    }

    function schedule_patch() {
        window.setTimeout(patch_pos_printing, 0);
        window.setTimeout(patch_pos_printing, 250);
        window.setTimeout(patch_pos_printing, 750);
        window.setTimeout(patch_inventory_intelligence, 0);
        window.setTimeout(patch_inventory_intelligence, 250);
        window.setTimeout(patch_inventory_intelligence, 750);
    }

    if (frappe?.router?.on) frappe.router.on("change", schedule_patch);
    $(document).on("page-change", schedule_patch);
    schedule_patch();
})();
