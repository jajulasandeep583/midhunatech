# Copyright (c) 2026, Midhunatech and Contributors
# License: GPL-3.0
"""Run any Frappe report and return mobile-friendly columns/rows + the
report's summary KPIs, chart and message so the PWA can render the full
report experience (not just the table)."""

import json

import frappe
from frappe import _
from frappe.utils import get_first_day, nowdate, strip_html_tags


@frappe.whitelist()
def run(report_name, filters=None):
    report = frappe.get_doc("Report", report_name)
    if not report.is_permitted():
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    if isinstance(filters, str):
        filters = json.loads(filters or "{}")
    filters = filters or {}

    from frappe.desk.query_report import run as query_report_run

    # First try with the given filters; many standard reports (Balance Sheet,
    # GL, Stock Balance, ...) have mandatory filters the mobile app does not
    # collect — on failure retry once with sensible defaults merged in.
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

    return {
        "columns": columns,
        "rows": rows,
        "summary": _clean_summary(res.get("report_summary")),
        "chart": _clean_chart(res.get("chart")),
        "message": _clean_message(res.get("message")),
        "applied_filters": applied,
    }


def _merge_defaults(filters):
    """User filters + the defaults the desk would normally preset (company,
    fiscal year, period dates). Extra keys are harmless — reports read only
    the filters they know."""
    today = nowdate()
    d = {
        "from_date": get_first_day(today),
        "to_date": today,
        "report_date": today,
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
