// Copyright (c) 2024, Midhunatech and Contributors
// License: GPL-3.0

import { defineConfig } from "vite";
import vue  from "@vitejs/plugin-vue";
import path from "path";
import { VitePWA } from "vite-plugin-pwa";

// ── Production asset base path ─────────────────────────────────────────────
// CRITICAL: must match exactly so Frappe serves assets correctly.
// Frappe copies app public/ to sites/assets/<appname>/
// www/midhunatech.html references /assets/midhunatech/frontend/index.js
const PROD_BASE = "/assets/midhunatech/frontend/";

export default defineConfig(({ mode }) => ({
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      // We supply our own manifest.json in public/ — don't auto-generate
      manifest: false,
      // Service worker scope must match our PWA path
      scope: "/midhunatech",
      workbox: {
        globPatterns: ["**/*.{js,css,html}"],
        // Don't use navigateFallback — Frappe handles routing server-side
        navigateFallback: null,
        runtimeCaching: [
          {
            // Cache Frappe API responses (NetworkFirst = try network, fall back to cache)
            urlPattern: /^https?:\/\/.*\/api\/(resource|method)\/.*/i,
            handler: "NetworkFirst",
            options: {
              cacheName:           "frappe-api-cache",
              networkTimeoutSeconds: 8,
              expiration: { maxEntries: 100, maxAgeSeconds: 86400 },
            },
          },
          {
            // Cache uploaded files / images
            urlPattern: /^https?:\/\/.*\/(files|private)\/.*/i,
            handler: "CacheFirst",
            options: {
              cacheName: "frappe-files-cache",
              expiration: { maxEntries: 50, maxAgeSeconds: 604800 },
            },
          },
        ],
      },
      devOptions: { enabled: false }, // disable SW in dev
    }),
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
