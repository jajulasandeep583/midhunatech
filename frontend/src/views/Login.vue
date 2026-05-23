<!-- Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0 -->
<template>
  <ion-page>
    <ion-content :fullscreen="true">
      <div class="login-root">

        <!-- ── Branding (pure CSS — no images) ── -->
        <div class="login-brand">
          <div class="brand-mark" :style="{ background: brandColor }">
            <span>M</span>
          </div>
          <h1 class="brand-name">{{ brandName }}</h1>
          <p class="brand-sub">Sign in to continue</p>
        </div>

        <!-- ── Form card ── -->
        <div class="login-card">

          <!-- Email -->
          <div class="field-wrap">
            <label class="field-label">Email or Username</label>
            <input
              ref="emailRef"
              v-model="form.usr"
              class="field-input"
              type="email"
              inputmode="email"
              autocomplete="username"
              autocapitalize="none"
              placeholder="admin@yoursite.com"
              :disabled="loading"
              @keyup.enter="focusPw"
            />
          </div>

          <!-- Password -->
          <div class="field-wrap" style="margin-top:14px;">
            <label class="field-label">Password</label>
            <div class="pw-wrap">
              <input
                ref="pwRef"
                v-model="form.pwd"
                class="field-input"
                :type="showPw ? 'text' : 'password'"
                autocomplete="current-password"
                placeholder="••••••••"
                :disabled="loading"
                @keyup.enter="submit"
              />
              <button class="pw-toggle" type="button" tabindex="-1" @click="showPw = !showPw">
                {{ showPw ? "Hide" : "Show" }}
              </button>
            </div>
          </div>

          <!-- Error message -->
          <div v-if="error" class="login-error" role="alert">
            <span aria-hidden="true">⚠</span>
            <span>{{ error }}</span>
          </div>

          <!-- Submit button -->
          <button
            class="login-btn"
            :style="{ background: brandColor }"
            :disabled="loading || !form.usr || !form.pwd"
            @click="submit"
            type="button"
          >
            <span v-if="loading" class="mt-spinner" aria-label="Signing in" />
            <span v-else>Sign in</span>
          </button>

        </div>

        <p class="login-footer">Midhunatech &middot; Powered by Frappe v16</p>
      </div>
    </ion-content>
  </ion-page>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useRouter, useRoute } from "vue-router";
import { IonPage, IonContent } from "@ionic/vue";
import { login, loadConfig } from "@/data/session.js";

const router   = useRouter();
const route    = useRoute();
const form     = ref({ usr: "", pwd: "" });
const loading  = ref(false);
const error    = ref("");
const showPw   = ref(false);
const emailRef = ref(null);
const pwRef    = ref(null);

// Branding from server (loaded without auth)
const brandName  = ref("Midhunatech");
const brandColor = ref("#6366f1");

onMounted(async () => {
  // Fetch public branding — no auth needed
  try {
    const r = await fetch("/api/method/midhunatech.api.pwa.get_public_config", {
      credentials: "include",
    });
    const d = await r.json();
    if (d.message) {
      brandName.value  = d.message.app_name    || "Midhunatech";
      brandColor.value = d.message.theme_color || "#6366f1";
    }
  } catch { /* use defaults */ }

  // Auto-focus email field
  setTimeout(() => emailRef.value?.focus(), 150);
});

function focusPw() { pwRef.value?.focus(); }

async function submit() {
  if (loading.value || !form.value.usr || !form.value.pwd) return;
  loading.value = true;
  error.value   = "";
  try {
    await login(form.value.usr, form.value.pwd);
    await loadConfig();
    // Redirect to original destination or home
    const dest = route.query.r || "/midhunatech/home";
    router.replace(dest);
  } catch (e) {
    error.value = e.message || "Login failed. Please try again.";
    // Re-focus email field for retry
    setTimeout(() => emailRef.value?.focus(), 100);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-root {
  min-height: 100dvh;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 32px 20px 48px;
  background: #f1f5f9;
}

/* ── Branding ── */
.login-brand { text-align: center; margin-bottom: 28px; }
.brand-mark {
  width: 72px; height: 72px; border-radius: 22px;
  display: flex; align-items: center; justify-content: center;
  font-size: 34px; font-weight: 900; color: #fff;
  margin: 0 auto 12px; letter-spacing: -1px;
}
.brand-name {
  font-size: 26px; font-weight: 900; color: #1e293b;
  letter-spacing: -.5px; margin: 0 0 4px;
}
.brand-sub { font-size: 14px; color: #94a3b8; margin: 0; }

/* ── Card ── */
.login-card {
  width: 100%; max-width: 360px;
  background: #fff; border-radius: 20px;
  padding: 24px 20px 20px;
  box-shadow: 0 2px 20px rgba(0,0,0,.07);
}

/* ── Fields ── */
.field-wrap   { display: flex; flex-direction: column; gap: 6px; }
.field-label  { font-size: 13px; font-weight: 600; color: #475569; }
.field-input {
  width: 100%; padding: 12px 14px;
  border: 1.5px solid #e2e8f0; border-radius: 12px;
  font-size: 15px; color: #1e293b; outline: none;
  background: #f8fafc; transition: border-color .15s;
  -webkit-appearance: none; appearance: none;
}
.field-input:focus { border-color: #6366f1; background: #fff; }
.field-input:disabled { opacity: .5; }

/* ── Password toggle ── */
.pw-wrap   { position: relative; }
.pw-toggle {
  position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
  background: none; border: none; cursor: pointer;
  font-size: 12px; font-weight: 600; color: #6366f1;
  padding: 4px; -webkit-appearance: none;
}

/* ── Error ── */
.login-error {
  display: flex; align-items: center; gap: 6px;
  background: #fef2f2; border-radius: 10px;
  padding: 10px 12px; margin-top: 12px;
  font-size: 13px; color: #dc2626; line-height: 1.4;
}

/* ── Submit ── */
.login-btn {
  width: 100%; height: 50px; margin-top: 16px;
  border: none; border-radius: 14px;
  color: #fff; font-size: 16px; font-weight: 700;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: opacity .15s; -webkit-appearance: none;
}
.login-btn:active:not(:disabled) { opacity: .85; transform: scale(.98); }
.login-btn:disabled { opacity: .5; cursor: not-allowed; }

.login-footer {
  font-size: 12px; color: #94a3b8; margin-top: 24px; text-align: center;
}
</style>
