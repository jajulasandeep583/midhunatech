<!-- Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0 -->
<!--
  Generic, mobile-first native list for ANY doctype.
  Driven entirely by midhunatech.api.data.* — number cards on top, a search
  box, a scrollable card list, and a tap-through read-only detail sheet.
  No Frappe desk, no iframe.
-->
<template>
  <div class="dl-root">

    <!-- ── Number / summary cards ── -->
    <div v-if="view.cards.length" class="dl-cards">
      <div v-for="(c, i) in view.cards" :key="i" class="dl-card">
        <div class="dl-card-val" :style="{ color: c.color }">{{ c.value }}</div>
        <div class="dl-card-lbl">{{ c.label }}</div>
      </div>
    </div>

    <!-- ── Search ── -->
    <ion-searchbar
      class="dl-search"
      :placeholder="`Search ${view.label || ''}`"
      :debounce="350"
      @ionInput="onSearch($event.detail.value)"
    />

    <!-- ── Loading skeleton ── -->
    <template v-if="loading && !rows.length">
      <div v-for="i in 5" :key="i" class="dl-item" aria-hidden="true">
        <ion-skeleton-text :animated="true" style="width:60%;height:15px;border-radius:6px;" />
        <ion-skeleton-text :animated="true" style="width:40%;height:12px;border-radius:6px;margin-top:8px;" />
      </div>
    </template>

    <!-- ── Error ── -->
    <div v-else-if="error" class="dl-empty" role="alert">
      <div class="dl-empty-ico">⚠</div>
      <h3>Couldn’t load</h3>
      <p>{{ error }}</p>
      <ion-button fill="outline" size="small" @click="reload">Try again</ion-button>
    </div>

    <!-- ── Empty ── -->
    <div v-else-if="!rows.length" class="dl-empty">
      <div class="dl-empty-ico">🗂️</div>
      <h3>Nothing here yet</h3>
      <p>No {{ view.label || 'records' }} found{{ search ? ' for your search' : '' }}.</p>
    </div>

    <!-- ── Record cards ── -->
    <template v-else>
      <div
        v-for="row in rows"
        :key="row.name"
        class="dl-item"
        role="button"
        tabindex="0"
        @click="open(row)"
        @keyup.enter="open(row)"
      >
        <div class="dl-item-top">
          <div class="dl-item-title">{{ row.title }}</div>
          <span v-if="row.badge" class="dl-badge" :class="badgeClass(row.badge)">{{ row.badge }}</span>
        </div>

        <div v-if="row.fields.length" class="dl-meta">
          <span v-for="(f, i) in row.fields" :key="i" class="dl-meta-item">
            <span class="dl-meta-lbl">{{ f.label }}:</span> {{ f.value }}
          </span>
        </div>

        <div class="dl-item-bot">
          <span v-if="row.amount" class="dl-amount">{{ row.amount }}</span>
          <span v-if="row.date" class="dl-date">{{ row.date }}</span>
        </div>
      </div>

      <ion-infinite-scroll :disabled="!hasMore" @ionInfinite="loadMore">
        <ion-infinite-scroll-content loading-spinner="crescent" />
      </ion-infinite-scroll>
    </template>

    <!-- ── Detail sheet ── -->
    <ion-modal :is-open="!!detail || detailLoading" @didDismiss="detail = null" :initial-breakpoint="1" :breakpoints="[0, 1]">
      <ion-header>
        <ion-toolbar>
          <ion-title class="dl-detail-title">{{ detail?.title || 'Loading…' }}</ion-title>
          <ion-buttons slot="end">
            <ion-button @click="detail = null">Close</ion-button>
          </ion-buttons>
        </ion-toolbar>
      </ion-header>
      <ion-content class="ion-padding">
        <div v-if="detailLoading" class="dl-empty"><ion-spinner name="crescent" color="primary" /></div>
        <template v-else-if="detail">
          <div class="dl-detail-head">
            <span v-if="detail.status" class="dl-badge" :class="badgeClass(detail.status)">
              {{ detail.status }}
            </span>
            <div v-if="detail.name" class="dl-actions">
              <button v-if="detail.can_submit" class="dl-act primary" :disabled="!!acting"
                      @click="doSubmit">{{ acting === "submit" ? "Submitting…" : "✓ Submit" }}</button>
              <button v-if="detail.can_edit" class="dl-act" :disabled="!!acting"
                      @click="startEdit">✏️ Edit</button>
              <button v-if="detail.can_einvoice" class="dl-act" :disabled="!!acting"
                      @click="doEinvoice">{{ acting === "einv" ? "Generating…" : "🧾 e-Invoice" }}</button>
              <button v-if="detail.can_ewaybill" class="dl-act" :disabled="!!acting"
                      @click="doEwaybill">{{ acting === "ewb" ? "Generating…" : "🚚 e-Way Bill" }}</button>
              <button v-if="detail.can_pay" class="dl-act" :class="{ on: payOpen }"
                      @click="togglePay">💰 Payment</button>
              <button v-if="view.can_print" class="dl-act" @click="openPrint">🖨️ Print</button>
              <button v-if="view.can_print" class="dl-act" @click="openPdf">📄 PDF</button>
              <button v-if="view.can_email" class="dl-act" :class="{ on: emailOpen }"
                      @click="emailOpen = !emailOpen">✉️ Email</button>
              <button v-if="detail.can_cancel" class="dl-act danger" :disabled="!!acting"
                      @click="doCancel">
                {{ acting === "cancel" ? "Cancelling…" : "✕ Cancel" }}
              </button>
              <button v-if="detail.can_amend" class="dl-act primary" :disabled="!!acting"
                      @click="doAmend">{{ acting === "amend" ? "Amending…" : "✎ Amend" }}</button>
              <button v-if="detail.can_delete" class="dl-act danger" :disabled="!!acting"
                      @click="doDelete">
                {{ acting === "delete" ? "Deleting…" : "🗑 Delete" }}
              </button>
            </div>
          </div>

          <div v-if="actNote" class="dl-email-note" :class="{ err: actErr }"
               style="margin-bottom:10px;" role="alert">{{ actNote }}</div>

          <!-- inline record-payment form -->
          <div v-if="payOpen" class="dl-email">
            <label class="dl-mini-lbl">Amount</label>
            <input v-model="payAmount" type="number" class="dl-email-input" />
            <label class="dl-mini-lbl">Date</label>
            <input v-model="payDate" type="date" class="dl-email-input" />
            <label class="dl-mini-lbl">Mode / account</label>
            <select v-model="payMode" class="dl-email-input">
              <option value="">— default —</option>
              <option v-for="m in payModes" :key="m" :value="m">{{ m }}</option>
            </select>
            <label class="dl-mini-lbl">Reference no. — cheque / UTR (optional)</label>
            <input v-model="payRef" type="text" class="dl-email-input"
                   placeholder="leave blank to auto-fill" />
            <button class="dl-email-send" :disabled="!payAmount || !!acting" @click="doPay">
              {{ acting === "pay" ? "Recording…"
                 : (!payAmount ? "Enter the amount above first" : "Record Payment") }}
            </button>
          </div>

          <!-- inline email (PDF attached) -->
          <div v-if="emailOpen" class="dl-email">
            <input v-model="emailTo" type="email" class="dl-email-input"
                   placeholder="To — email address" />
            <textarea v-model="emailMsg" rows="2" class="dl-email-input"
                      placeholder="Message (optional)"></textarea>
            <button class="dl-email-send" :disabled="!emailTo || emailSending" @click="doEmail">
              {{ emailSending ? "Sending…" : "Send with PDF attached" }}
            </button>
            <div v-if="emailNote" class="dl-email-note" :class="{ err: emailErr }" role="alert">
              {{ emailNote }}
            </div>
          </div>

          <div class="dl-fieldgrid">
            <div class="dl-field" v-for="(f, i) in detail.fields" :key="i"
                 :class="{ wide: String(f.value).length > 26, money: f.fieldtype === 'Currency' }">
              <div class="dl-field-lbl">{{ f.label }}</div>
              <div class="dl-field-val">{{ f.value }}</div>
            </div>
          </div>

          <!-- child tables (items, taxes, accounts, …) -->
          <div v-for="t in detail.tables || []" :key="t.fieldname" class="dl-tbl-sec">
            <div class="dl-tbl-title">{{ t.label }} <span class="dl-tbl-count">{{ t.count }}</span></div>
            <div class="dl-tbl-scroll">
              <table class="dl-t">
                <thead>
                  <tr>
                    <th v-for="(c, ci) in t.columns" :key="ci"
                        :class="{ num: isNumCol(c) }">{{ c.label }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(r, ri) in t.rows" :key="ri">
                    <td v-for="(v, vi) in r" :key="vi"
                        :class="{ num: isNumCol(t.columns[vi]) }">{{ v }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </template>

      </ion-content>
    </ion-modal>


    <!-- ── Floating "+" create button ── -->
    <button v-if="view.can_create" class="dl-fab" :aria-label="`New ${view.label}`"
            @click="editName = ''; showForm = true">+</button>

    <!-- ── Create / edit form ── -->
    <DocForm
      :open="showForm"
      :doctype="props.doctype"
      :label="view.label || props.label"
      :name="editName"
      @close="showForm = false"
      @created="onCreated"
    />

    <ion-toast :is-open="!!toast" :message="toast" :duration="2200" color="success"
      @didDismiss="toast = ''" />

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from "vue";
import {
  IonSearchbar, IonSkeletonText, IonButton, IonInfiniteScroll,
  IonInfiniteScrollContent, IonModal, IonHeader, IonToolbar, IonTitle,
  IonButtons, IonContent, IonSpinner, IonToast,
} from "@ionic/vue";
import {
  getView, getList, getDoc, emailDoc, submitDoc, cancelDoc, amendDoc, deleteDoc,
  generateEinvoice, generateEwaybill, getPaymentMeta, recordPayment, badgeClass,
} from "@/data/docdata.js";

const NUM_COL_TYPES = new Set(["Currency", "Float", "Int", "Percent"]);
function isNumCol(c) { return !!c && NUM_COL_TYPES.has(c.fieldtype); }
import DocForm from "@/views/modules/DocForm.vue";

const props = defineProps({
  doctype: { type: String, required: true },
  label:   { type: String, default: "" },
  // tile-configured display fields (JSON array string) + list filters (JSON dict string)
  fields:  { type: String, default: "" },
  filters: { type: String, default: "" },
});

const view = reactive({ label: props.label, cards: [], doctype: props.doctype });
const rows = ref([]);
const loading = ref(true);
const error = ref(null);
const search = ref("");
const hasMore = ref(false);
let start = 0;

const detail = ref(null);
const detailLoading = ref(false);
const showForm = ref(false);
const editName = ref("");
const toast = ref("");

function startEdit() {
  editName.value = detail.value.name;
  detail.value = null;      // close the sheet; the edit form takes over
  showForm.value = true;
}

async function onCreated(name) {
  toast.value = `Created ${name}`;
  await reload();
  // open the new record straight away — Submit / Print / Payment are right
  // there instead of the user hunting for the draft in the list
  open({ name, title: name });
}

async function reload() {
  loading.value = true;
  error.value = null;
  start = 0;
  try {
    const [v, l] = await Promise.all([
      getView(props.doctype, props.label, props.fields, props.filters),
      getList(props.doctype, { search: search.value, start: 0, page_length: 20,
                               fields: props.fields, filters: props.filters }),
    ]);
    Object.assign(view, v);
    rows.value = l.rows;
    hasMore.value = l.has_more;
    start = l.rows.length;
  } catch (e) {
    error.value = e.message || "Something went wrong.";
  } finally {
    loading.value = false;
  }
}

async function onSearch(val) {
  search.value = val || "";
  start = 0;
  loading.value = true;
  try {
    const l = await getList(props.doctype, { search: search.value, start: 0, page_length: 20,
                                             fields: props.fields, filters: props.filters });
    rows.value = l.rows;
    hasMore.value = l.has_more;
    start = l.rows.length;
    error.value = null;
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function loadMore(ev) {
  try {
    const l = await getList(props.doctype, { search: search.value, start, page_length: 20,
                                             fields: props.fields, filters: props.filters });
    rows.value.push(...l.rows);
    hasMore.value = l.has_more;
    start += l.rows.length;
  } catch { /* keep what we have */ }
  ev.target.complete();
}

async function open(row) {
  detailLoading.value = true;
  emailOpen.value = false; emailNote.value = ""; emailErr.value = false;
  actNote.value = ""; actErr.value = false;
  payOpen.value = false; payModes.value = []; payMode.value = ""; payRef.value = "";
  detail.value = { title: row.title, status: row.badge, fields: [] };
  try {
    detail.value = await getDoc(props.doctype, row.name, props.fields);
  } catch (e) {
    detail.value = { title: row.title, status: row.badge,
      fields: [{ label: "Error", value: e.message }] };
  } finally {
    detailLoading.value = false;
  }
}

// ── submit / e-invoice actions ──
const acting = ref("");
const actNote = ref("");
const actErr = ref(false);

async function doSubmit() {
  acting.value = "submit";
  actNote.value = ""; actErr.value = false;
  try {
    await submitDoc(props.doctype, detail.value.name);
    toast.value = `${detail.value.title || detail.value.name} submitted`;
    detail.value = await getDoc(props.doctype, detail.value.name, props.fields);
    softRefresh();
  } catch (e) {
    actErr.value = true;
    actNote.value = e.message || "Could not submit.";
  } finally {
    acting.value = "";
  }
}

// One tap does the action — no confirmation step. (Cancel is reversible
// by amending; Delete only ever applies to drafts and cancelled docs.)
function doCancel() {
  runCancel();
}

async function runCancel() {
  acting.value = "cancel";
  actNote.value = ""; actErr.value = false;
  try {
    await cancelDoc(props.doctype, detail.value.name);
    toast.value = `${detail.value.name} cancelled`;
    detail.value = await getDoc(props.doctype, detail.value.name, props.fields);
    softRefresh();
  } catch (e) {
    actErr.value = true;
    actNote.value = e.message || "Could not cancel.";
  } finally {
    acting.value = "";
  }
}

function doDelete() {
  runDelete();
}

async function runDelete() {
  acting.value = "delete";
  actNote.value = ""; actErr.value = false;
  try {
    const name = detail.value.name;
    await deleteDoc(props.doctype, name);
    detail.value = null;               // close the sheet — the doc is gone
    toast.value = `${name} deleted`;
    softRefresh();
  } catch (e) {
    actErr.value = true;
    actNote.value = e.message || "Could not delete.";
  } finally {
    acting.value = "";
  }
}

async function doAmend() {
  acting.value = "amend";
  actNote.value = ""; actErr.value = false;
  try {
    const r = await amendDoc(props.doctype, detail.value.name);
    toast.value = `Amended as ${r.name}`;
    softRefresh();
    open({ name: r.name, title: r.name });
  } catch (e) {
    actErr.value = true;
    actNote.value = e.message || "Could not amend.";
  } finally {
    acting.value = "";
  }
}

async function doEwaybill() {
  acting.value = "ewb";
  actNote.value = ""; actErr.value = false;
  try {
    const r = await generateEwaybill(detail.value.name);
    actNote.value = r.ewaybill ? `e-Way Bill ${r.ewaybill} generated` : "e-Way Bill generated";
    detail.value = await getDoc(props.doctype, detail.value.name, props.fields);
  } catch (e) {
    actErr.value = true;
    actNote.value = e.message || "Could not generate e-Way Bill.";
  } finally {
    acting.value = "";
  }
}

async function doEinvoice() {
  acting.value = "einv";
  actNote.value = ""; actErr.value = false;
  try {
    const r = await generateEinvoice(detail.value.name);
    actNote.value = r.irn ? `e-Invoice generated — IRN ${r.irn}` : "e-Invoice generated";
    detail.value = await getDoc(props.doctype, detail.value.name, props.fields);
  } catch (e) {
    actErr.value = true;
    actNote.value = e.message || "Could not generate e-Invoice.";
  } finally {
    acting.value = "";
  }
}

// ── record payment ──
const payOpen = ref(false);
const payAmount = ref("");
const payDate = ref("");
const payMode = ref("");
const payRef = ref("");
const payModes = ref([]);

async function togglePay() {
  payOpen.value = !payOpen.value;
  if (payOpen.value && !payModes.value.length) {
    try {
      const m = await getPaymentMeta(props.doctype, detail.value.name);
      payAmount.value = m.outstanding || "";
      payDate.value = m.today || "";
      payModes.value = m.modes || [];
    } catch { /* form still usable with manual values */ }
  }
}

async function doPay() {
  acting.value = "pay";
  actNote.value = ""; actErr.value = false;
  try {
    const r = await recordPayment(props.doctype, detail.value.name, {
      amount: payAmount.value, posting_date: payDate.value,
      mode_of_payment: payMode.value, reference_no: payRef.value,
    });
    payOpen.value = false;
    toast.value = `Payment ${r.name} recorded`;
    detail.value = await getDoc(props.doctype, detail.value.name, props.fields);
    softRefresh();
  } catch (e) {
    actErr.value = true;
    actNote.value = e.message || "Could not record payment.";
  } finally {
    acting.value = "";
  }
}

// ── print / pdf / email actions ──
const emailOpen = ref(false);
const emailTo = ref("");
const emailMsg = ref("");
const emailSending = ref(false);
const emailNote = ref("");
const emailErr = ref(false);

function docUrlParams() {
  return `doctype=${encodeURIComponent(props.doctype)}&name=${encodeURIComponent(detail.value?.name || "")}`;
}
function openUrl(url) {
  // window.open is silently blocked in some embedded/in-app browsers —
  // fall back to navigating this tab (Back returns to the app).
  const w = window.open(url, "_blank");
  if (!w) window.location.href = url;
}
function openPrint() {
  openUrl(`/printview?${docUrlParams()}&trigger_print=1`);
}
function openPdf() {
  openUrl(`/api/method/frappe.utils.print_format.download_pdf?${docUrlParams()}`);
}
async function doEmail() {
  emailSending.value = true;
  emailNote.value = "";
  emailErr.value = false;
  try {
    await emailDoc(props.doctype, detail.value.name, emailTo.value, emailMsg.value);
    emailNote.value = `Sent to ${emailTo.value}`;
    emailTo.value = ""; emailMsg.value = "";
  } catch (e) {
    emailErr.value = true;
    emailNote.value = e.message || "Could not send.";
  } finally {
    emailSending.value = false;
  }
}

// Silent background refresh — same data as reload() but without the
// skeleton flash. Used when the user navigates back to this list or the
// PWA is resumed, so the screen is always current without feeling laggy.
let softBusy = false;
async function softRefresh() {
  if (softBusy || loading.value) return;
  softBusy = true;
  try {
    const [v, l] = await Promise.all([
      getView(props.doctype, props.label, props.fields, props.filters),
      getList(props.doctype, { search: search.value, start: 0, page_length: 20,
                               fields: props.fields, filters: props.filters }),
    ]);
    Object.assign(view, v);
    rows.value = l.rows;
    hasMore.value = l.has_more;
    start = l.rows.length;
    error.value = null;
  } catch { /* keep what's on screen */ } finally {
    softBusy = false;
  }
}

function onVisibility() {
  if (document.visibilityState === "visible") softRefresh();
}

// expose reload for parent pull-to-refresh, softRefresh for view re-entry
defineExpose({ reload, softRefresh });

onMounted(() => {
  reload();
  document.addEventListener("visibilitychange", onVisibility);
});
onUnmounted(() => document.removeEventListener("visibilitychange", onVisibility));
</script>

<style scoped>
.dl-root { padding: 12px 14px 24px; }

/* number cards */
.dl-cards {
  display: flex; gap: 10px; overflow-x: auto;
  padding: 4px 2px 8px; scrollbar-width: none;
}
.dl-cards::-webkit-scrollbar { display: none; }
.dl-card {
  flex: 1 0 auto; min-width: 92px;
  background: linear-gradient(160deg, #fff 30%, #f3f5ff);
  border: 1px solid #e0e5f5; border-radius: 16px;
  padding: 14px 16px; text-align: center;
  box-shadow: 0 1px 8px rgba(15,23,42,.04);
}
.dl-card-val { font-size: 24px; font-weight: 900; letter-spacing: -1px; line-height: 1; }
.dl-card-lbl { font-size: 11px; font-weight: 700; color: #94a3b8; margin-top: 5px;
  text-transform: uppercase; letter-spacing: .4px; white-space: nowrap; }

.dl-search { padding: 4px 0 6px; --border-radius: 14px; --box-shadow: none;
  --background: #fff; }

/* detail child tables (items, taxes, …) */
.dl-tbl-sec { margin-top: 18px; }
.dl-tbl-title { font-size: 13px; font-weight: 800; color: #334155; margin-bottom: 8px; }
.dl-tbl-count {
  display: inline-block; min-width: 20px; padding: 1px 7px; margin-left: 4px;
  background: #eef2ff; color: #4338ca; border-radius: 10px;
  font-size: 11px; font-weight: 800; text-align: center;
}
.dl-tbl-scroll {
  overflow-x: auto; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff;
  -webkit-overflow-scrolling: touch;
}
.dl-t { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12px; }
.dl-t th {
  background: #eef2ff; color: #4338ca; text-align: left; font-weight: 800;
  padding: 8px 10px; white-space: nowrap; border-bottom: 1px solid #c7d2fe;
}
.dl-t td {
  padding: 7px 10px; border-bottom: 1px solid #f1f5f9; color: #1e293b;
  white-space: nowrap; background: #fff;
}
.dl-t tbody tr:nth-child(even) td { background: #f8fafc; }
.dl-t tbody tr:last-child td { border-bottom: none; }
.dl-t th.num, .dl-t td.num { text-align: right; font-variant-numeric: tabular-nums; }

/* record card */
.dl-item {
  background: #fff; border: 1px solid #e8edf3; border-radius: 16px;
  padding: 14px 16px; margin-bottom: 10px; cursor: pointer;
  transition: transform .1s, border-color .15s;
}
.dl-item:active { transform: scale(.985); border-color: var(--ion-color-primary); }
.dl-item-top { display: flex; align-items: flex-start; gap: 10px; justify-content: space-between; }
.dl-item-title { font-size: 15px; font-weight: 800; color: #1e293b; line-height: 1.3;
  word-break: break-word; }

.dl-meta { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px 14px; }
.dl-meta-item { font-size: 12.5px; color: #475569; }
.dl-meta-lbl { color: #94a3b8; font-weight: 600; }

.dl-item-bot { margin-top: 10px; display: flex; align-items: center; justify-content: space-between; }
.dl-amount { font-size: 14.5px; font-weight: 800; color: #0f172a; }
.dl-date { font-size: 11.5px; color: #94a3b8; font-weight: 600; margin-left: auto; }

/* status badge */
.dl-badge { font-size: 11px; font-weight: 800; padding: 3px 10px; border-radius: 999px;
  white-space: nowrap; flex-shrink: 0; }
.dl-badge.ok      { background: #dcfce7; color: #15803d; }
.dl-badge.warn    { background: #fef3c7; color: #b45309; }
.dl-badge.bad     { background: #fee2e2; color: #dc2626; }
.dl-badge.neutral { background: #f1f5f9; color: #64748b; }

/* states */
.dl-empty { text-align: center; padding: 60px 24px; color: #64748b; }
.dl-empty-ico { font-size: 40px; margin-bottom: 8px; }
.dl-empty h3 { margin: 0 0 4px; font-size: 16px; color: #334155; font-weight: 800; }
.dl-empty p { margin: 0 0 12px; font-size: 13px; }

/* detail sheet */
.dl-detail-title { font-size: 15px; font-weight: 800; }
.dl-detail-head { display: flex; align-items: center; justify-content: space-between;
  gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
/* MUST wrap: on phone widths the extra buttons (Cancel/Delete/Payment/…)
   were overflowing and getting clipped — "where is the cancel option" */
.dl-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-left: auto;
  justify-content: flex-end; }
.dl-act {
  border: 1px solid #e2e8f0; background: #fff; color: #334155;
  font-size: 12.5px; font-weight: 700; border-radius: 999px; padding: 7px 13px;
  cursor: pointer; -webkit-appearance: none; white-space: nowrap;
}
.dl-act:active { transform: scale(.95); }
.dl-act:disabled { opacity: .55; }
.dl-act.on { border-color: var(--ion-color-primary); color: var(--ion-color-primary);
  background: #eef2ff; }
.dl-act.primary { background: #4f46e5; border-color: #4f46e5;
  color: #fff; font-weight: 800; box-shadow: 0 2px 8px rgba(79,70,229,.35); }
.dl-act.danger { border-color: #fecaca; color: #dc2626; background: #fef2f2; }


.dl-email { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px;
  padding: 12px; margin-bottom: 14px; }
.dl-email-input {
  width: 100%; border: 1px solid #d8dee9; border-radius: 10px; padding: 10px 12px;
  font-size: 14px; background: #fff; color: #1e293b; margin-bottom: 8px;
  font-family: inherit; -webkit-appearance: none;
}
.dl-email-input:focus { outline: none; border-color: var(--ion-color-primary); }
.dl-email-send {
  width: 100%; height: 42px; border: none; border-radius: 10px;
  background: var(--ion-color-primary); color: #fff; font-size: 14px; font-weight: 700;
  cursor: pointer; -webkit-appearance: none;
}
.dl-email-send:disabled { opacity: .5; }
.dl-email-note { margin-top: 8px; font-size: 12.5px; color: #15803d; text-align: center; }
.dl-email-note.err { color: #dc2626; }
.dl-mini-lbl { display: block; font-size: 11.5px; font-weight: 700; color: #64748b;
  margin: 2px 2px 4px; }

.dl-fieldgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 16px; }
.dl-field { padding: 10px 0; border-bottom: 1px solid #f1f5f9; min-width: 0; }
.dl-field.wide { grid-column: 1 / -1; }
.dl-field-lbl { font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase;
  letter-spacing: .3px; }
.dl-field-val { font-size: 14px; color: #1e293b; margin-top: 3px; word-break: break-word; }
.dl-field.money .dl-field-val { font-weight: 800; font-variant-numeric: tabular-nums; }

/* floating create button */
.dl-fab {
  position: fixed; right: 18px; bottom: 22px; z-index: 50;
  width: 56px; height: 56px; border-radius: 18px; border: none;
  background: var(--ion-color-primary); color: #fff;
  font-size: 30px; font-weight: 400; line-height: 1; cursor: pointer;
  box-shadow: 0 8px 22px rgba(99,102,241,.45);
  display: flex; align-items: center; justify-content: center;
  transition: transform .12s;
}
.dl-fab:active { transform: scale(.92); }
</style>
