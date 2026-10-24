import { defineStore } from "pinia";

import { api, apiBytes } from "../api";
import { arrivalsState, mergeDevices, unpackPoints } from "./batch";
import { openLiveSocket } from "./stream";

let closeSocket = null;

/** Running inserted total: database count plus rows stored since this session opened. */
export function nextInserted(base, origin, storedTotal) {
  if (!Number.isFinite(base) || !Number.isFinite(storedTotal)) return null;
  if (origin === null) return base;
  const added = storedTotal - origin;
  if (!Number.isFinite(added) || added < 0) return base;
  return base + added;
}

export const useLiveStore = defineStore("live", {
  state: () => ({
    storedPerSec: null,
    inserted: null,
    base: null,
    origin: null,
    running: false,
    devices: {},
    alerts: { devices: {}, polygons: {} },
    lastBatch: null,
  }),
  actions: {
    async start() {
      if (this.running) return;
      this.running = true;
      try {
        const stats = await api("/statistics");
        if (!this.running) return;
        const total = Number(stats.telemetry);
        if (!Number.isFinite(total)) throw new Error("statistics did not include a telemetry count");
        this.base = total;
        this.inserted = total;
        closeSocket = openLiveSocket((body) => this.apply(body));
      } catch (error) {
        this.running = false;
        console.error("live statistics failed", error);
      }
    },
    stop() {
      this.running = false;
      closeSocket?.();
      closeSocket = null;
      this.storedPerSec = null;
      this.inserted = null;
      this.base = null;
      this.origin = null;
      this.devices = {};
      this.alerts = { devices: {}, polygons: {} };
      this.lastBatch = null;
    },
    apply(body) {
      if (body?.type === "arrivals") {
        this.alerts = arrivalsState(body.data);
        return;
      }
      if (typeof body.stored === "number") this.storedPerSec = body.stored;
      if (typeof body.batch === "number") this.useBatch(body.batch);
      if (typeof body.stored_total !== "number" || !Number.isFinite(this.base)) return;
      if (this.origin === null) this.origin = body.stored_total;
      const inserted = nextInserted(this.base, this.origin, body.stored_total);
      if (inserted !== null) this.inserted = inserted;
    },
    useBatch(id) {
      if (id === this.lastBatch) return;
      this.loadBatch(id);
    },
    async loadBatch(id) {
      const previous = this.lastBatch;
      this.lastBatch = id;
      try {
        const buffer = await apiBytes(`/telemetry/batches/${id}`);
        if (this.lastBatch !== id) return;
        this.devices = mergeDevices(this.devices, unpackPoints(buffer));
      } catch (error) {
        if (this.lastBatch === id && error?.status !== 404) this.lastBatch = previous;
        console.error("telemetry batch failed", error);
      }
    },
  },
});
