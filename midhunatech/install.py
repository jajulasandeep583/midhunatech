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
    """Runs before bench migrate — safe to leave empty."""
    pass
