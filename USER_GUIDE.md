# Midhunatech PWA — User Guide

> **Maintenance rule:** this guide is updated in the SAME commit as any feature
> change. If you change behavior, update the matching section here.
>
> Last updated: 2026-06-11 (commit: report filter bar + native Material Request creation + push notifications)

The Midhunatech PWA is a mobile app served by your Frappe/ERPNext site at
**`https://yoursite.com/midhunatech`**. Users never see the ERPNext desk —
everything (lists, approvals, reports, material requests, notifications) is
native mobile UI.

---

## 1. Installation (server)

```bash
cd ~/frappe-bench
bench get-app https://github.com/jajulasandeep583/midhunatech.git
bench --site yoursite.com install-app midhunatech
bench --site yoursite.com migrate
bench --site yoursite.com clear-cache
bench restart
```

- Built frontend is committed — **no Node/yarn needed on the server**.
- The installer auto-seeds a working home grid: Dashboard, Sales Order,
  Stock Entry, Material Request, Attendance, Leave, Expense Claim, Tasks,
  Team, **Approvals**, and report tiles (Balance Sheet, P&L, Trial Balance,
  General Ledger, Stock Balance). Tiles whose doctype/report is missing
  (no ERPNext/HRMS) are skipped automatically.
- Installed ERPNext later? Re-seed any newly possible tiles:
  `bench --site yoursite.com execute midhunatech.install.seed_default_modules`
- **HTTPS is required** for installing the app to the home screen and for
  push notifications (service workers need a secure origin).

### Install on the phone
Open `https://yoursite.com/midhunatech` in Chrome (Android) or Safari (iPhone)
→ browser menu → **Add to Home screen / Install app**. On iPhone, push
notifications only work after the app is added to the home screen.

---

## 2. App layout

| Area | What it is |
|---|---|
| **Home** | Tile grid (one tile per module) + check-in card (if enabled) + 🔔 notification bell with unread badge |
| **Bottom tabs** | Home, up to 3 pinned modules (configurable), Attendance (optional), Profile |
| **Profile** | User info, **push notification toggle**, change password, App Settings (admins), sign out |

---

## 3. Adding a tile (example: Sales Invoice)

Tiles are rows in the **"Midhunatech PWA Config"** single doctype. Two ways to
edit it:

**A. In the app (System Manager):** Profile → **⚙ App Settings** — branding,
tiles, and bottom-nav pins.

**B. On the desk (full control):** open `/app/midhunatech-pwa-config` and add
a row to the *Modules* table.

To add a **Sales Invoice** tile:

| Field | Value |
|---|---|
| Module Name | `sales_invoice` (unique key, lowercase) |
| Label | `Sales Invoice` |
| Module Type | `doc_list` |
| Doctype Name / Target URL | `Sales Invoice` |
| Icon | an emoji (🧾) or icon name |
| Enabled | ✓ |

Save → users pull-to-refresh or reopen the app. That's it — the tile opens a
native, searchable, paginated Sales Invoice list with number cards on top and
a read-only detail sheet on tap.

### All module types

| Module Type | What it shows | Key field to set |
|---|---|---|
| `doc_list` | Native list + detail (+ create form where supported) for ANY doctype | Doctype name in *Target URL / Doctype Name* |
| `report` | Any Frappe report: KPI summary cards + chart + filter bar + table | *Report Name* |
| `dashboard` | Grid of Frappe Number Cards (KPIs) | *Target URL* = Dashboard name, comma-separated card names, or blank for all |
| `iframe_url` | A web page inside the app (e.g. SCADA pages) | *Target URL* = `/your-page` |
| `custom_view` | A custom Vue screen shipped with the app (e.g. `approvals`) | Module Name must match the Vue file |
| `frappe_page` | Legacy: desk page in an iframe (avoid) | desk route |

### Pinning a tile to the bottom tab bar
On the module row set **Show in Bottom Nav** ✓ (+ optional nav icon/label/
order). Max 3 custom tabs are shown.

---

## 4. Which fields are displayed — and how to change them

The app reads everything from the doctype's **meta**, so you control display
with standard Frappe customization (**Customize Form**), no app changes:

| Where | What's shown | How to change |
|---|---|---|
| List card title | The doctype's **Title Field** (falls back to ID) | Customize Form → *Title Field* |
| List card badge | `status` or `workflow_state` | automatic |
| List card amount | First of `grand_total`, `total`, `net_total`, `amount`, … (Currency) | automatic |
| List card date | `transaction_date` / `posting_date` / `date` / … | automatic |
| List card extra lines (max 3) | Fields with **In List View** checked | Customize Form → check *In List View* |
| Detail sheet (tap a record) | Every permitted, non-empty field | hide a field → *Hidden* in Customize Form; permlevel-restricted fields are never shown |
| Create form (+ button) | Mandatory fields first, then In-List-View/Bold fields (max 12) | Customize Form: *Mandatory*, *In List View*, *Bold* |

Values are always formatted for reading: currency as `1,82,018.00`, dates as
`dd-mm-yyyy`, HTML (addresses, terms) flattened to plain text, and technical
fieldtypes (Code, JSON, attachments, signatures) hidden entirely.

### Approval preview fields (fixed, curated)
For transactional documents the approval screen shows ONLY the key facts:

- **PO / PI / SO / SI / DN / PR / Quotation:** party, dates, company,
  total qty, total, taxes, grand total, address, contact + **Items** and
  **Taxes** tables (item, qty, UOM, rate, amount)
- **Material Request:** type, dates, company, target warehouse + Items

To change these lists, edit `_KEY_FIELDS` in
`midhunatech/api/approvals.py` (one line per doctype). Doctypes not in the
map fall back to the full (cleaned) field list.

---

## 5. Approvals

Tile/tab **Approvals** lists every document waiting in a workflow state the
logged-in user's role can act on — across ALL active Workflows (PO, SO, SI,
MR, …). Activate/deactivate workflows on the desk (`/app/workflow`); the
screen adapts automatically.

- Tap a document → key fields + line items + a **pinned action bar**
  (✓ Approve green / ✕ Reject red) that never scrolls away.
- After acting, the list refreshes and a confirmation toast shows.
- Deep links: `/midhunatech/m/approvals?open=Sales Invoice|ACC-SINV-0001`
  opens that document directly — push notifications use this.

---

## 6. Reports

Open any `report` tile. The screen renders, top to bottom:

1. **Filter bar** — From/To dates (pre-filled with the fiscal year/company
   defaults) + report-specific filters:
   - **Stock Balance / Stock Ledger:** Item and Warehouse search boxes —
     type, pick a suggestion, the report re-runs for just that item/warehouse;
     ✕ clears the filter.
   - **General Ledger:** Party Type.
   - Add more in `_REPORT_FILTERS` (`midhunatech/api/reports.py`).
2. **KPI summary cards** — whatever the report publishes (e.g. Balance Sheet:
   Total Asset / Liability / Equity / Profit, shown as ₹ Cr/L).
3. **Chart** — the report's chart, rendered natively.
4. **Table** — sticky header + sticky first column, indented account trees,
   bold group rows, Indian number format, first 500 rows.

Mandatory filters (company, fiscal year, dates) are auto-filled server-side,
so standard financial reports run with zero setup. **DB Script Reports**
(custom reports stored in the database) additionally need
`"server_script_enabled": 1` in the bench's `common_site_config.json`.

---

## 7. Creating documents from the phone

Any `doc_list` tile shows a **＋** button when the user has Create permission
and the doctype is supported:

- **Simple doctypes** (Task, Attendance, Leave Application, Employee, ToDo…):
  a meta-driven form — mandatory fields, link fields with autocomplete.
- **Material Request** (line items supported): Purpose, Company (pre-filled),
  dates (pre-filled), then **item cards** — Item search, Quantity, Warehouse
  search, "＋ Add item" for more rows. UOM/conversions are filled
  automatically. On create, the MR enters its approval workflow and approvers
  get a push notification.
- Doctypes with required line items that aren't supported yet show a friendly
  "use the desk" note. To support another one, add it to `_CHILD_CREATE`
  in `midhunatech/api/data.py` (one small spec — see Material Request).

---

## 8. Push notifications

**User setup (once per device):** Profile → *Notifications* → toggle
**Push notifications** ON → accept the browser permission prompt. Done.

**What arrives:**
- *Approval required* — when a document enters a state the user's role can
  act on. Tapping opens the document's approval screen directly.
- Frappe notifications (mentions, assignments, alerts) — tapping opens the
  in-app notification feed.

**Admin facts:** no Firebase/external service — self-hosted Web Push (VAPID).
Keys are generated automatically per site (stored in `site_config.json`).
Subscriptions live in the *Midhunatech Push Subscription* doctype; expired
devices clean themselves up. Requires HTTPS. iPhone: app must be installed
to the home screen (iOS 16.4+).

---

## 9. Branding & app settings

Profile → **⚙ App Settings** (System Manager only), or the desk config:

- **App name** — header + install name
- **Theme / primary color** — applied app-wide
- **Show Attendance** — toggles the check-in card + Attendance tab
- **Tiles** — add / remove / reorder / enable / disable
- **Bottom nav** — pin up to 3 modules

---

## 10. Updating the app on a live site

```bash
cd ~/frappe-bench/apps/midhunatech && git pull
cd ~/frappe-bench
bench --site yoursite.com migrate
bench --site yoursite.com clear-cache
bench restart
```

Users get the new version automatically the next time they open the app
(the shell cache-busts on every build; an open tab self-reloads once when it
detects a newer build).

---

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| Old UI after an update | Just close and reopen the app (cache-busting is automatic); worst case `bench clear-cache` |
| Report says "Report failed" | Check the user has the report's role; DB Script Reports need `server_script_enabled` in **common** site config |
| Empty home grid on a fresh site | `bench --site <s> execute midhunatech.install.seed_default_modules` |
| Approvals tile empty | No active Workflow has a state the user's role can act on — check `/app/workflow` |
| Push toggle errors "not supported" | Needs HTTPS; on iPhone install to home screen first |
| Tile opens "Module not found" | Module Name in the config row doesn't match the URL slug |
