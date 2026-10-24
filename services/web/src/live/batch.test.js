import assert from "node:assert/strict";
import test from "node:test";

import { arrivalsState, deviceFeatures, mergeDevices, unpackPoints } from "./batch.js";

test("unpack keeps only the devices in the buffer", () => {
  const buffer = new ArrayBuffer(40);
  const view = new DataView(buffer);
  writePoint(view, 0, 7, 55.75, 37.61, 1_700_000_000);
  writePoint(view, 20, 9, 48.85, 2.35, 1_700_000_100);

  const devices = unpackPoints(buffer);

  assert.equal(devices.size, 2);
  assert.ok(Math.abs(devices.get(7).latitude - 55.75) < 0.001);
  assert.ok(Math.abs(devices.get(7).longitude - 37.61) < 0.001);
  assert.equal(devices.get(9).timestamp, 1_700_000_100);
});

test("merge updates devices from the batch and leaves the rest", () => {
  const current = {
    1: { latitude: 1, longitude: 2, timestamp: 3 },
    4: { latitude: 10, longitude: 20, timestamp: 30 },
  };
  const updates = new Map([[4, { latitude: 11, longitude: 21, timestamp: 31 }]]);

  const merged = mergeDevices(current, updates);

  assert.deepEqual(merged[1], current[1]);
  assert.equal(merged[4].latitude, 11);
  assert.equal(merged[4].longitude, 21);
  assert.equal(merged[4].timestamp, 31);
  assert.ok(merged[4].direction > 0 && merged[4].direction < 90);
  assert.equal(current[4].latitude, 10);
});

test("merge stores the heading from the previous position", () => {
  const current = {
    1: { latitude: 0, longitude: 0, timestamp: 1, direction: 180 },
    2: { latitude: 0, longitude: 179, timestamp: 1, direction: 0 },
    3: { latitude: 10, longitude: 10, timestamp: 1, direction: 45 },
  };
  const updates = new Map([
    [1, { latitude: 0, longitude: 10, timestamp: 2 }],
    [2, { latitude: 0, longitude: -179, timestamp: 2 }],
    [3, { latitude: 10, longitude: 10, timestamp: 2 }],
    [4, { latitude: 5, longitude: 5, timestamp: 2 }],
  ]);

  const merged = mergeDevices(current, updates);

  assert.ok(Math.abs(merged[1].direction - 90) < 0.01);
  assert.ok(Math.abs(merged[2].direction - 90) < 0.01);
  assert.equal(merged[3].direction, 45);
  assert.equal(merged[4].direction, 0);
});

test("device features use longitude then latitude", () => {
  const features = deviceFeatures({
    7: { latitude: 55.75, longitude: 37.61, timestamp: 1 },
    8: { latitude: Number.NaN, longitude: 1, timestamp: 1 },
  });

  assert.equal(features.features.length, 1);
  assert.deepEqual(features.features[0].geometry.coordinates, [37.61, 55.75]);
  assert.equal(features.features[0].properties.id, 7);
  assert.equal(features.features[0].properties.direction, 0);
});

test("arrivals replace the devices and areas that stay inside", () => {
  const inside = arrivalsState([
    { user_id: 1, device_id: 7, polygon_id: 3 },
    { user_id: 1, device_id: 8, polygon_id: 3 },
    { user_id: 1, device_id: 9, polygon_id: 4 },
  ]);
  const left = arrivalsState([{ user_id: 1, device_id: 8, polygon_id: 3 }]);

  assert.deepEqual(inside.devices, { 7: true, 8: true, 9: true });
  assert.deepEqual(inside.polygons, { 3: true, 4: true });
  assert.deepEqual(left.devices, { 8: true });
  assert.deepEqual(left.polygons, { 3: true });
  assert.deepEqual(arrivalsState([]), { devices: {}, polygons: {} });
});

test("device features keep a stored heading", () => {
  const features = deviceFeatures({
    7: { latitude: 1, longitude: 2, timestamp: 1, direction: 90 },
    8: { latitude: 1, longitude: 2, timestamp: 1, direction: 450 },
  });

  assert.equal(features.features[0].properties.direction, 90);
  assert.equal(features.features[1].properties.direction, 90);
});

test("a device inside an area carries the alert flag", () => {
  const features = deviceFeatures(
    {
      7: { latitude: 1, longitude: 2, timestamp: 1, direction: 90 },
      8: { latitude: 3, longitude: 4, timestamp: 1, direction: 0 },
    },
    { 7: true },
  );

  assert.equal(features.features[0].properties.alert, 1);
  assert.equal(features.features[0].properties.unknown, 0);
  assert.equal(features.features[1].properties.alert, 0);
  assert.equal(features.features[1].properties.unknown, 0);
});

test("a device inside an area without a websocket arrival gets a question mark", () => {
  const features = deviceFeatures(
    {
      7: { latitude: 1, longitude: 2, timestamp: 1 },
      8: { latitude: 3, longitude: 4, timestamp: 1 },
    },
    { 8: true },
    { 7: true, 8: true },
  );

  assert.equal(features.features[0].properties.unknown, 1);
  assert.equal(features.features[0].properties.alert, 0);
  assert.equal(features.features[1].properties.unknown, 0);
  assert.equal(features.features[1].properties.alert, 1);
});

test("device features keep every finite position", () => {
  const devices = {};
  for (let id = 1; id <= 5; id += 1) {
    devices[id] = { latitude: id - 80, longitude: id * 10 - 30, timestamp: id };
  }

  const features = deviceFeatures(devices);

  assert.equal(features.features.length, 5);
  assert.deepEqual(
    features.features.map((feature) => feature.geometry.coordinates),
    [
      [-20, -79],
      [-10, -78],
      [0, -77],
      [10, -76],
      [20, -75],
    ],
  );
});

function writePoint(view, offset, id, latitude, longitude, timestamp) {
  view.setBigInt64(offset, BigInt(id), true);
  view.setFloat32(offset + 8, latitude, true);
  view.setFloat32(offset + 12, longitude, true);
  view.setUint32(offset + 16, timestamp, true);
}
