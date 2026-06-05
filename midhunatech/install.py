# Copyright (c) 2024, Midhunatech and Contributors
# License: GPL-3.0

import frappe

# Native (doc_list) modules seeded on install.
# (label, module_name, icon, color, route, doctype)
# Only seeded if the target Doctype exists on the site (skips HRMS/ERPNext
# doctypes that aren't installed).
NATIVE_MODULES = [
    ("Sales Order",   "sales_order",   "dollar",       "#22c55e", "/sales_order",   "Sales Order"),
    ("Stock Entry",   "stock_entry",   "box",          "#f59e0b", "/stock_entry",   "Stock Entry"),
    ("Attendance",    "attendance",    "clock",        "#3b82f6", "/attendance",    "Attendance"),
    ("Leave Request", "leave_request", "calendar",     "#ec4899", "/leave_request", "Leave Application"),
    ("Expense Claim", "expense_claim", "report",       "#8b5cf6", "/expense_claim", "Expense Claim"),
    ("My Tasks",      "my_tasks",      "check-circle", "#10b981", "/my_tasks",      "Task"),
    ("Team",          "team",          "users",        "#f97316", "/team",          "Employee"),
]


def after_install():
    """Runs after `bench --site <site> install-app midhunatech`.
    Auto-configures the PWA so a fresh site is usable immediately."""
    try:
        seed_default_modules()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "midhunatech: seed_default_modules failed")

    try:
        from midhunatech.setup.web_pages import create_pages
        create_pages()  # creates About/Notices web pages + links them as modules
    except Exception:
        frappe.log_error(frappe.get_traceback(), "midhunatech: create_pages failed")

    frappe.msgprint(
        "Midhunatech PWA installed and configured. Open /midhunatech on your phone, "
        "or manage tiles at /app/midhunatech-pwa-config.",
        title="Midhunatech PWA Ready",
        indicator="green",
    )


def before_migrate():
    """Runs before bench migrate — safe to leave empty."""
    pass


def after_migrate():
    """Runs after every `bench migrate` (i.e. after each app update on a site).
    Converges the default tiles to the native UI so a site updating from an older
    version stops opening the ERPNext desk and matches the latest app."""
    try:
        ensure_native_modules()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "midhunatech: ensure_native_modules failed")


def ensure_native_modules():
    """Convert the DEFAULT tiles from the legacy frappe_page (desk iframe) type to
    native doc_list. Scoped to known module keys only — custom/user tiles (e.g. a
    SCADA web page) are left untouched. Idempotent."""
    keymap = {m[1]: m[5] for m in NATIVE_MODULES}   # module_name -> doctype
    cfg = frappe.get_single("Midhunatech PWA Config")
    changed = 0
    for row in cfg.get("modules", []):
        doctype = keymap.get(row.module_name)
        if not doctype or row.module_type == "doc_list":
            continue
        if not frappe.db.exists("DocType", doctype):
            continue
        row.module_type = "doc_list"
        row.target_url = doctype
        changed += 1
    if changed:
        cfg.save(ignore_permissions=True)
        frappe.db.commit()
    print(f"ensure_native_modules: converted {changed} legacy tile(s) to native")
    return changed


def seed_default_modules():
    """Idempotently add the default native modules to the PWA Config.
    Safe to re-run (e.g. after installing ERPNext/HRMS later):
        bench --site <site> execute midhunatech.install.seed_default_modules
    """
    cfg = frappe.get_single("Midhunatech PWA Config")
    if not cfg.app_name:
        cfg.app_name      = "Midhunatech ERP"
        cfg.theme_color   = "#6366f1"
        cfg.primary_color = "#6366f1"

    existing = {r.module_name for r in cfg.get("modules", [])}
    order = max([int(r.display_order or 0) for r in cfg.get("modules", [])] or [0])

    added = []
    for label, key, icon, color, route, doctype in NATIVE_MODULES:
        if key in existing:
            continue
        if not frappe.db.exists("DocType", doctype):
            continue  # ERPNext/HRMS not installed — skip this tile
        order += 1
        cfg.append("modules", {
            "label":         label,
            "module_name":   key,
            "icon":          icon,
            "color":         color,
            "route_path":    route,
            "module_type":   "doc_list",
            "target_url":    doctype,
            "display_order": order,
            "is_enabled":    1,
        })
        added.append(label)

    cfg.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"Seeded {len(added)} native module(s): {', '.join(added) or '(no new — already configured or doctypes not installed)'}")
    return added


# Backwards-compatible alias
def seed_demo_modules():
    return seed_default_modules()
