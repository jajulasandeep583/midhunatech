# Midhunatech PWA — User Guide

> **Maintenance rule:** this guide is updated in the SAME commit as any feature
> change. If you change behavior, update the matching section here.
>
> Last updated: 2026-06-11 (commit: caching service worker removed, ⟳ hard
> refresh button, works-on-any-site compatibility matrix)

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
bench build --app midhunatech        # links assets — REQUIRED on production (nginx)
bench --site yoursite.com clear-cache
bench restart
# verify everything:
bench --site yoursite.com execute midhunatech.install.doctor
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

To add a **Sales Invoice** tile, add a row in the *Modules* table and open it
(click the row → expand). Fill:

| Field | Value |
|---|---|
| Display Label | `Sales Invoice` |
| Module Key | `sales_invoice` (unique, lowercase, no spaces) |
| Module Type | `doc_list` |
| **DocType** (appears in the *Source* section after picking doc_list) | `Sales Invoice` |
| Icon | an emoji, e.g. 🧾 |
| Enabled | ✓ (it is ON by default — a tile with Enabled off never shows) |
| Fields (JSON array) — *optional* | `["customer", "posting_date", "grand_total", "status", "outstanding_amount"]` |
| Filters (JSON) — *optional* | `{"status": "Unpaid"}` |

*Target URL is computed automatically on save — leave it alone.*

**Save**, then in the app pull down on Home or reopen it. The tile opens a
native, searchable, paginated Sales Invoice list with number cards on top and
a tap-through detail sheet.

> Tile saved but not showing? It is almost always one of: **Enabled** unticked,
> or the app not refreshed. Run the doctor (section 12) — it checks every tile
> and tells you exactly what's wrong.

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

### Per-tile control (recommended)
On any list tile (`doc_list`) **or report tile** (`report`), set
**Fields (JSON array)** in the PWA Config row, e.g. for Sales Invoice:

```json
["customer", "posting_date", "grand_total", "status", "outstanding_amount"]
```

- The **detail sheet** then shows exactly these fields, in this order.
- The **list cards** show them too (the ones already used as the automatic
  title/badge/amount/date aren't repeated; up to 5 extra lines).
- Use the *fieldname* (lowercase with underscores), not the label — find it in
  Customize Form. Unknown or permission-restricted fieldnames are ignored
  safely.
- Leave it **blank for automatic mode**: the main fields (title, status,
  amount, date + *In List View* fields) are picked for you.

### Built-in defaults (blank Fields, common doctypes)
For the most common transactional doctypes a curated set of important fields
is built in, so tiles look right with zero configuration. Your Fields JSON
always overrides these.

| Doctype | Default fields |
|---|---|
| Sales Invoice | customer, posting_date, due_date, grand_total, outstanding_amount, status |
| Sales Order | customer, transaction_date, delivery_date, grand_total, status |
| Purchase Invoice | supplier, posting_date, due_date, grand_total, outstanding_amount, status |
| Purchase Order | supplier, transaction_date, schedule_date, grand_total, status |
| Purchase Receipt | supplier, posting_date, grand_total, status |
| Payment Entry | payment_type, party_type, party, posting_date, paid_amount, status |
| Journal Entry | voucher_type, posting_date, total_debit, user_remark |
| Material Request | material_request_type, transaction_date, schedule_date, status |

(Edit `_DEFAULT_FIELDS` in `midhunatech/api/data.py` to change the built-ins.)

Also available per tile — **Filters (JSON)**: e.g. `{"status": "Unpaid"}`
shows only unpaid invoices; the number cards on top respect the filter too.

### Site-wide control (automatic mode)
Without per-tile Fields, the app derives display from the doctype's meta via
standard **Customize Form** settings:

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
   - **Custom reports (Script / Query, made in the desk):** their own
     filters are read automatically — from the Report's *Filters* table, or
     parsed straight out of the report's **JavaScript** `filters: [...]`
     definition. Link filters become search boxes, Selects dropdowns, Dates
     date pickers; the report's own `default:` values (today, month start,
     user's company, …) are applied. If a mandatory filter still fails, the
     error shows **with the filter bar still on screen** so it can be fixed.
   - Add more standard-report filters in `_REPORT_FILTERS`
     (`midhunatech/api/reports.py`).
2. **KPI summary cards** — whatever the report publishes (e.g. Balance Sheet:
   Total Asset / Liability / Equity / Profit, shown as ₹ Cr/L).
3. **Chart** — the report's chart, rendered natively.
4. **Table** — sticky header + sticky first column, indented account trees,
   bold group rows, zebra striping, Indian number format, first 500 rows.

### Choosing which report columns show (any report type)
Works for **every** kind of report — standard (Stock Balance, GL…), Script
Reports, Query Reports and Report Builder reports. On the report tile's row
in PWA Config, set **Fields (JSON array)** to the columns you want, in order:

```json
["item_code", "warehouse", "bal_qty"]
```

- Match by column **fieldname or label** (case doesn't matter) —
  `"Warehouse"` and `"warehouse"` both work.
- Unknown names are dropped safely; if nothing matches (or the JSON is
  invalid) the report falls back to **all** columns — a typo can never blank
  a report.
- Blank = built-in defaults for common reports, all columns otherwise:

| Report | Default columns |
|---|---|
| Stock Balance | item_code, warehouse, bal_qty, bal_val |
| Stock Ledger | date, item_code, warehouse, actual_qty, qty_after_transaction |
| General Ledger | posting_date, account, debit, credit, balance, voucher_no |
| Trial Balance | account, debit, credit, closing_debit, closing_credit |
| Accounts Receivable / Payable | posting_date, party, voucher_no, invoiced, paid, outstanding |

(Edit `_DEFAULT_REPORT_COLUMNS` in `midhunatech/api/reports.py` to change.)

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

### Your own user-based notifications (HRMS-style)
Configure them exactly like email notifications — same **Notification**
doctype, different channel:

1. Desk → **Notification** → New.
2. *Document Type* + *Send Alert On* (New / Save / Submit / Value Change /
   Days Before-After a date, with an optional *Condition*).
3. **Channel = "System Notification"** ← this is the key step.
4. *Recipients*: by a document field (e.g. `allocated_to`, `owner`,
   `employee`) and/or by Role.
5. Subject/message support Jinja: `{{ doc.name }}`, `{{ doc.status }}`, …

Each matching event then lands in the recipient's 🔔 in-app feed **and** is
pushed to their phone (if push is enabled) — leave approved, attendance
marked, invoice submitted, anything. The same rule can also have an Email
sibling: create a second Notification with Channel = Email.

Two gotchas:
- Recipients are matched **by email** — the built-in `Administrator` account
  never receives system notifications, so always test with a real user.
- Delivery runs through the background workers — `bench doctor` /
  `midhunatech.install.doctor` checks they're alive.

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
bench build --app midhunatech
bench --site yoursite.com clear-cache
bench restart
```

Users get the new version automatically the next time they open the app
(the shell cache-busts on every build; an open tab self-reloads once when it
detects a newer build).

### Caching & the ⟳ refresh button
There is deliberately **no caching service worker** — every screen reads live
data from the server, so what users see is always current. The only service
worker is the push-notification one (it never serves cached content).
If a device ever looks out of date anyway (e.g. after a server update):
- tap the **⟳ button** in the Home header, or
- Profile → **⟳ Check for updates & reload app**

Both wipe all browser caches, remove any stale service workers (keeping the
push subscription), and reload the app fresh from the server.

## 10b. Works on ANY site — compatibility matrix

Nothing in the app is tied to a particular site: all API calls are relative
URLs, all display logic reads the site's own metadata, and all configuration
lives in the site's database. Per feature:

| Feature | Works on a fresh real site? | Needs |
|---|---|---|
| Login / Home / tiles / branding | ✅ automatic | — |
| Native doctype lists + detail (`doc_list`) | ✅ any doctype on the site | — |
| Per-tile Fields / Filters control | ✅ | — |
| Create documents (incl. Material Request line items) | ✅ | Create permission |
| Approvals (list / preview / approve / reject) | ✅ adapts to the site's workflows | at least one **active Workflow** |
| Reports: table + KPI cards + charts + date/Item/Warehouse filters | ✅ | the Report (ERPNext for the financial ones) |
| Balance Sheet, P&L, Trial Balance, GL, Stock Balance | ✅ defaults auto-filled from the site's own Company/Fiscal Year | ERPNext |
| Custom DB Script Reports | ✅ | `server_script_enabled: 1` in **common_site_config.json** |
| KPI Dashboard (Number Cards) | ✅ | — |
| Notification feed + bell badge | ✅ | — |
| Push notifications | ✅ keys self-generate per site | HTTPS, background workers, user toggles once per device |
| Check-in / Attendance tab | ✅ (optional, `show_attendance`) | — |
| In-app Settings editor | ✅ | System Manager role |
| Web-page tiles (`iframe_url` / `webpage`) | ✅ | the Web Page must exist **on that site** (site-specific content, e.g. /san) |

The only genuinely site-specific items are *content*: Web Pages you built on
one site don't exist on another (export/import them or recreate), and tile
configuration is per-site by design (seeded with sensible defaults on
install). Verify any installation in one shot:
`bench --site <site> execute midhunatech.install.doctor` → must end `0 failed`.

---

## 11. Troubleshooting

| Symptom | Fix |
|---|---|
| **App blank / not loading on a production site** | `bench build --app midhunatech && bench restart` — production nginx serves `sites/assets`, which is created by bench build. Then run the doctor (below) |
| Old UI after an update | Just close and reopen the app (cache-busting is automatic); worst case `bench clear-cache` |
| Added tile not showing | *Enabled* unticked, or app not refreshed (pull down on Home). Run the doctor |
| Tile opens "… is not configured" | List tiles: set the **DocType** field. Page tiles (webpage/url/frappe_page): set the **Webpage Route / External URL** — an empty target used to open a blank screen |
| Report says "Report failed" | Check the user has the report's role; DB Script Reports need `server_script_enabled` in **common** site config |
| Empty home grid on a fresh site | `bench --site <s> execute midhunatech.install.seed_default_modules` |
| Approvals tile empty | No active Workflow has a state the user's role can act on — check `/app/workflow` |
| Push enabled but nothing arrives | Background workers must be running (`supervisorctl status`); needs HTTPS; iPhone: install to home screen first |
| Push toggle errors "not supported" | Needs HTTPS; on iPhone install to home screen first |
| Tile opens "Module not found" | Module Key in the config row doesn't match the URL slug |

**Harmless console messages** (not errors, safe to ignore):
`initHighlighting() is deprecated` comes from Frappe's own website bundle
(highlight.js), not this app. Real problems show as red **errors** (HTTP 4xx/5xx,
"Uncaught …"), not deprecation/accessibility warnings.

## 12. Production health check (doctor)

One command verifies the whole installation — assets, tiles, doctypes,
reports, server scripts, background workers, scheduler, push library — and
prints the exact fix for anything broken:

```bash
bench --site yoursite.com execute midhunatech.install.doctor
```

Run it after every install/update on a live site, and whenever someone
reports "the app is not loading". Aim for `0 failed`.

### Full diagnosis: doctor + live feature tests

`diagnose` runs everything `doctor` checks **plus** real server-side feature
tests — it actually executes every enabled tile (reports, lists, approvals,
notifications, push) as Administrator, and prints environment versions and
the exact app commit the site is running:

```bash
bench --site yoursite.com execute midhunatech.install.diagnose
```

How to read the result:

- A tile **fails here** → the problem is server-side (data, permissions,
  tile config) — the FAIL line tells you what to fix. It is not the phone.
- **Everything passes here** but the phone still misbehaves → the problem is
  the browser cache on that device: tap the ⟳ button, or remove and re-add
  the home-screen app.

### Status page — when the app itself won't load

Open **`https://yoursite.com/midhunatech_status`** in any browser while
logged in as a **System Manager**. It is a plain server-rendered page (no PWA
code at all), so it works even when the frontend is completely broken, and it
shows the same environment info, installation checks, and feature tests as
`diagnose`, with PASS/FAIL on every line.
