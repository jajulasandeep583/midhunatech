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
          <span v-if="detail.status" class="dl-badge" :class="badgeClass(detail.status)" style="margin-bottom:14px;display:inline-block;">
            {{ detail.status }}
          </span>
          <div class="dl-field" v-for="(f, i) in detail.fields" :key="i">
            <div class="dl-field-lbl">{{ f.label }}</div>
            <div class="dl-field-val">{{ f.value }}</div>
          </div>
        </template>
      </ion-content>
    </ion-modal>

    <!-- ── Floating "+" create button ── -->
    <button v-if="view.can_create" class="dl-fab" :aria-label="`New ${view.label}`" @click="showForm = true">+</button>

    <!-- ── Create form ── -->
    <DocForm
      :open="showForm"
      :doctype="props.doctype"
      :label="view.label || props.label"
      @close="showForm = false"
      @created="onCreated"
    />

    <ion-toast :is-open="!!toast" :message="toast" :duration="2200" color="success"
      @didDismiss="toast = ''" />

  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import {
  IonSearchbar, IonSkeletonText, IonButton, IonInfiniteScroll,
  IonInfiniteScrollContent, IonModal, IonHeader, IonToolbar, IonTitle,
  IonButtons, IonContent, IonSpinner, IonToast,
} from "@ionic/vue";
import { getView, getList, getDoc, badgeClass } from "@/data/docdata.js";
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
const toast = ref("");

async function onCreated(name) {
  toast.value = `Created ${name}`;
  await reload();
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

// expose reload for parent pull-to-refresh
defineExpose({ reload });

onMounted(reload);
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
.dl-field { padding: 11px 0; border-bottom: 1px solid #f1f5f9; }
.dl-field:last-child { border-bottom: none; }
.dl-field-lbl { font-size: 11.5px; font-weight: 700; color: #94a3b8; text-transform: uppercase;
  letter-spacing: .3px; }
.dl-field-val { font-size: 14.5px; color: #1e293b; margin-top: 3px; word-break: break-word; }

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
