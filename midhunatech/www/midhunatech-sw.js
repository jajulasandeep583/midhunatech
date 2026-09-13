/* Copyright (c) 2026, Midhunatech and Contributors — GPL-3.0
 *
 * App service worker for the /midhunatech PWA.
 *
 * Purpose: make the app INSTALLABLE (Chromium needs a service worker with a
 * fetch handler that controls the manifest scope, and the push SW lives at the
 * /assets scope so it cannot). Served at the site root (/midhunatech-sw.js) so
 * it can legally claim scope "/midhunatech".
 *
 * Strategy: NETWORK-FIRST for navigations + same-origin GETs, so online users
 * ALWAYS get the freshest shell/bundle. /api is never touched by the SW.
 * Cache is only an offline fallback. No stale-shell risk.
 *
 * v2: on activate, wipe EVERY Cache Storage entry on the origin (including
 * caches left behind by older precache/vite-pwa workers that served stale
 * shells) and force-reload every open client — so a browser stuck on an old
 * cached copy of the app heals itself on its next visit.
 */
var SW_VERSION = "mt-app-v4";
var SHELL_CACHE = "midhunatech-shell-" + SW_VERSION;
var OFFLINE_URL = "/midhunatech";

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(SHELL_CACHE)
      .then(function (c) { return c.add(OFFLINE_URL).catch(function () {}); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      // stale caches present = this is an UPDATE over an older version;
      // a brand-new install must NOT reload pages (it would wipe a login
      // form the user is typing into)
      var isUpdate = keys.some(function (k) { return k !== SHELL_CACHE; });
      return Promise.all(keys.map(function (k) {
        if (k !== SHELL_CACHE) return caches.delete(k);
      })).then(function () { return isUpdate; });
    }).then(function (isUpdate) {
      return self.clients.claim().then(function () { return isUpdate; });
    }).then(function (isUpdate) {
      if (!isUpdate) return;
      // Reload every open page so no tab keeps running a stale bundle.
      return self.clients.matchAll({ type: "window" }).then(function (clients) {
        return Promise.all(clients.map(function (c) {
          return c.navigate(c.url).catch(function () {});
        }));
      });
    })
  );
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;   // only same-origin
  if (url.pathname.indexOf("/api/") === 0) return;    // never intercept API calls

  // Network-first: try the network, fall back to cache only when offline.
  e.respondWith(
    fetch(req).then(function (res) {
      if (res && res.status === 200 && res.type === "basic") {
        var copy = res.clone();
        caches.open(SHELL_CACHE).then(function (c) { c.put(req, copy); }).catch(function () {});
      }
      return res;
    }).catch(function () {
      return caches.match(req).then(function (cached) {
        return cached || (req.mode === "navigate" ? caches.match(OFFLINE_URL) : undefined);
      });
    })
  );
});
