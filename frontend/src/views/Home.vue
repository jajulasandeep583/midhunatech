<!-- Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0 -->
<template>
  <ion-page>

    <!-- ── Sticky header ── -->
    <ion-header :translucent="true">
      <ion-toolbar>
        <div slot="start" style="padding-left:14px;">
          <span class="mt-wordmark">Midhuna<span class="accent">tech</span></span>
        </div>
        <!-- Text-based user avatar — no image needed -->
        <div slot="end" style="padding-right:14px;">
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
            <div style="font-size:13px;font-weight:500;color:#94a3b8;margin-bottom:3px;">Welcome back</div>
            <div style="font-size:26px;font-weight:900;letter-spacing:-.5px;color:#1e293b;">
              {{ session.fullname || session.user }}
            </div>
          </ion-title>
        </ion-toolbar>
      </ion-header>

      <!-- Pull to refresh -->
      <ion-refresher slot="fixed" @ionRefresh="onRefresh">
        <ion-refresher-content
          pulling-text="Pull to refresh"
          refreshing-spinner="crescent"
        />
      </ion-refresher>

      <!-- ── SKELETON loading ── -->
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
        <ion-button fill="outline" size="small" @click="retry" style="margin-top:12px;">
          Try again
        </ion-button>
      </div>

      <!-- ── EMPTY — no modules configured ── -->
      <div v-else-if="appConfig.modules.length === 0" class="empty-state">
        <div class="empty-icon" aria-hidden="true">⊞</div>
        <h3>No modules yet</h3>
        <p>
          Go to ERPNext desk →
          <strong>Midhunatech PWA Config</strong>
          → add module rows to show them here.
        </p>
        <ion-button
          v-if="session.is_system_manager"
          fill="outline"
          size="small"
          @click="openConfig"
          style="margin-top:12px;"
        >
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
            <!-- Icon circle with translucent brand color background -->
            <div
              class="module-icon"
              :style="{ background: hexAlpha(mod.color, .12) }"
              aria-hidden="true"
            >
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
import { computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import {
  IonPage, IonHeader, IonToolbar, IonTitle, IonContent,
  IonRefresher, IonRefresherContent, IonSkeletonText, IonButton,
} from "@ionic/vue";
import { session, appConfig, loadConfig, hexAlpha } from "@/data/session.js";

const router      = useRouter();
const userInitial = computed(() =>
  (session.fullname || session.user || "M")[0].toUpperCase()
);

onMounted(() => loadConfig());

async function onRefresh(e) {
  await loadConfig(true);   // force = true
  e.target.complete();
}

async function retry() {
  appConfig.error  = null;
  appConfig.loaded = false;
  await loadConfig();
}

function openModule(mod) {
  router.push(`/midhunatech/module/${encodeURIComponent(mod.name)}`);
}

function openConfig() {
  window.open("/app/midhunatech-pwa-config", "_blank");
}

// ── Display helpers ─────────────────────────────────────────────────────────
function typeLabel(t) {
  return {
    frappe_page:  "Frappe",
    iframe_url:   "Web",
    custom_view:  "Built-in",
  }[t] || t;
}

// Maps the icon field value to a Unicode character (no SVG images needed)
const ICON_MAP = {
  calendar:       "📅",
  "check-circle": "✅",
  clipboard:      "📋",
  users:          "👥",
  briefcase:      "💼",
  dollar:         "💰",
  clock:          "🕐",
  file:           "📄",
  settings:       "⚙️",
  star:           "⭐",
  bell:           "🔔",
  location:       "📍",
  chart:          "📊",
  box:            "📦",
  shield:         "🛡️",
  heart:          "❤️",
  mail:           "✉️",
  phone:          "📞",
  home:           "🏠",
  "trend-up":     "📈",
  task:           "✔️",
  report:         "📑",
  grid:           "⊞",
};
function iconChar(name) { return ICON_MAP[name] || "⊞"; }
</script>
