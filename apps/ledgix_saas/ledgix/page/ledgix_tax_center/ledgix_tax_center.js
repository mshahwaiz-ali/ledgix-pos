/* global frappe, $ */

frappe.pages["ledgix-tax-center"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Federal FBR POS / IMS V1"),
		single_column: true,
	});
	const body = $('<div class="p-4"></div>').appendTo(page.main);

	$("<h3>").text(__("Legacy Tax & FBR Center retired")).appendTo(body);
	$("<p>")
		.text(__(
			"This route previously exposed Digital Invoicing V1.2 workflows. " +
			"Federal Tier-1 POS / IMS V1 is now the only active FBR runtime."
		))
		.appendTo(body);
	$("<p class=\"text-muted\">")
		.text(__(
			"ERPNext remains the tax and accounting authority. Use the FBR V1 Center for " +
			"POSID/device setup, mappings, readiness, fiscalization, offline evidence, and reconciliation."
		))
		.appendTo(body);

	const actions = $('<div class="mt-3"></div>').appendTo(body);
	$('<button class="btn btn-primary mr-2"></button>')
		.text(__("Open FBR V1 Center"))
		.on("click", () => frappe.set_route("fbr-v1-center"))
		.appendTo(actions);
	$('<button class="btn btn-default mr-2"></button>')
		.text(__("Tax Categories"))
		.on("click", () => frappe.set_route("List", "Tax Category"))
		.appendTo(actions);
	$('<button class="btn btn-default"></button>')
		.text(__("Sales Tax Templates"))
		.on("click", () => frappe.set_route("List", "Sales Taxes and Charges Template"))
		.appendTo(actions);
};
