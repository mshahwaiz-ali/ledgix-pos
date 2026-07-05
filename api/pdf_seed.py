"""Thin wrapper so bench can seed PDF demo data."""
import importlib.util
from pathlib import Path

import frappe


@frappe.whitelist()
def seed_pdf_demo_data():
    frappe.only_for(("System Manager", "Ledgix Admin"))
    path = Path(__file__).resolve().parents[4] / "pdf" / "tools" / "seed_demo_data.py"
    spec = importlib.util.spec_from_file_location("ledgix_pdf_seed", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run()
