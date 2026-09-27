"""In-memory Federal V1 fixtures; never a site or HTTP connection."""
from copy import deepcopy
from contextlib import ExitStack
import unittest
from unittest.mock import patch, Mock
import frappe
from fbr_v1.services.fbr_v1_payload_builder import digest

class Row(frappe._dict):
    def set(self, key, value):
        self[key] = value
    @property
    def meta(self):
        return Mock(has_field=lambda key: True)
    def as_dict(self):
        return dict(self)
    def check_permission(self, *args):
        pass
    def reload(self):
        return self
    def update(self, *args, **kwargs):
        return dict.update(self, *args, **kwargs)


def fixture(doctype="Sales Invoice", credit=False, third=False):
    sign = -1 if credit else 1
    identity = dict(protocol="Federal POS/IMS V1", snapshot_version=1, source_doctype=doctype,
                    source_name="INV-1", company="Test Company")
    line = dict(**identity, line=dict(item_row="ROW-1", item_code="SKU", item_name="Example",
        qty=sign, net_amount=100 * sign, amount=100 * sign, discount_amount=0, distributed_discount_amount=0,
        fbr_mapping=dict(name="MAP-1", needs_review=0, hs_code="12345678",
            tax_basis="Notified Retail Price" if third else "Transaction Value"),
        components=dict(sales_tax=18 * sign, further_tax=0, extra_tax=0, fed_payable=0, sales_tax_withheld_at_source=0),
        component_rows=[dict(component="Sales Tax Applicable", tax_rate=18, tax_amount=18 * sign,
            charge_type="On Notified Retail Price" if third else "On Net Total")]))
    header = dict(**identity, posting_date="2026-09-01", posting_time="12:34:56", currency="PKR",
        is_return=credit, return_against="ORIGINAL" if credit else "", ref_usin="ORIGINAL" if credit else "", usin="INV-1",
        net_total=100 * sign, total_taxes_and_charges=18 * sign, grand_total=118 * sign,
        identity={"seller": {"ntn_cnic": "123", "business_name": "Shop", "address": "Address"}, "buyer": {"business_name": "Customer"}},
        pos_device=dict(name="DEVICE-1", pos_id="123", company="Test Company", pos_profile=None,
            environment="Sandbox", transport_topology="Cloud API", software_registration_number=None,
            outlet_address=None, onboarding_reference=None), payment={"payment_mode": 1},
        reconciliation={"passed": True}, line_count=1)
    return rehash(dict(header=header, lines={"ROW-1": line}))


def rehash(snapshot):
    snapshot["header"]["line_hashes"] = [{"item_row": k, "sha256": digest(v)} for k,v in snapshot["lines"].items()]
    snapshot["snapshot_hash"] = digest(snapshot["header"])
    return snapshot


class NoNetworkTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        def throw(message, exc=frappe.ValidationError, **kwargs):
            raise exc(message)
        self.stack.enter_context(patch.object(frappe, "throw", side_effect=throw))
        self.stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("Network forbidden in tests")))
        self.stack.enter_context(patch("requests.sessions.Session.request", side_effect=AssertionError("HTTP forbidden in tests")))
        self.stack.enter_context(patch.object(frappe, "get_system_settings", return_value="Asia/Karachi"))
        self.stack.enter_context(patch.object(frappe.local, "flags", Row(in_test=False), create=True))
        self.db = self.stack.enter_context(patch.object(frappe, "db", Mock(), create=True))
        self.stack.enter_context(patch.object(frappe, "session", Row(user="test@example.invalid"), create=True))
