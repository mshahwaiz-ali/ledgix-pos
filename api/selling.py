from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from ledgix_saas.services import erpnext_selling
from ledgix_saas.api.security import require_ledgix_cashier_or_above


def _parse(value):
    return frappe.parse_json(value) if isinstance(value, str) else value


def _require_manager() -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"System Manager", "Ledgix Admin", "Ledgix Manager"}):
        frappe.throw(_("Manager or Admin access is required."), frappe.PermissionError)


def _require_admin() -> None:
    roles = set(frappe.get_roles(frappe.session.user))
    if not roles.intersection({"System Manager", "Ledgix Admin"}):
        frappe.throw(_("Admin access is required."), frappe.PermissionError)


def _allow_rate_override() -> bool:
    return bool(
        set(frappe.get_roles(frappe.session.user)).intersection(
            {"System Manager", "Ledgix Admin", "Ledgix Manager"}
        )
    )


def _invoice_items_from_cart(cart_items) -> list[dict]:
    rows = _parse(cart_items) or []
    return [
        {
            "item": row.get("item") or row.get("item_code"),
            "qty": row.get("qty") or row.get("quantity"),
            "uom": row.get("uom"),
            "override_rate": row.get("override_rate"),
            "warehouse": row.get("warehouse"),
        }
        for row in rows
    ]


def _auto_allocations(customer: str, amount: float) -> list[dict]:
    credit = erpnext_selling.get_customer_receivables(customer)
    remaining = flt(amount)
    allocations = []
    for row in credit.get("invoices") or []:
        if remaining <= 0:
            break
        outstanding = flt(row.get("outstanding"))
        if outstanding <= 0:
            continue
        allocated = min(remaining, outstanding)
        allocations.append(
            {
                "reference_doctype": "Sales Invoice",
                "reference_name": row["invoice"],
                "allocated_amount": allocated,
            }
        )
        remaining -= allocated
    return allocations


def _native_invoice_reference(value: str | None):
    value = str(value or "").strip()
    if not value:
        return None
    if frappe.db.exists("Sales Invoice", value):
        doc = frappe.get_doc("Sales Invoice", value)
        return doc if doc.docstatus == 1 else None
    name = frappe.db.get_value(
        "Sales Invoice",
        {"custom_ledgix_client_sale_id": value, "docstatus": 1},
        "name",
    )
    return frappe.get_doc("Sales Invoice", name) if name else None


@frappe.whitelist()
def preview_b2b_invoice(
    customer,
    items=None,
    price_list=None,
    discount_type="Amount",
    discount_value=0,
    due_date=None,
):
    _require_manager()
    return erpnext_selling.preview_sales_invoice(
        customer=customer,
        items=_invoice_items_from_cart(items),
        selling_price_list=price_list,
        sale_channel="B2B",
        due_date=due_date,
        discount_type=discount_type,
        discount_value=discount_value,
        allow_rate_override=_allow_rate_override(),
        update_stock=False,
        checkout_source="Ledgix B2B Preview",
    )


@frappe.whitelist()
def create_b2b_invoice(
    customer,
    items=None,
    price_list=None,
    client_sale_id=None,
    discount_type="Amount",
    discount_value=0,
    due_date=None,
):
    _require_manager()
    invoice = erpnext_selling.create_sales_invoice(
        customer=customer,
        items=_invoice_items_from_cart(items),
        selling_price_list=price_list,
        sale_channel="B2B",
        client_sale_id=client_sale_id,
        due_date=due_date,
        discount_type=discount_type,
        discount_value=discount_value,
        allow_rate_override=_allow_rate_override(),
        update_stock=False,
        checkout_source="Ledgix B2B Checkout",
        submit=True,
    )
    return erpnext_selling.invoice_summary(invoice, include_items=True)


@frappe.whitelist()
def complete_b2b_sale(
    customer,
    cart_items=None,
    tenders=None,
    price_list=None,
    client_sale_id=None,
    discount_type="Amount",
    discount_value=0,
    due_date=None,
):
    """Current Ledgix B2B checkout contract backed only by ERPNext finance docs."""

    _require_manager()
    invoice = erpnext_selling.create_sales_invoice(
        customer=customer,
        items=_invoice_items_from_cart(cart_items),
        selling_price_list=price_list,
        sale_channel="B2B",
        client_sale_id=client_sale_id,
        due_date=due_date,
        discount_type=discount_type,
        discount_value=discount_value,
        allow_rate_override=_allow_rate_override(),
        update_stock=False,
        checkout_source="Ledgix POS B2B Checkout",
        submit=True,
    )
    duplicate = bool(getattr(invoice.flags, "ledgix_duplicate_client_sale", False))

    payments = []
    if not duplicate:
        for index, tender in enumerate(_parse(tenders) or [], start=1):
            amount = flt(tender.get("amount"))
            method = tender.get("payment_method") or tender.get("mode_of_payment")
            if amount <= 0 or not method:
                continue
            invoice.reload()
            allocation = min(amount, max(flt(invoice.outstanding_amount), 0))
            if allocation <= 0:
                break
            payment = erpnext_selling.post_customer_payment(
                customer=invoice.customer,
                mode_of_payment=method,
                amount=amount,
                allocations=[
                    {"reference_name": invoice.name, "allocated_amount": allocation}
                ],
                client_payment_id=(
                    f"{client_sale_id}:PAY:{index}" if client_sale_id else None
                ),
                reference_number=tender.get("reference_number")
                or tender.get("reference_no"),
                payment_source="Ledgix POS B2B Checkout",
            )
            payments.append(payment.name)

    invoice.reload()
    result = erpnext_selling.invoice_summary(invoice, include_items=False)
    result.update(
        {
            "success": True,
            "sale": invoice.name,
            "invoice_number": invoice.name,
            "paid_amount": flt(invoice.grand_total - invoice.outstanding_amount, 2),
            "remaining_amount": max(flt(invoice.outstanding_amount, 2), 0),
            "change_amount": 0.0,
            "payment_status": (
                "Paid"
                if abs(flt(invoice.outstanding_amount)) <= 0.005
                else "Partial"
                if flt(invoice.outstanding_amount) < flt(invoice.grand_total) - 0.005
                else "Unpaid"
            ),
            "payments": payments,
            "print_mode": "A4",
            "duplicate": duplicate,
            "financial_authority": "ERPNext",
        }
    )
    return result


@frappe.whitelist()
def get_customer_credit(customer):
    _require_manager()
    return erpnext_selling.get_customer_receivables(customer)


@frappe.whitelist()
def get_customer_open_invoices(customer):
    _require_manager()
    return erpnext_selling.get_customer_receivables(customer)


@frappe.whitelist()
def post_customer_payment(
    customer,
    payment_method,
    amount,
    allocations=None,
    reference_number=None,
    client_payment_id=None,
):
    _require_manager()
    allocations = _parse(allocations) or _auto_allocations(customer, flt(amount))
    if not allocations:
        frappe.throw(_("No open ERPNext Sales Invoice is available for allocation."))
    payment = erpnext_selling.post_customer_payment(
        customer=customer,
        mode_of_payment=payment_method,
        amount=amount,
        allocations=allocations,
        reference_number=reference_number,
        client_payment_id=client_payment_id,
        payment_source="Ledgix B2B Customer Payment",
    )
    return {
        "payment": payment.name,
        "docstatus": payment.docstatus,
        "amount": flt(payment.paid_amount, 2),
        "allocated_amount": flt(payment.total_allocated_amount, 2),
        "unallocated_amount": flt(payment.unallocated_amount, 2),
        "credit": erpnext_selling.get_customer_receivables(customer),
        "authority": "ERPNext Payment Entry",
    }


@frappe.whitelist()
def cancel_customer_payment(payment, reason):
    _require_admin()
    doc = erpnext_selling.cancel_payment_entry(payment, reason)
    return {
        "payment": doc.name,
        "docstatus": doc.docstatus,
        "cancelled": doc.docstatus == 2,
        "customer": doc.party if doc.party_type == "Customer" else None,
        "reason": reason,
    }


@frappe.whitelist()
def create_credit_note(
    sales_invoice,
    return_items=None,
    reason=None,
    client_return_id=None,
):
    _require_manager()
    note = erpnext_selling.create_sales_return(
        sales_invoice=sales_invoice,
        return_items=_parse(return_items),
        reason=reason,
        client_return_id=client_return_id,
    )
    return erpnext_selling.invoice_summary(note, include_items=True)


@frappe.whitelist()
def refund_credit_note(
    credit_note,
    payment_method,
    amount=None,
    client_payment_id=None,
    reference_number=None,
):
    _require_manager()
    payment = erpnext_selling.refund_credit_note(
        credit_note=credit_note,
        mode_of_payment=payment_method,
        amount=amount,
        client_payment_id=client_payment_id,
        reference_number=reference_number,
    )
    return {
        "payment": payment.name,
        "docstatus": payment.docstatus,
        "payment_type": payment.payment_type,
        "paid_amount": flt(payment.paid_amount, 2),
        "unallocated_amount": flt(payment.unallocated_amount, 2),
    }


@frappe.whitelist()
def create_exchange(
    sales_invoice,
    return_items=None,
    replacement_items=None,
    reason=None,
    exchange_reference=None,
    client_return_id=None,
    client_sale_id=None,
    price_list=None,
):
    _require_manager()
    result = erpnext_selling.create_exchange(
        sales_invoice=sales_invoice,
        return_items=_parse(return_items),
        replacement_items=_invoice_items_from_cart(replacement_items),
        reason=reason,
        exchange_reference=exchange_reference,
        client_return_id=client_return_id,
        client_sale_id=client_sale_id,
        selling_price_list=price_list,
    )
    return {
        "exchange_reference": exchange_reference,
        "credit_note": erpnext_selling.invoice_summary(
            result["credit_note"], include_items=True
        ),
        "replacement_invoice": erpnext_selling.invoice_summary(
            result["replacement_invoice"], include_items=True
        ),
        "authority": "ERPNext Sales Invoice / Credit Note",
    }


@frappe.whitelist()
def complete_pos_v2_sale_compat(
    cart_items=None,
    tenders=None,
    customer=None,
    sale_channel="Retail",
    price_list=None,
    discount_type="Amount",
    discount_value=0,
    client_sale_id=None,
):
    """Keep the existing POS RPC stable while B2B writes move to ERPNext."""

    if sale_channel == "B2B":
        return complete_b2b_sale(
            customer=customer,
            cart_items=cart_items,
            tenders=tenders,
            price_list=price_list,
            client_sale_id=client_sale_id,
            discount_type=discount_type,
            discount_value=discount_value,
        )
    from ledgix_saas.api.pos_compat import complete_pos_v2_sale

    return complete_pos_v2_sale(
        cart_items=cart_items,
        tenders=tenders,
        customer=customer,
        sale_channel=sale_channel,
        price_list=price_list,
        discount_type=discount_type,
        discount_value=discount_value,
        client_sale_id=client_sale_id,
    )


@frappe.whitelist()
def preview_pos_v2_checkout_compat(
    cart_items=None,
    customer=None,
    sale_channel="Retail",
    price_list=None,
    discount_type="Amount",
    discount_value=0,
):
    if sale_channel == "B2B":
        native = preview_b2b_invoice(
            customer=customer,
            items=cart_items,
            price_list=price_list,
            discount_type=discount_type,
            discount_value=discount_value,
        )
        credit = erpnext_selling.get_customer_receivables(customer)
        return {
            "subtotal": native["net_total"],
            "discount_amount": flt((native.get("discount") or {}).get("amount"), 2),
            "total_amount": native["net_total"],
            "tax_amount": native["tax_amount"],
            "grand_total": native["grand_total"],
            "price_list": native["price_list"],
            "sale_channel": "B2B",
            "credit": credit,
            "items": native.get("items") or [],
            "financial_authority": "ERPNext",
        }
    from ledgix_saas.api.pos_compat import preview_pos_v2_checkout

    return preview_pos_v2_checkout(
        cart_items=cart_items,
        customer=customer,
        sale_channel=sale_channel,
        price_list=price_list,
        discount_type=discount_type,
        discount_value=discount_value,
    )


@frappe.whitelist()
def get_pos_v2_customer_context_compat(customer, sale_channel=None):
    from ledgix_saas.api.pos_compat import get_pos_v2_customer_context

    result = get_pos_v2_customer_context(customer, sale_channel)
    if result.get("sale_channel") == "B2B":
        credit = erpnext_selling.get_customer_receivables(customer)
        customer_row = dict(result.get("customer") or {})
        customer_row.update(
            {
                "outstanding": flt(credit.get("outstanding"), 2),
                "available_credit": flt(credit.get("available_credit"), 2),
                "overdue": flt(credit.get("overdue"), 2),
            }
        )
        result["customer"] = customer_row
        result["financial_authority"] = "ERPNext"
    return result


def _native_return_context(invoice) -> dict:
    returned = {}
    return_names = frappe.get_all(
        "Sales Invoice",
        filters={"return_against": invoice.name, "is_return": 1, "docstatus": 1},
        pluck="name",
        limit_page_length=0,
    )
    if return_names:
        rows = frappe.get_all(
            "Sales Invoice Item",
            filters={"parent": ["in", return_names], "parenttype": "Sales Invoice"},
            fields=["sales_invoice_item", "item_code", "qty"],
            limit_page_length=0,
        )
        for row in rows:
            key = row.sales_invoice_item or row.item_code
            returned[key] = flt(returned.get(key)) + abs(flt(row.qty))

    items = []
    for row in invoice.items:
        already = flt(returned.get(row.name) or returned.get(row.item_code), 2)
        returnable = max(flt(row.qty) - already, 0)
        if returnable <= 0.005:
            continue
        items.append(
            {
                "item": row.item_code,
                "item_code": row.item_code,
                "original_sale_item_row": row.name,
                "sales_invoice_item": row.name,
                "item_name": row.item_name,
                "sold_qty": flt(row.qty),
                "already_returned_qty": already,
                "returnable_qty": returnable,
                "return_qty": 0,
                "rate": flt(row.rate),
                "amount": 0,
            }
        )
    return {
        "success": True,
        "sale_id": invoice.name,
        "invoice_number": invoice.name,
        "customer": invoice.customer,
        "sale_date": invoice.posting_date,
        "items": items,
        "financial_authority": "ERPNext",
    }


@frappe.whitelist()
def get_pos_return_context_compat(sale_id=None):
    require_ledgix_cashier_or_above()
    invoice = _native_invoice_reference(sale_id)
    if invoice:
        return _native_return_context(invoice)
    from ledgix_saas.services import erpnext_pos
    result = erpnext_pos.get_return_context(sale_id)
    if not result:
        frappe.throw("Select a submitted ERPNext Sales Invoice or POS Invoice.")
    return result


@frappe.whitelist()
def create_pos_return_compat(original_sale=None, return_items=None, reason=None, client_return_id=None):
    require_ledgix_cashier_or_above()
    invoice = _native_invoice_reference(original_sale)
    if invoice:
        _require_manager()
        note = erpnext_selling.create_sales_return(
            sales_invoice=invoice.name,
            return_items=_parse(return_items) or [],
            reason=reason,
            client_return_id=client_return_id,
            checkout_source="Ledgix POS B2B Return",
        )
        return {
            "success": True,
            "return_id": note.name,
            "original_sale": invoice.name,
            "customer": note.customer,
            "total_amount": flt(note.net_total, 2),
            "tax_amount": flt(note.total_taxes_and_charges, 2),
            "grand_total": flt(note.grand_total, 2),
            "fbr_status": note.get("custom_ledgix_fbr_status") or "",
            "financial_authority": "ERPNext",
        }
    from ledgix_saas.services import erpnext_pos
    if not erpnext_pos._submitted_pos_invoice(original_sale):
        frappe.throw("Select a submitted ERPNext Sales Invoice or POS Invoice.")
    return erpnext_pos.return_result(erpnext_pos.create_return(
        original_sale=original_sale,
        return_items=_parse(return_items) or [],
        reason=reason,
        client_return_id=client_return_id,
    ))
