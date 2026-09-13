# Copyright (c) 2024, Midhunatech and Contributors
# License: GPL-3.0

import os

import frappe

# module-level no_cache = 1 is the v16 pattern (same as HRMS)
# prevents Frappe from caching this page's rendered HTML
no_cache = 1


def _build_version():
    """mtime of the built bundle — busts the browser HTTP cache on every
    yarn build, so users always get the latest app without a hard refresh."""
    try:
        path = frappe.get_app_path("midhunatech", "public", "frontend", "index.js")
        return int(os.path.getmtime(path))
    except Exception:
        return 1


def get_context(context):
    """
    This file sits at midhunatech/www/midhunatech.py
    Frappe automatically maps it to the URL: yoursite.com/midhunatech
    Same mechanism as HRMS: hrms/www/hrms.py → yoursite.com/hrms

    The SPA shell is served to EVERYONE (including guests) so the PWA can
    render its own polished login screen. The Vue router guard sends
    unauthenticated users to /midhunatech/login, and login happens in-app
    via /api/method/login — no bounce to the Frappe desk login page.
    """
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

    context.csrf_token    = frappe.sessions.get_csrf_token()
    context.session_user  = frappe.session.user
    context.session_fname = frappe.utils.get_fullname(frappe.session.user)
    context.site_name     = frappe.local.site
    context.build_v       = _build_version()

    _log_boot(context.build_v)


def _log_boot(build_v):
    """Record every app launch (build, browser, host) to
    logs/pwa-boot.log. Without this there is no way to tell which build a
    user's device is actually running — the single hardest thing to
    diagnose remotely."""
    try:
        import datetime

        req = frappe.local.request
        line = " | ".join([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            f"build={build_v}",
            f"user={frappe.session.user}",
            f"host={req.headers.get('Host', '?')}",
            f"ua={(req.headers.get('User-Agent') or '?')[:110]}",
        ])
        path = frappe.get_site_path("..", "..", "logs", "pwa-boot.log")
        with open(path, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass   # logging must never break the page
