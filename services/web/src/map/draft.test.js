import assert from "node:assert/strict";
import test from "node:test";

import { closedRing, draftCollection, signedArea } from "./draft.js";

test("a single click is a vertex", () => {
  const draft = draftCollection([[10, 20]], 1);
  assert.deepEqual(draft.features.map((item) => item.geometry.type), ["Point"]);
});

test("two clicks are a line with vertices", () => {
  const draft = draftCollection(
    [
      [0, 0],
      [1, 1],
    ],
    2,
  );
  assert.deepEqual(draft.features.map((item) => item.geometry.type), ["Point", "Point", "LineString"]);
});

test("the cursor preview is not a vertex", () => {
  const draft = draftCollection(
    [
      [0, 0],
      [1, 0],
      [1, 1],
    ],
    2,
  );
  const points = draft.features.filter((item) => item.geometry.type === "Point");
  assert.equal(points.length, 2);
  assert.equal(draft.features.some((item) => item.geometry.type === "Polygon"), true);
});

test("a finished ring closes the outline", () => {
  const draft = draftCollection(
    [
      [0, 0],
      [2, 0],
      [1, 2],
    ],
    0,
  );
  const line = draft.features.find((item) => item.geometry.type === "LineString");
  assert.deepEqual(line.geometry.coordinates[0], line.geometry.coordinates.at(-1));
  assert.equal(draft.features.some((item) => item.geometry.type === "Point"), false);
});

test("a clockwise ring is stored counter-clockwise", () => {
  const ring = closedRing([
    [0, 0],
    [0, 1],
    [1, 1],
    [1, 0],
  ]);
  assert.ok(signedArea(ring) > 0);
  assert.deepEqual(ring[0], ring.at(-1));
});
