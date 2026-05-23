# Copyright (c) 2024, Midhunatech and Contributors
# License: GPL-3.0

import frappe


def after_install():
    """Runs after bench --site mysite install-app midhunatech"""
    # Seed the Single DocType with default values if not already set
    try:
        cfg = frappe.get_single("Midhunatech PWA Config")
        if not cfg.app_name:
            cfg.app_name      = "Midhunatech"
            cfg.theme_color   = "#6366f1"
            cfg.primary_color = "#6366f1"
            cfg.save(ignore_permissions=True)
            frappe.db.commit()
    except Exception:
        pass

    frappe.msgprint(
        "Midhunatech PWA installed successfully. "
        "Visit /app/midhunatech-pwa-config to configure your PWA modules.",
        title="Midhunatech PWA Ready",
        indicator="green",
    )


def before_migrate():
    """Runs before bench migrate â€” safe to leave empty."""
    pass


def seed_demo_modules():
    cfg = frappe.get_single("Midhunatech PWA Config")
    cfg.app_name = "Midhunatech ERP"
    cfg.theme_color = "#6366f1"
    cfg.primary_color = "#6366f1"
    cfg.set("modules", [])

    rows = [
        ("Purchase Order",  "purchase_order",  "briefcase",    "#6366f1", "/purchase_order",  "frappe_page", "/app/purchase-order",    1),
        ("Sales Order",     "sales_order",     "dollar",       "#22c55e", "/sales_order",     "frappe_page", "/app/sales-order",       2),
        ("Stock Entry",     "stock_entry",     "box",          "#f59e0b", "/stock_entry",     "frappe_page", "/app/stock-entry",       3),
        ("Attendance",      "attendance",      "clock",        "#3b82f6", "/attendance",      "frappe_page", "/app/attendance",        4),
        ("Leave Request",   "leave_request",   "calendar",     "#ec4899", "/leave_request",   "frappe_page", "/app/leave-application", 5),
        ("Expense Claim",   "expense_claim",   "report",       "#8b5cf6", "/expense_claim",   "frappe_page", "/app/expense-claim",     6),
        ("My Tasks",        "my_tasks",        "check-circle", "#10b981", "/my_tasks",        "frappe_page", "/app/task",              7),
        ("Team",            "team",            "users",        "#f97316", "/team",            "frappe_page", "/app/employee",          8),
    ]
    for label, key, icon, color, route, mtype, url, order in rows:
        row = cfg.append("modules", {})
        row.label        = label
        row.module_name  = key
        row.icon         = icon
        row.color        = color
        row.route_path   = route
        row.module_type  = mtype
        row.target_url   = url
        row.display_order = order
        row.is_enabled   = 1

    cfg.save(ignore_permissions=True)
    frappe.db.commit()
    print("Demo modules seeded OK")