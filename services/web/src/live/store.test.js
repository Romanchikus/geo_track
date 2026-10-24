import assert from "node:assert/strict";
import test from "node:test";

import { nextInserted } from "./store.js";

test("inserted stays at the database count until the first total arrives", () => {
  assert.equal(nextInserted(120, null, 4), 120);
});

test("inserted adds rows stored after the session opened", () => {
  assert.equal(nextInserted(120, 4, 9), 125);
});

test("a missing count does not become NaN", () => {
  assert.equal(nextInserted(undefined, 4, 9), null);
  assert.equal(nextInserted(120, 4, Number.NaN), null);
});
