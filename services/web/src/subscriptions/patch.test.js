import assert from "node:assert/strict";
import test from "node:test";

import { subscriptionPatch } from "./patch.js";

const area = {
  coordinates: [
    [10, 10],
    [12, 10],
    [12, 12],
  ],
  devices: [{ device_id: 4 }, { device_id: 9 }],
};

test("a moved corner patches only the polygon", () => {
  const body = subscriptionPatch(area, {
    coordinates: [
      [10, 10],
      [13, 10],
      [12, 12],
    ],
    mode: "ids",
    deviceIds: [4, 9],
  });
  assert.deepEqual(body, {
    coordinates: [
      [10, 10],
      [13, 10],
      [12, 12],
    ],
  });
});

test("device scope patches replace the saved devices", () => {
  assert.deepEqual(subscriptionPatch(area, { coordinates: area.coordinates, mode: "all" }), { mode: "all" });
  assert.deepEqual(subscriptionPatch(area, { coordinates: area.coordinates, mode: "percent", percent: 25 }), {
    mode: "percent",
    percent: 25,
  });
  assert.deepEqual(subscriptionPatch(area, { coordinates: area.coordinates, mode: "ids", deviceIds: [9] }), {
    device_ids: [9],
  });
});

test("an unchanged subscription sends nothing", () => {
  const body = subscriptionPatch(area, { coordinates: area.coordinates, mode: "ids", deviceIds: [4, 9] });
  assert.deepEqual(body, {});
});
