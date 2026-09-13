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
    "Quotation":        ["party_name", "transaction_date", "valid_till", "grand_total", "status"],
    "Item":             ["item_group", "stock_uom", "standard_rate"],
    "Customer":         ["customer_group", "territory", "mobile_no", "customer_type"],
    "Supplier":         ["supplier_group", "country", "mobile_no", "supplier_type"],
    "Expense Claim":    ["employee_name", "posting_date", "total_claimed_amount", "total_sanctioned_amount", "status"],
    "Account":          ["account_type", "root_type"],
    "Delivery Note":    ["customer", "posting_date", "grand_total", "status"],
    "Purchase Order":   ["supplier", "transaction_date", "schedule_date", "grand_total", "status"],
    "Purchase Receipt": ["supplier", "posting_date", "grand_total", "status"],
    "Stock Entry":      ["stock_entry_type", "posting_date", "total_outgoing_value"],
    "Warehouse":        ["warehouse_type", "company", "is_group"],
}


# Default child tables (+ columns) shown on the detail sheet for common
# transactional doctypes. The tile's Fields JSON overrides: a bare table
# fieldname ("items") shows it with automatic columns, dotted entries
# ("items.qty") pick exact columns in that order.
_DEFAULT_TABLES = {
    "Sales Invoice":    {"items": ["item_name", "qty", "uom", "rate", "amount"],
                         "taxes": ["description", "rate", "tax_amount", "total"]},
    "Purchase Invoice": {"items": ["item_name", "qty", "uom", "rate", "amount"],
                         "taxes": ["description", "rate", "tax_amount", "total"]},
    "Sales Order":      {"items": ["item_name", "qty", "uom", "rate", "amount"]},
    "Purchase Order":   {"items": ["item_name", "qty", "uom", "rate", "amount"]},
    "Purchase Receipt": {"items": ["item_name", "qty", "uom", "rate", "amount"]},
    "Delivery Note":    {"items": ["item_name", "qty", "uom", "rate", "amount"]},
    "Quotation":        {"items": ["item_name", "qty", "uom", "rate", "amount"]},
    "Material Request": {"items": ["item_code", "qty", "uom", "warehouse", "schedule_date"]},
    "Stock Entry":      {"items": ["item_code", "qty", "uom", "s_warehouse", "t_warehouse"]},
    "Journal Entry":    {"accounts": ["account", "party", "debit_in_account_currency",
                                      "credit_in_account_currency"]},
    "Payment Entry":    {"references": ["reference_doctype", "reference_name",
                                        "total_amount", "allocated_amount"]},
    "Expense Claim":    {"expenses": ["expense_type", "expense_date", "amount",
                                      "sanctioned_amount"]},
}

# Automatic child-column pick order (doctypes/tables not covered above)
_PREF_CHILD_COLS = (
    "item_code", "item_name", "qty", "uom", "rate", "amount",
    "account", "account_head", "party", "debit", "credit",
    "warehouse", "s_warehouse", "t_warehouse", "schedule_date",
    "expense_type", "description", "tax_amount", "total",
)


def _split_fields_spec(fields):
    """The tile's Fields JSON may mix scalar fieldnames with child-table
    entries: "items" (whole table, automatic columns) or "items.qty"
    (specific column, order preserved). Returns (scalars, {table: [cols]})."""
    try:
        lst = frappe.parse_json(fields) if isinstance(fields, str) else fields
    except Exception:
        return None, {}
    if not isinstance(lst, list):
        return None, {}
    scalars, tables = [], {}
    for fn in lst:
        fn = str(fn).strip()
        if "." in fn:
            t, c = fn.split(".", 1)
            tables.setdefault(t.strip(), [])
            if c.strip():
                tables[t.strip()].append(c.strip())
        else:
            scalars.append(fn)
    return scalars, tables


def _detail_tables(meta, doc, spec, doctype):
    """Child tables for the detail sheet. spec comes from the tile JSON;
    when empty, the curated defaults for common doctypes are used, then a
    generic fallback (every visible child table, automatic columns)."""
    explicit = bool(spec)
    if not spec:
        spec = _DEFAULT_TABLES.get(doctype) or {}
    limit_tables = None if (explicit or doctype in _DEFAULT_TABLES) else 3

    out = []
    for tf in meta.fields:
        if tf.fieldtype != "Table" or tf.fieldname in _SKIP:
            continue
        if spec and tf.fieldname not in spec:
            continue
        if not spec and tf.hidden:
            continue
        rows = doc.get(tf.fieldname) or []
        if not rows:
            continue

        cmeta = frappe.get_meta(tf.options)
        cperm = _permitted_fields(cmeta)

        def usable(cdf):
            return (cdf and cdf.fieldname in cperm and cdf.fieldname not in _SKIP
                    and cdf.fieldtype not in _LAYOUT and cdf.fieldtype not in _TECH_TYPES
                    and cdf.fieldtype != "Password")

        cols = []
        for cn in (spec.get(tf.fieldname) or []):
            cdf = cmeta.get_field(cn)
            if usable(cdf) and cdf not in cols:
                cols.append(cdf)
        if not cols:
            # automatic: preferred names first, then In List View, max 6 —
            # only columns that actually hold a value in at least one row
            cand = [cmeta.get_field(cn) for cn in _PREF_CHILD_COLS]
            cand += [df for df in cmeta.fields if df.in_list_view]
            for cdf in cand:
                if len(cols) >= 6:
                    break
                if not usable(cdf) or cdf in cols:
                    continue
                if any(r.get(cdf.fieldname) not in (None, "", 0) for r in rows):
                    cols.append(cdf)
        if not cols:
            continue

        out.append({
            "fieldname": tf.fieldname,
            "label":     tf.label or tf.fieldname.replace("_", " ").title(),
            "count":     len(rows),
            "columns":   [{"label": c.label or c.fieldname, "fieldtype": c.fieldtype} for c in cols],
            "rows":      [[_fmt(c, r.get(c.fieldname)) for c in cols] for r in rows[:50]],
        })
        if limit_tables and len(out) >= limit_tables:
            break
    return out


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
        "can_print":    int(bool(frappe.has_permission(doctype, "print"))),
        "can_email":    int(bool(frappe.has_permission(doctype, "email"))),
        "cards":        (_account_cards() if doctype == "Account"
                         else _cards(doctype, meta, status_field, date_field, base)),
    }


def _account_cards():
    """Chart of Accounts header: one card per root type with its net balance
    (Asset/Expense shown as debit balances, Liability/Income/Equity as credit)."""
    from frappe.utils import flt
    rows = dict(frappe.db.sql(
        """select a.root_type, sum(g.debit) - sum(g.credit)
           from `tabGL Entry` g
           join `tabAccount` a on g.account = a.name
           where g.is_cancelled = 0
           group by a.root_type"""))
    cur = _company_currency()
    cards = []
    for root, color in (("Asset", "#0ea5e9"), ("Liability", "#f59e0b"),
                        ("Income", "#22c55e"), ("Expense", "#ec4899"),
                        ("Equity", "#8b5cf6")):
        net = flt(rows.get(root, 0))
        if root in ("Liability", "Income", "Equity"):
            net = -net
        cards.append({"label": _(root), "value": fmt_money(net, currency=cur),
                      "color": color})
    return cards


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
    # Sales cycle — rate left optional: blank rate falls back to the price
    # list via set_missing_values, a typed rate wins.
    "Quotation": {
        "table": "items",
        "fields": ["item_code", "qty", "rate"],
        "reqd": {"item_code", "qty"},
    },
    "Sales Order": {
        "table": "items",
        "fields": ["item_code", "qty", "rate"],
        "reqd": {"item_code", "qty"},
        "parent_reqd": {"delivery_date"},
        "copy_parent": {"delivery_date": "delivery_date"},
    },
    "Sales Invoice": {
        "table": "items",
        "fields": ["item_code", "qty", "rate"],
        "reqd": {"item_code", "qty"},
    },
    "Purchase Invoice": {
        "table": "items",
        "fields": ["item_code", "qty", "rate"],
        "reqd": {"item_code", "qty"},
    },
    "Purchase Order": {
        "table": "items",
        "fields": ["item_code", "qty", "rate"],
        "reqd": {"item_code", "qty"},
        "parent_reqd": {"schedule_date"},
        "copy_parent": {"schedule_date": "schedule_date"},
    },
    "Expense Claim": {
        "table": "expenses",
        "fields": ["expense_type", "expense_date", "amount", "description"],
        "reqd": {"expense_type", "expense_date", "amount"},
    },
    # ── stock movement documents ──
    "Delivery Note": {
        "table": "items",
        "fields": ["item_code", "qty", "rate", "warehouse"],
        "reqd": {"item_code", "qty"},
    },
    "Purchase Receipt": {
        "table": "items",
        "fields": ["item_code", "qty", "rate", "warehouse"],
        "reqd": {"item_code", "qty", "warehouse"},
    },
    "Stock Entry": {
        "table": "items",
        "fields": ["item_code", "qty", "s_warehouse", "t_warehouse"],
        "reqd": {"item_code", "qty"},
    },
    # Accounting postings from the phone: bank charges, office expenses, any
    # debit/credit pair. Debit the expense account, credit the bank account.
    "Journal Entry": {
        "table": "accounts",
        "fields": ["account", "debit_in_account_currency", "credit_in_account_currency"],
        "reqd": {"account"},
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

    if doctype == "Item":
        _add_item_stock(out)
    elif doctype in ("Customer", "Supplier"):
        _add_party_money(doctype, out)
    elif doctype == "Account":
        _add_account_balance(out)

    return {"rows": out, "has_more": len(rows) == page_length}


def _fmt_qty(q):
    from frappe.utils import flt
    q = flt(q)
    return str(int(q)) if q == int(q) else str(round(q, 2))


def _party_money(doctype, names):
    """{party: {total, due}} from submitted invoices. Customer → Sales
    Invoices (due = they owe us); Supplier → Purchase Invoices (due = we owe
    them)."""
    inv, field = (("Sales Invoice", "customer") if doctype == "Customer"
                  else ("Purchase Invoice", "supplier"))
    if not names or not frappe.db.exists("DocType", inv):
        return {}
    rows = frappe.db.sql(
        f"""select `{field}`, sum(base_grand_total), sum(outstanding_amount)
            from `tab{inv}` where docstatus = 1 and `{field}` in %(names)s
            group by `{field}`""",
        {"names": names})
    return {r[0]: frappe._dict(total=r[1], due=r[2]) for r in rows}


def _company_currency():
    company = (frappe.defaults.get_user_default("Company")
               or frappe.db.get_single_value("Global Defaults", "default_company"))
    return (frappe.get_cached_value("Company", company, "default_currency")
            if company else None) or "INR"


def _add_party_money(doctype, rows):
    """Prepend business totals to Customer / Supplier cards: total business
    done + how much is still due."""
    money = _party_money(doctype, [r["name"] for r in rows])
    cur = _company_currency()
    total_lbl = _("Total Sales") if doctype == "Customer" else _("Total Purchases")
    due_lbl = _("To Receive") if doctype == "Customer" else _("To Pay")
    from frappe.utils import flt
    for r in rows:
        m = money.get(r["name"])
        total, due = (flt(m.total), flt(m.due)) if m else (0, 0)
        fields = [{"label": total_lbl, "value": fmt_money(total, currency=cur)}]
        if due:
            fields.append({"label": due_lbl, "value": fmt_money(due, currency=cur)})
        r["fields"] = fields + r["fields"]


def _party_primary_address(doctype, name):
    """One-line display address for a Customer / Supplier (primary first)."""
    links = frappe.get_all("Dynamic Link", filters={
        "link_doctype": doctype, "link_name": name, "parenttype": "Address",
    }, pluck="parent")
    if not links:
        return None
    rows = frappe.get_all("Address", filters={"name": ("in", links)},
                          fields=["address_line1", "address_line2", "city",
                                  "state", "pincode"],
                          order_by="is_primary_address desc, creation asc",
                          limit_page_length=1)
    if not rows:
        return None
    a = rows[0]
    parts = [a.address_line1, a.address_line2, a.city, a.state,
             (a.pincode and f"PIN {a.pincode}")]
    return ", ".join(p for p in parts if p)


def _add_account_balance(rows):
    """Chart-of-accounts list: show each ledger account's live balance."""
    try:
        from erpnext.accounts.utils import get_balance_on
    except ImportError:
        return
    groups = set(frappe.get_all("Account", filters={
        "name": ("in", [r["name"] for r in rows]), "is_group": 1}, pluck="name"))
    cur = _company_currency()
    for r in rows:
        if r["name"] in groups:
            r["fields"].insert(0, {"label": _("Type"), "value": _("Group")})
            continue
        try:
            bal = get_balance_on(r["name"])
            r["fields"].insert(0, {"label": _("Balance"),
                                   "value": fmt_money(bal or 0, currency=cur)})
        except Exception:
            continue


def _add_item_stock(rows):
    """Prepend total available stock (sum of Bin.actual_qty) to each stock
    item's card. Bin read permission is intentionally not required — stock
    on the item list is the product behaviour for a trading app."""
    codes = [r["name"] for r in rows]
    if not codes:
        return
    stockable = set(frappe.get_all("Item", filters={"name": ("in", codes), "is_stock_item": 1},
                                   pluck="name"))
    if not stockable:
        return
    qty = dict(frappe.db.sql(
        """select item_code, sum(actual_qty) from `tabBin`
           where item_code in %(codes)s group by item_code""",
        {"codes": list(stockable)}))
    for r in rows:
        if r["name"] in stockable:
            r["fields"].insert(0, {"label": _("In Stock"),
                                   "value": _fmt_qty(qty.get(r["name"], 0))})


# ── detail ─────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_doc(doctype, name, fields=None):
    meta = _require_read(doctype)
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    perm = _permitted_fields(meta)
    scalars, table_spec = _split_fields_spec(fields)
    if scalars:
        # a bare table fieldname ("items") means: show that table, auto columns
        keep = []
        for fn in scalars:
            df = meta.get_field(fn)
            if df and df.fieldtype == "Table":
                table_spec.setdefault(fn, [])
            else:
                keep.append(fn)
        scalars = keep
    cfg_fields = _effective_fields(meta, perm, scalars, doctype)

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
        if df.fieldname in ("status", "workflow_state"):
            continue  # already shown as the status chip
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

    result = {
        "name":   doc.name,
        "title":  str(doc.get(title_field) or doc.name),
        "status": (doc.get("status") or doc.get("workflow_state") or None),
        "docstatus": doc.docstatus,
        "can_submit": int(bool(meta.is_submittable and doc.docstatus == 0
                               and frappe.has_permission(doctype, "submit", doc=doc))),
        "can_einvoice": _einvoice_available(doc),
        "can_ewaybill": _ewaybill_available(doc),
        "can_pay": _can_pay(doc),
        "can_cancel": int(bool(doc.docstatus == 1
                               and frappe.has_permission(doctype, "cancel", doc=doc))),
        "can_amend": int(bool(doc.docstatus == 2 and meta.is_submittable
                              and frappe.has_permission(doctype, "create"))),
        "can_delete": int(bool(doc.docstatus in (0, 2)
                               and frappe.has_permission(doctype, "delete", doc=doc))),
        "can_edit": int(bool(doc.docstatus == 0
                             and doctype not in _PARTY_FORM
                             and doctype not in ("Payment Entry", "Journal Entry")
                             and frappe.has_permission(doctype, "write", doc=doc))),
        "fields": out_fields,
        "tables": _detail_tables(meta, doc, table_spec, doctype),
    }

    # Customer / Supplier detail: total business + amount still due, up top,
    # plus the party's address and their recent invoices
    if doctype in ("Customer", "Supplier"):
        from frappe.utils import flt
        m = _party_money(doctype, [doc.name]).get(doc.name)
        cur = _company_currency()
        total, due = (flt(m.total), flt(m.due)) if m else (0, 0)
        result["fields"].insert(0, {
            "label": _("To Receive") if doctype == "Customer" else _("To Pay"),
            "value": fmt_money(due, currency=cur), "fieldtype": "Currency"})
        result["fields"].insert(0, {
            "label": _("Total Sales") if doctype == "Customer" else _("Total Purchases"),
            "value": fmt_money(total, currency=cur), "fieldtype": "Currency"})

        addr = _party_primary_address(doctype, doc.name)
        if addr:
            result["fields"].append({"label": _("Address"), "value": addr,
                                     "fieldtype": "Small Text"})

        inv, pf = (("Sales Invoice", "customer") if doctype == "Customer"
                   else ("Purchase Invoice", "supplier"))
        recent = frappe.get_all(inv, filters={pf: doc.name, "docstatus": ("<", 2)},
                                fields=["name", "posting_date", "grand_total",
                                        "outstanding_amount", "status"],
                                order_by="posting_date desc, creation desc",
                                limit_page_length=8)
        if recent:
            result["tables"].insert(0, {
                "fieldname": "_invoices",
                "label":     _("Recent Invoices"),
                "count":     len(recent),
                "columns":   [{"label": _("Invoice"), "fieldtype": "Data"},
                              {"label": _("Date"), "fieldtype": "Data"},
                              {"label": _("Amount"), "fieldtype": "Currency"},
                              {"label": _("Outstanding"), "fieldtype": "Currency"},
                              {"label": _("Status"), "fieldtype": "Data"}],
                "rows":      [[r.name, format_date(r.posting_date),
                               fmt_money(r.grand_total, currency=cur),
                               fmt_money(r.outstanding_amount, currency=cur),
                               r.status or ""] for r in recent],
            })

    # Transactional docs: totals breakdown (net + taxes) when taxed
    if not scalars and doc.get("taxes"):
        from frappe.utils import flt
        cur = doc.get("currency") or _company_currency()
        for fn, label in (("net_total", _("Net Total")),
                          ("total_taxes_and_charges", _("Total Tax"))):
            if meta.has_field(fn) and not any(f["label"] == label
                                              for f in result["fields"]):
                result["fields"].append({"label": label,
                                         "value": fmt_money(flt(doc.get(fn)), currency=cur),
                                         "fieldtype": "Currency"})

    # Transactional docs: show the billing / shipping address on the sheet
    if not scalars:
        for fn, label in (("address_display", _("Address")),
                          ("shipping_address", _("Shipping Address"))):
            val = meta.has_field(fn) and doc.get(fn)
            if val and not any(f["label"] == label for f in result["fields"]):
                result["fields"].append({"label": label,
                                         "value": _clean_text(str(val)),
                                         "fieldtype": "Small Text"})

    # Item detail: available stock up top + warehouse-wise breakup table
    if doctype == "Item" and doc.get("is_stock_item"):
        from frappe.utils import flt
        bins = [b for b in frappe.get_all(
                    "Bin", filters={"item_code": doc.name},
                    fields=["warehouse", "actual_qty"], order_by="actual_qty desc")
                if flt(b.actual_qty)]
        total = sum(flt(b.actual_qty) for b in bins)
        result["fields"].insert(0, {"label": _("Available Stock"),
                                    "value": f"{_fmt_qty(total)} {doc.stock_uom or ''}".strip(),
                                    "fieldtype": "Float"})
        if bins:
            result["tables"].insert(0, {
                "fieldname": "_stock",
                "label":     _("Stock by Warehouse"),
                "count":     len(bins),
                "columns":   [{"label": _("Warehouse"), "fieldtype": "Data"},
                              {"label": _("Qty"), "fieldtype": "Float"}],
                "rows":      [[b.warehouse, _fmt_qty(b.actual_qty)] for b in bins[:50]],
            })

    return result


# ── create (self-service) ───────────────────────────────────────────────────────

_CREATE_TYPES = {
    "Data", "Link", "Select", "Small Text", "Text", "Long Text", "Text Editor",
    "Int", "Float", "Currency", "Percent", "Date", "Datetime", "Time",
    "Check", "Phone", "Read Only",
}

# System fields hidden from the mobile create form — they're auto-filled from
# defaults / set_missing_values server-side (company, currency, exchange rate,
# price lists, …). Keeps New Sales Order = customer + dates + items.
_CREATE_AUTO = {
    "company", "currency", "conversion_rate", "plc_conversion_rate",
    "price_list_currency", "selling_price_list", "buying_price_list",
    "quotation_to", "order_type", "tax_category", "letter_head",
    "language", "source", "territory", "customer_group", "supplier_group",
    "gst_category", "cost_center", "project", "set_warehouse",
    # accounting fields ERPNext derives on save (receivable/payable accounts)
    "debit_to", "credit_to", "against_income_account", "expense_account",
    "income_account", "mode_of_payment", "cash_bank_account",
}


# Optional fields forced ONTO the create form for specific doctypes (they are
# neither mandatory nor in_list_view, so the generic picker would skip them).
_CREATE_EXTRA = {
    "Purchase Invoice": ["bill_no", "bill_date"],   # supplier invoice no / date
}


def _create_fields(meta, perm, cap=12, doctype=None):
    """Mandatory-first creatable field list for a (parent or child) meta."""
    fields, seen = [], set()

    def add(df):
        if df.fieldname in seen or df.fieldname in _SKIP or df.fieldname in _CREATE_AUTO:
            return
        if df.hidden or df.read_only or df.fieldname not in perm:
            return
        # Dynamic Link (e.g. Quotation.party_name) → plain Link to the
        # controlling field's default doctype, so the mobile form gets a
        # real picker instead of dropping the field.
        if df.fieldtype == "Dynamic Link":
            ctrl = meta.get_field(df.options or "")
            target = (ctrl.default or "") if ctrl else ""
            if not target or not frappe.db.exists("DocType", target):
                return
            seen.add(df.fieldname)
            fields.append({
                "fieldname": df.fieldname, "label": df.label or df.fieldname,
                "fieldtype": "Link", "options": target,
                "reqd": 1 if (df.reqd or (ctrl and ctrl.reqd)) else 0, "default": "",
            })
            return
        if df.fieldtype not in _CREATE_TYPES or df.fieldtype == "Read Only":
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
        elif df.fieldtype == "Dynamic Link":
            # party fields (Quotation.party_name) whose controller is
            # mandatory count as mandatory themselves
            ctrl = meta.get_field(df.options or "")
            if ctrl is not None and ctrl.reqd:
                add(df)
    for fn in _CREATE_EXTRA.get(doctype or "", []):   # curated extras next
        df = meta.get_field(fn)
        if df is not None:
            add(df)
    for df in meta.fields:          # then a few common optional ones
        if len(fields) >= cap:
            break
        if df.in_list_view or df.bold:
            add(df)
    return fields


# One simple mobile form for Customer / Supplier: name + mobile + GSTIN +
# address in a single screen. The synthetic _-prefixed fields are turned into
# a linked Address + Contact server-side (create_doc), so the user never
# deals with separate Address/Contact doctypes. GSTIN auto-fills PAN, GST
# category and the state (from the GSTIN state code).
_PARTY_FORM = {
    "Customer": "customer_name",
    "Supplier": "supplier_name",
}

_PARTY_EXTRA_FIELDS = [
    ("_mobile",   "Mobile Number",                  "Phone"),
    ("_gstin",    "GSTIN (auto-fills PAN & state)", "Data"),
    ("_address",  "Address (shop / street / area)", "Data"),
    ("_city",     "City / District",                "Data"),
    ("_state",    "State",                          "Select"),
    ("_pincode",  "PIN Code",                       "Data"),
]

# GSTIN state code (first 2 digits) → state name, for the auto-created address
_GST_STATES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi",
    "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep Islands",
    "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana",
    "37": "Andhra Pradesh", "38": "Ladakh",
}


@frappe.whitelist()
def get_create_meta(doctype):
    """Fields needed to create a record natively. Doctypes with a required
    child table are refused unless the table is supported (_CHILD_CREATE) —
    then its row fields are returned too (mobile line-item editor)."""
    if not frappe.has_permission(doctype, "create"):
        frappe.throw(_("You are not permitted to create {0}").format(doctype),
                     frappe.PermissionError)

    if doctype == "Payment Entry":
        # Curated MSME payment form — the raw doctype (paid_from account
        # pickers over the whole CoA) is desk territory.
        modes = frappe.get_all("Mode of Payment", filters={"enabled": 1}, pluck="name")
        fields = [
            {"fieldname": "payment_type", "label": _("Payment Type"), "fieldtype": "Select",
             "options": "Receive\nPay", "reqd": 1, "default": "Receive"},
            {"fieldname": "_customer", "label": _("Customer (when receiving)"),
             "fieldtype": "Link", "options": "Customer", "reqd": 0, "default": ""},
            {"fieldname": "_supplier", "label": _("Supplier (when paying)"),
             "fieldtype": "Link", "options": "Supplier", "reqd": 0, "default": ""},
            {"fieldname": "amount", "label": _("Amount"), "fieldtype": "Currency",
             "reqd": 1, "default": ""},
            {"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date",
             "reqd": 1, "default": nowdate()},
            {"fieldname": "_mode", "label": _("Mode of Payment"), "fieldtype": "Select",
             "options": "\n".join(modes), "reqd": 0,
             "default": (modes[0] if modes else "")},
            {"fieldname": "reference_no", "label": _("Reference No (UTR / cheque)"),
             "fieldtype": "Data", "reqd": 0, "default": ""},
        ]
        return {"creatable": True, "doctype": doctype, "fields": fields, "child": None,
                "submittable": int(bool(frappe.has_permission(doctype, "submit")))}

    if doctype == "Journal Entry":
        # Simple two-sided posting: debit one account, credit another.
        fields = [
            {"fieldname": "_debit_account", "label": _("Debit — expense / where money went"),
             "fieldtype": "Link", "options": "Account", "reqd": 1, "default": ""},
            {"fieldname": "_credit_account", "label": _("Credit — paid from (bank / cash)"),
             "fieldtype": "Link", "options": "Account", "reqd": 1, "default": ""},
            {"fieldname": "amount", "label": _("Amount"), "fieldtype": "Currency",
             "reqd": 1, "default": ""},
            {"fieldname": "posting_date", "label": _("Date"), "fieldtype": "Date",
             "reqd": 1, "default": nowdate()},
            {"fieldname": "user_remark", "label": _("Remark (e.g. bank charges)"),
             "fieldtype": "Small Text", "reqd": 0, "default": ""},
        ]
        return {"creatable": True, "doctype": doctype, "fields": fields, "child": None,
                "submittable": int(bool(frappe.has_permission(doctype, "submit")))}

    if doctype in _PARTY_FORM:
        name_field = _PARTY_FORM[doctype]
        states = "\n".join(sorted(set(_GST_STATES.values())))
        fields = [{"fieldname": name_field, "label": _("Name"), "fieldtype": "Data",
                   "options": "", "reqd": 1, "default": ""}]
        for fn, label, ftype in _PARTY_EXTRA_FIELDS:
            fields.append({"fieldname": fn, "label": _(label), "fieldtype": ftype,
                           "options": states if fn == "_state" else "",
                           "reqd": 0, "default": ""})
        return {"creatable": True, "doctype": doctype, "fields": fields,
                "child": None, "submittable": 0}
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

    fields = _create_fields(meta, perm, doctype=doctype)
    if spec:
        for f in fields:
            if f["fieldname"] in spec.get("parent_reqd", ()):
                f["reqd"] = 1

    # taxable docs: let the user pick the GST template like the desk does —
    # blank means auto (In-State/Out-State by the customer's state)
    if doctype in _TAXABLE_DOCTYPES and meta.has_field("taxes_and_charges"):
        templates = frappe.get_all(_taxes_master(doctype), filters={"disabled": 0},
                                   pluck="name")
        if templates:
            fields.append({"fieldname": "_taxes",
                           "label": _("Taxes (blank = auto by customer state)"),
                           "fieldtype": "Select",
                           "options": "\n".join(templates),
                           "reqd": 0, "default": ""})

    return {"creatable": True, "doctype": doctype, "fields": fields, "child": child,
            "submittable": int(bool(meta.is_submittable
                                    and frappe.has_permission(doctype, "submit")))}


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
    # only pickable records: ledger accounts, not group nodes
    filters = {"is_group": 0} if meta.has_field("is_group") else None
    wanted = ["name"] + ([title] if title != "name" else [])
    rows = frappe.get_list(doctype, filters=filters, or_filters=or_filters,
                           fields=wanted, page_length=int(page_length),
                           order_by="modified desc")
    return [{"value": r.get("name"), "label": str(r.get(title) or r.get("name"))}
            for r in rows]


@frappe.whitelist()
def create_doc(doctype, values, submit=0):
    """Create a record from the native form (permissions + validations enforced).
    `values` may include a list under the supported child fieldname
    (e.g. Material Request "items") — rows are filtered the same way.
    `submit=1` also submits the new document (Create & Submit)."""
    if isinstance(values, str):
        values = frappe.parse_json(values)
    if not frappe.has_permission(doctype, "create"):
        frappe.throw(_("You are not permitted to create {0}").format(doctype),
                     frappe.PermissionError)

    if doctype == "Payment Entry":
        return _create_party_payment(values or {}, submit)
    if doctype == "Journal Entry":
        return _create_simple_je(values or {}, submit)
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

    # company is hidden on the mobile form (_CREATE_AUTO) — backfill it
    if meta.has_field("company") and not doc.get("company"):
        doc.company = (frappe.defaults.get_user_default("Company")
                       or frappe.db.get_single_value("Global Defaults", "default_company"))
    # same-currency default the desk UI sets client-side (e.g. HRMS Expense
    # Claim makes exchange_rate mandatory)
    if meta.has_field("exchange_rate") and not doc.get("exchange_rate"):
        doc.exchange_rate = 1

    if doctype in _PARTY_FORM:
        _apply_party_gstin(doc, (values or {}).get("_gstin"))

    # explicitly chosen taxes template wins; blank = auto by customer state
    chosen_taxes = (values or {}).get("_taxes")
    if chosen_taxes and doctype in _TAXABLE_DOCTYPES and not doc.get("taxes"):
        _append_taxes(doc, chosen_taxes)

    _set_gst_tax_category(doc)
    _apply_taxes_template(doc)

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

    if frappe.utils.cint(submit) and doc.meta.is_submittable:
        doc.submit()

    warning = None
    if doctype in _PARTY_FORM:
        warning = _create_party_extras(doc, values or {})

    frappe.db.commit()
    out = {"name": doc.name, "docstatus": doc.docstatus}
    if warning:
        out["warning"] = warning
    return out


_TAXABLE_DOCTYPES = {
    "Quotation", "Sales Order", "Sales Invoice", "Delivery Note",
    "Purchase Order", "Purchase Invoice", "Purchase Receipt",
}


def _party_state(party_type, party):
    """Party's GST state — from their GSTIN first, else their address."""
    gstin = frappe.db.get_value(party_type, party, "gstin") \
        if frappe.get_meta(party_type).has_field("gstin") else None
    if gstin and _GST_STATES.get(gstin[:2]):
        return _GST_STATES[gstin[:2]]
    links = frappe.get_all("Dynamic Link", filters={
        "link_doctype": party_type, "link_name": party, "parenttype": "Address",
    }, pluck="parent")
    if links:
        rows = frappe.get_all("Address", filters={"name": ("in", links)},
                              fields=["state"],
                              order_by="is_primary_address desc", limit_page_length=1)
        if rows:
            return rows[0].state
    return None


def _set_gst_tax_category(doc):
    """India: derive In-State / Out-State on app-created documents so
    ERPNext auto-applies the matching GST taxes template (CGST+SGST vs
    IGST) during set_missing_values. No-op when tax categories are absent
    (non-India site), a category is already set, or taxes were provided."""
    if doc.doctype not in _TAXABLE_DOCTYPES or doc.get("tax_category") \
            or doc.get("taxes") or not doc.meta.has_field("tax_category"):
        return
    if not frappe.db.exists("Tax Category", "In-State"):
        return

    company_gstin = (frappe.get_cached_value("Company", doc.company, "gstin")
                     if doc.get("company")
                     and frappe.get_meta("Company").has_field("gstin") else None)
    company_state = _GST_STATES.get((company_gstin or "")[:2])

    party_type, party = None, None
    if doc.get("customer"):
        party_type, party = "Customer", doc.customer
    elif doc.get("supplier"):
        party_type, party = "Supplier", doc.supplier
    elif doc.doctype == "Quotation" and doc.get("party_name"):
        party_type, party = (doc.get("quotation_to") or "Customer"), doc.party_name
    pstate = _party_state(party_type, party) if (party_type == "Customer"
              or party_type == "Supplier") and party else None

    if company_state and pstate:
        doc.tax_category = "In-State" if company_state == pstate else "Out-State"
    else:
        doc.tax_category = "In-State"   # local trade is the MSME default


def _taxes_master(doctype):
    return ("Sales Taxes and Charges Template"
            if doctype in ("Quotation", "Sales Order", "Sales Invoice",
                           "Delivery Note")
            else "Purchase Taxes and Charges Template")


def _append_taxes(doc, tname):
    """Set the named taxes template on the doc and copy in its rows."""
    try:
        from erpnext.controllers.accounts_controller import get_taxes_and_charges
        master = _taxes_master(doc.doctype)
        doc.taxes_and_charges = tname
        for row in get_taxes_and_charges(master, tname) or []:
            doc.append("taxes", row)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "midhunatech: taxes template")


def _apply_taxes_template(doc):
    """Copy the tax rows from the taxes template matching the document's
    tax category (fallback: the default template). The desk does this from
    a client script, so server-side creates must do it themselves."""
    if doc.doctype not in _TAXABLE_DOCTYPES or doc.get("taxes"):
        return
    if not doc.meta.has_field("taxes_and_charges") or not doc.get("company"):
        return
    # Purchases from an unregistered supplier carry no input GST — applying
    # a GST template there is rejected ("supplier without GSTIN").
    if doc.get("supplier") and frappe.get_meta("Supplier").has_field("gstin") \
            and not frappe.db.get_value("Supplier", doc.supplier, "gstin"):
        return
    master = _taxes_master(doc.doctype)
    tname = None
    if doc.get("tax_category"):
        tname = frappe.db.get_value(master, {"company": doc.company, "disabled": 0,
                                             "tax_category": doc.tax_category})
    if not tname:
        tname = frappe.db.get_value(master, {"company": doc.company, "disabled": 0,
                                             "is_default": 1})
    if tname:
        _append_taxes(doc, tname)


def _apply_party_gstin(doc, gstin):
    """GSTIN on the simple party form → gstin, PAN and GST category on the
    party itself (fields exist when india_compliance is installed)."""
    gstin = (gstin or "").strip().upper()
    if not gstin:
        return
    if doc.meta.has_field("gstin"):
        doc.gstin = gstin
    if doc.meta.has_field("pan") and len(gstin) == 15:
        doc.pan = gstin[2:12]
    if doc.meta.has_field("gst_category"):
        doc.gst_category = "Registered Regular"


def _create_party_extras(doc, values):
    """Turn the _-prefixed simple-form fields into a linked Contact (mobile)
    and Address (street/city/PIN, state auto-derived from the GSTIN). A
    failure here never fails the party creation — returns a warning string."""
    name_label = doc.get(_PARTY_FORM[doc.doctype]) or doc.name
    gstin = (values.get("_gstin") or "").strip().upper()
    mobile = (values.get("_mobile") or "").strip()
    problems = []

    if mobile:
        try:
            frappe.get_doc({
                "doctype": "Contact", "first_name": name_label,
                "is_primary_contact": 1,
                "phone_nos": [{"phone": mobile, "is_primary_mobile_no": 1}],
                "links": [{"link_doctype": doc.doctype, "link_name": doc.name}],
            }).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "midhunatech: party contact")
            problems.append(_("mobile number could not be saved"))

    if (values.get("_address") or values.get("_city") or values.get("_pincode")
            or values.get("_state")):
        try:
            addr = {
                "doctype": "Address", "address_title": name_label,
                "address_type": "Billing",
                "address_line1": values.get("_address") or name_label,
                "city": values.get("_city") or "",
                "pincode": values.get("_pincode") or "",
                "is_primary_address": 1, "is_shipping_address": 1,
                "links": [{"link_doctype": doc.doctype, "link_name": doc.name}],
            }
            # typed state wins; GSTIN state code fills the gap
            state = (values.get("_state")
                     or (_GST_STATES.get(gstin[:2]) if gstin else None))
            if state:
                addr["state"] = state
            if frappe.db.exists("Country", "India"):
                addr["country"] = "India"
            adoc = frappe.get_doc(addr)
            if gstin and adoc.meta.has_field("gstin"):
                adoc.gstin = gstin
            adoc.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "midhunatech: party address")
            problems.append(_("address could not be saved"))

    if problems:
        return _("Saved, but {0} — you can add it from the desk later.").format(
            _(" and ").join(problems))
    return None


def _einvoice_available(doc):
    """1 when the india_compliance e-Invoice button should show: submitted
    Sales Invoice, no IRN yet, and e-invoicing applicable per GST Settings."""
    if doc.doctype != "Sales Invoice" or doc.docstatus != 1 or doc.get("irn"):
        return 0
    try:
        from india_compliance.gst_india.utils.e_invoice import (
            validate_e_invoice_applicability,
        )
        return 1 if validate_e_invoice_applicability(doc, throw=False) else 0
    except ImportError:
        return 0
    except Exception:
        return 0


def _mode_account(mode, company):
    """The Mode of Payment's default account for this company."""
    if not mode:
        return None
    return frappe.db.get_value("Mode of Payment Account",
                               {"parent": mode, "company": company},
                               "default_account")


def _create_party_payment(values, submit=0):
    """The curated Payments '+' form → a properly-booked Payment Entry:
    party receivable/payable account on one side, the Mode of Payment's
    cash/bank account on the other, auto-allocated against the party's
    outstanding invoices oldest-first. Unallocated remainder = advance."""
    from frappe.utils import cint, flt

    ptype = values.get("payment_type") or "Receive"
    party_type = "Customer" if ptype == "Receive" else "Supplier"
    party = values.get("_customer") if party_type == "Customer" else values.get("_supplier")
    if not party:
        frappe.throw(_("Select the {0} for this {1} payment").format(
            _(party_type), _(ptype)))
    amount = flt(values.get("amount"))
    if amount <= 0:
        frappe.throw(_("Enter the payment amount"))

    company = (frappe.defaults.get_user_default("Company")
               or frappe.db.get_single_value("Global Defaults", "default_company"))
    from erpnext.accounts.party import get_party_account
    party_account = get_party_account(party_type, party, company)

    mode = values.get("_mode")
    bank_account = _mode_account(mode, company)
    if not bank_account:
        from erpnext.accounts.utils import get_default_bank_cash_account
        acc = (get_default_bank_cash_account(company, "Cash")
               or get_default_bank_cash_account(company, "Bank"))
        bank_account = acc and acc.get("account")
    if not bank_account:
        frappe.throw(_("No cash/bank account found — set a default account on "
                       "the Mode of Payment"))

    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = ptype
    pe.company = company
    pe.posting_date = values.get("posting_date") or nowdate()
    pe.mode_of_payment = mode
    pe.party_type = party_type
    pe.party = party
    if ptype == "Receive":
        pe.paid_from, pe.paid_to = party_account, bank_account
    else:
        pe.paid_from, pe.paid_to = bank_account, party_account
    pe.paid_amount = amount
    pe.received_amount = amount
    pe.source_exchange_rate = 1
    pe.target_exchange_rate = 1

    # allocate against outstanding invoices, oldest first
    try:
        from erpnext.accounts.utils import get_outstanding_invoices
        outstanding = get_outstanding_invoices(party_type, party, [party_account])
        remaining = amount
        for inv in sorted(outstanding, key=lambda d: d.get("posting_date") or ""):
            if remaining <= 0:
                break
            due = flt(inv.get("outstanding_amount"))
            if due <= 0:
                continue
            alloc = min(remaining, due)
            pe.append("references", {
                "reference_doctype": inv.get("voucher_type"),
                "reference_name":   inv.get("voucher_no"),
                "total_amount":     inv.get("invoice_amount"),
                "outstanding_amount": due,
                "allocated_amount": alloc,
            })
            remaining -= alloc
    except Exception:
        frappe.log_error(frappe.get_traceback(), "midhunatech: payment allocation")

    pe.reference_no = values.get("reference_no") or f"{party} {pe.posting_date}"
    pe.reference_date = pe.posting_date
    pe.insert()
    if cint(submit):
        pe.submit()
    frappe.db.commit()
    return {"name": pe.name, "docstatus": pe.docstatus}


def _create_simple_je(values, submit=0):
    """The simple Journal Entry form: debit one account, credit another,
    one amount — bank charges, office expenses, corrections."""
    from frappe.utils import cint, flt

    debit_acc = values.get("_debit_account")
    credit_acc = values.get("_credit_account")
    amount = flt(values.get("amount"))
    if not debit_acc or not credit_acc:
        frappe.throw(_("Pick both accounts — debit and credit"))
    if debit_acc == credit_acc:
        frappe.throw(_("Debit and credit accounts must be different"))
    if amount <= 0:
        frappe.throw(_("Enter the amount"))

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.company = (frappe.defaults.get_user_default("Company")
                  or frappe.db.get_single_value("Global Defaults", "default_company"))
    je.posting_date = values.get("posting_date") or nowdate()
    je.user_remark = values.get("user_remark") or ""
    je.append("accounts", {"account": debit_acc, "debit_in_account_currency": amount})
    je.append("accounts", {"account": credit_acc, "credit_in_account_currency": amount})
    je.insert()
    if cint(submit):
        je.submit()
    frappe.db.commit()
    return {"name": je.name, "docstatus": je.docstatus}


def _can_pay(doc):
    """1 when the Record-Payment button should show: a submitted Sales /
    Purchase Invoice with outstanding amount, user allowed to make payments."""
    from frappe.utils import flt
    if doc.doctype not in ("Sales Invoice", "Purchase Invoice") or doc.docstatus != 1:
        return 0
    if flt(doc.get("outstanding_amount")) <= 0:
        return 0
    return int(bool(frappe.has_permission("Payment Entry", "create")))


@frappe.whitelist()
def get_payment_meta(doctype, name):
    """What the mobile Record-Payment form needs: outstanding, today, and the
    Modes of Payment configured for the company."""
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("read")
    modes = frappe.get_all("Mode of Payment", filters={"enabled": 1}, pluck="name")
    return {
        "outstanding": doc.get("outstanding_amount"),
        "today":       nowdate(),
        "modes":       modes,
    }


@frappe.whitelist()
def record_payment(doctype, name, amount=None, posting_date=None,
                   mode_of_payment=None, reference_no=None):
    """Create AND submit a Payment Entry against a submitted invoice — the
    one-tap 'customer paid us' / 'we paid the supplier' flow."""
    from frappe.utils import flt
    if doctype not in ("Sales Invoice", "Purchase Invoice"):
        frappe.throw(_("Payments can only be recorded against invoices"))
    frappe.has_permission("Payment Entry", "create", throw=True)

    from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
    pe = get_payment_entry(doctype, name)
    if posting_date:
        pe.posting_date = posting_date
    if amount:
        amount = flt(amount)
        pe.paid_amount = amount
        pe.received_amount = amount
        for ref in pe.references:
            ref.allocated_amount = amount
    if mode_of_payment:
        pe.mode_of_payment = mode_of_payment
        acc = _mode_account(mode_of_payment, pe.company)
        if acc:
            if pe.payment_type == "Receive":
                pe.paid_to = acc
            else:
                pe.paid_from = acc
    # Bank transactions need a reference — default to the invoice number so
    # one-tap payment works; a typed UTR / cheque no. wins.
    pe.reference_no = reference_no or pe.reference_no or name
    pe.reference_date = posting_date or nowdate()
    pe.insert()
    pe.submit()
    frappe.db.commit()
    return {"name": pe.name}


@frappe.whitelist()
def get_edit_meta(doctype, name):
    """The create form's field list pre-filled with a draft's current
    values (child rows included) — powers Edit on drafts."""
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("write")
    if doc.docstatus != 0:
        frappe.throw(_("Only draft documents can be edited"))
    if doctype in _PARTY_FORM or doctype in ("Payment Entry", "Journal Entry"):
        frappe.throw(_("This document type cannot be edited here"))

    info = get_create_meta(doctype)
    if not info.get("creatable"):
        frappe.throw(info.get("reason") or _("Not editable"))
    for f in info["fields"]:
        fn = f["fieldname"]
        if fn == "_taxes":
            f["default"] = doc.get("taxes_and_charges") or ""
        elif not fn.startswith("_"):
            v = doc.get(fn)
            f["default"] = "" if v is None else v
    rows = []
    if info.get("child"):
        cfields = [cf["fieldname"] for cf in info["child"]["fields"]]
        for row in doc.get(info["child"]["fieldname"]) or []:
            rows.append({fn: ("" if row.get(fn) is None else row.get(fn))
                         for fn in cfields})
    info["name"] = name
    info["child_rows"] = rows
    return info


@frappe.whitelist()
def update_doc(doctype, name, values, submit=0):
    """Save changes to a draft from the edit form (same field filtering as
    create); submit=1 also submits it."""
    from frappe.utils import cint
    if isinstance(values, str):
        values = frappe.parse_json(values)
    values = values or {}
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("write")
    if doc.docstatus != 0:
        frappe.throw(_("Only draft documents can be edited"))
    if doctype in _PARTY_FORM or doctype in ("Payment Entry", "Journal Entry"):
        frappe.throw(_("This document type cannot be edited here"))

    meta = frappe.get_meta(doctype)
    writable = _permitted_fields(meta, "write")
    skip = _SKIP | {"owner", "creation", "modified", "modified_by", "docstatus"}
    spec = _CHILD_CREATE.get(doctype)
    child_field = spec["table"] if spec else None

    for key, val in values.items():
        if key == child_field or key.startswith("_"):
            continue
        if key in writable and key not in skip:
            doc.set(key, val if val not in (None, "") else None)

    # taxes template re-selection (blank keeps whatever the doc has)
    sel = values.get("_taxes")
    if sel and doctype in _TAXABLE_DOCTYPES and meta.has_field("taxes_and_charges") \
            and sel != (doc.get("taxes_and_charges") or ""):
        doc.set("taxes", [])
        _append_taxes(doc, sel)

    rows = values.get(child_field) if child_field else None
    if child_field and isinstance(rows, list):
        cmeta = frappe.get_meta(meta.get_field(child_field).options)
        cwritable = _permitted_fields(cmeta, "write")
        doc.set(child_field, [])
        for row in rows:
            if not isinstance(row, dict):
                continue
            clean = {k: v for k, v in row.items()
                     if k in cwritable and k not in skip and v not in (None, "")}
            for ck, pk in (spec.get("copy_parent") or {}).items():
                if not clean.get(ck) and values.get(pk):
                    clean[ck] = values[pk]
            if clean:
                doc.append(child_field, clean)

    doc.save()
    if cint(submit):
        doc.submit()
    frappe.db.commit()
    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist()
def delete_doc(doctype, name):
    """Delete a draft or cancelled document (submitted ones must be
    cancelled first — same rule as the desk)."""
    doc = frappe.get_doc(doctype, name)
    if doc.docstatus == 1:
        frappe.throw(_("Cancel the document before deleting it"))
    frappe.delete_doc(doctype, name)   # enforces delete permission
    frappe.db.commit()
    return {"ok": True}


@frappe.whitelist()
def cancel_doc(doctype, name):
    """Cancel a submitted document (reverses its GL/stock effects)."""
    doc = frappe.get_doc(doctype, name)
    doc.cancel()
    frappe.db.commit()
    return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist()
def amend_doc(doctype, name):
    """Amend a cancelled document — returns the new editable draft copy."""
    src = frappe.get_doc(doctype, name)
    src.check_permission("read")
    if src.docstatus != 2:
        frappe.throw(_("Only a cancelled document can be amended"))
    if not frappe.has_permission(doctype, "create"):
        frappe.throw(_("You are not permitted to create {0}").format(doctype),
                     frappe.PermissionError)
    new = frappe.copy_doc(src)
    new.amended_from = name
    new.docstatus = 0
    new.insert()
    frappe.db.commit()
    return {"name": new.name}


@frappe.whitelist()
def submit_doc(doctype, name):
    """Submit a draft from the PWA (doc.submit() enforces permissions and
    runs the full validation/GL posting)."""
    doc = frappe.get_doc(doctype, name)
    doc.submit()
    frappe.db.commit()
    return {"name": doc.name, "docstatus": doc.docstatus}


def _ewaybill_available(doc):
    """1 when the e-Way Bill button should show: submitted Sales Invoice,
    no e-way bill yet, and india_compliance says one is applicable."""
    if doc.doctype != "Sales Invoice" or doc.docstatus != 1 or doc.get("ewaybill"):
        return 0
    try:
        from india_compliance.gst_india.utils.e_waybill import EWaybillData
        EWaybillData(doc).validate_applicability()
        return 1
    except ImportError:
        return 0
    except Exception:
        return 0


@frappe.whitelist()
def generate_ewaybill(name):
    """Generate the e-Way Bill for a submitted Sales Invoice through
    india_compliance (same GST API credentials as e-Invoice)."""
    frappe.has_permission("Sales Invoice", "submit", doc=name, throw=True)
    try:
        from india_compliance.gst_india.utils.e_waybill import generate_e_waybill
    except ImportError:
        frappe.throw(_("India Compliance is not installed on this site."))
    generate_e_waybill(doctype="Sales Invoice", docname=name)
    return {"ewaybill": frappe.db.get_value("Sales Invoice", name, "ewaybill")}


@frappe.whitelist()
def generate_einvoice(name):
    """Generate the IRN/e-Invoice for a submitted Sales Invoice through
    india_compliance (needs GST API credentials in GST Settings)."""
    frappe.has_permission("Sales Invoice", "submit", doc=name, throw=True)
    try:
        from india_compliance.gst_india.utils.e_invoice import generate_e_invoice
    except ImportError:
        frappe.throw(_("India Compliance is not installed on this site."))
    generate_e_invoice(name, throw=True)
    return {"irn": frappe.db.get_value("Sales Invoice", name, "irn")}


@frappe.whitelist()
def email_doc(doctype, name, recipients, subject=None, message=None):
    """Email a document with its PDF attached (default print format), the
    way the desk's Email button does — but one tap from the PWA."""
    doc = frappe.get_doc(doctype, name)
    doc.check_permission("email")
    recipients = (recipients or "").strip()
    if not recipients:
        frappe.throw(_("Enter a recipient email address"))

    subject = (subject or "").strip() or f"{_(doctype)} {name}"
    message = (message or "").strip() or _("Please find attached {0} {1}.").format(_(doctype), name)

    try:
        attachment = frappe.attach_print(doctype, name, doc=doc,
                                         print_letterhead=True)
        frappe.sendmail(
            recipients=[r.strip() for r in recipients.replace(";", ",").split(",") if r.strip()],
            subject=subject,
            message=message,
            attachments=[attachment],
            reference_doctype=doctype,
            reference_name=name,
        )
    except frappe.OutgoingEmailError:
        frappe.throw(_("No outgoing email account is set up on this site. "
                       "Ask your administrator to configure one (Settings → Email Account)."))
    return {"ok": True}


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
