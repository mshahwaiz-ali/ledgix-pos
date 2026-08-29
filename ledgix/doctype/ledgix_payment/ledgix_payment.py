import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class LedgixPayment(Document):
	def validate(self):
		self._validate_amounts()
		self._validate_allocations()

	def _validate_amounts(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Payment amount must be greater than zero."))
		if flt(self.amount_tendered) and flt(self.amount_tendered) < flt(self.amount):
			frappe.throw(_("Amount tendered cannot be less than the payment amount."))
		self.change_amount = max(flt(self.amount_tendered) - flt(self.amount), 0)

	def _validate_allocations(self):
		allocated = sum(flt(row.allocated_amount) for row in self.allocations)
		if allocated - flt(self.amount) > 0.005:
			frappe.throw(_("Payment allocations cannot exceed the payment amount."))
		self.allocated_amount = allocated
		self.unallocated_amount = max(flt(self.amount) - allocated, 0)

	def on_submit(self):
		if self.status == "Draft":
			self.db_set("status", "Posted", update_modified=False)
