"""Documented Federal FBR Tier-1 POS / IMS V1 constants.

These are V1 POS/IMS endpoints, not Digital Invoicing V1.2 endpoints.
"""

LOCAL_HEALTH_URL = "http://localhost:8524/api/IMSFiscal/Get"
LOCAL_POST_URL = "http://localhost:8524/api/IMSFiscal/GetInvoiceNumberByModel"

CLOUD_SANDBOX_URL = "https://esp.fbr.gov.pk:8244/FBR/v1/api/Live/PostData"
CLOUD_PRODUCTION_URL = "https://gw.fbr.gov.pk/imsp/v1/api/Live/PostData"

SUCCESS_CODE = "100"

PAYMENT_MODES = {
    1: "Cash",
    2: "Card",
    3: "Gift Voucher",
    4: "Loyalty Card",
    5: "Mixed",
    6: "Cheque",
}

HEADER_INVOICE_TYPES = {
    1: "New",
    2: "Debit",
    3: "Credit",
}

# The archived Federal item table documents these item-level types.
# Header Debit (2) is documented, but item-level Debit is not listed there.
ITEM_INVOICE_TYPES = {
    1: "New",
    3: "Credit",
    11: "3rd Schedule New",
    12: "3rd Schedule Credit",
}
