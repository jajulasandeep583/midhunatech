# Copyright (c) 2026, Midhunatech and Contributors
# License: GPL-3.0
"""
In-app PWA configuration editor (System Manager only).

Lets the owner manage branding, bottom-nav tabs and the home-grid tiles
from inside the PWA itself — no desk, no code.
"""

import json

import frappe
from frappe import _

CONFIG_FIELDS = [
    "app_name", "theme_color", "primary_color", "secondary_color",
    "accent_color", "bottom_nav_enabled",
]

MODULE_FIELDS = [
    "label", "module_name", "icon", "color", "gradient_from", "gradient_to",
    "module_type", "display_order", "is_enabled",
    "doctype_name", "report_name", "report_filters", "dashboard_name",
    "webpage_route", "external_url", "target_url", "badge_count_method",
    "show_in_bottom_nav", "bottom_nav_icon", "bottom_nav_label", "bottom_nav_order",
]


def _require_admin():
    if frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
        frappe.throw(_("Not permitted"), frappe.PermissionError)


@frappe.whitelist()
def get_admin_config():
    _require_admin()
    cfg = frappe.get_doc("Midhunatech PWA Config")
    return {
        "config": {f: cfg.get(f) for f in CONFIG_FIELDS},
        "modules": [{f: row.get(f) for f in MODULE_FIELDS} for row in cfg.get("modules", [])],
        "module_types": [
            "iframe_url", "doc_list", "report", "dashboard", "custom_view", "url", "frappe_page",
        ],
    }


@frappe.whitelist()
def save_admin_config(config=None, modules=None):
    _require_admin()
    if isinstance(config, str):
        config = json.loads(config or "{}")
    if isinstance(modules, str):
        modules = json.loads(modules or "null")

    cfg = frappe.get_doc("Midhunatech PWA Config")
    for f, v in (config or {}).items():
        if f in CONFIG_FIELDS:
            cfg.set(f, v)

    if modules is not None:
        cfg.set("modules", [])
        for order, m in enumerate(modules, start=1):
            row = {f: m.get(f) for f in MODULE_FIELDS if f in m}
            row.setdefault("display_order", order)
            if not row.get("module_name"):
                row["module_name"] = frappe.scrub(row.get("label") or f"module_{order}")
            cfg.append("modules", row)

    cfg.save(ignore_permissions=True)
    return {"ok": True}
