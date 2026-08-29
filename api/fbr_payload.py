import re

import frappe
from frappe.utils import cint, flt, getdate

from ledgix_saas.api.fbr_settings import get_fbr_control_state_internal, get_fbr_settings_internal
from ledgix_saas.api.security import has_any_role


# -----------------------------------------------------------------------------
# Document access
# -----------------------------------------------------------------------------

def get_sale_for_fbr(sale_name):
    if not sale_name or not frappe.db.exists("DocType", "Ledgix Sale"):
        return None
    if not frappe.db.exists("Ledgix Sale", sale_name):
        return None
    return frappe.get_doc("Ledgix Sale", sale_name)


def get_customer_for_fbr(customer_name):
    if not customer_name or not frappe.db.exists("DocType", "Ledgix Customer"):
        return None
    if not frappe.db.exists("Ledgix Customer", customer_name):
        return None
    return frappe.get_doc("Ledgix Customer", customer_name)


def get_invoice_tax_rows_for_fbr(sale_doc):
    if not sale_doc:
        return []
    rows = list(sale_doc.get("tax_details") or [])
    if rows:
        return rows

    # Compatibility fallback for old draft/test records that pre-date immutable
    # V2 tax snapshots. Finalized V2 sales always persist tax_details.
    from ledgix_saas.api.taxation import prepare_sale_tax_snapshot_for_doc

    prepared = prepare_sale_tax_snapshot_for_doc(sale_doc)
    return list(prepared.get("snapshot_rows") or [])


def get_return_for_fbr(return_name):
    if not return_name or not frappe.db.exists("DocType", "Ledgix Sales Return"):
        return None
    if not frappe.db.exists("Ledgix Sales Return", return_name):
        return None
    return frappe.get_doc("Ledgix Sales Return", return_name)


def get_return_tax_rows_for_fbr(return_doc):
    return list(return_doc.get("tax_details") or []) if return_doc else []


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _clean_text(value):
    return str(value or "").strip()


def _clean_identifier(value):
    return _clean_text(value).replace(" ", "").replace("-", "")


def _clean_hs_code(value):
    return _clean_text(value)


def _is_digits(value):
    return bool(value) and str(value).isdigit()


def _is_valid_hs_code(value):
    return bool(re.match(r"^[0-9]{2,8}(\.[0-9]{1,8})?$", value or ""))


def _is_missing(value):
    return value in (None, "")


def _money(value):
    return flt(value, 2)


def _format_invoice_date(value):
    return getdate(value).strftime("%Y-%m-%d") if value else ""


def _format_tax_rate(value):
    rate = flt(value)
    if rate == int(rate):
        return f"{int(rate)}%"
    return f"{rate:g}%"


def _fbr_rate_description(row):
    return _clean_text(row.get("fbr_rate_description")) or _format_tax_rate(row.get("tax_rate"))


def _charged_tax_amount(row):
    return flt(
        flt(row.get("tax_amount"))
        + flt(row.get("extra_tax"))
        + flt(row.get("further_tax"))
        + flt(row.get("fed_payable")),
        2,
    )


def _add_required_error(errors, label):
    errors.append(f"{label} is required for FBR payload.")


def _get_tax_profile_defaults():
    from ledgix_saas.api.taxation import get_tax_profile

    profile = get_tax_profile() or {}
    return {
        "default_buyer_type": profile.get("default_buyer_type") or "Unregistered",
        "province": profile.get("province") or "",
        "outlet_address": profile.get("outlet_address") or "",
    }


def _normalize_buyer_registration_type(value, default_buyer_type=None):
    registration_type = _clean_text(value) or _clean_text(default_buyer_type)
    if registration_type == "Consumer":
        return "Unregistered"
    return registration_type if registration_type in {"Registered", "Unregistered"} else ""


def _customer_address_fallback(customer_doc):
    if not customer_doc:
        return ""
    parts = [
        _clean_text(customer_doc.get("buyer_fbr_address")),
        _clean_text(customer_doc.get("address_line_1")),
        _clean_text(customer_doc.get("area")),
        _clean_text(customer_doc.get("city")),
    ]
    return ", ".join(part for part in parts if part)


def _validate_ntn_cnic(value, label, errors, warnings, required=False, production=False):
    cleaned = _clean_identifier(value)
    if not cleaned:
        if required:
            _add_required_error(errors, label)
        return
    if not _is_digits(cleaned):
        errors.append(f"{label} must contain digits only.")
        return
    if len(cleaned) not in (7, 9, 13):
        message = f"{label} should be 7 or 9 digit NTN, or 13 digit CNIC."
        (errors if production else warnings).append(message)


def _validate_province(value, label, errors):
    if not _clean_text(value):
        _add_required_error(errors, label)


def _validate_sro_fields(row, prefix, errors, warnings):
    schedule_number = _clean_text(row.get("sro_schedule_number"))
    item_serial_number = _clean_text(row.get("sro_item_serial_number"))
    if bool(schedule_number) != bool(item_serial_number):
        errors.append(
            f"{prefix} SRO schedule number and SRO item serial number must both be provided when either is used."
        )


def _require_fbr_view_permission(action="view"):
    if not has_any_role(("System Manager", "Ledgix Admin", "Ledgix Manager")):
        frappe.throw(
            f"Only System Manager, Ledgix Admin, or Ledgix Manager can {action} FBR payload data.",
            frappe.PermissionError,
        )


def _settings_summary(settings, control_state):
    return {
        "enabled": bool(control_state.get("enabled")),
        "mode": settings.get("mode") or "Disabled",
        "submit_trigger": settings.get("submit_trigger") or "Manual",
        "token_configured": bool(control_state.get("token_configured")),
    }


def _sale_summary(sale_doc=None, sale_name=None):
    if not sale_doc:
        return {
            "name": sale_name or "",
            "docstatus": None,
            "customer": "",
            "sale_date": None,
            "total_amount": 0,
            "tax_amount": 0,
            "grand_total": 0,
            "fbr_status": "",
        }
    return {
        "name": sale_doc.name,
        "docstatus": cint(sale_doc.docstatus),
        "customer": sale_doc.get("customer") or "",
        "sale_date": sale_doc.get("sale_date"),
        "total_amount": flt(sale_doc.get("total_amount"), 2),
        "tax_amount": flt(sale_doc.get("tax_amount"), 2),
        "grand_total": flt(sale_doc.get("grand_total"), 2),
        "fbr_status": sale_doc.get("fbr_status") or "",
    }


def _return_summary(return_doc=None, return_name=None):
    if not return_doc:
        return {
            "name": return_name or "",
            "docstatus": None,
            "customer": "",
            "original_sale": "",
            "return_date": None,
            "total_amount": 0,
            "tax_amount": 0,
            "grand_total": 0,
            "fbr_status": "",
        }
    return {
        "name": return_doc.name,
        "docstatus": cint(return_doc.docstatus),
        "customer": return_doc.get("customer") or "",
        "original_sale": return_doc.get("original_sale") or "",
        "return_date": return_doc.get("return_date"),
        "total_amount": flt(return_doc.get("total_amount"), 2),
        "tax_amount": flt(return_doc.get("tax_amount"), 2),
        "grand_total": flt(return_doc.get("grand_total"), 2),
        "fbr_status": return_doc.get("fbr_status") or "",
    }


# -----------------------------------------------------------------------------
# Seller / buyer snapshots
# -----------------------------------------------------------------------------

def build_fbr_seller_block():
    settings = get_fbr_settings_internal()
    return {
        "seller_ntn_cnic": settings.get("seller_ntn_cnic") or "",
        "seller_strn": "",
        "seller_business_name": settings.get("seller_business_name") or "",
        "seller_province": settings.get("seller_province") or "",
        "seller_address": settings.get("seller_address") or "",
        "seller_phone": "",
        "seller_email": "",
    }


def build_fbr_seller_block_from_sale(sale_doc):
    if not sale_doc:
        return build_fbr_seller_block()

    snapshot_fields = (
        "seller_name_snapshot",
        "seller_address_snapshot",
        "seller_province_snapshot",
        "seller_ntn_cnic_snapshot",
        "seller_strn_snapshot",
        "seller_phone_snapshot",
        "seller_email_snapshot",
    )
    if not any(_clean_text(sale_doc.get(fieldname)) for fieldname in snapshot_fields):
        return build_fbr_seller_block()

    return {
        "seller_ntn_cnic": sale_doc.get("seller_ntn_cnic_snapshot") or "",
        "seller_strn": sale_doc.get("seller_strn_snapshot") or "",
        "seller_business_name": sale_doc.get("seller_name_snapshot") or "",
        "seller_province": sale_doc.get("seller_province_snapshot") or "",
        "seller_address": sale_doc.get("seller_address_snapshot") or "",
        "seller_phone": sale_doc.get("seller_phone_snapshot") or "",
        "seller_email": sale_doc.get("seller_email_snapshot") or "",
    }


def build_fbr_buyer_block(customer_doc):
    defaults = _get_tax_profile_defaults()
    if not customer_doc:
        return {
            "buyer_ntn_cnic": "",
            "buyer_strn": "",
            "buyer_registration_type": "Unregistered",
            "buyer_province": defaults.get("province") or "",
            "buyer_fbr_address": defaults.get("outlet_address") or "",
            "buyer_business_name": "Walk-in Customer",
        }
    registration_type = _normalize_buyer_registration_type(
        customer_doc.get("buyer_registration_type"), defaults.get("default_buyer_type")
    )
    return {
        "buyer_ntn_cnic": customer_doc.get("buyer_ntn_cnic") or "",
        "buyer_strn": customer_doc.get("buyer_strn") or "",
        "buyer_registration_type": registration_type,
        "buyer_province": customer_doc.get("buyer_province") or defaults.get("province") or "",
        "buyer_fbr_address": _customer_address_fallback(customer_doc) or defaults.get("outlet_address") or "",
        "buyer_business_name": _clean_text(customer_doc.get("customer_name") or customer_doc.name),
    }


def build_fbr_buyer_block_from_sale(sale_doc):
    defaults = _get_tax_profile_defaults()
    if not sale_doc:
        return build_fbr_buyer_block(None)

    snapshot_present = any(
        _clean_text(sale_doc.get(fieldname))
        for fieldname in (
            "buyer_name_snapshot",
            "buyer_ntn_cnic_snapshot",
            "buyer_strn_snapshot",
            "buyer_registration_type_snapshot",
            "buyer_province_snapshot",
            "buyer_address_snapshot",
        )
    )
    if not snapshot_present:
        return build_fbr_buyer_block(get_customer_for_fbr(sale_doc.get("customer")))

    registration_type = _normalize_buyer_registration_type(
        sale_doc.get("buyer_registration_type_snapshot"), defaults.get("default_buyer_type")
    )
    return {
        "buyer_ntn_cnic": sale_doc.get("buyer_ntn_cnic_snapshot") or "",
        "buyer_strn": sale_doc.get("buyer_strn_snapshot") or "",
        "buyer_registration_type": registration_type or "Unregistered",
        "buyer_province": sale_doc.get("buyer_province_snapshot") or defaults.get("province") or "",
        "buyer_fbr_address": sale_doc.get("buyer_address_snapshot") or defaults.get("outlet_address") or "",
        "buyer_business_name": sale_doc.get("buyer_name_snapshot") or sale_doc.get("customer") or "Walk-in Customer",
    }


# -----------------------------------------------------------------------------
# Readiness validation
# -----------------------------------------------------------------------------

def _validate_tax_rows(rows, errors, warnings, mode, prefix_label="Tax row"):
    production_mode = mode == "Production"
    if not rows:
        errors.append("Tax snapshot rows are required for FBR payload.")
        return

    for index, row in enumerate(rows, start=1):
        prefix = f"{prefix_label} {index}"
        if not row.get("item"):
            _add_required_error(errors, f"{prefix} item")
        qty = flt(row.get("qty") or row.get("returned_qty"))
        if qty <= 0:
            errors.append(f"{prefix} qty must be greater than zero.")
        for fieldname, label in (
            ("taxable_amount", "taxable amount"),
            ("tax_rate", "tax rate"),
            ("tax_amount", "tax amount"),
            ("net_amount", "net amount"),
            ("hs_code", "HS code"),
            ("uom_for_fbr", "UOM for FBR"),
            ("sales_type", "sales type"),
        ):
            if _is_missing(row.get(fieldname)):
                _add_required_error(errors, f"{prefix} {label}")

        for fieldname, label in (
            ("sales_tax_withheld_at_source", "sales tax withheld at source"),
            ("extra_tax", "extra tax"),
            ("further_tax", "further tax"),
            ("fed_payable", "FED payable"),
        ):
            if flt(row.get(fieldname)) < 0:
                errors.append(f"{prefix} {label} cannot be negative.")

        hs_code = _clean_hs_code(row.get("hs_code"))
        if hs_code and not _is_valid_hs_code(hs_code):
            errors.append(f"{prefix} HS code format is invalid.")
        elif hs_code and not 4 <= len(hs_code.replace(".", "")) <= 8:
            message = f"{prefix} HS code should be 4 to 8 digits."
            (errors if production_mode else warnings).append(message)

        if mode == "Sandbox" and not row.get("scenario_id"):
            _add_required_error(errors, f"{prefix} scenario ID")

        if row.get("tax_basis") == "Notified Retail Price" and flt(row.get("notified_retail_price")) <= 0:
            errors.append(f"{prefix} notified retail price is required for Third Schedule tax basis.")
        _validate_sro_fields(row, prefix, errors, warnings)


def _validate_seller_block(seller, errors, warnings, production_mode=False):
    _validate_ntn_cnic(
        seller.get("seller_ntn_cnic"),
        "Seller NTN/CNIC",
        errors,
        warnings,
        required=True,
        production=production_mode,
    )
    if not _clean_text(seller.get("seller_business_name")):
        _add_required_error(errors, "Seller business name")
    _validate_province(seller.get("seller_province"), "Seller province", errors)
    if not _clean_text(seller.get("seller_address")):
        _add_required_error(errors, "Seller address")


def _validate_buyer_block(buyer, errors, warnings, production_mode=False):
    registration_type = _normalize_buyer_registration_type(buyer.get("buyer_registration_type"))
    if not registration_type:
        errors.append("Buyer registration type must be Registered or Unregistered.")
    if not _clean_text(buyer.get("buyer_business_name")):
        _add_required_error(errors, "Buyer business name")
    _validate_province(buyer.get("buyer_province"), "Buyer province", errors)
    if not _clean_text(buyer.get("buyer_fbr_address")):
        _add_required_error(errors, "Buyer FBR address")
    if registration_type == "Registered":
        _validate_ntn_cnic(
            buyer.get("buyer_ntn_cnic"),
            "Buyer NTN/CNIC",
            errors,
            warnings,
            required=True,
            production=production_mode,
        )
        if not _clean_text(buyer.get("buyer_strn")):
            warnings.append("Registered buyer has no STRN.")


def _unique_scenario_ids(rows):
    ids = []
    for row in rows or []:
        scenario_id = _clean_text(row.get("scenario_id"))
        if scenario_id and scenario_id not in ids:
            ids.append(scenario_id)
    return ids


def _validate_single_sandbox_scenario(rows, errors):
    scenario_ids = _unique_scenario_ids(rows)
    if not scenario_ids:
        _add_required_error(errors, "Scenario ID")
    elif len(scenario_ids) > 1:
        errors.append(
            "Sandbox invoice contains multiple scenario IDs. FBR scenario testing requires one scenario per invoice."
        )
    return scenario_ids


def _validate_sale_fbr_readiness_internal(sale_name):
    errors, warnings = [], []
    settings = get_fbr_settings_internal()
    control_state = get_fbr_control_state_internal()
    sale_doc = get_sale_for_fbr(sale_name)

    if not sale_doc:
        errors.append(f"Ledgix Sale {sale_name or ''} was not found.")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "sale": _sale_summary(sale_name=sale_name),
            "settings": _settings_summary(settings, control_state),
        }

    if cint(sale_doc.docstatus) == 0:
        errors.append("Draft sale cannot be used for FBR payload.")
    elif cint(sale_doc.docstatus) == 2:
        errors.append("Cancelled sale cannot be used for FBR payload.")

    mode = settings.get("mode") or "Disabled"
    production_mode = mode == "Production"
    seller = build_fbr_seller_block_from_sale(sale_doc)
    _validate_seller_block(seller, errors, warnings, production_mode=production_mode)

    if mode in {"Sandbox", "Production"} and settings.get("enabled"):
        token_key = "sandbox_token_configured" if mode == "Sandbox" else "production_token_configured"
        if not settings.get(token_key):
            errors.append(f"{mode} FBR token is not configured.")

    buyer = build_fbr_buyer_block_from_sale(sale_doc)
    _validate_buyer_block(buyer, errors, warnings, production_mode=production_mode)

    tax_rows = get_invoice_tax_rows_for_fbr(sale_doc)
    if tax_rows:
        invoice_tax_total = flt(sum(_charged_tax_amount(row) for row in tax_rows), 2)
        net_total = flt(sum(flt(row.get("net_amount")) for row in tax_rows), 2)
        if abs(invoice_tax_total - flt(sale_doc.get("tax_amount"), 2)) > 0.05:
            errors.append("Sale tax_amount does not match immutable FBR tax component total.")
        if abs(net_total - flt(sale_doc.get("grand_total"), 2)) > 0.05:
            errors.append("Sale grand_total does not match tax_details net_amount total.")
    _validate_tax_rows(tax_rows, errors, warnings, mode)
    if mode == "Sandbox":
        _validate_single_sandbox_scenario(tax_rows, errors)

    if production_mode:
        warnings.append("Production mode is selected. Verify credentials and FBR master data before submission.")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "sale": _sale_summary(sale_doc=sale_doc),
        "settings": _settings_summary(settings, control_state),
    }


@frappe.whitelist()
def validate_sale_fbr_readiness(sale_name):
    _require_fbr_view_permission("validate")
    return _validate_sale_fbr_readiness_internal(sale_name)


# -----------------------------------------------------------------------------
# Sale payload builders
# -----------------------------------------------------------------------------

def _item_description(item):
    if not item:
        return ""
    if frappe.db.exists("DocType", "Ledgix Item") and frappe.db.exists("Ledgix Item", item):
        return frappe.db.get_value("Ledgix Item", item, "item_name") or item
    return item


def build_fbr_item_rows(sale_doc):
    items = []
    for index, row in enumerate(get_invoice_tax_rows_for_fbr(sale_doc), start=1):
        item = row.get("item") or ""
        items.append({
            "line_no": index,
            "item": item,
            "product_description": _item_description(item),
            "qty": flt(row.get("qty"), 2),
            "rate": flt(row.get("rate"), 2),
            "gross_amount": flt(row.get("gross_amount"), 2),
            "discount_amount": flt(row.get("discount_amount"), 2),
            "taxable_amount": flt(row.get("taxable_amount"), 2),
            "tax_rate": flt(row.get("tax_rate"), 2),
            "fbr_rate_description": _fbr_rate_description(row),
            "tax_amount": flt(row.get("tax_amount"), 2),
            "sales_tax_withheld_at_source": flt(row.get("sales_tax_withheld_at_source"), 2),
            "extra_tax": flt(row.get("extra_tax"), 2),
            "further_tax": flt(row.get("further_tax"), 2),
            "fed_payable": flt(row.get("fed_payable"), 2),
            "net_amount": flt(row.get("net_amount"), 2),
            "price_includes_tax": 1 if row.get("price_includes_tax") else 0,
            "tax_category": row.get("tax_category") or "",
            "tax_basis": row.get("tax_basis") or "Transaction Value",
            "notified_retail_price": flt(row.get("notified_retail_price"), 2),
            "hs_code": row.get("hs_code") or "",
            "uom_for_fbr": row.get("uom_for_fbr") or "",
            "sales_type": row.get("sales_type") or "",
            "scenario_id": row.get("scenario_id") or "",
            "sro_schedule_number": row.get("sro_schedule_number") or "",
            "sro_item_serial_number": row.get("sro_item_serial_number") or "",
        })
    return items


def _payload_totals(items, sale_doc):
    return {
        "gross_amount": flt(sum(flt(row.get("gross_amount")) for row in items), 2),
        "taxable_amount": flt(sum(flt(row.get("taxable_amount")) for row in items), 2),
        "tax_amount": flt(sum(_charged_tax_amount(row) for row in items), 2),
        "net_amount": flt(sum(flt(row.get("net_amount")) for row in items), 2),
        "grand_total": flt(sale_doc.get("grand_total"), 2) if sale_doc else 0,
    }


def build_internal_fbr_payload(sale_doc):
    settings = get_fbr_settings_internal()
    item_rows = build_fbr_item_rows(sale_doc) if sale_doc else []
    return {
        "source": "Ledgix",
        "payload_version": "2.1",
        "environment": settings.get("mode") or "Disabled",
        "invoice_type": "Sale Invoice",
        "sale": {
            "name": sale_doc.name if sale_doc else "",
            "invoice_number": (sale_doc.get("invoice_number") or sale_doc.name) if sale_doc else "",
            "sale_date": sale_doc.get("sale_date") if sale_doc else None,
            "docstatus": cint(sale_doc.docstatus) if sale_doc else None,
            "customer": sale_doc.get("customer") if sale_doc else "",
            "sale_channel": sale_doc.get("sale_channel") if sale_doc else "",
            "price_list": sale_doc.get("price_list") if sale_doc else "",
            "total_amount": flt(sale_doc.get("total_amount"), 2) if sale_doc else 0,
            "tax_amount": flt(sale_doc.get("tax_amount"), 2) if sale_doc else 0,
            "grand_total": flt(sale_doc.get("grand_total"), 2) if sale_doc else 0,
        },
        "seller": build_fbr_seller_block_from_sale(sale_doc),
        "buyer": build_fbr_buyer_block_from_sale(sale_doc),
        "items": item_rows,
        "totals": _payload_totals(item_rows, sale_doc),
    }


def _official_item_payload(row, qty_field="qty", discount_field="discount_amount"):
    return {
        "hsCode": _clean_hs_code(row.get("hs_code")),
        "productDescription": _item_description(row.get("item")),
        "rate": _fbr_rate_description(row),
        "uoM": row.get("uom_for_fbr") or "",
        "quantity": flt(row.get(qty_field), 2),
        "totalValues": _money(row.get("net_amount")),
        "valueSalesExcludingST": _money(row.get("taxable_amount")),
        "fixedNotifiedValueOrRetailPrice": _money(row.get("notified_retail_price"))
        if row.get("tax_basis") == "Notified Retail Price" else 0.00,
        "salesTaxApplicable": _money(row.get("tax_amount")),
        "salesTaxWithheldAtSource": _money(row.get("sales_tax_withheld_at_source")),
        "extraTax": _money(row.get("extra_tax")),
        "furtherTax": _money(row.get("further_tax")),
        "sroScheduleNo": row.get("sro_schedule_number") or "",
        "fedPayable": _money(row.get("fed_payable")),
        "discount": _money(row.get(discount_field)),
        "saleType": row.get("sales_type") or "",
        "sroItemSerialNo": row.get("sro_item_serial_number") or "",
    }


def build_official_sale_invoice_payload(sale_doc):
    if not sale_doc:
        return {}
    settings = get_fbr_settings_internal()
    seller = build_fbr_seller_block_from_sale(sale_doc)
    buyer = build_fbr_buyer_block_from_sale(sale_doc)
    tax_rows = get_invoice_tax_rows_for_fbr(sale_doc)

    payload = {
        "invoiceType": "Sale Invoice",
        "invoiceDate": _format_invoice_date(sale_doc.get("sale_date")),
        "sellerNTNCNIC": _clean_identifier(seller.get("seller_ntn_cnic")),
        "sellerBusinessName": seller.get("seller_business_name") or "",
        "sellerProvince": seller.get("seller_province") or "",
        "sellerAddress": seller.get("seller_address") or "",
        "buyerNTNCNIC": _clean_identifier(buyer.get("buyer_ntn_cnic")),
        "buyerBusinessName": buyer.get("buyer_business_name") or "",
        "buyerProvince": buyer.get("buyer_province") or "",
        "buyerAddress": buyer.get("buyer_fbr_address") or "",
        "buyerRegistrationType": buyer.get("buyer_registration_type") or "",
        "invoiceRefNo": "",
        "items": [_official_item_payload(row) for row in tax_rows],
    }
    scenario_ids = _unique_scenario_ids(tax_rows)
    if settings.get("mode") == "Sandbox" and len(scenario_ids) == 1:
        payload["scenarioId"] = scenario_ids[0]
    return payload


def _build_sale_invoice_payload_internal(sale_name):
    validation = _validate_sale_fbr_readiness_internal(sale_name)
    sale_doc = get_sale_for_fbr(sale_name)
    official_payload = build_official_sale_invoice_payload(sale_doc)
    internal_payload = build_internal_fbr_payload(sale_doc)
    validation["valid"] = not validation.get("errors")
    return {"validation": validation, "payload": official_payload, "internal_payload": internal_payload}


@frappe.whitelist()
def build_sale_invoice_payload(sale_name):
    _require_fbr_view_permission("view")
    return _build_sale_invoice_payload_internal(sale_name)


# -----------------------------------------------------------------------------
# Sales return / electronic note
# -----------------------------------------------------------------------------

def _validate_return_fbr_readiness_internal(return_name):
    errors, warnings = [], []
    settings = get_fbr_settings_internal()
    control_state = get_fbr_control_state_internal()
    return_doc = get_return_for_fbr(return_name)
    if not return_doc:
        errors.append(f"Ledgix Sales Return {return_name or ''} was not found.")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "return_doc": _return_summary(return_name=return_name),
            "settings": _settings_summary(settings, control_state),
        }

    if cint(return_doc.docstatus) == 0:
        errors.append("Draft sales return cannot be used for FBR payload.")
    elif cint(return_doc.docstatus) == 2:
        errors.append("Cancelled sales return cannot be used for FBR payload.")
    if not return_doc.get("original_sale"):
        _add_required_error(errors, "Original sale")
    if not return_doc.get("return_date"):
        _add_required_error(errors, "Return date")
    if not _clean_text(return_doc.get("return_reason")):
        _add_required_error(errors, "Return reason")

    original_sale = get_sale_for_fbr(return_doc.get("original_sale"))
    original_fbr_invoice = _clean_text(original_sale.get("fbr_invoice_number")) if original_sale else ""
    if return_doc.get("original_sale") and not original_sale:
        errors.append(f"Original sale {return_doc.get('original_sale')} was not found.")

    mode = settings.get("mode") or "Disabled"
    if original_sale and mode in {"Sandbox", "Production"} and not original_fbr_invoice:
        errors.append("Original sale must have an FBR invoice number before validating or posting an electronic note.")

    if original_sale and return_doc.get("return_date") and original_sale.get("sale_date"):
        original_date = getdate(original_sale.get("sale_date"))
        note_date = getdate(return_doc.get("return_date"))
        age_days = (note_date - original_date).days
        if age_days < 0:
            errors.append("Return date cannot be earlier than the original invoice date.")
        elif age_days > 180:
            errors.append("FBR electronic note date cannot be more than 180 days after the original invoice date.")

    if original_sale:
        seller = build_fbr_seller_block_from_sale(original_sale)
        buyer = build_fbr_buyer_block_from_sale(original_sale)
        _validate_seller_block(seller, errors, warnings, production_mode=(mode == "Production"))
        _validate_buyer_block(buyer, errors, warnings, production_mode=(mode == "Production"))

    tax_rows = get_return_tax_rows_for_fbr(return_doc)
    if tax_rows:
        invoice_tax_total = flt(sum(_charged_tax_amount(row) for row in tax_rows), 2)
        net_total = flt(sum(flt(row.get("net_amount")) for row in tax_rows), 2)
        if abs(invoice_tax_total - flt(return_doc.get("tax_amount"), 2)) > 0.05:
            errors.append("Return tax_amount does not match immutable FBR tax component total.")
        if abs(net_total - flt(return_doc.get("grand_total"), 2)) > 0.05:
            errors.append("Return grand_total does not match tax_details net_amount total.")

    _validate_tax_rows(tax_rows, errors, warnings, mode, "Return tax row")
    if mode == "Sandbox":
        _validate_single_sandbox_scenario(tax_rows, errors)

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "return_doc": _return_summary(return_doc=return_doc),
        "original_sale_fbr_invoice_number": original_fbr_invoice,
        "settings": _settings_summary(settings, control_state),
    }


def build_official_return_invoice_payload(return_doc):
    if not return_doc:
        return {}
    settings = get_fbr_settings_internal()
    original_sale = get_sale_for_fbr(return_doc.get("original_sale"))
    seller = build_fbr_seller_block_from_sale(original_sale)
    buyer = build_fbr_buyer_block_from_sale(original_sale)
    tax_rows = get_return_tax_rows_for_fbr(return_doc)

    # Current FBR v1.12 material contains credit-note validation rules while some
    # tables describe Debit Note only. Preserve the existing Credit Note contract
    # until the client's assigned Sandbox confirms the exact accepted note type.
    payload = {
        "invoiceType": "Credit Note",
        "invoiceDate": _format_invoice_date(return_doc.get("return_date")),
        "sellerNTNCNIC": _clean_identifier(seller.get("seller_ntn_cnic")),
        "sellerBusinessName": seller.get("seller_business_name") or "",
        "sellerProvince": seller.get("seller_province") or "",
        "sellerAddress": seller.get("seller_address") or "",
        "buyerNTNCNIC": _clean_identifier(buyer.get("buyer_ntn_cnic")),
        "buyerBusinessName": buyer.get("buyer_business_name") or "",
        "buyerProvince": buyer.get("buyer_province") or "",
        "buyerAddress": buyer.get("buyer_fbr_address") or "",
        "buyerRegistrationType": buyer.get("buyer_registration_type") or "",
        "invoiceRefNo": _clean_text(original_sale.get("fbr_invoice_number")) if original_sale else "",
        "reason": _clean_text(return_doc.get("return_reason")),
        "reasonRemarks": _clean_text(return_doc.get("fbr_reason_remarks")),
        "items": [_official_item_payload(row, qty_field="returned_qty", discount_field="discount_amount") for row in tax_rows],
    }
    scenario_ids = _unique_scenario_ids(tax_rows)
    if settings.get("mode") == "Sandbox" and len(scenario_ids) == 1:
        payload["scenarioId"] = scenario_ids[0]
    return payload


def _build_return_invoice_payload_internal(return_name):
    validation = _validate_return_fbr_readiness_internal(return_name)
    return_doc = get_return_for_fbr(return_name)
    payload = build_official_return_invoice_payload(return_doc)
    validation["valid"] = not validation.get("errors")
    return {"validation": validation, "payload": payload}


@frappe.whitelist()
def build_return_invoice_payload(return_name):
    _require_fbr_view_permission("view")
    return _build_return_invoice_payload_internal(return_name)
