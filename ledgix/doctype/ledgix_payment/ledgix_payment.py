import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class LedgixPayment(Document):
	def validate(self):
		self._validate_payment_method()
		self._validate_amounts()
		self._validate_allocations()

	def _validate_payment_method(self):
		method = frappe.db.get_value(
			"Ledgix Payment Method",
			self.payment_method,
			["method_type", "enabled", "requires_reference", "allow_change"],
			as_dict=True,
		)
		if not method:
			frappe.throw(_("Unknown payment method: {0}").format(self.payment_method or ""))
		if not cint(method.enabled):
			frappe.throw(_("Payment Method {0} is disabled.").format(self.payment_method))
		if cint(method.requires_reference) and not (self.reference_number or "").strip():
			frappe.throw(_("Reference number is required for Payment Method {0}.").format(self.payment_method))

		self.flags.payment_method_type = method.method_type or "Other"
		self.flags.payment_method_allows_change = bool(cint(method.allow_change))

	def _validate_amounts(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Payment amount must be greater than zero."))
		if not flt(self.amount_tendered):
			self.amount_tendered = flt(self.amount)
		if flt(self.amount_tendered) < flt(self.amount):
			frappe.throw(_("Amount tendered cannot be less than the payment amount."))

		change_amount = max(flt(self.amount_tendered) - flt(self.amount), 0)
		if change_amount > 0.005:
			if self.flags.payment_method_type != "Cash":
				frappe.throw(_("Only cash payment methods can return change."))
			if not self.flags.payment_method_allows_change:
				frappe.throw(_("Payment Method {0} does not allow cash change.").format(self.payment_method))
		self.change_amount = change_amount

	def _validate_allocations(self):
		allocated = 0.0
		allocations_by_sale = {}
		for row in self.allocations:
			row_amount = flt(row.allocated_amount)
			if row_amount <= 0:
				frappe.throw(_("Payment allocation amount must be greater than zero."))
			if row.reference_doctype != "Ledgix Sale":
				frappe.throw(_("Ledgix V2 payments can currently be allocated only to Ledgix Sale."))
			if not row.reference_name or not frappe.db.exists("Ledgix Sale", row.reference_name):
				frappe.throw(_("Sale not found for payment allocation."))

			sale_customer = frappe.db.get_value("Ledgix Sale", row.reference_name, "customer")
			if not self.customer:
				self.customer = sale_customer
			if sale_customer != self.customer:
				frappe.throw(_("Payment cannot be allocated across different customers."))

			allocated += row_amount
			allocations_by_sale[row.reference_name] = flt(allocations_by_sale.get(row.reference_name)) + row_amount

		if allocated - flt(self.amount) > 0.005:
			frappe.throw(_("Payment allocations cannot exceed the payment amount."))

		if allocations_by_sale and not self.reversal_of:
			from ledgix_saas.services.receivables import get_customer_receivables

			receivables = get_customer_receivables(self.customer)
			outstanding_by_sale = {
				row.get("sale"): flt(row.get("outstanding"))
				for row in receivables.get("invoices") or []
			}
			for sale_name, allocation_amount in allocations_by_sale.items():
				outstanding = flt(outstanding_by_sale.get(sale_name))
				if allocation_amount - outstanding > 0.005:
					frappe.throw(
						_("Payment allocation for Sale {0} exceeds its outstanding amount ({1:.2f}).").format(
							sale_name,
							outstanding,
						)
					)

		self.allocated_amount = allocated
		self.unallocated_amount = max(flt(self.amount) - allocated, 0)

	def on_submit(self):
		if self.status == "Draft":
			self.db_set("status", "Posted", update_modified=False)
