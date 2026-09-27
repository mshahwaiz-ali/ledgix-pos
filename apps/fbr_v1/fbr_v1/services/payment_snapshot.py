"""Capture native payment evidence without inferring Cash."""
from decimal import Decimal
import frappe

FIELD = "custom_ledgix_fbr_v1_payment_mode"
ALLOWED = {1, 2, 3, 4, 6}


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
    methods = {row["mode_of_payment"] for row in rows}
    return {"payment_mode": 5 if len(methods) > 1 else rows[0]["fbr_code"], "evidence": rows}
