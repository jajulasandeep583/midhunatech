// Copyright (c) 2024, Midhunatech and Contributors — GPL-3.0
import { createApp }  from "vue";
import { IonicVue }   from "@ionic/vue";
import App    from "./App.vue";
import router from "./router/index.js";

// Ionic required CSS — order matters
import "@ionic/vue/css/core.css";
import "@ionic/vue/css/normalize.css";
import "@ionic/vue/css/structure.css";
import "@ionic/vue/css/typography.css";
import "@ionic/vue/css/padding.css";
import "@ionic/vue/css/flex-utils.css";
import "@ionic/vue/css/display.css";

// Our theme overrides (must come AFTER Ionic CSS)
import "./theme/variables.css";
import "./main.css";

const app = createApp(App);

app.use(IonicVue, {
  mode:             "ios",   // consistent iOS look on all platforms
  animated:          true,
  swipeBackEnabled:  true,
});
app.use(router);

// Wait for router to be ready before mounting (Ionic requirement)
router.isReady().then(() => app.mount("#app"));
