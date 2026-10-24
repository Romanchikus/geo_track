<script setup>
import { onMounted, ref } from "vue";

import { api } from "../api";

const counts = ref(null);
const error = ref("");

onMounted(async () => {
  try {
    counts.value = await api("/statistics");
  } catch (err) {
    error.value = err.message;
  }
});
</script>

<template>
  <section>
    <h1>Statistics</h1>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="!counts" class="muted">Loading…</p>
    <div v-else class="metrics">
      <article>
        <span>Devices</span>
        <strong>{{ counts.devices }}</strong>
      </article>
      <article>
        <span>Telemetry, last day</span>
        <strong>{{ counts.telemetry_last_day }}</strong>
      </article>
      <article>
        <span>Subscriptions</span>
        <strong>{{ counts.subscriptions }}</strong>
      </article>
      <article>
        <span>Users</span>
        <strong>{{ counts.users }}</strong>
      </article>
    </div>
  </section>
</template>
