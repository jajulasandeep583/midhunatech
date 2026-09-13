# Copyright (c) 2026, Midhunatech and Contributors
# License: GPL-3.0
"""End-to-end smoke test of the native mobile screens' backend.

Run:  bench --site <site> execute midhunatech.smoke.run
Creates (idempotently) one test Item / Customer / Supplier and one draft
Quotation, Sales Order, Sales Invoice and Purchase Invoice through the SAME
API the PWA create form uses (get_create_meta + create_doc), then prints a
PASS/FAIL line per screen. The drafts stay so they're visible in the app.
"""

import frappe
from frappe.utils import nowdate, add_days

from midhunatech.api.data import get_view, get_create_meta, create_doc

TILES = [
    ("Item", None), ("Customer", None), ("Quotation", None),
    ("Sales Order", None), ("Sales Invoice", None),
    ("Purchase Invoice", None), ("Expense Claim", None),
]


def _ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        return name
    doc = frappe.get_doc({"doctype": doctype, **values})
    doc.insert(ignore_permissions=True)
    return doc.name


def run():
    frappe.set_user("Administrator")
    ok, fail = [], []

    # ── masters used by the transaction drafts ──
    item_values = {
        "item_code": "MT-TEST-ITEM", "item_name": "MT Test Item",
        "item_group": frappe.db.get_value("Item Group", {"is_group": 0}) or "All Item Groups",
        "stock_uom": "Nos", "is_stock_item": 0, "standard_rate": 100,
    }
    if frappe.db.exists("DocType", "GST HSN Code"):  # india_compliance sites
        hsn = frappe.db.get_value("GST HSN Code", {}) or _ensure(
            "GST HSN Code", "84131091", {"hsn_code": "84131091", "description": "Pumps"})
        item_values["gst_hsn_code"] = hsn
    item = _ensure("Item", "MT-TEST-ITEM", item_values)
    customer = _ensure("Customer", "MT Test Customer", {"customer_name": "MT Test Customer"})
    supplier = _ensure("Supplier", "MT Test Supplier", {"supplier_name": "MT Test Supplier"})
    frappe.db.commit()

    # ── every tile's list view + create meta ──
    for doctype, _ in TILES:
        try:
            v = get_view(doctype)
            m = get_create_meta(doctype)
            status = "creatable" if m.get("creatable") else f"NOT creatable: {m.get('reason')}"
            ok.append(f"{doctype}: view ok ({len(v.get('cards', []))} cards), {status}")
        except Exception as e:
            fail.append(f"{doctype}: {e}")

    # Quotation must expose party_name as a Link to Customer
    try:
        qm = get_create_meta("Quotation")
        pn = next((f for f in qm["fields"] if f["fieldname"] == "party_name"), None)
        assert pn and pn["fieldtype"] == "Link" and pn["options"] == "Customer", pn
        assert qm.get("child") and qm["child"]["fieldname"] == "items"
        ok.append("Quotation meta: party_name → Link(Customer), items editor present")
    except Exception as e:
        fail.append(f"Quotation meta: {e}")

    # ── create one draft of each through the PWA endpoint ──
    line = [{"item_code": item, "qty": 2, "rate": 150}]
    for doctype, values in [
        ("Quotation",        {"quotation_to": "Customer", "party_name": customer,
                              "transaction_date": nowdate(), "items": line}),
        ("Sales Order",      {"customer": customer, "transaction_date": nowdate(),
                              "delivery_date": add_days(nowdate(), 7), "items": line}),
        ("Sales Invoice",    {"customer": customer, "posting_date": nowdate(), "items": line}),
        ("Purchase Invoice", {"supplier": supplier, "posting_date": nowdate(), "items": line}),
    ]:
        try:
            res = create_doc(doctype, values)
            ok.append(f"created {doctype}: {res['name']}")
        except Exception as e:
            frappe.db.rollback()
            fail.append(f"create {doctype}: {frappe.get_traceback().splitlines()[-1]}")

    print("\n".join("  [OK]   " + s for s in ok))
    if fail:
        print("\n".join("  [FAIL] " + s for s in fail))
    print(f"\n{len(ok)} passed, {len(fail)} failed.")
    return {"passed": len(ok), "failed": len(fail)}
