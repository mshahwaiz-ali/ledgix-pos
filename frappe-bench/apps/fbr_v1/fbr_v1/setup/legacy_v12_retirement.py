"""Retire only exact historical Desk identities; preserve fiscal evidence."""
import frappe

# Workspace child rows can dynamically link to the Page. Retire that exact
# owned workspace first so normal Frappe link checks remain enabled.
TARGETS = (("Workspace", "FBR V1.2"), ("Page", "fbr-v12-center"))


def retire_legacy_desk_metadata():
    # Preflight every target before changing anything. Never infer ownership
    # from a name fragment or remove shared current Print Formats.
    found = []
    for doctype, name in TARGETS:
        if not frappe.db.exists(doctype, name):
            continue
        doc = frappe.get_doc(doctype, name)
        if doc.module != "FBR V12" or (doctype == "Page" and doc.title != "FBR V1.2 Center"):
            frappe.throw(f"Retired Desk identity {doctype} {name} has unexpected ownership; retirement blocked.")
        found.append((doctype, name))
    for doctype, name in found:
        frappe.delete_doc(doctype, name, ignore_permissions=True)
    return {"retired": len(found), "network_call": False}
