<!-- Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0 -->
<template>
  <ion-page>
    <ion-header :translucent="true">
      <ion-toolbar>
        <ion-title>Profile</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content :fullscreen="true">
      <!-- iOS collapsible large title -->
      <ion-header collapse="condense">
        <ion-toolbar>
          <ion-title size="large">Profile</ion-title>
        </ion-toolbar>
      </ion-header>

      <!-- ── User hero ── -->
      <div class="profile-hero">
        <div
          class="mt-avatar"
          style="width:72px;height:72px;font-size:28px;border-radius:50%;flex-shrink:0;"
          :style="{ background: appConfig.primary_color }"
          aria-hidden="true"
        >{{ userInitial }}</div>
        <div>
          <div class="profile-name">{{ session.fullname || session.user }}</div>
          <div class="profile-email">{{ session.email || session.user }}</div>
        </div>
      </div>

      <!-- ── App info ── -->
      <div class="section-title">App</div>
      <ion-list lines="inset" class="info-list">
        <ion-item>
          <ion-label>
            <h3>App name</h3>
            <p>{{ appConfig.app_name }}</p>
          </ion-label>
        </ion-item>
        <ion-item>
          <ion-label>
            <h3>Site</h3>
            <p>{{ hostname }}</p>
          </ion-label>
        </ion-item>
        <ion-item>
          <ion-label>
            <h3>Modules active</h3>
            <p>{{ appConfig.modules.length }} module{{ appConfig.modules.length !== 1 ? "s" : "" }}</p>
          </ion-label>
        </ion-item>
        <ion-item>
          <ion-label>
            <h3>Version</h3>
            <p>1.0.0 &middot; Frappe v16</p>
          </ion-label>
        </ion-item>
      </ion-list>

      <!-- ── Admin (only visible to System Manager / Administrator) ── -->
      <template v-if="session.is_system_manager">
        <div class="section-title">Admin</div>
        <ion-list lines="inset" class="info-list">
          <ion-item button detail @click="openConfig">
            <ion-label color="primary">⚙ Configure PWA Modules</ion-label>
          </ion-item>
          <ion-item button detail @click="openDesk">
            <ion-label color="primary">🖥 Open ERPNext Desk</ion-label>
          </ion-item>
        </ion-list>
      </template>

      <!-- ── Logout ── -->
      <div class="logout-wrap">
        <button
          class="logout-btn"
          type="button"
          :disabled="busy"
          @click="handleLogout"
          aria-label="Sign out"
        >
          <span v-if="busy" class="mt-spinner" style="border-top-color:#ef4444;border-color:rgba(239,68,68,.3);" />
          <span v-else>Sign out</span>
        </button>
      </div>

    </ion-content>
  </ion-page>
</template>

<script setup>
import { ref, computed } from "vue";
import { useRouter } from "vue-router";
import {
  IonPage, IonHeader, IonToolbar, IonTitle, IonContent,
  IonList, IonItem, IonLabel,
} from "@ionic/vue";
import { session, appConfig, logout } from "@/data/session.js";

const router   = useRouter();
const busy     = ref(false);
const hostname = window.location.hostname;

const userInitial = computed(() =>
  (session.fullname || session.user || "M")[0].toUpperCase()
);

async function handleLogout() {
  if (busy.value) return;
  busy.value = true;
  try {
    await logout();
    router.replace("/midhunatech/login");
  } finally {
    busy.value = false;
  }
}

function openConfig() { window.open("/app/midhunatech-pwa-config", "_blank", "noopener"); }
function openDesk()   { window.open("/app",                         "_blank", "noopener"); }
</script>

<style scoped>
.profile-hero {
  display: flex; align-items: center; gap: 16px;
  padding: 20px 16px 16px;
}
.profile-name  { font-size: 19px; font-weight: 800; color: #1e293b; letter-spacing: -.3px; }
.profile-email { font-size: 13px; color: #94a3b8; margin-top: 2px; }

.info-list { border-radius: 14px; margin: 0 16px; overflow: hidden; }

.logout-wrap { padding: 24px 16px 60px; }
.logout-btn {
  width: 100%; height: 50px; border-radius: 14px;
  border: 1.5px solid #ef4444; background: #fff;
  color: #ef4444; font-size: 16px; font-weight: 700;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  gap: 8px; transition: background .15s;
  -webkit-appearance: none;
}
.logout-btn:hover:not(:disabled)   { background: #fef2f2; }
.logout-btn:active:not(:disabled)  { transform: scale(.98); }
.logout-btn:disabled { opacity: .5; cursor: not-allowed; }
</style>
