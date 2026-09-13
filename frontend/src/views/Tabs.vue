<!-- Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0 -->
<template>
  <ion-page>
    <ion-tabs>
      <ion-router-outlet />
      <ion-tab-bar slot="bottom">
        <ion-tab-button tab="home" href="/midhunatech/home">
          <ion-icon :icon="homeOutline" aria-hidden="true" />
          <ion-label>Home</ion-label>
        </ion-tab-button>

        <!-- config-driven tabs: any module with "Show in Bottom Nav" -->
        <ion-tab-button
          v-for="m in navModules"
          :key="m.name"
          :tab="`mod-${m.name}`"
          :href="`/midhunatech/m/${encodeURIComponent(m.name)}`"
        >
          <span class="nav-emoji" aria-hidden="true">{{ m.nav_icon || m.icon || "⊞" }}</span>
          <ion-label>{{ m.nav_label || m.label }}</ion-label>
        </ion-tab-button>

        <ion-tab-button tab="profile" href="/midhunatech/profile">
          <ion-icon :icon="personOutline" aria-hidden="true" />
          <ion-label>Profile</ion-label>
        </ion-tab-button>
      </ion-tab-bar>
    </ion-tabs>
  </ion-page>
</template>

<script setup>
import { computed } from "vue";
import {
  IonPage, IonTabs, IonTabBar, IonTabButton,
  IonIcon, IonLabel, IonRouterOutlet,
} from "@ionic/vue";
import { homeOutline, personOutline } from "ionicons/icons";
import { appConfig } from "@/data/session.js";

// max 3 custom tabs so the bar stays usable on small phones
const navModules = computed(() =>
  appConfig.modules
    .filter((m) => m.nav)
    .sort((a, b) => (a.nav_order || 0) - (b.nav_order || 0))
    .slice(0, 3)
);
</script>

<style scoped>
.nav-emoji {
  font-size: 20px;
  line-height: 1;
  margin-bottom: 2px;
}
</style>
