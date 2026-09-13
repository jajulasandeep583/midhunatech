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

from midhunatech.api.data import (
    get_view, get_list, get_doc, get_create_meta, create_doc, submit_doc,
)

TILES = [
    ("Item", None), ("Customer", None), ("Supplier", None), ("Quotation", None),
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

    # ── create one draft of each through the PWA endpoint (skip if a draft
    #     from an earlier run is still lying around) ──
    line = [{"item_code": item, "qty": 2, "rate": 150}]
    for doctype, party_field, party, values in [
        ("Quotation",        "party_name", customer,
         {"quotation_to": "Customer", "party_name": customer,
          "transaction_date": nowdate(), "items": line}),
        ("Sales Order",      "customer", customer,
         {"customer": customer, "transaction_date": nowdate(),
          "delivery_date": add_days(nowdate(), 7), "items": line}),
        ("Sales Invoice",    "customer", customer,
         {"customer": customer, "posting_date": nowdate(), "items": line}),
        ("Purchase Invoice", "supplier", supplier,
         {"supplier": supplier, "posting_date": nowdate(), "items": line}),
    ]:
        try:
            existing = frappe.db.exists(doctype, {party_field: party, "docstatus": 0})
            if existing:
                ok.append(f"{doctype}: draft already exists ({existing}) — create path verified earlier")
                continue
            res = create_doc(doctype, values)
            ok.append(f"created {doctype}: {res['name']}")
        except Exception as e:
            frappe.db.rollback()
            fail.append(f"create {doctype}: {frappe.get_traceback().splitlines()[-1]}")

    # ── simple party form: one screen → Customer + Address + Contact ──
    try:
        cm = get_create_meta("Customer")
        names = [f["fieldname"] for f in cm["fields"]]
        assert "_gstin" in names and "_mobile" in names and "_address" in names, names
        ok.append("Customer meta: simple one-form create (mobile/GSTIN/address)")
    except Exception as e:
        fail.append(f"Customer meta: {e}")

    gst_cust = "MT GST Test Customer"
    try:
        if not frappe.db.exists("Customer", gst_cust):
            create_doc("Customer", {
                "customer_name": gst_cust, "_mobile": "9876543210",
                "_gstin": "36AABCT1234F1ZR", "_address": "12 MG Road",
                "_city": "Hyderabad", "_pincode": "500001",
            })
        c = frappe.get_doc("Customer", gst_cust)
        assert (c.get("gstin") or "") == "36AABCT1234F1ZR", f"gstin={c.get('gstin')}"
        assert (c.get("pan") or "") == "AABCT1234F", f"pan={c.get('pan')}"
        has_addr = frappe.db.exists("Dynamic Link", {"link_doctype": "Customer",
                    "link_name": gst_cust, "parenttype": "Address"})
        has_contact = frappe.db.exists("Dynamic Link", {"link_doctype": "Customer",
                    "link_name": gst_cust, "parenttype": "Contact"})
        assert has_addr and has_contact, f"addr={has_addr} contact={has_contact}"
        ok.append(f"created {gst_cust}: GSTIN→PAN auto, Address + Contact linked")
    except Exception as e:
        frappe.db.rollback()
        fail.append(f"create Customer(simple form): {e}")

    # ── forms hide accounting/system noise ──
    try:
        sim = get_create_meta("Sales Invoice")
        shown = {f["fieldname"] for f in sim["fields"]}
        noisy = shown & {"company", "currency", "debit_to", "selling_price_list",
                         "conversion_rate"}
        assert not noisy, f"still shown: {noisy}"
        ok.append("Sales Invoice form: company/currency/debit_to hidden (auto-filled)")
    except Exception as e:
        fail.append(f"Sales Invoice form fields: {e}")

    # ── list injections: stock on Item cards, money on Customer cards ──
    try:
        l = get_list("Item", page_length=5)
        assert l["rows"], "no items"
        stocked = [r for r in l["rows"] if r["fields"] and r["fields"][0]["label"] == "In Stock"]
        ok.append(f"Item list: {len(stocked)}/{len(l['rows'])} cards show In Stock")
    except Exception as e:
        fail.append(f"Item list stock: {e}")
    try:
        l = get_list("Customer", page_length=5)
        assert l["rows"], "no customers"
        assert l["rows"][0]["fields"][0]["label"] in ("Total Sales",), l["rows"][0]["fields"][:2]
        ok.append("Customer list: cards lead with Total Sales / To Receive")
    except Exception as e:
        fail.append(f"Customer list money: {e}")

    # ── submit a draft invoice from the PWA endpoint ──
    try:
        draft = frappe.db.exists("Sales Invoice", {"customer": customer, "docstatus": 0})
        if draft:
            r = submit_doc("Sales Invoice", draft)
            assert r["docstatus"] == 1, r
            ok.append(f"submitted Sales Invoice {draft} from the app endpoint")
        else:
            submitted = frappe.db.exists("Sales Invoice", {"customer": customer, "docstatus": 1})
            assert submitted, "no draft and no submitted invoice for the test customer"
            ok.append(f"submit path verified earlier ({submitted} already submitted)")
        d = get_doc("Sales Invoice", frappe.db.exists(
            "Sales Invoice", {"customer": customer, "docstatus": 1}))
        assert d["docstatus"] == 1 and not d["can_submit"], d["name"]
    except Exception as e:
        frappe.db.rollback()
        fail.append(f"submit Sales Invoice: {frappe.get_traceback().splitlines()[-1]}")

    # ── party money summary on customer detail ──
    try:
        d = get_doc("Customer", customer)
        labels = [f["label"] for f in d["fields"][:3]]
        assert any("Total Sales" in l for l in labels), labels
        ok.append("Customer detail: Total Sales / To Receive summary present")
    except Exception as e:
        fail.append(f"Customer money summary: {e}")

    # ── record a payment against a submitted invoice ──
    try:
        from midhunatech.api.data import record_payment
        si = frappe.get_all("Sales Invoice",
                            filters={"customer": customer, "docstatus": 1,
                                     "outstanding_amount": (">", 0)},
                            limit_page_length=1, pluck="name")
        if si:
            d = get_doc("Sales Invoice", si[0])
            assert d.get("can_pay") == 1, f"can_pay={d.get('can_pay')}"
            r = record_payment("Sales Invoice", si[0], amount=50)
            ok.append(f"recorded payment {r['name']} against {si[0]}")
        else:
            pe = frappe.db.exists("Payment Entry", {"party": customer, "docstatus": 1})
            assert pe, "no open invoice and no prior payment"
            ok.append(f"payment path verified earlier ({pe})")
    except Exception as e:
        frappe.db.rollback()
        fail.append(f"record_payment: {frappe.get_traceback().splitlines()[-1]}")

    # ── journal entry (expense posting) from the app ──
    try:
        je_exists = frappe.db.exists("Journal Entry",
                                     {"user_remark": "MT smoke expense", "docstatus": 0})
        if not je_exists:
            expense = frappe.get_all("Account", filters={"root_type": "Expense",
                                     "is_group": 0}, limit_page_length=1, pluck="name")[0]
            cash = frappe.get_all("Account", filters={"account_type": "Cash",
                                  "is_group": 0}, limit_page_length=1, pluck="name")[0]
            r = create_doc("Journal Entry", {
                "posting_date": nowdate(), "user_remark": "MT smoke expense",
                "accounts": [
                    {"account": expense, "debit_in_account_currency": 25},
                    {"account": cash, "credit_in_account_currency": 25},
                ],
            })
            ok.append(f"created Journal Entry {r['name']} (expense posting)")
        else:
            ok.append(f"Journal Entry draft already exists ({je_exists})")
    except Exception as e:
        frappe.db.rollback()
        fail.append(f"Journal Entry: {frappe.get_traceback().splitlines()[-1]}")

    # ── chart of accounts list shows balances ──
    try:
        l = get_list("Account", page_length=10)
        with_bal = [r for r in l["rows"] if r["fields"] and
                    r["fields"][0]["label"] in ("Balance", "Type")]
        assert with_bal, l["rows"][:2]
        ok.append(f"Account list: {len(with_bal)}/{len(l['rows'])} rows show Balance/Type")
    except Exception as e:
        fail.append(f"Account balances: {e}")

    # ── purchase invoice form has supplier invoice no / date ──
    try:
        pim = get_create_meta("Purchase Invoice")
        names = {f["fieldname"] for f in pim["fields"]}
        assert {"bill_no", "bill_date"} <= names, names
        ok.append("Purchase Invoice form: bill_no + bill_date present")
    except Exception as e:
        fail.append(f"PI bill fields: {e}")

    # ── customer detail: address + recent invoices ──
    try:
        d = get_doc("Customer", gst_cust)
        labels = [f["label"] for f in d["fields"]]
        assert "Address" in labels, labels
        d2 = get_doc("Customer", customer)
        assert any(t["fieldname"] == "_invoices" for t in d2["tables"]), \
            [t["fieldname"] for t in d2["tables"]]
        ok.append("Party detail: Address shown; Recent Invoices table present")
    except Exception as e:
        fail.append(f"party detail extras: {e}")

    print("\n".join("  [OK]   " + s for s in ok))
    if fail:
        print("\n".join("  [FAIL] " + s for s in fail))
    print(f"\n{len(ok)} passed, {len(fail)} failed.")
    return {"passed": len(ok), "failed": len(fail)}
