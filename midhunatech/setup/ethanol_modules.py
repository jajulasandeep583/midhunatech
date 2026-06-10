# Copyright (c) 2026, Midhunatech and Contributors
# License: GPL-3.0
"""
Ethanol Industries plant PWA — seed the Midhunatech PWA Config with the
user's SCADA Web Pages so the app home grid is webpages-only.

Run with:
    bench --site ethanol execute midhunatech.setup.ethanol_modules.setup

Idempotent: replaces the module list with the tiles below (webpages only,
/san Plant Overview hub first). Auth (login / logout / change password)
is built into the PWA shell itself, so nothing else is needed.
"""

import frappe

APP_NAME = "Ethanol Industries"
THEME = {
    "theme_color": "#065f46",
    "primary_color": "#059669",
    "secondary_color": "#0f766e",
    "accent_color": "#34d399",
}

# (route, label, icon, gradient_from, gradient_to)
# NOTE: routes are used verbatim in target_url; "mojj-liquefaction%202d" is a
# literal route containing %20, so its URL needs the % escaped as %25.
PAGES = [
    ("san", "Plant Overview", "🏭", "#065f46", "#10b981"),
    ("recovery", "Recovery", "♻️", "#0f766e", "#2dd4bf"),
    ("fermentation-", "Fermentation (Lab)", "🧪", "#7c3aed", "#a78bfa"),
    ("fermentation-WITHOUTLAB", "Fermenters", "🫧", "#7c3aed", "#c4b5fd"),
    ("mojj", "Mojj SCADA", "🖥️", "#1d4ed8", "#60a5fa"),
    ("praj-scada", "Praj SCADA", "🖥️", "#1d4ed8", "#38bdf8"),
    ("milling", "Mojj Milling", "⚙️", "#b45309", "#f59e0b"),
    ("mojj-liquefaction", "Mojj Liquefaction 3D", "💧", "#0369a1", "#38bdf8"),
    ("mojj-liquefaction%25202d", "Mojj Liquefaction 2D", "💧", "#0369a1", "#7dd3fc"),
    ("mojj-fermentation", "Mojj Fermentation", "🧬", "#6d28d9", "#a78bfa"),
    ("mojj-distillation", "Mojj Distillation", "🏗️", "#9f1239", "#fb7185"),
    ("mojj-evaporation", "Mojj Evaporation", "♨️", "#c2410c", "#fb923c"),
    ("mojj-ethanol", "Mojj Ethanol Mode", "⛽", "#15803d", "#4ade80"),
    ("ethanol", "3D Mojj Ethanol", "⛽", "#15803d", "#86efac"),
    ("d-distillation", "3D Mojj Distillation", "🧊", "#9f1239", "#fda4af"),
    ("m-distillation", "3D Mojj Evaporation", "🧊", "#c2410c", "#fdba74"),
    ("clude-ai", "Distillation", "🌡️", "#be123c", "#f87171"),
    ("praj-scada-distillation", "Praj Distillation", "🏗️", "#9d174d", "#f472b6"),
    ("prajj-scada-evaporation", "Praj Evaporation", "♨️", "#ea580c", "#fdba74"),
    ("praj-scada-msdh", "Praj MSDH", "🌫️", "#475569", "#94a3b8"),
    ("d-msdh", "3D Praj MSDH", "🌫️", "#475569", "#cbd5e1"),
    ("d-evaporation", "3D Praj Evaporation", "♨️", "#ea580c", "#fed7aa"),
    ("page", "3D Praj Distillation", "🏗️", "#9d174d", "#fbcfe8"),
    ("dryer", "Dryer Section", "🔥", "#dc2626", "#f87171"),
    ("sand", "Main Warehouse", "📦", "#92400e", "#d97706"),
    ("quality", "Quality (Warehouse)", "✅", "#166534", "#4ade80"),
    ("weighbridge-dashboard", "Weighbridge", "⚖️", "#374151", "#9ca3af"),
    ("praj-scada-shift-reports", "Praj Shift Report", "📋", "#0e7490", "#22d3ee"),
    ("mojj-shift", "Mojj Shift Checking", "📋", "#0e7490", "#67e8f9"),
    ("mojj-shift-", "Mojj Shift", "📋", "#155e75", "#a5f3fc"),
    ("my-shifts", "My Shifts", "🗓️", "#4338ca", "#818cf8"),
    ("check-1", "Fermenter 1 (3D)", "🫙", "#5b21b6", "#a78bfa"),
    ("moj-dis-all-colms-3d", "Mojj Columns 3D", "🏗️", "#831843", "#f9a8d4"),
    ("mojj-distillation-visual", "Distillation Visual", "📊", "#1e40af", "#93c5fd"),
]


# Injected into every website page via Website Settings head_html. Hides the
# Frappe website navbar/footer ONLY when the page is rendered inside the PWA
# iframe, so the SCADA pages look native in the app but stay normal in a browser.
_IFRAME_CHROME_MARKER = "<!-- ethanol-pwa-iframe-chrome -->"
_IFRAME_CHROME = _IFRAME_CHROME_MARKER + """
<script>
(function () {
  if (window.self === window.top) return;
  var s = document.createElement("style");
  s.textContent =
    ".navbar, .web-footer, footer, .footer, .navbar-fixed-top," +
    ".page-head, .breadcrumb-container, #navbar-collapse" +
    "{display:none !important}" +
    "body{padding-top:0 !important;margin-top:0 !important}" +
    ".main-section{padding-top:0 !important}";
  document.head.appendChild(s);
})();
</script>
"""


def _inject_iframe_chrome():
    ws = frappe.get_doc("Website Settings")
    head = ws.head_html or ""
    if _IFRAME_CHROME_MARKER in head:
        return
    ws.head_html = head + "\n" + _IFRAME_CHROME
    ws.save(ignore_permissions=True)
    print("Injected iframe chrome-hider into Website Settings head_html.")


def setup():
    """Rebrand the PWA and replace the home grid with the plant web pages."""
    _inject_iframe_chrome()
    cfg = frappe.get_doc("Midhunatech PWA Config")
    cfg.app_name = APP_NAME
    # webpages-only app: no check-in card / Attendance tab
    if hasattr(cfg, "show_attendance"):
        cfg.show_attendance = 0
    for field, value in THEME.items():
        if hasattr(cfg, field):
            cfg.set(field, value)

    cfg.set("modules", [])
    for order, (route, label, icon, gfrom, gto) in enumerate(PAGES, start=1):
        cfg.append("modules", {
            "module_name": route.replace("-", "_").replace("%", "_").lower(),
            "label": label,
            "icon": icon,
            "color": gfrom,
            "gradient_from": gfrom,
            "gradient_to": gto,
            "module_type": "iframe_url",
            "target_url": f"/{route}",
            "display_order": order,
            "is_enabled": 1,
        })

    cfg.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"PWA configured: app_name='{APP_NAME}', {len(PAGES)} webpage tiles.")
