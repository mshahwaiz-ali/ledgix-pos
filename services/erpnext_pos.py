from __future__ import annotations

"""ERPNext-native POS engine behind the retained Ledgix POS user interface.

Phase 8 keeps the fast Ledgix screen but makes ERPNext POS Profile, POS Opening /
Closing Entry, POS Invoice, Customer, Item, Price List, Mode of Payment, Bin,
Batch and Serial No authoritative. Legacy Ledgix POS/Sale/Payment/Shift/Hold
DocTypes remain historical only and are never written here.
"""

import json
from collections.abc import Iterable

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime, nowdate

from ledgix_saas.services import erpnext_buying_inventory, erpnext_selling, erpnext_tax_authority
from ledgix_saas.setup import erpnext_phase8_extensions

MONEY_TOLERANCE = 0.005


def _parse(value):
    return frappe.parse_json(value) if isinstance(value, str) else value


def _company(company: str | None = None) -> str:
    return erpnext_selling._company(company)


def _user(user: str | None = None) -> str:
    return str(user or frappe.session.user or "").strip()


def profile_for_user(
    company: str | None = None,
    *,
    user: str | None = None,
    pos_profile: str | None = None,
):
    company = _company(company)
    user = _user(user)
    if pos_profile:
        doc = frappe.get_doc("POS Profile", pos_profile)
    else:
        from erpnext.stock.get_item_details import get_pos_profile

        profile_row = get_pos_profile(company, user=user)
        profile_name = (
            profile_row.get("name")
            if isinstance(profile_row, dict)
            else getattr(profile_row, "name", profile_row)
        )
        doc = frappe.get_doc("POS Profile", profile_name) if profile_name else None
    if not doc:
        frappe.throw(_("No active ERPNext POS Profile is configured for {0} in {1}.").format(user, company))
    if doc.company != company:
        frappe.throw(_("POS Profile {0} belongs to another Company.").format(doc.name))
    if cint(doc.get("disabled")):
        frappe.throw(_("POS Profile {0} is disabled.").format(doc.name))
    return doc


def _profile_warehouse(profile) -> str:
    warehouse = str(profile.warehouse or "").strip()
    if warehouse:
        return erpnext_buying_inventory._resolve_warehouse(warehouse, profile.company)
    return erpnext_buying_inventory.default_warehouse(profile.company)


def _profile_customer(profile, customer: str | None = None) -> str:
    candidate = str(customer or profile.customer or "").strip()
    if not candidate:
        frappe.throw(_("POS Profile {0} needs a default Customer for retail checkout.").format(profile.name))
    return erpnext_selling._resolve_customer(candidate)


def _price_list(profile, price_list: str | None = None) -> str:
    return erpnext_selling._resolve_price_list(price_list or profile.selling_price_list)


def _mode_policy(mode: str, company: str) -> dict:
    mode = erpnext_selling._resolve_mode_of_payment(mode)
    meta = frappe.get_meta("Mode of Payment")
    fields = ["name", "type"]
    for optional in (
        "enabled",
        "custom_ledgix_legacy_payment_method",
        "custom_ledgix_legacy_method_type",
        "custom_ledgix_sort_order",
        "custom_ledgix_requires_reference",
        "custom_ledgix_allow_change",
    ):
        if meta.has_field(optional):
            fields.append(optional)
    row = frappe.db.get_value("Mode of Payment", mode, fields, as_dict=True) or {}
    account = erpnext_selling._mode_account(mode, company)
    return {
        "name": mode,
        "payment_method_name": mode,
        "type": row.get("type") or "",
        "method_type": row.get("custom_ledgix_legacy_method_type") or row.get("type") or "",
        "legacy_payment_method": row.get("custom_ledgix_legacy_payment_method") or "",
        "sort_order": cint(row.get("custom_ledgix_sort_order")),
        "requires_reference": bool(cint(row.get("custom_ledgix_requires_reference"))),
        "allow_change": bool(cint(row.get("custom_ledgix_allow_change"))),
        "account": account,
    }


def payment_methods(profile) -> list[dict]:
    rows = []
    for index, configured in enumerate(profile.payments or []):
        policy = _mode_policy(configured.mode_of_payment, profile.company)
        policy["default"] = bool(cint(configured.default))
        policy["profile_index"] = index
        rows.append(policy)
    rows.sort(key=lambda row: (row["sort_order"], row["profile_index"], row["name"]))
    return rows


def _cash_modes(profile) -> list[str]:
    return [row["name"] for row in payment_methods(profile) if row["type"] == "Cash"]


def active_opening(profile=None, *, company: str | None = None, user: str | None = None):
    user = _user(user)
    profile = profile or profile_for_user(company, user=user)
    name = frappe.db.get_value(
        "POS Opening Entry",
        {
            "company": profile.company,
            "pos_profile": profile.name,
            "user": user,
            "status": "Open",
            "docstatus": 1,
        },
        "name",
        order_by="period_start_date desc",
    )
    return frappe.get_doc("POS Opening Entry", name) if name else None


def open_shift(
    opening_cash: float = 0,
    *,
    notes: str | None = None,
    company: str | None = None,
    user: str | None = None,
    pos_profile: str | None = None,
):
    user = _user(user)
    profile = profile_for_user(company, user=user, pos_profile=pos_profile)
    existing = active_opening(profile, user=user)
    if existing:
        return existing

    opening_cash = max(flt(opening_cash), 0)
    methods = payment_methods(profile)
    cash_modes = [row["name"] for row in methods if row["type"] == "Cash"]
    if opening_cash and not cash_modes:
        frappe.throw(_("Opening cash cannot be recorded because the POS Profile has no Cash mode."))

    balance_details = []
    cash_assigned = False
    for row in methods:
        amount = 0.0
        if row["type"] == "Cash" and not cash_assigned:
            amount = opening_cash
            cash_assigned = True
        balance_details.append({"mode_of_payment": row["name"], "opening_amount": amount})

    opening = frappe.get_doc(
        {
            "doctype": "POS Opening Entry",
            "period_start_date": now_datetime(),
            "posting_date": nowdate(),
            "company": profile.company,
            "pos_profile": profile.name,
            "user": user,
            "custom_ledgix_opening_notes": str(notes or "").strip(),
            "balance_details": balance_details,
        }
    )
    opening.insert(ignore_permissions=True)
    opening.submit()
    opening.reload()
    return opening


def _opening_cash(opening) -> float:
    if not opening:
        return 0.0
    cash_modes = set(_cash_modes(frappe.get_doc("POS Profile", opening.pos_profile)))
    return flt(sum(flt(row.opening_amount) for row in opening.balance_details if row.mode_of_payment in cash_modes), 2)


def _unclosed_pos_invoices(opening) -> list[str]:
    if not opening:
        return []
    rows = frappe.db.sql(
        """
        select name
        from `tabPOS Invoice`
        where docstatus = 1
          and pos_profile = %s
          and owner = %s
          and ifnull(consolidated_invoice, '') = ''
          and timestamp(posting_date, coalesce(posting_time, '00:00:00')) >= %s
        order by posting_date asc, posting_time asc, creation asc
        """,
        (opening.pos_profile, opening.user, opening.period_start_date),
        as_dict=True,
    )
    return [row.name for row in rows]


def shift_info(*, company: str | None = None, user: str | None = None, pos_profile: str | None = None) -> dict:
    user = _user(user)
    profile = profile_for_user(company, user=user, pos_profile=pos_profile)
    opening = active_opening(profile, user=user)
    if not opening:
        return {
            "has_active_shift": False,
            "shift_id": None,
            "opening_cash": 0.0,
            "total_sales": 0.0,
            "cash_sales": 0.0,
            "non_cash_sales": 0.0,
            "invoice_count": 0,
            "expected_cash": 0.0,
            "actual_cash": None,
            "cash_variance": None,
            "pos_profile": profile.name,
            "authority": "ERPNext POS Opening Entry / POS Closing Entry",
        }

    invoice_names = _unclosed_pos_invoices(opening)
    total_sales = 0.0
    cash_sales = 0.0
    non_cash_sales = 0.0
    cash_modes = set(_cash_modes(profile))
    for name in invoice_names:
        invoice = frappe.get_doc("POS Invoice", name)
        total_sales += flt(invoice.grand_total)
        for row in invoice.payments:
            amount = flt(row.amount)
            if row.mode_of_payment in cash_modes:
                cash_sales += amount
            else:
                non_cash_sales += amount

    opening_cash = _opening_cash(opening)
    expected_cash = flt(opening_cash + cash_sales, 2)
    return {
        "has_active_shift": True,
        "shift_id": opening.name,
        "opening_cash": flt(opening_cash, 2),
        "total_sales": flt(total_sales, 2),
        "cash_sales": flt(cash_sales, 2),
        "non_cash_sales": flt(non_cash_sales, 2),
        "invoice_count": len(invoice_names),
        "expected_cash": expected_cash,
        "actual_cash": None,
        "cash_variance": None,
        "pos_profile": profile.name,
        "authority": "ERPNext POS Opening Entry / POS Invoice",
    }


def close_shift(
    actual_cash: float,
    *,
    closing_notes: str | None = None,
    shift_name: str | None = None,
    company: str | None = None,
    user: str | None = None,
):
    user = _user(user)
    profile = profile_for_user(company, user=user)
    opening = active_opening(profile, user=user)
    if not opening:
        frappe.throw(_("No active ERPNext POS Opening Entry exists for this user."))
    if shift_name and opening.name != str(shift_name):
        frappe.throw(_("The requested shift is not the active ERPNext POS Opening Entry."))

    from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening

    closing = make_closing_entry_from_opening(opening)
    closing.custom_ledgix_closing_notes = str(closing_notes or "").strip()
    cash_modes = set(_cash_modes(profile))
    actual_cash = max(flt(actual_cash), 0)
    cash_assigned = False
    for row in closing.payment_reconciliation:
        if row.mode_of_payment in cash_modes and not cash_assigned:
            row.closing_amount = actual_cash
            cash_assigned = True
        elif row.mode_of_payment in cash_modes:
            row.closing_amount = flt(row.expected_amount)
        else:
            row.closing_amount = flt(row.expected_amount)
    closing.insert(ignore_permissions=True)
    closing.submit()
    closing.reload()
    opening.reload()
    return opening, closing


def _customer_payload(customer: str, sale_channel: str, company: str) -> dict:
    name = erpnext_selling._resolve_customer(customer)
    row = frappe.db.get_value(
        "Customer",
        name,
        ["name", "customer_name", "customer_group", "territory", "tax_id"],
        as_dict=True,
    ) or {}
    result = {
        "name": name,
        "customer_name": row.get("customer_name") or name,
        "customer_group": row.get("customer_group") or "",
        "territory": row.get("territory") or "",
        "ntn_cnic": row.get("tax_id") or "",
        "outstanding": 0.0,
        "available_credit": 0.0,
        "overdue": 0.0,
    }
    if sale_channel == "B2B":
        credit = erpnext_selling.get_customer_receivables(name, company=company)
        result.update(
            {
                "outstanding": flt(credit.get("outstanding"), 2),
                "available_credit": flt(credit.get("available_credit"), 2),
                "overdue": flt(credit.get("overdue"), 2),
            }
        )
    return result


def customer_context(customer: str | None, sale_channel: str = "Retail", *, company: str | None = None) -> dict:
    company = _company(company)
    profile = profile_for_user(company)
    sale_channel = "B2B" if sale_channel == "B2B" else "Retail"
    if sale_channel == "B2B" and not str(customer or "").strip():
        frappe.throw(_("Customer is required for B2B POS mode."))
    customer_name = _profile_customer(profile, customer)
    price_list = _price_list(profile, None)
    return {
        "sale_channel": sale_channel,
        "customer": _customer_payload(customer_name, sale_channel, company),
        "price_list": price_list,
        "authority": "ERPNext Customer / Price List",
    }


def _item_groups() -> list[dict]:
    rows = frappe.db.sql(
        """
        select distinct ig.name, ig.item_group_name
        from `tabItem Group` ig
        inner join `tabItem` i on i.item_group = ig.name
        where ig.is_group = 0
          and i.disabled = 0
          and i.is_sales_item = 1
        order by ig.item_group_name asc, ig.name asc
        """,
        as_dict=True,
    )
    return [{"name": row.name, "category_name": row.item_group_name or row.name} for row in rows]


def _tracking_type(row) -> str:
    if cint(row.get("has_serial_no")):
        return "Serial Based"
    if cint(row.get("has_batch_no")):
        return "Lot Based"
    return "Normal"


def _barcode(item_code: str) -> str:
    return frappe.db.get_value("Item Barcode", {"parent": item_code}, "barcode") or ""


def search_items(
    *,
    query: str | None = None,
    category: str | None = None,
    customer: str | None = None,
    sale_channel: str = "Retail",
    price_list: str | None = None,
    company: str | None = None,
    limit: int = 80,
) -> dict:
    company = _company(company)
    profile = profile_for_user(company)
    sale_channel = "B2B" if sale_channel == "B2B" else "Retail"
    customer_name = _profile_customer(profile, customer)
    if sale_channel == "B2B" and not str(customer or "").strip():
        frappe.throw(_("Select a Customer before loading B2B pricing."))
    resolved_price_list = _price_list(profile, price_list)
    warehouse = _profile_warehouse(profile)
    limit = min(max(cint(limit) or 80, 1), 200)

    filters: dict = {"disabled": 0, "is_sales_item": 1}
    if category and category != "All":
        filters["item_group"] = category
    query = str(query or "").strip()
    or_filters = None
    if query:
        like = f"%{query}%"
        or_filters = {"item_code": ["like", like], "item_name": ["like", like]}
    rows = frappe.get_all(
        "Item",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "item_code",
            "item_name",
            "item_group",
            "stock_uom",
            "is_stock_item",
            "has_serial_no",
            "has_batch_no",
            "custom_ledgix_legacy_sku",
        ],
        order_by="item_name asc, item_code asc",
        limit_page_length=limit,
    )

    if query:
        barcode_item = frappe.db.get_value("Item Barcode", {"barcode": query}, "parent")
        if barcode_item and all(row.name != barcode_item for row in rows):
            extra = frappe.db.get_value(
                "Item",
                barcode_item,
                [
                    "name",
                    "item_code",
                    "item_name",
                    "item_group",
                    "stock_uom",
                    "is_stock_item",
                    "has_serial_no",
                    "has_batch_no",
                    "custom_ledgix_legacy_sku",
                ],
                as_dict=True,
            )
            if extra and not cint(frappe.db.get_value("Item", barcode_item, "disabled")):
                rows.insert(0, extra)

    items = []
    for row in rows:
        try:
            pricing = erpnext_selling._native_item_rate(
                item_code=row.item_code,
                customer=customer_name,
                company=company,
                price_list=resolved_price_list,
                qty=1,
                posting_date=nowdate(),
            )
        except Exception:
            continue
        stock = {"actual_qty": 0.0}
        if cint(row.is_stock_item):
            stock = erpnext_buying_inventory.stock_snapshot(row.item_code, warehouse=warehouse, company=company)
        items.append(
            {
                "name": row.item_code,
                "item_code": row.item_code,
                "sku": row.get("custom_ledgix_legacy_sku") or row.item_code,
                "barcode": _barcode(row.item_code),
                "item_name": row.item_name,
                "category": row.item_group,
                "unit": row.stock_uom,
                "rate": flt(pricing.rate, 2),
                "list_rate": flt(pricing.price_list_rate, 2),
                "current_stock": flt(stock.get("actual_qty"), 3),
                "is_stock_item": bool(cint(row.is_stock_item)),
                "tracking_type": _tracking_type(row),
                "warehouse": warehouse,
            }
        )
    return {
        "items": items,
        "price_list": resolved_price_list,
        "warehouse": warehouse,
        "sale_channel": sale_channel,
        "authority": "ERPNext Item / Item Price / Pricing Rule / Bin",
    }


def boot(sale_channel: str = "Retail", customer: str | None = None, *, company: str | None = None) -> dict:
    company = _company(company)
    profile = profile_for_user(company)
    sale_channel = "B2B" if sale_channel == "B2B" else "Retail"
    roles = set(frappe.get_roles(frappe.session.user))
    can_b2b = bool(roles.intersection({"System Manager", "Ledgix Admin", "Ledgix Manager"}))
    can_override = can_b2b
    if sale_channel == "B2B" and not can_b2b:
        frappe.throw(_("B2B checkout requires Ledgix Manager or Admin access."), frappe.PermissionError)

    resolved_customer = str(customer or "").strip()
    if sale_channel == "Retail":
        resolved_customer = _profile_customer(profile, resolved_customer or None)
    customer_row = (
        _customer_payload(resolved_customer, sale_channel, company) if resolved_customer else None
    )
    opening = active_opening(profile)
    return {
        "sale_channel": sale_channel,
        "customer": customer_row,
        "price_list": _price_list(profile, None),
        "price_lists": [
            {"name": row.name, "price_list_name": row.name}
            for row in frappe.get_all(
                "Price List",
                filters={"enabled": 1, "selling": 1},
                fields=["name"],
                order_by="name asc",
                limit_page_length=0,
            )
        ],
        "payment_methods": payment_methods(profile),
        "categories": _item_groups(),
        "active_shift": opening.name if opening else None,
        "pos_profile": profile.name,
        "warehouse": _profile_warehouse(profile),
        "can_b2b": can_b2b,
        "can_discount": can_override,
        "can_override_price": can_override,
        "authority": "ERPNext POS Profile / Customer / Item / Price / Stock / Payment",
    }


def _raw_items(items) -> list[dict]:
    rows = _parse(items) or []
    return [dict(row) for row in rows]


def _override_audit(raw_items: list[dict], normalized: list[dict], allow_rate_override: bool) -> list[dict]:
    audit = []
    for raw, row in zip(raw_items, normalized):
        requested = raw.get("override_rate")
        if requested in (None, ""):
            continue
        if not allow_rate_override:
            frappe.throw(_("Price override requires Ledgix Manager or Admin access."), frappe.PermissionError)
        reason = str(raw.get("override_reason") or "").strip()
        if not reason:
            frappe.throw(_("A reason is required for every POS price override."))
        audit.append(
            {
                "item_code": row["item_code"],
                "native_price_list_rate": flt(row.get("price_list_rate"), 6),
                "override_rate": flt(row.get("rate"), 6),
                "reason": reason,
                "user": frappe.session.user,
            }
        )
    return audit


def build_pos_invoice(
    *,
    cart_items,
    customer: str | None = None,
    price_list: str | None = None,
    discount_type: str = "Amount",
    discount_value: float = 0,
    client_sale_id: str | None = None,
    allow_rate_override: bool = False,
    source: str = "Ledgix POS",
    company: str | None = None,
    pos_profile: str | None = None,
):
    erpnext_phase8_extensions.sync_all()
    company = _company(company)
    profile = profile_for_user(company, pos_profile=pos_profile)
    customer_name = _profile_customer(profile, customer)
    resolved_price_list = _price_list(profile, price_list)
    warehouse = _profile_warehouse(profile)
    raw = _raw_items(cart_items)
    normalized = erpnext_selling._normalize_items(
        raw,
        customer=customer_name,
        company=company,
        price_list=resolved_price_list,
        posting_date=nowdate(),
        allow_rate_override=allow_rate_override,
    )
    discount = erpnext_selling._apply_checkout_discount(normalized, discount_type, discount_value)
    audit = _override_audit(raw, normalized, allow_rate_override)
    for source_row, row in zip(raw, normalized):
        row["warehouse"] = row.get("warehouse") or warehouse
        serials = source_row.get("serial_numbers") or source_row.get("serial_no")
        if isinstance(serials, (list, tuple)):
            serials = "\n".join(str(value).strip() for value in serials if str(value).strip())
        if serials:
            row["serial_no"] = str(serials).replace(",", "\n")

    invoice = frappe.get_doc(
        {
            "doctype": "POS Invoice",
            "company": company,
            "customer": customer_name,
            "posting_date": nowdate(),
            "currency": erpnext_selling._currency(company),
            "selling_price_list": resolved_price_list,
            "pos_profile": profile.name,
            "set_warehouse": warehouse,
            "is_pos": 1,
            "custom_ledgix_client_sale_id": str(client_sale_id or "").strip(),
            "custom_ledgix_sale_channel": "Retail",
            "custom_ledgix_checkout_source": source,
            "custom_ledgix_price_override_json": json.dumps(audit, sort_keys=True) if audit else "",
            "items": normalized,
        }
    )
    invoice.set_missing_values()
    invoice.set("payments", [])
    erpnext_tax_authority.apply_sales_tax_authority(invoice)
    invoice._ledgix_discount = discount
    return invoice


def preview_checkout(**kwargs) -> dict:
    invoice = build_pos_invoice(**kwargs)
    discount = getattr(invoice, "_ledgix_discount", {}) or {}
    return {
        "subtotal": flt(invoice.total, 2),
        "discount_amount": flt(discount.get("amount"), 2),
        "total_amount": flt(invoice.net_total, 2),
        "tax_amount": flt(invoice.total_taxes_and_charges, 2),
        "grand_total": flt(invoice.grand_total, 2),
        "price_list": invoice.selling_price_list,
        "sale_channel": "Retail",
        "items": [
            {
                "item": row.item_code,
                "item_code": row.item_code,
                "item_name": row.item_name,
                "qty": flt(row.qty),
                "rate": flt(row.rate, 2),
                "amount": flt(row.amount, 2),
                "warehouse": row.warehouse,
            }
            for row in invoice.items
        ],
        "financial_authority": "ERPNext POS Invoice",
    }


def _existing_pos_sale(client_sale_id: str, company: str):
    client_sale_id = str(client_sale_id or "").strip()
    if not client_sale_id:
        return None
    name = frappe.db.get_value(
        "POS Invoice",
        {
            "company": company,
            "custom_ledgix_client_sale_id": client_sale_id,
            "docstatus": ["!=", 2],
        },
        "name",
    )
    return frappe.get_doc("POS Invoice", name) if name else None


def _normalize_tenders(tenders, profile, grand_total: float) -> list[dict]:
    rows = _parse(tenders) or []
    configured = {row["name"]: row for row in payment_methods(profile)}
    normalized = []
    for raw in rows:
        mode = erpnext_selling._resolve_mode_of_payment(
            raw.get("payment_method") or raw.get("mode_of_payment")
        )
        if mode not in configured:
            frappe.throw(_("Mode of Payment {0} is not configured on POS Profile {1}.").format(mode, profile.name))
        amount = flt(raw.get("amount"))
        if amount <= 0:
            continue
        policy = configured[mode]
        reference = str(raw.get("reference_number") or raw.get("reference_no") or "").strip()
        if policy["requires_reference"] and not reference:
            frappe.throw(_("Reference number is required for Mode of Payment {0}.").format(mode))
        normalized.append(
            {
                "mode_of_payment": mode,
                "amount": amount,
                "account": policy["account"],
                "type": policy["type"],
                "default": 1 if policy["default"] else 0,
                "reference_no": reference,
                "allow_change": policy["allow_change"],
            }
        )
    if not normalized:
        frappe.throw(_("At least one POS payment is required."))
    tendered = flt(sum(row["amount"] for row in normalized), 2)
    allow_partial = bool(cint(profile.allow_partial_payment))
    if tendered + MONEY_TOLERANCE < flt(grand_total) and not allow_partial:
        frappe.throw(_("POS Profile requires full payment before checkout."))
    change = flt(max(tendered - flt(grand_total), 0), 2)
    if change > MONEY_TOLERANCE and not any(row["allow_change"] and row["type"] == "Cash" for row in normalized):
        frappe.throw(_("Over-tendered payment requires a Cash mode configured to allow change."))
    return normalized


def complete_sale(
    *,
    cart_items,
    tenders,
    customer: str | None = None,
    price_list: str | None = None,
    discount_type: str = "Amount",
    discount_value: float = 0,
    client_sale_id: str | None = None,
    allow_rate_override: bool = False,
    company: str | None = None,
):
    company = _company(company)
    profile = profile_for_user(company)
    if not active_opening(profile):
        frappe.throw(_("Open an ERPNext POS shift before completing a retail sale."))
    erpnext_selling._lock_company(company)
    existing = _existing_pos_sale(str(client_sale_id or ""), company)
    if existing:
        existing.flags.ledgix_duplicate_client_sale = True
        return existing

    invoice = build_pos_invoice(
        cart_items=cart_items,
        customer=customer,
        price_list=price_list,
        discount_type=discount_type,
        discount_value=discount_value,
        client_sale_id=client_sale_id,
        allow_rate_override=allow_rate_override,
        source="Ledgix POS Retail Checkout",
        company=company,
        pos_profile=profile.name,
    )
    normalized = _normalize_tenders(tenders, profile, flt(invoice.rounded_total or invoice.grand_total))
    invoice.set("payments", [])
    for row in normalized:
        values = {key: value for key, value in row.items() if key != "allow_change"}
        invoice.append("payments", values)
    cash_change_row = next((row for row in normalized if row["allow_change"] and row["type"] == "Cash"), None)
    if cash_change_row:
        invoice.account_for_change_amount = cash_change_row["account"]
    invoice.insert(ignore_permissions=True)
    invoice.submit()
    invoice.reload()
    invoice.flags.ledgix_duplicate_client_sale = False
    return invoice


def sale_result(invoice) -> dict:
    duplicate = bool(getattr(invoice.flags, "ledgix_duplicate_client_sale", False))
    return {
        "success": True,
        "sale": invoice.name,
        "invoice_number": invoice.name,
        "doctype": "POS Invoice",
        "docstatus": invoice.docstatus,
        "grand_total": flt(invoice.grand_total, 2),
        "paid_amount": flt(invoice.paid_amount, 2),
        "remaining_amount": max(flt(invoice.outstanding_amount, 2), 0),
        "change_amount": max(flt(invoice.change_amount, 2), 0),
        "payment_status": (
            "Paid"
            if abs(flt(invoice.outstanding_amount)) <= MONEY_TOLERANCE
            else "Partial"
            if flt(invoice.outstanding_amount) < flt(invoice.grand_total) - MONEY_TOLERANCE
            else "Unpaid"
        ),
        "payments": [row.mode_of_payment for row in invoice.payments],
        "print_mode": "POS",
        "print_doctype": "POS Invoice",
        "duplicate": duplicate,
        "financial_authority": "ERPNext POS Invoice",
    }


def _default_draft_payment(invoice, profile) -> None:
    methods = payment_methods(profile)
    default = next((row for row in methods if row["default"]), methods[0] if methods else None)
    if not default:
        frappe.throw(_("POS Profile {0} has no payment method.").format(profile.name))
    invoice.append(
        "payments",
        {
            "mode_of_payment": default["name"],
            "amount": flt(invoice.rounded_total or invoice.grand_total, 2),
            "account": default["account"],
            "type": default["type"],
            "default": 1,
        },
    )


def create_hold(
    *,
    cart_items,
    sale_channel: str = "Retail",
    customer: str | None = None,
    price_list: str | None = None,
    discount_type: str = "Amount",
    discount_value: float = 0,
    notes: str | None = None,
    company: str | None = None,
):
    company = _company(company)
    sale_channel = "B2B" if sale_channel == "B2B" else "Retail"
    hold_id = f"HOLD-{frappe.generate_hash(length=16).upper()}"
    safe_items = [
        {
            "item": row.get("item") or row.get("item_code"),
            "qty": row.get("qty") or row.get("quantity"),
            "serial_numbers": row.get("serial_numbers") or "",
        }
        for row in _raw_items(cart_items)
    ]
    payload = {
        "cart_items": safe_items,
        "sale_channel": sale_channel,
        "customer": str(customer or "").strip(),
        "price_list": str(price_list or "").strip(),
        "discount_type": discount_type,
        "discount_value": flt(discount_value),
        "notes": str(notes or "").strip(),
    }

    if sale_channel == "Retail":
        profile = profile_for_user(company)
        if not active_opening(profile):
            frappe.throw(_("Open an ERPNext POS shift before holding a retail sale."))
        invoice = build_pos_invoice(
            cart_items=safe_items,
            customer=customer,
            price_list=price_list,
            discount_type=discount_type,
            discount_value=discount_value,
            allow_rate_override=False,
            source="Ledgix POS Held Cart",
            company=company,
            pos_profile=profile.name,
        )
        invoice.custom_ledgix_hold_id = hold_id
        invoice.custom_ledgix_hold_status = "Held"
        invoice.custom_ledgix_hold_request_json = json.dumps(payload, sort_keys=True)
        _default_draft_payment(invoice, profile)
        invoice.insert(ignore_permissions=True)
    else:
        if not str(customer or "").strip():
            frappe.throw(_("Customer is required for a B2B held sale."))
        invoice = erpnext_selling.build_sales_invoice(
            customer=customer,
            items=safe_items,
            selling_price_list=price_list,
            sale_channel="B2B",
            discount_type=discount_type,
            discount_value=discount_value,
            allow_rate_override=False,
            update_stock=False,
            checkout_source="Ledgix B2B Held Cart",
            company=company,
        )
        invoice.custom_ledgix_hold_id = hold_id
        invoice.custom_ledgix_hold_status = "Held"
        invoice.custom_ledgix_hold_request_json = json.dumps(payload, sort_keys=True)
        invoice.insert(ignore_permissions=True)
    invoice.reload()
    return invoice


def _hold_docs() -> list:
    docs = []
    for doctype in ("POS Invoice", "Sales Invoice"):
        rows = frappe.get_all(
            doctype,
            filters={
                "docstatus": 0,
                "owner": frappe.session.user,
                "custom_ledgix_hold_status": "Held",
                "custom_ledgix_hold_id": ["is", "set"],
            },
            pluck="name",
            order_by="modified desc",
            limit_page_length=100,
        )
        docs.extend(frappe.get_doc(doctype, name) for name in rows)
    docs.sort(key=lambda doc: str(doc.modified or doc.creation), reverse=True)
    return docs


def list_holds() -> list[dict]:
    result = []
    for doc in _hold_docs():
        payload = frappe.parse_json(doc.get("custom_ledgix_hold_request_json") or "{}") or {}
        item_names = [row.item_name or row.item_code for row in doc.items[:3]]
        result.append(
            {
                "name": doc.custom_ledgix_hold_id,
                "doctype": doc.doctype,
                "native_document": doc.name,
                "sale_channel": payload.get("sale_channel") or ("Retail" if doc.doctype == "POS Invoice" else "B2B"),
                "customer": doc.customer,
                "price_list": doc.selling_price_list,
                "total": flt(doc.grand_total, 2),
                "items_preview": ", ".join(item_names),
                "modified": doc.modified,
            }
        )
    return result


def _hold_by_id(hold_id: str):
    hold_id = str(hold_id or "").strip()
    for doctype in ("POS Invoice", "Sales Invoice"):
        name = frappe.db.get_value(
            doctype,
            {
                "custom_ledgix_hold_id": hold_id,
                "custom_ledgix_hold_status": "Held",
                "docstatus": 0,
            },
            "name",
        )
        if name:
            doc = frappe.get_doc(doctype, name)
            if doc.owner != frappe.session.user and not set(frappe.get_roles()).intersection({"System Manager", "Ledgix Admin", "Ledgix Manager"}):
                frappe.throw(_("You cannot access another user's held sale."), frappe.PermissionError)
            return doc
    frappe.throw(_("Held sale {0} was not found.").format(hold_id))


def resume_hold(hold_id: str) -> dict:
    doc = _hold_by_id(hold_id)
    payload = frappe.parse_json(doc.get("custom_ledgix_hold_request_json") or "{}") or {}
    doc.db_set("custom_ledgix_hold_status", "Resumed", update_modified=True)
    items = payload.get("cart_items") or [
        {"item": row.item_code, "qty": flt(row.qty), "serial_numbers": row.get("serial_no") or ""}
        for row in doc.items
    ]
    price_list = payload.get("price_list") or doc.selling_price_list
    customer = payload.get("customer") or doc.customer
    sale_channel = payload.get("sale_channel") or ("Retail" if doc.doctype == "POS Invoice" else "B2B")
    priced = search_items(
        query=None,
        category=None,
        customer=customer,
        sale_channel=sale_channel,
        price_list=price_list,
        limit=200,
    )
    price_map = {row["item_code"]: row for row in priced["items"]}
    cart = []
    for row in items:
        item_code = erpnext_selling._resolve_item(row.get("item") or row.get("item_code"))
        priced_row = price_map.get(item_code) or {}
        cart.append(
            {
                "item": item_code,
                "item_name": priced_row.get("item_name") or frappe.db.get_value("Item", item_code, "item_name"),
                "tracking_type": priced_row.get("tracking_type") or "Normal",
                "serial_numbers": row.get("serial_numbers") or "",
                "qty": flt(row.get("qty") or 1),
                "rate": flt(priced_row.get("rate")),
            }
        )
    return {
        "success": True,
        "hold_id": hold_id,
        "sale_channel": sale_channel,
        "customer": customer,
        "price_list": price_list,
        "cart_items": cart,
        "discount_type": payload.get("discount_type") or "Amount",
        "discount_value": flt(payload.get("discount_value")),
        "total": flt(doc.grand_total, 2),
        "authority": f"ERPNext draft {doc.doctype}",
    }


def cancel_hold(hold_id: str):
    doc = _hold_by_id(hold_id)
    doc.db_set("custom_ledgix_hold_status", "Cancelled", update_modified=True)
    return doc


def _submitted_pos_invoice(value: str):
    value = str(value or "").strip()
    if not value:
        return None
    if frappe.db.exists("POS Invoice", value):
        doc = frappe.get_doc("POS Invoice", value)
        return doc if doc.docstatus == 1 and not cint(doc.is_return) else None
    name = frappe.db.get_value(
        "POS Invoice",
        {"custom_ledgix_client_sale_id": value, "docstatus": 1, "is_return": 0},
        "name",
    )
    return frappe.get_doc("POS Invoice", name) if name else None


def return_context(invoice) -> dict:
    returned = {}
    return_names = frappe.get_all(
        "POS Invoice",
        filters={"return_against": invoice.name, "is_return": 1, "docstatus": 1},
        pluck="name",
        limit_page_length=0,
    )
    if return_names:
        rows = frappe.get_all(
            "POS Invoice Item",
            filters={"parent": ["in", return_names], "parenttype": "POS Invoice"},
            fields=["pos_invoice_item", "item_code", "qty"],
            limit_page_length=0,
        )
        for row in rows:
            key = row.pos_invoice_item or row.item_code
            returned[key] = flt(returned.get(key)) + abs(flt(row.qty))

    items = []
    for row in invoice.items:
        already = flt(returned.get(row.name) or returned.get(row.item_code), 3)
        returnable = max(flt(row.qty) - already, 0)
        if returnable <= MONEY_TOLERANCE:
            continue
        items.append(
            {
                "item": row.item_code,
                "item_code": row.item_code,
                "original_sale_item_row": row.name,
                "pos_invoice_item": row.name,
                "item_name": row.item_name,
                "sold_qty": flt(row.qty),
                "already_returned_qty": already,
                "returnable_qty": returnable,
                "rate": flt(row.rate, 2),
                "amount": flt(row.amount, 2),
            }
        )
    return {
        "sale_id": invoice.name,
        "invoice_number": invoice.name,
        "customer": invoice.customer,
        "posting_date": invoice.posting_date,
        "grand_total": flt(invoice.grand_total, 2),
        "items": items,
        "sale_channel": "Retail",
        "financial_authority": "ERPNext POS Invoice",
    }


def get_return_context(sale_id: str) -> dict | None:
    invoice = _submitted_pos_invoice(sale_id)
    return return_context(invoice) if invoice else None


def create_return(
    *,
    original_sale: str,
    return_items,
    reason: str,
    client_return_id: str | None = None,
):
    invoice = _submitted_pos_invoice(original_sale)
    if not invoice:
        frappe.throw(_("Submitted ERPNext POS Invoice not found."))
    if not str(reason or "").strip():
        frappe.throw(_("Return reason is required."))
    profile = frappe.get_doc("POS Profile", invoice.pos_profile)
    if not active_opening(profile):
        frappe.throw(_("Open an ERPNext POS shift before posting a retail return."))

    requested = _parse(return_items) or []
    request_map = {}
    for raw in requested:
        qty = flt(raw.get("qty") or raw.get("quantity"))
        if qty <= 0:
            continue
        key = str(raw.get("original_sale_item_row") or raw.get("pos_invoice_item") or raw.get("item") or "").strip()
        if key:
            request_map[key] = qty
    if not request_map:
        frappe.throw(_("Select at least one item to return."))

    from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return

    return_doc = make_sales_return(invoice.name)
    selected = []
    for row in list(return_doc.items):
        source_key = str(row.pos_invoice_item or row.item_code or "").strip()
        qty = request_map.get(source_key)
        if qty is None:
            qty = request_map.get(row.item_code)
        if qty is None:
            continue
        max_qty = abs(flt(row.qty))
        if qty - max_qty > MONEY_TOLERANCE:
            frappe.throw(_("Return quantity exceeds ERPNext returnable quantity for {0}.").format(row.item_code))
        row.qty = -abs(qty)
        selected.append(row)
    if not selected:
        frappe.throw(_("Selected items do not match the original POS Invoice."))
    return_doc.set("items", selected)
    return_doc.custom_ledgix_sale_channel = "Retail"
    return_doc.custom_ledgix_checkout_source = "Ledgix POS Retail Return"
    return_doc.custom_ledgix_client_return_id = str(client_return_id or f"RET-{frappe.generate_hash(length=16)}").strip()
    return_doc.custom_ledgix_return_reason = str(reason).strip()
    return_doc.remarks = str(reason).strip()
    erpnext_tax_authority.apply_sales_tax_authority(return_doc)
    return_doc.insert(ignore_permissions=True)
    return_doc.submit()
    return_doc.reload()
    return return_doc


def return_result(doc) -> dict:
    return {
        "success": True,
        "return_id": doc.name,
        "return_invoice": doc.name,
        "original_sale": doc.return_against,
        "grand_total": flt(doc.grand_total, 2),
        "total_refund": abs(flt(doc.grand_total, 2)),
        "docstatus": doc.docstatus,
        "financial_authority": "ERPNext POS Invoice Return",
    }
