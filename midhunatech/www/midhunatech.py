# Copyright (c) 2024, Midhunatech and Contributors
# License: GPL-3.0

import frappe

# module-level no_cache = 1 is the v16 pattern (same as HRMS)
# prevents Frappe from caching this page's rendered HTML
no_cache = 1


def get_context(context):
    """
    This file sits at midhunatech/www/midhunatech.py
    Frappe automatically maps it to the URL: yoursite.com/midhunatech
    Same mechanism as HRMS: hrms/www/hrms.py → yoursite.com/hrms

    Guests are redirected to login.
    Authenticated users get the Vue SPA booted with injected window.__MT__ data.
    """
    # v16 redirect pattern — same as frappe/crm, frappe/helpdesk etc.
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            f"/login?redirect-to=/midhunatech"
        )
        raise frappe.Redirect

    # Get PWA config to inject into window.__MT__
    try:
        cfg = frappe.get_cached_doc("Midhunatech PWA Config")
        context.pwa_app_name      = cfg.app_name      or "Midhunatech"
        context.pwa_theme_color   = cfg.theme_color   or "#6366f1"
        context.pwa_primary_color = cfg.primary_color or "#6366f1"
    except Exception:
        context.pwa_app_name      = "Midhunatech"
        context.pwa_theme_color   = "#6366f1"
        context.pwa_primary_color = "#6366f1"

    context.csrf_token    = frappe.session.data.csrf_token
    context.session_user  = frappe.session.user
    context.session_fname = frappe.utils.get_fullname(frappe.session.user)
    context.site_name     = frappe.local.site
