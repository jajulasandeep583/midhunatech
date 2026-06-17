<!-- Copyright (c) 2026, Midhunatech and Contributors — GPL-3.0 -->
<!-- In-app notification-rules editor (System Manager): event-driven alerts and
     scheduled reports — configured on the phone, no desk. Backed by Frappe's
     native Notification + Auto Email Report doctypes. -->
<template>
  <ion-page>
    <ion-header :translucent="true">
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button default-href="/midhunatech/settings" text="Back" />
        </ion-buttons>
        <ion-title>Notifications</ion-title>
      </ion-toolbar>
      <ion-toolbar>
        <ion-segment v-model="tab">
          <ion-segment-button value="alerts"><ion-label>Alerts</ion-label></ion-segment-button>
          <ion-segment-button value="reports"><ion-label>Scheduled Reports</ion-label></ion-segment-button>
        </ion-segment>
      </ion-toolbar>
    </ion-header>

    <ion-content :fullscreen="true">
      <div v-if="loadError" class="empty-state" style="padding-top:70px;" role="alert">
        <div class="empty-icon" aria-hidden="true">⚠</div>
        <h3>Could not load</h3>
        <p>{{ loadError }}</p>
        <ion-button fill="outline" size="small" @click="load">Try again</ion-button>
      </div>

      <div v-else-if="!loaded" class="empty-state" style="padding-top:80px;">
        <ion-spinner name="crescent" color="primary" style="font-size:36px;" />
      </div>

      <!-- ══════════ ALERTS ══════════ -->
      <template v-else-if="tab === 'alerts'">
        <div class="st-hint">
          Send an in-app + push (and optional email) when something happens — e.g.
          a Sales Order is submitted, notify the approver.
        </div>

        <div class="st-mods">
          <div v-for="n in notifs" :key="n.name" class="st-mod">
            <div class="st-mod-head">
              <span class="st-mod-icon">{{ n.send_system_notification ? '🔔' : '✉️' }}</span>
              <div class="st-mod-info" role="button" tabindex="0" @click="editNotif(n.name)" @keyup.enter="editNotif(n.name)">
                <div class="st-mod-label">{{ n.subject || '(untitled)' }}</div>
                <div class="st-mod-sub">{{ n.document_type }} · on {{ n.event }}</div>
              </div>
              <label class="sw">
                <input type="checkbox" :checked="!!n.enabled" @change="onToggleNotif(n)" />
                <span class="sw-track"></span>
              </label>
            </div>
          </div>
          <div v-if="!notifs.length" class="st-hint" style="text-align:center;">No alerts yet.</div>
        </div>

        <button class="st-add" @click="newNotif">＋ New alert</button>
      </template>

      <!-- ══════════ REPORTS ══════════ -->
      <template v-else>
        <div class="st-hint">
          Email a report automatically on a schedule (daily / weekly / monthly).
        </div>

        <div class="st-mods">
          <div v-for="a in reports" :key="a.name" class="st-mod">
            <div class="st-mod-head">
              <span class="st-mod-icon">📊</span>
              <div class="st-mod-info" role="button" tabindex="0" @click="editReport(a.name)" @keyup.enter="editReport(a.name)">
                <div class="st-mod-label">{{ a.report }}</div>
                <div class="st-mod-sub">{{ a.frequency }} · {{ a.format }} → {{ a.email_to }}</div>
              </div>
              <label class="sw">
                <input type="checkbox" :checked="!!a.enabled" @change="onToggleReport(a)" />
                <span class="sw-track"></span>
              </label>
            </div>
          </div>
          <div v-if="!reports.length" class="st-hint" style="text-align:center;">No scheduled reports yet.</div>
        </div>

        <button class="st-add" @click="newReport">＋ New scheduled report</button>
      </template>

      <div style="height:40px;" />
      <ion-toast :is-open="!!toast" :message="toast" :duration="2000" position="top" color="success" @didDismiss="toast = ''" />
    </ion-content>

    <!-- ══════════ ALERT EDITOR ══════════ -->
    <ion-modal :is-open="!!editing" @didDismiss="editing = null">
      <ion-header><ion-toolbar>
        <ion-buttons slot="start"><ion-button @click="editing = null">Cancel</ion-button></ion-buttons>
        <ion-title>{{ editing && editing.name ? 'Edit alert' : 'New alert' }}</ion-title>
        <ion-buttons slot="end"><ion-button strong :disabled="saving" @click="saveNotif">
          <span v-if="saving" class="mt-spinner" /><span v-else>Save</span>
        </ion-button></ion-buttons>
      </ion-toolbar></ion-header>
      <ion-content v-if="editing" class="ion-padding">
        <div class="st-field">
          <label>Title</label>
          <input v-model="editing.subject" type="text" placeholder="Sales Order submitted" />
        </div>
        <div class="st-field">
          <label>Document type</label>
          <input v-model="editing.document_type" type="text" list="dt-list"
                 placeholder="Sales Order" @change="onDoctypeChange" />
          <datalist id="dt-list">
            <option v-for="d in meta.doctypes" :key="d" :value="d" />
          </datalist>
        </div>
        <div class="st-row">
          <div class="st-field">
            <label>When (trigger)</label>
            <select v-model="editing.event">
              <option v-for="e in meta.events" :key="e" :value="e">{{ eventLabel(e) }}</option>
            </select>
          </div>
          <div v-if="editing.event === 'Value Change'" class="st-field">
            <label>Field that changes</label>
            <select v-model="editing.value_changed">
              <option v-for="f in dtFields.all" :key="f.value" :value="f.value">{{ f.label }}</option>
            </select>
          </div>
          <div v-if="editing.event === 'Days Before' || editing.event === 'Days After'" class="st-field">
            <label>Days</label>
            <input v-model.number="editing.days_in_advance" type="number" />
          </div>
        </div>

        <div class="section-title" style="margin-top:6px;">Send to</div>
        <div v-for="(r, i) in editing.recipients" :key="i" class="st-row" style="align-items:flex-end;">
          <div class="st-field" style="max-width:110px;">
            <label>By</label>
            <select v-model="r.type">
              <option value="field">Doc field</option>
              <option value="role">Role</option>
            </select>
          </div>
          <div class="st-field">
            <label>{{ r.type === 'role' ? 'Role' : 'Field' }}</label>
            <select v-if="r.type === 'role'" v-model="r.value">
              <option v-for="ro in meta.roles" :key="ro" :value="ro">{{ ro }}</option>
            </select>
            <select v-else v-model="r.value">
              <option v-for="f in dtFields.recipient_fields" :key="f.value" :value="f.value">{{ f.label }}</option>
            </select>
          </div>
          <button class="st-ib danger" style="margin-bottom:10px;" @click="editing.recipients.splice(i,1)">✕</button>
        </div>
        <button class="st-add" style="margin:4px 0 10px;height:38px;font-size:13px;" @click="addRecipient">＋ Add recipient</button>

        <div class="section-title" style="margin-top:6px;">Channel</div>
        <div class="st-field">
          <select v-model="editing.channel">
            <option value="System Notification">In-app + push only</option>
            <option value="Email">Email + in-app + push</option>
          </select>
        </div>

        <div class="st-field">
          <label>Message (Markdown · Jinja)</label>
          <textarea v-model="editing.message" rows="4"></textarea>
        </div>
        <div class="st-field">
          <label>Condition (optional Python, e.g. doc.grand_total &gt; 100000)</label>
          <input v-model="editing.condition" type="text" placeholder="leave blank for always" />
        </div>

        <button v-if="editing.name" class="st-del" @click="removeNotif">Delete this alert</button>
        <div v-if="editError" class="st-err" role="alert">{{ editError }}</div>
        <div style="height:30px;" />
      </ion-content>
    </ion-modal>

    <!-- ══════════ REPORT EDITOR ══════════ -->
    <ion-modal :is-open="!!editingReport" @didDismiss="editingReport = null">
      <ion-header><ion-toolbar>
        <ion-buttons slot="start"><ion-button @click="editingReport = null">Cancel</ion-button></ion-buttons>
        <ion-title>{{ editingReport && editingReport.name ? 'Edit report' : 'New report' }}</ion-title>
        <ion-buttons slot="end"><ion-button strong :disabled="saving" @click="saveReport">
          <span v-if="saving" class="mt-spinner" /><span v-else>Save</span>
        </ion-button></ion-buttons>
      </ion-toolbar></ion-header>
      <ion-content v-if="editingReport" class="ion-padding">
        <div class="st-field">
          <label>Report</label>
          <input v-model="editingReport.report" type="text" list="rep-list" placeholder="Sales Register" />
          <datalist id="rep-list">
            <option v-for="r in reportNames" :key="r" :value="r" />
          </datalist>
        </div>
        <div class="st-row">
          <div class="st-field">
            <label>Frequency</label>
            <select v-model="editingReport.frequency">
              <option v-for="f in meta.frequencies" :key="f" :value="f">{{ f }}</option>
            </select>
          </div>
          <div v-if="editingReport.frequency === 'Weekly'" class="st-field">
            <label>Day</label>
            <select v-model="editingReport.day_of_week">
              <option v-for="d in days" :key="d" :value="d">{{ d }}</option>
            </select>
          </div>
          <div class="st-field" style="max-width:110px;">
            <label>Format</label>
            <select v-model="editingReport.format">
              <option v-for="f in meta.formats" :key="f" :value="f">{{ f }}</option>
            </select>
          </div>
        </div>
        <div class="st-field">
          <label>Email to (comma separated)</label>
          <input v-model="editingReport.email_to" type="text" placeholder="boss@company.com" />
        </div>
        <div class="st-row">
          <div class="st-field" style="max-width:130px;">
            <label>Max rows</label>
            <input v-model.number="editingReport.no_of_rows" type="number" />
          </div>
          <label class="st-check" style="flex:1;">
            <input v-model="editingReport.send_if_data" type="checkbox" :true-value="1" :false-value="0" />
            Only send if there is data
          </label>
        </div>
        <div class="st-field">
          <label>Filters (JSON, optional)</label>
          <input v-model="editingReport.filters" type="text" placeholder='{"company": "Your Company"}' />
        </div>

        <button v-if="editingReport.name" class="st-del" @click="removeReport">Delete this report</button>
        <div v-if="editError" class="st-err" role="alert">{{ editError }}</div>
        <div style="height:30px;" />
      </ion-content>
    </ion-modal>
  </ion-page>
</template>

<script setup>
import { onMounted, ref } from "vue";
import {
  IonPage, IonHeader, IonToolbar, IonTitle, IonContent, IonButtons, IonBackButton,
  IonButton, IonSpinner, IonToast, IonSegment, IonSegmentButton, IonLabel, IonModal,
} from "@ionic/vue";
import * as api from "@/data/notifyAdmin.js";

const tab = ref("alerts");
const loaded = ref(false);
const loadError = ref(null);
const saving = ref(false);
const toast = ref("");
const editError = ref("");

const meta = ref({ doctypes: [], events: [], channels: [], frequencies: [], formats: [], roles: [] });
const notifs = ref([]);
const reports = ref([]);
const reportNames = ref([]);
const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const editing = ref(null);          // alert being edited
const editingReport = ref(null);    // scheduled report being edited
const dtFields = ref({ all: [], recipient_fields: [{ value: "owner", label: "Owner (creator)" }] });

onMounted(load);

async function load() {
  loadError.value = null;
  try {
    const [m, n, r, reps] = await Promise.all([
      api.getMeta(), api.listNotifications(), api.listAutoEmailReports(), api.getReports(),
    ]);
    meta.value = m;
    notifs.value = n;
    reports.value = r;
    reportNames.value = reps.map((x) => x.name);
    loaded.value = true;
  } catch (e) {
    loadError.value = e.message;
  }
}

function eventLabel(e) {
  return {
    "New": "Created", "Save": "Saved", "Submit": "Submitted", "Cancel": "Cancelled",
    "Value Change": "A field changes", "Days After": "Days after a date",
    "Days Before": "Days before a date",
  }[e] || e;
}

// ── Alerts ──
async function loadDtFields(doctype) {
  if (!doctype) return;
  try {
    dtFields.value = await api.getDoctypeFields(doctype);
  } catch { /* non-fatal */ }
}
function onDoctypeChange() {
  loadDtFields(editing.value.document_type);
}
function addRecipient() {
  editing.value.recipients.push({ type: "field", value: "owner" });
}
function newNotif() {
  dtFields.value = { all: [], recipient_fields: [{ value: "owner", label: "Owner (creator)" }] };
  editError.value = "";
  editing.value = {
    name: null, subject: "", document_type: "", event: "Submit", value_changed: "workflow_state",
    channel: "System Notification", message: "", condition: "", days_in_advance: 1,
    recipients: [{ type: "field", value: "owner" }],
  };
}
async function editNotif(name) {
  editError.value = "";
  try {
    const d = await api.getNotification(name);
    if (!d.recipients.length) d.recipients = [{ type: "field", value: "owner" }];
    editing.value = d;
    await loadDtFields(d.document_type);
  } catch (e) { toast.value = e.message; }
}
async function saveNotif() {
  if (!editing.value.document_type) { editError.value = "Pick a document type"; return; }
  saving.value = true; editError.value = "";
  try {
    await api.saveNotification(editing.value);
    editing.value = null;
    await load();
    toast.value = "Saved ✓";
  } catch (e) { editError.value = e.message; }
  finally { saving.value = false; }
}
async function removeNotif() {
  if (!editing.value.name) return;
  saving.value = true;
  try {
    await api.deleteNotification(editing.value.name);
    editing.value = null;
    await load();
    toast.value = "Deleted";
  } catch (e) { editError.value = e.message; }
  finally { saving.value = false; }
}
async function onToggleNotif(n) {
  n.enabled = n.enabled ? 0 : 1;
  try { await api.toggleNotification(n.name, n.enabled); }
  catch (e) { n.enabled = n.enabled ? 0 : 1; toast.value = e.message; }
}

// ── Reports ──
function newReport() {
  editError.value = "";
  editingReport.value = {
    name: null, report: "", frequency: "Weekly", day_of_week: "Monday", format: "HTML",
    email_to: "", no_of_rows: 100, send_if_data: 1, filters: "",
  };
}
async function editReport(name) {
  editError.value = "";
  try { editingReport.value = await api.getAutoEmailReport(name); }
  catch (e) { toast.value = e.message; }
}
async function saveReport() {
  if (!editingReport.value.report) { editError.value = "Pick a report"; return; }
  saving.value = true; editError.value = "";
  try {
    await api.saveAutoEmailReport(editingReport.value);
    editingReport.value = null;
    await load();
    toast.value = "Saved ✓";
  } catch (e) { editError.value = e.message; }
  finally { saving.value = false; }
}
async function removeReport() {
  if (!editingReport.value.name) return;
  saving.value = true;
  try {
    await api.deleteAutoEmailReport(editingReport.value.name);
    editingReport.value = null;
    await load();
    toast.value = "Deleted";
  } catch (e) { editError.value = e.message; }
  finally { saving.value = false; }
}
async function onToggleReport(a) {
  a.enabled = a.enabled ? 0 : 1;
  try { await api.toggleAutoEmailReport(a.name, a.enabled); }
  catch (e) { a.enabled = a.enabled ? 0 : 1; toast.value = e.message; }
}
</script>

<style scoped>
.section-title { font-size: 12px; font-weight: 800; color: #64748b; text-transform: uppercase; letter-spacing: .4px; margin: 14px 16px 6px; }
.st-hint { font-size: 12.5px; color: #94a3b8; margin: 12px 18px; }
.st-mods { display: flex; flex-direction: column; gap: 9px; padding: 0 16px; }
.st-mod { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; overflow: hidden; }
.st-mod-head { display: flex; align-items: center; gap: 11px; padding: 11px 12px; }
.st-mod-icon { font-size: 20px; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; background: #f1f5f9; border-radius: 10px; flex-shrink: 0; }
.st-mod-info { flex: 1; min-width: 0; cursor: pointer; }
.st-mod-label { font-size: 14px; font-weight: 700; color: #1e293b; }
.st-mod-sub { font-size: 11.5px; color: #94a3b8; margin-top: 1px; }

.st-field { margin-bottom: 12px; min-width: 0; }
.st-field label { display: block; font-size: 11px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: .3px; margin-bottom: 4px; }
.st-field input[type="text"], .st-field input[type="number"], .st-field select, .st-field textarea {
  width: 100%; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 11px;
  font-size: 14px; background: #f8fafc; color: #1e293b; font-family: inherit;
}
.st-field input[type="text"], .st-field input[type="number"], .st-field select { height: 42px; padding: 0 11px; }
.st-row { display: flex; gap: 10px; }
.st-row .st-field { flex: 1; }
.st-check { display: flex; align-items: center; gap: 9px; font-size: 13.5px; font-weight: 600; color: #334155; padding: 7px 0; }
.st-check input { width: 18px; height: 18px; }

.st-add { margin: 8px 16px 6px; width: calc(100% - 32px); height: 46px; border: 2px dashed #cbd5e1; background: transparent; border-radius: 14px; font-size: 14px; font-weight: 700; color: #64748b; cursor: pointer; }
.st-del { margin: 18px 0 6px; width: 100%; height: 44px; border: 1px solid #fecaca; background: #fef2f2; color: #dc2626; border-radius: 12px; font-size: 14px; font-weight: 700; cursor: pointer; }
.st-ib { width: 34px; height: 38px; border: 1px solid #e2e8f0; background: #f8fafc; border-radius: 8px; font-size: 14px; color: #475569; cursor: pointer; }
.st-ib.danger { color: #ef4444; }
.st-err { margin: 12px 0; background: #fef2f2; color: #dc2626; font-size: 13px; border-radius: 10px; padding: 10px 12px; }

/* toggle switch */
.sw { position: relative; display: inline-flex; flex-shrink: 0; cursor: pointer; }
.sw input { position: absolute; opacity: 0; width: 0; height: 0; }
.sw-track { width: 44px; height: 26px; border-radius: 999px; background: #cbd5e1; transition: background .2s; position: relative; }
.sw-track::after { content: ""; position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: #fff; transition: transform .2s; box-shadow: 0 1px 3px rgba(0,0,0,.25); }
.sw input:checked + .sw-track { background: #16a34a; }
.sw input:checked + .sw-track::after { transform: translateX(18px); }
</style>
