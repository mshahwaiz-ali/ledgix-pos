from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate, today

from ledgix_saas.services import erpnext_tax_authority
from ledgix_saas.setup import erpnext_phase6_extensions

MONEY_TOLERANCE = 0.005


def _company(company: str | None = None) -> str:
    value = (
        company
        or frappe.defaults.get_user_default("Company")
        or frappe.db.get_single_value("Global Defaults", "default_company")
    )
    if not value or not frappe.db.exists("Company", value):
        frappe.throw(_("A valid ERPNext Company is required."))
    return value


def _lock_company(company: str) -> None:
    """Serialize client-id checks inside the current database transaction."""

    frappe.db.sql("SELECT name FROM `tabCompany` WHERE name=%s FOR UPDATE", (company,))


def _resolve_customer(customer: str) -> str:
    customer = str(customer or "").strip()
    if not customer:
        frappe.throw(_("Customer is required."))
    if frappe.db.exists("Customer", customer):
        return customer
    mapped = frappe.db.get_value(
        "Customer", {"custom_ledgix_legacy_customer": customer}, "name"
    )
    if mapped:
        return mapped
    frappe.throw(_("ERPNext Customer not found for {0}.").format(customer))


def _resolve_item(item: str) -> str:
    item = str(item or "").strip()
    if not item:
        frappe.throw(_("Item is required."))
    if frappe.db.exists("Item", item):
        return item
    mapped = frappe.db.get_value("Item", {"custom_ledgix_legacy_item": item}, "name")
    if mapped:
        return mapped
    frappe.throw(_("ERPNext Item not found for {0}.").format(item))


def _resolve_price_list(price_list: str | None) -> str:
    price_list = str(price_list or "").strip()
    if price_list and frappe.db.exists("Price List", price_list):
        return price_list
    if price_list:
        mapped = frappe.db.get_value(
            "Price List", {"custom_ledgix_legacy_price_list": price_list}, "name"
        )
        if mapped:
            return mapped
    default = frappe.db.get_single_value("Selling Settings", "selling_price_list")
    if default and frappe.db.exists("Price List", default):
        return default
    if frappe.db.exists("Price List", "Standard Selling"):
        return "Standard Selling"
    frappe.throw(_("A valid ERPNext selling Price List is required."))


def _resolve_mode_of_payment(mode: str) -> str:
    mode = str(mode or "").strip()
    if not mode:
        frappe.throw(_("Mode of Payment is required."))
    if frappe.db.exists("Mode of Payment", mode):
        return mode
    mapped = frappe.db.get_value(
        "Mode of Payment", {"custom_ledgix_legacy_payment_method": mode}, "name"
    )
    if mapped:
        return mapped
    frappe.throw(_("ERPNext Mode of Payment not found for {0}.").format(mode))


def _mode_account(mode: str, company: str) -> str:
    account = frappe.db.get_value(
        "Mode of Payment Account",
        {"parent": mode, "company": company},
        "default_account",
    )
    if not account:
        frappe.throw(
            _("Mode of Payment {0} has no default account for Company {1}.").format(
                mode, company
            )
        )
    return account


def _account_currency(account: str) -> str:
    return frappe.db.get_value("Account", account, "account_currency") or "PKR"


def _currency(company: str) -> str:
    return frappe.db.get_value("Company", company, "default_currency") or "PKR"


def _price_list_currency(price_list: str, company: str) -> str:
    return frappe.db.get_value("Price List", price_list, "currency") or _currency(company)


def _native_item_rate(
    *,
    item_code: str,
    customer: str,
    company: str,
    price_list: str,
    qty: float,
    posting_date: str,
) -> dict:
    from erpnext.stock.get_item_details import get_item_details

    currency = _currency(company)
    price_list_currency = _price_list_currency(price_list, company)
    args = frappe._dict(
        {
            "doctype": "Sales Invoice",
            "company": company,
            "customer": customer,
            "item_code": item_code,
            "qty": qty,
            "transaction_date": posting_date,
            "posting_date": posting_date,
            "price_list": price_list,
            "selling_price_list": price_list,
            "currency": currency,
            "conversion_rate": 1,
            "price_list_currency": price_list_currency,
            "plc_conversion_rate": 1,
            "order_type": "Sales",
            "ignore_pricing_rule": 0,
            "name": None,
        }
    )
    details = frappe._dict(get_item_details(args) or {})
    rate = flt(details.get("rate") or details.get("price_list_rate"))
    if rate <= 0:
        rows = frappe.get_all(
            "Item Price",
            filters={
                "item_code": item_code,
                "price_list": price_list,
                "selling": 1,
            },
            fields=["name", "price_list_rate"],
            order_by="valid_from desc, creation desc",
            limit_page_length=1,
        )
        price_row = rows[0] if rows else None
        rate = flt((price_row or {}).get("price_list_rate"))
        if price_row:
            details.item_price_reference = price_row.name
    if rate <= 0:
        frappe.throw(
            _("No effective ERPNext selling price was found for item {0} in {1}.").format(
                item_code, price_list
            )
        )
    details.rate = rate
    details.price_list_rate = flt(details.get("price_list_rate") or rate)
    return details


def _normalize_items(
    items,
    *,
    customer: str,
    company: str,
    price_list: str,
    posting_date: str,
    allow_rate_override: bool = False,
) -> list[dict]:
    if isinstance(items, str):
        items = frappe.parse_json(items)
    items = items or []
    if not items:
        frappe.throw(_("At least one invoice item is required."))

    normalized = []
    for raw in items:
        item_code = _resolve_item(raw.get("item_code") or raw.get("item"))
        qty = flt(raw.get("qty") or raw.get("quantity"))
        if qty <= 0:
            frappe.throw(_("Quantity must be greater than zero for {0}.").format(item_code))
        details = _native_item_rate(
            item_code=item_code,
            customer=customer,
            company=company,
            price_list=price_list,
            qty=qty,
            posting_date=posting_date,
        )
        rate = flt(details.rate)
        requested = raw.get("override_rate")
        if requested in (None, "") and raw.get("rate") not in (None, ""):
            requested = raw.get("rate")
        if requested not in (None, ""):
            if not allow_rate_override:
                frappe.throw(_("Explicit rate override is not allowed for this request."))
            requested = flt(requested)
            if requested < 0:
                frappe.throw(_("Rate cannot be negative."))
            rate = requested
        normalized.append(
            {
                "item_code": item_code,
                "qty": qty,
                "uom": raw.get("uom")
                or details.get("uom")
                or frappe.db.get_value("Item", item_code, "stock_uom"),
                "rate": rate,
                "price_list_rate": flt(details.price_list_rate),
                "discount_percentage": flt(details.get("discount_percentage")),
                "warehouse": raw.get("warehouse") or None,
            }
        )
    return normalized


def _apply_checkout_discount(
    items: list[dict], discount_type: str, discount_value: float
) -> dict:
    discount_value = max(flt(discount_value), 0)
    subtotal = sum(flt(row["qty"]) * flt(row["rate"]) for row in items)
    if not discount_value or subtotal <= 0:
        return {"type": "Amount", "value": 0.0, "amount": 0.0, "ratio": 0.0}

    if discount_type == "Percent":
        value = min(discount_value, 100)
        amount = subtotal * value / 100.0
    else:
        discount_type = "Amount"
        value = min(discount_value, subtotal)
        amount = value
    ratio = amount / subtotal if subtotal else 0.0
    for row in items:
        base_rate = flt(row["rate"])
        row["rate"] = flt(base_rate * (1.0 - ratio), 6)
        row["discount_percentage"] = flt(ratio * 100.0, 6)
    return {
        "type": discount_type,
        "value": flt(value, 2),
        "amount": flt(amount, 2),
        "ratio": ratio,
    }


def _existing_invoice_by_client_id(client_sale_id: str, company: str):
    if not client_sale_id:
        return None
    name = frappe.db.get_value(
        "Sales Invoice",
        {
            "company": company,
            "custom_ledgix_client_sale_id": client_sale_id,
            "docstatus": ["!=", 2],
        },
        "name",
    )
    return frappe.get_doc("Sales Invoice", name) if name else None


def build_sales_invoice(
    *,
    customer: str,
    items,
    company: str | None = None,
    selling_price_list: str | None = None,
    sale_channel: str = "B2B",
    client_sale_id: str | None = None,
    posting_date: str | None = None,
    due_date: str | None = None,
    discount_type: str = "Amount",
    discount_value: float = 0,
    allow_rate_override: bool = False,
    update_stock: bool = False,
    checkout_source: str = "Ledgix Native Selling",
    exchange_reference: str | None = None,
):
    """Build an unsaved ERPNext Sales Invoice using ERPNext masters/pricing."""

    erpnext_phase6_extensions.sync_all()
    company = _company(company)
    customer = _resolve_customer(customer)
    price_list = _resolve_price_list(selling_price_list)
    posting_date = str(posting_date or nowdate())
    sale_channel = sale_channel if sale_channel in {"Retail", "B2B"} else "B2B"

    normalized = _normalize_items(
        items,
        customer=customer,
        company=company,
        price_list=price_list,
        posting_date=posting_date,
        allow_rate_override=allow_rate_override,
    )
    discount = _apply_checkout_discount(normalized, discount_type, discount_value)

    invoice = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "company": company,
            "customer": customer,
            "posting_date": posting_date,
            "currency": _currency(company),
            "selling_price_list": price_list,
            "update_stock": 1 if update_stock else 0,
            "custom_ledgix_sale_channel": sale_channel,
            "custom_ledgix_client_sale_id": (client_sale_id or "").strip(),
            "custom_ledgix_exchange_reference": (exchange_reference or "").strip(),
            "custom_ledgix_checkout_source": checkout_source,
            "items": normalized,
        }
    )
    invoice.set_missing_values()
    if due_date:
        invoice.due_date = getdate(due_date)
    erpnext_tax_authority.apply_sales_tax_authority(invoice)
    invoice._ledgix_discount = discount
    return invoice


def preview_sales_invoice(**kwargs) -> dict:
    invoice = build_sales_invoice(**kwargs)
    return invoice_summary(invoice, include_items=True)


def create_sales_invoice(*, submit: bool = True, **kwargs):
    company = _company(kwargs.get("company"))
    client_sale_id = str(kwargs.get("client_sale_id") or "").strip()
    _lock_company(company)
    existing = _existing_invoice_by_client_id(client_sale_id, company)
    if existing:
        existing.flags.ledgix_duplicate_client_sale = True
        return existing

    kwargs["company"] = company
    invoice = build_sales_invoice(**kwargs)
    invoice.insert(ignore_permissions=True)
    if submit:
        invoice.submit()
        invoice.reload()
    invoice.flags.ledgix_duplicate_client_sale = False
    return invoice


def _normalize_allocations(customer: str, company: str, allocations) -> list[dict]:
    if isinstance(allocations, str):
        allocations = frappe.parse_json(allocations)
    allocations = allocations or []
    normalized = []
    for row in allocations:
        reference_name = str(
            row.get("reference_name") or row.get("invoice") or ""
        ).strip()
        if not reference_name:
            continue
        invoice = frappe.db.get_value(
            "Sales Invoice",
            reference_name,
            [
                "name",
                "customer",
                "company",
                "docstatus",
                "grand_total",
                "outstanding_amount",
            ],
            as_dict=True,
        )
        if not invoice or cint(invoice.docstatus) != 1:
            frappe.throw(_("Submitted Sales Invoice not found: {0}").format(reference_name))
        if invoice.customer != customer or invoice.company != company:
            frappe.throw(_("Payment allocations cannot cross Customer or Company boundaries."))
        if flt(invoice.outstanding_amount) <= MONEY_TOLERANCE:
            frappe.throw(
                _("Sales Invoice {0} has no positive receivable outstanding.").format(
                    reference_name
                )
            )
        allocated = flt(row.get("allocated_amount"))
        if allocated <= 0:
            continue
        if allocated - flt(invoice.outstanding_amount) > MONEY_TOLERANCE:
            frappe.throw(
                _("Allocated amount exceeds outstanding amount for {0}.").format(
                    reference_name
                )
            )
        normalized.append(
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": reference_name,
                "total_amount": flt(invoice.grand_total),
                "outstanding_amount": flt(invoice.outstanding_amount),
                "allocated_amount": allocated,
            }
        )
    return normalized


def post_customer_payment(
    *,
    customer: str,
    mode_of_payment: str,
    amount: float,
    allocations,
    company: str | None = None,
    client_payment_id: str | None = None,
    reference_number: str | None = None,
    payment_source: str = "Ledgix Native Selling",
):
    """Submit a native Payment Entry against one or more Sales Invoices."""

    erpnext_phase6_extensions.sync_all()
    company = _company(company)
    customer = _resolve_customer(customer)
    mode_of_payment = _resolve_mode_of_payment(mode_of_payment)
    amount = flt(amount)
    if amount <= 0:
        frappe.throw(_("Payment amount must be greater than zero."))

    _lock_company(company)
    client_payment_id = str(client_payment_id or "").strip()
    if client_payment_id:
        existing_name = frappe.db.get_value(
            "Payment Entry",
            {
                "company": company,
                "custom_ledgix_client_payment_id": client_payment_id,
                "docstatus": ["!=", 2],
            },
            "name",
        )
        if existing_name:
            existing = frappe.get_doc("Payment Entry", existing_name)
            existing.flags.ledgix_duplicate_client_payment = True
            return existing

    references = _normalize_allocations(customer, company, allocations)
    if not references:
        frappe.throw(
            _(
                "At least one Sales Invoice allocation is required on the Ledgix cutover path. "
                "Use native ERPNext Payment Entry directly for an unapplied customer advance."
            )
        )
    allocated_total = flt(sum(flt(row["allocated_amount"]) for row in references), 2)
    if amount + MONEY_TOLERANCE < allocated_total:
        frappe.throw(_("Payment amount cannot be less than its allocated amount."))

    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    payment = get_payment_entry("Sales Invoice", references[0]["reference_name"])
    payment.company = company
    payment.posting_date = nowdate()
    payment.mode_of_payment = mode_of_payment
    payment.custom_remarks = 1
    payment.remarks = payment_source
    payment.custom_ledgix_client_payment_id = client_payment_id
    payment.custom_ledgix_payment_source = payment_source
    if reference_number:
        payment.reference_no = reference_number
        payment.reference_date = nowdate()
    payment.set("references", [])
    for row in references:
        payment.append("references", row)

    account = _mode_account(mode_of_payment, company)
    payment.paid_to = account
    payment.paid_to_account_currency = _account_currency(account)
    payment.paid_amount = amount
    payment.received_amount = amount
    payment.base_paid_amount = amount
    payment.base_received_amount = amount
    payment.insert(ignore_permissions=True)
    payment.submit()
    payment.reload()
    payment.flags.ledgix_duplicate_client_payment = False
    return payment


def refund_credit_note(
    *,
    credit_note: str,
    mode_of_payment: str,
    amount: float | None = None,
    client_payment_id: str | None = None,
    reference_number: str | None = None,
):
    """Refund a submitted native Sales Invoice Credit Note through Payment Entry."""

    note = frappe.get_doc("Sales Invoice", credit_note)
    if note.docstatus != 1 or not cint(note.is_return):
        frappe.throw(_("A submitted Sales Invoice Credit Note is required for refund."))
    mode = _resolve_mode_of_payment(mode_of_payment)
    company = note.company
    _lock_company(company)

    client_payment_id = str(client_payment_id or "").strip()
    if client_payment_id:
        existing_name = frappe.db.get_value(
            "Payment Entry",
            {
                "company": company,
                "custom_ledgix_client_payment_id": client_payment_id,
                "docstatus": ["!=", 2],
            },
            "name",
        )
        if existing_name:
            existing = frappe.get_doc("Payment Entry", existing_name)
            existing.flags.ledgix_duplicate_client_payment = True
            return existing

    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

    payment = get_payment_entry("Sales Invoice", note.name)
    if payment.payment_type != "Pay":
        frappe.throw(_("ERPNext did not resolve the Credit Note as a customer refund."))
    refund_amount = flt(amount or abs(flt(note.outstanding_amount)))
    if refund_amount <= 0:
        frappe.throw(_("Credit Note has no refundable outstanding amount."))
    if refund_amount - abs(flt(note.outstanding_amount)) > MONEY_TOLERANCE:
        frappe.throw(_("Refund amount exceeds the Credit Note outstanding amount."))

    payment.mode_of_payment = mode
    account = _mode_account(mode, company)
    payment.paid_from = account
    payment.paid_from_account_currency = _account_currency(account)
    payment.custom_remarks = 1
    payment.remarks = "Ledgix Native Customer Refund"
    payment.custom_ledgix_client_payment_id = client_payment_id
    payment.custom_ledgix_payment_source = "Ledgix Native Customer Refund"
    if reference_number:
        payment.reference_no = reference_number
        payment.reference_date = nowdate()
    payment.paid_amount = refund_amount
    payment.received_amount = refund_amount
    payment.base_paid_amount = refund_amount
    payment.base_received_amount = refund_amount
    if not payment.references:
        frappe.throw(_("ERPNext refund mapper returned no Credit Note reference."))
    payment.references[0].allocated_amount = -refund_amount
    payment.insert(ignore_permissions=True)
    payment.submit()
    payment.reload()
    payment.flags.ledgix_duplicate_client_payment = False
    return payment


def cancel_payment_entry(payment_entry: str, reason: str):
    reason = str(reason or "").strip()
    if not reason:
        frappe.throw(_("Cancellation reason is required."))
    payment = frappe.get_doc("Payment Entry", payment_entry)
    if payment.docstatus != 1:
        frappe.throw(_("Only a submitted Payment Entry can be cancelled."))
    payment.db_set("custom_ledgix_reversal_reason", reason, update_modified=False)
    payment.cancel()
    payment.reload()
    return payment


def _return_request_map(source, return_items) -> dict:
    if isinstance(return_items, str):
        return_items = frappe.parse_json(return_items)
    return_items = return_items or []
    if not return_items:
        frappe.throw(_("At least one return item is required."))

    source_by_name = {row.name: row for row in source.items}
    source_by_code = defaultdict(list)
    for row in source.items:
        source_by_code[row.item_code].append(row)

    requested = {}
    for raw in return_items:
        source_row_name = str(
            raw.get("sales_invoice_item") or raw.get("original_sale_item_row") or ""
        ).strip()
        item_code = str(raw.get("item_code") or raw.get("item") or "").strip()
        source_row = source_by_name.get(source_row_name) if source_row_name else None
        if source_row is None and item_code:
            resolved = _resolve_item(item_code)
            candidates = source_by_code.get(resolved) or []
            if len(candidates) != 1:
                frappe.throw(
                    _("Return item {0} is ambiguous; send the Sales Invoice Item row ID.").format(
                        resolved
                    )
                )
            source_row = candidates[0]
        if source_row is None:
            frappe.throw(_("Return row does not belong to the source Sales Invoice."))

        qty = flt(raw.get("return_qty") or raw.get("qty") or raw.get("quantity"))
        if qty <= 0 or qty - flt(source_row.qty) > MONEY_TOLERANCE:
            frappe.throw(_("Invalid return quantity for item {0}.").format(source_row.item_code))
        requested[source_row.name] = {
            "qty": qty,
            "item_code": source_row.item_code,
        }
    return requested


def create_sales_return(
    *,
    sales_invoice: str,
    return_items,
    reason: str,
    client_return_id: str | None = None,
    exchange_reference: str | None = None,
    checkout_source: str = "Ledgix Native Return",
):
    """Create a native ERPNext Credit Note/Return against exact invoice rows."""

    reason = str(reason or "").strip()
    if not reason:
        frappe.throw(_("Return reason is required."))
    source = frappe.get_doc("Sales Invoice", sales_invoice)
    if source.docstatus != 1 or cint(source.is_return):
        frappe.throw(_("A submitted non-return Sales Invoice is required."))

    company = source.company
    _lock_company(company)
    client_return_id = str(client_return_id or "").strip()
    if client_return_id:
        existing_name = frappe.db.get_value(
            "Sales Invoice",
            {
                "company": company,
                "custom_ledgix_client_return_id": client_return_id,
                "docstatus": ["!=", 2],
            },
            "name",
        )
        if existing_name:
            existing = frappe.get_doc("Sales Invoice", existing_name)
            existing.flags.ledgix_duplicate_client_return = True
            return existing

    requested = _return_request_map(source, return_items)
    from erpnext.controllers.sales_and_purchase_return import make_return_doc

    credit = make_return_doc("Sales Invoice", source.name)
    credit.payment_schedule = []
    credit.update_stock = 0
    credit.custom_ledgix_sale_channel = source.get("custom_ledgix_sale_channel") or "B2B"
    credit.custom_ledgix_client_return_id = client_return_id
    credit.custom_ledgix_exchange_reference = (exchange_reference or "").strip()
    credit.custom_ledgix_checkout_source = checkout_source
    credit.remarks = reason

    selected = []
    selected_source_names = set()
    for row in credit.items:
        source_row_name = row.get("sales_invoice_item") or ""
        request = requested.get(source_row_name)
        if request is None:
            candidates = [
                (name, value)
                for name, value in requested.items()
                if value["item_code"] == row.item_code and name not in selected_source_names
            ]
            if len(candidates) == 1:
                source_row_name, request = candidates[0]
        if request is None:
            continue
        qty = -abs(flt(request["qty"]))
        row.qty = qty
        row.stock_qty = qty * flt(row.get("conversion_factor") or 1)
        # ERPNext's native return mapper carries the original submitted line rate.
        # Never replace it with a client-supplied return rate.
        selected_source_names.add(source_row_name)
        selected.append(row)

    if len(selected_source_names) != len(requested):
        frappe.throw(_("ERPNext return mapper could not match every requested source row."))
    credit.set("items", selected)

    erpnext_tax_authority.apply_sales_tax_authority(credit)
    credit.insert(ignore_permissions=True)
    credit.submit()
    credit.reload()
    credit.flags.ledgix_duplicate_client_return = False
    return credit


def create_exchange(
    *,
    sales_invoice: str,
    return_items,
    replacement_items,
    customer: str | None = None,
    reason: str,
    exchange_reference: str,
    client_return_id: str | None = None,
    client_sale_id: str | None = None,
    selling_price_list: str | None = None,
):
    exchange_reference = str(exchange_reference or "").strip()
    if not exchange_reference:
        frappe.throw(_("Exchange reference is required."))
    source = frappe.get_doc("Sales Invoice", sales_invoice)
    credit = create_sales_return(
        sales_invoice=source.name,
        return_items=return_items,
        reason=reason,
        client_return_id=client_return_id,
        exchange_reference=exchange_reference,
        checkout_source="Ledgix Native Exchange Return",
    )
    replacement = create_sales_invoice(
        customer=customer or source.customer,
        items=replacement_items,
        company=source.company,
        selling_price_list=selling_price_list or source.selling_price_list,
        sale_channel=source.get("custom_ledgix_sale_channel") or "B2B",
        client_sale_id=client_sale_id,
        exchange_reference=exchange_reference,
        checkout_source="Ledgix Native Exchange Replacement",
        submit=True,
    )
    return {"credit_note": credit, "replacement_invoice": replacement}


def _customer_credit_limit(customer: str, company: str) -> float:
    value = frappe.db.get_value(
        "Customer Credit Limit",
        {"parent": customer, "company": company, "parenttype": "Customer"},
        "credit_limit",
    )
    return flt(value)


def get_customer_receivables(
    customer: str,
    *,
    company: str | None = None,
    as_of: str | None = None,
) -> dict:
    """Read customer AR/credit exclusively from ERPNext transaction state."""

    company = _company(company)
    customer = _resolve_customer(customer)
    as_of_date = getdate(as_of or today())
    rows = frappe.get_all(
        "Sales Invoice",
        filters={"company": company, "customer": customer, "docstatus": 1},
        fields=[
            "name",
            "posting_date",
            "due_date",
            "is_return",
            "return_against",
            "grand_total",
            "outstanding_amount",
            "custom_ledgix_sale_channel",
        ],
        order_by="posting_date asc, creation asc",
        limit_page_length=0,
    )

    positive_outstanding = 0.0
    invoice_credit = 0.0
    overdue = 0.0
    oldest_due_date = None
    invoices = []
    credits = []
    for row in rows:
        balance = flt(row.outstanding_amount, 2)
        due = getdate(row.due_date or row.posting_date)
        if balance > MONEY_TOLERANCE:
            positive_outstanding += balance
            if due < as_of_date:
                overdue += balance
                if oldest_due_date is None or due < oldest_due_date:
                    oldest_due_date = due
            invoices.append(
                {
                    "invoice": row.name,
                    "grand_total": flt(row.grand_total, 2),
                    "outstanding": balance,
                    "due_date": due,
                    "sale_channel": row.custom_ledgix_sale_channel or "",
                }
            )
        elif balance < -MONEY_TOLERANCE:
            amount = abs(balance)
            invoice_credit += amount
            credits.append(
                {
                    "credit_note": row.name,
                    "return_against": row.return_against,
                    "credit": amount,
                }
            )

    payment_rows = frappe.get_all(
        "Payment Entry",
        filters={
            "company": company,
            "party_type": "Customer",
            "party": customer,
            "docstatus": 1,
            "payment_type": "Receive",
        },
        fields=["name", "unallocated_amount"],
        limit_page_length=0,
    )
    unallocated_credit = flt(
        sum(max(flt(row.unallocated_amount), 0) for row in payment_rows), 2
    )
    outstanding = flt(positive_outstanding, 2)
    total_credit = flt(invoice_credit + unallocated_credit, 2)
    net_balance = flt(outstanding - total_credit, 2)
    credit_limit = _customer_credit_limit(customer, company)

    return {
        "customer": customer,
        "company": company,
        "credit_limit": credit_limit,
        "outstanding": outstanding,
        "invoice_credit": flt(invoice_credit, 2),
        "unallocated_credit": unallocated_credit,
        "net_balance": net_balance,
        "credit_balance": max(-net_balance, 0),
        "available_credit": max(flt(credit_limit - net_balance, 2), 0),
        "overdue": flt(overdue, 2),
        "oldest_due_date": oldest_due_date,
        "invoices": invoices,
        "credits": credits,
        "authority": "ERPNext Sales Invoice + Payment Entry",
    }


def invoice_summary(invoice, *, include_items: bool = False) -> dict:
    result = {
        "invoice": invoice.name or "",
        "docstatus": cint(invoice.docstatus),
        "customer": invoice.customer,
        "sale_channel": invoice.get("custom_ledgix_sale_channel") or "",
        "price_list": invoice.selling_price_list,
        "net_total": flt(invoice.net_total, 2),
        "tax_amount": flt(invoice.total_taxes_and_charges, 2),
        "grand_total": flt(invoice.grand_total, 2),
        "outstanding_amount": flt(invoice.outstanding_amount, 2),
        "is_return": bool(cint(invoice.is_return)),
        "return_against": invoice.return_against or "",
        "client_sale_id": invoice.get("custom_ledgix_client_sale_id") or "",
        "client_return_id": invoice.get("custom_ledgix_client_return_id") or "",
        "exchange_reference": invoice.get("custom_ledgix_exchange_reference") or "",
        "fbr_status": invoice.get("custom_ledgix_fbr_status") or "",
        "duplicate": bool(
            getattr(invoice.flags, "ledgix_duplicate_client_sale", False)
            or getattr(invoice.flags, "ledgix_duplicate_client_return", False)
        ),
    }
    discount = getattr(invoice, "_ledgix_discount", None)
    if discount:
        result["discount"] = discount
    if include_items:
        result["items"] = [
            {
                "sales_invoice_item": row.name or "",
                "item_code": row.item_code,
                "item_name": row.item_name,
                "qty": flt(row.qty),
                "rate": flt(row.rate, 2),
                "amount": flt(row.amount, 2),
                "price_list_rate": flt(row.price_list_rate, 2),
            }
            for row in invoice.items
        ]
    return result
