# Copyright (c) 2024, Midhunatech and Contributors
# License: GPL-3.0
"""
Generic, mobile-first doctype data API for the Midhunatech PWA.

One small set of endpoints powers a single native list/detail UI for ANY
doctype — no Frappe desk iframe. Everything respects the logged-in user's
permissions (uses frappe.get_list, which applies role + user permissions).

    get_view(doctype)  -> number/summary cards + display config for the list
    get_list(doctype)  -> searchable, paginated rows (pre-formatted for display)
    get_doc(doctype)   -> read-only field list for the detail sheet
"""

import frappe
from frappe import _
from frappe.utils import fmt_money, format_date, format_datetime, get_first_day, nowdate

# Fields that should never be shown to the user
_SKIP = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "_user_tags", "_comments", "_assign", "_liked_by", "_seen",
    "parent", "parentfield", "parenttype", "naming_series", "amended_from",
}
_LAYOUT = {"Section Break", "Column Break", "Tab Break", "HTML", "Table",
           "Table MultiSelect", "Button", "Fold", "Heading", "Image"}

_CARD_COLORS = ["#6366f1", "#22c55e", "#f59e0b", "#ec4899", "#0ea5e9", "#8b5cf6"]


# ── helpers ────────────────────────────────────────────────────────────────────

def _require_read(doctype):
    if not frappe.db.exists("DocType", doctype):
        frappe.throw(_("Doctype {0} not found").format(doctype))
    if not frappe.has_permission(doctype, "read"):
        frappe.throw(_("You are not permitted to view {0}").format(doctype),
                     frappe.PermissionError)
    return frappe.get_meta(doctype)


def _pick_date_field(meta):
    for c in ("transaction_date", "posting_date", "attendance_date", "date",
              "from_date", "expense_date", "creation"):
        if meta.has_field(c):
            return c
    return "modified"


def _pick_status_field(meta):
    for c in ("status", "workflow_state"):
        if meta.has_field(c):
            return c
    return None


def _pick_amount_field(meta):
    preferred = ("grand_total", "total", "net_total", "amount", "total_amount",
                 "total_claimed_amount", "total_sanctioned_amount")
    for c in preferred:
        df = meta.get_field(c)
        if df and df.fieldtype in ("Currency", "Float"):
            return c
    for df in meta.fields:
        if df.fieldtype == "Currency":
            return df.fieldname
    return None


def _list_fields(meta, title_field, status_field, amount_field, date_field, permitted=None):
    """Up to 3 secondary fields shown under the title on each card."""
    used = {title_field, status_field, amount_field, date_field, "name"}
    out = []
    for df in meta.fields:
        if len(out) >= 3:
            break
        if df.fieldname in used or df.fieldname in _SKIP:
            continue
        if permitted is not None and df.fieldname not in permitted:
            continue
        if df.fieldtype in _LAYOUT or df.hidden:
            continue
        if not df.in_list_view:
            continue
        if df.fieldtype in ("Data", "Link", "Select", "Int", "Float", "Currency",
                            "Date", "Datetime", "Small Text", "Check"):
            out.append(df.fieldname)
            used.add(df.fieldname)
    return out


def _fmt(df, value):
    """Format a single value for display based on its fieldtype."""
    if value is None or value == "":
        return ""
    ft = df.fieldtype if df else "Data"
    try:
        if ft == "Currency":
            return fmt_money(value)
        if ft == "Float":
            return f"{float(value):g}"
        if ft == "Date":
            return format_date(value)
        if ft == "Datetime":
            return format_datetime(value)
        if ft == "Check":
            return "Yes" if int(value) else "No"
        if ft == "Time":
            return str(value).split(".")[0]
    except Exception:
        pass
    return str(value)


def _permitted_fields(meta, ptype="read"):
    """Fieldnames the current user may access at their permlevel — so restricted
    fields (e.g. salary at permlevel 1) are never leaked. Falls back to
    permlevel-0 fields if the framework helper is unavailable."""
    try:
        allowed = set(meta.get_permitted_fieldnames(permission_type=ptype) or [])
    except Exception:
        allowed = {df.fieldname for df in meta.fields if int(df.permlevel or 0) == 0}
    allowed.add("name")
    return allowed


# ── view config + number cards ─────────────────────────────────────────────────

@frappe.whitelist()
def get_view(doctype, label=None):
    meta = _require_read(doctype)
    perm = _permitted_fields(meta)

    title_field  = meta.title_field or "name"
    if title_field not in perm:
        title_field = "name"
    status_field = _pick_status_field(meta)
    if status_field and status_field not in perm:
        status_field = None
    amount_field = _pick_amount_field(meta)
    if amount_field and amount_field not in perm:
        amount_field = None
    date_field   = _pick_date_field(meta)
    if date_field not in perm:
        date_field = "modified"
    sec_fields   = _list_fields(meta, title_field, status_field, amount_field, date_field, perm)

    fields_meta = []
    for fn in sec_fields:
        df = meta.get_field(fn)
        fields_meta.append({"fieldname": fn, "label": df.label or fn, "fieldtype": df.fieldtype})

    return {
        "doctype":      doctype,
        "label":        label or _(doctype),
        "title_field":  title_field,
        "status_field": status_field,
        "amount_field": amount_field,
        "amount_label": (meta.get_field(amount_field).label if amount_field else None),
        "date_field":   date_field,
        "date_label":   (meta.get_field(date_field).label if meta.get_field(date_field) else "Date"),
        "fields":       fields_meta,
        "can_create":   _can_create_native(doctype, meta),
        "cards":        _cards(doctype, meta, status_field, date_field),
    }


def _can_create_native(doctype, meta):
    """True only if the user can create AND the doctype has no required child
    table (line items) — so the native "+" never leads to a dead end."""
    if not frappe.has_permission(doctype, "create"):
        return False
    for df in meta.fields:
        if df.fieldtype in ("Table", "Table MultiSelect") and df.reqd:
            return False
    return True


def _cards(doctype, meta, status_field, date_field):
    """Number cards. Uses frappe.db.count (v16 disallows SQL count() in get_list)."""
    cards = []

    def cnt(filters=None):
        try:
            return int(frappe.db.count(doctype, filters or None))
        except Exception:
            return 0

    cards.append({"label": "Total", "value": cnt(), "color": _CARD_COLORS[0]})

    # This-month card if there is a real (non-modified) date field
    if date_field and date_field != "modified" and meta.has_field(date_field):
        cards.append({"label": "This month",
                      "value": cnt({date_field: [">=", get_first_day(nowdate())]}),
                      "color": _CARD_COLORS[4]})

    # Status / docstatus breakdown — top 2 statuses by count
    ci = 1
    if status_field:
        try:
            values = [v for v in frappe.get_all(
                doctype, distinct=True, pluck=status_field, limit_page_length=0) if v]
            ranked = sorted(((v, cnt({status_field: v})) for v in values),
                            key=lambda x: x[1], reverse=True)
            for label, value in ranked[:2]:
                cards.append({"label": str(label), "value": value,
                              "color": _CARD_COLORS[ci % len(_CARD_COLORS)]})
                ci += 1
        except Exception:
            pass
    elif meta.is_submittable:
        for code, label in ((0, "Draft"), (1, "Submitted")):
            cards.append({"label": label, "value": cnt({"docstatus": code}),
                          "color": _CARD_COLORS[ci % len(_CARD_COLORS)]})
            ci += 1

    return cards[:4]


# ── list rows ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_list(doctype, search=None, start=0, page_length=20):
    meta = _require_read(doctype)
    perm = _permitted_fields(meta)
    start = int(start or 0)
    page_length = min(int(page_length or 20), 100)

    title_field  = meta.title_field or "name"
    if title_field not in perm:
        title_field = "name"
    status_field = _pick_status_field(meta)
    if status_field and status_field not in perm:
        status_field = None
    amount_field = _pick_amount_field(meta)
    if amount_field and amount_field not in perm:
        amount_field = None
    date_field   = _pick_date_field(meta)
    if date_field not in perm:
        date_field = "modified"
    sec_fields   = _list_fields(meta, title_field, status_field, amount_field, date_field, perm)

    wanted = ["name"]
    for f in [title_field, status_field, amount_field, date_field, *sec_fields]:
        if f and f != "name" and meta.has_field(f) and f not in wanted:
            wanted.append(f)

    or_filters = None
    if search:
        s = f"%{search}%"
        or_filters = [["name", "like", s]]
        if title_field != "name":
            or_filters.append([title_field, "like", s])

    rows = frappe.get_list(
        doctype, fields=wanted, or_filters=or_filters,
        start=start, page_length=page_length,
        order_by=f"{date_field} desc" if meta.has_field(date_field) else "modified desc",
    )

    out = []
    for r in rows:
        title = r.get(title_field) or r.get("name")
        item = {
            "name":   r.get("name"),
            "title":  str(title),
            "badge":  (str(r.get(status_field)) if status_field and r.get(status_field) else None),
            "amount": (_fmt(meta.get_field(amount_field), r.get(amount_field))
                       if amount_field and r.get(amount_field) else None),
            "date":   (_fmt(meta.get_field(date_field), r.get(date_field))
                       if meta.has_field(date_field) else None),
            "fields": [],
        }
        for fn in sec_fields:
            val = _fmt(meta.get_field(fn), r.get(fn))
            if val:
                item["fields"].append({"label": meta.get_field(fn).label or fn, "value": val})
        out.append(item)

    return {"rows": out, "has_more": len(rows) == page_length}


# ── detail ─────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_doc(doctype, name):
    meta = _require_read(doctype)
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    perm = _permitted_fields(meta)

    title_field = meta.title_field or "name"
    if title_field not in perm:
        title_field = "name"
    fields = []
    for df in meta.fields:
        if df.fieldname in _SKIP or df.fieldtype in _LAYOUT or df.hidden:
            continue
        if df.fieldtype in ("Password",) or df.fieldname not in perm:
            continue
        val = doc.get(df.fieldname)
        if val in (None, "", 0) and df.fieldtype not in ("Check", "Currency", "Float", "Int"):
            continue
        formatted = _fmt(df, val)
        if formatted == "":
            continue
        fields.append({"label": df.label or df.fieldname, "value": formatted,
                       "fieldtype": df.fieldtype})

    return {
        "name":   doc.name,
        "title":  str(doc.get(title_field) or doc.name),
        "status": (doc.get("status") or doc.get("workflow_state") or None),
        "fields": fields,
    }


# ── create (self-service) ───────────────────────────────────────────────────────

_CREATE_TYPES = {
    "Data", "Link", "Select", "Small Text", "Text", "Long Text", "Text Editor",
    "Int", "Float", "Currency", "Percent", "Date", "Datetime", "Time",
    "Check", "Phone", "Read Only",
}


@frappe.whitelist()
def get_create_meta(doctype):
    """Fields needed to create a record natively. Refuses doctypes that require
    child tables (line items) — those are directed to the desk to avoid breakage."""
    if not frappe.has_permission(doctype, "create"):
        frappe.throw(_("You are not permitted to create {0}").format(doctype),
                     frappe.PermissionError)
    meta = frappe.get_meta(doctype)
    perm = _permitted_fields(meta, "write")

    for df in meta.fields:
        if df.fieldtype in ("Table", "Table MultiSelect") and df.reqd:
            return {"creatable": False,
                    "reason": _("{0} needs line items — please use the desk to create it.").format(_(doctype))}

    fields, seen = [], set()

    def add(df):
        if df.fieldname in seen or df.fieldname in _SKIP:
            return
        if df.fieldtype not in _CREATE_TYPES or df.fieldtype == "Read Only":
            return
        if df.hidden or df.read_only or df.fieldname not in perm:
            return
        seen.add(df.fieldname)
        fields.append({
            "fieldname": df.fieldname, "label": df.label or df.fieldname,
            "fieldtype": df.fieldtype, "options": df.options or "",
            "reqd": int(df.reqd or 0), "default": df.default or "",
        })

    for df in meta.fields:          # mandatory fields first
        if df.reqd:
            add(df)
    for df in meta.fields:          # then a few common optional ones
        if len(fields) >= 12:
            break
        if df.in_list_view or df.bold:
            add(df)

    return {"creatable": True, "doctype": doctype, "fields": fields}


@frappe.whitelist()
def search_link(doctype, txt="", page_length=10):
    """Autocomplete options for a Link field's target doctype."""
    if not doctype or not frappe.has_permission(doctype, "read"):
        return []
    meta = frappe.get_meta(doctype)
    title = meta.title_field or "name"
    or_filters = None
    if txt:
        s = f"%{txt}%"
        or_filters = [["name", "like", s]]
        if title != "name":
            or_filters.append([title, "like", s])
    wanted = ["name"] + ([title] if title != "name" else [])
    rows = frappe.get_list(doctype, or_filters=or_filters, fields=wanted,
                           page_length=int(page_length), order_by="modified desc")
    return [{"value": r.get("name"), "label": str(r.get(title) or r.get("name"))}
            for r in rows]


@frappe.whitelist()
def create_doc(doctype, values):
    """Create a record from the native form (permissions + validations enforced)."""
    if isinstance(values, str):
        values = frappe.parse_json(values)
    if not frappe.has_permission(doctype, "create"):
        frappe.throw(_("You are not permitted to create {0}").format(doctype),
                     frappe.PermissionError)
    meta = frappe.get_meta(doctype)
    # Only accept fields the user is allowed to write (respects permlevel) — so a
    # crafted request can't set restricted fields the form never exposed.
    writable = _permitted_fields(meta, "write")
    skip = _SKIP | {"owner", "creation", "modified", "modified_by", "docstatus"}

    doc = frappe.new_doc(doctype)
    for key, val in (values or {}).items():
        if key in writable and key not in skip and val not in (None, ""):
            doc.set(key, val)
    doc.insert()
    frappe.db.commit()
    return {"name": doc.name}
