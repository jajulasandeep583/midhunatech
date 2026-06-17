# Copyright (c) 2026, Midhunatech and Contributors
# License: GPL-3.0
"""
In-app *notification rules* editor for the PWA (System Manager only).

A thin, mobile-friendly CRUD layer over two native Frappe doctypes so the
owner can configure alerts without ever opening the ERPNext desk:

  - "Notification"        -> event-driven alerts (e.g. Sales Order submitted ->
                            notify the approver). When send_system_notification
                            is on, Frappe writes a Notification Log row, which the
                            PWA already shows in the in-app feed and mirrors to a
                            web push (see hooks.py + api/push.py).
  - "Auto Email Report"   -> scheduled reports emailed daily / weekly / monthly.

Recipients are modelled for the UI as a flat list of:
    {"type": "role",  "value": "Sales Manager"}
    {"type": "field", "value": "owner"}          # a User/Link field on the doc
which map to Notification Recipient.receiver_by_role / receiver_by_document_field.
"""

import json

import frappe
from frappe import _

EVENTS = ["New", "Save", "Submit", "Cancel", "Value Change", "Days After", "Days Before"]
CHANNELS = ["System Notification", "Email"]
REPORT_FREQUENCIES = ["Daily", "Weekdays", "Weekly", "Monthly"]
REPORT_FORMATS = ["HTML", "XLSX", "CSV", "PDF"]


def _require_admin():
    if frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
        frappe.throw(_("System Manager role required"), frappe.PermissionError)


def _loads(v, default):
    if v is None:
        return default
    if isinstance(v, str):
        return json.loads(v or "null") if v.strip() else default
    return v


# -- Meta helpers --------------------------------------------------------------
@frappe.whitelist()
def get_meta():
    """Option lists + a curated set of common doctypes for the alert editor."""
    _require_admin()
    return {
        "events": EVENTS,
        "channels": CHANNELS,
        "frequencies": REPORT_FREQUENCIES,
        "formats": REPORT_FORMATS,
        "doctypes": _common_doctypes(),
        "roles": [r.name for r in frappe.get_all("Role",
                  filters={"disabled": 0}, fields=["name"], order_by="name")
                  if not r.name.startswith("All")],
    }


def _common_doctypes():
    """DocTypes worth alerting on: not single, not child. Returns names only --
    the UI offers them as suggestions but still accepts any typed doctype."""
    rows = frappe.get_all(
        "DocType",
        filters={"issingle": 0, "istable": 0},
        fields=["name", "is_submittable"],
        order_by="is_submittable desc, name",
    )
    return [r.name for r in rows]


@frappe.whitelist()
def get_doctype_fields(doctype):
    """Fields of doctype for the value-changed and recipient-by-field pickers."""
    _require_admin()
    if not doctype or not frappe.db.exists("DocType", doctype):
        return {"all": [], "recipient_fields": []}
    meta = frappe.get_meta(doctype)
    all_fields, recipient_fields = [], [{"value": "owner", "label": "Owner (creator)"}]
    for df in meta.fields:
        if df.fieldtype in ("Section Break", "Column Break", "HTML", "Tab Break", "Button"):
            continue
        all_fields.append({"value": df.fieldname, "label": df.label or df.fieldname})
        if (df.fieldtype == "Link" and df.options in ("User", "Employee")) or \
           (df.fieldtype == "Data" and "email" in (df.fieldname or "").lower()):
            recipient_fields.append({"value": df.fieldname, "label": df.label or df.fieldname})
    return {"all": all_fields, "recipient_fields": recipient_fields}


# -- Notifications (alerts) ----------------------------------------------------
@frappe.whitelist()
def list_notifications():
    """All notification rules, with a short human summary line."""
    _require_admin()
    return frappe.get_all(
        "Notification",
        fields=["name", "subject", "document_type", "event", "channel",
                "enabled", "send_system_notification"],
        order_by="document_type, name",
    )


@frappe.whitelist()
def get_notification(name):
    _require_admin()
    doc = frappe.get_doc("Notification", name)
    recipients = []
    for r in doc.recipients:
        if r.receiver_by_role:
            recipients.append({"type": "role", "value": r.receiver_by_role})
        elif r.receiver_by_document_field:
            recipients.append({"type": "field", "value": r.receiver_by_document_field})
    return {
        "name": doc.name,
        "subject": doc.subject,
        "document_type": doc.document_type,
        "event": doc.event,
        "value_changed": doc.value_changed,
        "channel": doc.channel,
        "send_system_notification": int(doc.send_system_notification or 0),
        "enabled": int(doc.enabled or 0),
        "condition": doc.condition,
        "message": doc.message,
        "days_in_advance": doc.days_in_advance,
        "date_changed": doc.date_changed,
        "recipients": recipients,
    }


@frappe.whitelist()
def save_notification(payload):
    """Create or update a Notification rule from the PWA editor."""
    _require_admin()
    p = _loads(payload, {})

    name = p.get("name")
    doc = frappe.get_doc("Notification", name) if name and frappe.db.exists("Notification", name) \
        else frappe.new_doc("Notification")

    doc.subject = p.get("subject") or "Alert"
    doc.document_type = p.get("document_type")
    doc.event = p.get("event") or "Submit"
    doc.channel = p.get("channel") or "System Notification"
    doc.send_system_notification = 1
    doc.enabled = int(p.get("enabled", 1))
    doc.is_standard = 0
    doc.message_type = "Markdown"
    doc.message = p.get("message") or _default_message(doc.document_type)
    doc.condition = p.get("condition") or ""

    if doc.event == "Value Change":
        doc.value_changed = p.get("value_changed") or "workflow_state"
    else:
        doc.value_changed = None

    if doc.event in ("Days After", "Days Before"):
        doc.date_changed = p.get("date_changed")
        doc.days_in_advance = int(p.get("days_in_advance") or 0)

    doc.set("recipients", [])
    for r in (p.get("recipients") or []):
        if r.get("type") == "role" and r.get("value"):
            doc.append("recipients", {"receiver_by_role": r["value"]})
        elif r.get("type") == "field" and r.get("value"):
            doc.append("recipients", {"receiver_by_document_field": r["value"]})
    if not doc.recipients:
        doc.append("recipients", {"receiver_by_document_field": "owner"})

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name}


@frappe.whitelist()
def toggle_notification(name, enabled):
    _require_admin()
    frappe.db.set_value("Notification", name, "enabled", int(enabled))
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def delete_notification(name):
    _require_admin()
    frappe.delete_doc("Notification", name, ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}


def _default_message(doctype):
    dt = doctype or "document"
    return (
        "{{ doc.name }} (" + dt + ") needs your attention.\n\n"
        "Status: {{ doc.workflow_state or doc.status or doc.docstatus }}\n"
        "Owner: {{ doc.owner }}"
    )


# -- Scheduled reports (Auto Email Report) -------------------------------------
@frappe.whitelist()
def get_reports():
    """Reports the user may schedule -- name + ref doctype."""
    _require_admin()
    return frappe.get_all("Report", fields=["name", "ref_doctype", "report_type"],
                          order_by="name")


@frappe.whitelist()
def list_auto_email_reports():
    _require_admin()
    return frappe.get_all(
        "Auto Email Report",
        fields=["name", "report", "frequency", "format", "enabled", "email_to"],
        order_by="report",
    )


@frappe.whitelist()
def get_auto_email_report(name):
    _require_admin()
    doc = frappe.get_doc("Auto Email Report", name)
    return {
        "name": doc.name,
        "report": doc.report,
        "frequency": doc.frequency,
        "day_of_week": doc.day_of_week,
        "format": doc.format,
        "email_to": doc.email_to,
        "enabled": int(doc.enabled or 0),
        "no_of_rows": doc.no_of_rows,
        "send_if_data": int(doc.send_if_data or 0),
        "filters": doc.filters,
    }


@frappe.whitelist()
def save_auto_email_report(payload):
    _require_admin()
    p = _loads(payload, {})
    name = p.get("name")
    doc = frappe.get_doc("Auto Email Report", name) if name and frappe.db.exists("Auto Email Report", name) \
        else frappe.new_doc("Auto Email Report")

    doc.report = p.get("report")
    doc.user = frappe.session.user
    doc.frequency = p.get("frequency") or "Weekly"
    if doc.frequency == "Weekly":
        doc.day_of_week = p.get("day_of_week") or "Monday"
    doc.format = p.get("format") or "HTML"
    doc.email_to = p.get("email_to") or frappe.session.user
    doc.enabled = int(p.get("enabled", 1))
    doc.no_of_rows = int(p.get("no_of_rows") or 100)
    doc.send_if_data = int(p.get("send_if_data", 1))
    if p.get("filters") is not None:
        doc.filters = p["filters"] if isinstance(p["filters"], str) else json.dumps(p["filters"])

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name}


@frappe.whitelist()
def toggle_auto_email_report(name, enabled):
    _require_admin()
    frappe.db.set_value("Auto Email Report", name, "enabled", int(enabled))
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def delete_auto_email_report(name):
    _require_admin()
    frappe.delete_doc("Auto Email Report", name, ignore_permissions=True)
    frappe.db.commit()
    return {"ok": True}
