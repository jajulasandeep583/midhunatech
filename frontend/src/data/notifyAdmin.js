// Copyright (c) 2026, Midhunatech and Contributors — GPL-3.0
// Data layer for the in-app notification-rules editor (System Manager only).
// Thin wrapper over midhunatech.api.notify_admin.

import { apiFetch } from "@/data/session.js";

const BASE = "/api/method/midhunatech.api.notify_admin";

async function call(method, body) {
  const opts = body
    ? { method: "POST", body: JSON.stringify(body) }
    : {};
  const r = await apiFetch(`${BASE}.${method}`, opts);
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    const msg = e.exception ? e.exception.split(":").pop().trim() : `HTTP ${r.status}`;
    throw new Error(r.status === 403 ? "System Manager role required" : msg);
  }
  return (await r.json()).message;
}

// ── Meta ──
export const getMeta = () => call("get_meta");
export const getDoctypeFields = (doctype) =>
  call(`get_doctype_fields?doctype=${encodeURIComponent(doctype)}`);

// ── Notifications (alerts) ──
export const listNotifications = () => call("list_notifications");
export const getNotification = (name) =>
  call(`get_notification?name=${encodeURIComponent(name)}`);
export const saveNotification = (payload) => call("save_notification", { payload });
export const toggleNotification = (name, enabled) =>
  call("toggle_notification", { name, enabled: enabled ? 1 : 0 });
export const deleteNotification = (name) => call("delete_notification", { name });

// ── Scheduled reports (Auto Email Report) ──
export const getReports = () => call("get_reports");
export const listAutoEmailReports = () => call("list_auto_email_reports");
export const getAutoEmailReport = (name) =>
  call(`get_auto_email_report?name=${encodeURIComponent(name)}`);
export const saveAutoEmailReport = (payload) => call("save_auto_email_report", { payload });
export const toggleAutoEmailReport = (name, enabled) =>
  call("toggle_auto_email_report", { name, enabled: enabled ? 1 : 0 });
export const deleteAutoEmailReport = (name) => call("delete_auto_email_report", { name });
