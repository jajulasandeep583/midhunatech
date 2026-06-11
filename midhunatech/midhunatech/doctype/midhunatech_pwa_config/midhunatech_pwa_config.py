# Copyright (c) 2024, Midhunatech and Contributors
# License: GPL-3.0

import frappe
from frappe.model.document import Document

scrub = frappe.scrub


class MidhunatechPWAConfig(Document):
    def before_save(self):
        self._sort_modules()
        self._compute_target_urls()
        self._bump_version()

    # ── sort tiles by display order ────────────────────────────────────────────
    def _sort_modules(self):
        rows = sorted(self.modules or [], key=lambda r: int(r.display_order or 0))
        for i, r in enumerate(rows, start=1):
            r.idx = i
        self.modules = rows

    # ── auto-compute target_url for every tile ─────────────────────────────────
    def _compute_target_urls(self):
        for m in self.modules or []:
            m.target_url = compute_target_url(m)

    # ── auto-increment patch version ───────────────────────────────────────────
    def _bump_version(self):
        parts = (self.pwa_version or "1.0.0").split(".")
        try:
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        except Exception:
            major, minor, patch = 1, 0, 0
        self.pwa_version = f"{major}.{minor}.{patch + 1}"


def compute_target_url(m):
    """Best-effort URL/route for a tile. Never wipes an existing target_url when
    the type-specific source field is empty (keeps the legacy /midhunatech app
    working — its rows store the doctype/card list in target_url)."""
    t = m.module_type
    existing = m.get("target_url") or ""
    dt = m.get("doctype_name")

    if t in ("doctype", "list_view"):
        return f"#list/{dt}" if dt else existing
    if t == "doc_list":
        # the doctype IS the target — prefer the explicit DocType field
        return (dt or "") or existing
    if t == "form_view":
        return f"/app/{scrub(dt)}/new" if dt else existing
    if t == "report":
        return f"/app/query-report/{m.get('report_name')}" if m.get("report_name") else existing
    if t == "number_card":
        return f"#card/{m.get('number_card_name')}" if m.get("number_card_name") else existing
    if t == "dashboard":
        if m.get("dashboard_name"):
            return f"/app/dashboard-view/{m.get('dashboard_name')}"
        return existing or "#dashboard"
    if t == "webpage":
        route = m.get("webpage_route")
        if route:
            return route if route.startswith(("/", "http")) else "/" + route
        return existing
    if t == "url":
        return m.get("external_url") or existing
    if t == "custom_html":
        return existing or f"#html/{m.module_name}"
    # frappe_page, iframe_url, custom_view, or anything else → preserve
    return existing
