# Copyright (c) 2026, Midhunatech and Contributors
# License: GPL-3.0
"""
Generic in-app workflow approvals for the PWA.

Works with ANY doctype that has an active Workflow (Purchase Order,
Sales Invoice, Delivery Note, Material Request, ...): lists documents
waiting in a state the current user's roles can act on, lets the user
preview them (via midhunatech.api.data.get_doc) and apply a transition
(Approve / Reject / ...) — all without ever opening the desk.
"""

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow, get_transitions

# Curated previews for transactional documents: a phone-sized approval screen
# only needs the key business facts, not every field on the form.
# Order here = display order. Missing/empty fields are skipped automatically.
_PARTY = ["customer", "customer_name", "supplier", "supplier_name", "quotation_to", "party_name"]
_TOTALS = ["total_qty", "total", "total_taxes_and_charges", "grand_total",
           "rounded_total", "outstanding_amount", "advance_paid"]
_ADDRESS = ["address_display", "shipping_address", "dispatch_address",
            "contact_display", "contact_mobile"]

_KEY_FIELDS = {
    "Sales Order":      _PARTY + ["transaction_date", "delivery_date", "po_no", "company"] + _TOTALS + _ADDRESS,
    "Sales Invoice":    _PARTY + ["posting_date", "due_date", "po_no", "company"] + _TOTALS + _ADDRESS,
    "Delivery Note":    _PARTY + ["posting_date", "lr_no", "vehicle_no", "company"] + _TOTALS + _ADDRESS,
    "Quotation":        _PARTY + ["transaction_date", "valid_till", "company"] + _TOTALS + _ADDRESS,
    "Purchase Order":   _PARTY + ["transaction_date", "schedule_date", "company"] + _TOTALS + _ADDRESS,
    "Purchase Invoice": _PARTY + ["posting_date", "due_date", "bill_no", "bill_date", "company"] + _TOTALS + _ADDRESS,
    "Purchase Receipt": _PARTY + ["posting_date", "lr_no", "company"] + _TOTALS + _ADDRESS,
    "Material Request": ["material_request_type", "transaction_date", "schedule_date",
                         "company", "set_warehouse"],
}

# Child tables worth showing on an approval screen (line items + taxes)
_KEY_TABLES = {"items", "taxes"}

# Preferred line-item columns (falls back to in_list_view columns)
_ITEM_COLS = ["item_name", "qty", "uom", "rate", "amount"]


def _active_workflows():
    """Active workflows whose doctype actually exists on this site."""
    for wf in frappe.get_all(
        "Workflow",
        filters={"is_active": 1},
        fields=["name", "document_type", "workflow_state_field"],
    ):
        if frappe.db.exists("DocType", wf.document_type):
            yield wf


@frappe.whitelist()
def get_pending(limit=50):
    """Documents the current user can act on, newest first."""
    user_roles = set(frappe.get_roles())
    out = []
    for wf in _active_workflows():
        try:
            if not frappe.has_permission(wf.document_type, "read"):
                continue
            transitions = frappe.get_all(
                "Workflow Transition",
                filters={"parent": wf.name},
                fields=["state", "allowed"],
            )
            states = sorted({t.state for t in transitions if t.allowed in user_roles})
            if not states:
                continue

            meta = frappe.get_meta(wf.document_type)
            sf = wf.workflow_state_field or "workflow_state"
            if not meta.has_field(sf):
                continue
            fields = ["name", sf, "modified"]
            title_field = meta.title_field if (meta.title_field and meta.has_field(meta.title_field)) else None
            if title_field and title_field not in fields:
                fields.append(title_field)

            docs = frappe.get_list(
                wf.document_type,
                filters={sf: ["in", states]},
                fields=fields,
                order_by="modified desc",
                limit_page_length=int(limit),
            )
            for d in docs:
                out.append({
                    "doctype": wf.document_type,
                    "name": d.name,
                    "title": (d.get(title_field) if title_field else None) or d.name,
                    "state": d.get(sf),
                    "modified": str(d.modified),
                })
        except Exception:
            # one broken workflow must never take the whole list down
            frappe.clear_messages()
            continue

    out.sort(key=lambda x: x["modified"], reverse=True)
    return out


@frappe.whitelist()
def pending_count():
    """Badge count for the Approvals tile / tab."""
    return len(get_pending())


@frappe.whitelist()
def get_actions(doctype, name):
    """Transitions the current user may apply to this document."""
    doc = frappe.get_doc(doctype, name)
    if not frappe.has_permission(doctype, "read", doc=doc):
        frappe.throw(_("Not permitted"), frappe.PermissionError)
    return _safe_transitions(doc)


@frappe.whitelist()
def get_preview(doctype, name):
    """Mobile preview: key header fields + line-item tables + allowed actions."""
    from midhunatech.api.data import _fmt, _permitted_fields, get_doc as data_get_doc

    out = data_get_doc(doctype, name)  # permission-checked, permlevel-safe
    doc = frappe.get_doc(doctype, name)
    meta = frappe.get_meta(doctype)
    key_fields = _KEY_FIELDS.get(doctype)

    if key_fields:
        # curated, ordered, deduped (customer vs customer_name often repeat)
        perm = _permitted_fields(meta)
        fields, seen = [], set()
        for fn in key_fields:
            df = meta.get_field(fn)
            if not df or fn not in perm:
                continue
            formatted = _fmt(df, doc.get(fn))
            if not formatted or formatted in seen:
                continue
            seen.add(formatted)
            fields.append({"label": df.label or fn, "value": formatted,
                           "fieldtype": df.fieldtype})
        out["fields"] = fields

    tables = []
    for df in meta.fields:
        if df.fieldtype != "Table":
            continue
        if key_fields and df.fieldname not in _KEY_TABLES:
            continue
        rows = doc.get(df.fieldname) or []
        if not rows:
            continue
        cmeta = frappe.get_meta(df.options)
        if df.fieldname == "items":
            wanted = list(_ITEM_COLS)
            if not cmeta.get_field("item_name"):
                wanted[0] = "item_code"
            cols = [cmeta.get_field(c) for c in wanted if cmeta.get_field(c)][:5]
        else:
            cols = [c for c in cmeta.fields if c.in_list_view and c.fieldtype != "Table"][:4]
        if not cols:
            continue
        tables.append({
            "label": df.label or df.fieldname,
            "columns": [c.label or c.fieldname for c in cols],
            "rows": [[_fmt(c, r.get(c.fieldname)) for c in cols] for r in rows[:30]],
        })

    out["tables"] = tables
    out["actions"] = _safe_transitions(doc)
    return out


def _safe_transitions(doc):
    """get_transitions throws if the doc has no workflow state yet — treat as none."""
    try:
        return [{"action": t.action, "next_state": t.next_state} for t in get_transitions(doc)]
    except Exception:
        frappe.clear_messages()
        return []


@frappe.whitelist()
def take_action(doctype, name, action):
    """Apply a workflow transition (permission-checked by apply_workflow)."""
    doc = frappe.get_doc(doctype, name)
    apply_workflow(doc, action)
    sf = (
        frappe.db.get_value("Workflow", {"document_type": doctype, "is_active": 1}, "workflow_state_field")
        or "workflow_state"
    )
    doc.reload()
    return {"ok": True, "state": doc.get(sf)}
