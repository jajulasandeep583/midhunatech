// Copyright (c) 2026, Midhunatech and Contributors — GPL-3.0
// Web Push subscription helper for the PWA (VAPID, self-hosted).

import { apiFetch } from "@/data/session.js";

const SW_URL = "/assets/midhunatech/frontend/push-sw.js";

export function pushSupported() {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

async function registration() {
  return navigator.serviceWorker.register(SW_URL);
}

/** Current state: "unsupported" | "denied" | "on" | "off" */
export async function pushState() {
  if (!pushSupported()) return "unsupported";
  if (Notification.permission === "denied") return "denied";
  try {
    const reg = await navigator.serviceWorker.getRegistration(SW_URL);
    const sub = reg && (await reg.pushManager.getSubscription());
    return sub ? "on" : "off";
  } catch {
    return "off";
  }
}

/** Ask permission, subscribe this device, save on the server. */
export async function enablePush() {
  if (!pushSupported()) throw new Error("Push is not supported on this device/browser.");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("Notification permission was not granted.");

  const keyRes = await apiFetch("/api/method/midhunatech.api.push.get_vapid_public_key");
  if (!keyRes.ok) throw new Error("Could not get server key.");
  const publicKey = (await keyRes.json()).message;

  const reg = await registration();
  await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey),
    });
  }
  const save = await apiFetch("/api/method/midhunatech.api.push.subscribe", {
    method: "POST",
    body: JSON.stringify({ subscription: sub.toJSON(), user_agent: navigator.userAgent }),
  });
  if (!save.ok) throw new Error("Could not save subscription.");
  return true;
}

/** Unsubscribe this device and remove it on the server. */
export async function disablePush() {
  const reg = await navigator.serviceWorker.getRegistration(SW_URL);
  const sub = reg && (await reg.pushManager.getSubscription());
  if (sub) {
    const endpoint = sub.endpoint;
    await sub.unsubscribe().catch(() => {});
    await apiFetch("/api/method/midhunatech.api.push.unsubscribe", {
      method: "POST",
      body: JSON.stringify({ endpoint }),
    }).catch(() => {});
  }
  return true;
}
