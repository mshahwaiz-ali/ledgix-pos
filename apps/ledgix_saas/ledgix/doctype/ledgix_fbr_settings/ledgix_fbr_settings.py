# Copyright (c) 2026, Ali and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document


RETIRED_MESSAGE = (
    "Ledgix FBR Settings is retired. "
    "Use the company-scoped Ledgix FBR Integration Profile in Tax & FBR Center."
)


class LedgixFBRSettings(Document):
    def validate(self):
        # The old singleton remains installed temporarily for historical
        # compatibility, but it is no longer a writable configuration authority.
        frappe.throw(RETIRED_MESSAGE)
