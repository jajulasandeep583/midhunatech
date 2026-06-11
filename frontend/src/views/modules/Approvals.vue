<!-- Copyright (c) 2026, Midhunatech and Contributors — GPL-3.0 -->
<!-- Generic in-app workflow approvals: works with any doctype that has an
     active Workflow. List → preview (key fields + line items) → Approve/Reject.
     Supports deep links: ?open=Doctype|Name (used by push notifications). -->
<template>
  <div class="ap-wrap">
    <div v-if="loading" class="empty-state" style="padding-top:60px;">
      <ion-spinner name="crescent" color="primary" style="font-size:36px;" />
      <p style="margin-top:10px;">Loading approvals…</p>
    </div>

    <div v-else-if="error" class="empty-state" style="padding-top:60px;" role="alert">
      <div class="empty-icon" aria-hidden="true">⚠</div>
      <h3>Could not load</h3>
      <p>{{ error }}</p>
      <ion-button fill="outline" size="small" @click="load">Try again</ion-button>
    </div>

    <div v-else-if="!items.length" class="empty-state" style="padding-top:60px;">
      <div class="empty-icon" aria-hidden="true">✅</div>
      <h3>Nothing to approve</h3>
      <p>No documents are waiting for your action.</p>
    </div>

    <template v-else>
      <div class="ap-count">{{ items.length }} document{{ items.length !== 1 ? "s" : "" }} waiting</div>
      <div class="ap-list">
        <div
          v-for="it in items"
          :key="it.doctype + it.name"
          class="ap-item"
          role="button"
          tabindex="0"
          @click="openDoc(it)"
          @keyup.enter="openDoc(it)"
        >
          <div class="ap-item-top">
            <span class="ap-chip">{{ it.doctype }}</span>
            <span class="ap-state">{{ it.state }}</span>
          </div>
          <div class="ap-title">{{ it.title }}</div>
          <div class="ap-sub">{{ it.name }}</div>
        </div>
      </div>
    </template>

    <!-- ── Preview + actions: full modal so the action bar is ALWAYS visible ── -->
    <ion-modal :is-open="!!current" @didDismiss="current = null">
      <ion-header>
        <ion-toolbar>
          <ion-title>
            <div class="ap-m-title">{{ detail?.title || current?.name }}</div>
            <div class="ap-m-sub">{{ current?.doctype }} · {{ current?.name }}</div>
          </ion-title>
          <ion-buttons slot="end">
            <ion-button @click="current = null" aria-label="Close">Close</ion-button>
          </ion-buttons>
        </ion-toolbar>
      </ion-header>

      <ion-content>
        <div v-if="detailLoading" class="empty-state" style="padding-top:60px;">
          <ion-spinner name="crescent" color="primary" style="font-size:36px;" />
        </div>

        <div v-else-if="detail" class="ap-detail">
          <div v-if="detail.status" class="ap-d-staterow">
            <span class="ap-state">{{ detail.status }}</span>
          </div>

          <!-- key fields -->
          <div class="ap-fields">
            <div v-for="f in detail.fields" :key="f.label" class="ap-field">
              <div class="ap-f-label">{{ f.label }}</div>
              <div class="ap-f-value">{{ f.value }}</div>
            </div>
          </div>

          <!-- child tables (line items, taxes) -->
          <div v-for="t in detail.tables" :key="t.label" class="ap-table-sec">
            <div class="ap-t-label">{{ t.label }} <span class="ap-t-count">({{ t.rows.length }})</span></div>
            <div class="ap-t-scroll">
              <table class="ap-t">
                <thead>
                  <tr><th v-for="c in t.columns" :key="c">{{ c }}</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(r, i) in t.rows" :key="i">
                    <td v-for="(v, j) in r" :key="j">{{ v }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div v-if="actionError" class="ap-err" role="alert">{{ actionError }}</div>
        </div>
      </ion-content>

      <!-- pinned action bar — never scrolls away -->
      <ion-footer v-if="detail">
        <div class="ap-actions">
          <button
            v-for="a in detail.actions"
            :key="a.action"
            class="ap-btn"
            :class="btnClass(a.action)"
            :disabled="!!acting"
            @click="apply(a)"
          >
            <span v-if="acting === a.action" class="mt-spinner" />
            <span v-else>{{ btnIcon(a.action) }} {{ a.action }}</span>
          </button>
          <div v-if="!detail.actions.length" class="ap-noact">No actions available for your role.</div>
        </div>
      </ion-footer>
    </ion-modal>

    <ion-toast
      :is-open="!!toast"
      :message="toast"
      :duration="2200"
      position="top"
      color="success"
      @didDismiss="toast = ''"
    />
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import {
  IonButton, IonButtons, IonContent, IonFooter, IonHeader,
  IonModal, IonSpinner, IonTitle, IonToast, IonToolbar,
} from "@ionic/vue";
import { apiFetch } from "@/data/session.js";

const route = useRoute();
const loading = ref(true);
const error = ref(null);
const items = ref([]);
const current = ref(null);
const detail = ref(null);
const detailLoading = ref(false);
const acting = ref("");
const actionError = ref("");
const toast = ref("");

onMounted(async () => {
  await load();
  // deep link from a push notification: ?open=Doctype|Name
  const open = route.query.open;
  if (open) {
    const [dt, ...rest] = String(open).split("|");
    const name = rest.join("|");
    if (dt && name) openDoc({ doctype: dt, name, title: name });
  }
});

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const r = await apiFetch("/api/method/midhunatech.api.approvals.get_pending");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    items.value = (await r.json()).message || [];
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function openDoc(it) {
  current.value = it;
  detail.value = null;
  detailLoading.value = true;
  actionError.value = "";
  try {
    const q = `doctype=${encodeURIComponent(it.doctype)}&name=${encodeURIComponent(it.name)}`;
    const r = await apiFetch(`/api/method/midhunatech.api.approvals.get_preview?${q}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    detail.value = (await r.json()).message;
  } catch (e) {
    actionError.value = e.message;
    detail.value = { title: it.title, name: it.name, fields: [], tables: [], actions: [] };
  } finally {
    detailLoading.value = false;
  }
}

async function apply(a) {
  acting.value = a.action;
  actionError.value = "";
  try {
    const r = await apiFetch("/api/method/midhunatech.api.approvals.take_action", {
      method: "POST",
      body: JSON.stringify({
        doctype: current.value.doctype,
        name: current.value.name,
        action: a.action,
      }),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      throw new Error(e._server_messages ? "Action failed — check document" : `HTTP ${r.status}`);
    }
    toast.value = `${a.action}: ${current.value.name} ✓`;
    current.value = null;
    await load();
  } catch (e) {
    actionError.value = e.message;
  } finally {
    acting.value = "";
  }
}

function btnClass(action) {
  const a = (action || "").toLowerCase();
  if (a.includes("reject") || a.includes("cancel")) return "danger";
  if (a.includes("approve") || a.includes("submit")) return "success";
  return "neutral";
}

function btnIcon(action) {
  const a = (action || "").toLowerCase();
  if (a.includes("reject") || a.includes("cancel")) return "✕";
  if (a.includes("approve") || a.includes("submit")) return "✓";
  return "→";
}

defineExpose({ reload: load });
</script>

<style scoped>
.ap-wrap { padding: 12px 14px 30px; }
.ap-count { font-size: 12.5px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: .4px; margin: 4px 2px 10px; }
.ap-list { display: flex; flex-direction: column; gap: 10px; }
.ap-item { background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; padding: 14px; cursor: pointer; }
.ap-item:active { background: #f8fafc; }
.ap-item-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; gap: 8px; }
.ap-chip { font-size: 10.5px; font-weight: 800; color: #6366f1; background: #eef2ff; border-radius: 999px; padding: 3px 9px; white-space: nowrap; }
.ap-state { font-size: 11px; font-weight: 800; color: #b45309; background: #fef3c7; border-radius: 999px; padding: 3px 9px; white-space: nowrap; }
.ap-title { font-size: 15px; font-weight: 800; color: #1e293b; word-break: break-word; }
.ap-sub { font-size: 12px; color: #94a3b8; margin-top: 2px; word-break: break-all; }

/* ── modal ── */
.ap-m-title { font-size: 15px; font-weight: 800; color: #0f172a; line-height: 1.2;
              overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ap-m-sub { font-size: 11px; font-weight: 500; color: #94a3b8;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ap-detail { padding: 14px 16px 20px; }
.ap-d-staterow { margin-bottom: 12px; }
.ap-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.ap-field { background: #f8fafc; border-radius: 12px; padding: 9px 11px; min-width: 0; }
.ap-field:first-child { grid-column: 1 / -1; }
.ap-f-label { font-size: 10.5px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: .3px; }
.ap-f-value { font-size: 13.5px; font-weight: 600; color: #1e293b; margin-top: 2px; word-break: break-word; }
@media (max-width: 360px) { .ap-fields { grid-template-columns: 1fr; } }

.ap-table-sec { margin-top: 16px; }
.ap-t-label { font-size: 12.5px; font-weight: 800; color: #475569; margin-bottom: 7px; }
.ap-t-count { font-weight: 600; color: #94a3b8; }
.ap-t-scroll { overflow-x: auto; border: 1px solid #e2e8f0; border-radius: 12px; -webkit-overflow-scrolling: touch; }
.ap-t { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.ap-t th { background: #f8fafc; text-align: left; padding: 8px 10px; font-weight: 700; color: #64748b; white-space: nowrap; }
.ap-t td { padding: 8px 10px; border-top: 1px solid #f1f5f9; color: #1e293b; white-space: nowrap; }

.ap-err { margin-top: 14px; background: #fef2f2; color: #dc2626; font-size: 13px; border-radius: 10px; padding: 10px 12px; }

/* pinned action bar */
.ap-actions {
  display: flex; gap: 10px; flex-wrap: wrap;
  padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, .97);
  backdrop-filter: blur(6px);
  border-top: 1px solid #eef2f7;
}
.ap-btn {
  flex: 1; min-width: 120px; height: 50px; border: none; border-radius: 14px;
  font-size: 15.5px; font-weight: 800; color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 6px;
  -webkit-appearance: none;
}
.ap-btn.success { background: #16a34a; box-shadow: 0 3px 10px rgba(22,163,74,.3); }
.ap-btn.danger  { background: #ef4444; box-shadow: 0 3px 10px rgba(239,68,68,.3); }
.ap-btn.neutral { background: #6366f1; box-shadow: 0 3px 10px rgba(99,102,241,.3); }
.ap-btn:active:not(:disabled) { transform: scale(.98); }
.ap-btn:disabled { opacity: .6; }
.ap-noact { font-size: 13px; color: #94a3b8; padding: 8px 0; }
</style>
