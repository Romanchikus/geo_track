import assert from "node:assert/strict";
import test from "node:test";

import { areaCollection, areaLabel, createCoverage, ringCentroid, ringContains, unconfirmedDevices } from "./areas.js";
import { signedArea } from "./draft.js";
import { circleRing, squareRing } from "./shapes.js";

test("saved areas are labeled by polygon id", () => {
  assert.equal(areaLabel({ polygon_id: 4 }), "Area 4");
  const collection = areaCollection([
    {
      polygon_id: 4,
      coordinates: [
        [0, 0],
        [0, 2],
        [2, 2],
        [2, 0],
      ],
    },
  ]);
  const ring = collection.features[0].geometry.coordinates[0];
  assert.ok(signedArea(ring) > 0);
  assert.equal(collection.features[0].properties.label, "Area 4");
  assert.equal(collection.features[0].properties.alert, 0);
  const alerted = areaCollection(
    [
      {
        polygon_id: 4,
        coordinates: [
          [0, 0],
          [0, 2],
          [2, 2],
          [2, 0],
        ],
      },
      {
        polygon_id: 5,
        coordinates: [
          [3, 0],
          [3, 2],
          [5, 2],
          [5, 0],
        ],
      },
    ],
    { 4: true },
  );
  assert.equal(alerted.features[0].properties.alert, 1);
  assert.equal(alerted.features[1].properties.alert, 0);
});

test("circle and square outlines face counter-clockwise", () => {
  assert.ok(signedArea(circleRing([0, 0], [1, 0])) > 0);
  assert.ok(signedArea(squareRing([0, 0], [1, 1])) > 0);
});

test("a point inside an area is unknown until the websocket confirms it", () => {
  const square = [
    [0, 0],
    [2, 0],
    [2, 2],
    [0, 2],
  ];
  assert.equal(ringContains(square, [1, 1]), true);
  assert.equal(ringContains(square, [3, 1]), false);
  const devices = {
    7: { latitude: 1, longitude: 1 },
    8: { latitude: 1, longitude: 4 },
    9: { latitude: 1, longitude: 1 },
  };
  const areas = [{ coordinates: square, devices: [{ device_id: 7 }, { device_id: 9 }] }];

  assert.deepEqual(unconfirmedDevices(devices, areas, { 9: true }), { 7: true });
  assert.deepEqual(unconfirmedDevices({ 4: { latitude: 1, longitude: 1 } }, areas, {}), {});

  const coverage = createCoverage();
  const outside = {};
  for (let id = 0; id < 2000; id += 1) outside[id] = { latitude: 40, longitude: id };
  outside[7] = { latitude: 1, longitude: 1 };
  assert.deepEqual(coverage.unknown(outside, areas, {}), { 7: true });
  outside[7] = { latitude: 1, longitude: 1 };
  assert.deepEqual(coverage.unknown(outside, areas, { 7: true }), {});
  areas[0].coordinates = [
    [10, 10],
    [12, 10],
    [12, 12],
    [10, 12],
  ];
  assert.deepEqual(coverage.unknown(outside, areas, {}), {});
});

test("centroid sits inside a square", () => {
  const center = ringCentroid([
    [0, 0],
    [2, 0],
    [2, 2],
    [0, 2],
  ]);
  assert.ok(Math.abs(center[0] - 1) < 1e-9);
  assert.ok(Math.abs(center[1] - 1) < 1e-9);
});
