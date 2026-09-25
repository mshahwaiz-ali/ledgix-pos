from __future__ import annotations

"""Guarded physical retirement for obsolete Ledgix tax configuration masters.

The current authority is ERPNext monetary tax + Ledgix FBR V2 classification.
This patch physically removes only these obsolete configuration masters:

- Ledgix Tax Profile
- Ledgix Tax Category
- Ledgix Tax Rate
- Ledgix Item Tax Profile

Historical/legal evidence remains in:
- Ledgix Tax Audit Log
- Ledgix Invoice Tax Detail
- Ledgix Return Tax Detail

Existing sites require an explicit verified-backup authorization. Fresh sites
where no retired artifacts exist are a no-op and require no authorization.
No FBR network operation is performed.
"""

import hashlib

import frappe
from frappe.utils import cint, flt

from ledgix_saas.api.legacy_retirement import legacy_write_bypass


TARGET_DOCTYPES = (
    "Ledgix Tax Profile",
    "Ledgix Tax Category",
    "Ledgix Tax Rate",
    "Ledgix Item Tax Profile",
)

TABLE_DOCTYPES = (
    "Ledgix Tax Category",
    "Ledgix Tax Rate",
    "Ledgix Item Tax Profile",
)

AUDIT_DOCTYPE = "Ledgix Tax Audit Log"
RETIREMENT_STATE = "Ledgix Legacy Retirement State"
V2_PROFILE = "Ledgix FBR Integration Profile"
V2_MAPPING = "Ledgix FBR Item Mapping"

AUTHORIZATION_KEY = "ledgix_legacy_tax_config_cleanup_authorization"
AUTHORIZATION_VALUE = "VERIFIED_BACKUP_AND_APPROVED_LEGACY_TAX_CONFIG_CLEANUP"

VERSION_MARKER = "__frappe_version_snapshot__"


def _qi(value: str) -> str:
    return "`" + str(value).replace("`", "``") + "`"


def _table_exists(doctype: str) -> bool:
    return bool(
        frappe.db.sql(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name = %s
            """,
            (f"tab{doctype}",),
        )[0][0]
    )


def _column_exists(doctype: str, fieldname: str) -> bool:
    return bool(
        frappe.db.sql(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
              AND column_name = %s
            """,
            (f"tab{doctype}", fieldname),
        )[0][0]
    )


def _anything_remaining() -> bool:
    if any(frappe.db.exists("DocType", doctype) for doctype in TARGET_DOCTYPES):
        return True

    if any(_table_exists(doctype) for doctype in TABLE_DOCTYPES):
        return True

    if frappe.db.count("Singles", filters={"doctype": "Ledgix Tax Profile"}):
        return True

    return bool(_version_rows())


def _assert_authorized() -> None:
    value = str(frappe.conf.get(AUTHORIZATION_KEY) or "").strip()
    if value != AUTHORIZATION_VALUE:
        frappe.throw(
            "Legacy tax configuration cleanup is not authorized. Take and "
            "verify a fresh site backup first, then set site_config.json "
            f"{AUTHORIZATION_KEY}={AUTHORIZATION_VALUE!r} for the controlled "
            "migration only."
        )


def _assert_frozen() -> None:
    if not frappe.db.exists("DocType", RETIREMENT_STATE):
        frappe.throw("Legacy Retirement State is missing.")

    status = str(
        frappe.db.get_single_value(RETIREMENT_STATE, "status") or ""
    ).strip()
    if status != "Frozen":
        frappe.throw(
            f"Legacy retirement must be Frozen before physical tax-master "
            f"cleanup; got {status!r}."
        )


def _profile_rows() -> list[dict]:
    if not frappe.db.exists("DocType", V2_PROFILE):
        return []

    return [
        dict(row)
        for row in frappe.get_all(
            V2_PROFILE,
            fields=[
                "name",
                "enabled",
                "mode",
                "submit_trigger",
                "production_post_armed",
            ],
            limit_page_length=0,
        )
    ]


def _assert_v2_safe() -> None:
    profiles = _profile_rows()
    if not profiles:
        frappe.throw("FBR V2 Integration Profile is missing.")

    unsafe = [
        row
        for row in profiles
        if cint(row.get("enabled"))
        or str(row.get("mode") or "") != "Disabled"
        or str(row.get("submit_trigger") or "") != "Manual"
        or cint(row.get("production_post_armed"))
    ]
    if unsafe:
        frappe.throw(
            "Refusing legacy tax configuration cleanup unless every V2 "
            "profile is Disabled / Manual / unarmed: "
            + frappe.as_json([row.get("name") for row in unsafe])
        )


def _assert_snapshot_schema() -> None:
    required = (
        ("Ledgix Invoice Tax Detail", "tax_category"),
        ("Ledgix Return Tax Detail", "tax_category"),
        (AUDIT_DOCTYPE, "reference_doctype"),
        (AUDIT_DOCTYPE, "reference_name"),
    )

    for doctype, fieldname in required:
        if not frappe.db.exists("DocType", doctype):
            frappe.throw(f"Required historical evidence DocType missing: {doctype}")

        row = frappe.db.get_value(
            "DocField",
            {"parent": doctype, "fieldname": fieldname},
            ["fieldtype", "options"],
            as_dict=True,
        )
        if not row or row.fieldtype != "Data" or str(row.options or "").strip():
            frappe.throw(
                f"{doctype}.{fieldname} must be a detached Data snapshot "
                "before physical retirement."
            )


def _assert_no_customizations_on_targets() -> None:
    custom_fields = frappe.get_all(
        "Custom Field",
        filters={"dt": ["in", TARGET_DOCTYPES]},
        pluck="name",
        limit_page_length=0,
    )
    property_setters = frappe.get_all(
        "Property Setter",
        filters={"doc_type": ["in", TARGET_DOCTYPES]},
        pluck="name",
        limit_page_length=0,
    )
    if custom_fields or property_setters:
        frappe.throw(
            "Refusing physical retirement while target config masters have "
            "unreviewed customizations: "
            + frappe.as_json(
                {
                    "custom_fields": custom_fields,
                    "property_setters": property_setters,
                }
            )
        )


def _assert_no_external_static_links() -> None:
    blockers = []

    for row in frappe.get_all(
        "DocField",
        filters={
            "fieldtype": "Link",
            "options": ["in", TARGET_DOCTYPES],
            "parent": ["not in", TARGET_DOCTYPES],
        },
        fields=["parent", "fieldname", "options"],
        limit_page_length=0,
    ):
        blockers.append(
            {
                "kind": "DocField Link",
                "parent": row.parent,
                "fieldname": row.fieldname,
                "target": row.options,
            }
        )

    for row in frappe.get_all(
        "Custom Field",
        filters={
            "fieldtype": "Link",
            "options": ["in", TARGET_DOCTYPES],
            "dt": ["not in", TARGET_DOCTYPES],
        },
        fields=["dt", "fieldname", "options"],
        limit_page_length=0,
    ):
        blockers.append(
            {
                "kind": "Custom Field Link",
                "parent": row.dt,
                "fieldname": row.fieldname,
                "target": row.options,
            }
        )

    if blockers:
        frappe.throw(
            "External static Links to retired tax config masters remain: "
            + frappe.as_json(blockers)
        )


def _dynamic_reference_blockers() -> list[dict]:
    blockers = []

    fields = frappe.db.sql(
        """
        SELECT parent AS source_doctype, fieldname, options
        FROM `tabDocField`
        WHERE fieldtype='Dynamic Link'
        UNION
        SELECT dt AS source_doctype, fieldname, options
        FROM `tabCustom Field`
        WHERE fieldtype='Dynamic Link'
        ORDER BY 1,2
        """,
        as_dict=True,
    )

    for row in fields:
        doctype = str(row.source_doctype or "")
        link_field = str(row.fieldname or "")
        type_field = str(row.options or "")

        if not doctype or not link_field or not type_field:
            continue
        if doctype in TARGET_DOCTYPES:
            continue
        if not _table_exists(doctype):
            continue
        if not _column_exists(doctype, link_field):
            continue
        if not _column_exists(doctype, type_field):
            continue

        table = _qi(f"tab{doctype}")
        link_col = _qi(link_field)
        type_col = _qi(type_field)
        placeholders = ", ".join(["%s"] * len(TARGET_DOCTYPES))

        count = cint(
            frappe.db.sql(
                f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE (
                    {type_col} IN ({placeholders})
                    AND COALESCE(CAST({link_col} AS CHAR), '') <> ''
                )
                OR (
                    {type_col} = 'DocType'
                    AND {link_col} IN ({placeholders})
                )
                """,
                (*TARGET_DOCTYPES, *TARGET_DOCTYPES),
            )[0][0]
        )

        if count:
            blockers.append(
                {
                    "kind": "Dynamic Link",
                    "doctype": doctype,
                    "link_field": link_field,
                    "type_field": type_field,
                    "count": count,
                }
            )

    return blockers


def _doctype_link_reference_blockers(*, allow_version_rows: bool) -> list[dict]:
    blockers = []

    fields = frappe.db.sql(
        """
        SELECT parent AS source_doctype, fieldname
        FROM `tabDocField`
        WHERE fieldtype='Link' AND options='DocType'
        UNION
        SELECT dt AS source_doctype, fieldname
        FROM `tabCustom Field`
        WHERE fieldtype='Link' AND options='DocType'
        ORDER BY 1,2
        """,
        as_dict=True,
    )

    placeholders = ", ".join(["%s"] * len(TARGET_DOCTYPES))

    for row in fields:
        doctype = str(row.source_doctype or "")
        fieldname = str(row.fieldname or "")
        if not doctype or not fieldname:
            continue
        if not _table_exists(doctype) or not _column_exists(doctype, fieldname):
            continue

        table = _qi(f"tab{doctype}")
        field = _qi(fieldname)
        count = cint(
            frappe.db.sql(
                f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE {field} IN ({placeholders})
                """,
                TARGET_DOCTYPES,
            )[0][0]
        )
        if not count:
            continue

        if (
            allow_version_rows
            and doctype == "Version"
            and fieldname == "ref_doctype"
        ):
            continue

        blockers.append(
            {
                "kind": "Link to DocType",
                "doctype": doctype,
                "fieldname": fieldname,
                "count": count,
            }
        )

    return blockers


def _explicit_metadata_blockers() -> list[dict]:
    checks = (
        ("Workspace Link", "link_to"),
        ("Workspace Shortcut", "link_to"),
        ("Report", "ref_doctype"),
        ("Property Setter", "doc_type"),
        ("Property Setter", "value"),
    )
    blockers = []
    for doctype, fieldname in checks:
        if not _table_exists(doctype) or not _column_exists(doctype, fieldname):
            continue
        table = _qi(f"tab{doctype}")
        field = _qi(fieldname)
        placeholders = ", ".join(["%s"] * len(TARGET_DOCTYPES))
        count = cint(
            frappe.db.sql(
                f"""
                SELECT COUNT(*)
                FROM {table}
                WHERE {field} IN ({placeholders})
                """,
                TARGET_DOCTYPES,
            )[0][0]
        )
        if count:
            blockers.append(
                {
                    "kind": "Metadata reference",
                    "doctype": doctype,
                    "fieldname": fieldname,
                    "count": count,
                }
            )
    return blockers


def _assert_no_external_references(*, allow_version_rows: bool) -> None:
    _assert_no_external_static_links()

    blockers = []
    blockers.extend(_dynamic_reference_blockers())
    blockers.extend(
        _doctype_link_reference_blockers(
            allow_version_rows=allow_version_rows
        )
    )
    blockers.extend(_explicit_metadata_blockers())

    if blockers:
        frappe.throw(
            "Actual external references to retired tax config masters remain: "
            + frappe.as_json(blockers)
        )


def _norm_text(value) -> str:
    return str(value or "").strip()


def _norm_basis(value) -> str:
    return _norm_text(value) or "Transaction Value"


def _legacy_matches_v2(legacy: dict, current: dict) -> bool:
    text_pairs = (
        ("hs_code", "hs_code"),
        ("uom_for_fbr", "fbr_uom"),
        ("sales_type", "sales_type"),
        ("fbr_rate_description", "fbr_rate_description"),
        ("sro_schedule_number", "sro_schedule_number"),
        ("sro_item_serial_number", "sro_item_serial_number"),
    )

    for old_field, new_field in text_pairs:
        old_value = _norm_text(legacy.get(old_field))
        if old_value and old_value != _norm_text(current.get(new_field)):
            return False

    old_basis = _norm_basis(legacy.get("tax_basis"))
    if old_basis and old_basis != _norm_basis(current.get("tax_basis")):
        return False

    old_retail = flt(legacy.get("notified_retail_price"), 6)
    if old_retail and old_retail != flt(current.get("notified_retail_price"), 6):
        return False

    return True


def _assert_mapping_parity() -> None:
    if not _table_exists("Ledgix Item Tax Profile"):
        return

    if not _table_exists(V2_MAPPING):
        frappe.throw("FBR V2 Item Mapping table is missing.")

    legacy_rows = frappe.db.sql(
        """
        SELECT
            name,
            erpnext_item,
            hs_code,
            uom_for_fbr,
            sales_type,
            fbr_rate_description,
            tax_basis,
            notified_retail_price,
            sro_schedule_number,
            sro_item_serial_number
        FROM `tabLedgix Item Tax Profile`
        WHERE IFNULL(active,0)=1
        ORDER BY name
        """,
        as_dict=True,
    )

    current_rows = frappe.db.sql(
        """
        SELECT
            name,
            company,
            erpnext_item,
            hs_code,
            fbr_uom,
            sales_type,
            fbr_rate_description,
            tax_basis,
            notified_retail_price,
            sro_schedule_number,
            sro_item_serial_number,
            needs_review
        FROM `tabLedgix FBR Item Mapping`
        WHERE IFNULL(active,0)=1
        ORDER BY name
        """,
        as_dict=True,
    )

    by_item: dict[str, list[dict]] = {}
    for row in current_rows:
        item = _norm_text(row.erpnext_item)
        if item:
            by_item.setdefault(item, []).append(dict(row))

    seen_legacy_items = set()
    blockers = []

    for row in legacy_rows:
        legacy = dict(row)
        item = _norm_text(legacy.get("erpnext_item"))
        if not item:
            blockers.append(
                {
                    "legacy_name": legacy.get("name"),
                    "reason": "missing erpnext_item",
                }
            )
            continue

        if item in seen_legacy_items:
            blockers.append(
                {
                    "legacy_name": legacy.get("name"),
                    "erpnext_item": item,
                    "reason": "duplicate active legacy erpnext_item",
                }
            )
            continue
        seen_legacy_items.add(item)

        candidates = by_item.get(item) or []
        if not candidates:
            blockers.append(
                {
                    "legacy_name": legacy.get("name"),
                    "erpnext_item": item,
                    "reason": "no active V2 mapping",
                }
            )
            continue

        if not any(_legacy_matches_v2(legacy, candidate) for candidate in candidates):
            blockers.append(
                {
                    "legacy_name": legacy.get("name"),
                    "erpnext_item": item,
                    "reason": "legacy classification evidence not preserved in V2",
                    "candidate_names": [x.get("name") for x in candidates],
                }
            )

    if blockers:
        frappe.throw(
            "Legacy -> V2 item-classification parity failed: "
            + frappe.as_json(blockers)
        )


def _version_rows() -> list[dict]:
    if not _table_exists("Version"):
        return []

    placeholders = ", ".join(["%s"] * len(TARGET_DOCTYPES))
    return [
        dict(row)
        for row in frappe.db.sql(
            f"""
            SELECT
                name,
                ref_doctype,
                docname,
                owner,
                creation,
                modified,
                data
            FROM `tabVersion`
            WHERE ref_doctype IN ({placeholders})
               OR (
                    ref_doctype='DocType'
                    AND docname IN ({placeholders})
               )
            ORDER BY ref_doctype, docname, creation, name
            """,
            (*TARGET_DOCTYPES, *TARGET_DOCTYPES),
            as_dict=True,
        )
    ]


def _audit_marker_filter(version: dict) -> dict:
    return {
        "reference_doctype": _norm_text(version.get("ref_doctype")),
        "reference_name": _norm_text(version.get("docname")),
        "field_changed": VERSION_MARKER,
        "old_value": _norm_text(version.get("name")),
    }


def _migrate_versions_to_audit() -> list[dict]:
    versions = _version_rows()
    if not versions:
        return []

    if not frappe.db.exists("DocType", AUDIT_DOCTYPE):
        frappe.throw("Ledgix Tax Audit Log is missing.")

    migrated = []

    with legacy_write_bypass("Phase 9 physical tax-master retirement"):
        for version in versions:
            data = str(version.get("data") or "")
            digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
            marker = _audit_marker_filter(version)

            existing = frappe.db.get_value(
                AUDIT_DOCTYPE,
                marker,
                ["name", "new_value", "reason__note"],
                as_dict=True,
            )

            if existing:
                if str(existing.new_value or "") != data:
                    frappe.throw(
                        f"Existing audit migration for Version "
                        f"{version['name']} has different payload."
                    )
                migrated.append(
                    {
                        "version": version["name"],
                        "audit": existing.name,
                        "sha256": digest,
                    }
                )
                continue

            original_owner = _norm_text(version.get("owner"))
            changed_by = (
                original_owner
                if original_owner and frappe.db.exists("User", original_owner)
                else "Administrator"
            )

            doc = frappe.get_doc(
                {
                    "doctype": AUDIT_DOCTYPE,
                    "reference_doctype": marker["reference_doctype"],
                    "reference_name": marker["reference_name"],
                    "field_changed": VERSION_MARKER,
                    "old_value": marker["old_value"],
                    "new_value": data,
                    "changed_by": changed_by,
                    "changed_at": version.get("creation"),
                    "reason__note": (
                        "Phase 9 migrated Frappe Version before physical "
                        f"config-master retirement; source_version={version['name']}; "
                        f"source_sha256={digest}; original_owner={original_owner}"
                    ),
                }
            )
            doc.flags.ignore_permissions = True
            doc.insert()

            migrated.append(
                {
                    "version": version["name"],
                    "audit": doc.name,
                    "sha256": digest,
                }
            )

    for version in versions:
        marker = _audit_marker_filter(version)
        audit = frappe.db.get_value(
            AUDIT_DOCTYPE,
            marker,
            ["name", "new_value"],
            as_dict=True,
        )
        if not audit:
            frappe.throw(
                f"Version {version['name']} was not preserved in Tax Audit Log."
            )
        if str(audit.new_value or "") != str(version.get("data") or ""):
            frappe.throw(
                f"Version {version['name']} audit payload verification failed."
            )

    return migrated


def _delete_version_rows(versions: list[dict]) -> None:
    for row in versions:
        frappe.db.delete("Version", {"name": row["name"]})


def _delete_owned_metadata() -> None:
    frappe.db.delete("Custom DocPerm", {"parent": ["in", TARGET_DOCTYPES]})
    frappe.db.delete("DocPerm", {"parent": ["in", TARGET_DOCTYPES]})
    frappe.db.delete("Singles", {"doctype": "Ledgix Tax Profile"})


def _delete_doctype_metadata() -> None:
    for doctype in TARGET_DOCTYPES:
        if not frappe.db.exists("DocType", doctype):
            continue
        frappe.delete_doc(
            "DocType",
            doctype,
            force=True,
            ignore_permissions=True,
            for_reload=True,
            delete_permanently=True,
        )


def _drop_physical_tables() -> None:
    for doctype in TABLE_DOCTYPES:
        table = _qi(f"tab{doctype}")
        frappe.db.sql_ddl(f"DROP TABLE IF EXISTS {table}")


def _assert_retired() -> None:
    residual = {
        "doctypes": [
            doctype
            for doctype in TARGET_DOCTYPES
            if frappe.db.exists("DocType", doctype)
        ],
        "tables": [
            doctype for doctype in TABLE_DOCTYPES if _table_exists(doctype)
        ],
        "tax_profile_single_rows": frappe.db.count(
            "Singles",
            filters={"doctype": "Ledgix Tax Profile"},
        ),
        "version_rows": len(_version_rows()),
        "docperms": frappe.db.count(
            "DocPerm",
            filters={"parent": ["in", TARGET_DOCTYPES]},
        ),
        "custom_docperms": frappe.db.count(
            "Custom DocPerm",
            filters={"parent": ["in", TARGET_DOCTYPES]},
        ),
    }

    if (
        residual["doctypes"]
        or residual["tables"]
        or residual["tax_profile_single_rows"]
        or residual["version_rows"]
        or residual["docperms"]
        or residual["custom_docperms"]
    ):
        frappe.throw(
            "Legacy tax configuration physical retirement left residual data: "
            + frappe.as_json(residual)
        )

    _assert_no_external_references(allow_version_rows=False)


def preview_cleanup() -> dict:
    """Read-only preview of the guarded physical-retirement surface."""

    return {
        "targets": TARGET_DOCTYPES,
        "doctype_exists": {
            doctype: bool(frappe.db.exists("DocType", doctype))
            for doctype in TARGET_DOCTYPES
        },
        "table_exists": {
            doctype: _table_exists(doctype)
            for doctype in TABLE_DOCTYPES
        },
        "tax_profile_single_rows": frappe.db.count(
            "Singles",
            filters={"doctype": "Ledgix Tax Profile"},
        ),
        "version_rows": len(_version_rows()),
        "v2_profiles": _profile_rows(),
        "read_only": True,
        "database_write": False,
        "fbr_network_call": False,
    }


def execute() -> None:
    """Physically retire old tax config masters after all fail-closed gates."""

    if not _anything_remaining():
        _assert_no_customizations_on_targets()
        _assert_retired()
        return

    _assert_authorized()
    _assert_frozen()
    _assert_v2_safe()
    _assert_snapshot_schema()
    _assert_no_customizations_on_targets()
    _assert_mapping_parity()
    _assert_no_external_references(allow_version_rows=True)

    versions = _version_rows()
    _migrate_versions_to_audit()

    _delete_version_rows(versions)
    frappe.db.commit()

    _assert_no_external_references(allow_version_rows=False)

    _delete_owned_metadata()
    _delete_doctype_metadata()
    frappe.db.commit()

    _drop_physical_tables()

    for doctype in TARGET_DOCTYPES:
        frappe.clear_cache(doctype=doctype)
    frappe.clear_cache(doctype=AUDIT_DOCTYPE)

    _assert_retired()
