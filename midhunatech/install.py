# Copyright (c) 2024, Midhunatech and Contributors
# License: GPL-3.0

import frappe

# Native (doc_list) modules seeded on install.
# (label, module_name, icon, color, route, doctype)
# Only seeded if the target Doctype exists on the site (skips HRMS/ERPNext
# doctypes that aren't installed).
NATIVE_MODULES = [
    # ── masters ──
    ("Items",             "items",             "box",       "#f59e0b", "/items",             "Item"),
    ("Customers",         "customers",         "users",     "#0ea5e9", "/customers",         "Customer"),
    ("Suppliers",         "suppliers",         "🏭",        "#f97316", "/suppliers",         "Supplier"),
    # ── sales cycle ──
    ("Quotation",         "quotation",         "file",      "#6366f1", "/quotation",         "Quotation"),
    ("Sales Order",       "sales_order",       "clipboard", "#22c55e", "/sales_order",       "Sales Order"),
    ("Delivery Note",     "delivery_note",     "🚚",        "#06b6d4", "/delivery_note",     "Delivery Note"),
    ("Sales Invoice",     "sales_invoice",     "dollar",    "#10b981", "/sales_invoice",     "Sales Invoice"),
    # ── purchase cycle ──
    ("Material Request",  "material_request",  "📝",        "#a855f7", "/material_request",  "Material Request"),
    ("Purchase Order",    "purchase_order",    "📦",        "#7c3aed", "/purchase_order",    "Purchase Order"),
    ("Purchase Receipt",  "purchase_receipt",  "📥",        "#9333ea", "/purchase_receipt",  "Purchase Receipt"),
    ("Purchase Invoice",  "purchase_invoice",  "🧾",        "#8b5cf6", "/purchase_invoice",  "Purchase Invoice"),
    # ── stock ──
    ("Stock Entry",       "stock_entry",       "🔄",        "#eab308", "/stock_entry",       "Stock Entry"),
    ("Warehouses",        "warehouses",        "🏬",        "#d97706", "/warehouses",        "Warehouse"),
    # ── money ──
    ("Payments",          "payments",          "💳",        "#14b8a6", "/payments",          "Payment Entry"),
    ("Journal Entry",     "journal_entry",     "✍️",        "#64748b", "/journal_entry",     "Journal Entry"),
    ("Expense Claim",     "expense_claim",     "💸",        "#ec4899", "/expense_claim",     "Expense Claim"),
    ("Accounts",          "accounts",          "🏦",        "#0f766e", "/accounts",          "Account"),
]

# Report tiles seeded on install — only if the Report exists (i.e. ERPNext
# is installed). They get the mobile KPI cards / chart / filter bar for free.
# (label, module_name, icon, report_name)
REPORT_MODULES = [
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
        seed_default_notifications()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "midhunatech: seed_default_notifications failed")

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

    try:
        drop_checkin_doctype()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "midhunatech: drop_checkin_doctype failed")


def drop_checkin_doctype():
    """The check-in / attendance feature was removed from the app — erase its
    DocType and data from any site that still has them. Idempotent."""
    if frappe.db.exists("DocType", "Midhunatech Checkin"):
        frappe.delete_doc("DocType", "Midhunatech Checkin", force=True,
                          ignore_permissions=True, ignore_missing=True)
        frappe.db.sql_ddl("drop table if exists `tabMidhunatech Checkin`")
        frappe.db.commit()
        print("Dropped Midhunatech Checkin doctype + table")


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
    ("MT Quotations",        "Quotation",        "#6366f1"),
    ("MT Sales Orders",      "Sales Order",      "#22c55e"),
    ("MT Sales Invoices",    "Sales Invoice",    "#10b981"),
    ("MT Purchase Invoices", "Purchase Invoice", "#8b5cf6"),
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
    print(f"midhunatech doctor — site: {frappe.local.site}\n")
    results = collect_doctor()
    for label, ok, fix in results:
        print(("  [OK]   " if ok else "  [FAIL] ") + label + ("" if ok else f"\n         FIX: {fix}"))
    failed = sum(1 for _, ok, _ in results if not ok)
    print(f"\n{len(results) - failed} passed, {failed} failed.")
    if failed:
        print("Fix the FAIL lines above, then run the doctor again.")
    return {"passed": len(results) - failed, "failed": failed}


def collect_doctor():
    """The doctor's checks as data: [(label, ok, fix)] — reused by the
    /midhunatech_status page."""
    import os

    results = []

    def check(label, cond, fix=""):
        results.append((label, bool(cond), fix))

    # 1. built frontend exists inside the app
    app_index = frappe.get_app_path("midhunatech", "public", "frontend", "index.js")
    check("Built frontend bundle exists (app)", os.path.exists(app_index),
          "git pull in apps/midhunatech (the build is committed); never delete public/frontend")

    # 2. assets are exposed under sites/assets (nginx serves THIS path in production)
    assets_index = os.path.join(frappe.utils.get_bench_path(), "sites", "assets",
                                "midhunatech", "frontend", "index.js")
    check("Assets linked under sites/assets (served by nginx)", os.path.exists(assets_index),
          "run: bench build --app midhunatech   (creates the assets symlink) then bench restart")

    # 2b. the served bundle must be the SAME build as the app's (stale copies
    # happen when assets were copied instead of symlinked and never rebuilt)
    if os.path.exists(app_index) and os.path.exists(assets_index):
        same = (os.path.realpath(assets_index) == os.path.realpath(app_index)
                or (os.path.getsize(assets_index) == os.path.getsize(app_index)
                    and abs(os.path.getmtime(assets_index) - os.path.getmtime(app_index)) < 2))
        check("Served bundle matches the app's build (not stale)", same,
              "run: bench build --app midhunatech && bench --site {} clear-cache".format(frappe.local.site))

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

    return results


def app_version_info():
    """Versions + the exact app commit running on this site."""
    import os
    import subprocess

    info = {"site": frappe.local.site, "frappe": frappe.__version__}
    try:
        import erpnext
        info["erpnext"] = erpnext.__version__
    except Exception:
        info["erpnext"] = "not installed"
    try:
        app_dir = os.path.dirname(frappe.get_app_path("midhunatech"))
        out = subprocess.run(
            ["git", "-C", app_dir, "log", "-1", "--format=%h %cd %s", "--date=short"],
            capture_output=True, text=True, timeout=10,
        )
        info["midhunatech_commit"] = (out.stdout or out.stderr or "").strip()[:120] or "unknown"
    except Exception:
        info["midhunatech_commit"] = "unknown"
    return info


def run_feature_tests():
    """Exercise every backend feature the PWA uses (as Administrator) and
    return [(label, ok, detail)] — `detail` carries the REAL error message,
    so a broken real-site install explains itself."""
    results = []
    original_user = frappe.session.user
    frappe.set_user("Administrator")

    def test(label, fn):
        try:
            detail = fn() or "ok"
            results.append((label, True, str(detail)[:300]))
        except Exception as e:
            frappe.clear_messages()
            results.append((label, False, f"{type(e).__name__}: {str(e)[:300]}"))

    def t_config():
        from midhunatech.api.pwa import get_config
        c = get_config()
        bad = [m["name"] for m in c["modules"]
               if m["type"] in ("doc_list", "doctype", "list_view") and not m.get("doctype")]
        out = f"{len(c['modules'])} enabled tiles, build_v={c['build_v']}"
        if bad:
            out += f" — TILES WITHOUT DOCTYPE: {bad}"
        return out
    test("get_config (app boot)", t_config)

    try:
        cfg = frappe.get_single("Midhunatech PWA Config")
        rows = [r for r in cfg.get("modules", []) if r.is_enabled]
    except Exception:
        rows = []

    for row in rows:
        if row.module_type in ("doc_list", "doctype", "list_view"):
            dt = row.get("doctype_name") or (row.target_url or "").replace("#list/", "")
            def t_list(dt=dt, fields=row.get("doctype_fields"), filters=row.get("doctype_filters")):
                from midhunatech.api import data
                v = data.get_view(dt, fields=fields, filters=filters)
                lst = data.get_list(dt, page_length=3, fields=fields, filters=filters)
                return f"{dt}: {len(v['cards'])} cards, {len(lst['rows'])} sample rows"
            test(f"list tile '{row.label}'", t_list)
        elif row.module_type == "report" and row.get("report_name"):
            def t_report(r=row.report_name, f=row.get("report_filters")):
                from midhunatech.api import reports
                out = reports.run(r, f or {})
                return (f"cols={len(out['columns'])} rows={len(out['rows'])} "
                        f"kpis={len(out['summary'])} chart={'yes' if out['chart'] else 'no'}")
            test(f"report tile '{row.label}'", t_report)

    def t_approvals():
        from midhunatech.api import approvals
        return f"{len(approvals.get_pending())} pending document(s)"
    test("approvals", t_approvals)

    def t_notifications():
        from midhunatech.api import notifications
        return f"{notifications.get_feed()['unread']} unread"
    test("notification feed", t_notifications)

    def t_push():
        from midhunatech.api import push
        return f"VAPID key ready (len {len(push.get_vapid_public_key())})"
    test("push notifications (server side)", t_push)

    frappe.set_user(original_user)
    return results


def diagnose():
    """EVERYTHING in one shot — run this when 'nothing works' on a site:
        bench --site <site> execute midhunatech.install.diagnose
    Prints versions + doctor checks + live feature tests with real errors."""
    for k, v in app_version_info().items():
        print(f"{k}: {v}")
    print()
    doctor()
    print("\nFEATURE TESTS (server-side, as Administrator):")
    for label, ok, detail in run_feature_tests():
        print(("  [OK]   " if ok else "  [FAIL] ") + f"{label} — {detail}")


# ── Default notification rules ──────────────────────────────────────────────────
# Event-driven alerts seeded on install. Each has send_system_notification=1 so it
# lands in the PWA in-app feed + web push (see api/push.py). Guarded by doctype /
# field existence so HRMS/ERPNext-only rules are skipped on sites without them.
# (subject, doctype, event, value_changed, recipient_field, recipient_role, message)
DEFAULT_NOTIFICATIONS = [
    ("Sales Order Submitted", "Sales Order", "Submit", None, "owner", None,
     "Sales Order {{ doc.name }} for {{ doc.customer }} was submitted "
     "(Total: {{ doc.get_formatted('grand_total') }})."),
    ("Sales Order Pending Approval", "Sales Order", "Value Change", "workflow_state", "owner", None,
     "Sales Order {{ doc.name }} is now **{{ doc.workflow_state }}** and needs attention."),
    ("Material Request Submitted", "Material Request", "Submit", None, "owner", None,
     "Material Request {{ doc.name }} ({{ doc.material_request_type }}) was submitted."),
    ("Purchase Order Submitted", "Purchase Order", "Submit", None, "owner", None,
     "Purchase Order {{ doc.name }} for {{ doc.supplier }} was submitted."),
    ("Delivery Note Submitted", "Delivery Note", "Submit", None, "owner", None,
     "Delivery Note {{ doc.name }} for {{ doc.customer }} was submitted."),
    ("Leave Application Submitted", "Leave Application", "Submit", None, "leave_approver", None,
     "Leave Application {{ doc.name }} from {{ doc.employee_name }} awaits your approval."),
    ("Task Assigned To You", "Task", "Value Change", "status", None, None,
     "Task {{ doc.name }}: {{ doc.subject }} is now {{ doc.status }}."),
]


def seed_default_notifications():
    """Idempotently create the default Notification rules. Re-runnable:
        bench --site <site> execute midhunatech.install.seed_default_notifications
    Skips any whose DocType (or value_changed / recipient field) is missing."""
    if not frappe.db.exists("DocType", "Notification"):
        return []
    made = []
    for subject, doctype, event, value_changed, rfield, rrole, message in DEFAULT_NOTIFICATIONS:
        if not frappe.db.exists("DocType", doctype):
            continue
        if frappe.db.exists("Notification", {"subject": subject, "document_type": doctype}):
            continue
        meta = frappe.get_meta(doctype)
        if value_changed and not meta.get_field(value_changed):
            continue
        if rfield and rfield != "owner" and not meta.get_field(rfield):
            continue
        try:
            doc = frappe.new_doc("Notification")
            doc.subject = subject
            doc.document_type = doctype
            doc.event = event
            doc.channel = "System Notification"
            doc.send_system_notification = 1
            doc.is_standard = 0
            doc.enabled = 1
            doc.message_type = "Markdown"
            doc.message = message
            if value_changed:
                doc.value_changed = value_changed
            if rrole:
                doc.append("recipients", {"receiver_by_role": rrole})
            else:
                doc.append("recipients", {"receiver_by_document_field": rfield or "owner"})
            doc.insert(ignore_permissions=True)
            made.append(subject)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "midhunatech: seed_default_notifications")
    if made:
        frappe.db.commit()
    print(f"Seeded {len(made)} notification rule(s): {', '.join(made) or '(none new)'}")
    return made
