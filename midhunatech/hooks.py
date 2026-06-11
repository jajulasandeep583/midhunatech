# Copyright (c) 2024, Midhunatech and Contributors
# License: GPL-3.0 — see LICENSE for details

app_name        = "midhunatech"
app_title       = "Midhunatech"
app_publisher   = "Midhunatech"
app_description = "Midhunatech — Configurable Progressive Web App on Frappe v16"
app_email       = "admin@midhunatech.com"
app_license     = "GNU General Public License (v3)"
app_version     = "1.0.0"

source_link  = "https://github.com/midhunatech/midhunatech"
app_logo_url = "/assets/midhunatech/images/logo.svg"

# Only frappe is required — no ERPNext dependency (pure Frappe app)
required_apps = ["frappe"]

# ── v16: app home + apps-screen entry ─────────────────────────────────────────
# app_home tells Frappe where to send users when they click the app icon
app_home = "/midhunatech"

# add_to_apps_screen adds a tile on the Frappe v16 apps launcher grid
add_to_apps_screen = [
    {
        "name":           "midhunatech",
        "logo":           "/assets/midhunatech/images/logo.svg",
        "title":          "Midhunatech",
        "route":          "/midhunatech",
        "has_permission": "midhunatech.api.pwa.check_app_permission",
    }
]

# ── Website ────────────────────────────────────────────────────────────────────
# This is THE key hook:
#   www/midhunatech.html → yoursite.com/midhunatech  (Frappe serves it automatically)
#   The rule below makes ALL sub-paths like /midhunatech/home, /midhunatech/profile
#   also render from the same www/midhunatech.html — Vue Router handles sub-routing
website_route_rules = [
    {"from_route": "/midhunatech/<path:app_path>", "to_route": "midhunatech"},
]

# ── Boot injection (v16 pattern) ───────────────────────────────────────────────
# Injects mt_config into window.frappe.boot on every desk page load
extend_bootinfo = "midhunatech.api.pwa.extend_boot"

# ── Installation hooks ─────────────────────────────────────────────────────────
after_install  = "midhunatech.install.after_install"
before_migrate = "midhunatech.install.before_migrate"
after_migrate  = "midhunatech.install.after_migrate"

# ── Push notifications (Web Push) ─────────────────────────────────────────────
# New Workflow Action → push "Approval required" to everyone who can act;
# new Notification Log → mirror Frappe's in-app notification as a push.
doc_events = {
    "Workflow Action": {
        "after_insert": "midhunatech.api.push.notify_workflow_action",
    },
    "Notification Log": {
        "after_insert": "midhunatech.api.push.notify_notification_log",
    },
}

# ── Jinja ─────────────────────────────────────────────────────────────────────
jinja = {
    "methods": [
        "midhunatech.api.pwa.get_pwa_boot_context",
    ]
}
