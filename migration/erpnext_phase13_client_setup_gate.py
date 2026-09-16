from __future__ import annotations

import traceback

import frappe

from ledgix_saas.api import client_setup, legacy_retirement, product_shell
from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE, TEST_COMPANY
from ledgix_saas.setup.erpnext_extensions import FEATURE_FIELDS, PROFILE_DEFAULTS, apply_business_profile_defaults


BUSINESS_MASTER_COUNTS = (
    "Company",
    "Item",
    "Customer",
    "Supplier",
    "Warehouse",
    "Price List",
    "Item Price",
    "POS Profile",
    "Mode of Payment",
    "Account",
)

SETUP_STATE_FIELDS = (
    "business_profile",
    "use_profile_defaults",
    *FEATURE_FIELDS,
    "setup_complete",
    "setup_version",
    "setup_company",
    "setup_completed_at",
    "setup_completed_by",
    "setup_snapshot_json",
)


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 13 client setup gate on {frappe.local.site!r}; restricted to {INTEGRATION_SITE!r}."
        )
    if not frappe.db.exists("Company", TEST_COMPANY):
        frappe.throw(f"Integration company {TEST_COMPANY!r} is missing.")


def _counts() -> dict:
    return {
        doctype: frappe.db.count(doctype) if frappe.db.exists("DocType", doctype) else None
        for doctype in BUSINESS_MASTER_COUNTS
    }


def _case(name: str, fn) -> dict:
    try:
        evidence, checks = fn()
        return {
            "name": name,
            "evidence": evidence,
            "checks": checks,
            "passed": all(checks.values()),
        }
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


def _setup_payload(profile: str, *, pos_profile: str, warehouse: str, price_list: str) -> dict:
    return {
        "business_profile": profile,
        "company": TEST_COMPANY,
        "warehouse": warehouse,
        "selling_price_list": price_list,
        "pos_profile": pos_profile,
        "apply_standard_defaults": 0,
    }


def _restore_profile(original: dict) -> None:
    doc = frappe.get_single("Ledgix Business Profile")
    doc.business_profile = original.get("business_profile") or "Small Retail"
    doc.use_profile_defaults = original.get("use_profile_defaults") or 0
    if doc.use_profile_defaults:
        apply_business_profile_defaults(doc)
    else:
        for fieldname in FEATURE_FIELDS:
            doc.set(fieldname, original.get(fieldname) or 0)
    for fieldname in SETUP_STATE_FIELDS:
        if fieldname in {"business_profile", "use_profile_defaults", *FEATURE_FIELDS}:
            continue
        doc.set(fieldname, original.get(fieldname))
    doc.save(ignore_permissions=True)


def run() -> dict:
    _assert_safe_site()
    frappe.set_user("Administrator")

    if not legacy_retirement.is_frozen():
        frappe.throw("Phase 13 requires the Phase 12 legacy retirement freeze to be active first.")
    legacy_before = legacy_retirement.verify_frozen_snapshot()
    if not legacy_before.get("matches"):
        frappe.throw("Phase 12 frozen legacy snapshot is not stable before Phase 13.")

    profile = frappe.get_single("Ledgix Business Profile")
    original_profile = {fieldname: profile.get(fieldname) for fieldname in SETUP_STATE_FIELDS}
    counts_before = _counts()

    company = TEST_COMPANY
    price_list = client_setup._selling_price_list()
    warehouse = client_setup._warehouse(company)
    pos_profile = client_setup._pos_profile(company)

    cases = {}

    def dependency_case():
        installed = set(frappe.get_installed_apps())
        page_exists = bool(frappe.db.exists("Page", "ledgix-setup"))
        checks = {
            "frappe_installed": "frappe" in installed,
            "erpnext_installed": "erpnext" in installed,
            "ledgix_installed": "ledgix_saas" in installed,
            "setup_page_installed": page_exists,
            "company_available": bool(company),
            "selling_price_list_available": bool(price_list),
            "warehouse_available": bool(warehouse),
            "pos_profile_available": bool(pos_profile),
        }
        return {
            "installed_apps": sorted(installed),
            "company": company,
            "selling_price_list": price_list,
            "warehouse": warehouse,
            "pos_profile": pos_profile,
        }, checks

    def preset_matrix_case():
        rows = []
        all_ready = True
        exact_features = True
        for name, expected in PROFILE_DEFAULTS.items():
            evaluation = client_setup.evaluate_client_setup(
                _setup_payload(name, pos_profile=pos_profile, warehouse=warehouse, price_list=price_list)
            )
            rows.append(
                {
                    "profile": name,
                    "ready": evaluation.get("ready"),
                    "features": evaluation.get("features"),
                    "blockers": evaluation.get("blockers"),
                }
            )
            all_ready = all_ready and bool(evaluation.get("ready"))
            exact_features = exact_features and evaluation.get("features") == {
                key: int(value) for key, value in expected.items()
            }
        checks = {
            "all_five_presets_exercised": len(rows) == 5,
            "all_presets_ready_on_integration_configuration": all_ready,
            "preset_features_match_phase3_contract": exact_features,
        }
        return {"rows": rows}, checks

    def requirement_split_case():
        invoice = client_setup.evaluate_client_setup(
            {
                **_setup_payload(
                    "Invoice + FBR Only",
                    pos_profile="DOES-NOT-EXIST",
                    warehouse="",
                    price_list=price_list,
                ),
                "warehouse": "",
            }
        )
        retail = client_setup.evaluate_client_setup(
            _setup_payload(
                "Small Retail",
                pos_profile="DOES-NOT-EXIST",
                warehouse=warehouse,
                price_list=price_list,
            )
        )
        invalid_price = client_setup.evaluate_client_setup(
            _setup_payload(
                "Invoice + FBR Only",
                pos_profile="",
                warehouse="",
                price_list="DOES-NOT-EXIST",
            )
        )
        invalid_warehouse = client_setup.evaluate_client_setup(
            _setup_payload(
                "Small Retail",
                pos_profile=pos_profile,
                warehouse="DOES-NOT-EXIST",
                price_list=price_list,
            )
        )
        retail_keys = {row.get("key") for row in retail.get("blockers") or []}
        price_keys = {row.get("key") for row in invalid_price.get("blockers") or []}
        warehouse_keys = {row.get("key") for row in invalid_warehouse.get("blockers") or []}
        checks = {
            "invoice_only_does_not_require_pos_profile": bool(invoice.get("ready")),
            "retail_requires_pos_profile": not retail.get("ready") and "pos_profile" in retail_keys,
            "explicit_invalid_selling_price_list_fails_closed": (
                not invalid_price.get("ready") and "selling_price_list" in price_keys
            ),
            "explicit_invalid_warehouse_fails_closed": (
                not invalid_warehouse.get("ready") and "warehouse" in warehouse_keys
            ),
            "fbr_activation_is_warning_not_setup_blocker": any(
                row.get("key") == "fbr_activation" and not row.get("blocking")
                for row in invoice.get("warnings") or []
            ),
        }
        return {
            "invoice_only": invoice,
            "small_retail_bad_pos": retail,
            "invoice_only_bad_price_list": invalid_price,
            "small_retail_bad_warehouse": invalid_warehouse,
        }, checks

    def apply_case():
        result = client_setup.apply_client_setup(
            _setup_payload("Mixed", pos_profile=pos_profile, warehouse=warehouse, price_list=price_list)
        )
        state = result.get("state") or {}
        effective = state.get("features") or {}
        admin_context = product_shell.build_product_context(
            roles=["Ledgix Admin"],
            features=effective,
        )
        cashier_context = product_shell.build_product_context(
            roles=["Ledgix Cashier"],
            features=effective,
        )
        checks = {
            "configuration_applied": bool(result.get("applied")),
            "setup_state_persisted": bool(
                state.get("setup_complete")
                and state.get("setup_version") == client_setup.SETUP_VERSION
                and state.get("setup_company") == company
            ),
            "mixed_profile_features_applied": all(
                int(effective.get(key) or 0) == int(value)
                for key, value in PROFILE_DEFAULTS["Mixed"].items()
            ),
            "admin_sees_setup_wizard": "Setup Wizard" in admin_context.get("visible_workspace_links", []),
            "cashier_lands_in_pos_for_mixed": cashier_context.get("landing_route") == "ledgix-pos",
            "apply_is_configuration_only": result.get("evaluation", {}).get("authority")
            == "ERPNext native configuration + Ledgix product preset",
        }
        return {"result": result, "admin_context": admin_context, "cashier_context": cashier_context}, checks

    def no_business_master_creation_case():
        counts_after_apply = _counts()
        legacy_after_apply = legacy_retirement.verify_frozen_snapshot()
        checks = {
            "erpnext_business_master_counts_unchanged": counts_before == counts_after_apply,
            "phase12_legacy_snapshot_still_matches": bool(legacy_after_apply.get("matches")),
            "phase12_legacy_remains_frozen": legacy_retirement.is_frozen(),
        }
        return {
            "counts_before": counts_before,
            "counts_after_apply": counts_after_apply,
            "legacy_verification": legacy_after_apply,
        }, checks

    for name, fn in (
        ("site_dependency_and_setup_surface", dependency_case),
        ("five_client_profile_presets", preset_matrix_case),
        ("profile_specific_readiness_requirements", requirement_split_case),
        ("apply_configuration_without_fork", apply_case),
        ("configuration_creates_no_business_masters", no_business_master_creation_case),
    ):
        cases[name] = _case(name, fn)

    restore_error = ""
    try:
        _restore_profile(original_profile)
    except Exception as exc:
        restore_error = f"{type(exc).__name__}: {exc}"

    counts_after_restore = _counts()
    legacy_final = legacy_retirement.verify_frozen_snapshot()
    restored = frappe.get_single("Ledgix Business Profile")
    restoration_checks = {
        "original_business_profile_restored": restored.get("business_profile") == original_profile.get("business_profile"),
        "original_setup_complete_restored": restored.get("setup_complete") == original_profile.get("setup_complete"),
        "business_master_counts_unchanged": counts_after_restore == counts_before,
        "legacy_snapshot_matches": bool(legacy_final.get("matches")),
        "legacy_remains_frozen": legacy_retirement.is_frozen(),
        "restore_completed_without_error": not restore_error,
    }
    cases["integration_site_state_restored"] = {
        "name": "integration_site_state_restored",
        "evidence": {
            "restore_error": restore_error,
            "original_profile": original_profile,
            "restored_profile": {fieldname: restored.get(fieldname) for fieldname in SETUP_STATE_FIELDS},
            "counts_before": counts_before,
            "counts_after_restore": counts_after_restore,
            "legacy_verification": legacy_final,
        },
        "checks": restoration_checks,
        "passed": all(restoration_checks.values()),
    }

    failed = [name for name, case in cases.items() if not case.get("passed")]
    result = {
        "site": frappe.local.site,
        "run_as": frappe.session.user,
        "company": company,
        "cases": cases,
        "case_count": len(cases),
        "failed_cases": failed,
        "decisions": {
            "codebase": "one Ledgix codebase",
            "client_differences": "configuration and product presets only",
            "business_authority": "ERPNext",
            "setup_wizard_scope": "configuration only; no duplicate business masters",
            "supported_presets": list(PROFILE_DEFAULTS),
            "erpnext_dependency_required": True,
            "legacy_history_state": "Phase 12 frozen historical audit",
        },
        "phase13_complete": not failed and bool(legacy_final.get("matches")) and legacy_retirement.is_frozen(),
        "migration_complete": not failed and bool(legacy_final.get("matches")) and legacy_retirement.is_frozen(),
        "next_step": "Client acceptance, production provisioning and release hardening",
        "passed": not failed and bool(legacy_final.get("matches")) and legacy_retirement.is_frozen(),
    }
    frappe.db.commit()
    return result
