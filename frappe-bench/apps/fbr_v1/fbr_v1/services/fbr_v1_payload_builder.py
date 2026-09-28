"""Serialize hash-verified ERPNext evidence. No tax calculation occurs here."""
import hashlib
import json
from decimal import Decimal
from fbr_v1.protocol.tax_identity import normalize_tax_id
from fbr_v1.protocol.models import Invoice, InvoiceItem, ProtocolValidationError

PROTOCOL = "Federal POS/IMS V1"
TOLERANCE = Decimal("0.011")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, default=str).encode()).hexdigest()


def number(value):
    result = Decimal(str(value or 0))
    if not result.is_finite():
        raise ProtocolValidationError("Non-finite monetary evidence.")
    return result


def equal(actual, expected, label):
    if abs(number(actual) - number(expected)) > TOLERANCE:
        raise ProtocolValidationError("ERPNext reconciliation failed: " + label)


def verify_snapshot(snapshot):
    header, lines = snapshot["header"], snapshot["lines"]
    if header.get("protocol") != PROTOCOL or header.get("snapshot_version") != 1:
        raise ProtocolValidationError("Only immutable Federal V1 snapshots are accepted.")
    if digest(header) != snapshot.get("snapshot_hash"):
        raise ProtocolValidationError("Snapshot header hash mismatch.")
    manifest = [{"item_row": key, "sha256": digest(line)} for key, line in lines.items()]
    if manifest != header.get("line_hashes") or len(lines) != header.get("line_count"):
        raise ProtocolValidationError("Snapshot line manifest mismatch.")
    for line in lines.values():
        for key in ("protocol", "snapshot_version", "source_doctype", "source_name", "company"):
            if line.get(key) != header.get(key):
                raise ProtocolValidationError("Snapshot line identity mismatch.")
    return header, lines


def build_invoice(snapshot):
    h, lines = verify_snapshot(snapshot)
    if h.get("note_type") == "Debit":
        raise ProtocolValidationError("Unresolved Federal item-level Debit contract; no payload emitted.")
    credit = bool(h.get("is_return"))
    if h.get("note_type") == "Credit" and not credit:
        raise ProtocolValidationError("Credit requires a native ERPNext return.")
    ref = h.get("ref_usin") or ""
    if credit and not ref:
        raise ProtocolValidationError("Credit requires the original invoice USIN.")
    if h.get("currency") != "PKR":
        raise ProtocolValidationError("Foreign-currency V1 serialization is unresolved.")
    if not h.get("reconciliation", {}).get("passed"):
        raise ProtocolValidationError("Native tax capture did not reconcile.")
    items = []
    for payload in lines.values():
        line = payload["line"]
        mapping = line.get("fbr_mapping") or {}
        if not mapping.get("name") or mapping.get("needs_review"):
            raise ProtocolValidationError("An approved Item Mapping is required.")
        components = line["components"]
        for unsupported in ("extra_tax", "fed_payable", "sales_tax_withheld_at_source"):
            if number(components.get(unsupported)):
                raise ProtocolValidationError("Unresolved V1 wire field for " + unsupported)
        for key in ("qty", "net_amount"):
            value = number(line.get(key))
            if (credit and value > 0) or (not credit and value < 0):
                raise ProtocolValidationError("Mixed sale/credit signs are unsupported.")
        for key in ("sales_tax", "further_tax"):
            value = number(components.get(key))
            if (credit and value > 0) or (not credit and value < 0):
                raise ProtocolValidationError("Tax evidence sign differs from invoice type.")
        tax = abs(number(components.get("sales_tax")))
        further = abs(number(components.get("further_tax")))
        rates = {number(row.get("tax_rate")) for row in line.get("component_rows", [])
                 if row.get("component") == "Sales Tax Applicable"}
        if len(rates) > 1 or (tax and not rates):
            raise ProtocolValidationError("Sales tax rate evidence is missing or ambiguous.")
        # Addition/distribution is native evidence, not a second tax engine.
        discount = abs(number(line.get("distributed_discount_amount"))) + abs(
            number(line.get("discount_amount")) * number(line.get("qty")))
        if discount and any(r.get("included_in_print_rate") for r in line.get("component_rows", [])):
            raise ProtocolValidationError("Inclusive-tax discount wire reconciliation is unresolved.")
        net = abs(number(line.get("net_amount")))
        third = mapping.get("tax_basis") == "Notified Retail Price"
        native_retail_rows = [r for r in line.get("component_rows", [])
                              if r.get("component") == "Sales Tax Applicable"
                              and r.get("charge_type") == "On Notified Retail Price"]
        if third != bool(native_retail_rows):
            raise ProtocolValidationError("Third Schedule mapping and native ERPNext taxable-base evidence differ.")
        items.append(InvoiceItem(
            item_code=line["item_code"], item_name=line["item_name"],
            quantity=float(abs(number(line["qty"]))), pct_code=mapping.get("hs_code") or "",
            tax_rate=float(next(iter(rates), Decimal(0))), sale_value=float(net + discount),
            discount=float(discount), tax_charged=float(tax), further_tax=float(further),
            total_amount=float(net + tax + further),
            invoice_type=(12 if third else 3) if credit else (11 if third else 1), ref_usin=ref or None))
    net = sum(number(i.sale_value) - number(i.discount) for i in items)
    tax = sum(number(i.tax_charged) for i in items)
    further = sum(number(i.further_tax) for i in items)
    service_fee = abs(number(h.get("pos_service_fee") or 0))
    if credit and service_fee:
        raise ProtocolValidationError("Credit notes must not add a new POS Service Fee.")
    if service_fee not in {Decimal("0"), Decimal("1.00")}:
        raise ProtocolValidationError("POS Service Fee must be zero (legacy/credit) or Re.1.")
    equal(net, abs(number(h["net_total"])), "net total")
    equal(tax + further + service_fee, abs(number(h["total_taxes_and_charges"])), "tax/charge total")
    equal(sum(number(i.total_amount) for i in items) + service_fee, abs(number(h["grand_total"])), "grand total")
    if (credit and number(h["grand_total"]) > 0) or (not credit and number(h["grand_total"]) < 0):
        raise ProtocolValidationError("Header amount sign differs from invoice type.")
    buyer = h.get("identity", {}).get("buyer", {})
    tax_id, kind = normalize_tax_id(buyer.get("tax_id_raw", buyer.get("ntn_cnic")))
    return Invoice(
        pos_id=int(h["pos_device"]["pos_id"]), usin=h["usin"], ref_usin=ref or None,
        date_time=f"{h['posting_date']} {h['posting_time']}",
        buyer_name=buyer.get("business_name") or "", buyer_ntn=tax_id if kind == "NTN" else "",
        buyer_cnic=tax_id if kind == "CNIC" else "", buyer_phone_number=buyer.get("phone") or "",
        total_bill_amount=float(abs(number(h["grand_total"]))),
        total_quantity=sum(i.quantity for i in items), total_sale_value=sum(i.sale_value for i in items),
        total_tax_charged=float(tax), further_tax=float(further), discount=sum(i.discount for i in items),
        payment_mode=int(h["payment"]["payment_mode"]), invoice_type=3 if credit else 1, items=items)
