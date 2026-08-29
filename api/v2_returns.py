from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from ledgix_saas.api.pos import _allocate_return_items_from_sale, get_pos_sale_for_return
from ledgix_saas.api.security import require_ledgix_cashier_or_above
from ledgix_saas.api.settings import get_stock_control_mode, sale_matches_current_stock_mode


@frappe.whitelist()
def get_pos_v2_return_context(sale_id=None):
	"""Return the authoritative submitted-sale rows available for POS return."""
	require_ledgix_cashier_or_above()
	return get_pos_sale_for_return(sale_id=sale_id)


@frappe.whitelist()
def create_pos_v2_return(original_sale=None, return_items=None, reason=None):
	"""Create a submitted correction against exact original Sale Item rows."""
	require_ledgix_cashier_or_above()
	return_items = frappe.parse_json(return_items) if isinstance(return_items, str) else return_items
	reason = str(reason or "").strip()

	if not original_sale:
		frappe.throw(_("Original sale is required."))
	if not return_items:
		frappe.throw(_("No return items selected."))
	if not reason:
		frappe.throw(_("Return Reason is required."))
	if not frappe.db.exists("Ledgix Sale", original_sale):
		frappe.throw(_("Original sale was not found."))

	sale = frappe.get_doc("Ledgix Sale", original_sale)
	if sale.docstatus != 1:
		frappe.throw(_("Only submitted sales can be returned."))
	if not sale_matches_current_stock_mode(sale.name):
		frappe.throw(
			_("This invoice belongs to a different stock mode. Current mode: {0}.").format(
				get_stock_control_mode()
			)
		)

	allocations = _allocate_return_items_from_sale(sale, return_items)
	if not allocations:
		frappe.throw(_("Enter a return quantity for at least one item."))

	return_doc = frappe.new_doc("Ledgix Sales Return")
	return_doc.original_sale = sale.name
	return_doc.return_reason = reason
	for row in allocations:
		return_doc.append("items", row)
	return_doc.insert(ignore_permissions=True)
	return_doc.submit()

	return {
		"success": True,
		"return_id": return_doc.name,
		"original_sale": sale.name,
		"customer": return_doc.customer,
		"total_amount": flt(return_doc.total_amount),
		"tax_amount": flt(return_doc.tax_amount),
		"grand_total": flt(return_doc.grand_total or return_doc.total_amount),
		"fbr_status": return_doc.fbr_status or "",
	}
