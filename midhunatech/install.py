# Copyright (c) 2024, Midhunatech and Contributors
# License: GPL-3.0

import frappe

# Native (doc_list) modules seeded on install.
# (label, module_name, icon, color, route, doctype)
# Only seeded if the target Doctype exists on the site (skips HRMS/ERPNext
# doctypes that aren't installed).
NATIVE_MODULES = [
    ("Sales Order",      "sales_order",      "dollar",       "#22c55e", "/sales_order",      "Sales Order"),
    ("Stock Entry",      "stock_entry",      "box",          "#f59e0b", "/stock_entry",      "Stock Entry"),
    ("Material Request", "material_request", "box",          "#0ea5e9", "/material_request", "Material Request"),
    ("Attendance",       "attendance",       "clock",        "#3b82f6", "/attendance",       "Attendance"),
    ("Leave Request",    "leave_request",    "calendar",     "#ec4899", "/leave_request",    "Leave Application"),
    ("Expense Claim",    "expense_claim",    "report",       "#8b5cf6", "/expense_claim",    "Expense Claim"),
    ("My Tasks",         "my_tasks",         "check-circle", "#10b981", "/my_tasks",         "Task"),
    ("Team",             "team",             "users",        "#f97316", "/team",             "Employee"),
]

# Report tiles seeded on install — only if the Report exists (i.e. ERPNext
# is installed). They get the mobile KPI cards / chart / filter bar for free.
# (label, module_name, icon, report_name)
REPORT_MODULES = [
    ("Balance Sheet",  "balance_sheet",   "📊", "Balance Sheet"),
    ("Profit & Loss",  "pl_statement",    "📈", "Profit and Loss Statement"),
    ("Trial Balance",  "trial_balance",   "⚖️", "Trial Balance"),
    ("General Ledger", "general_ledger",  "📒", "General Ledger"),
    ("Stock Balance",  "stock_balance",   "📦", "Stock Balance"),
]


def after_install():
    """Runs after `bench --site <site> install-app midhunatech`.
    Auto-configures the PWA so a fresh site is usable immediately."""
    try:
        seed_number_cards()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "midhunatech: seed_number_cards failed")

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

    # KPI dashboard tile — first on the grid. Targets the seeded MT cards by
    # default (clean business KPIs); set target_url blank to show ALL cards,
    # or to a Dashboard name / comma-separated Number Card names.
    if "dashboard" not in existing:
        cfg.append("modules", {
            "label":         "Dashboard",
            "module_name":   "dashboard",
            "icon":          "chart",
            "color":         "#6366f1",
            "route_path":    "/dashboard",
            "module_type":   "dashboard",
            "target_url":    ",".join(c[0] for c in DEFAULT_CARDS),
            "display_order": 0,
            "is_enabled":    1,
        })
        added.append("Dashboard")

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

    # Approvals (generic — works with whatever Workflows the site activates)
    if "approvals" not in existing:
        order += 1
        cfg.append("modules", {
            "label":         "Approvals",
            "module_name":   "approvals",
            "icon":          "✅",
            "color":         "#16a34a",
            "route_path":    "/approvals",
            "module_type":   "custom_view",
            "display_order": order,
            "is_enabled":    1,
        })
        added.append("Approvals")

    # Financial / stock report tiles (need ERPNext)
    for label, key, icon, report in REPORT_MODULES:
        if key in existing:
            continue
        if not frappe.db.exists("Report", report):
            continue
        order += 1
        cfg.append("modules", {
            "label":         label,
            "module_name":   key,
            "icon":          icon,
            "route_path":    f"/{key}",
            "module_type":   "report",
            "report_name":   report,
            "target_url":    f"/app/query-report/{report}",
            "display_order": order,
            "is_enabled":    1,
        })
        added.append(label)

    cfg.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"Seeded {len(added)} native module(s): {', '.join(added) or '(no new — already configured or doctypes not installed)'}")
    return added


# Default KPI cards (Count) seeded on install — guarded by doctype existence.
# (label, document_type, color)
DEFAULT_CARDS = [
    ("MT Total Sales Orders", "Sales Order", "#6366f1"),
    ("MT Employees",          "Employee",    "#f97316"),
    ("MT Open Tasks",         "Task",        "#10b981"),
    ("MT Stock Entries",      "Stock Entry", "#f59e0b"),
]


def seed_number_cards():
    """Create a few default Frappe Number Cards so the Dashboard tile is useful
    out of the box. Idempotent; only for doctypes that exist."""
    if not frappe.db.exists("DocType", "Number Card"):
        return []
    made = []
    for label, doctype, color in DEFAULT_CARDS:
        if not frappe.db.exists("DocType", doctype):
            continue
        if frappe.db.exists("Number Card", {"label": label}):
            continue
        try:
            frappe.get_doc({
                "doctype":       "Number Card",
                "label":         label,
                "type":          "Document Type",
                "document_type": doctype,
                "function":      "Count",
                "filters_json":  "[]",
                "color":         color,
                "is_public":     1,
                "show_percentage_stats": 0,
            }).insert(ignore_permissions=True)
            made.append(label)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "midhunatech: number card seed")
    if made:
        frappe.db.commit()
    print(f"Seeded {len(made)} number card(s): {', '.join(made) or '(none)'}")
    return made


# Backwards-compatible alias
def seed_demo_modules():
    return seed_default_modules()


def doctor():
    """Production health check. Run on any site:
        bench --site <site> execute midhunatech.install.doctor
    Prints PASS/FAIL per check with the exact fix for each failure."""
    import os

    okc, fail = [], []

    def check(label, cond, fix=""):
        (okc if cond else fail).append((label, fix))
        print(("  [OK]   " if cond else "  [FAIL] ") + label + ("" if cond else f"\n         FIX: {fix}"))

    print(f"midhunatech doctor — site: {frappe.local.site}\n")

    # 1. built frontend exists inside the app
    app_index = frappe.get_app_path("midhunatech", "public", "frontend", "index.js")
    check("Built frontend bundle exists (app)", os.path.exists(app_index),
          "git pull in apps/midhunatech (the build is committed); never delete public/frontend")

    # 2. assets are exposed under sites/assets (nginx serves THIS path in production)
    assets_index = os.path.join(frappe.utils.get_bench_path(), "sites", "assets",
                                "midhunatech", "frontend", "index.js")
    check("Assets linked under sites/assets (served by nginx)", os.path.exists(assets_index),
          "run: bench build --app midhunatech   (creates the assets symlink) then bench restart")

    # 3. app installed on this site
    installed = "midhunatech" in frappe.get_installed_apps()
    check("App installed on this site", installed,
          "bench --site {} install-app midhunatech".format(frappe.local.site))

    # 4. config + tiles sanity
    try:
        cfg = frappe.get_single("Midhunatech PWA Config")
        rows = cfg.get("modules", [])
        check("PWA Config has tiles", bool(rows),
              "bench --site {} execute midhunatech.install.seed_default_modules".format(frappe.local.site))
        enabled = [r for r in rows if r.is_enabled]
        check("At least one tile is Enabled", bool(enabled),
              "tick 'Enabled' on tiles in /app/midhunatech-pwa-config")
        for r in enabled:
            if r.module_type in ("doc_list", "doctype", "list_view"):
                dt = r.get("doctype_name") or (r.target_url or "").replace("#list/", "")
                check(f"Tile '{r.label}' has a DocType", bool(dt),
                      f"set the DocType field on tile '{r.label}'")
                if dt:
                    check(f"Tile '{r.label}' doctype exists: {dt}", bool(frappe.db.exists("DocType", dt)),
                          f"fix the DocType on tile '{r.label}' — '{dt}' is not on this site")
            if r.module_type == "report" and r.get("report_name"):
                check(f"Tile '{r.label}' report exists", bool(frappe.db.exists("Report", r.report_name)),
                      f"report '{r.report_name}' missing — is ERPNext installed?")
    except Exception as e:
        check("PWA Config readable", False, f"error: {e} — run bench --site <s> migrate")

    # 5. DB Script Reports need server scripts enabled in COMMON config
    has_db_script = bool(frappe.db.exists("Report", {"report_type": "Script Report", "is_standard": "No"}))
    if has_db_script:
        check("server_script_enabled for DB Script Reports",
              bool(frappe.get_common_site_config().get("server_script_enabled")),
              "add \"server_script_enabled\": 1 to sites/common_site_config.json + bench restart")

    # 6. background workers — push notifications are DELIVERED by RQ workers
    try:
        from frappe.utils.background_jobs import get_workers
        check("Background workers running (deliver push notifications)", bool(get_workers()),
              "production: sudo supervisorctl restart all / dev: make sure bench start includes workers")
    except Exception:
        pass
    try:
        from frappe.utils.scheduler import is_scheduler_disabled
        check("Scheduler enabled (daily jobs)", not is_scheduler_disabled(),
              "bench --site {} enable-scheduler".format(frappe.local.site))
    except Exception:
        pass

    # 7. pywebpush importable (push notifications)
    try:
        import pywebpush  # noqa: F401
        check("pywebpush installed", True)
    except Exception:
        check("pywebpush installed", False,
              "bench pip install pywebpush   (or: ./env/bin/pip install pywebpush) + bench restart")

    print(f"\n{len(okc)} passed, {len(fail)} failed.")
    if fail:
        print("Fix the FAIL lines above, then run the doctor again.")
    return {"passed": len(okc), "failed": len(fail)}
