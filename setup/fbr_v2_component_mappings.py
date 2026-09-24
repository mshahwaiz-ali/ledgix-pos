from __future__ import annotations

from collections.abc import Iterable

import frappe
from frappe.utils import cint


MAPPING_DOCTYPE = "Ledgix FBR Tax Component Mapping"

ALLOWED_COMPONENTS = frozenset(
    {
        "Sales Tax Applicable",
        "Sales Tax Withheld At Source",
        "Extra Tax",
        "Further Tax",
        "FED Payable",
    }
)

NON_POSTING_FBR_COMPONENTS = frozenset(
    {
        "Sales Tax Withheld At Source",
    }
)


def _normalize_plan(
    component_plan: Iterable[tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    normalized: list[tuple[str, str]] = []
    seen: dict[str, str] = {}

    for raw_account, raw_component in component_plan:
        account = str(raw_account or "").strip()
        component = str(raw_component or "").strip()

        if not account:
            frappe.throw("FBR component mapping plan contains a blank Account.")
        if component not in ALLOWED_COMPONENTS:
            frappe.throw(f"Unsupported FBR tax component: {component or '<blank>'}.")

        previous = seen.get(account)
        if previous and previous != component:
            frappe.throw(
                f"FBR component mapping plan maps Account {account} to both "
                f"{previous} and {component}."
            )

        if previous:
            continue

        seen[account] = component
        normalized.append((account, component))

    return tuple(normalized)


def _account_state(company: str, account_head: str) -> dict:
    account = frappe.db.get_value(
        "Account",
        account_head,
        ["name", "company", "is_group", "disabled", "account_type", "root_type"],
        as_dict=True,
    )

    if not account:
        frappe.throw(f"Missing ERPNext Account {account_head}.")
    if account.company != company:
        frappe.throw(
            f"ERPNext Account {account_head} belongs to {account.company}, "
            f"not {company}."
        )
    if cint(account.is_group):
        frappe.throw(f"ERPNext Account {account_head} is a group Account.")
    if cint(account.disabled):
        frappe.throw(f"ERPNext Account {account_head} is disabled.")

    return dict(account)


def preview_component_mappings(
    company: str,
    component_plan: Iterable[tuple[str, str]],
) -> dict:
    company = str(company or "").strip()

    if not company or not frappe.db.exists("Company", company):
        frappe.throw("Select a valid ERPNext Company.")

    plan = _normalize_plan(component_plan)
    rows: list[dict] = []
    blockers: list[str] = []

    for account_head, component in plan:
        account = _account_state(company, account_head)

        active_rows = frappe.get_all(
            MAPPING_DOCTYPE,
            filters={
                "company": company,
                "account_head": account_head,
                "active": 1,
            },
            fields=["name", "component", "active"],
            order_by="name asc",
            limit_page_length=0,
        )

        if len(active_rows) > 1:
            blocker = (
                f"Multiple active FBR component mappings exist for Account "
                f"{account_head}."
            )
            blockers.append(blocker)
            action = "blocked_duplicate"
            existing_name = ""
        elif active_rows and str(active_rows[0].component or "") != component:
            blocker = (
                f"Active FBR component mapping {active_rows[0].name} maps "
                f"{account_head} to {active_rows[0].component}; expected "
                f"{component}."
            )
            blockers.append(blocker)
            action = "blocked_conflict"
            existing_name = active_rows[0].name
        elif active_rows:
            action = "keep_existing"
            existing_name = active_rows[0].name
        else:
            action = "create"
            existing_name = ""

        rows.append(
            {
                "account_head": account_head,
                "component": component,
                "action": action,
                "existing_mapping": existing_name,
                "account_type": account.get("account_type") or "",
                "root_type": account.get("root_type") or "",
                "non_posting_fbr_evidence": component in NON_POSTING_FBR_COMPONENTS,
            }
        )

    return {
        "company": company,
        "read_only": True,
        "database_write": False,
        "fbr_network_call": False,
        "mapping_count": len(rows),
        "create_count": sum(1 for row in rows if row["action"] == "create"),
        "keep_existing_count": sum(
            1 for row in rows if row["action"] == "keep_existing"
        ),
        "blockers": blockers,
        "mappings": rows,
    }


def provision_component_mappings(
    company: str,
    component_plan: Iterable[tuple[str, str]],
    *,
    notes: str = "Provisioned from verified ERPNext-native FBR semantic mapping.",
) -> dict:
    preview = preview_component_mappings(company, component_plan)

    if preview["blockers"]:
        frappe.throw(
            "FBR component mapping provisioning is blocked: "
            + " | ".join(preview["blockers"])
        )

    created: list[str] = []
    kept: list[str] = []

    for row in preview["mappings"]:
        if row["action"] == "keep_existing":
            kept.append(row["existing_mapping"])
            continue

        doc = frappe.get_doc(
            {
                "doctype": MAPPING_DOCTYPE,
                "company": company,
                "account_head": row["account_head"],
                "component": row["component"],
                "active": 1,
                "notes": notes,
            }
        )
        doc.insert(ignore_permissions=True)
        created.append(doc.name)

    return {
        "company": company,
        "database_write": bool(created),
        "fbr_network_call": False,
        "created": created,
        "kept_existing": kept,
        "mapping_count": len(preview["mappings"]),
        "non_posting_components": sorted(NON_POSTING_FBR_COMPONENTS),
    }
