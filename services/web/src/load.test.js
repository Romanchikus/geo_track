import assert from "node:assert/strict";
import test from "node:test";

import { loadPatch } from "./load.js";

test("load patch sends only the filled controls", () => {
  assert.deepEqual(loadPatch("", ""), {});
  assert.deepEqual(loadPatch(120, ""), { speed_kmh: 120 });
  assert.deepEqual(loadPatch(80.5, 2500), {
    speed_kmh: 80.5,
    telemetry_batch_max_size: 2500,
  });
  assert.deepEqual(loadPatch(0, 1.2), {});
});
