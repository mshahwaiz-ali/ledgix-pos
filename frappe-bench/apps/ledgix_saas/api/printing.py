"""Current native V1 prints and strict persisted historical DI views."""
import frappe
from frappe.utils import cint, flt
from ledgix_saas.services import historical_fbr_evidence

SUPPORTED_PRINT_DOCTYPES = {"Sales Invoice", "POS Invoice"}

def get_fbr_qr_data_uri(fbr_invoice_number):
    # A bare historical number is insufficient fiscal evidence.
    return ""

def _identity_for_print(doc):
    if cint(doc.get("custom_ledgix_fbr_v2_snapshot_version")) != historical_fbr_evidence.SNAPSHOT_VERSION:
        frappe.throw("Historical fiscal evidence unavailable.")
    persisted = historical_fbr_evidence.read_persisted_v2_snapshot(doc.doctype, doc.name)
    identity = dict(persisted["header"].get("identity") or {})
    if not all((identity.get("seller") or {}).get(f) for f in ("business_name", "ntn_cnic", "province", "address")) or not (identity.get("buyer") or {}).get("business_name"):
        frappe.throw("Historical fiscal evidence incomplete.")
    return identity, "persisted_v2", persisted["snapshot_hash"]

def get_native_invoice_print_context(reference_doctype, reference_name):
    if reference_doctype not in SUPPORTED_PRINT_DOCTYPES:
        frappe.throw("Native print source must be Sales Invoice or POS Invoice.")
    doc = frappe.get_doc(reference_doctype, reference_name)
    doc.check_permission("read")
    historical = cint(doc.get("custom_ledgix_fbr_v2_snapshot_version")) or (
        doc.get("custom_ledgix_fbr_snapshot_protocol") != "Federal POS/IMS V1" and
        (doc.get("custom_ledgix_fbr_invoice_number") or doc.get("custom_ledgix_fbr_required")))
    if not historical:
        from fbr_v1.api.printing import get_native_invoice_print_context as current_print
        return current_print(reference_doctype, reference_name)
    identity, identity_source, identity_snapshot_hash = _identity_for_print(doc)
    seller, buyer = identity["seller"], identity["buyer"]
    return dict(doctype=doc.doctype, name=doc.name, title="HISTORICAL TRANSACTION",
        identity_source=identity_source, identity_snapshot_hash=identity_snapshot_hash,
        seller=dict(name=seller["business_name"], ntn=seller["ntn_cnic"], strn=seller.get("strn") or "",
                    province=seller["province"], address=seller["address"], digital_invoicing_logo=""),
        buyer=dict(name=buyer["business_name"], ntn_cnic=buyer.get("ntn_cnic") or "", address=buyer.get("address") or ""),
        items=[dict(item_code=r.get("item_code"), item_name=r.get("item_name"), qty=r.get("qty"), amount=r.get("amount")) for r in doc.get("items") or []],
        grand_total=doc.get("grand_total"), fbr_invoice_number=doc.get("custom_ledgix_fbr_invoice_number") or "",
        fbr_qr_data_uri="", authority="Verified persisted historical DI evidence; no current fiscal execution")
