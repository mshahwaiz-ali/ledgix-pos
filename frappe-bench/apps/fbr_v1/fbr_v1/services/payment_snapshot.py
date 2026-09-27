"""Capture native payment evidence without inferring Cash."""
from decimal import Decimal, InvalidOperation
import frappe

FIELD = "custom_ledgix_fbr_v1_payment_mode"
ALLOWED = {1, 2, 3, 4, 6}
MONEY_TOLERANCE = Decimal("0.005")


def _transient_checkout_rows(doc):
    evidence = getattr(
        getattr(doc, "flags", None),
        "ledgix_fbr_v1_payment_evidence",
        None,
    )
    if evidence is None:
        return None
    if doc.doctype != "Sales Invoice" or evidence.get("source") != "Ledgix B2B Checkout":
        frappe.throw("Unsupported transient Federal V1 payment evidence source.")
    if doc.get("is_return"):
        frappe.throw(
            "Federal V1 B2B Credit Note payment semantics are unresolved; "
            "the credit note remains blocked."
        )
    if not evidence.get("require_full_coverage"):
        frappe.throw("Ledgix B2B fiscal payment evidence must require full coverage.")

    rows = []
    for supplied in evidence.get("rows") or []:
        mode = str(supplied.get("mode_of_payment") or "").strip()
        try:
            amount = Decimal(str(supplied.get("amount") or 0))
        except (InvalidOperation, ValueError):
            frappe.throw("Ledgix B2B fiscal tenders require positive finite amounts.")
        if not amount.is_finite() or amount <= 0:
            frappe.throw("Ledgix B2B fiscal tenders require positive finite amounts.")
        if not mode:
            frappe.throw("Ledgix B2B fiscal tenders require a Mode of Payment.")
        rows.append({
            "mode_of_payment": mode,
            "amount": str(amount),
            "reference_no": str(supplied.get("reference_no") or "").strip(),
            "source": evidence["source"],
        })

    if not rows:
        frappe.throw(
            "Federal V1 has no proven Credit/Pay-Later PaymentMode; "
            "a fully tendered Ledgix B2B checkout is required."
        )

    invoice_total = abs(Decimal(str(doc.get("grand_total") or 0)))
    tender_total = sum((Decimal(row["amount"]) for row in rows), Decimal("0"))
    if abs(tender_total - invoice_total) > MONEY_TOLERANCE:
        frappe.throw(
            "Federal V1 has no proven Credit/Pay-Later PaymentMode; "
            "Ledgix B2B tenders must fully cover the invoice total."
        )
    return rows


def capture_payment(doc, lookup=None):
    lookup = lookup or (lambda mode: frappe.db.get_value("Mode of Payment", mode, FIELD))
    rows = []
    for row in doc.get("payments") or []:
        amount = Decimal(str(row.get("amount") or 0))
        if not amount.is_finite():
            frappe.throw("Payment amount must be finite.")
        if amount:
            rows.append({"mode_of_payment": row.get("mode_of_payment"), "amount": str(amount),
                         "reference_no": row.get("reference_no") or ""})
    if not rows:
        transient_rows = _transient_checkout_rows(doc)
        if transient_rows is not None:
            rows = transient_rows
    if not rows:
        mode = doc.get("custom_ledgix_fbr_mode_of_payment")
        if doc.doctype == "POS Invoice" or not mode:
            frappe.throw("Native payment evidence or an explicit fiscal Mode of Payment is required.")
        rows = [{"mode_of_payment": mode, "amount": None, "source": "explicit fiscal input"}]
    for row in rows:
        configured = str(lookup(row["mode_of_payment"]) or "")
        try:
            code = int(configured.split(" - ", 1)[0])
        except ValueError:
            code = 0
        if code not in ALLOWED:
            frappe.throw(f"Missing Federal V1 payment mapping for {row['mode_of_payment']}.")
        row["fbr_code"] = code
    mapped_codes = {row["fbr_code"] for row in rows}
    return {
        "payment_mode": 5 if len(mapped_codes) > 1 else rows[0]["fbr_code"],
        "evidence": rows,
    }
