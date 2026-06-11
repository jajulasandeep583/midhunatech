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
              {{ checkin.greeting || 'Welcome back' }}
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

      <!-- ── ATTENDANCE / CHECK-IN CARD ── -->
      <div v-if="appConfig.show_attendance" class="ci-wrap">
        <div class="ci-card" :class="{ 'ci-active': checkin.checked_in }">
          <!-- date row -->
          <div class="ci-toprow">
            <span class="ci-date">{{ checkin.today || todayFallback }}</span>
            <span class="ci-status-chip" :class="checkin.checked_in ? 'in' : 'out'">
              <span class="ci-dot" />
              {{ checkin.checked_in ? 'Checked in' : 'Checked out' }}
            </span>
          </div>

          <!-- worked time -->
          <div class="ci-worked">
            <div class="ci-worked-num">{{ formatDuration(liveWorked) }}</div>
            <div class="ci-worked-lbl">
              {{ checkin.checked_in
                  ? `Since ${formatTime(checkin.last_time)}`
                  : (checkin.logs.length ? 'Worked today' : 'No activity yet today') }}
            </div>
          </div>

          <!-- big toggle button -->
          <button
            class="ci-btn"
            :class="checkin.checked_in ? 'ci-btn-out' : 'ci-btn-in'"
            :disabled="checkin.toggling || checkin.loading"
            @click="doToggle"
          >
            <span v-if="checkin.toggling" class="mt-spinner" />
            <span v-else>{{ checkin.checked_in ? 'Check out' : 'Check in' }}</span>
          </button>

          <!-- today's timeline -->
          <div v-if="checkin.logs.length" class="ci-timeline">
            <div v-for="(log, i) in checkin.logs" :key="i" class="ci-log">
              <span class="ci-log-badge" :class="log.log_type === 'IN' ? 'in' : 'out'">
                {{ log.log_type === 'IN' ? '↓' : '↑' }}
              </span>
              <div>
                <div class="ci-log-type">{{ log.log_type === 'IN' ? 'Checked in' : 'Checked out' }}</div>
                <div class="ci-log-time">{{ formatTime(log.time) }}</div>
              </div>
            </div>
          </div>

          <button class="ci-history-link" @click="router.push('/midhunatech/checkin')">
            View attendance history →
          </button>

          <div v-if="checkin.error" class="ci-error" role="alert">{{ checkin.error }}</div>
        </div>
      </div>

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

    </ion-content>
  </ion-page>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  IonPage, IonHeader, IonToolbar, IonTitle, IonContent,
  IonRefresher, IonRefresherContent, IonSkeletonText, IonButton,
} from "@ionic/vue";
import { session, appConfig, loadConfig, hexAlpha, hardRefresh } from "@/data/session.js";
import { notify, loadFeed } from "@/data/notify.js";
import {
  checkin, loadDashboard, toggleCheckin, getCoords,
  formatDuration, formatTime,
} from "@/data/checkin.js";

const router      = useRouter();
const userInitial = computed(() =>
  (session.fullname || session.user || "M")[0].toUpperCase()
);
const todayFallback = new Date().toLocaleDateString(undefined, {
  weekday: "long", day: "numeric", month: "short",
});

// Live-ticking clock while checked in: recompute worked time from the last
// check-in timestamp so the big number counts up in real time.
const now = ref(Date.now());
let timer = null;
const liveWorked = computed(() => {
  if (checkin.checked_in && checkin.last_time) {
    const last = new Date(String(checkin.last_time).replace(" ", "T")).getTime();
    const elapsed = Math.max(0, (now.value - last) / 1000);
    return checkin.worked_seconds + elapsed;
  }
  return checkin.worked_seconds;
});

onMounted(() => {
  loadConfig();
  loadDashboard();
  loadFeed();
  timer = setInterval(() => { now.value = Date.now(); }, 1000);
});
onUnmounted(() => clearInterval(timer));

async function onRefresh(e) {
  await Promise.all([loadConfig(true), loadDashboard(true)]);
  e.target.complete();
}

async function doToggle() {
  try {
    const coords = await getCoords();
    await toggleCheckin(coords);
  } catch { /* error surfaced in checkin.error */ }
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
.mt-bell-badge {
  position: absolute; top: -3px; right: -4px;
  min-width: 17px; height: 17px; padding: 0 4px;
  background: #ef4444; color: #fff;
  font-size: 10px; font-weight: 800; line-height: 17px;
  border-radius: 999px; text-align: center;
}

.ci-wrap { padding: 14px 16px 4px; }

.ci-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 22px;
  padding: 18px;
  box-shadow: 0 1px 12px rgba(15, 23, 42, .04);
  transition: border-color .2s;
}
.ci-card.ci-active { border-color: rgba(34, 197, 94, .4); }

.ci-toprow { display: flex; align-items: center; justify-content: space-between; }
.ci-date { font-size: 13px; font-weight: 600; color: #64748b; }

.ci-status-chip {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11.5px; font-weight: 700;
  padding: 4px 10px; border-radius: 999px;
}
.ci-status-chip.in  { background: #dcfce7; color: #15803d; }
.ci-status-chip.out { background: #f1f5f9; color: #64748b; }
.ci-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.ci-status-chip.in .ci-dot { animation: ci-pulse 1.6s ease-in-out infinite; }
@keyframes ci-pulse { 0%,100% { opacity: 1; } 50% { opacity: .35; } }

.ci-worked { text-align: center; padding: 18px 0 16px; }
.ci-worked-num { font-size: 42px; font-weight: 900; letter-spacing: -1.5px; color: #0f172a; line-height: 1; }
.ci-worked-lbl { font-size: 12.5px; color: #94a3b8; margin-top: 6px; font-weight: 500; }

.ci-btn {
  width: 100%; height: 52px; border: none; border-radius: 16px;
  font-size: 16px; font-weight: 800; color: #fff; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: transform .12s, opacity .15s; -webkit-appearance: none;
}
.ci-btn:active:not(:disabled) { transform: scale(.97); }
.ci-btn:disabled { opacity: .6; }
.ci-btn-in  { background: #16a34a; }
.ci-btn-out { background: #ef4444; }

.ci-timeline {
  display: flex; gap: 10px; overflow-x: auto;
  margin-top: 16px; padding: 4px 2px 2px;
}
.ci-log {
  display: flex; align-items: center; gap: 8px;
  background: #f8fafc; border: 1px solid #eef2f7;
  border-radius: 12px; padding: 8px 12px; flex-shrink: 0;
}
.ci-log-badge {
  width: 26px; height: 26px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-weight: 900; font-size: 14px;
}
.ci-log-badge.in  { background: #dcfce7; color: #16a34a; }
.ci-log-badge.out { background: #fee2e2; color: #ef4444; }
.ci-log-type { font-size: 12px; font-weight: 700; color: #334155; }
.ci-log-time { font-size: 11px; color: #94a3b8; }

.ci-history-link {
  width: 100%; margin-top: 14px; background: none; border: none;
  font-size: 13px; font-weight: 600; color: var(--ion-color-primary);
  cursor: pointer; padding: 4px;
}
.ci-error {
  margin-top: 10px; font-size: 12.5px; color: #dc2626;
  background: #fef2f2; border-radius: 10px; padding: 8px 12px; text-align: center;
}
</style>
