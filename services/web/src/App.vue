<script setup>
import { watch } from "vue";
import { useRouter } from "vue-router";

import { auth, logout } from "./auth";
import LiveStats from "./components/LiveStats.vue";
import { useLiveStore } from "./live/store";

const router = useRouter();
const live = useLiveStore();

watch(
  () => auth.user,
  (user) => {
    if (user) live.start();
    else live.stop();
  },
  { immediate: true },
);

async function signOut() {
  await logout();
  await router.push("/login");
}
</script>

<template>
  <div class="app">
    <header class="top">
      <router-link class="brand" to="/subscriptions">Geo Track</router-link>
      <nav v-if="auth.user" class="nav">
        <router-link to="/subscriptions">Subscriptions</router-link>
        <router-link to="/stats">Statistics</router-link>
        <router-link to="/accounts">Users</router-link>
        <span class="who">{{ auth.user.email }}</span>
        <button type="button" class="btn btn-outline-light btn-sm" @click="signOut">Log out</button>
        <LiveStats />
      </nav>
    </header>
    <main>
      <router-view />
    </main>
  </div>
</template>
