<script setup>
import { storeToRefs } from "pinia";

import { useLiveStore } from "../live/store";

const { storedPerSec, inserted } = storeToRefs(useLiveStore());

function num(value) {
  return value == null ? "—" : value.toLocaleString();
}
</script>

<template>
  <div class="live" aria-label="Live telemetry">
    <span><strong>{{ num(storedPerSec) }}</strong> stored/s</span>
    <span><strong>{{ num(inserted) }}</strong> inserted</span>
  </div>
</template>
