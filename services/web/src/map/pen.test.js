import assert from "node:assert/strict";
import test from "node:test";

import { pushStroke, simplifyStroke, startStroke, strokeRing } from "./pen.js";

test("a click is not a freehand ring", () => {
  const stroke = startStroke([0, 0], { x: 0, y: 0 });
  assert.equal(strokeRing(stroke), null);
});

test("a drag becomes a ring", () => {
  const stroke = startStroke([0, 0], { x: 0, y: 0 });
  pushStroke(stroke, [1, 0], { x: 8, y: 0 });
  pushStroke(stroke, [1, 1], { x: 8, y: 10 });
  pushStroke(stroke, [1, 1], { x: 9, y: 11 });
  const ring = strokeRing(stroke);
  assert.equal(ring.length, 3);
  assert.deepEqual(ring[0], [0, 0]);
});

test("a long stroke is capped", () => {
  const points = Array.from({ length: 400 }, (_, index) => [index, index]);
  assert.equal(simplifyStroke(points, 32).length, 32);
});
