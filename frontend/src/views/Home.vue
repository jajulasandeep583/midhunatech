<!-- Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0 -->
<template>
  <ion-page>

    <!-- ── Sticky header ── -->
    <ion-header :translucent="true">
      <ion-toolbar>
        <div slot="start" style="padding-left:14px;">
          <span v-if="appConfig.app_name && appConfig.app_name !== 'Midhunatech'" class="mt-wordmark">
            {{ appConfig.app_name }}
          </span>
          <span v-else class="mt-wordmark">Midhuna<span class="accent">tech</span></span>
        </div>
        <div slot="end" style="padding-right:14px;display:flex;align-items:center;gap:10px;">
          <button
            class="mt-bell"
            aria-label="Refresh app"
            :disabled="refreshing"
            @click="doHardRefresh"
          >
            <span :class="{ 'mt-spin': refreshing }" style="display:inline-block;">⟳</span>
          </button>
          <button
            class="mt-bell"
            aria-label="Notifications"
            @click="router.push('/midhunatech/notifications')"
          >
            🔔
            <span v-if="notify.unread" class="mt-bell-badge">{{ notify.unread > 99 ? "99+" : notify.unread }}</span>
          </button>
          <div
            class="mt-avatar"
            :style="{ background: appConfig.primary_color }"
            @click="router.push('/midhunatech/profile')"
            role="button"
            :aria-label="`${session.fullname || session.user} — go to profile`"
            tabindex="0"
            @keyup.enter="router.push('/midhunatech/profile')"
          >{{ userInitial }}</div>
        </div>
      </ion-toolbar>
    </ion-header>

    <ion-content :fullscreen="true">

      <!-- iOS large collapsible title -->
      <ion-header collapse="condense">
        <ion-toolbar>
          <ion-title size="large">
            <div style="font-size:13px;font-weight:500;color:#94a3b8;margin-bottom:3px;">
              {{ greeting }}
            </div>
            <div style="font-size:26px;font-weight:900;letter-spacing:-.5px;color:#1e293b;">
              {{ session.fullname || session.user }}
            </div>
          </ion-title>
        </ion-toolbar>
      </ion-header>

      <!-- Pull to refresh -->
      <ion-refresher slot="fixed" @ionRefresh="onRefresh">
        <ion-refresher-content pulling-text="Pull to refresh" refreshing-spinner="crescent" />
      </ion-refresher>

      <!-- ── SKELETON loading (apps) ── -->
      <template v-if="!appConfig.loaded && !appConfig.error">
        <div class="section-title">Apps</div>
        <div class="module-grid">
          <div v-for="i in 6" :key="i" class="module-card" style="pointer-events:none;" aria-hidden="true">
            <ion-skeleton-text :animated="true" style="width:44px;height:44px;border-radius:12px;" />
            <ion-skeleton-text :animated="true" style="width:80%;height:14px;border-radius:6px;" />
            <ion-skeleton-text :animated="true" style="width:50%;height:11px;border-radius:6px;" />
          </div>
        </div>
      </template>

      <!-- ── ERROR state ── -->
      <div v-else-if="appConfig.error" class="empty-state" role="alert">
        <div class="empty-icon" aria-hidden="true">⚠</div>
        <h3>Could not load modules</h3>
        <p>{{ appConfig.error }}</p>
        <ion-button fill="outline" size="small" @click="retry" style="margin-top:12px;">Try again</ion-button>
      </div>

      <!-- ── EMPTY — no modules configured ── -->
      <div v-else-if="appConfig.modules.length === 0" class="empty-state">
        <div class="empty-icon" aria-hidden="true">⊞</div>
        <h3>No modules yet</h3>
        <p>Open <strong>App Settings</strong> to add your first tile.</p>
        <ion-button v-if="session.is_system_manager" fill="outline" size="small" @click="openConfig" style="margin-top:12px;">
          Configure now ↗
        </ion-button>
      </div>

      <!-- ── MODULE GRID ── -->
      <template v-else>
        <div class="section-title">Apps</div>
        <div class="module-grid" role="list">
          <div
            v-for="mod in appConfig.modules"
            :key="mod.name"
            class="module-card"
            role="listitem"
            tabindex="0"
            :aria-label="`Open ${mod.label}`"
            @click="openModule(mod)"
            @keyup.enter="openModule(mod)"
          >
            <div class="module-icon" :style="{ background: hexAlpha(mod.color, .12) }" aria-hidden="true">
              <span :style="{ color: mod.color }">{{ iconChar(mod.icon) }}</span>
            </div>
            <div>
              <div class="module-label">{{ mod.label }}</div>
              <div class="module-sub">{{ typeLabel(mod.type) }}</div>
            </div>
          </div>
        </div>
      </template>

      <!-- build stamp: tells us instantly whether this copy is current -->
      <div class="mt-build">
        Build {{ buildVersion }}
        <button class="mt-build-btn" :disabled="refreshing" @click="doHardRefresh">
          {{ refreshing ? "updating…" : "update now" }}
        </button>
      </div>

    </ion-content>
  </ion-page>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  IonPage, IonHeader, IonToolbar, IonTitle, IonContent,
  IonRefresher, IonRefresherContent, IonSkeletonText, IonButton,
} from "@ionic/vue";
import {
  session, appConfig, loadConfig, hexAlpha, hardRefresh, buildVersion,
} from "@/data/session.js";
import { notify, loadFeed } from "@/data/notify.js";

const router      = useRouter();
const userInitial = computed(() =>
  (session.fullname || session.user || "M")[0].toUpperCase()
);

const greeting = computed(() => {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
});

onMounted(() => {
  loadConfig();
  loadFeed();
});

async function onRefresh(e) {
  await Promise.all([loadConfig(true), loadFeed()]);
  e.target.complete();
}

const refreshing = ref(false);
async function doHardRefresh() {
  refreshing.value = true;
  try { await hardRefresh(); } finally { /* page navigates away */ }
}

async function retry() {
  appConfig.error  = null;
  appConfig.loaded = false;
  await loadConfig();
}

function openModule(mod) {
  // drop focus from the tapped tile BEFORE Ionic hides this page —
  // a focused element under aria-hidden triggers a browser a11y warning
  document.activeElement?.blur?.();
  router.push(`/midhunatech/module/${encodeURIComponent(mod.name)}`);
}
function openConfig() {
  router.push("/midhunatech/settings");
}

function typeLabel(t) {
  return {
    frappe_page: "Frappe", iframe_url: "Web", webpage: "Web", url: "Web",
    custom_view: "Built-in", doc_list: "Native", doctype: "Native", list_view: "Native",
    dashboard: "Dashboard", number_card: "KPI", report: "Report",
  }[t] || t;
}

const ICON_MAP = {
  calendar: "📅", "check-circle": "✅", clipboard: "📋", users: "👥",
  briefcase: "💼", dollar: "💰", clock: "🕐", file: "📄", settings: "⚙️",
  star: "⭐", bell: "🔔", location: "📍", chart: "📊", box: "📦",
  shield: "🛡️", heart: "❤️", mail: "✉️", phone: "📞", home: "🏠",
  "trend-up": "📈", task: "✔️", report: "📑", grid: "⊞",
};
function iconChar(name) {
  if (!name) return "⊞";
  if (ICON_MAP[name]) return ICON_MAP[name];
  // emojis (or any non-ascii char) pass through untouched
  return /[^\x00-\x7F]/.test(name) ? name : "⊞";
}
</script>

<style scoped>
@keyframes mt-rotate { from { transform: rotate(0); } to { transform: rotate(360deg); } }
.mt-spin { animation: mt-rotate 1s linear infinite; }
.mt-bell {
  position: relative;
  width: 38px; height: 38px;
  border: none; background: #f1f5f9; border-radius: 50%;
  font-size: 17px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
}
.mt-build {
  text-align: center; font-size: 11px; color: #94a3b8;
  padding: 18px 0 26px; font-variant-numeric: tabular-nums;
}
.mt-build-btn {
  background: none; border: none; color: var(--ion-color-primary);
  font-size: 11px; font-weight: 700; text-decoration: underline; cursor: pointer;
  -webkit-appearance: none; padding: 2px 4px;
}
.mt-bell-badge {
  position: absolute; top: -3px; right: -4px;
  min-width: 17px; height: 17px; padding: 0 4px;
  background: #ef4444; color: #fff;
  font-size: 10px; font-weight: 800; line-height: 17px;
  border-radius: 999px; text-align: center;
}
</style>
