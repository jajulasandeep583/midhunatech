<div align="center">

# Midhunatech PWA

**Configurable Progressive Web App on Frappe Framework v16**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Frappe Version](https://img.shields.io/badge/Frappe-v16-green)](https://frappeframework.com)

Install once → configure everything from ERPNext desk → no code changes needed.

</div>

---

## How it works (same mechanism as Frappe HRMS)

```
Frappe HRMS:    hrms/www/hrms.html        →  yoursite.com/hrms
This app:  midhunatech/www/midhunatech.html → yoursite.com/midhunatech
```

Frappe automatically serves any file in `www/` as a URL. That's it.  
`website_route_rules` in `hooks.py` makes sub-paths like `/midhunatech/home` also work.

---

## Requirements

| Requirement | Version |
|---|---|
| Frappe Framework | **v16.x** |
| Python | 3.10+ |
| Node.js | 18+ |
| Yarn | 1.22+ |

---

## Install

```bash
# 1 — Get app into bench
cd ~/frappe-bench
bench get-app https://github.com/midhunatech/midhunatech

# 2 — Install on your site
bench --site yoursite.localhost install-app midhunatech

# 3 — Run migrations (creates DocTypes in MariaDB)
bench --site yoursite.localhost migrate

# 4 — Build frontend assets
cd apps/midhunatech/frontend
yarn install
yarn build

# 5 — Clear Frappe's page cache
cd ~/frappe-bench
bench --site yoursite.localhost clear-cache

# 6 — Open the PWA
# Desktop: https://yoursite.com/midhunatech
# Mobile:  navigate to same URL in Chrome/Safari → Add to Home Screen
```

---

## Development

```bash
# Terminal 1 — run Frappe bench
bench start

# Terminal 2 — Vite dev server (port 8080, proxies to bench on 8000)
cd apps/midhunatech/frontend
yarn dev

# Disable CSRF check for the Vite dev server (DEV ONLY)
bench --site yoursite.localhost set-config ignore_csrf 1

# Open PWA at:
# http://yoursite.localhost:8080/midhunatech
```

After changes to Python files, run `bench --site yoursite.localhost clear-cache`.  
After changes to Vue files, Vite hot-reloads automatically.

---

## Configure from ERPNext desk

1. Log into ERPNext desk
2. Search **Midhunatech PWA Config** (or go to `/app/midhunatech-pwa-config`)
3. Set branding:
   - **App Name** — shown in header and on login screen
   - **Theme Color** — browser address bar / PWA splash color
   - **Primary Color** — buttons, active states, highlights
4. Add rows to the **Modules** table — each row = one tile on the mobile home screen

### Module fields

| Field | Example | Description |
|---|---|---|
| Label | Leave Request | Text on the tile (what user sees) |
| Module Key | `leave_request` | Internal unique slug, no spaces |
| Icon | `calendar` | See icon list below |
| Tile Color | `#22c55e` | Hex color for icon background |
| Route Path | `/leave` | URL slug starting with `/` |
| Module Type | `frappe_page` | See types below |
| Target URL | `/app/leave-application` | Required for frappe_page / iframe_url |
| Display Order | `1` | Lower = appears first |
| Enabled | ✓ | Uncheck to instantly hide from mobile |

### Module types

| Type | What it does | Target URL example |
|---|---|---|
| `frappe_page` | Opens a Frappe/ERPNext desk URL in fullscreen iframe | `/app/leave-application` |
| `iframe_url` | Embeds any external HTTPS URL | `https://metabase.mycompany.com/1` |
| `custom_view` | Renders a Vue component you build yourself | *(leave blank)* |

### Example module rows (copy into desk)

| Label | Key | Icon | Type | Target URL |
|---|---|---|---|---|
| Leave Request | `leave_request` | `calendar` | `frappe_page` | `/app/leave-application` |
| Attendance | `attendance` | `clock` | `frappe_page` | `/app/attendance` |
| Expense Claim | `expense_claim` | `dollar` | `frappe_page` | `/app/expense-claim` |
| My Tasks | `my_tasks` | `check-circle` | `frappe_page` | `/app/task` |
| Team Directory | `team` | `users` | `frappe_page` | `/app/employee` |
| Reports | `reports` | `chart` | `frappe_page` | `/app/query-report` |

---

## Available icons

`calendar` `check-circle` `clipboard` `users` `briefcase` `dollar` `clock`  
`file` `settings` `star` `bell` `location` `chart` `box` `shield`  
`heart` `mail` `phone` `home` `trend-up` `task` `report` `grid`

---

## Adding a custom Vue view

Set module type to `custom_view` and module key to `my_module`.  
Then create: `frontend/src/views/modules/MyModule.vue`

```vue
<template>
  <div>
    <div class="section-title">My Module</div>
    <ion-list>
      <ion-item v-for="item in items" :key="item.name">
        <ion-label>{{ item.title }}</ion-label>
      </ion-item>
    </ion-list>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { IonList, IonItem, IonLabel } from "@ionic/vue";
import { apiFetch } from "@/data/session.js";

const items = ref([]);
onMounted(async () => {
  const r = await apiFetch('/api/resource/MyDocType?fields=["name","title"]');
  const d = await r.json();
  items.value = d.data || [];
});
</script>
```

---

## PWA install on mobile

- **Android Chrome**: visit `/midhunatech` → tap menu → "Add to Home Screen"
- **iOS Safari**: tap Share → "Add to Home Screen"
- **Desktop Chrome**: click install icon in address bar

> HTTPS is required for the browser install prompt in production.  
> Use `bench setup lets-encrypt` or Frappe Cloud.

---

## Project structure

```
midhunatech/                         ← Frappe app root
├── pyproject.toml                   ← v16 packaging config
├── LICENSE                          ← GPL-3.0
├── MANIFEST.in
├── .gitignore
│
├── midhunatech/                     ← Python package
│   ├── __init__.py                  ← __version__ = "1.0.0"
│   ├── hooks.py                     ← all Frappe hooks
│   ├── install.py                   ← after_install, before_migrate
│   ├── modules.txt                  ← "Midhunatech"
│   ├── patches.txt
│   │
│   ├── api/
│   │   └── pwa.py                   ← @frappe.whitelist() API methods
│   │
│   ├── config/
│   │   └── desktop.py               ← v16 workspace sidebar
│   │
│   ├── doctype/
│   │   ├── midhunatech_pwa_config/  ← Single DocType (global config)
│   │   └── midhunatech_pwa_module/  ← Child table (each module row)
│   │
│   ├── public/
│   │   ├── images/logo.svg          ← SVG logo (no raster images)
│   │   └── frontend/                ← built by vite (git-ignored)
│   │
│   └── www/
│       ├── midhunatech.py           ← auth guard + context
│       └── midhunatech.html         ← Jinja entry → boots Vue SPA
│
└── frontend/                        ← Vue 3 + Ionic SPA
    ├── package.json
    ├── vite.config.js
    ├── index.html
    ├── public/manifest.json
    └── src/
        ├── main.js
        ├── App.vue
        ├── main.css
        ├── theme/variables.css
        ├── data/session.js          ← auth + config reactive state
        ├── router/index.js
        └── views/
            ├── Login.vue
            ├── Tabs.vue
            ├── Home.vue
            ├── ModuleView.vue
            ├── Profile.vue
            └── modules/             ← add custom_view components here
```

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE)

Copyright © 2024 Midhunatech. All rights reserved.
