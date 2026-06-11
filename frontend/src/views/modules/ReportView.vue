<!-- Copyright (c) 2026, Midhunatech and Contributors — GPL-3.0 -->
<!-- Native mobile renderer for any Frappe report (Report Builder / Query /
     Script): summary KPI cards + chart + table with tree indentation.
     Optional default filters come from the module row (JSON). -->
<template>
  <div class="rp-wrap">
    <div v-if="loading" class="empty-state" style="padding-top:60px;">
      <ion-spinner name="crescent" color="primary" style="font-size:36px;" />
      <p style="margin-top:10px;">Running {{ report }}…</p>
    </div>

    <div v-else-if="error" class="empty-state" style="padding-top:60px;" role="alert">
      <div class="empty-icon" aria-hidden="true">⚠</div>
      <h3>Report failed</h3>
      <p>{{ error }}</p>
      <ion-button fill="outline" size="small" @click="run()">Try again</ion-button>
    </div>

    <template v-else>
      <!-- ── filter bar (dates + report-specific filters) ── -->
      <div v-if="hasDates || filterMeta.length" class="rp-filters">
        <div v-if="hasDates" class="rp-f-row">
          <label class="rp-fl">
            <span>From</span>
            <input type="date" v-model="fromDate" />
          </label>
          <label class="rp-fl">
            <span>To</span>
            <input type="date" v-model="toDate" />
          </label>
        </div>

        <div v-for="fm in filterMeta" :key="fm.fieldname" class="rp-f-row">
          <label class="rp-fl" style="flex:1;">
            <span>{{ fm.label }}</span>
            <!-- Select -->
            <select v-if="fm.fieldtype === 'Select'" v-model="extra[fm.fieldname]">
              <option value="">All</option>
              <option v-for="o in selectOptions(fm)" :key="o" :value="o">{{ o }}</option>
            </select>
            <!-- Link autocomplete -->
            <div v-else class="rp-link">
              <input
                type="text"
                :value="extra[fm.fieldname] || ''"
                :placeholder="`All — search ${fm.label.toLowerCase()}…`"
                @input="onLink(fm, $event.target.value)"
                @focus="onLink(fm, extra[fm.fieldname] || '')"
                @blur="closeLinkSoon"
              />
              <button v-if="extra[fm.fieldname]" class="rp-clear" aria-label="Clear"
                      @mousedown.prevent="clearLink(fm)">✕</button>
              <ul v-if="linkFor === fm.fieldname && linkResults.length" class="rp-link-list">
                <li v-for="o in linkResults" :key="o.value" @mousedown.prevent="pickLink(fm, o)">
                  <b>{{ o.value }}</b><span v-if="o.label !== o.value"> — {{ o.label }}</span>
                </li>
              </ul>
            </div>
          </label>
        </div>

        <button class="rp-apply" :disabled="loading" @click="apply">Apply filters</button>
      </div>

      <!-- ── summary KPI cards ── -->
      <div v-if="summary.length" class="rp-summary">
        <div v-for="(s, i) in summary" :key="i" class="rp-sum-card" :class="`ind-${s.indicator || 'Blue'}`">
          <div class="rp-sum-value">{{ fmtSummary(s) }}</div>
          <div class="rp-sum-label">{{ s.label }}</div>
        </div>
      </div>

      <!-- ── chart ── -->
      <div v-if="chart" class="rp-chart-card">
        <div ref="chartEl"></div>
      </div>

      <div v-if="message" class="rp-message">{{ message }}</div>

      <!-- ── table ── -->
      <div v-if="!rows.length" class="empty-state" style="padding-top:40px;">
        <div class="empty-icon" aria-hidden="true">📑</div>
        <h3>No data</h3>
        <p>The report returned no rows.</p>
      </div>
      <template v-else>
        <div class="rp-meta">{{ rows.length }} row{{ rows.length !== 1 ? "s" : "" }}{{ rows.length >= 500 ? " (first 500)" : "" }}</div>
        <div class="rp-scroll">
          <table class="rp-t">
            <thead>
              <tr>
                <th v-for="(c, ci) in columns" :key="c.fieldname"
                    :class="{ num: isNum(c), first: ci === 0 }">{{ c.label }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(r, i) in rows" :key="i" :class="{ bold: isBold(r) }">
                <td v-for="(c, ci) in columns" :key="c.fieldname"
                    :class="{ num: isNum(c), first: ci === 0 }"
                    :style="ci === 0 && hasTree ? { paddingLeft: (11 + (Number(r.indent) || 0) * 14) + 'px' } : null">
                  {{ display(r[c.fieldname], c) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { IonButton, IonSpinner } from "@ionic/vue";
import { apiFetch } from "@/data/session.js";
import { searchLink } from "@/data/docdata.js";

const props = defineProps({
  report:  { type: String, required: true },
  filters: { type: [String, Object], default: "" },
});

const loading = ref(true);
const error = ref(null);
const columns = ref([]);
const rows = ref([]);
const summary = ref([]);
const chart = ref(null);
const message = ref(null);
const chartEl = ref(null);
const fromDate = ref("");
const toDate = ref("");
const hasDates = ref(false);
const filterMeta = ref([]);
const extra = reactive({});

// link-filter autocomplete state
const linkFor = ref(null);
const linkResults = ref([]);
let linkTimer = null;

function selectOptions(fm) {
  return (fm.options || "").split("\n").map((s) => s.trim()).filter(Boolean);
}
function onLink(fm, txt) {
  extra[fm.fieldname] = txt;
  linkFor.value = fm.fieldname;
  clearTimeout(linkTimer);
  linkTimer = setTimeout(async () => {
    try { linkResults.value = await searchLink(fm.options, txt); }
    catch { linkResults.value = []; }
  }, 250);
}
function pickLink(fm, o) {
  extra[fm.fieldname] = o.value;
  linkResults.value = [];
  linkFor.value = null;
  apply();
}
function clearLink(fm) {
  extra[fm.fieldname] = "";
  linkResults.value = [];
  linkFor.value = null;
  apply();
}
function closeLinkSoon() {
  setTimeout(() => { linkFor.value = null; linkResults.value = []; }, 200);
}

function apply() {
  const f = { ...extra };
  if (hasDates.value) { f.from_date = fromDate.value; f.to_date = toDate.value; }
  run(f);
}

const NUM_TYPES = new Set(["Currency", "Float", "Int", "Percent", "Duration"]);
const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const inr0 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

const hasTree = computed(() => rows.value.some(r => Number(r.indent) > 0));

onMounted(() => run());

async function run(extra = null) {
  loading.value = true;
  error.value = null;
  try {
    let base = props.filters || {};
    if (typeof base === "string") { try { base = JSON.parse(base || "{}"); } catch { base = {}; } }
    const filters = { ...base, ...(extra || {}) };
    const r = await apiFetch("/api/method/midhunatech.api.reports.run", {
      method: "POST",
      body: JSON.stringify({ report_name: props.report, filters }),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      throw new Error(e.exception ? e.exception.split(":").pop() : `HTTP ${r.status}`);
    }
    const d = (await r.json()).message;
    columns.value = d.columns || [];
    rows.value = d.rows || [];
    summary.value = d.summary || [];
    chart.value = d.chart || null;
    message.value = d.message || null;
    filterMeta.value = d.filter_meta || [];

    const af = d.applied_filters || {};
    if (af.from_date && af.to_date) {
      hasDates.value = true;
      fromDate.value = String(af.from_date).slice(0, 10);
      toDate.value = String(af.to_date).slice(0, 10);
    }
    // flip loading off BEFORE drawing: the chart container only exists
    // once the content branch is rendered
    loading.value = false;
    await nextTick();
    renderChart();
  } catch (e) {
    error.value = e.message || "Could not run report";
  } finally {
    loading.value = false;
  }
}

let chartInst = null;
async function renderChart() {
  if (!chart.value || !chartEl.value) return;
  try {
    const { Chart } = await import("frappe-charts");
    chartEl.value.innerHTML = "";
    chartInst = new Chart(chartEl.value, {
      data: chart.value.data,
      type: ["bar", "line", "percentage", "pie", "donut", "axis-mixed"].includes(chart.value.type)
        ? chart.value.type : "bar",
      height: 230,
      colors: chart.value.colors?.length ? chart.value.colors
        : ["#6366f1", "#22c55e", "#f59e0b", "#ec4899", "#0ea5e9"],
      axisOptions: { xIsSeries: 0, shortenYAxisNumbers: 1 },
      barOptions: { spaceRatio: 0.4 },
    });
  } catch (e) {
    // chart is decoration — never let it break the report
    console.warn("chart render failed", e);
    chart.value = null;
  }
}

function isNum(c) { return NUM_TYPES.has(c.fieldtype); }

function isBold(r) {
  // tree reports (Balance Sheet, P&L, Trial Balance): top-level rows are groups
  if (r.bold) return true;
  return hasTree.value && Number(r.indent || 0) === 0;
}

function display(v, c) {
  if (v === null || v === undefined || v === "") return "";
  if (typeof v === "number") {
    if (c.fieldtype === "Int") return inr0.format(v);
    if (NUM_TYPES.has(c.fieldtype)) return inr.format(Math.round(v * 100) / 100);
    return inr.format(v);
  }
  // strip any html that leaked into cell values
  const s = String(v);
  return s.includes("<") ? s.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim() : s;
}

function fmtSummary(s) {
  const v = s.value;
  if (typeof v !== "number") return String(v ?? "");
  const a = Math.abs(v);
  let txt;
  if (a >= 1e7) txt = inr.format(Math.round(v / 1e5) / 100) + " Cr";
  else if (a >= 1e5) txt = inr.format(Math.round(v / 1e3) / 100) + " L";
  else txt = inr.format(Math.round(v * 100) / 100);
  return (s.datatype === "Currency" ? "₹ " : "") + txt;
}

defineExpose({ reload: () => run() });
</script>

<style scoped>
.rp-wrap { padding: 12px 14px 30px; }

/* ── filter bar ── */
.rp-filters {
  display: flex; flex-direction: column; gap: 8px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
  padding: 10px 12px; margin-bottom: 12px;
}
.rp-f-row { display: flex; align-items: flex-end; gap: 8px; }
.rp-fl { flex: 1; display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.rp-fl span { font-size: 10.5px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: .3px; }
.rp-fl input, .rp-fl select {
  width: 100%; border: 1.5px solid #e2e8f0; border-radius: 10px; background: #f8fafc;
  padding: 7px 8px; font-size: 13px; color: #1e293b; outline: none; -webkit-appearance: none;
  font-family: inherit;
}
.rp-link { position: relative; }
.rp-clear {
  position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
  border: none; background: #e2e8f0; color: #64748b; border-radius: 50%;
  width: 20px; height: 20px; font-size: 11px; line-height: 1; cursor: pointer;
}
.rp-link-list {
  position: absolute; z-index: 30; top: 100%; left: 0; right: 0; margin: 4px 0 0; padding: 4px;
  list-style: none; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15,23,42,.12); max-height: 220px; overflow-y: auto;
}
.rp-link-list li { padding: 9px 12px; font-size: 13px; border-radius: 8px; cursor: pointer; }
.rp-link-list li:hover { background: #f1f5f9; }
.rp-apply {
  height: 38px; border: none; border-radius: 10px;
  background: var(--ion-color-primary, #6366f1); color: #fff;
  font-size: 13.5px; font-weight: 700; cursor: pointer; -webkit-appearance: none;
}
.rp-apply:disabled { opacity: .6; }

/* ── summary KPI cards ── */
.rp-summary {
  display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px;
}
.rp-sum-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
  padding: 12px 13px; border-left: 4px solid #6366f1; min-width: 0;
}
.rp-sum-card.ind-Green { border-left-color: #22c55e; }
.rp-sum-card.ind-Red   { border-left-color: #ef4444; }
.rp-sum-card.ind-Blue  { border-left-color: #6366f1; }
.rp-sum-value { font-size: 17px; font-weight: 900; color: #0f172a; letter-spacing: -.3px; word-break: break-word; }
.rp-sum-label { font-size: 11.5px; font-weight: 600; color: #94a3b8; margin-top: 3px; }

/* ── chart ── */
.rp-chart-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
  padding: 6px 4px; margin-bottom: 12px; overflow: hidden;
}

.rp-message {
  background: #eef2ff; color: #4338ca; font-size: 12.5px;
  border-radius: 12px; padding: 10px 12px; margin-bottom: 12px;
}

/* ── table ── */
.rp-meta { font-size: 12.5px; font-weight: 700; color: #94a3b8; margin: 4px 2px 10px; }
.rp-scroll {
  overflow: auto; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff;
  max-height: 70vh; -webkit-overflow-scrolling: touch;
}
.rp-t { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 12.5px; }
.rp-t th {
  position: sticky; top: 0; z-index: 3; background: #f8fafc; text-align: left;
  padding: 9px 11px; font-weight: 700; color: #64748b; white-space: nowrap;
  border-bottom: 1px solid #e2e8f0;
}
.rp-t th.first { left: 0; z-index: 4; }
.rp-t td {
  padding: 8px 11px; border-bottom: 1px solid #f1f5f9; color: #1e293b; white-space: nowrap;
  background: #fff;
}
.rp-t td.first {
  position: sticky; left: 0; z-index: 2;
  max-width: 46vw; overflow: hidden; text-overflow: ellipsis;
  border-right: 1px solid #f1f5f9;
}
.rp-t th.num, .rp-t td.num { text-align: right; font-variant-numeric: tabular-nums; }
.rp-t tr.bold td { font-weight: 800; color: #0f172a; background: #fafbfd; }
</style>
