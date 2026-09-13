# Copyright (c) 2026, Midhunatech and Contributors
# License: GPL-3.0
"""Enable india_compliance e-Invoice SANDBOX mode for app testing.

Run:  bench --site <site> execute midhunatech.setup.gst_sandbox.setup

Idempotent. Turns on API + sandbox + e-Invoice in GST Settings, gives the
default company a GST-registered address with the standard NIC sandbox GSTIN
(05AAACG2115R1ZN, Uttarakhand) so invoices carry a company GSTIN, and seeds a
sandbox credential row. NOTE: actually generating an IRN additionally needs
an India Compliance account API secret (GST Settings → API → API Secret) —
free signup at india-compliance.app; without it the API call is rejected.
"""

import frappe

SANDBOX_GSTIN = "05AAACG2115R1ZN"   # NIC sandbox seller GSTIN (state 05)


def setup():
    company = (frappe.defaults.get_user_default("Company")
               or frappe.db.get_single_value("Global Defaults", "default_company"))
    if not company:
        print("No default company — aborting.")
        return

    # ── company address carrying the sandbox GSTIN ──
    title = f"{company} - GST Sandbox"
    addr_name = frappe.db.exists("Address", {"address_title": title})
    if not addr_name:
        addr = frappe.get_doc({
            "doctype": "Address", "address_title": title,
            "address_type": "Billing", "address_line1": "Sandbox Lane 1",
            "city": "Dehradun", "state": "Uttarakhand", "pincode": "248001",
            "country": "India", "gstin": SANDBOX_GSTIN,
            "gst_category": "Registered Regular",
            "is_your_company_address": 1, "is_primary_address": 1,
            "links": [{"link_doctype": "Company", "link_name": company}],
        })
        addr.insert(ignore_permissions=True)
        addr_name = addr.name
        print(f"Created company address {addr_name} with GSTIN {SANDBOX_GSTIN}")

    # company-level gstin field (india_compliance adds it)
    if frappe.get_meta("Company").has_field("gstin"):
        frappe.db.set_value("Company", company, "gstin", SANDBOX_GSTIN)

    # ── GST Settings: API + sandbox + e-invoice ──
    s = frappe.get_doc("GST Settings")
    s.enable_api = 1
    s.sandbox_mode = 1
    s.enable_e_invoice = 1
    s.auto_generate_e_invoice = 0
    if s.meta.has_field("e_invoice_applicable_from"):
        s.e_invoice_applicable_from = "2026-01-01"
    if s.meta.has_field("nil_exempt_e_invoice_treatment"):
        # test items carry no GST rate — still allow e-invoice generation
        s.nil_exempt_e_invoice_treatment = "Generate with Taxable Values"
    if not any(c.gstin == SANDBOX_GSTIN for c in (s.credentials or [])):
        s.append("credentials", {
            "company": company, "gstin": SANDBOX_GSTIN,
            "service": "e-Waybill / e-Invoice",
            "username": "sandbox", "password": "sandbox",
        })
    s.flags.ignore_mandatory = True
    s.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"GST Settings: API on, SANDBOX on, e-Invoice on (company {company}).")
    print("To actually generate an IRN, paste your India Compliance account "
          "API Secret in GST Settings → API (free signup: india-compliance.app), "
          "and your NIC sandbox username/password in the credentials row.")
