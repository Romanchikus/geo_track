import assert from "node:assert/strict";
import test from "node:test";

import { moveVertex, nearestVertex } from "./edit.js";

const ring = [
  [0, 0],
  [10, 0],
  [10, 10],
];

test("the closest corner within reach is the one to drag", () => {
  const project = (point) => ({ x: point[0], y: point[1] });
  assert.equal(nearestVertex(ring, { x: 11, y: 1 }, project), 1);
  assert.equal(nearestVertex(ring, { x: 40, y: 40 }, project), -1);
});

test("dragging a corner leaves the other corners in place", () => {
  assert.deepEqual(moveVertex(ring, 1, [14, 2]), [
    [0, 0],
    [14, 2],
    [10, 10],
  ]);
});
