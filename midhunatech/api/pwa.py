# Copyright (c) 2024, Midhunatech and Contributors
# License: GPL-3.0

import frappe
from frappe import _
from frappe.utils.password import check_password, update_password as _update_password


# ── Boot injection ─────────────────────────────────────────────────────────────

def extend_boot(bootinfo):
    """
    Called by Frappe v16 extend_bootinfo hook on every authenticated page load.
    Injects minimal PWA config into window.frappe.boot so the desk knows
    the app exists. The full config is fetched lazily by the PWA frontend.
    """
    if frappe.session.user == "Guest":
        return
    try:
        cfg = frappe.get_cached_doc("Midhunatech PWA Config")
        bootinfo.mt_config = {
            "app_name":      cfg.app_name      or "Midhunatech",
            "theme_color":   cfg.theme_color   or "#6366f1",
            "primary_color": cfg.primary_color or "#6366f1",
        }
    except Exception:
        bootinfo.mt_config = {
            "app_name": "Midhunatech",
            "theme_color": "#6366f1",
            "primary_color": "#6366f1",
        }


def get_pwa_boot_context():
    """
    Jinja method — called from www/midhunatech.html template.
    Returns a dict that gets injected as window.__MT__ in the HTML.
    """
    out = {
        "csrf":          frappe.session.data.csrf_token if frappe.session.user != "Guest" else "",
        "user":          frappe.session.user,
        "fullname":      frappe.utils.get_fullname(frappe.session.user) if frappe.session.user != "Guest" else "",
        "app_name":      "Midhunatech",
        "theme_color":   "#6366f1",
        "primary_color": "#6366f1",
        "site_name":     frappe.local.site,
    }
    if frappe.session.user != "Guest":
        try:
            cfg = frappe.get_cached_doc("Midhunatech PWA Config")
            out["app_name"]      = cfg.app_name      or "Midhunatech"
            out["theme_color"]   = cfg.theme_color   or "#6366f1"
            out["primary_color"] = cfg.primary_color or "#6366f1"
        except Exception:
            pass
    return out


# ── App-screen permission check ────────────────────────────────────────────────

def check_app_permission():
    """
    Called by add_to_apps_screen has_permission hook.
    Returns True for any logged-in user.
    """
    if frappe.session.user == "Guest":
        return False
    return True


# ── Whitelisted API methods ────────────────────────────────────────────────────

def _build_version():
    """mtime of the built bundle — clients compare this against the version
    they booted with and reload themselves when it changes."""
    import os

    try:
        return int(os.path.getmtime(frappe.get_app_path("midhunatech", "public", "frontend", "index.js")))
    except Exception:
        return 1


@frappe.whitelist()
def get_config():
    """
    Returns the full PWA configuration: branding + ordered enabled modules.
    Called by the Vue frontend once per session after login.
    Requires authentication (no allow_guest).
    """
    cfg     = frappe.get_cached_doc("Midhunatech PWA Config")
    user    = frappe.get_cached_doc("User", frappe.session.user)
    roles   = [r.role for r in user.get("roles", [])]

    modules = []
    for row in cfg.get("modules", []):
        if not row.is_enabled:
            continue
        url = row.target_url or ""
        # resolve the doctype for list-type tiles regardless of which field
        # the admin filled (DocType field, legacy target_url, "#list/..." rows)
        doctype = row.get("doctype_name") or ""
        if not doctype:
            if url.startswith("#list/"):
                doctype = url[6:]
            elif row.module_type == "doc_list":
                doctype = url
        modules.append({
            "name":   row.module_name,
            "label":  row.label,
            "icon":   row.icon   or "grid",
            "color":  row.color  or "#6366f1",
            "route":  row.get("route_path"),
            "type":   row.module_type,        # frappe_page | iframe_url | custom_view | doc_list | dashboard | report
            "url":    url,
            "order":  int(row.display_order or 0),
            "doctype": doctype,
            "fields":  row.get("doctype_fields"),
            "filters": row.get("doctype_filters"),
            "report": row.get("report_name"),
            "report_filters": row.get("report_filters"),
            "badge_method": row.get("badge_count_method"),
            "nav":        int(row.get("show_in_bottom_nav") or 0),
            "nav_icon":   row.get("bottom_nav_icon"),
            "nav_label":  row.get("bottom_nav_label"),
            "nav_order":  int(row.get("bottom_nav_order") or 0),
        })

    modules.sort(key=lambda x: x["order"])

    # missing/never-saved value counts as ON so older sites keep the feature
    show_attendance = cfg.get("show_attendance")
    show_attendance = 1 if show_attendance is None else int(show_attendance)

    return {
        "app_name":      cfg.app_name      or "Midhunatech",
        "theme_color":   cfg.theme_color   or "#6366f1",
        "primary_color": cfg.primary_color or "#6366f1",
        "show_attendance": show_attendance,
        "build_v":       _build_version(),
        "modules":       modules,
        "user":          frappe.session.user,
        "fullname":      user.full_name or frappe.session.user,
        "email":         user.email or "",
        "user_image":    user.user_image or "",
        "roles":         roles,
        "is_system_manager": "System Manager" in roles or "Administrator" in roles,
    }


@frappe.whitelist(allow_guest=True)
def get_public_config():
    """
    Returns minimal branding used on the Login screen.
    No authentication required — called before the user logs in.
    """
    try:
        cfg = frappe.get_cached_doc("Midhunatech PWA Config")
        return {
            "app_name":    cfg.app_name    or "Midhunatech",
            "theme_color": cfg.theme_color or "#6366f1",
        }
    except Exception:
        return {"app_name": "Midhunatech", "theme_color": "#6366f1"}


@frappe.whitelist()
def get_notifications():
    """Returns unread notification count for badge display."""
    count = frappe.db.count(
        "Notification Log",
        filters={"for_user": frappe.session.user, "read": 0},
    )
    return {"unread": int(count or 0)}


@frappe.whitelist()
def change_password(old_password, new_password):
    """Change the logged-in user's own password after verifying the current one."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("You must be logged in to change your password."))

    if not new_password or len(new_password) < 6:
        frappe.throw(_("New password must be at least 6 characters."))

    try:
        check_password(user, old_password)
    except frappe.AuthenticationError:
        frappe.throw(_("Your current password is incorrect."))

    from frappe.core.doctype.user.user import test_password_strength

    user_doc = frappe.get_doc("User", user)
    result = test_password_strength(
        new_password,
        user_data=[user_doc.first_name, user_doc.last_name, user_doc.email],
    )
    feedback = (result or {}).get("feedback") or {}
    if feedback.get("password_policy_validation_passed") is False:
        suggestions = " ".join(feedback.get("suggestions") or [])
        frappe.throw(_("Password is too weak. {0}").format(suggestions or ""))

    _update_password(user, new_password)
    frappe.db.commit()
    return {"ok": True}
