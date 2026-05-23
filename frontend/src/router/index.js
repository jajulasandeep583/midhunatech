// Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0

import { createRouter, createWebHistory } from "@ionic/vue-router";
import { session, checkSession } from "@/data/session.js";

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
      { path: "profile", name: "Profile", component: () => import("@/views/Profile.vue") },
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

  return true;
});

export default router;
