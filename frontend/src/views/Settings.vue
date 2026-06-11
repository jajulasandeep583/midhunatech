<!-- Copyright (c) 2026, Midhunatech and Contributors — GPL-3.0 -->
<!-- In-app PWA configuration for System Managers: branding, home tiles and
     bottom-nav tabs — fully editable on the phone, no desk, no code. -->
<template>
  <ion-page>
    <ion-header :translucent="true">
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button default-href="/midhunatech/profile" text="Back" />
        </ion-buttons>
        <ion-title>App Settings</ion-title>
        <ion-buttons slot="end">
          <ion-button :disabled="saving || !loaded" strong @click="save">
            <span v-if="saving" class="mt-spinner" />
            <span v-else>Save</span>
          </ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content :fullscreen="true">
      <div v-if="!loaded && !loadError" class="empty-state" style="padding-top:80px;">
        <ion-spinner name="crescent" color="primary" style="font-size:36px;" />
      </div>

      <div v-else-if="loadError" class="empty-state" style="padding-top:80px;" role="alert">
        <div class="empty-icon" aria-hidden="true">⚠</div>
        <h3>Could not load settings</h3>
        <p>{{ loadError }}</p>
        <ion-button fill="outline" size="small" @click="load">Try again</ion-button>
      </div>

      <template v-else>
        <!-- ── Branding ── -->
        <div class="section-title">Branding</div>
        <div class="st-card">
          <div class="st-field">
            <label>App name</label>
            <input v-model="cfg.app_name" type="text" />
          </div>
          <div class="st-row">
            <div class="st-field">
              <label>Primary color</label>
              <input v-model="cfg.primary_color" type="color" />
            </div>
            <div class="st-field">
              <label>Theme color</label>
              <input v-model="cfg.theme_color" type="color" />
            </div>
          </div>
          <label class="st-check">
            <input v-model="cfg.show_attendance" type="checkbox" :true-value="1" :false-value="0" />
            Show Attendance / Check-in
          </label>
        </div>

        <!-- ── Modules ── -->
        <div class="section-title">Tiles &amp; tabs ({{ mods.length }})</div>
        <div class="st-hint">
          Tap a tile to edit it. Use ☰ Bottom tab to pin it in the bottom bar (max 3).
        </div>

        <div class="st-mods">
          <div v-for="(m, i) in mods" :key="i" class="st-mod">
            <div class="st-mod-head" role="button" tabindex="0" @click="toggle(i)" @keyup.enter="toggle(i)">
              <span class="st-mod-icon">{{ m.icon || "⊞" }}</span>
              <div class="st-mod-info">
                <div class="st-mod-label">{{ m.label || "(untitled)" }}</div>
                <div class="st-mod-sub">
                  {{ typeName(m.module_type) }}
                  <template v-if="m.show_in_bottom_nav"> · 📌 bottom tab</template>
                  <template v-if="!Number(m.is_enabled)"> · hidden</template>
                </div>
              </div>
              <div class="st-mod-btns" @click.stop>
                <button class="st-ib" :disabled="i === 0" aria-label="Move up" @click="move(i, -1)">↑</button>
                <button class="st-ib" :disabled="i === mods.length - 1" aria-label="Move down" @click="move(i, 1)">↓</button>
                <button class="st-ib danger" aria-label="Remove" @click="remove(i)">✕</button>
              </div>
            </div>

            <div v-if="open === i" class="st-mod-form">
              <div class="st-row">
                <div class="st-field"><label>Label</label><input v-model="m.label" type="text" /></div>
                <div class="st-field" style="max-width:90px;"><label>Icon</label><input v-model="m.icon" type="text" placeholder="🏭" /></div>
              </div>
              <div class="st-row">
                <div class="st-field">
                  <label>Type</label>
                  <select v-model="m.module_type">
                    <option value="iframe_url">Web page</option>
                    <option value="report">Report</option>
                    <option value="doc_list">Doctype list</option>
                    <option value="dashboard">Dashboard (KPIs)</option>
                    <option value="url">External URL</option>
                    <option value="custom_view">Built-in view</option>
                    <option value="frappe_page">Desk page (iframe)</option>
                  </select>
                </div>
                <div class="st-field">
                  <label>{{ sourceLabel(m.module_type) }}</label>
                  <input v-model="m.target_url" type="text" :placeholder="sourcePlaceholder(m.module_type)" />
                </div>
              </div>
              <div v-if="m.module_type === 'report'" class="st-field">
                <label>Report filters (JSON, optional)</label>
                <input v-model="m.report_filters" type="text" placeholder='{"company": "Your Company"}' />
              </div>
              <label class="st-check">
                <input v-model="m.is_enabled" type="checkbox" :true-value="1" :false-value="0" />
                Show on Home grid
              </label>
              <label class="st-check">
                <input v-model="m.show_in_bottom_nav" type="checkbox" :true-value="1" :false-value="0" />
                ☰ Bottom tab
              </label>
              <div v-if="Number(m.show_in_bottom_nav)" class="st-row">
                <div class="st-field" style="max-width:90px;"><label>Tab icon</label><input v-model="m.bottom_nav_icon" type="text" placeholder="🏭" /></div>
                <div class="st-field"><label>Tab label</label><input v-model="m.bottom_nav_label" type="text" :placeholder="m.label" /></div>
                <div class="st-field" style="max-width:80px;"><label>Order</label><input v-model.number="m.bottom_nav_order" type="number" /></div>
              </div>
            </div>
          </div>
        </div>

        <button class="st-add" @click="add">＋ Add tile</button>

        <div v-if="saveError" class="st-err" role="alert">{{ saveError }}</div>
        <div style="height:30px;" />
      </template>

      <ion-toast :is-open="!!toast" :message="toast" :duration="2000" position="top" color="success" @didDismiss="toast = ''" />
    </ion-content>
  </ion-page>
</template>

<script setup>
import { onMounted, ref } from "vue";
import {
  IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons,
  IonBackButton, IonButton, IonSpinner, IonToast,
} from "@ionic/vue";
import { apiFetch, loadConfig } from "@/data/session.js";

const loaded = ref(false);
const loadError = ref(null);
const cfg = ref({});
const mods = ref([]);
const open = ref(null);
const saving = ref(false);
const saveError = ref("");
const toast = ref("");

onMounted(load);

async function load() {
  loadError.value = null;
  try {
    const r = await apiFetch("/api/method/midhunatech.api.admin.get_admin_config");
    if (!r.ok) throw new Error(r.status === 403 ? "System Manager role required" : `HTTP ${r.status}`);
    const d = (await r.json()).message;
    cfg.value = d.config || {};
    mods.value = d.modules || [];
    loaded.value = true;
  } catch (e) {
    loadError.value = e.message;
  }
}

function toggle(i) { open.value = open.value === i ? null : i; }
function move(i, dir) {
  const j = i + dir;
  if (j < 0 || j >= mods.value.length) return;
  const arr = mods.value;
  [arr[i], arr[j]] = [arr[j], arr[i]];
  if (open.value === i) open.value = j;
}
function remove(i) {
  mods.value.splice(i, 1);
  if (open.value === i) open.value = null;
}
function add() {
  mods.value.push({
    label: "", icon: "🌐", module_type: "iframe_url", target_url: "/",
    is_enabled: 1, show_in_bottom_nav: 0, color: "#059669",
    gradient_from: "#065f46", gradient_to: "#10b981",
  });
  open.value = mods.value.length - 1;
}

function typeName(t) {
  return {
    iframe_url: "Web page", report: "Report", doc_list: "Doctype list",
    dashboard: "Dashboard", url: "External URL", custom_view: "Built-in view",
    frappe_page: "Desk page",
  }[t] || t;
}
function sourceLabel(t) {
  return {
    iframe_url: "Page route", report: "Report name", doc_list: "Doctype name",
    dashboard: "Dashboard / cards", url: "URL", custom_view: "View key",
    frappe_page: "Desk route",
  }[t] || "Source";
}
function sourcePlaceholder(t) {
  return {
    iframe_url: "/san", report: "Production Summary", doc_list: "Sales Order",
    dashboard: "(blank = default cards)", url: "https://…", custom_view: "approvals",
    frappe_page: "/app/sales-order",
  }[t] || "";
}

async function save() {
  saving.value = true;
  saveError.value = "";
  try {
    // derive per-type source fields from the single source input
    const modules = mods.value.map((m, i) => {
      const out = { ...m, display_order: i + 1 };
      if (m.module_type === "report") out.report_name = m.target_url;
      if (m.module_type === "iframe_url") out.webpage_route = m.target_url;
      if (m.module_type === "url") out.external_url = m.target_url;
      if (m.module_type === "doc_list") out.doctype_name = m.target_url;
      return out;
    });
    const r = await apiFetch("/api/method/midhunatech.api.admin.save_admin_config", {
      method: "POST",
      body: JSON.stringify({ config: cfg.value, modules }),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      throw new Error(e.exception ? e.exception.split(":").pop() : `HTTP ${r.status}`);
    }
    await loadConfig(true);
    toast.value = "Saved ✓";
  } catch (e) {
    saveError.value = e.message;
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.st-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 14px; margin: 0 16px 6px; }
.st-row { display: flex; gap: 10px; }
.st-row .st-field { flex: 1; }
.st-field { margin-bottom: 10px; min-width: 0; }
.st-field label { display: block; font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: .3px; margin-bottom: 4px; }
.st-field input[type="text"], .st-field input[type="number"], .st-field select {
  width: 100%; height: 42px; border: 1px solid #e2e8f0; border-radius: 10px;
  padding: 0 11px; font-size: 14px; background: #f8fafc; color: #1e293b;
}
.st-field input[type="color"] { width: 100%; height: 42px; border: 1px solid #e2e8f0; border-radius: 10px; background: #f8fafc; padding: 4px; }
.st-check { display: flex; align-items: center; gap: 9px; font-size: 13.5px; font-weight: 600; color: #334155; padding: 7px 0; }
.st-check input { width: 18px; height: 18px; }

.st-hint { font-size: 12px; color: #94a3b8; margin: -4px 18px 10px; }
.st-mods { display: flex; flex-direction: column; gap: 9px; padding: 0 16px; }
.st-mod { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; overflow: hidden; }
.st-mod-head { display: flex; align-items: center; gap: 11px; padding: 11px 12px; cursor: pointer; }
.st-mod-icon { font-size: 21px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: #f1f5f9; border-radius: 10px; flex-shrink: 0; }
.st-mod-info { flex: 1; min-width: 0; }
.st-mod-label { font-size: 14px; font-weight: 700; color: #1e293b; }
.st-mod-sub { font-size: 11.5px; color: #94a3b8; margin-top: 1px; }
.st-mod-btns { display: flex; gap: 5px; }
.st-ib {
  width: 30px; height: 30px; border: 1px solid #e2e8f0; background: #f8fafc;
  border-radius: 8px; font-size: 14px; color: #475569; cursor: pointer;
}
.st-ib:disabled { opacity: .35; }
.st-ib.danger { color: #ef4444; }
.st-mod-form { border-top: 1px solid #f1f5f9; padding: 12px; }

.st-add {
  margin: 14px 16px 6px; width: calc(100% - 32px); height: 46px;
  border: 2px dashed #cbd5e1; background: transparent; border-radius: 14px;
  font-size: 14px; font-weight: 700; color: #64748b; cursor: pointer;
}
.st-err { margin: 12px 16px; background: #fef2f2; color: #dc2626; font-size: 13px; border-radius: 10px; padding: 10px 12px; }
</style>
