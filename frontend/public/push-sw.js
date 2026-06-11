/* Copyright (c) 2026, Midhunatech and Contributors — GPL-3.0
 * Push-only service worker for the Midhunatech PWA.
 * Registered from /assets/midhunatech/frontend/ — its scope never controls
 * page fetches; it exists solely to receive Web Push and deep-link on tap. */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let d = {};
  try { d = event.data ? event.data.json() : {}; } catch (e) { /* ignore */ }
  const title = d.title || "Midhunatech";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: d.body || "",
      tag: d.tag || "midhunatech",
      renotify: true,
      icon: "/assets/midhunatech/frontend/icon-192.png",
      badge: "/assets/midhunatech/frontend/icon-192.png",
      data: { url: d.url || "/midhunatech/home" },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/midhunatech/home";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if (w.url.includes("/midhunatech") && "focus" in w) {
          if ("navigate" in w) w.navigate(url);
          return w.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
