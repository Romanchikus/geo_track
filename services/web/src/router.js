import { createRouter, createWebHistory } from "vue-router";

import { auth, refreshMe } from "./auth";
import LoginView from "./views/LoginView.vue";
import StatsView from "./views/StatsView.vue";
import SubscriptionsView from "./views/SubscriptionsView.vue";
import UsersView from "./views/UsersView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/subscriptions" },
    { path: "/login", component: LoginView, meta: { public: true } },
    { path: "/accounts", component: UsersView },
    { path: "/stats", component: StatsView },
    { path: "/subscriptions", component: SubscriptionsView },
  ],
});

router.beforeEach(async (to) => {
  if (!auth.ready) {
    try {
      await refreshMe();
    } catch {
      auth.user = null;
      auth.ready = true;
    }
  }
  if (!to.meta.public && !auth.user) return "/login";
  if (to.path === "/login" && auth.user) return "/subscriptions";
  return true;
});

export default router;
