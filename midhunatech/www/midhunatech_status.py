# Copyright (c) 2026, Midhunatech and Contributors
# License: GPL-3.0
"""
/midhunatech_status — self-service diagnostics page (System Manager only).

Works even when the PWA frontend itself cannot load (it is plain
server-rendered HTML, no JS bundle), so it is THE tool for "the app is
not working on this site": versions, doctor checks and live feature
tests with the real error messages.
"""

import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/midhunatech_status"
        raise frappe.Redirect
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Managers can view this page", frappe.PermissionError)

    from midhunatech.install import app_version_info, collect_doctor, run_feature_tests

    context.versions = app_version_info()
    context.doctor = collect_doctor()
    context.features = run_feature_tests()
    context.doctor_failed = sum(1 for _, ok, _ in context.doctor if not ok)
    context.features_failed = sum(1 for _, ok, _ in context.features if not ok)
    context.no_breadcrumbs = 1
    return context
