<!-- Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0 -->
<!-- Native KPI dashboard — renders Frappe Number Cards as tappable stat cards. -->
<template>
  <div class="dash-root">
    <!-- loading -->
    <div v-if="loading" class="dash-grid">
      <div v-for="i in 4" :key="i" class="dash-card" aria-hidden="true">
        <ion-skeleton-text :animated="true" style="width:60%;height:30px;border-radius:8px;" />
        <ion-skeleton-text :animated="true" style="width:80%;height:13px;border-radius:6px;margin-top:10px;" />
      </div>
    </div>

    <!-- error -->
    <div v-else-if="error" class="dash-empty" role="alert">
      <div class="dash-empty-ico">⚠</div>
      <h3>Couldn’t load dashboard</h3>
      <p>{{ error }}</p>
      <ion-button fill="outline" size="small" @click="reload">Try again</ion-button>
    </div>

    <!-- empty -->
    <div v-else-if="!cards.length" class="dash-empty">
      <div class="dash-empty-ico">📊</div>
      <h3>No cards yet</h3>
      <p>Create <strong>Number Cards</strong> in the Frappe desk (New → Number Card),
         then they’ll appear here automatically.</p>
    </div>

    <!-- cards -->
    <template v-else>
      <div class="dash-grid">
        <div v-for="c in cards" :key="c.name" class="dash-card"
          :style="{ '--accent': c.color }">
          <div class="dash-bar" :style="{ background: c.color }" />
          <div class="dash-val">{{ c.value }}</div>
          <div class="dash-lbl">{{ c.label }}</div>
          <div class="dash-meta">{{ c.function }} · {{ c.doctype }}</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { IonSkeletonText, IonButton } from "@ionic/vue";
import { getDashboard } from "@/data/docdata.js";

const props = defineProps({
  target: { type: String, default: "" },
});

const cards = ref([]);
const loading = ref(true);
const error = ref(null);

async function reload() {
  loading.value = true;
  error.value = null;
  try {
    const d = await getDashboard(props.target);
    cards.value = d.cards || [];
  } catch (e) {
    error.value = e.message || "Something went wrong.";
  } finally {
    loading.value = false;
  }
}

defineExpose({ reload });
onMounted(reload);
</script>

<style scoped>
.dash-root { padding: 16px 14px 28px; }
.dash-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.dash-card {
  position: relative; background: #fff; border: 1px solid #e8edf3; border-radius: 18px;
  padding: 18px 16px 14px; overflow: hidden;
  box-shadow: 0 1px 10px rgba(15,23,42,.04);
  /* accent tint — browsers without color-mix keep the white fallback above */
  background: linear-gradient(150deg, color-mix(in srgb, var(--accent, #6366f1) 11%, #fff), #fff 75%);
  border-color: color-mix(in srgb, var(--accent, #6366f1) 26%, #e8edf3);
}
.dash-bar { position: absolute; top: 0; left: 0; right: 0; height: 4px; }
.dash-val { font-size: 30px; font-weight: 900; letter-spacing: -1.2px; color: #0f172a; line-height: 1; }
.dash-lbl { font-size: 13px; font-weight: 700; color: #334155; margin-top: 8px; }
.dash-meta { font-size: 10.5px; color: #94a3b8; margin-top: 4px; text-transform: uppercase; letter-spacing: .3px; }

.dash-empty { text-align: center; padding: 60px 24px; color: #64748b; }
.dash-empty-ico { font-size: 40px; margin-bottom: 8px; }
.dash-empty h3 { margin: 0 0 4px; font-size: 16px; color: #334155; font-weight: 800; }
.dash-empty p { margin: 0 0 12px; font-size: 13px; line-height: 1.5; }
</style>
