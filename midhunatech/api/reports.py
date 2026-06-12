# Copyright (c) 2026, Midhunatech and Contributors
# License: GPL-3.0
"""Run any Frappe report and return mobile-friendly columns/rows + the
report's summary KPIs, chart and message so the PWA can render the full
report experience (not just the table)."""

import json
import re

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, nowdate, strip_html_tags


# Interactive filters the mobile filter bar offers per report (beyond dates).
# Link filters use the same autocomplete API as the create forms.
_REPORT_FILTERS = {
    # as_list: the desk defines these as MultiSelectList — the report code
    # expects a list, a bare string crashes the query builder
    "Stock Balance": [
        {"fieldname": "item_code", "label": "Item", "fieldtype": "Link", "options": "Item", "as_list": 1},
        {"fieldname": "warehouse", "label": "Warehouse", "fieldtype": "Link", "options": "Warehouse", "as_list": 1},
    ],
    "Stock Ledger": [
        {"fieldname": "item_code", "label": "Item", "fieldtype": "Link", "options": "Item"},
        {"fieldname": "warehouse", "label": "Warehouse", "fieldtype": "Link", "options": "Warehouse"},
    ],
    "General Ledger": [
        {"fieldname": "party_type", "label": "Party Type", "fieldtype": "Select",
         "options": "\nCustomer\nSupplier\nEmployee"},
    ],
}

# Curated default columns for common standard reports — used when the tile
# has no Fields (JSON array) configured. The tile's JSON always wins; reports
# not listed here keep all their columns.
_DEFAULT_REPORT_COLUMNS = {
    "Stock Balance":       ["item_code", "warehouse", "bal_qty", "bal_val"],
    "Stock Ledger":        ["date", "item_code", "warehouse", "actual_qty", "qty_after_transaction"],
    "General Ledger":      ["posting_date", "account", "debit", "credit", "balance", "voucher_no"],
    "Trial Balance":       ["account", "debit", "credit", "closing_debit", "closing_credit"],
    "Accounts Receivable": ["posting_date", "party", "voucher_no", "invoiced", "paid", "outstanding"],
    "Accounts Payable":    ["posting_date", "party", "voucher_no", "invoiced", "paid", "outstanding"],
}

# Mobile filter bar renders these fieldtypes (MultiSelectList is mapped to a
# Link autocomplete + as_list). Everything else a custom report defines is
# left to its server-side defaults.
_FILTERABLE_TYPES = {"Link", "Select", "Data", "Date", "Datetime", "MultiSelectList"}

# JS default expressions we can evaluate server-side (custom report filters)
_JS_DEFAULTS = (
    (re.compile(r"frappe\.datetime\.get_today\(\)"), lambda: nowdate()),
    (re.compile(r"frappe\.datetime\.month_start\(\)"), lambda: get_first_day(nowdate())),
    (re.compile(r"frappe\.datetime\.month_end\(\)"), lambda: get_last_day(nowdate())),
    (re.compile(r"frappe\.defaults\.get_user_default\(\s*[\"']Company[\"']\s*\)"),
     lambda: (frappe.defaults.get_user_default("Company")
              or frappe.db.get_single_value("Global Defaults", "default_company") or "")),
)


def _custom_filter_meta(report):
    """Filters for CUSTOM (is_standard=No) Query/Script reports. They live
    either in the Report doc's `filters` child table, or — far more commonly
    for DB Script Reports — as a JS array inside the `javascript` field,
    which the desk evals client-side and the mobile app cannot. Parse the
    flat keys (fieldname/label/fieldtype/options/reqd + known default
    expressions) out of that JS instead, so the mobile filter bar works for
    custom reports too. Any parse failure returns [] — the report still runs
    with its server defaults."""
    try:
        if (report.get("is_standard") or "No") == "Yes":
            return []

        # 1. structured filters child table, when maintained
        meta = []
        for f in (report.get("filters") or []):
            meta.append({
                "fieldname": f.get("fieldname"), "label": f.get("label") or f.get("fieldname"),
                "fieldtype": f.get("fieldtype") or "Data", "options": f.get("options") or "",
                "default": f.get("default") or "", "reqd": int(f.get("mandatory") or 0),
            })
        if meta:
            return _mobile_filters(meta)

        # 2. parse the filters array out of the report JS
        js = report.get("javascript") or ""
        m = re.search(r"filters\s*:\s*\[", js)
        if not m:
            return []
        body = js[m.end():]
        # cut at the array end: track [ ] depth, skipping string literals
        depth, i, in_str, q = 1, 0, False, ""
        while i < len(body) and depth:
            ch = body[i]
            if in_str:
                if ch == "\\":
                    i += 2
                    continue
                if ch == q:
                    in_str = False
            elif ch in "\"'`":
                in_str, q = True, ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
            i += 1
        body = body[: i - 1]

        # chunk per filter: from each fieldname key to the next
        starts = [s.start() for s in re.finditer(r"fieldname\s*:", body)]
        meta = []
        for n, s in enumerate(starts):
            chunk = body[s: starts[n + 1] if n + 1 < len(starts) else len(body)]

            def grab(key):
                g = re.search(key + r"""\s*:\s*(?:__\(\s*)?["']([^"']*)["']""", chunk)
                return g.group(1) if g else ""

            fieldname = grab("fieldname")
            if not fieldname:
                continue
            default = grab("default")
            if not default:
                dm = re.search(r"default\s*:\s*([^\n,]+)", chunk)
                if dm:
                    for rx, fn in _JS_DEFAULTS:
                        if rx.search(dm.group(1)):
                            default = fn()
                            break
            meta.append({
                "fieldname": fieldname,
                "label": grab("label") or fieldname.replace("_", " ").title(),
                "fieldtype": grab("fieldtype") or "Data",
                "options": grab("options"),
                "default": default,
                "reqd": 1 if re.search(r"reqd\s*:\s*(1|true)", chunk) else 0,
            })
        return _mobile_filters(meta)
    except Exception:
        return []


def _mobile_filters(meta):
    """Keep only what the mobile bar can render; map MultiSelectList to a
    Link autocomplete that submits a list. from_date/to_date are handled by
    the dedicated date bar, so they carry only their defaults (hidden)."""
    out = []
    for f in meta:
        if not f.get("fieldname") or f.get("fieldtype") not in _FILTERABLE_TYPES:
            continue
        if f["fieldtype"] == "MultiSelectList":
            f["fieldtype"], f["as_list"] = "Link", 1
        if f["fieldtype"] == "Datetime":
            f["fieldtype"] = "Date"
        if f["fieldname"] in ("from_date", "to_date"):
            f["hidden"] = 1  # default still applied; input comes from the date bar
        out.append(f)
    return out


@frappe.whitelist()
def run(report_name, filters=None, fields=None):
    report = frappe.get_doc("Report", report_name)
    if not report.is_permitted():
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    if isinstance(filters, str):
        filters = json.loads(filters or "{}")
    filters = {k: v for k, v in (filters or {}).items() if v not in (None, "")}
    filter_meta = _REPORT_FILTERS.get(report_name) or _custom_filter_meta(report)

    # custom reports tell us whether a from/to date bar makes sense at all;
    # standard reports always get one (we can't introspect their filters)
    custom_meta = bool(filter_meta) and report_name not in _REPORT_FILTERS
    has_date_range = 1
    if custom_meta:
        has_date_range = int(any(f["fieldname"] in ("from_date", "to_date") for f in filter_meta))
    filter_meta_visible = [f for f in filter_meta if not f.get("hidden")]

    from frappe.desk.query_report import run as query_report_run

    # Reports with an interactive filter bar always get the defaults merged
    # (so the date range is real and visible). Everything else: try the given
    # filters first; many standard reports (Balance Sheet, GL, ...) have
    # mandatory filters the mobile app does not collect — on failure retry
    # once with sensible defaults merged in.
    if filter_meta:
        # precedence: user input > the report's own filter defaults > generics
        base = dict(filters)
        for f in filter_meta:
            dv = f.get("default")
            if dv not in (None, "") and base.get(f["fieldname"]) in (None, ""):
                base[f["fieldname"]] = dv
        applied = _merge_defaults(base)
        for f in filter_meta:
            if f.get("as_list") and isinstance(applied.get(f["fieldname"]), str):
                applied[f["fieldname"]] = [applied[f["fieldname"]]]
        try:
            res = query_report_run(report_name, filters=applied, ignore_prepared_report=True)
        except Exception as e:
            # keep the filter bar usable so the user can fix the filters
            frappe.clear_messages()
            return {
                "columns": [], "rows": [], "summary": [], "chart": None, "message": None,
                "error": _err_text(e), "applied_filters": applied,
                "filter_meta": filter_meta_visible, "has_date_range": has_date_range,
            }
    else:
        try:
            res = query_report_run(report_name, filters=filters, ignore_prepared_report=True)
            applied = filters
            if not res.get("columns") and not res.get("result"):
                # frappe swallows mandatory-filter errors and returns an empty
                # result (e.g. General Ledger) — treat that as "needs defaults"
                raise frappe.ValidationError("empty result")
        except Exception:
            frappe.clear_messages()
            applied = _merge_defaults(filters)
            res = query_report_run(report_name, filters=applied, ignore_prepared_report=True)

    columns = []
    for c in res.get("columns") or []:
        if isinstance(c, str):
            label = c.split(":")[0]
            columns.append({"label": label, "fieldname": label})
        else:
            columns.append({
                "label": c.get("label") or c.get("fieldname"),
                "fieldname": c.get("fieldname") or c.get("label"),
                "fieldtype": c.get("fieldtype"),
            })

    rows = []
    for r in (res.get("result") or [])[:500]:
        if isinstance(r, (list, tuple)):
            row = {columns[i]["fieldname"]: r[i] for i in range(min(len(columns), len(r)))}
            rows.append(row)
        elif isinstance(r, dict):
            rows.append(r)

    # Per-tile column control — must run AFTER rows are built, because
    # list-form rows are mapped to fieldnames positionally from the full
    # column list. No tile config → curated defaults for common reports.
    selected = _select_columns(columns, fields or _DEFAULT_REPORT_COLUMNS.get(report_name))
    if selected is not columns:
        columns = selected
        keep = {c["fieldname"] for c in columns} | {"indent", "bold", "currency"}
        rows = [{k: v for k, v in r.items() if k in keep} for r in rows]

    return {
        "columns": columns,
        "rows": rows,
        "summary": _clean_summary(res.get("report_summary")),
        "chart": _clean_chart(res.get("chart")),
        "message": _clean_message(res.get("message")),
        "applied_filters": applied,
        "filter_meta": filter_meta_visible,
        "has_date_range": has_date_range,
    }


def _err_text(e):
    s = strip_html_tags(str(e) or e.__class__.__name__)
    return re.sub(r"\s+", " ", s).strip()[:300]


def _select_columns(columns, fields):
    """Per-tile column control — same idea as doctype_fields on doc_list
    tiles: the module row's Fields JSON array picks which report columns
    show, in that order. Names match column fieldname OR label,
    case-insensitively; unknown names are dropped. An empty/invalid
    selection (or one matching nothing) keeps all columns, so a typo can
    never blank a report."""
    if isinstance(fields, str):
        try:
            fields = json.loads(fields or "[]")
        except Exception:
            fields = []
    if not fields or not isinstance(fields, (list, tuple)):
        return columns

    by_key = {}
    for c in columns:
        for k in (c.get("fieldname"), c.get("label")):
            if k:
                by_key.setdefault(str(k).strip().lower(), c)

    picked = []
    for f in fields:
        c = by_key.get(str(f).strip().lower())
        if c and c not in picked:
            picked.append(c)
    return picked or columns


def _merge_defaults(filters):
    """User filters + the defaults the desk would normally preset (company,
    fiscal year, period dates). Extra keys are harmless — reports read only
    the filters they know."""
    today = nowdate()
    d = {
        "from_date": get_first_day(today),
        "to_date": today,
        "report_date": today,
        "as_on_date": today,
        "periodicity": "Yearly",
        "filter_based_on": "Fiscal Year",
        "range": "30, 60, 90, 120",
    }

    company = (frappe.defaults.get_user_default("Company")
               or frappe.db.get_single_value("Global Defaults", "default_company")
               or frappe.db.get_value("Company", {}, "name"))
    if company:
        d["company"] = company

    try:
        from erpnext.accounts.utils import get_fiscal_year
        fy = get_fiscal_year(today, company=company, as_dict=True)
        d.update({
            "fiscal_year": fy.name,
            "from_fiscal_year": fy.name,
            "to_fiscal_year": fy.name,
            "period_start_date": str(fy.year_start_date),
            "period_end_date": str(fy.year_end_date),
            "from_date": str(fy.year_start_date),
        })
    except Exception:
        pass

    d.update(filters or {})
    return d


def _clean_summary(summary):
    """report_summary → [{label, value, datatype, indicator}] (display-safe)."""
    out = []
    for s in summary or []:
        if not isinstance(s, dict):
            continue
        out.append({
            "label": strip_html_tags(str(s.get("label") or "")),
            "value": s.get("value"),
            "datatype": s.get("datatype"),
            "currency": s.get("currency"),
            "indicator": s.get("indicator"),
        })
    return out


def _clean_chart(chart):
    """Keep only what the frontend chart renderer needs."""
    if not isinstance(chart, dict) or not chart.get("data"):
        return None
    data = chart["data"]
    if not isinstance(data, dict) or not data.get("labels"):
        return None
    datasets = [
        {"name": strip_html_tags(str(ds.get("name") or "")), "values": ds.get("values") or []}
        for ds in (data.get("datasets") or [])
        if isinstance(ds, dict) and any(v for v in (ds.get("values") or []))
    ][:6]  # a phone chart with more series than this is unreadable
    if (chart.get("type") or "") in ("percentage", "pie", "donut"):
        datasets = datasets[:1]
    if not datasets:
        return None
    return {
        "type": chart.get("type") or "bar",
        "colors": chart.get("colors"),
        "data": {
            "labels": [strip_html_tags(str(l)) for l in data.get("labels") or []],
            "datasets": datasets,
        },
    }


def _clean_message(message):
    if not message:
        return None
    if isinstance(message, (list, tuple)):
        message = " · ".join(str(m) for m in message if m)
    return strip_html_tags(str(message)).strip() or None
