import assert from "node:assert/strict";
import test from "node:test";

import { signedArea } from "./draft.js";
import { unionRing } from "./union.js";

test("a simple ring stays in order", () => {
  assert.deepEqual(
    unionRing([
      [0, 0],
      [2, 0],
      [1, 2],
    ]),
    [
      [0, 0],
      [2, 0],
      [1, 2],
    ],
  );
});

test("a stroke that crosses itself becomes the solid outline", () => {
  const outline = unionRing([
    [0, 0],
    [4, 0],
    [4, 3],
    [1, 3],
    [1, 1],
    [3, 1],
    [3, 2],
    [0, 2],
  ]);
  assert.equal(outline.length >= 3, true);
  assert.ok(Math.abs(signedArea(outline) - 11) < 1e-6);
});
