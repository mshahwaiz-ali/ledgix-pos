"""Federal V1 lifecycle. Durable intent precedes every possible send."""
import uuid
import frappe
from frappe.utils import cint, now_datetime
from fbr_v1.protocol import transport
from fbr_v1.protocol.response import parse_fiscal_response
from fbr_v1.services.pos_identity import PROTOCOL, get_profile, profile_active, is_consolidated
from fbr_v1.services.fbr_v1_readiness import inspect_invoice
from fbr_v1.services.fbr_v1_payload_builder import digest
from fbr_v1.services.fbr_submission_support import submission_lock, create_submission_log, sanitize

LOG = "Ledgix FBR Submission Log"


def require_operator():
    if not set(frappe.get_roles()).intersection({"System Manager", "Accounts Manager"}):
        frappe.throw("Accounts Manager permission is required.", frappe.PermissionError)


def source(doctype, name, permission="read"):
    if doctype not in {"Sales Invoice", "POS Invoice"}:
        frappe.throw("Select Sales Invoice or POS Invoice.")
    doc = frappe.get_doc(doctype, name)
    doc.check_permission(permission)
    return doc


def mark(doc, status, **values):
    fields = {"custom_ledgix_fbr_status": status, **values}
    frappe.db.set_value(doc.doctype, doc.name, fields, update_modified=False)
    doc.update(fields)


def history(doc):
    return frappe.get_all(LOG, filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
        fields=["name", "protocol", "fbr_status", "fbr_invoice_number", "transport_outcome", "attempt_id"],
        order_by="creation asc", limit_page_length=0)


def history_blocker(doc, rows):
    number = doc.get("custom_ledgix_fbr_invoice_number") or next(
        (r.get("fbr_invoice_number") for r in rows if r.get("fbr_invoice_number")), "")
    if number:
        return {"status": "Already Submitted", "invoice_number": number, "network_call": False}
    # An Ambiguous intent has a matching terminal row only after durable completion.
    completed = {r.get("attempt_id") for r in rows if r.get("transport_outcome") in {"Accepted", "Rejected"}}
    if any(r.get("transport_outcome") == "Ambiguous" and r.get("attempt_id") not in completed for r in rows):
        return {"status": "Reconciliation Required", "network_call": False}
    if any(r.get("protocol") != PROTOCOL and r.get("fbr_status") in {"Submitted", "Reconciliation Required"} for r in rows):
        return {"status": "Reconciliation Required", "network_call": False}
    if doc.get("custom_ledgix_fbr_reconciliation_required") or doc.get("custom_ledgix_fbr_status") == "Reconciliation Required":
        return {"status": "Reconciliation Required", "network_call": False}
    return None


def classify_result(result):
    status = result.get("http_status") or 0
    body = result.get("body")
    parsed = parse_fiscal_response(body)

    if 200 <= status < 300 and parsed.success:
        return "Submitted", "Accepted", parsed.invoice_number

    # Observed FBR Sandbox/API-gateway rejection. This response is explicit
    # and terminal for the current attempt; it is not an uncertain transport
    # outcome. Keep this narrow because the complete external error catalogue
    # remains intentionally unresolved.
    fault = body.get("fault") if isinstance(body, dict) else None
    fault_code = (
        str(fault.get("code") or "").strip()
        if isinstance(fault, dict)
        else ""
    )
    if 200 <= status < 500 and fault_code == "900908":
        return "Failed", "Rejected", ""

    if 200 <= status < 500 and parsed.code and parsed.code != "100":
        return "Failed", "Rejected", ""

    return "Reconciliation Required", "Ambiguous", ""


def submit_internal(doctype, name):
    doc = source(doctype, name, "submit")
    if cint(doc.docstatus) != 1 or is_consolidated(doc):
        frappe.throw("Fiscalization requires a submitted native source, not a POS consolidation.")
    with submission_lock(f"{doctype}:{name}"):
        doc.reload()
        rows = history(doc)
        blocked = history_blocker(doc, rows)
        if blocked:
            return blocked
        ready = inspect_invoice(doc)
        if not ready["network_ready"]:
            return {"status": "Not Attempted", "network_call": False,
                    "errors": ready["errors"] + ready["network_blockers"]}
        # Defense in depth, including against accidental readiness regressions.
        if not transport.network_cutover_active():
            frappe.throw("V1 network cutover is disabled.")
        payload = ready["invoice"].to_payload()
        profile, device = ready["profile"], ready["device"]
        attempt = str(uuid.uuid4())
        snapshot_hash = ready["snapshot"]["snapshot_hash"]
        evidence = dict(protocol=PROTOCOL, pos_device=device["name"], attempt_id=attempt,
            idempotency_key=digest([doctype, name, snapshot_hash]), source_snapshot_hash=snapshot_hash,
            request_hash=digest(payload), operator=frappe.session.user, transport_started_at=now_datetime())
        create_submission_log(doctype, name, "Credit Note" if doc.get("is_return") else "Sale Invoice",
            "Reconciliation Required", request_json=payload, transport_outcome="Ambiguous",
            reconciliation_required=1, **evidence)
        mark(doc, "Reconciliation Required", custom_ledgix_fbr_reconciliation_required=1)
        # A crash after this commit must NEVER cause a blind retransmission.
        frappe.db.commit()
        token = ""
        attempted = False
        try:
            if device["transport_topology"] == "Cloud API":
                field = "v1_production_token" if profile.mode == "Production" else "v1_sandbox_token"
                token = profile.get_password(field, raise_exception=False)
                attempted = True
                result = transport.post_cloud(payload, token=token, environment=profile.mode)
            else:
                attempted = True
                result = transport.post_local(payload, environment=profile.mode)
            status, outcome, number = classify_result(result)
            response = sanitize(result.get("body"), (token,))
        except transport.TransportUnavailable:
            attempted = False
            status, outcome, number = "Failed", "Rejected", ""
            response = {"error": "Definite pre-send transport refusal."}
        except Exception:
            # Do not persist exception text: requests exceptions can contain credentials.
            if attempted:
                status, outcome, number = "Reconciliation Required", "Ambiguous", ""
                response = {"error": "Uncertain transport outcome; operator reconciliation required."}
            else:
                status, outcome, number = "Failed", "Rejected", ""
                response = {"error": "Definite pre-send failure."}
        log = create_submission_log(doctype, name, "Credit Note" if doc.get("is_return") else "Sale Invoice",
            status, request_json=payload, response_json=response, fbr_invoice_number=number,
            transport_outcome=outcome, response_hash=digest(response), transport_finished_at=now_datetime(),
            reconciliation_required=int(outcome == "Ambiguous"), **evidence)
        values = dict(custom_ledgix_fbr_reconciliation_required=int(outcome == "Ambiguous"),
                      custom_ledgix_fbr_submission_log=log)
        if number:
            values.update(custom_ledgix_fbr_invoice_number=number, custom_ledgix_fbr_submitted_at=now_datetime())
            frappe.db.set_value("Ledgix FBR POS Device", device["name"], "last_successful_fiscalization", now_datetime())
        mark(doc, status, **values)
        frappe.db.commit()
        return {"status": status, "invoice_number": number, "log": log, "network_call": attempted}


@frappe.whitelist()
def submit_invoice(reference_doctype, reference_name):
    require_operator()
    return submit_internal(reference_doctype, reference_name)


@frappe.whitelist()
def invoice_readiness(reference_doctype, reference_name):
    ready = inspect_invoice(source(reference_doctype, reference_name))
    return {k: ready[k] for k in ("ready", "network_ready", "errors", "network_blockers", "unresolved_contracts")}


@frappe.whitelist()
def get_invoice_fiscal_state(reference_doctype, reference_name):
    """Read current fiscal wait/print state without transport or mutation."""

    from fbr_v1.api.printing import get_invoice_fiscal_print_state

    state = get_invoice_fiscal_print_state(
        source(reference_doctype, reference_name, "read")
    )
    return {**state, "network_call": False}


def on_native_invoice_submit(doc, method=None):
    if is_consolidated(doc) or not profile_active(get_profile(doc.company)):
        return
    if doc.get("is_return"):
        from fbr_v1.api.fbr_offline import append_event
        append_event(doc.get("custom_ledgix_fbr_pos_device"), "Credit Note",
                     {"return_against": doc.get("return_against")}, doctype=doc.doctype, name=doc.name)
    if frappe.db.get_value("Ledgix FBR POS Device", doc.get("custom_ledgix_fbr_pos_device"), "operational_state") == "Offline":
        from fbr_v1.api.fbr_offline import offline_invoice
        offline_invoice(doc)
        return
    mark(doc, "Pending")
    create_submission_log(doc.doctype, doc.name, "Credit Note" if doc.get("is_return") else "Sale Invoice",
                          "Pending", transport_outcome="Not Attempted",
                          source_snapshot_hash=doc.get("custom_ledgix_fbr_snapshot_hash"),
                          pos_device=doc.get("custom_ledgix_fbr_pos_device"))
    profile = get_profile(doc.company)
    if (transport.network_cutover_active() and profile.get("submit_trigger") == "On Submit"
            and (profile.mode != "Production" or transport.production_cutover_active())):
        frappe.db.after_commit.add(lambda: frappe.enqueue(
            "fbr_v1.api.fiscalization.submit_internal", doctype=doc.doctype, name=doc.name))


def cancellation_requires_credit(doc, rows):
    if doc.get("custom_ledgix_fbr_invoice_number"):
        return True

    completed = {
        r.get("attempt_id")
        for r in rows
        if r.get("transport_outcome") in {"Accepted", "Rejected"}
    }

    if any(
        r.get("transport_outcome") == "Ambiguous"
        and r.get("attempt_id") not in completed
        for r in rows
    ):
        return True

    if any(r.get("transport_outcome") in {"Accepted", "Offline Deferred"} for r in rows):
        return True

    if any(
        r.get("protocol") != PROTOCOL
        and r.get("fbr_status") in {"Submitted", "Reconciliation Required", "Offline Pending"}
        for r in rows
    ):
        return True

    if doc.get("custom_ledgix_fbr_reconciliation_required"):
        return True

    return doc.get("custom_ledgix_fbr_status") in {
        "Submitted",
        "Reconciliation Required",
        "Offline Pending",
    }


def block_cancel_after_fbr_submission(doc, method=None):
    rows = history(doc)
    if cancellation_requires_credit(doc, rows):
        device = doc.get("custom_ledgix_fbr_pos_device")
        if device:
            # The rejected cancellation rolls back its transaction. Persist only
            # the audit event afterward, without committing the attempted cancel.
            def record_attempt():
                from fbr_v1.api.fbr_offline import append_event
                append_event(device, "Cancellation Attempt", {"blocked": True},
                             doctype=doc.doctype, name=doc.name)
                frappe.db.commit()
            frappe.db.after_rollback.add(record_attempt)
        frappe.throw(
            "Fiscal history is retained. Use a native linked credit/return "
            "and reconciliation; cancellation is blocked."
        )
