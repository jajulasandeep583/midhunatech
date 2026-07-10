<!-- Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0 -->
<template>
  <ion-app>
    <InstallBanner />
    <ion-router-outlet />
  </ion-app>
</template>

<script setup>
import { IonApp, IonRouterOutlet } from "@ionic/vue";
import InstallBanner from "@/components/InstallBanner.vue";
</script>
