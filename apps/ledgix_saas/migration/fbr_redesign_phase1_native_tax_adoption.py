from __future__ import annotations

from collections import Counter, defaultdict

import frappe
from frappe.utils import cint, flt

from ledgix_saas.migration.erpnext_integration_bootstrap import INTEGRATION_SITE


COMPANY = "Ledgix ERPNext Integration"
COMPANY_ABBR = "LEI"
GST_ACCOUNT = "GST - LEI"

STANDARD_TITLE = "Ledgix Sales Tax 18"
ZERO_TITLE = "Ledgix Sales Tax Zero Rated"
EXEMPT_TITLE = "Ledgix Sales Tax Exempt"

STANDARD_TEMPLATE = f"{STANDARD_TITLE} - {COMPANY_ABBR}"
ZERO_TEMPLATE = f"{ZERO_TITLE} - {COMPANY_ABBR}"
EXEMPT_TEMPLATE = f"{EXEMPT_TITLE} - {COMPANY_ABBR}"

EXPECTED_ACTIVE_PROFILES = 73
EXPECTED_MAPPED_PROFILES = 64
EXPECTED_BLOCKED_PROFILES = 9


def _assert_safe_site() -> None:
    if frappe.local.site != INTEGRATION_SITE:
        frappe.throw(
            f"Refusing Phase 1 native tax adoption on {frappe.local.site!r}; "
            f"this helper is restricted to {INTEGRATION_SITE!r}."
        )


def _table_exists(doctype: str) -> bool:
    return frappe.db.table_exists(doctype, cached=False)


def _nonzero(value) -> bool:
    return abs(flt(value)) > 0.000001


def _load_categories() -> dict[str, dict]:
    if not _table_exists("Ledgix Tax Category"):
        frappe.throw("Legacy Ledgix Tax Category table is required for controlled adoption.")

    rows = frappe.get_all(
        "Ledgix Tax Category",
        fields=[
            "name",
            "category_name",
            "tax_type",
            "default_rate",
            "active",
            "is_exempt",
            "is_zero_rated",
        ],
        limit_page_length=0,
    )
    return {row.name: dict(row) for row in rows}


def _load_profiles() -> list[dict]:
    if not _table_exists("Ledgix Item Tax Profile"):
        frappe.throw("Legacy Ledgix Item Tax Profile table is required for controlled adoption.")

    return [
        dict(row)
        for row in frappe.get_all(
            "Ledgix Item Tax Profile",
            fields=[
                "name",
                "erpnext_item",
                "tax_category",
                "taxable",
                "active",
                "needs_review",
                "tax_basis",
                "notified_retail_price",
                "sales_tax_withheld_at_source_per_unit",
                "extra_tax_per_unit",
                "further_tax_per_unit",
                "fed_payable_per_unit",
            ],
            order_by="name asc",
            limit_page_length=0,
        )
    ]


def _item_state(item_code: str) -> dict:
    row = frappe.db.get_value(
        "Item",
        item_code,
        ["name", "disabled", "has_variants", "variant_of"],
        as_dict=True,
    )
    return dict(row or {})


def _classify_profile(row: dict, categories: dict[str, dict]) -> dict:
    item_code = str(row.get("erpnext_item") or "").strip()
    category_name = str(row.get("tax_category") or "").strip()

    reasons = []

    if not item_code:
        reasons.append("missing_erpnext_item")
        item_state = {}
    else:
        item_state = _item_state(item_code)
        if not item_state:
            reasons.append("missing_item_master")

    if item_state and cint(item_state.get("has_variants")):
        reasons.append("item_is_variant_template")

    if cint(row.get("needs_review")):
        reasons.append("needs_review")

    tax_basis = str(row.get("tax_basis") or "").strip()
    if tax_basis != "Transaction Value":
        reasons.append("non_transaction_value_tax_basis")

    specials = {
        "sales_tax_withheld_at_source_per_unit": row.get(
            "sales_tax_withheld_at_source_per_unit"
        ),
        "extra_tax_per_unit": row.get("extra_tax_per_unit"),
        "further_tax_per_unit": row.get("further_tax_per_unit"),
        "fed_payable_per_unit": row.get("fed_payable_per_unit"),
    }
    if any(_nonzero(value) for value in specials.values()):
        reasons.append("special_per_unit_tax")

    category = categories.get(category_name)
    if not category:
        reasons.append("unknown_tax_category")
    elif not cint(category.get("active")):
        reasons.append("inactive_tax_category")

    mapping = None
    template = None

    if not reasons and category:
        rate = flt(category.get("default_rate"))
        taxable = bool(cint(row.get("taxable")))
        is_exempt = bool(cint(category.get("is_exempt")))
        is_zero_rated = bool(cint(category.get("is_zero_rated")))

        if is_exempt and not taxable and abs(rate) <= 0.000001:
            mapping = "exempt"
            template = EXEMPT_TEMPLATE
        elif is_zero_rated and not taxable and abs(rate) <= 0.000001:
            mapping = "zero_rated"
            template = ZERO_TEMPLATE
        elif taxable and not is_exempt and not is_zero_rated and abs(rate - 18.0) <= 0.000001:
            mapping = "standard_18"
            template = STANDARD_TEMPLATE
        else:
            reasons.append("unsupported_financial_signature")

    return {
        "profile": row.get("name"),
        "item": item_code,
        "category": category_name,
        "mapping": mapping,
        "template": template,
        "blocked": bool(reasons),
        "reasons": reasons,
        "item_state": item_state,
    }


def build_plan() -> dict:
    _assert_safe_site()

    if not frappe.db.exists("Company", COMPANY):
        frappe.throw(f"Company {COMPANY!r} does not exist.")

    account = frappe.db.get_value(
        "Account",
        GST_ACCOUNT,
        ["name", "company", "account_type", "root_type", "is_group", "disabled"],
        as_dict=True,
    )
    if not account:
        frappe.throw(f"Required native GST account {GST_ACCOUNT!r} does not exist.")
    if account.company != COMPANY:
        frappe.throw(f"{GST_ACCOUNT} belongs to another Company.")
    if cint(account.is_group) or cint(account.disabled):
        frappe.throw(f"{GST_ACCOUNT} must be an enabled leaf Account.")
    if account.account_type != "Tax":
        frappe.throw(f"{GST_ACCOUNT} must be Account Type Tax.")

    add_from_item_template = bool(
        frappe.db.get_single_value(
            "Accounts Settings",
            "add_taxes_from_item_tax_template",
        )
    )
    if not add_from_item_template:
        frappe.throw(
            "Accounts Settings must keep Automatically Add Taxes and Charges "
            "from Item Tax Template enabled."
        )

    categories = _load_categories()
    profiles = [
        row
        for row in _load_profiles()
        if cint(row.get("active"))
    ]

    seen_items = defaultdict(list)
    for row in profiles:
        item_code = str(row.get("erpnext_item") or "").strip()
        if item_code:
            seen_items[item_code].append(row["name"])

    duplicates = {
        item: names
        for item, names in seen_items.items()
        if len(names) > 1
    }
    if duplicates:
        frappe.throw(
            "Duplicate active legacy Item Tax Profiles exist for ERPNext Items: "
            + ", ".join(sorted(duplicates))
        )

    classified = [
        _classify_profile(row, categories)
        for row in profiles
    ]

    mapped = [row for row in classified if not row["blocked"]]
    blocked = [row for row in classified if row["blocked"]]

    mapping_counts = Counter(row["mapping"] for row in mapped)
    blocker_counts = Counter(
        reason
        for row in blocked
        for reason in row["reasons"]
    )

    existing_item_tax_conflicts = []
    already_targeted = []

    for row in mapped:
        item = frappe.get_doc("Item", row["item"])
        taxes = list(item.get("taxes") or [])
        if not taxes:
            continue

        if (
            len(taxes) == 1
            and str(taxes[0].item_tax_template or "") == row["template"]
            and not str(taxes[0].tax_category or "").strip()
            and not taxes[0].valid_from
            and not flt(taxes[0].minimum_net_rate)
            and not flt(taxes[0].maximum_net_rate)
        ):
            already_targeted.append(row["item"])
            continue

        existing_item_tax_conflicts.append(
            {
                "item": row["item"],
                "existing": [
                    {
                        "item_tax_template": tax.item_tax_template,
                        "tax_category": tax.tax_category or "",
                        "valid_from": tax.valid_from,
                        "minimum_net_rate": tax.minimum_net_rate,
                        "maximum_net_rate": tax.maximum_net_rate,
                    }
                    for tax in taxes
                ],
            }
        )

    if existing_item_tax_conflicts:
        frappe.throw(
            "Refusing to overwrite existing Item Tax assignments: "
            + ", ".join(row["item"] for row in existing_item_tax_conflicts)
        )

    if len(profiles) != EXPECTED_ACTIVE_PROFILES:
        frappe.throw(
            f"Active profile count changed: expected {EXPECTED_ACTIVE_PROFILES}, "
            f"found {len(profiles)}."
        )

    if len(mapped) != EXPECTED_MAPPED_PROFILES:
        frappe.throw(
            f"Safe mapping count changed: expected {EXPECTED_MAPPED_PROFILES}, "
            f"found {len(mapped)}."
        )

    if len(blocked) != EXPECTED_BLOCKED_PROFILES:
        frappe.throw(
            f"Blocked mapping count changed: expected {EXPECTED_BLOCKED_PROFILES}, "
            f"found {len(blocked)}."
        )

    return {
        "site": frappe.local.site,
        "company": COMPANY,
        "gst_account": GST_ACCOUNT,
        "read_only_preview": True,
        "active_profiles": len(profiles),
        "safe_mappings": len(mapped),
        "blocked_profiles": len(blocked),
        "mapping_counts": dict(sorted(mapping_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "already_targeted_items": sorted(already_targeted),
        "templates": {
            "standard_18": STANDARD_TEMPLATE,
            "zero_rated": ZERO_TEMPLATE,
            "exempt": EXEMPT_TEMPLATE,
        },
        "mapped": mapped,
        "blocked": blocked,
    }


def preview() -> dict:
    return build_plan()


def _template_spec(name: str) -> tuple[str, float, int]:
    specs = {
        STANDARD_TEMPLATE: (STANDARD_TITLE, 18.0, 0),
        ZERO_TEMPLATE: (ZERO_TITLE, 0.0, 0),
        EXEMPT_TEMPLATE: (EXEMPT_TITLE, 0.0, 1),
    }
    if name not in specs:
        frappe.throw(f"Unexpected native Item Tax Template target: {name}")
    return specs[name]


def _ensure_template(name: str) -> tuple[str, bool]:
    title, rate, not_applicable = _template_spec(name)

    if frappe.db.exists("Item Tax Template", name):
        doc = frappe.get_doc("Item Tax Template", name)
        if doc.company != COMPANY:
            frappe.throw(f"Existing Item Tax Template {name} belongs to another Company.")
        if cint(doc.disabled):
            frappe.throw(f"Existing Item Tax Template {name} is disabled.")
        if doc.title != title:
            frappe.throw(f"Existing Item Tax Template {name} has unexpected title.")
        if len(doc.taxes) != 1:
            frappe.throw(f"Existing Item Tax Template {name} must have exactly one tax row.")

        tax = doc.taxes[0]
        if tax.tax_type != GST_ACCOUNT:
            frappe.throw(f"Existing Item Tax Template {name} has unexpected Tax Account.")
        if abs(flt(tax.tax_rate) - rate) > 0.000001:
            frappe.throw(f"Existing Item Tax Template {name} has unexpected rate.")
        if cint(tax.not_applicable) != not_applicable:
            frappe.throw(
                f"Existing Item Tax Template {name} has unexpected not-applicable state."
            )
        return name, False

    doc = frappe.get_doc(
        {
            "doctype": "Item Tax Template",
            "title": title,
            "company": COMPANY,
            "disabled": 0,
            "taxes": [
                {
                    "tax_type": GST_ACCOUNT,
                    "tax_rate": rate,
                    "not_applicable": not_applicable,
                }
            ],
        }
    )
    doc.insert(ignore_permissions=True)

    if doc.name != name:
        frappe.throw(
            f"ERPNext generated unexpected Item Tax Template name {doc.name!r}; "
            f"expected {name!r}."
        )

    return doc.name, True


def apply() -> dict:
    _assert_safe_site()

    plan = build_plan()

    created_templates = []
    reused_templates = []

    try:
        for template_name in (
            STANDARD_TEMPLATE,
            ZERO_TEMPLATE,
            EXEMPT_TEMPLATE,
        ):
            _, created = _ensure_template(template_name)
            if created:
                created_templates.append(template_name)
            else:
                reused_templates.append(template_name)

        changed_items = []
        unchanged_items = []

        for row in plan["mapped"]:
            item = frappe.get_doc("Item", row["item"])
            taxes = list(item.get("taxes") or [])

            if taxes:
                if (
                    len(taxes) == 1
                    and str(taxes[0].item_tax_template or "") == row["template"]
                    and not str(taxes[0].tax_category or "").strip()
                    and not taxes[0].valid_from
                    and not flt(taxes[0].minimum_net_rate)
                    and not flt(taxes[0].maximum_net_rate)
                ):
                    unchanged_items.append(item.name)
                    continue

                frappe.throw(
                    f"Refusing to overwrite existing Item Tax assignment on {item.name}."
                )

            item.append(
                "taxes",
                {
                    "item_tax_template": row["template"],
                    "tax_category": "",
                },
            )
            item.save(ignore_permissions=True)
            changed_items.append(item.name)

        frappe.db.commit()

    except Exception:
        frappe.db.rollback()
        raise

    verification = verify()

    return {
        "site": frappe.local.site,
        "applied": True,
        "created_templates": sorted(created_templates),
        "reused_templates": sorted(reused_templates),
        "changed_items": sorted(changed_items),
        "unchanged_items": sorted(unchanged_items),
        "blocked_profiles_untouched": [
            {
                "profile": row["profile"],
                "item": row["item"],
                "reasons": row["reasons"],
            }
            for row in plan["blocked"]
        ],
        "verification": verification,
    }


def verify() -> dict:
    _assert_safe_site()

    plan = build_plan()

    expected_by_item = {
        row["item"]: row["template"]
        for row in plan["mapped"]
    }

    problems = []

    for item_code, template_name in sorted(expected_by_item.items()):
        item = frappe.get_doc("Item", item_code)
        taxes = list(item.get("taxes") or [])
        if len(taxes) != 1:
            problems.append(
                f"{item_code}: expected exactly one Item Tax row, found {len(taxes)}"
            )
            continue
        tax = taxes[0]
        if tax.item_tax_template != template_name:
            problems.append(
                f"{item_code}: expected {template_name}, found {tax.item_tax_template}"
            )

    blocked_items = {
        row["item"]
        for row in plan["blocked"]
        if row["item"]
    }
    blocked_with_tax = []
    for item_code in sorted(blocked_items):
        item = frappe.get_doc("Item", item_code)
        if item.get("taxes"):
            blocked_with_tax.append(item_code)

    for template_name in (
        STANDARD_TEMPLATE,
        ZERO_TEMPLATE,
        EXEMPT_TEMPLATE,
    ):
        if not frappe.db.exists("Item Tax Template", template_name):
            problems.append(f"Missing Item Tax Template {template_name}")

    assignment_rows = frappe.get_all(
        "Item Tax",
        fields=["parent", "item_tax_template", "tax_category"],
        filters={"parenttype": "Item"},
        limit_page_length=0,
    )

    ledgix_assignments = [
        dict(row)
        for row in assignment_rows
        if row.item_tax_template
        in {STANDARD_TEMPLATE, ZERO_TEMPLATE, EXEMPT_TEMPLATE}
    ]

    if len(ledgix_assignments) != EXPECTED_MAPPED_PROFILES:
        problems.append(
            "Expected "
            f"{EXPECTED_MAPPED_PROFILES} Ledgix native Item Tax assignments, "
            f"found {len(ledgix_assignments)}."
        )

    if blocked_with_tax:
        problems.append(
            "Blocked complex/review items unexpectedly received Item Tax assignments: "
            + ", ".join(blocked_with_tax)
        )

    if problems:
        frappe.throw(
            "Native tax adoption verification failed:\n- "
            + "\n- ".join(problems)
        )

    return {
        "valid": True,
        "native_item_tax_assignments": len(ledgix_assignments),
        "blocked_items_with_tax_assignments": blocked_with_tax,
        "templates_present": [
            STANDARD_TEMPLATE,
            ZERO_TEMPLATE,
            EXEMPT_TEMPLATE,
        ],
        "mapping_counts": plan["mapping_counts"],
        "blocked_profiles": plan["blocked_profiles"],
    }
