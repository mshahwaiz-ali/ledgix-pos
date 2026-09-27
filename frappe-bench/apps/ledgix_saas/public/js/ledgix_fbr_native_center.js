/* global frappe, $ */

(() => {
	"use strict";

	function patch_native_fbr_center() {
		const center = frappe?.ledgix_tax_center;
		if (!center || center.__ledgix_native_fbr_phase9) return false;
		center.__ledgix_native_fbr_phase9 = true;
		center.state.fbr.referenceDoctype = center.state.fbr.referenceDoctype || "Sales Invoice";
		center.methods.fbrPreview = "ledgix_saas.api.fbr_native_ui.get_native_fbr_preview";
		center.methods.fbrValidateSandbox = "ledgix_saas.api.fbr_native_ui.validate_native_fbr_sandbox";
		center.methods.fbrValidateProduction = "ledgix_saas.api.fbr_native_ui.validate_native_fbr_production";
		center.methods.fbrSubmitProduction = "ledgix_saas.api.fbr_native.submit_native_to_fbr";

		center.mount_fbr_sale_control = function () {
			const $holder = this.$root.find(".lx-fbr-sale-control");
			if (!$holder.length) return;
			$holder.empty().append(`
				<div class="lx-native-fbr-source">
					<select class="form-control lx-native-fbr-doctype">
						<option value="Sales Invoice" ${this.state.fbr.referenceDoctype === "Sales Invoice" ? "selected" : ""}>Sales Invoice</option>
						<option value="POS Invoice" ${this.state.fbr.referenceDoctype === "POS Invoice" ? "selected" : ""}>POS Invoice</option>
					</select>
					<div class="lx-native-fbr-link"></div>
				</div>
			`);
			$holder.find(".lx-native-fbr-doctype").on("change", (event) => {
				this.state.fbr.referenceDoctype = event.currentTarget.value || "Sales Invoice";
				this.state.fbr.sale = "";
				this.state.fbr.preview = null;
				this.render_fbr();
			});
			let control;
			control = frappe.ui.form.make_control({
				parent: $holder.find(".lx-native-fbr-link")[0],
				df: {
					fieldname: "fbr_native_invoice",
					label: "Submitted ERPNext Invoice",
					fieldtype: "Link",
					options: this.state.fbr.referenceDoctype,
					get_query: () => ({ filters: { docstatus: 1 } }),
					onchange: () => {
						this.state.fbr.sale = control.get_value() || "";
						this.state.fbr.preview = null;
					},
				},
				render_input: true,
			});
			control.set_value(this.state.fbr.sale || "");
		};

		center.preview_fbr = async function () {
			const referenceName = (this.state.fbr.sale || "").trim();
			const referenceDoctype = this.state.fbr.referenceDoctype || "Sales Invoice";
			if (!referenceName) return frappe.msgprint("Select a submitted ERPNext invoice first.");
			try {
				this.state.fbr.preview = await this.call(this.methods.fbrPreview, {
					reference_doctype: referenceDoctype,
					reference_name: referenceName,
				});
				this.render_fbr();
			} catch (error) {
				this.show_error("Could not preview native FBR payload.", error);
			}
		};

		center.validate_fbr = function (environment) {
			const referenceName = (this.state.fbr.sale || "").trim();
			const referenceDoctype = this.state.fbr.referenceDoctype || "Sales Invoice";
			if (!referenceName || !this.state.fbr.preview) return frappe.msgprint("Preview the ERPNext invoice first.");
			const production = environment === "production";
			frappe.confirm(
				production
					? "Send this immutable ERPNext invoice payload to the FBR Production Validate API?"
					: "Send this immutable ERPNext invoice payload to FBR Sandbox Validate?",
				async () => {
					try {
						const method = production ? this.methods.fbrValidateProduction : this.methods.fbrValidateSandbox;
						const result = await this.call(method, {
							reference_doctype: referenceDoctype,
							reference_name: referenceName,
						});
						frappe.msgprint({
							title: production ? "Production validation" : "Sandbox validation",
							message: this.escape(result.error_message || result.status || "Validation completed."),
							indicator: result.status === "Failed" ? "red" : "green",
						});
						await this.load_fbr();
						this.state.fbr.referenceDoctype = referenceDoctype;
						this.state.fbr.sale = referenceName;
						await this.preview_fbr();
					} catch (error) {
						this.show_error("FBR validation failed.", error);
					}
				},
			);
		};

		center.submit_fbr = function () {
			const referenceName = (this.state.fbr.sale || "").trim();
			const referenceDoctype = this.state.fbr.referenceDoctype || "Sales Invoice";
			if (!referenceName || !this.state.fbr.preview?.can_submit_now) {
				return frappe.msgprint("This ERPNext invoice is not currently eligible for Production Submit.");
			}
			frappe.confirm(
				`Submit ${this.escape(referenceDoctype)} ${this.escape(referenceName)} to the LIVE FBR production system?`,
				async () => {
					try {
						const result = await this.call(this.methods.fbrSubmitProduction, {
							reference_doctype: referenceDoctype,
							reference_name: referenceName,
						});
						frappe.msgprint({
							title: "FBR Production Submit",
							message: this.escape(result.error_message || result.status || "Submission completed."),
							indicator: result.status === "Failed" ? "red" : "green",
						});
						await this.load_fbr();
					} catch (error) {
						this.show_error("FBR production submission failed.", error);
					}
				},
			);
		};

		center.start_fbr_correction = function () {
			const referenceName = (this.state.fbr.sale || "").trim();
			const referenceDoctype = this.state.fbr.referenceDoctype || "Sales Invoice";
			if (!referenceName) return frappe.msgprint("Select a submitted ERPNext FBR invoice first.");
			frappe.new_doc("Ledgix FBR Correction Request", {
				reference_doctype: referenceDoctype,
				reference_name: referenceName,
			});
		};

		if (center.state.area === "fbr") center.render_fbr();
		return true;
	}

	function schedule_patch() {
		window.setTimeout(patch_native_fbr_center, 0);
		window.setTimeout(patch_native_fbr_center, 250);
		window.setTimeout(patch_native_fbr_center, 750);
	}

	if (frappe?.router?.on) frappe.router.on("change", schedule_patch);
	$(document).on("page-change", schedule_patch);
	schedule_patch();
})();
