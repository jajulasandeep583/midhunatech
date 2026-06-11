// Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0

import { createRouter, createWebHistory } from "@ionic/vue-router";
import { session, checkSession, appConfig, loadConfig } from "@/data/session.js";

const routes = [
  // ── Public ────────────────────────────────────────────────────────────────
  {
    path:      "/midhunatech/login",
    name:      "Login",
    component: () => import("@/views/Login.vue"),
    meta:      { public: true },
  },

  // ── Authenticated — tab layout ─────────────────────────────────────────────
  {
    path:      "/midhunatech",
    component: () => import("@/views/Tabs.vue"),
    meta:      { requiresAuth: true },
    children: [
      { path: "",        redirect: "/midhunatech/home" },
      { path: "home",    name: "Home",    component: () => import("@/views/Home.vue") },
      { path: "checkin", name: "Checkin", component: () => import("@/views/Checkin.vue") },
      { path: "profile", name: "Profile", component: () => import("@/views/Profile.vue") },
      { path: "notifications", name: "Notifications", component: () => import("@/views/Notifications.vue") },
      { path: "settings", name: "Settings", component: () => import("@/views/Settings.vue") },
      // module opened from a bottom-nav tab — keeps the tab bar visible
      { path: "m/:slug", name: "TabModule", component: () => import("@/views/ModuleView.vue") },
    ],
  },

  // ── Module view — full screen, above tabs ──────────────────────────────────
  {
    path:      "/midhunatech/module/:slug",
    name:      "Module",
    component: () => import("@/views/ModuleView.vue"),
    meta:      { requiresAuth: true },
  },

  // ── Catch-all ─────────────────────────────────────────────────────────────
  { path: "/:catchAll(.*)", redirect: "/midhunatech/home" },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// ── Navigation guard ──────────────────────────────────────────────────────────
router.beforeEach(async (to) => {
  // Public routes (login) — always allow
  if (to.meta.public) return true;

  // Check session if not yet verified
  if (!session.isChecked) {
    await checkSession();
  }

  // Redirect to login if not authenticated
  if (!session.isLoggedIn) {
    return {
      name:  "Login",
      query: { r: to.fullPath },   // preserve the original destination
    };
  }

  // Direct deep links (e.g. from a push notification) land on module routes
  // without ever visiting Home — make sure the PWA config is loaded.
  if (!appConfig.loaded) {
    await loadConfig();
  }

  return true;
});

export default router;
