// Copyright (c) 2024, Midhunatech and Contributors
// License: GPL-3.0

import { defineConfig } from "vite";
import vue  from "@vitejs/plugin-vue";
import path from "path";

// ── Production asset base path ─────────────────────────────────────────────
// CRITICAL: must match exactly so Frappe serves assets correctly.
// Frappe copies app public/ to sites/assets/<appname>/
// www/midhunatech.html references /assets/midhunatech/frontend/index.js
const PROD_BASE = "/assets/midhunatech/frontend/";

export default defineConfig(({ mode }) => ({
  // NOTE: no service-worker / workbox caching layer on purpose.
  // A caching SW served STALE app shells and API data on production sites
  // (its registration scope never matched /midhunatech anyway). Freshness
  // strategy instead: www/midhunatech.html cache-busts index.js with
  // ?v=<build mtime>, lazy chunks are content-hashed, the app self-reloads
  // when it detects a newer build, and users have a ⟳ hard-refresh button.
  // The only SW shipped is public/push-sw.js (push notifications only, no
  // fetch interception).
  plugins: [
    vue(),
  ],

  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },

  // ── Dev server ─────────────────────────────────────────────────────────────
  // Proxies all Frappe API calls to your running bench (port 8000)
  // Vite itself runs on port 8080
  server: {
    port: 8080,
    host: "0.0.0.0",
    proxy: {
      "/api":     { target: "http://127.0.0.1:8000", changeOrigin: true, ws: true },
      "/assets":  { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/files":   { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/private": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },

  // ── Production build ───────────────────────────────────────────────────────
  // Output to ../midhunatech/public/frontend/
  // Frappe will then serve it at /assets/midhunatech/frontend/
  base: mode === "production" ? PROD_BASE : "/",
  build: {
    outDir:     "../midhunatech/public/frontend",
    emptyOutDir: true,
    sourcemap:   false,
    rollupOptions: {
      output: {
        // www/midhunatech.html references these by exact name
        entryFileNames: "index.js",
        chunkFileNames: "[name]-[hash].js",
        assetFileNames: (info) => {
          if (info.name?.endsWith(".css")) return "index.css";
          return "[name]-[hash][extname]";
        },
        // Split vendor chunks for better caching
        manualChunks: {
          ionic:  ["@ionic/vue", "@ionic/vue-router", "ionicons"],
          vendor: ["vue", "vue-router"],
        },
      },
    },
  },
}));
