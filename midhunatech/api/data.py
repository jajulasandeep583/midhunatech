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

import re

import frappe
from frappe import _
from frappe.utils import fmt_money, format_date, format_datetime, get_first_day, nowdate, strip_html_tags

# Fields that should never be shown to the user
_SKIP = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus", "idx",
    "_user_tags", "_comments", "_assign", "_liked_by", "_seen",
    "parent", "parentfield", "parenttype", "naming_series", "amended_from",
}
_LAYOUT = {"Section Break", "Column Break", "Tab Break", "HTML", "Table",
           "Table MultiSelect", "Button", "Fold", "Heading", "Image"}

# Technical fieldtypes that are meaningless (or unreadable) on a phone screen
_TECH_TYPES = {"Code", "JSON", "HTML Editor", "Markdown Editor", "Attach",
               "Attach Image", "Signature", "Geolocation", "Barcode", "Icon", "Color"}

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
    return _clean_text(str(value))


def _clean_text(s):
    """Raw HTML (addresses, terms, rich text) → short readable text."""
    if "<" in s and ">" in s:
        s = re.sub(r"<br\s*/?>", ", ", s, flags=re.I)
        s = re.sub(r"</(p|div|tr|li|h\d)>", ", ", s, flags=re.I)
        s = strip_html_tags(s)
    s = re.sub(r"\s+", " ", s).strip(" ,")
    if len(s) > 400:
        s = s[:400].rstrip() + "…"
    return s


# Curated default display fields for common transactional doctypes — used
# when the tile has no Fields (JSON array) configured. The tile's JSON always
# wins; doctypes not listed here keep the automatic meta-derived display.
_DEFAULT_FIELDS = {
    "Sales Invoice":    ["customer", "posting_date", "due_date", "grand_total", "outstanding_amount", "status"],
    "Sales Order":      ["customer", "transaction_date", "delivery_date", "grand_total", "status"],
    "Purchase Invoice": ["supplier", "posting_date", "due_date", "grand_total", "outstanding_amount", "status"],
    "Purchase Order":   ["supplier", "transaction_date", "schedule_date", "grand_total", "status"],
    "Purchase Receipt": ["supplier", "posting_date", "grand_total", "status"],
    "Payment Entry":    ["payment_type", "party_type", "party", "posting_date", "paid_amount", "status"],
    "Journal Entry":    ["voucher_type", "posting_date", "total_debit", "user_remark"],
    "Material Request": ["material_request_type", "transaction_date", "schedule_date", "status"],
}


def _effective_fields(meta, perm, fields, doctype):
    """Tile-configured fields win; otherwise the curated defaults for common
    doctypes; otherwise None (automatic meta-derived display)."""
    return (_user_fields(meta, perm, fields)
            or _user_fields(meta, perm, _DEFAULT_FIELDS.get(doctype)))


def _user_fields(meta, perm, fields):
    """Tile-configured display fields (JSON array of fieldnames) → sanitized
    ordered list. Unknown, layout, technical and permission-restricted
    fieldnames are silently dropped. Returns None when not configured."""
    if not fields:
        return None
    try:
        lst = frappe.parse_json(fields) if isinstance(fields, str) else fields
    except Exception:
        return None
    if not isinstance(lst, list):
        return None
    out = []
    for fn in lst:
        fn = str(fn).strip()
        df = meta.get_field(fn)
        if not df or fn in _SKIP or fn not in perm:
            continue
        if df.fieldtype in _LAYOUT or df.fieldtype in _TECH_TYPES or df.fieldtype == "Password":
            continue
        if fn not in out:
            out.append(fn)
    return out or None


def _user_filters(filters):
    """Tile-configured list filters (JSON dict) → dict or None."""
    if not filters:
        return None
    try:
        d = frappe.parse_json(filters) if isinstance(filters, str) else filters
    except Exception:
        return None
    return d if isinstance(d, dict) and d else None


def _permitted_fields(meta, ptype="read"):
    """Fieldnames the current user may access at their permlevel — so restricted
    fields (e.g. salary at permlevel 1) are never leaked. Falls back to
    permlevel-0 fields if the framework helper is unavailable. Child doctypes
    have no permissions of their own (the helper returns nothing for them) —
    use their permlevel-0 fields."""
    allowed = set()
    if not getattr(meta, "istable", 0):
        try:
            allowed = set(meta.get_permitted_fieldnames(permission_type=ptype) or [])
        except Exception:
            allowed = set()
    if not allowed:
        allowed = {df.fieldname for df in meta.fields if int(df.permlevel or 0) == 0}
    allowed.add("name")
    return allowed


# ── view config + number cards ─────────────────────────────────────────────────

@frappe.whitelist()
def get_view(doctype, label=None, fields=None, filters=None):
    meta = _require_read(doctype)
    perm = _permitted_fields(meta)
    base = _user_filters(filters)

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
    cfg_fields   = _effective_fields(meta, perm, fields, doctype)
    if cfg_fields:
        used = {title_field, status_field, amount_field, date_field, "name"}
        sec_fields = [f for f in cfg_fields if f not in used][:5]
    else:
        sec_fields = _list_fields(meta, title_field, status_field, amount_field, date_field, perm)

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
        "cards":        _cards(doctype, meta, status_field, date_field, base),
    }


# Doctypes whose required line-item table the native create form CAN handle.
# fields: curated row fields (auto-filled ones like uom/conversion_factor are
# left to set_missing_values); reqd: required in the mobile form even when the
# docfield itself is optional (e.g. warehouse — mandatory for stock items);
# copy_parent: row field ← parent field when the row leaves it blank.
_CHILD_CREATE = {
    "Material Request": {
        "table": "items",
        "fields": ["item_code", "qty", "warehouse"],
        "reqd": {"item_code", "qty", "warehouse"},
        "parent_reqd": {"schedule_date"},
        "copy_parent": {"schedule_date": "schedule_date"},
    },
}


def _can_create_native(doctype, meta):
    """True only if the user can create AND the doctype has no required child
    table (line items) — unless we support that table natively."""
    if not frappe.has_permission(doctype, "create"):
        return False
    for df in meta.fields:
        if df.fieldtype in ("Table", "Table MultiSelect") and df.reqd:
            return doctype in _CHILD_CREATE
    return True


def _cards(doctype, meta, status_field, date_field, base=None):
    """Number cards. Uses frappe.db.count (v16 disallows SQL count() in get_list).
    `base` = tile-configured filters — every card respects them."""
    cards = []

    def cnt(filters=None):
        try:
            f = dict(base or {})
            f.update(filters or {})
            return int(frappe.db.count(doctype, f or None))
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
                doctype, filters=base or None, distinct=True,
                pluck=status_field, limit_page_length=0) if v]
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
def get_list(doctype, search=None, start=0, page_length=20, fields=None, filters=None):
    meta = _require_read(doctype)
    perm = _permitted_fields(meta)
    base = _user_filters(filters)
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
    cfg_fields   = _effective_fields(meta, perm, fields, doctype)
    if cfg_fields:
        used = {title_field, status_field, amount_field, date_field, "name"}
        sec_fields = [f for f in cfg_fields if f not in used][:5]
    else:
        sec_fields = _list_fields(meta, title_field, status_field, amount_field, date_field, perm)

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
        doctype, fields=wanted, filters=base or None, or_filters=or_filters,
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
def get_doc(doctype, name, fields=None):
    meta = _require_read(doctype)
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    perm = _permitted_fields(meta)
    cfg_fields = _effective_fields(meta, perm, fields, doctype)

    title_field = meta.title_field or "name"
    if title_field not in perm:
        title_field = "name"

    if cfg_fields:
        # tile-configured: show exactly these fields, in this order
        source = [meta.get_field(fn) for fn in cfg_fields]
    else:
        source = [df for df in meta.fields if not df.hidden]

    out_fields = []
    for df in source:
        if df.fieldname in _SKIP or df.fieldtype in _LAYOUT:
            continue
        if df.fieldtype in ("Password",) or df.fieldtype in _TECH_TYPES or df.fieldname not in perm:
            continue
        val = doc.get(df.fieldname)
        if val in (None, "", 0) and df.fieldtype not in ("Check", "Currency", "Float", "Int"):
            continue
        formatted = _fmt(df, val)
        if formatted == "":
            continue
        out_fields.append({"label": df.label or df.fieldname, "value": formatted,
                           "fieldtype": df.fieldtype})

    return {
        "name":   doc.name,
        "title":  str(doc.get(title_field) or doc.name),
        "status": (doc.get("status") or doc.get("workflow_state") or None),
        "fields": out_fields,
    }


# ── create (self-service) ───────────────────────────────────────────────────────

_CREATE_TYPES = {
    "Data", "Link", "Select", "Small Text", "Text", "Long Text", "Text Editor",
    "Int", "Float", "Currency", "Percent", "Date", "Datetime", "Time",
    "Check", "Phone", "Read Only",
}


def _create_fields(meta, perm, cap=12):
    """Mandatory-first creatable field list for a (parent or child) meta."""
    fields, seen = [], set()

    def add(df):
        if df.fieldname in seen or df.fieldname in _SKIP:
            return
        if df.fieldtype not in _CREATE_TYPES or df.fieldtype == "Read Only":
            return
        if df.hidden or df.read_only or df.fieldname not in perm:
            return
        seen.add(df.fieldname)
        default = df.default or ""
        # resolve dynamic defaults so the mobile form prefills real values
        if df.fieldtype == "Date" and str(default).lower() == "today":
            default = nowdate()
        elif df.fieldtype == "Datetime" and str(default).lower() == "now":
            default = frappe.utils.now()
        elif df.fieldtype == "Link" and df.options == "Company" and not default:
            default = (frappe.defaults.get_user_default("Company")
                       or frappe.db.get_single_value("Global Defaults", "default_company") or "")
        fields.append({
            "fieldname": df.fieldname, "label": df.label or df.fieldname,
            "fieldtype": df.fieldtype, "options": df.options or "",
            "reqd": int(df.reqd or 0), "default": default,
        })

    for df in meta.fields:          # mandatory fields first
        if df.reqd:
            add(df)
    for df in meta.fields:          # then a few common optional ones
        if len(fields) >= cap:
            break
        if df.in_list_view or df.bold:
            add(df)
    return fields


@frappe.whitelist()
def get_create_meta(doctype):
    """Fields needed to create a record natively. Doctypes with a required
    child table are refused unless the table is supported (_CHILD_CREATE) —
    then its row fields are returned too (mobile line-item editor)."""
    if not frappe.has_permission(doctype, "create"):
        frappe.throw(_("You are not permitted to create {0}").format(doctype),
                     frappe.PermissionError)
    meta = frappe.get_meta(doctype)
    perm = _permitted_fields(meta, "write")

    child = None
    spec = _CHILD_CREATE.get(doctype)
    for df in meta.fields:
        if df.fieldtype in ("Table", "Table MultiSelect") and df.reqd:
            if not spec:
                return {"creatable": False,
                        "reason": _("{0} needs line items — please use the desk to create it.").format(_(doctype))}
            cdf = meta.get_field(spec["table"])
            cmeta = frappe.get_meta(cdf.options)
            cperm = _permitted_fields(cmeta, "write")
            cfields = []
            for fn in spec["fields"]:
                fdf = cmeta.get_field(fn)
                if not fdf or fn not in cperm:
                    continue
                cfields.append({
                    "fieldname": fn, "label": fdf.label or fn,
                    "fieldtype": fdf.fieldtype, "options": fdf.options or "",
                    "reqd": 1 if fn in spec["reqd"] else int(fdf.reqd or 0),
                    "default": fdf.default or "",
                })
            child = {"fieldname": spec["table"], "label": cdf.label or spec["table"],
                     "fields": cfields}
            break

    fields = _create_fields(meta, perm)
    if spec:
        for f in fields:
            if f["fieldname"] in spec.get("parent_reqd", ()):
                f["reqd"] = 1

    return {"creatable": True, "doctype": doctype, "fields": fields, "child": child}


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
    """Create a record from the native form (permissions + validations enforced).
    `values` may include a list under the supported child fieldname
    (e.g. Material Request "items") — rows are filtered the same way."""
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
    spec = _CHILD_CREATE.get(doctype)
    child_field = spec["table"] if spec else None

    doc = frappe.new_doc(doctype)
    for key, val in (values or {}).items():
        if key == child_field:
            continue
        if key in writable and key not in skip and val not in (None, ""):
            doc.set(key, val)

    rows = (values or {}).get(child_field) if child_field else None
    if child_field and rows:
        cmeta = frappe.get_meta(meta.get_field(child_field).options)
        cwritable = _permitted_fields(cmeta, "write")
        for row in rows:
            if not isinstance(row, dict):
                continue
            clean = {k: v for k, v in row.items()
                     if k in cwritable and k not in skip and v not in (None, "")}
            for ck, pk in (spec.get("copy_parent") or {}).items():
                if not clean.get(ck) and (values or {}).get(pk):
                    clean[ck] = values[pk]
            if clean:
                doc.append(child_field, clean)

    doc.insert()
    frappe.db.commit()
    return {"name": doc.name}


# ── dashboard (KPI / number cards) ──────────────────────────────────────────────

@frappe.whitelist()
def get_dashboard(target=None):
    """Render Frappe Number Cards as KPI cards. `target` may be a Dashboard name,
    a comma-separated list of Number Card names, or blank (all permitted cards).
    Only 'Document Type' cards are computed natively (Report/Custom are skipped)."""
    from frappe.desk.doctype.number_card.number_card import get_result

    names = _resolve_card_names(target)
    cards = []
    for name in names:
        try:
            card = frappe.get_doc("Number Card", name)
            if not card.has_permission("read"):
                continue
            if (card.type or "Document Type") != "Document Type":
                continue
            if not card.document_type or not frappe.has_permission(card.document_type, "read"):
                continue
            value = get_result(card.as_dict(), card.get("filters_json") or "[]")
            cards.append({
                "name":     card.name,
                "label":    card.label or card.name,
                "value":    _fmt_card_value(value, card),
                "color":    card.get("color") or "#6366f1",
                "doctype":  card.document_type,
                "function": card.function,
            })
        except Exception:
            continue
    return {"cards": cards}


def _resolve_card_names(target):
    if target and frappe.db.exists("Dashboard", target):
        dash = frappe.get_doc("Dashboard", target)
        return [c.card for c in dash.get("cards", []) if c.card]
    if target:
        names = []
        for tok in (t.strip() for t in str(target).split(",") if t.strip()):
            if frappe.db.exists("Number Card", tok):
                names.append(tok)
            else:
                by_label = frappe.db.get_value("Number Card", {"label": tok}, "name")
                if by_label:
                    names.append(by_label)
        return names
    return frappe.get_all("Number Card", pluck="name", limit_page_length=24,
                          order_by="modified desc")


def _fmt_card_value(value, card):
    try:
        if (card.function or "Count") == "Count":
            return str(int(value))
        field = card.get("aggregate_function_based_on")
        meta = frappe.get_meta(card.document_type)
        df = meta.get_field(field) if field else None
        if df and df.fieldtype in ("Currency",):
            return fmt_money(value)
        return f"{float(value):,.0f}" if float(value).is_integer() else f"{float(value):,.2f}"
    except Exception:
        return str(value)
