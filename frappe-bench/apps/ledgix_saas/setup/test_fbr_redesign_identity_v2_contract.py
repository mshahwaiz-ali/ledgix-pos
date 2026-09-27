from __future__ import annotations

import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestFBRRedesignIdentityV2Contract(unittest.TestCase):
    def setUp(self):
        self.source = (
            APP_ROOT / "services" / "erpnext_fbr_identity.py"
        ).read_text(encoding="utf-8")

    def test_seller_identity_uses_erpnext_company_and_address(self):
        for marker in (
            'company.get("tax_id")',
            'company.get("company_name") or company.name',
            'get_default_address("Company", doc.get("company"))',
            'seller_address["province"]',
            'seller_address["address"]',
            '"tax_id_source": "Company.tax_id"',
            '"province_source": "Address.state"',
        ):
            self.assertIn(marker, self.source)

        for forbidden in (
            "seller_ntn_cnic",
            "seller_business_name",
            "seller_province",
            "seller_address",
            "Ledgix FBR Settings",
        ):
            self.assertNotIn(f'get("{forbidden}")', self.source)

    def test_buyer_prefers_native_customer_tax_id(self):
        self.assertIn('native_tax_id = _text(customer.get("tax_id"))', self.source)
        self.assertIn('legacy_tax_id = _text(customer.get("custom_ledgix_buyer_ntn_cnic"))', self.source)
        self.assertIn('"ntn_cnic": native_tax_id or legacy_tax_id', self.source)
        self.assertIn('"Customer.tax_id"', self.source)
        self.assertIn("transition fallback", self.source)

    def test_buyer_address_uses_transaction_or_primary_erpnext_address(self):
        for marker in (
            'doc.get("customer_address")',
            'customer.get("customer_primary_address")',
            'get_default_address("Customer", customer.name)',
            '"province_source": "Address.state"',
            '"address_source": "Address"',
        ):
            self.assertIn(marker, self.source)

        self.assertNotIn(
            '"address": _text(customer.get("custom_ledgix_buyer_fbr_address"))',
            self.source,
        )
        self.assertNotIn(
            '"province": _text(customer.get("custom_ledgix_buyer_province"))',
            self.source,
        )

    def test_legacy_buyer_duplicates_are_conflict_evidence_not_authority(self):
        self.assertIn(
            "ERPNext Customer Tax ID conflicts with legacy Ledgix Buyer NTN/CNIC",
            self.source,
        )
        self.assertIn(
            "Legacy Buyer Province differs from ERPNext Address State/Province",
            self.source,
        )
        self.assertIn(
            "Legacy Buyer FBR Address differs from ERPNext Address",
            self.source,
        )

    def test_registration_type_remains_fbr_specific(self):
        self.assertIn(
            'customer.get("custom_ledgix_buyer_registration_type")',
            self.source,
        )
        self.assertIn('BUYER_REGISTRATION_TYPES = {"Registered", "Unregistered"}', self.source)
        self.assertIn(
            "Registered FBR buyer requires ERPNext Customer Tax ID.",
            self.source,
        )

    def test_resolver_is_read_only_and_non_networked(self):
        for forbidden in (
            "frappe.db.set_value(",
            ".insert(",
            ".save(",
            ".submit(",
            "requests.",
            "post_invoice(",
            "validate_invoice(",
        ):
            self.assertNotIn(forbidden, self.source)

        self.assertIn('"database_write": False', self.source)
        self.assertIn('"fbr_network_call": False', self.source)
        self.assertIn('"authority": "ERPNext"', self.source)


if __name__ == "__main__":
    unittest.main()
