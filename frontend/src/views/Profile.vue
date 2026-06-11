<!-- Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0 -->
<template>
  <ion-page>
    <ion-header :translucent="true">
      <ion-toolbar>
        <ion-title>Profile</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content :fullscreen="true">
      <!-- iOS collapsible large title -->
      <ion-header collapse="condense">
        <ion-toolbar>
          <ion-title size="large">Profile</ion-title>
        </ion-toolbar>
      </ion-header>

      <!-- ── User hero ── -->
      <div class="profile-hero">
        <div
          class="mt-avatar"
          style="width:72px;height:72px;font-size:28px;border-radius:50%;flex-shrink:0;"
          :style="{ background: appConfig.primary_color }"
          aria-hidden="true"
        >{{ userInitial }}</div>
        <div>
          <div class="profile-name">{{ session.fullname || session.user }}</div>
          <div class="profile-email">{{ session.email || session.user }}</div>
        </div>
      </div>

      <!-- ── App info ── -->
      <div class="section-title">App</div>
      <ion-list lines="inset" class="info-list">
        <ion-item>
          <ion-label>
            <h3>App name</h3>
            <p>{{ appConfig.app_name }}</p>
          </ion-label>
        </ion-item>
        <ion-item>
          <ion-label>
            <h3>Site</h3>
            <p>{{ hostname }}</p>
          </ion-label>
        </ion-item>
        <ion-item>
          <ion-label>
            <h3>Modules active</h3>
            <p>{{ appConfig.modules.length }} module{{ appConfig.modules.length !== 1 ? "s" : "" }}</p>
          </ion-label>
        </ion-item>
        <ion-item>
          <ion-label>
            <h3>Version</h3>
            <p>1.0.0 &middot; Frappe v16</p>
          </ion-label>
        </ion-item>
      </ion-list>

      <!-- ── Admin (only visible to System Manager / Administrator) ── -->
      <template v-if="session.is_system_manager">
        <div class="section-title">Admin</div>
        <ion-list lines="inset" class="info-list">
          <ion-item button detail @click="router.push('/midhunatech/settings')">
            <ion-label color="primary">⚙ App Settings — tiles, tabs &amp; branding</ion-label>
          </ion-item>
        </ion-list>
      </template>

      <!-- ── Push notifications ── -->
      <div class="section-title">Notifications</div>
      <div class="push-card">
        <div class="push-row">
          <div>
            <div class="push-title">🔔 Push notifications</div>
            <div class="push-sub">{{ pushHint }}</div>
          </div>
          <ion-toggle
            :checked="push.state === 'on'"
            :disabled="push.busy || push.state === 'unsupported' || push.state === 'denied'"
            @ionChange="togglePush"
            aria-label="Enable push notifications"
          />
        </div>
        <div v-if="push.error" class="pw-msg err">{{ push.error }}</div>
      </div>

      <!-- ── Security / change password ── -->
      <div class="section-title">Security</div>
      <div class="pw-card">
        <template v-if="!pwOpen">
          <button class="pw-open-btn" @click="pwOpen = true">
            <span>🔒 Change password</span>
            <span style="color:#cbd5e1;">›</span>
          </button>
        </template>

        <template v-else>
          <div class="pw-field">
            <label>Current password</label>
            <input v-model="pw.old_password" type="password" autocomplete="current-password" :disabled="pw.busy" />
          </div>
          <div class="pw-field">
            <label>New password</label>
            <input v-model="pw.new_password" type="password" autocomplete="new-password" :disabled="pw.busy" />
          </div>
          <div class="pw-field">
            <label>Confirm new password</label>
            <input v-model="pw.confirm" type="password" autocomplete="new-password" :disabled="pw.busy"
                   @keyup.enter="changePassword" />
          </div>

          <div v-if="pw.error" class="pw-msg err">{{ pw.error }}</div>
          <div v-if="pw.done" class="pw-msg ok">✓ Password updated</div>

          <div class="pw-actions">
            <button class="pw-cancel" :disabled="pw.busy" @click="closePw">Cancel</button>
            <button
              class="pw-save"
              :style="{ background: appConfig.primary_color }"
              :disabled="pw.busy || !pw.old_password || !pw.new_password"
              @click="changePassword"
            >
              <span v-if="pw.busy" class="mt-spinner" />
              <span v-else>Update</span>
            </button>
          </div>
        </template>
      </div>

      <!-- ── Logout ── -->
      <div class="logout-wrap">
        <button
          class="logout-btn"
          type="button"
          :disabled="busy"
          @click="handleLogout"
          aria-label="Sign out"
        >
          <span v-if="busy" class="mt-spinner" style="border-top-color:#ef4444;border-color:rgba(239,68,68,.3);" />
          <span v-else>Sign out</span>
        </button>
      </div>

    </ion-content>
  </ion-page>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import {
  IonPage, IonHeader, IonToolbar, IonTitle, IonContent,
  IonList, IonItem, IonLabel, IonToggle,
} from "@ionic/vue";
import { session, appConfig, logout, apiFetch } from "@/data/session.js";
import { pushState, enablePush, disablePush } from "@/data/push.js";

const router   = useRouter();
const busy     = ref(false);
const hostname = window.location.hostname;

// ── Push notifications ───────────────────────────────────────────────────────
const push = reactive({ state: "off", busy: false, error: "" });

onMounted(async () => { push.state = await pushState(); });

const pushHint = computed(() => {
  if (push.state === "unsupported") return "Not supported on this browser";
  if (push.state === "denied")      return "Blocked — allow notifications in browser settings";
  if (push.state === "on")          return "Approvals & alerts arrive on this device";
  return "Get notified of pending approvals & alerts";
});

async function togglePush(e) {
  if (push.busy) return;
  push.busy = true;
  push.error = "";
  try {
    if (e.detail.checked && push.state !== "on") {
      await enablePush();
      push.state = "on";
    } else if (!e.detail.checked && push.state === "on") {
      await disablePush();
      push.state = "off";
    }
  } catch (err) {
    push.error = err.message || "Could not change notification setting.";
    push.state = await pushState();
  } finally {
    push.busy = false;
  }
}

// ── Change password ──────────────────────────────────────────────────────────
const pwOpen = ref(false);
const pw = reactive({ old_password: "", new_password: "", confirm: "", busy: false, error: "", done: false });

function closePw() {
  pwOpen.value = false;
  pw.old_password = pw.new_password = pw.confirm = "";
  pw.error = ""; pw.done = false;
}

async function changePassword() {
  pw.error = ""; pw.done = false;
  if (pw.new_password !== pw.confirm) { pw.error = "New passwords do not match."; return; }
  if (pw.new_password.length < 6)     { pw.error = "New password must be at least 6 characters."; return; }
  pw.busy = true;
  try {
    const r = await apiFetch("/api/method/midhunatech.api.pwa.change_password", {
      method: "POST",
      body: JSON.stringify({ old_password: pw.old_password, new_password: pw.new_password }),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      const msg = (e._server_messages && JSON.parse(e._server_messages)[0]) || e.message || "Could not change password.";
      throw new Error(String(msg).replace(/.*"message":\s*"/, "").replace(/".*/, "").replace(/<[^>]*>/g, "") || "Could not change password.");
    }
    pw.done = true;
    pw.old_password = pw.new_password = pw.confirm = "";
    setTimeout(() => { if (pw.done) closePw(); }, 1800);
  } catch (e) {
    pw.error = e.message || "Could not change password.";
  } finally {
    pw.busy = false;
  }
}

const userInitial = computed(() =>
  (session.fullname || session.user || "M")[0].toUpperCase()
);

async function handleLogout() {
  if (busy.value) return;
  busy.value = true;
  try {
    await logout();
    router.replace("/midhunatech/login");
  } finally {
    busy.value = false;
  }
}

</script>

<style scoped>
.profile-hero {
  display: flex; align-items: center; gap: 16px;
  padding: 20px 16px 16px;
}
.profile-name  { font-size: 19px; font-weight: 800; color: #1e293b; letter-spacing: -.3px; }
.profile-email { font-size: 13px; color: #94a3b8; margin-top: 2px; }

.info-list { border-radius: 14px; margin: 0 16px; overflow: hidden; }

/* ── Push notifications card ── */
.push-card {
  margin: 0 16px; background: #fff; border: 1px solid #e2e8f0;
  border-radius: 14px; padding: 12px 16px;
}
.push-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.push-title { font-size: 15px; font-weight: 600; color: #334155; }
.push-sub { font-size: 12px; color: #94a3b8; margin-top: 2px; }

/* ── Change password card ── */
.pw-card {
  margin: 0 16px; background: #fff; border: 1px solid #e2e8f0;
  border-radius: 14px; padding: 6px 16px;
}
.pw-open-btn {
  width: 100%; display: flex; align-items: center; justify-content: space-between;
  background: none; border: none; padding: 12px 0; cursor: pointer;
  font-size: 15px; font-weight: 600; color: #334155; -webkit-appearance: none;
}
.pw-field { padding: 8px 0; display: flex; flex-direction: column; gap: 5px; }
.pw-field label { font-size: 12.5px; font-weight: 600; color: #64748b; }
.pw-field input {
  width: 100%; padding: 11px 13px; border: 1.5px solid #e2e8f0; border-radius: 11px;
  font-size: 15px; color: #1e293b; outline: none; background: #f8fafc;
  -webkit-appearance: none; transition: border-color .15s;
}
.pw-field input:focus { border-color: var(--ion-color-primary); background: #fff; }
.pw-msg { font-size: 12.5px; padding: 8px 0; }
.pw-msg.err { color: #dc2626; }
.pw-msg.ok  { color: #16a34a; font-weight: 600; }
.pw-actions { display: flex; gap: 10px; padding: 10px 0 12px; }
.pw-cancel {
  flex: 1; height: 44px; border-radius: 12px; border: 1.5px solid #e2e8f0;
  background: #fff; color: #64748b; font-weight: 700; font-size: 14px; cursor: pointer;
  -webkit-appearance: none;
}
.pw-save {
  flex: 2; height: 44px; border-radius: 12px; border: none;
  color: #fff; font-weight: 700; font-size: 14px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  -webkit-appearance: none;
}
.pw-save:disabled, .pw-cancel:disabled { opacity: .5; cursor: not-allowed; }

.logout-wrap { padding: 24px 16px 60px; }
.logout-btn {
  width: 100%; height: 50px; border-radius: 14px;
  border: 1.5px solid #ef4444; background: #fff;
  color: #ef4444; font-size: 16px; font-weight: 700;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  gap: 8px; transition: background .15s;
  -webkit-appearance: none;
}
.logout-btn:hover:not(:disabled)   { background: #fef2f2; }
.logout-btn:active:not(:disabled)  { transform: scale(.98); }
.logout-btn:disabled { opacity: .5; cursor: not-allowed; }
</style>
