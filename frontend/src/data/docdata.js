// Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0
// Thin client for the generic doctype data API (midhunatech.api.data.*)

import { apiFetch } from "./session.js";

async function call(method, params = {}) {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== "")),
  ).toString();
  const r = await apiFetch(`/api/method/${method}${qs ? `?${qs}` : ""}`);
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const e = await r.json();
      msg = (e._server_messages && JSON.parse(e._server_messages)[0]) || e.message || msg;
      try { msg = JSON.parse(msg).message || msg; } catch { /* plain string */ }
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  return (await r.json()).message;
}

async function callPost(method, body = {}) {
  const r = await apiFetch(`/api/method/${method}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let msg = `HTTP ${r.status}`;
    try {
      const e = await r.json();
      msg = (e._server_messages && JSON.parse(e._server_messages)[0]) || e.message || msg;
      try { msg = JSON.parse(msg).message || msg; } catch { /* plain */ }
      msg = String(msg).replace(/<[^>]*>/g, "");
    } catch { /* ignore */ }
    throw new Error(msg);
  }
  return (await r.json()).message;
}

export const getView = (doctype, label, fields, filters) =>
  call("midhunatech.api.data.get_view", { doctype, label, fields, filters });

export const getDashboard = (target) =>
  call("midhunatech.api.data.get_dashboard", { target });

export const getCreateMeta = (doctype) =>
  call("midhunatech.api.data.get_create_meta", { doctype });

export const searchLink = (doctype, txt) =>
  call("midhunatech.api.data.search_link", { doctype, txt });

export const createDoc = (doctype, values) =>
  callPost("midhunatech.api.data.create_doc", { doctype, values: JSON.stringify(values) });

export const getList = (doctype, { search, start, page_length, fields, filters } = {}) =>
  call("midhunatech.api.data.get_list", { doctype, search, start, page_length, fields, filters });

export const getDoc = (doctype, name, fields) =>
  call("midhunatech.api.data.get_doc", { doctype, name, fields });

// Map a status string to a soft badge palette (works for any doctype)
export function badgeClass(status) {
  const s = (status || "").toLowerCase();
  if (/(submit|approv|complet|paid|active|present|success|closed|open)/.test(s)) return "ok";
  if (/(draft|pending|open|to |unpaid|requested|review)/.test(s)) return "warn";
  if (/(cancel|reject|fail|overdue|absent|expired)/.test(s)) return "bad";
  return "neutral";
}
