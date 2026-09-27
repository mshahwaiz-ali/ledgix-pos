"""Deterministic internal fiscal evidence, never an external closing API."""
import calendar
import json
from datetime import timedelta
import frappe
from frappe.utils import getdate, now_datetime
from fbr_v1.api.fiscalization import require_operator, history, history_blocker
from fbr_v1.services.fbr_submission_support import submission_lock
from fbr_v1.services.fbr_v1_payload_builder import digest, number
from fbr_v1.services.pos_identity import is_consolidated
from fbr_v1.api.fbr_offline import append_event


def period_bounds(period_type, date):
    date = getdate(date)
    if period_type == "Daily":
        return date, date
    if period_type == "Weekly":
        start = date - timedelta(days=date.weekday())
        return start, start + timedelta(days=6)
    if period_type == "Monthly":
        return date.replace(day=1), date.replace(day=calendar.monthrange(date.year, date.month)[1])
    raise ValueError("Period type must be Daily, Weekly or Monthly.")


@frappe.whitelist()
def generate_closing(pos_device, period_type, date):
    require_operator()
    device = frappe.get_doc("Ledgix FBR POS Device", pos_device)
    device.check_permission("write")
    start, end = period_bounds(period_type, date)
    if end >= getdate():
        frappe.throw("Only a completed calendar period may be closed internally.")
    key = digest([pos_device, period_type, str(start), str(end)])
    with submission_lock("closing:" + key):
        existing = frappe.db.get_value("Ledgix FBR Fiscal Closing", {"period_key": key}, "name")
        if existing:
            return {"name": existing, "reused": True, "network_call": False}
        manifest = []
        totals = {"net_total": number(0), "tax_total": number(0), "grand_total": number(0)}
        counts = {"invoice_count": 0, "fiscalized_count": 0, "offline_pending_count": 0, "reconciliation_required_count": 0}
        for dt in ("Sales Invoice", "POS Invoice"):
            names = frappe.get_all(dt, filters={"company": device.company, "docstatus": 1,
                "custom_ledgix_fbr_pos_device": pos_device, "posting_date": ["between", [start, end]]},
                pluck="name", order_by="name asc", limit_page_length=0)
            for name in names:
                doc = frappe.get_doc(dt, name)
                if is_consolidated(doc):
                    continue
                counts["invoice_count"] += 1
                rows = history(doc)
                blocker = history_blocker(doc, rows) or {}
                status = blocker.get("status") or doc.get("custom_ledgix_fbr_status")
                counts["fiscalized_count"] += int(status == "Already Submitted")
                counts["offline_pending_count"] += int(status == "Offline Pending")
                counts["reconciliation_required_count"] += int(status == "Reconciliation Required")
                amounts = {"net_total": doc.net_total, "tax_total": doc.total_taxes_and_charges, "grand_total": doc.grand_total}
                for k, value in amounts.items():
                    totals[k] += number(value)
                manifest.append({"doctype": dt, "name": name, "amounts": amounts, "fiscal_status": status,
                    "snapshot_hash": doc.get("custom_ledgix_fbr_snapshot_hash"), "attempt_logs": [r.name for r in rows]})
        body = {"pos_device": pos_device, "period_type": period_type, "period_start": str(start),
                "period_end": str(end), **counts, **{k: str(v) for k, v in totals.items()},
                "source_manifest_hash": digest(manifest)}
        closing = frappe.get_doc({"doctype": "Ledgix FBR Fiscal Closing", **body, "period_key": key,
            "source_manifest": json.dumps(manifest, sort_keys=True, default=str), "snapshot_hash": digest(body),
            "status": "Closed Internally", "external_status": "Unresolved", "generated_at": now_datetime(), "generated_by": frappe.session.user}).insert(ignore_permissions=True)
        device.db_set("last_" + period_type.lower() + "_closing", now_datetime())
        append_event(pos_device, "Closing", {"closing": closing.name, "snapshot_hash": closing.snapshot_hash})
        return {"name": closing.name, "reused": False, "network_call": False, "external_status": "Unresolved"}
