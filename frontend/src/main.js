// Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0
import { createApp }  from "vue";
import { IonicVue }   from "@ionic/vue";
import App    from "./App.vue";
import router from "./router/index.js";

// Ionic required CSS — order matters
import "@ionic/vue/css/core.css";
import "@ionic/vue/css/normalize.css";
import "@ionic/vue/css/structure.css";
import "@ionic/vue/css/typography.css";
import "@ionic/vue/css/padding.css";
import "@ionic/vue/css/flex-utils.css";
import "@ionic/vue/css/display.css";

// Our theme overrides (must come AFTER Ionic CSS)
import "./theme/variables.css";
import "./main.css";

const app = createApp(App);

app.use(IonicVue, {
  mode:             "ios",   // consistent iOS look on all platforms
  animated:          true,
  swipeBackEnabled:  true,
});
app.use(router);

// Wait for router to be ready before mounting (Ionic requirement)
router.isReady().then(() => app.mount("#app"));

// Self-update: whenever the app becomes visible (and every 5 minutes while
// open), compare the running build with the server's and hard-refresh on
// mismatch — no tab can stay stale.
import { checkBuild } from "@/data/session.js";
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") checkBuild();
});
setInterval(checkBuild, 5 * 60 * 1000);

// Register the app service worker (scoped to /midhunatech) so the PWA is
// installable — Chromium requires a SW with a fetch handler controlling the
// manifest scope. Served from the site root so it can claim "/midhunatech".
// Network-first (see the SW), so it never serves a stale shell. Failure is
// non-fatal: the app works fine, the install banner just won't show.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", async () => {
    // Kill any legacy worker (old precache/vite-pwa builds) that isn't the
    // canonical app SW or the push SW — those served stale shells forever.
    try {
      const regs = await navigator.serviceWorker.getRegistrations();
      for (const reg of regs) {
        const url = reg.active?.scriptURL || reg.waiting?.scriptURL
          || reg.installing?.scriptURL || "";
        if (url && !url.endsWith("/midhunatech-sw.js") && !url.includes("push-sw.js")) {
          await reg.unregister().catch(() => {});
        }
      }
    } catch { /* non-fatal */ }
    navigator.serviceWorker
      .register("/midhunatech-sw.js", { scope: "/midhunatech" })
      .catch((err) => console.warn("[pwa] app SW registration failed", err));
  });
}
