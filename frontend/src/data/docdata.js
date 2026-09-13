// Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0
// Thin client for the generic doctype data API (midhunatech.api.data.*)

import { apiFetch } from "./session.js";

// Pull the REAL error out of a failed response. _server_messages can hold
// several messages — info ones (e.g. "Item Price added …") must not mask the
// actual validation error, so prefer the message that raised / is red, then
// fall back to the last one, then the exception line.
async function errMessage(r) {
  let msg = `HTTP ${r.status}`;
  try {
    const e = await r.json();
    const raw = e._server_messages ? JSON.parse(e._server_messages) : [];
    const parsed = raw.map((m) => {
      try { return JSON.parse(m); } catch { return { message: m }; }
    });
    const pick = parsed.find((m) => m.raise_exception || m.indicator === "red")
      || parsed[parsed.length - 1];
    msg = (pick && pick.message)
      || (e.exception && String(e.exception).split(":").slice(1).join(":"))
      || e.message || msg;
    msg = String(msg).replace(/<[^>]*>/g, "").trim() || `HTTP ${r.status}`;
  } catch { /* ignore */ }
  return msg;
}

async function call(method, params = {}) {
  const qs = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== "")),
  ).toString();
  const r = await apiFetch(`/api/method/${method}${qs ? `?${qs}` : ""}`);
  if (!r.ok) throw new Error(await errMessage(r));
  return (await r.json()).message;
}

async function callPost(method, body = {}) {
  const r = await apiFetch(`/api/method/${method}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await errMessage(r));
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

export const createDoc = (doctype, values, submit = 0) =>
  callPost("midhunatech.api.data.create_doc",
    { doctype, values: JSON.stringify(values), submit: submit ? 1 : 0 });

export const getList = (doctype, { search, start, page_length, fields, filters } = {}) =>
  call("midhunatech.api.data.get_list", { doctype, search, start, page_length, fields, filters });

export const getDoc = (doctype, name, fields) =>
  call("midhunatech.api.data.get_doc", { doctype, name, fields });

export const emailDoc = (doctype, name, recipients, message) =>
  callPost("midhunatech.api.data.email_doc", { doctype, name, recipients, message });

export const submitDoc = (doctype, name) =>
  callPost("midhunatech.api.data.submit_doc", { doctype, name });

export const cancelDoc = (doctype, name) =>
  callPost("midhunatech.api.data.cancel_doc", { doctype, name });

export const amendDoc = (doctype, name) =>
  callPost("midhunatech.api.data.amend_doc", { doctype, name });

export const deleteDoc = (doctype, name) =>
  callPost("midhunatech.api.data.delete_doc", { doctype, name });

export const generateEinvoice = (name) =>
  callPost("midhunatech.api.data.generate_einvoice", { name });

export const generateEwaybill = (name) =>
  callPost("midhunatech.api.data.generate_ewaybill", { name });

export const getPaymentMeta = (doctype, name) =>
  call("midhunatech.api.data.get_payment_meta", { doctype, name });

export const recordPayment = (doctype, name, values) =>
  callPost("midhunatech.api.data.record_payment", { doctype, name, ...values });

// Map a status string to a soft badge palette (works for any doctype)
export function badgeClass(status) {
  const s = (status || "").toLowerCase();
  if (/(submit|approv|complet|paid|active|present|success|closed|open)/.test(s)) return "ok";
  if (/(draft|pending|open|to |unpaid|requested|review)/.test(s)) return "warn";
  if (/(cancel|reject|fail|overdue|absent|expired)/.test(s)) return "bad";
  return "neutral";
}
