<script setup>
import { storeToRefs } from "pinia";
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { api, fetchAll } from "../api";
import { loadPatch } from "../load";
import { useLiveStore } from "../live/store";
import { moveVertex, nearestVertex } from "../map/edit";
import { createGlobe } from "../map/globe";
import { pushStroke, startStroke, strokeRing } from "../map/pen";
import { circleRing, distanceM, formatKm, squareRing } from "../map/shapes";
import { unionRing } from "../map/union";
import { subscriptionPatch } from "../subscriptions/patch";

const areas = ref([]);
const error = ref("");
const pending = ref(false);
const drawing = ref(false);
const shape = ref("polygon");
const points = ref([]);
const anchor = ref(null);
const draft = ref(null);
const modal = ref(false);
const editing = ref(null);
const mode = ref("all");
const percent = ref(25);
const deviceIds = ref("");
const sizeLabel = ref("");
const mapHost = ref(null);
const speedKmh = ref("");
const batchSize = ref("");
const loadError = ref("");
const loadPending = ref(false);
const { devices, alerts } = storeToRefs(useLiveStore());
let globe = null;
let pen = null;
let dragIndex = null;
let framed = false;

const hint = computed(() => {
  if (shape.value === "radius") return "Click the center, then click the edge of the circle.";
  if (shape.value === "square") return "Click the center, then click to set the square size.";
  return "Hold the pen and draw the outline, then release. Or click each corner.";
});

async function load() {
  error.value = "";
  const next = (await fetchAll("/subscriptions")).rows;
  showAreas(next, { fit: !framed && next.length > 0 });
  if (next.length > 0) framed = true;
}

function showAreas(next, options = {}) {
  areas.value = [...next].sort((a, b) => a.polygon_id - b.polygon_id);
  globe?.setAreas(areas.value, { ...options, alerted: alerts.value.polygons });
  paintDevices();
}

function report(err) {
  const message = typeof err?.message === "string" ? err.message : "Request failed";
  error.value = message.includes("coordinates") || message.length > 180 ? "Could not save this area." : message;
}

function paintDevices() {
  globe?.setDevices(devices.value, alerts.value.devices, areas.value);
}

function focusArea(area) {
  globe?.focus(area);
}

function startDrawing() {
  editing.value = null;
  draft.value = null;
  beginDraw();
}

function redrawArea() {
  beginDraw();
}

function beginDraw() {
  error.value = "";
  drawing.value = true;
  modal.value = false;
  points.value = [];
  anchor.value = null;
  sizeLabel.value = "";
  stopPen();
  globe?.setDraft(null);
  globe?.setTool(shape.value);
}

function cancelDrawing() {
  drawing.value = false;
  modal.value = false;
  points.value = [];
  anchor.value = null;
  sizeLabel.value = "";
  stopPen();
  globe?.setTool(null);
  if (editing.value && draft.value) {
    globe?.setDraft(draft.value, draft.value.length);
    return;
  }
  draft.value = null;
  globe?.setDraft(null);
}

function beginEdit(area) {
  error.value = "";
  editing.value = area;
  drawing.value = false;
  modal.value = false;
  draft.value = area.coordinates.map((point) => [...point]);
  mode.value = "ids";
  percent.value = 25;
  deviceIds.value = area.devices.map((device) => device.device_id).join(", ");
  points.value = [];
  anchor.value = null;
  stopPen();
  globe?.setTool(null);
  globe?.focus(area);
  globe?.setDraft(draft.value, draft.value.length);
}

function cancelEdit() {
  editing.value = null;
  cancelDrawing();
}

function stopPen() {
  pen = null;
  window.removeEventListener("mouseup", endPen);
}

function finishPolygon() {
  if (points.value.length < 3) return;
  openModal(points.value.map((point) => [...point]));
}

function openModal(coordinates) {
  draft.value = unionRing(coordinates);
  drawing.value = false;
  stopPen();
  globe?.setTool(null);
  if (editing.value) {
    globe?.setDraft(draft.value, draft.value.length);
    return;
  }
  modal.value = true;
  mode.value = "all";
  percent.value = 25;
  deviceIds.value = "";
  globe?.setDraft(coordinates);
}

function onMapDown(point, pixel) {
  if (editing.value && !drawing.value && !modal.value && draft.value && pixel) {
    const index = nearestVertex(draft.value, pixel, (pair) => globe?.pixelOf(pair));
    if (index >= 0) {
      dragIndex = index;
      window.addEventListener("mouseup", endDrag);
      return true;
    }
  }
  if (!drawing.value || modal.value || shape.value !== "polygon" || !pixel) return false;
  pen = startStroke(point, pixel);
  window.addEventListener("mouseup", endPen);
  return false;
}

function endDrag() {
  window.removeEventListener("mouseup", endDrag);
  dragIndex = null;
}

function endPen() {
  window.removeEventListener("mouseup", endPen);
  if (!pen) return;
  const stroke = pen;
  pen = null;
  const ring = strokeRing(stroke);
  if (ring) {
    error.value = "";
    openModal(ring);
    return;
  }
  points.value = [...points.value, stroke.points[0]];
  globe?.setDraft(points.value, points.value.length);
}

function onMapClick(point) {
  if (!drawing.value || modal.value || shape.value === "polygon") return;
  if (!anchor.value) {
    anchor.value = point;
    globe?.setDraft([point], 1);
    return;
  }
  const ring = shape.value === "radius" ? circleRing(anchor.value, point) : squareRing(anchor.value, point);
  if (!ring) {
    error.value = "Draw a larger radius or square.";
    return;
  }
  error.value = "";
  openModal(ring);
}

function onMapMove(point, pixel) {
  if (dragIndex !== null && draft.value) {
    draft.value = moveVertex(draft.value, dragIndex, point);
    globe?.setDraft(draft.value, draft.value.length);
    return;
  }
  if (!drawing.value || modal.value) return;
  if (shape.value === "polygon") {
    if (pen && pixel) {
      pushStroke(pen, point, pixel);
      globe?.setDraft(pen.moved ? pen.points : [...points.value, point], pen.moved ? 0 : points.value.length);
      return;
    }
    if (!points.value.length) return;
    globe?.setDraft([...points.value, point], points.value.length);
    return;
  }
  if (!anchor.value) return;
  const ring = shape.value === "radius" ? circleRing(anchor.value, point) : squareRing(anchor.value, point);
  sizeLabel.value = formatKm(distanceM(anchor.value, point));
  globe?.setDraft(ring ?? [anchor.value], ring ? 0 : 1);
}

function selectedDeviceIds() {
  if (mode.value !== "ids") return [];
  const ids = deviceIds.value
    .split(/[\s,]+/)
    .filter(Boolean)
    .map((item) => Number(item));
  if (ids.length === 0 || ids.some((id) => !Number.isInteger(id))) {
    error.value = "Enter one or more device ids.";
    return null;
  }
  return ids;
}

async function save() {
  error.value = "";
  if (!draft.value) return;
  const ids = selectedDeviceIds();
  if (ids === null) return;
  if (editing.value) {
    await saveEdit(ids);
    return;
  }
  const body = { coordinates: draft.value, mode: mode.value };
  if (mode.value === "percent") body.percent = Number(percent.value);
  if (mode.value === "ids") body.device_ids = ids;
  pending.value = true;
  try {
    const created = await api("/subscriptions", { method: "POST", body });
    cancelDrawing();
    showAreas([...areas.value, created]);
    await load();
  } catch (err) {
    report(err);
  } finally {
    pending.value = false;
  }
}

async function saveEdit(ids) {
  const body = subscriptionPatch(editing.value, {
    coordinates: draft.value,
    mode: mode.value,
    percent: Number(percent.value),
    deviceIds: ids,
  });
  if (!body.coordinates && !body.device_ids && !body.mode) {
    error.value = "No changes to save.";
    return;
  }
  pending.value = true;
  try {
    const updated = await api(`/subscriptions/${editing.value.polygon_id}`, { method: "PATCH", body });
    editing.value = null;
    draft.value = null;
    globe?.setDraft(null);
    showAreas(areas.value.map((area) => (area.polygon_id === updated.polygon_id ? updated : area)));
    await load();
  } catch (err) {
    report(err);
  } finally {
    pending.value = false;
  }
}

async function removeArea(area) {
  if (!window.confirm(`Delete area ${area.polygon_id}?`)) return;
  error.value = "";
  pending.value = true;
  try {
    await api(`/subscriptions/${area.polygon_id}`, { method: "DELETE" });
    if (editing.value?.polygon_id === area.polygon_id) cancelEdit();
    await load();
  } catch (err) {
    report(err);
  } finally {
    pending.value = false;
  }
}

watch(devices, (next) => globe?.setDevices(next, alerts.value.devices, areas.value));

watch(alerts, () => {
  globe?.setAreas(areas.value, { alerted: alerts.value.polygons });
  paintDevices();
});

watch(shape, () => {
  points.value = [];
  anchor.value = null;
  sizeLabel.value = "";
  stopPen();
  if (!drawing.value) return;
  globe?.setDraft(null);
  globe?.setTool(shape.value);
});

async function loadControls() {
  try {
    const current = await api("/load");
    speedKmh.value = current.speed_kmh ?? "";
    batchSize.value = current.telemetry_batch_max_size ?? "";
  } catch (err) {
    loadError.value = typeof err?.message === "string" ? err.message : "Could not read load controls.";
  }
}

async function saveLoad() {
  const body = loadPatch(speedKmh.value, batchSize.value);
  if (!body.speed_kmh && !body.telemetry_batch_max_size) {
    loadError.value = "Enter a speed or a batch size.";
    return;
  }
  loadError.value = "";
  loadPending.value = true;
  try {
    const saved = await api("/load", { method: "PATCH", body });
    speedKmh.value = saved.speed_kmh ?? "";
    batchSize.value = saved.telemetry_batch_max_size ?? "";
  } catch (err) {
    loadError.value = typeof err?.message === "string" ? err.message : "Could not update load controls.";
  } finally {
    loadPending.value = false;
  }
}

onMounted(async () => {
  globe = createGlobe(mapHost.value, { onClick: onMapClick, onMove: onMapMove, onDown: onMapDown });
  paintDevices();
  await Promise.all([load(), loadControls()]);
});

onBeforeUnmount(() => {
  stopPen();
  endDrag();
  globe?.destroy();
  globe = null;
});
</script>

<template>
  <section class="subscriptions">
    <div ref="mapHost" class="globe"></div>
    <aside class="side card">
      <h1>Subscriptions</h1>
      <p class="muted">Draw a region on the globe, then choose which devices to follow there.</p>
      <form @submit.prevent="saveLoad">
        <fieldset class="shapes">
          <legend>Load</legend>
          <label>
            Speed km/h
            <input v-model="speedKmh" type="number" min="1" step="any" placeholder="50000" />
          </label>
          <label>
            Batch size
            <input v-model="batchSize" type="number" min="1" max="1000000" step="1" placeholder="1000" />
          </label>
          <p v-if="loadError" class="error">{{ loadError }}</p>
          <button type="submit" class="btn btn-primary" :disabled="loadPending">Apply</button>
        </fieldset>
      </form>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="actions">
        <button v-if="!drawing && !editing" type="button" class="btn btn-primary" @click="startDrawing">
          Create polygon
        </button>
        <button v-else-if="drawing" type="button" class="btn btn-outline-light" @click="cancelDrawing">Cancel</button>
      </div>

      <fieldset v-if="drawing" class="shapes">
        <legend>Shape</legend>
        <label class="pick"><input v-model="shape" type="radio" value="polygon" /> Any figure</label>
        <label class="pick"><input v-model="shape" type="radio" value="radius" /> Radius</label>
        <label class="pick"><input v-model="shape" type="radio" value="square" /> Square</label>
        <p class="muted">{{ hint }}</p>
        <p v-if="sizeLabel" class="muted">Size {{ sizeLabel }}</p>
        <div class="actions">
          <button
            v-if="shape === 'polygon'"
            type="button"
            class="btn btn-primary"
            :disabled="points.length < 3"
            @click="finishPolygon"
          >
            Use this polygon
          </button>
        </div>
      </fieldset>

      <fieldset v-else-if="editing" class="shapes">
        <legend>Area {{ editing.polygon_id }}</legend>
        <p class="muted">Drag a corner to reshape the polygon, or redraw it. Then choose which devices it follows.</p>
        <div class="actions">
          <button type="button" class="btn btn-outline-primary" @click="redrawArea">Redraw polygon</button>
        </div>
        <label class="pick"><input v-model="mode" type="radio" value="all" /> All devices</label>
        <label class="pick">
          <input v-model="mode" type="radio" value="percent" />
          Random percent
          <input v-model.number="percent" type="number" min="1" max="100" :disabled="mode !== 'percent'" />
        </label>
        <label class="pick">
          <input v-model="mode" type="radio" value="ids" />
          Device ids
          <input v-model="deviceIds" :disabled="mode !== 'ids'" placeholder="1, 2, 3" />
        </label>
        <div class="actions">
          <button type="button" class="btn btn-primary" :disabled="pending" @click="save">Save</button>
          <button type="button" class="btn btn-outline-light" @click="cancelEdit">Cancel</button>
        </div>
      </fieldset>

      <ul class="areas">
        <li v-for="area in areas" :key="area.polygon_id">
          <button type="button" class="area-jump" @click="focusArea(area)">
            <strong>Area {{ area.polygon_id }}</strong>
          </button>
          <span class="area-actions">
            <button type="button" class="btn btn-outline-light btn-sm" :disabled="pending" @click="beginEdit(area)">
              Edit
            </button>
            <button type="button" class="btn btn-outline-danger btn-sm" :disabled="pending" @click="removeArea(area)">
              Delete
            </button>
          </span>
        </li>
        <li v-if="areas.length === 0" class="muted">No subscriptions yet.</li>
      </ul>
    </aside>

    <div v-if="modal" class="modal-back">
      <form class="card dialog" @submit.prevent="save">
        <h2>Devices in this area</h2>
        <p class="muted">Choose which devices this subscription follows.</p>
        <label class="pick"><input v-model="mode" type="radio" value="all" /> All devices</label>
        <label class="pick">
          <input v-model="mode" type="radio" value="percent" />
          Random percent
          <input v-model.number="percent" type="number" min="1" max="100" :disabled="mode !== 'percent'" />
        </label>
        <label class="pick">
          <input v-model="mode" type="radio" value="ids" />
          Device ids
          <input v-model="deviceIds" :disabled="mode !== 'ids'" placeholder="1, 2, 3" />
        </label>
        <div class="actions">
          <button type="submit" class="btn btn-primary" :disabled="pending">Subscribe</button>
          <button type="button" class="btn btn-outline-light" @click="cancelDrawing">Cancel</button>
        </div>
      </form>
    </div>
  </section>
</template>
