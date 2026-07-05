import re

import frappe
from frappe.utils import cint, flt, getdate, nowdate

from ledgix_saas.api.security import has_any_role
from ledgix_saas.api.fbr_settings import get_fbr_control_state_internal, get_fbr_settings_internal


# Document access
def get_sale_for_fbr(sale_name):
    if not sale_name:
        return None

    if not frappe.db.exists("DocType", "Ledgix Sale"):
        return None

    if not frappe.db.exists("Ledgix Sale", sale_name):
        return None

    return frappe.get_doc("Ledgix Sale", sale_name)


def get_customer_for_fbr(customer_name):
    if not customer_name:
        return None

    if not frappe.db.exists("DocType", "Ledgix Customer"):
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

    from ledgix_saas.api.taxation import prepare_sale_tax_snapshot_for_doc

    prepared = prepare_sale_tax_snapshot_for_doc(sale_doc)
    return list(prepared.get("snapshot_rows") or [])


# Validation
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


def _settings_summary(settings, control_state):
    return {
        "enabled": bool(control_state.get("enabled")),
        "mode": settings.get("mode") or "Disabled",
        "submit_trigger": settings.get("submit_trigger") or "Manual",
        "token_configured": bool(control_state.get("token_configured")),
    }


def _add_required_error(errors, label):
    errors.append(f"{label} is required for FBR payload.")


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
        if production:
            errors.append(message)
        else:
            warnings.append(message)


def _validate_province(value, label, errors):
    if not _clean_text(value):
        _add_required_error(errors, label)


def _normalize_buyer_registration_type(value, default_buyer_type=None):
    registration_type = _clean_text(value) or _clean_text(default_buyer_type)
    if registration_type == "Consumer":
        return "Unregistered"
    if registration_type not in {"Registered", "Unregistered"}:
        return ""
    return registration_type


def _customer_address_fallback(customer_doc):
    if not customer_doc:
        return ""

    parts = [
        _clean_text(customer_doc.get("buyer_fbr_address")),
        _clean_text(customer_doc.get("address_line_1")),
        _clean_text(customer_doc.get("area")),
        _clean_text(customer_doc.get("city")),
    ]
    return ", ".join([part for part in parts if part])


def _get_tax_profile_defaults():
    from ledgix_saas.api.taxation import get_tax_profile

    profile = get_tax_profile() or {}
    return {
        "default_buyer_type": profile.get("default_buyer_type") or "Unregistered",
        "province": profile.get("province") or "",
        "outlet_address": profile.get("outlet_address") or "",
    }


def _validate_sro_fields(row, prefix, errors, warnings):
    schedule_number = _clean_text(row.get("sro_schedule_number"))
    item_serial_number = _clean_text(row.get("sro_item_serial_number"))

    if bool(schedule_number) != bool(item_serial_number):
        warnings.append(
            f"{prefix} SRO schedule number and SRO item serial number should both "
            "be provided when either is used."
        )


def _require_fbr_view_permission(action="view"):
    if not has_any_role(("System Manager", "Ledgix Admin", "Ledgix Manager")):
        frappe.throw(f"Only System Manager, Ledgix Admin, or Ledgix Manager can {action} FBR payload data.", frappe.PermissionError)


def _validate_sale_fbr_readiness_internal(sale_name):
    errors = []
    warnings = []
    settings = get_fbr_settings_internal()
    control_state = get_fbr_control_state_internal()
    sale_doc = get_sale_for_fbr(sale_name)
    customer_doc = None

    if not sale_doc:
        errors.append(f"Ledgix Sale {sale_name or ''} was not found.")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
            "sale": _sale_summary(sale_name=sale_name),
            "settings": _settings_summary(settings, control_state),
        }

    docstatus = cint(sale_doc.docstatus)
    if docstatus == 0:
        errors.append("Draft sale cannot be used for FBR payload.")
    elif docstatus == 2:
        errors.append("Cancelled sale cannot be used for FBR payload.")

    if not sale_doc.get("customer"):
        _add_required_error(errors, "Sale customer")
    else:
        customer_doc = get_customer_for_fbr(sale_doc.get("customer"))
        if not customer_doc:
            errors.append(f"Ledgix Customer {sale_doc.get('customer')} was not found.")

    mode = settings.get("mode") or "Disabled"
    production_mode = mode == "Production"

    _validate_ntn_cnic(
        settings.get("seller_ntn_cnic"),
        "Seller NTN/CNIC",
        errors,
        warnings,
        required=True,
        production=production_mode,
    )

    seller_business_name = _clean_text(settings.get("seller_business_name"))
    if not seller_business_name:
        _add_required_error(errors, "Seller business name")
    elif len(seller_business_name) < 3:
        errors.append("Seller business name must be at least 3 characters.")

    _validate_province(settings.get("seller_province"), "Seller province", errors)

    seller_address = _clean_text(settings.get("seller_address"))
    if not seller_address:
        _add_required_error(errors, "Seller address")
    elif len(seller_address) < 5:
        errors.append("Seller address must be at least 5 characters.")

    if mode in {"Sandbox", "Production"} and settings.get("enabled"):
        token_key = (
            "sandbox_token_configured"
            if mode == "Sandbox"
            else "production_token_configured"
        )
        if not settings.get(token_key):
            errors.append(f"{mode} FBR token is not configured.")

    if production_mode:
        warnings.append(
            "Production mode is selected. Verify credentials and readiness before "
            "enabling submission."
        )
        warnings.append(
            "Reference API sync/check is not automated yet. Validate master data before production submission."
        )
        warnings.append("FBR QR/logo printing not fully configured.")

    if settings.get("submit_trigger") == "On Submit":
        warnings.append("Automatic Sale submission queues FBR work after sale commit.")

    if settings.get("block_sale_if_fbr_fails"):
        warnings.append(
            "Block Sale If FBR Readiness Fails only blocks submit when readiness validation fails before commit."
        )

    if customer_doc:
        tax_defaults = _get_tax_profile_defaults()
        default_buyer_type = tax_defaults.get("default_buyer_type") or "Unregistered"
        registration_type = _normalize_buyer_registration_type(
            customer_doc.get("buyer_registration_type"),
            default_buyer_type,
        )
        is_consumer_sale = default_buyer_type == "Consumer"

        if not registration_type:
            errors.append("Buyer registration type must be Registered or Unregistered.")
        buyer_name = _clean_text(customer_doc.get("customer_name") or customer_doc.name)
        if not buyer_name:
            if is_consumer_sale:
                buyer_name = "Walk-in Customer"
            else:
                _add_required_error(errors, "Buyer business name")

        buyer_province = _clean_text(customer_doc.get("buyer_province")) or _clean_text(
            tax_defaults.get("province")
        )
        if not buyer_province and is_consumer_sale:
            buyer_province = _clean_text(tax_defaults.get("province"))
        _validate_province(buyer_province, "Buyer province", errors)

        buyer_address = _customer_address_fallback(customer_doc) or _clean_text(
            tax_defaults.get("outlet_address")
        )
        if not buyer_address and is_consumer_sale:
            buyer_address = _clean_text(tax_defaults.get("outlet_address")) or "Walk-in Customer"
        if not buyer_address:
            _add_required_error(errors, "Buyer FBR address")
        elif len(buyer_address) < 5 and not is_consumer_sale:
            errors.append("Buyer FBR address must be at least 5 characters.")

        if registration_type == "Registered":
            _validate_ntn_cnic(
                customer_doc.get("buyer_ntn_cnic"),
                "Buyer NTN/CNIC",
                errors,
                warnings,
                required=True,
                production=production_mode,
            )
            if not _clean_text(customer_doc.get("buyer_strn")):
                warnings.append("Registered buyer has no STRN.")
        elif registration_type == "Unregistered":
            if not customer_doc.get("buyer_ntn_cnic"):
                warnings.append("Unregistered buyer has no NTN/CNIC.")

    tax_rows = get_invoice_tax_rows_for_fbr(sale_doc)
    if not tax_rows:
        errors.append("Sale tax_details must contain at least one immutable tax snapshot row.")
    else:
        tax_total = flt(sum(flt(row.get("tax_amount")) for row in tax_rows), 2)
        net_total = flt(sum(flt(row.get("net_amount")) for row in tax_rows), 2)

        if abs(tax_total - flt(sale_doc.get("tax_amount"), 2)) > 0.05:
            errors.append("Sale tax_amount does not match tax_details tax_amount total.")
        if abs(net_total - flt(sale_doc.get("grand_total"), 2)) > 0.05:
            errors.append("Sale grand_total does not match tax_details net_amount total.")

    for index, row in enumerate(tax_rows, start=1):
        prefix = f"Tax row {index}"
        if not row.get("item"):
            _add_required_error(errors, f"{prefix} item")
        if flt(row.get("qty")) <= 0:
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
            value = row.get(fieldname)
            if _is_missing(value):
                _add_required_error(errors, f"{prefix} {label}")

        hs_code = _clean_hs_code(row.get("hs_code"))
        if hs_code:
            if not _is_valid_hs_code(hs_code):
                errors.append(f"{prefix} HS code format is invalid.")
            elif len(hs_code.replace(".", "")) < 4 or len(hs_code.replace(".", "")) > 8:
                message = f"{prefix} HS code should be 4 to 8 digits."
                if production_mode:
                    errors.append(message)
                else:
                    warnings.append(message)

        if mode == "Sandbox" and not row.get("scenario_id"):
            _add_required_error(errors, f"{prefix} scenario ID")
        elif mode in {"Disabled", "Manual Only", "Paused", "Production"} and not row.get("scenario_id"):
            warnings.append(f"{prefix} scenario ID is not configured.")

        if row.get("tax_rate") not in (None, "") and flt(row.get("tax_rate")) == 0:
            warnings.append(f"{prefix} tax rate is zero.")
        if (
            row.get("tax_amount") not in (None, "")
            and flt(row.get("tax_amount")) == 0
            and flt(row.get("tax_rate")) > 0
        ):
            warnings.append(f"{prefix} tax amount is zero.")
        _validate_sro_fields(row, prefix, errors, warnings)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "sale": _sale_summary(sale_doc=sale_doc),
        "settings": _settings_summary(settings, control_state),
    }


@frappe.whitelist()
def validate_sale_fbr_readiness(sale_name):
    _require_fbr_view_permission("validate")
    return _validate_sale_fbr_readiness_internal(sale_name)


# Payload builders
def _item_description(item):
    if not item:
        return ""

    if frappe.db.exists("DocType", "Ledgix Item") and frappe.db.exists("Ledgix Item", item):
        return frappe.db.get_value("Ledgix Item", item, "item_name") or item

    return item


def build_fbr_seller_block():
    settings = get_fbr_settings_internal()
    return {
        "seller_ntn_cnic": settings.get("seller_ntn_cnic") or "",
        "seller_business_name": settings.get("seller_business_name") or "",
        "seller_province": settings.get("seller_province") or "",
        "seller_address": settings.get("seller_address") or "",
    }


def build_fbr_buyer_block(customer_doc):
    tax_defaults = _get_tax_profile_defaults()

    if not customer_doc:
        return {
            "buyer_ntn_cnic": "",
            "buyer_strn": "",
            "buyer_registration_type": tax_defaults.get("default_buyer_type") if tax_defaults.get("default_buyer_type") != "Consumer" else "Unregistered",
            "buyer_province": tax_defaults.get("province") or "",
            "buyer_fbr_address": tax_defaults.get("outlet_address") or "",
            "buyer_business_name": "Walk-in Customer",
        }

    registration_type = _normalize_buyer_registration_type(
        customer_doc.get("buyer_registration_type"),
        tax_defaults.get("default_buyer_type"),
    )
    buyer_name = _clean_text(customer_doc.get("customer_name") or customer_doc.name)
    if not buyer_name and tax_defaults.get("default_buyer_type") == "Consumer":
        buyer_name = "Walk-in Customer"

    return {
        "buyer_ntn_cnic": customer_doc.get("buyer_ntn_cnic") or "",
        "buyer_strn": customer_doc.get("buyer_strn") or "",
        "buyer_registration_type": registration_type,
        "buyer_province": customer_doc.get("buyer_province") or tax_defaults.get("province") or "",
        "buyer_fbr_address": _customer_address_fallback(customer_doc) or tax_defaults.get("outlet_address") or "",
        "buyer_business_name": buyer_name or customer_doc.name,
    }


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
            "tax_amount": flt(row.get("tax_amount"), 2),
            "net_amount": flt(row.get("net_amount"), 2),
            "price_includes_tax": 1 if row.get("price_includes_tax") else 0,
            "tax_category": row.get("tax_category") or "",
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
        "tax_amount": flt(sum(flt(row.get("tax_amount")) for row in items), 2),
        "net_amount": flt(sum(flt(row.get("net_amount")) for row in items), 2),
        "grand_total": flt(sale_doc.get("grand_total"), 2) if sale_doc else 0,
    }


def _format_invoice_date(value):
    return getdate(value).strftime("%Y-%m-%d") if value else ""


def _format_tax_rate(value):
    rate = flt(value)
    if rate == int(rate):
        return f"{int(rate)}%"
    return f"{rate:g}%"


def _money(value):
    return flt(value, 2)


def _scenario_ids(sale_doc):
    ids = []
    for row in get_invoice_tax_rows_for_fbr(sale_doc):
        scenario_id = _clean_text(row.get("scenario_id"))
        if scenario_id and scenario_id not in ids:
            ids.append(scenario_id)
    return ids


def build_internal_fbr_payload(sale_doc):
    settings = get_fbr_settings_internal()
    customer_doc = get_customer_for_fbr(sale_doc.get("customer")) if sale_doc else None
    item_rows = build_fbr_item_rows(sale_doc) if sale_doc else []
    price_includes_tax = 1 if any(row.get("price_includes_tax") for row in item_rows) else 0

    return {
        "source": "Ledgix",
        "payload_version": "1.0",
        "environment": settings.get("mode") or "Disabled",
        "invoice_type": "Sale Invoice",
        "sale": {
            "name": sale_doc.name if sale_doc else "",
            "invoice_number": (sale_doc.get("invoice_number") or sale_doc.name) if sale_doc else "",
            "sale_date": sale_doc.get("sale_date") if sale_doc else None,
            "docstatus": cint(sale_doc.docstatus) if sale_doc else None,
            "customer": sale_doc.get("customer") if sale_doc else "",
            "total_amount": flt(sale_doc.get("total_amount"), 2) if sale_doc else 0,
            "tax_amount": flt(sale_doc.get("tax_amount"), 2) if sale_doc else 0,
            "grand_total": flt(sale_doc.get("grand_total"), 2) if sale_doc else 0,
            "price_includes_tax": price_includes_tax,
        },
        "seller": build_fbr_seller_block(),
        "buyer": build_fbr_buyer_block(customer_doc),
        "items": item_rows,
        "totals": _payload_totals(item_rows, sale_doc),
    }


def build_official_sale_invoice_payload(sale_doc):
    settings = get_fbr_settings_internal()
    customer_doc = get_customer_for_fbr(sale_doc.get("customer")) if sale_doc else None
    seller = build_fbr_seller_block()
    buyer = build_fbr_buyer_block(customer_doc)
    items = []

    for row in get_invoice_tax_rows_for_fbr(sale_doc):
        items.append({
            "hsCode": _clean_hs_code(row.get("hs_code")),
            "productDescription": _item_description(row.get("item")),
            "rate": _format_tax_rate(row.get("tax_rate")),
            "uoM": row.get("uom_for_fbr") or "",
            "quantity": flt(row.get("qty"), 2),
            "totalValues": _money(row.get("net_amount")),
            "valueSalesExcludingST": _money(row.get("taxable_amount")),
            "fixedNotifiedValueOrRetailPrice": 0.00,
            "salesTaxApplicable": _money(row.get("tax_amount")),
            "salesTaxWithheldAtSource": 0.00,
            "extraTax": 0.00,
            "furtherTax": 0.00,
            "sroScheduleNo": row.get("sro_schedule_number") or "",
            "fedPayable": 0.00,
            "discount": _money(row.get("discount_amount")),
            "saleType": row.get("sales_type") or "",
            "sroItemSerialNo": row.get("sro_item_serial_number") or "",
        })

    payload = {
        "invoiceType": "Sale Invoice",
        "invoiceDate": _format_invoice_date(sale_doc.get("sale_date") if sale_doc else None),
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
        "items": items,
    }

    scenario_ids = _scenario_ids(sale_doc)
    if settings.get("mode") == "Sandbox" and scenario_ids:
        payload["scenarioId"] = scenario_ids[0]

    return payload


def _build_sale_invoice_payload_internal(sale_name):
    validation = _validate_sale_fbr_readiness_internal(sale_name)
    sale_doc = get_sale_for_fbr(sale_name)
    internal_payload = build_internal_fbr_payload(sale_doc)
    official_payload = build_official_sale_invoice_payload(sale_doc)

    if sale_doc:
        settings = get_fbr_settings_internal()
        scenario_ids = _scenario_ids(sale_doc)
        validation = validation or {"valid": False, "errors": [], "warnings": []}
        validation.setdefault("errors", [])
        validation.setdefault("warnings", [])

        if settings.get("mode") == "Sandbox" and not scenario_ids:
            _add_required_error(validation["errors"], "Scenario ID")
        if len(scenario_ids) > 1:
            validation["warnings"].append(
                "Multiple scenario IDs found in tax rows; first non-empty scenario ID was used."
            )
        validation["valid"] = len(validation.get("errors") or []) == 0

    return {
        "validation": validation,
        "payload": official_payload,
        "internal_payload": internal_payload,
    }


@frappe.whitelist()
def build_sale_invoice_payload(sale_name):
    _require_fbr_view_permission("view")
    return _build_sale_invoice_payload_internal(sale_name)


# ============================================================
# SALES RETURN / CREDIT NOTE
# ============================================================

def get_return_for_fbr(return_name):
    if not return_name:
        return None
    if not frappe.db.exists("DocType", "Ledgix Sales Return"):
        return None
    if not frappe.db.exists("Ledgix Sales Return", return_name):
        return None
    return frappe.get_doc("Ledgix Sales Return", return_name)


def get_return_tax_rows_for_fbr(return_doc):
    if not return_doc:
        return []
    return list(return_doc.get("tax_details") or [])


def _return_summary(return_doc=None, return_name=None):
    if not return_doc:
        return {
            "name": return_name or "",
            "docstatus": None,
            "customer": "",
            "original_sale": "",
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
        "total_amount": flt(return_doc.get("total_amount"), 2),
        "tax_amount": flt(return_doc.get("tax_amount"), 2),
        "grand_total": flt(return_doc.get("grand_total"), 2),
        "fbr_status": return_doc.get("fbr_status") or "",
    }


def _validate_return_fbr_readiness_internal(return_name):
    errors = []
    warnings = []
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

    docstatus = cint(return_doc.docstatus)
    if docstatus == 0:
        errors.append("Draft sales return cannot be used for FBR payload.")
    elif docstatus == 2:
        errors.append("Cancelled sales return cannot be used for FBR payload.")

    if not return_doc.get("original_sale"):
        _add_required_error(errors, "Original sale")

    original_sale = get_sale_for_fbr(return_doc.get("original_sale"))
    if return_doc.get("original_sale") and not original_sale:
        errors.append(f"Original sale {return_doc.get('original_sale')} was not found.")

    original_fbr_invoice = ""
    if original_sale:
        original_fbr_invoice = _clean_text(original_sale.get("fbr_invoice_number"))
        production_mode = (settings.get("mode") or "Disabled") == "Production"
        if not original_fbr_invoice:
            if production_mode:
                errors.append("Original sale must have an FBR invoice number before posting a credit note.")
            else:
                warnings.append("Original sale has no FBR invoice number yet.")

    tax_rows = get_return_tax_rows_for_fbr(return_doc)
    if not tax_rows:
        errors.append("Return tax_details must contain at least one immutable tax snapshot row.")

    for index, row in enumerate(tax_rows, start=1):
        prefix = f"Return tax row {index}"
        if flt(row.get("returned_qty") or row.get("qty")) <= 0:
            errors.append(f"{prefix} returned qty must be greater than zero.")
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

        if settings.get("mode") == "Sandbox" and not row.get("scenario_id"):
            _add_required_error(errors, f"{prefix} scenario ID")

    if original_fbr_invoice:
        warnings.append(f"Credit note will reference original FBR invoice {original_fbr_invoice}.")

    return {
        "valid": len(errors) == 0,
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
    customer_name = return_doc.get("customer") or (original_sale.get("customer") if original_sale else "")
    customer_doc = get_customer_for_fbr(customer_name)
    seller = build_fbr_seller_block()
    buyer = build_fbr_buyer_block(customer_doc)
    items = []

    for row in get_return_tax_rows_for_fbr(return_doc):
        qty = flt(row.get("returned_qty") or row.get("qty"), 2)
        items.append({
            "hsCode": _clean_hs_code(row.get("hs_code")),
            "productDescription": _item_description(row.get("item")),
            "rate": _format_tax_rate(row.get("tax_rate")),
            "uoM": row.get("uom_for_fbr") or "",
            "quantity": qty,
            "totalValues": _money(row.get("net_amount")),
            "valueSalesExcludingST": _money(row.get("taxable_amount")),
            "fixedNotifiedValueOrRetailPrice": 0.00,
            "salesTaxApplicable": _money(row.get("tax_amount")),
            "salesTaxWithheldAtSource": 0.00,
            "extraTax": 0.00,
            "furtherTax": 0.00,
            "sroScheduleNo": row.get("sro_schedule_number") or "",
            "fedPayable": 0.00,
            "discount": 0.00,
            "saleType": row.get("sales_type") or "",
            "sroItemSerialNo": row.get("sro_item_serial_number") or "",
        })

    payload = {
        "invoiceType": "Credit Note",
        "invoiceDate": _format_invoice_date(nowdate()),
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
        "items": items,
    }

    scenario_ids = []
    for row in get_return_tax_rows_for_fbr(return_doc):
        scenario_id = _clean_text(row.get("scenario_id"))
        if scenario_id and scenario_id not in scenario_ids:
            scenario_ids.append(scenario_id)

    if settings.get("mode") == "Sandbox" and scenario_ids:
        payload["scenarioId"] = scenario_ids[0]

    return payload


def _build_return_invoice_payload_internal(return_name):
    validation = _validate_return_fbr_readiness_internal(return_name)
    return_doc = get_return_for_fbr(return_name)
    official_payload = build_official_return_invoice_payload(return_doc)

    if return_doc:
        settings = get_fbr_settings_internal()
        scenario_ids = []
        for row in get_return_tax_rows_for_fbr(return_doc):
            scenario_id = _clean_text(row.get("scenario_id"))
            if scenario_id and scenario_id not in scenario_ids:
                scenario_ids.append(scenario_id)

        validation.setdefault("errors", [])
        validation.setdefault("warnings", [])
        if settings.get("mode") == "Sandbox" and not scenario_ids:
            _add_required_error(validation["errors"], "Scenario ID")
        validation["valid"] = len(validation.get("errors") or []) == 0

    return {
        "validation": validation,
        "payload": official_payload,
    }


@frappe.whitelist()
def build_return_invoice_payload(return_name):
    _require_fbr_view_permission("view")
    return _build_return_invoice_payload_internal(return_name)
