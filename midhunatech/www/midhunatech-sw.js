/* Copyright (c) 2026, Midhunatech and Contributors — GPL-3.0
 *
 * App service worker for the /midhunatech PWA.
 *
 * v5: CACHES NOTHING. Earlier versions kept an offline copy of the shell,
 * and stale copies of the app survived on real devices no matter what was
 * deployed — the single worst bug class in this project. This worker now
 * exists only so the app stays installable (Chromium requires a service
 * worker with a fetch handler): the fetch handler is a pass-through, and
 * on activation every cache on the origin is deleted and open pages are
 * reloaded onto the fresh build.
 */
var SW_VERSION = "mt-app-v5-nocache";

self.addEventListener("install", function (e) {
  e.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      var hadCaches = keys.length > 0;
      return Promise.all(keys.map(function (k) { return caches.delete(k); }))
        .then(function () { return hadCaches; });
    }).then(function (hadCaches) {
      return self.clients.claim().then(function () { return hadCaches; });
    }).then(function (hadCaches) {
      if (!hadCaches) return;   // fresh install: never reload (eats form input)
      return self.clients.matchAll({ type: "window" }).then(function (clients) {
        return Promise.all(clients.map(function (c) {
          return c.navigate(c.url).catch(function () {});
        }));
      });
    })
  );
});

// Pass-through: required for installability, never serves cached content.
self.addEventListener("fetch", function (e) {
  return;
});
