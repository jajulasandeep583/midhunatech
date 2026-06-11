<!-- Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0 -->
<!-- Generic native "create record" form for any doctype (meta-driven). -->
<template>
  <ion-modal :is-open="open" @didDismiss="$emit('close')">
    <ion-header>
      <ion-toolbar>
        <ion-title class="df-title">New {{ doctype }}</ion-title>
        <ion-buttons slot="end">
          <ion-button @click="$emit('close')">Cancel</ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <!-- loading meta -->
      <div v-if="loading" class="df-center"><ion-spinner name="crescent" color="primary" /></div>

      <!-- not creatable here -->
      <div v-else-if="notCreatable" class="df-center df-note">
        <div class="df-note-ico">📝</div>
        <p>{{ notCreatable }}</p>
      </div>

      <!-- form -->
      <template v-else>
        <div v-for="f in fields" :key="f.fieldname" class="df-field">
          <label class="df-label">
            {{ f.label }} <span v-if="f.reqd" class="df-req">*</span>
          </label>

          <!-- Select -->
          <select v-if="f.fieldtype === 'Select'" v-model="form[f.fieldname]" class="df-input">
            <option value="">— select —</option>
            <option v-for="o in selectOptions(f)" :key="o" :value="o">{{ o }}</option>
          </select>

          <!-- Check -->
          <ion-toggle v-else-if="f.fieldtype === 'Check'" :checked="!!form[f.fieldname]"
            @ionChange="form[f.fieldname] = $event.detail.checked ? 1 : 0" />

          <!-- Link (autocomplete) -->
          <div v-else-if="f.fieldtype === 'Link'" class="df-link">
            <input class="df-input" :value="form[f.fieldname]"
              :placeholder="`Search ${f.options}`"
              @input="onLink(f, $event.target.value)" @focus="onLink(f, form[f.fieldname] || '')" />
            <ul v-if="linkFor === f.fieldname && linkResults.length" class="df-link-list">
              <li v-for="o in linkResults" :key="o.value" @mousedown.prevent="pickLink(f, o)">
                <b>{{ o.value }}</b><span v-if="o.label !== o.value"> — {{ o.label }}</span>
              </li>
            </ul>
          </div>

          <!-- Long text -->
          <textarea v-else-if="['Text','Small Text','Long Text','Text Editor'].includes(f.fieldtype)"
            v-model="form[f.fieldname]" class="df-input df-textarea" rows="3" />

          <!-- Numbers / dates / data -->
          <input v-else v-model="form[f.fieldname]" class="df-input" :type="inputType(f.fieldtype)" />
        </div>

        <!-- ── line items (e.g. Material Request items) ── -->
        <template v-if="child">
          <div class="df-items-head">
            <span class="df-items-title">{{ child.label }}</span>
            <span class="df-items-count">{{ rows.length }} item{{ rows.length !== 1 ? "s" : "" }}</span>
          </div>

          <div v-for="(row, ri) in rows" :key="ri" class="df-item-card">
            <div class="df-item-top">
              <span class="df-item-no">#{{ ri + 1 }}</span>
              <button v-if="rows.length > 1" class="df-item-del" aria-label="Remove item"
                      @click="rows.splice(ri, 1)">✕ Remove</button>
            </div>
            <div v-for="cf in child.fields" :key="cf.fieldname" class="df-field" style="margin-bottom:10px;">
              <label class="df-label">
                {{ cf.label }} <span v-if="cf.reqd" class="df-req">*</span>
              </label>

              <select v-if="cf.fieldtype === 'Select'" v-model="row[cf.fieldname]" class="df-input">
                <option value="">— select —</option>
                <option v-for="o in selectOptions(cf)" :key="o" :value="o">{{ o }}</option>
              </select>

              <div v-else-if="cf.fieldtype === 'Link'" class="df-link">
                <input class="df-input" :value="row[cf.fieldname]"
                  :placeholder="`Search ${cf.options}`"
                  @input="onLink(cf, $event.target.value, ri)"
                  @focus="onLink(cf, row[cf.fieldname] || '', ri)" />
                <ul v-if="linkFor === `${ri}:${cf.fieldname}` && linkResults.length" class="df-link-list">
                  <li v-for="o in linkResults" :key="o.value" @mousedown.prevent="pickLink(cf, o, ri)">
                    <b>{{ o.value }}</b><span v-if="o.label !== o.value"> — {{ o.label }}</span>
                  </li>
                </ul>
              </div>

              <input v-else v-model="row[cf.fieldname]" class="df-input" :type="inputType(cf.fieldtype)" />
            </div>
          </div>

          <button class="df-add-item" @click="rows.push(emptyRow())">＋ Add item</button>
        </template>

        <div v-if="error" class="df-error" role="alert">{{ error }}</div>

        <button class="df-submit" :disabled="!canSubmit || saving" @click="submit">
          <ion-spinner v-if="saving" name="crescent" style="width:18px;height:18px;" />
          <span v-else>Create {{ doctype }}</span>
        </button>
      </template>
    </ion-content>
  </ion-modal>
</template>

<script setup>
import { ref, reactive, computed, watch } from "vue";
import {
  IonModal, IonHeader, IonToolbar, IonTitle, IonButtons, IonButton,
  IonContent, IonSpinner, IonToggle,
} from "@ionic/vue";
import { getCreateMeta, searchLink, createDoc } from "@/data/docdata.js";

const props = defineProps({
  open:    { type: Boolean, default: false },
  doctype: { type: String, required: true },
  label:   { type: String, default: "" },
});
const emit = defineEmits(["close", "created"]);

const loading = ref(false);
const saving = ref(false);
const error = ref(null);
const notCreatable = ref(null);
const fields = ref([]);
const form = reactive({});
const child = ref(null);          // {fieldname, label, fields} for line items
const rows = ref([]);             // line-item rows being edited

const linkFor = ref(null);
const linkResults = ref([]);
let linkTimer = null;

function emptyRow() {
  const r = {};
  for (const cf of child.value?.fields || []) r[cf.fieldname] = cf.default || "";
  return r;
}

watch(() => props.open, async (isOpen) => {
  if (!isOpen) return;
  // reset
  error.value = null; notCreatable.value = null; fields.value = [];
  child.value = null; rows.value = [];
  Object.keys(form).forEach(k => delete form[k]);
  loading.value = true;
  try {
    const meta = await getCreateMeta(props.doctype);
    if (!meta.creatable) { notCreatable.value = meta.reason; return; }
    fields.value = meta.fields;
    for (const f of meta.fields) {
      form[f.fieldname] = f.fieldtype === "Check" ? (Number(f.default) ? 1 : 0) : (f.default || "");
    }
    if (meta.child) {
      child.value = meta.child;
      rows.value = [emptyRow()];
    }
  } catch (e) {
    notCreatable.value = e.message;
  } finally {
    loading.value = false;
  }
});

function selectOptions(f) {
  return (f.options || "").split("\n").map(s => s.trim()).filter(Boolean);
}
function inputType(ft) {
  if (["Int", "Float", "Currency", "Percent"].includes(ft)) return "number";
  if (ft === "Date") return "date";
  if (ft === "Datetime") return "datetime-local";
  if (ft === "Time") return "time";
  if (ft === "Phone") return "tel";
  return "text";
}

function onLink(f, txt, ri = null) {
  const target = ri == null ? form : rows.value[ri];
  target[f.fieldname] = txt;
  linkFor.value = ri == null ? f.fieldname : `${ri}:${f.fieldname}`;
  clearTimeout(linkTimer);
  linkTimer = setTimeout(async () => {
    try { linkResults.value = await searchLink(f.options, txt); }
    catch { linkResults.value = []; }
  }, 250);
}
function pickLink(f, o, ri = null) {
  const target = ri == null ? form : rows.value[ri];
  target[f.fieldname] = o.value;
  linkResults.value = [];
  linkFor.value = null;
}

const filled = (v) => v !== "" && v != null;

const canSubmit = computed(() => {
  if (!fields.value.filter(f => f.reqd).every(f => filled(form[f.fieldname]))) return false;
  if (child.value) {
    const reqd = child.value.fields.filter(f => f.reqd);
    if (!rows.value.length) return false;
    if (!rows.value.every(r => reqd.every(f => filled(r[f.fieldname])))) return false;
  }
  return true;
});

async function submit() {
  saving.value = true;
  error.value = null;
  try {
    const payload = { ...form };
    if (child.value) payload[child.value.fieldname] = rows.value.map(r => ({ ...r }));
    const res = await createDoc(props.doctype, payload);
    emit("created", res.name);
    emit("close");
  } catch (e) {
    error.value = e.message || "Could not create.";
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.df-title { font-size: 16px; font-weight: 800; }
.df-center { display: flex; flex-direction: column; align-items: center; padding: 50px 20px; color: #64748b; }
.df-note-ico { font-size: 38px; margin-bottom: 10px; }
.df-note p { text-align: center; font-size: 14px; }

.df-field { margin-bottom: 16px; }
.df-label { display: block; font-size: 12.5px; font-weight: 700; color: #475569; margin-bottom: 6px; }
.df-req { color: #ef4444; }
.df-input {
  width: 100%; border: 1px solid #d8dee9; border-radius: 12px; padding: 12px 14px;
  font-size: 15px; background: #fff; color: #1e293b; -webkit-appearance: none; appearance: none;
  font-family: inherit;
}
.df-input:focus { outline: none; border-color: var(--ion-color-primary); }
.df-textarea { resize: vertical; }

.df-link { position: relative; }
.df-link-list {
  position: absolute; z-index: 30; top: 100%; left: 0; right: 0; margin: 4px 0 0; padding: 4px;
  list-style: none; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15,23,42,.12); max-height: 220px; overflow-y: auto;
}
.df-link-list li { padding: 9px 12px; font-size: 13.5px; border-radius: 8px; cursor: pointer; }
.df-link-list li:hover { background: #f1f5f9; }

/* ── line items ── */
.df-items-head { display: flex; align-items: baseline; justify-content: space-between;
  margin: 20px 0 10px; }
.df-items-title { font-size: 14px; font-weight: 800; color: #334155; }
.df-items-count { font-size: 12px; font-weight: 600; color: #94a3b8; }
.df-item-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 14px;
  padding: 12px 14px 4px; margin-bottom: 10px; }
.df-item-card .df-input { background: #fff; }
.df-item-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.df-item-no { font-size: 12px; font-weight: 800; color: #94a3b8; }
.df-item-del { border: none; background: #fef2f2; color: #dc2626; font-size: 12px; font-weight: 700;
  border-radius: 8px; padding: 5px 10px; cursor: pointer; -webkit-appearance: none; }
.df-add-item { width: 100%; height: 44px; border: 1.5px dashed #c7d2fe; border-radius: 12px;
  background: #eef2ff; color: #4f46e5; font-size: 14px; font-weight: 700; cursor: pointer;
  margin-bottom: 14px; -webkit-appearance: none; }

.df-error { background: #fef2f2; color: #dc2626; font-size: 13px; border-radius: 10px;
  padding: 10px 12px; margin-bottom: 12px; }
.df-submit {
  width: 100%; height: 50px; border: none; border-radius: 14px; margin-top: 6px;
  background: var(--ion-color-primary); color: #fff; font-size: 15.5px; font-weight: 800;
  display: flex; align-items: center; justify-content: center; cursor: pointer;
}
.df-submit:disabled { opacity: .5; }
</style>
