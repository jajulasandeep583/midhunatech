// Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0
// Reactive auth + config state for the Midhunatech PWA

import { reactive } from "vue";

// ── Read boot data injected by www/midhunatech.html Jinja template ───────────
// window.__MT__ is populated server-side — zero latency on first load
const boot = window.__MT__ || {};

/** Build version this page is running — shown in the app so a stale copy
 *  can be identified at a glance instead of guessed at. */
export const buildVersion = boot.build_v || "";

export const session = reactive({
  user:      boot.user     || null,
  fullname:  boot.fullname || "",
  email:     "",
  is_system_manager: false,
  // session is already checked if Frappe injected a real user
  isLoggedIn: !!(boot.user && boot.user !== "Guest"),
  isChecked:  !!(boot.user && boot.user !== "Guest"),
  csrf:       boot.csrf || "",
});

export const appConfig = reactive({
  app_name:      boot.app_name      || "Midhunatech",
  theme_color:   boot.theme_color   || "#6366f1",
  primary_color: boot.primary_color || "#6366f1",
  modules:  [],
  loaded:   false,
  error:    null,
});

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Returns current CSRF token — always prefer the boot-injected one */
export function csrf() {
  return session.csrf || window.frappe?.csrf_token || "";
}

/** Poll the server's build version (throttled to once a minute) and
 *  hard-refresh when a newer build is deployed. Long-lived tabs never
 *  navigate, so this is the only reliable way they pick up updates. */
let lastBuildCheck = 0;
export async function checkBuild() {
  const now = Date.now();
  if (!boot.build_v || now - lastBuildCheck < 60000) return;
  lastBuildCheck = now;
  try {
    const r = await fetch("/api/method/midhunatech.api.pwa.get_build",
                          { credentials: "include" });
    const b = (await r.json())?.message?.build_v;
    if (b && String(b) !== String(boot.build_v)) await hardRefresh();
  } catch { /* offline — try again on the next check */ }
}

/** Authenticated fetch — adds credentials + CSRF header.
 *  If the server rejects our CSRF token (a tab left open across a server
 *  restart / re-login holds a stale one, and every POST then fails with
 *  "Invalid Request"), silently fetch a fresh token and RETRY the request
 *  once — the user's tap just works, no reload, nothing lost. */
async function rawFetch(url, opts) {
  return fetch(url, {
    credentials: "include",
    headers: {
      "Content-Type":        "application/json",
      "X-Frappe-CSRF-Token": csrf(),
      ...(opts.headers || {}),
    },
    ...opts,
  });
}

export async function apiFetch(url, opts = {}) {
  let r = await rawFetch(url, opts);
  if (r.status === 400 || r.status === 403) {
    try {
      const body = await r.clone().text();
      if (body.includes("CSRFTokenError")) {
        const tr = await fetch("/api/method/midhunatech.api.pwa.get_csrf",
                               { credentials: "include" });
        const fresh = (await tr.json())?.message?.csrf_token;
        if (fresh) {
          session.csrf = fresh;
          r = await rawFetch(url, opts);   // retry the exact same request
        }
      }
    } catch { /* fall through to normal error handling */ }
  }
  return r;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

/**
 * Verify session against Frappe.
 * Called once by the router guard when boot data is absent (e.g. direct URL visit in dev).
 */
export async function checkSession() {
  if (session.isChecked) return session.isLoggedIn;
  try {
    const r = await fetch("/api/method/frappe.auth.get_logged_user", {
      credentials: "include",
    });
    const d = await r.json();
    if (d.message && d.message !== "Guest") {
      session.user      = d.message;
      session.isLoggedIn = true;
    } else {
      session.isLoggedIn = false;
    }
  } catch {
    session.isLoggedIn = false;
  } finally {
    session.isChecked = true;
  }
  return session.isLoggedIn;
}

/** Login — returns Frappe login response */
export async function login(usr, pwd) {
  const r = await fetch("/api/method/login", {
    method:      "POST",
    credentials: "include",
    headers: {
      "Content-Type":        "application/json",
      "X-Frappe-CSRF-Token": csrf(),
    },
    body: JSON.stringify({ usr, pwd }),
  });

  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(e.message || "Invalid email or password.");
  }

  const d = await r.json();

  // Update CSRF token from response headers if provided
  const newCsrf = r.headers.get("X-Frappe-CSRF-Token");
  if (newCsrf) session.csrf = newCsrf;

  session.user       = d.full_name || usr;
  session.isLoggedIn = true;
  session.isChecked  = true;
  return d;
}

/** Logout — clears all state and resets CSRF */
export async function logout() {
  try {
    await fetch("/api/method/logout", {
      method:      "POST",
      credentials: "include",
      headers: { "X-Frappe-CSRF-Token": csrf() },
    });
  } catch {
    // ignore network errors on logout
  }
  // Clear all reactive state
  session.user       = null;
  session.fullname   = "";
  session.email      = "";
  session.csrf       = "";
  session.isLoggedIn = false;
  session.isChecked  = false;
  session.is_system_manager = false;
  appConfig.modules  = [];
  appConfig.loaded   = false;
  appConfig.error    = null;
}

// ── Config ────────────────────────────────────────────────────────────────────

/** Load PWA config from the Frappe API — called once after login */
export async function loadConfig(force = false) {
  if (appConfig.loaded && !force) return;
  try {
    const r = await apiFetch("/api/method/midhunatech.api.pwa.get_config");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    const c = d.message;

    // self-update: if the server has a newer build than the one this page
    // booted with, hard-refresh once (clears caches + old SW) — even a tab
    // that was never closed catches up.
    if (c.build_v && boot.build_v && String(c.build_v) !== String(boot.build_v)) {
      const k = `mt_reloaded_${c.build_v}`;
      if (!sessionStorage.getItem(k)) {
        sessionStorage.setItem(k, "1");
        await hardRefresh();
        return;
      }
    }

    appConfig.app_name      = c.app_name;
    appConfig.theme_color   = c.theme_color;
    appConfig.primary_color = c.primary_color;
    appConfig.modules       = c.modules || [];
    appConfig.loaded        = true;
    appConfig.error         = null;

    session.fullname           = c.fullname;
    session.email              = c.email;
    session.is_system_manager  = c.is_system_manager || false;

    // Apply dynamic brand colors to Ionic CSS variables
    document.documentElement.style.setProperty("--ion-color-primary",          c.primary_color);
    document.documentElement.style.setProperty("--ion-color-primary-shade",    shadeHex(c.primary_color, -20));
    document.documentElement.style.setProperty("--ion-color-primary-tint",     shadeHex(c.primary_color, +20));
    document.documentElement.style.setProperty("--ion-tab-bar-color-selected", c.primary_color);
    document.querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", c.theme_color);

  } catch (e) {
    appConfig.error = e.message || "Failed to load PWA config.";
  }
}

// ── Hard refresh ──────────────────────────────────────────────────────────────

/**
 * Force-update the whole PWA: wipe every Cache Storage entry, unregister any
 * stale service workers (the push worker is kept — removing it would drop the
 * push subscription), then reload from the server with a cache-busting URL.
 * Wired to the ⟳ button on Home and "Check for updates" in Profile.
 */
export async function hardRefresh() {
  try {
    if ("caches" in window) {
      for (const key of await caches.keys()) await caches.delete(key);
    }
  } catch { /* cache API unavailable — continue */ }
  try {
    const regs = (await navigator.serviceWorker?.getRegistrations?.()) || [];
    for (const reg of regs) {
      const url = reg.active?.scriptURL || reg.installing?.scriptURL || "";
      if (!url.includes("push-sw.js")) await reg.unregister();
    }
  } catch { /* no service worker support — continue */ }
  // bypass any cached HTML for the shell
  window.location.replace(`/midhunatech/home?r=${Date.now()}`);
}

// ── Colour helpers ────────────────────────────────────────────────────────────

/** Returns a lightened/darkened version of a hex colour */
function shadeHex(hex, amount) {
  if (!hex || hex.length < 7) return hex;
  const r = Math.min(255, Math.max(0, parseInt(hex.slice(1, 3), 16) + amount));
  const g = Math.min(255, Math.max(0, parseInt(hex.slice(3, 5), 16) + amount));
  const b = Math.min(255, Math.max(0, parseInt(hex.slice(5, 7), 16) + amount));
  return `#${r.toString(16).padStart(2,"0")}${g.toString(16).padStart(2,"0")}${b.toString(16).padStart(2,"0")}`;
}

/** Returns rgba string from hex + alpha */
export function hexAlpha(hex, a) {
  if (!hex || hex.length < 7) return `rgba(99,102,241,${a})`;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
}
