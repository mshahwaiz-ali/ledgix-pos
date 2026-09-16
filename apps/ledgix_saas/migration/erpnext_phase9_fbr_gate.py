from __future__ import annotations

import traceback

import frappe
from frappe.utils import flt

from ledgix_saas.api import fbr_native
from ledgix_saas.migration import erpnext_phase4_tax_parity_gate as tax_gate
from ledgix_saas.migration import erpnext_pos_behavioral_spike as pos_base
from ledgix_saas.migration import erpnext_pos_behavioral_spike_runtime as pos_runtime
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.services import erpnext_pos, erpnext_selling
from ledgix_saas.setup import erpnext_phase9_extensions


ITEM = "LEDGIX-P9-FBR-NATIVE"
PRICE = 100.0
SCENARIO = "SN001"


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 9 FBR gate on {frappe.local.site!r}; restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing.")


def _count(doctype: str) -> int | None:
    if not frappe.db.exists("DocType", doctype):
        return None
    return frappe.db.count(doctype)


def _legacy_business_counts() -> dict:
    return {
        doctype: _count(doctype)
        for doctype in (
            "Ledgix Sale",
            "Ledgix Sales Return",
            "Ledgix Payment",
            "Ledgix Stock Movement",
        )
    }


def _legacy_fbr_log_count() -> int:
    if not frappe.db.exists("DocType", "Ledgix FBR Submission Log"):
        return 0
    return frappe.db.count(
        "Ledgix FBR Submission Log",
        {"reference_doctype": ["in", ["Ledgix Sale", "Ledgix Sales Return"]]},
    )


def _ensure_fixtures() -> dict:
    erpnext_phase9_extensions.sync_all()
    tax_gate._ensure_tax_accounts()
    customer = tax_gate._ensure_customer()
    tax_gate._ensure_category(tax_gate.STANDARD_CATEGORY, rate=18)
    tax_gate._ensure_item(ITEM)
    tax_gate._ensure_profile(
        ITEM,
        tax_gate.ProfileSpec(
            category=tax_gate.STANDARD_CATEGORY,
            hs_code="0101.21",
            sales_type="Goods at standard rate",
            scenario_id=SCENARIO,
        ),
    )
    price = frappe.db.get_value(
        "Item Price",
        {"item_code": ITEM, "price_list": "Standard Selling", "uom": "Nos"},
        "name",
    )
    if price:
        frappe.db.set_value("Item Price", price, "price_list_rate", PRICE, update_modified=False)
    else:
        frappe.get_doc(
            {
                "doctype": "Item Price",
                "item_code": ITEM,
                "price_list": "Standard Selling",
                "price_list_rate": PRICE,
                "currency": "PKR",
                "uom": "Nos",
            }
        ).insert(ignore_permissions=True)

    warehouse = pos_base._leaf_warehouse()
    cash_account = pos_base._ensure_cash_mode_account()
    profile_name = pos_runtime._ensure_pos_profile(customer, warehouse, cash_account)
    return {
        "customer": customer,
        "item": ITEM,
        "warehouse": warehouse,
        "pos_profile": profile_name,
    }


def _disabled_settings() -> dict:
    return {
        "enabled": False,
        "mode": "Disabled",
        "submit_trigger": "Manual",
        "sandbox_token_configured": False,
        "production_token_configured": False,
        "production_post_armed": False,
        "sandbox_post_on_submit": False,
    }


def _disabled_control() -> dict:
    return {
        "enabled": False,
        "mode": "Disabled",
        "submit_trigger": "Manual",
        "token_configured": False,
    }


def _sandbox_settings() -> dict:
    return {
        "enabled": True,
        "mode": "Sandbox",
        "submit_trigger": "Manual",
        "sandbox_token_configured": True,
        "production_token_configured": True,
        "production_post_armed": True,
        "sandbox_post_on_submit": False,
    }


def _sandbox_control() -> dict:
    return {
        "enabled": True,
        "mode": "Sandbox",
        "submit_trigger": "Manual",
        "token_configured": True,
        "can_manual_submit": True,
        "can_manual_validate": True,
    }


def _production_settings() -> dict:
    result = _sandbox_settings()
    result["mode"] = "Production"
    return result


def _production_control() -> dict:
    result = _sandbox_control()
    result["mode"] = "Production"
    return result


def _seller() -> dict:
    return {
        "seller_ntn_cnic": "1234567",
        "seller_strn": "",
        "seller_business_name": "Ledgix Phase 9 Integration Seller",
        "seller_province": "Sindh",
        "seller_address": "Phase 9 Integration Address",
        "seller_phone": "",
        "seller_email": "",
    }


class _NativeFBRPatch:
    def __init__(self):
        self.originals = {}
        self.post_calls = 0
        self.validate_calls = 0
        self.post_result = None
        self.validate_result = None

    def __enter__(self):
        for name in (
            "get_fbr_settings_internal",
            "get_fbr_control_state_internal",
            "_seller_block",
        ):
            self.originals[name] = getattr(fbr_native, name)
        self.originals["post_invoice"] = fbr_native.fbr_client.post_invoice
        self.originals["validate_invoice"] = fbr_native.fbr_client.validate_invoice
        fbr_native._seller_block = _seller
        self.use_disabled()

        def post_invoice(payload, mode=None):
            self.post_calls += 1
            if self.post_result is not None:
                return self.post_result
            return {
                "network_call": True,
                "success": True,
                "http_status": 200,
                "fbr_operation": "post",
                "response": {
                    "invoiceNumber": f"FBR-P9-{self.post_calls:04d}",
                    "QRCode": f"QR-P9-{self.post_calls:04d}",
                    "validationResponse": {
                        "status": "Valid",
                        "statusCode": "00",
                        "invoiceStatuses": [],
                    },
                },
            }

        def validate_invoice(payload, mode=None):
            self.validate_calls += 1
            if self.validate_result is not None:
                return self.validate_result
            return {
                "network_call": True,
                "success": True,
                "http_status": 200,
                "fbr_operation": "validate",
                "response": {
                    "QRCode": f"VALIDATE-QR-P9-{self.validate_calls:04d}",
                    "validationResponse": {
                        "status": "Valid",
                        "statusCode": "00",
                        "invoiceStatuses": [],
                    },
                },
            }

        fbr_native.fbr_client.post_invoice = post_invoice
        fbr_native.fbr_client.validate_invoice = validate_invoice
        return self

    def use_disabled(self):
        fbr_native.get_fbr_settings_internal = _disabled_settings
        fbr_native.get_fbr_control_state_internal = _disabled_control

    def use_sandbox(self):
        fbr_native.get_fbr_settings_internal = _sandbox_settings
        fbr_native.get_fbr_control_state_internal = _sandbox_control

    def use_production(self):
        fbr_native.get_fbr_settings_internal = _production_settings
        fbr_native.get_fbr_control_state_internal = _production_control

    def __exit__(self, exc_type, exc, tb):
        for name in (
            "get_fbr_settings_internal",
            "get_fbr_control_state_internal",
            "_seller_block",
        ):
            setattr(fbr_native, name, self.originals[name])
        fbr_native.fbr_client.post_invoice = self.originals["post_invoice"]
        fbr_native.fbr_client.validate_invoice = self.originals["validate_invoice"]
        return False


def _reset_status(doc) -> None:
    frappe.db.set_value(
        doc.doctype,
        doc.name,
        {
            "custom_ledgix_fbr_status": "Not Submitted",
            "custom_ledgix_fbr_invoice_number": "",
            "custom_ledgix_fbr_reference": "",
            "custom_ledgix_fbr_qr_code": "",
            "custom_ledgix_fbr_submission_log": "",
            "custom_ledgix_fbr_error_code": "",
            "custom_ledgix_fbr_error_message": "",
            "custom_ledgix_fbr_reconciliation_required": 0,
        },
        update_modified=False,
    )
    doc.reload()


def _new_sales_invoice(fixtures: dict, token: str):
    return erpnext_selling.create_sales_invoice(
        customer=fixtures["customer"],
        items=[{"item": fixtures["item"], "qty": 1}],
        company=TEST_COMPANY,
        selling_price_list="Standard Selling",
        sale_channel="B2B",
        client_sale_id=f"P9-SI-{token}",
        checkout_source="Phase 9 Native FBR Gate",
        submit=True,
    )


def _ensure_clean_pos_opening() -> None:
    info = erpnext_pos.shift_info(company=TEST_COMPANY)
    if info.get("has_active_shift"):
        erpnext_pos.close_shift(
            actual_cash=max(flt(info.get("expected_cash")), 0),
            shift_name=info.get("shift_id"),
            company=TEST_COMPANY,
        )


def _new_pos_invoice(fixtures: dict, token: str):
    _ensure_clean_pos_opening()
    erpnext_pos.open_shift(0, notes="Phase 9 FBR gate", company=TEST_COMPANY)
    preview = erpnext_pos.preview_checkout(
        cart_items=[{"item": fixtures["item"], "qty": 1}],
        customer=fixtures["customer"],
        price_list="Standard Selling",
        company=TEST_COMPANY,
    )
    invoice = erpnext_pos.complete_sale(
        cart_items=[{"item": fixtures["item"], "qty": 1}],
        tenders=[{"payment_method": "Cash", "amount": preview["grand_total"]}],
        customer=fixtures["customer"],
        price_list="Standard Selling",
        client_sale_id=f"P9-POS-{token}",
        company=TEST_COMPANY,
    )
    return invoice


def _case(name: str, fn) -> dict:
    try:
        evidence, checks = fn()
        return {"name": name, "evidence": evidence, "checks": checks, "passed": all(checks.values())}
    except Exception as exc:
        return {
            "name": name,
            "evidence": {},
            "checks": {},
            "passed": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback_tail": traceback.format_exc().splitlines()[-12:],
        }


def run() -> dict:
    _assert_safe_site()
    frappe.set_user("Administrator")
    fixtures = _ensure_fixtures()
    legacy_before = _legacy_business_counts()
    legacy_fbr_logs_before = _legacy_fbr_log_count()
    run_token = frappe.generate_hash(length=10).upper()
    state: dict = {"fixtures": fixtures}

    with _NativeFBRPatch() as patch:
        patch.use_disabled()
        sale = _new_sales_invoice(fixtures, run_token)
        pos = _new_pos_invoice(fixtures, run_token)
        _reset_status(sale)
        _reset_status(pos)
        state.update({"sale": sale, "pos": pos})

        def sales_payload_case():
            patch.use_sandbox()
            result = fbr_native.build_native_payload_internal("Sales Invoice", sale.name)
            payload = result.get("payload") or {}
            validation = result.get("validation") or {}
            checks = {
                "native_source_sales_invoice": result.get("source", {}).get("doctype") == "Sales Invoice",
                "ready_from_immutable_snapshot": bool(validation.get("valid")),
                "official_sale_invoice": payload.get("invoiceType") == "Sale Invoice",
                "native_item_payload": bool(payload.get("items")) and payload["items"][0].get("hsCode") == "0101.21",
                "sandbox_scenario_preserved": payload.get("scenarioId") == SCENARIO,
            }
            return {"invoice": sale.name, "payload": payload, "validation": validation}, checks

        def pos_payload_case():
            patch.use_sandbox()
            result = fbr_native.build_native_payload_internal("POS Invoice", pos.name)
            payload = result.get("payload") or {}
            validation = result.get("validation") or {}
            checks = {
                "native_source_pos_invoice": result.get("source", {}).get("doctype") == "POS Invoice",
                "ready_from_pos_snapshot": bool(validation.get("valid")),
                "official_sale_invoice": payload.get("invoiceType") == "Sale Invoice",
                "scenario_preserved": payload.get("scenarioId") == SCENARIO,
            }
            return {"invoice": pos.name, "payload": payload, "validation": validation}, checks

        def validation_log_case():
            patch.use_sandbox()
            before = patch.validate_calls
            result = fbr_native.validate_native_with_fbr_internal("Sales Invoice", sale.name, "Sandbox")
            status = fbr_native._get_status("Sales Invoice", sale.name)
            log = frappe.get_doc("Ledgix FBR Submission Log", result.get("log_name"))
            checks = {
                "mock_validation_called_once": patch.validate_calls == before + 1,
                "native_status_validated": status.get("fbr_status") == "Validated",
                "log_references_sales_invoice": log.reference_doctype == "Sales Invoice" and log.reference_name == sale.name,
                "no_invoice_number_from_validate": not status.get("fbr_invoice_number"),
            }
            return {"result": result, "status": status, "log": log.name}, checks

        def submit_idempotency_case():
            patch.use_production()
            before = patch.post_calls
            first = fbr_native.submit_native_to_fbr_internal("Sales Invoice", sale.name)
            second = fbr_native.submit_native_to_fbr_internal("Sales Invoice", sale.name)
            status = fbr_native._get_status("Sales Invoice", sale.name)
            checks = {
                "mock_post_called_once": patch.post_calls == before + 1,
                "submitted": first.get("status") == "Submitted",
                "idempotent_retry": second.get("status") == "Already Submitted",
                "native_invoice_number_persisted": bool(status.get("fbr_invoice_number")),
                "native_qr_persisted": bool(status.get("fbr_qr_code")),
            }
            return {"first": first, "second": second, "status": status}, checks

        def credit_note_case():
            patch.use_disabled()
            source = frappe.get_doc("Sales Invoice", sale.name)
            source_row = source.items[0]
            credit = erpnext_selling.create_sales_return(
                sales_invoice=source.name,
                return_items=[{"sales_invoice_item": source_row.name, "qty": 1}],
                reason="Phase 9 native FBR credit note",
                client_return_id=f"P9-RET-{run_token}",
                checkout_source="Phase 9 FBR Gate Return",
            )
            _reset_status(credit)
            patch.use_sandbox()
            result = fbr_native.build_native_payload_internal("Sales Invoice", credit.name)
            payload = result.get("payload") or {}
            checks = {
                "native_credit_note": bool(credit.is_return) and credit.return_against == source.name,
                "credit_note_payload": payload.get("invoiceType") == "Credit Note",
                "references_original_fbr_invoice": payload.get("invoiceRefNo") == fbr_native._get_status("Sales Invoice", source.name).get("fbr_invoice_number"),
                "return_reason_preserved": bool(payload.get("reason")),
            }
            state["credit"] = credit
            return {"credit_note": credit.name, "payload": payload}, checks

        def reconciliation_case():
            patch.use_disabled()
            other = _new_sales_invoice(fixtures, f"{run_token}-AMB")
            _reset_status(other)
            patch.use_production()
            old_result = patch.post_result
            patch.post_result = {
                "network_call": True,
                "success": False,
                "http_status": None,
                "status": "Network Error",
                "fbr_operation": "post",
                "error": "simulated ambiguous transport failure",
                "response": None,
            }
            before = patch.post_calls
            first = fbr_native.submit_native_to_fbr_internal("Sales Invoice", other.name)
            second = fbr_native.submit_native_to_fbr_internal("Sales Invoice", other.name)
            status = fbr_native._get_status("Sales Invoice", other.name)
            released = fbr_native.release_native_after_fbr_reconciliation(
                "Sales Invoice",
                other.name,
                fbr_native.RECONCILIATION_CONFIRMATION,
            )
            patch.post_result = old_result
            checks = {
                "ambiguous_post_called_once": patch.post_calls == before + 1,
                "reconciliation_required": first.get("status") == fbr_native.RECONCILIATION_REQUIRED,
                "blind_retry_blocked": second.get("status") == fbr_native.RECONCILIATION_REQUIRED,
                "no_invoice_number_on_ambiguous_result": not status.get("fbr_invoice_number"),
                "reconciliation_flag_persisted": bool(status.get("fbr_reconciliation_required")),
                "manual_release_requires_confirmation": released.get("status") == "Pending",
            }
            state["ambiguous"] = other
            return {"first": first, "second": second, "status": status, "released": released}, checks

        def consolidated_guard_case():
            patch.use_disabled()
            info = erpnext_pos.shift_info(company=TEST_COMPANY)
            opening_name = info.get("shift_id")
            opening, closing = erpnext_pos.close_shift(
                actual_cash=max(flt(info.get("expected_cash")), 0),
                shift_name=opening_name,
                company=TEST_COMPANY,
            )
            pos.reload()
            consolidated = pos.get("consolidated_invoice") or ""
            consolidated_doc = frappe.get_doc("Sales Invoice", consolidated) if consolidated else None
            log_count = (
                frappe.db.count(
                    "Ledgix FBR Submission Log",
                    {"reference_doctype": "Sales Invoice", "reference_name": consolidated},
                )
                if consolidated
                else 0
            )
            checks = {
                "closing_submitted": closing.docstatus == 1,
                "pos_consolidated": bool(consolidated),
                "consolidated_si_rejected_as_fbr_source": bool(consolidated_doc) and not fbr_native.is_native_fbr_source(consolidated_doc),
                "no_fbr_log_for_consolidated_si": log_count == 0,
            }
            return {"opening": opening.name, "closing": closing.name, "consolidated": consolidated}, checks

        def correction_case():
            status = fbr_native._get_status("Sales Invoice", sale.name)
            request = frappe.get_doc(
                {
                    "doctype": "Ledgix FBR Correction Request",
                    "reference_doctype": "Sales Invoice",
                    "reference_name": sale.name,
                    "action_type": "Edit",
                    "reason": "Phase 9 native correction tracking proof",
                }
            )
            request.insert(ignore_permissions=True)
            checks = {
                "native_reference_saved": request.reference_doctype == "Sales Invoice" and request.reference_name == sale.name,
                "fbr_number_frozen": request.fbr_invoice_number == status.get("fbr_invoice_number"),
                "deadline_calculated": bool(request.correction_deadline),
                "legacy_sale_not_required": not request.sale,
            }
            return {"correction_request": request.name, "deadline": request.correction_deadline}, checks

        cases = {}
        for name, fn in (
            ("native_sales_payload_from_snapshots", sales_payload_case),
            ("native_pos_payload_from_snapshots", pos_payload_case),
            ("mocked_validation_log_native_reference", validation_log_case),
            ("mocked_submit_idempotency", submit_idempotency_case),
            ("native_credit_note_original_reference", credit_note_case),
            ("ambiguous_production_reconciliation_lock", reconciliation_case),
            ("consolidated_pos_sales_invoice_excluded", consolidated_guard_case),
            ("native_fbr_correction_tracking", correction_case),
        ):
            cases[name] = _case(name, fn)

    legacy_after = _legacy_business_counts()
    legacy_fbr_logs_after = _legacy_fbr_log_count()
    cases["no_dual_legacy_fbr_source"] = {
        "name": "no_dual_legacy_fbr_source",
        "evidence": {
            "legacy_business_before": legacy_before,
            "legacy_business_after": legacy_after,
            "legacy_fbr_logs_before": legacy_fbr_logs_before,
            "legacy_fbr_logs_after": legacy_fbr_logs_after,
        },
        "checks": {
            "legacy_business_ledgers_unchanged": legacy_before == legacy_after,
            "no_legacy_fbr_submission_log_created": legacy_fbr_logs_before == legacy_fbr_logs_after,
        },
        "passed": legacy_before == legacy_after and legacy_fbr_logs_before == legacy_fbr_logs_after,
    }

    failed = [name for name, case in cases.items() if not case.get("passed")]
    result = {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "company": TEST_COMPANY,
        "fixtures": fixtures,
        "cases": cases,
        "case_count": len(cases),
        "failed_cases": failed,
        "network_safety": {
            "real_fbr_network_calls": 0,
            "validate_adapter_calls_mocked": patch.validate_calls,
            "post_adapter_calls_mocked": patch.post_calls,
        },
        "decisions": {
            "sale_invoice_fbr_source": "ERPNext Sales Invoice",
            "retail_fbr_source": "ERPNext POS Invoice",
            "credit_note_fbr_source": "ERPNext native return invoice",
            "pos_consolidated_sales_invoice_fbr_source": False,
            "submission_log_owner": "Ledgix FBR Submission Log",
            "legacy_ledgix_sale_new_submission_retired": True,
            "retry_policy": "Fail closed on ambiguous Production POST until external reconciliation",
        },
        "phase9_complete": not failed,
        "phase10_ready": not failed,
        "next_phase": "Phase 10 — Final Print Redesign",
        "passed": not failed,
    }
    frappe.db.commit()
    return result
