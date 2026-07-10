<!-- Copyright (c) 2026, Midhunatech and Contributors — GPL-3.0
     PWA install banner. Opening the app in a normal browser tab (not yet
     installed) surfaces a one-tap "Install" banner. Android/desktop Chromium:
     captures beforeinstallprompt and fires the native install dialog. iOS Safari
     (no beforeinstallprompt): shows Add-to-Home-Screen instructions instead.
     Hidden once installed (standalone) or dismissed. Fully self-contained. -->
<template>
  <transition name="ib-slide">
    <div v-if="visible" class="install-bar">
      <span class="install-msg" v-html="message"></span>
      <button v-if="!iosHint" class="install-do" type="button" @click="install">Install</button>
      <button class="install-x" type="button" aria-label="Dismiss" @click="dismiss">&times;</button>
    </div>
  </transition>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";

const DISMISS_KEY = "mtInstallDismissed";
const APP_LABEL = (window.__MT__ && window.__MT__.app_name) || "the app";

const visible = ref(false);
const iosHint = ref(false);
const message = ref(`📲 Install ${APP_LABEL} on your phone for one-tap access &amp; alerts`);
let deferred = null;

function isStandalone() {
  return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
}
function dismissed() {
  try { return localStorage.getItem(DISMISS_KEY) === "1"; } catch { return false; }
}
function setDismissed() {
  try { localStorage.setItem(DISMISS_KEY, "1"); } catch { /* ignore */ }
}

function onBeforeInstall(e) {
  e.preventDefault();          // stop Chrome's default mini-infobar
  deferred = e;                // stash so we can fire it on tap
  if (!isStandalone() && !dismissed()) visible.value = true;
}
function onInstalled() {
  visible.value = false;
  setDismissed();
}

async function install() {
  if (!deferred) return;
  deferred.prompt();
  const choice = await deferred.userChoice;
  deferred = null;
  visible.value = false;
  if (choice && choice.outcome === "accepted") setDismissed();
}
function dismiss() {
  visible.value = false;
  setDismissed();
}

onMounted(() => {
  if (isStandalone() || dismissed()) return;
  window.addEventListener("beforeinstallprompt", onBeforeInstall);
  window.addEventListener("appinstalled", onInstalled);

  // iOS Safari never fires beforeinstallprompt and has no programmatic install
  // → show manual Add-to-Home-Screen instructions.
  const ua = navigator.userAgent || "";
  const isIOS = /iphone|ipad|ipod/i.test(ua) || (/mac/i.test(ua) && "ontouchend" in document);
  const isIOSSafari = isIOS && /safari/i.test(ua) && !/crios|fxios|edgios|android/i.test(ua);
  if (isIOSSafari) {
    iosHint.value = true;
    message.value = "📲 Install this app: tap <b>Share</b>, then <b>Add to Home Screen</b>";
    visible.value = true;
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("beforeinstallprompt", onBeforeInstall);
  window.removeEventListener("appinstalled", onInstalled);
});
</script>

<style scoped>
.install-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 99999;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: calc(11px + env(safe-area-inset-top, 0px)) 14px 11px;
  background: linear-gradient(90deg, var(--ion-color-primary, #6366f1), #8b5cf6);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.25);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.install-msg { flex: 1; line-height: 1.35; }
.install-msg :deep(b) { font-weight: 800; }
.install-do {
  flex: none;
  background: #fff;
  color: var(--ion-color-primary, #6366f1);
  border: none;
  border-radius: 9px;
  padding: 8px 16px;
  font-weight: 800;
  font-size: 13px;
  white-space: nowrap;
  cursor: pointer;
}
.install-x {
  flex: none;
  background: transparent;
  color: #fff;
  border: none;
  padding: 4px 6px;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}
.ib-slide-enter-active, .ib-slide-leave-active { transition: transform 0.25s ease, opacity 0.25s ease; }
.ib-slide-enter-from, .ib-slide-leave-to { transform: translateY(-100%); opacity: 0; }
</style>
