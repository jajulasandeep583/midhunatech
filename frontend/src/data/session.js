// Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0
// Reactive auth + config state for the Midhunatech PWA

import { reactive } from "vue";

// ── Read boot data injected by www/midhunatech.html Jinja template ───────────
// window.__MT__ is populated server-side — zero latency on first load
const boot = window.__MT__ || {};

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
  show_attendance: 1,
  modules:  [],
  loaded:   false,
  error:    null,
});

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Returns current CSRF token — always prefer the boot-injected one */
export function csrf() {
  return session.csrf || window.frappe?.csrf_token || "";
}

/** Authenticated fetch — adds credentials + CSRF header */
export function apiFetch(url, opts = {}) {
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

    appConfig.app_name      = c.app_name;
    appConfig.theme_color   = c.theme_color;
    appConfig.primary_color = c.primary_color;
    appConfig.show_attendance = c.show_attendance == null ? 1 : Number(c.show_attendance);
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
