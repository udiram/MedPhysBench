import assert from "node:assert/strict";
import test from "node:test";

import { providerIdsForSlice } from "../src/lib/modelSlice.ts";

test("provider slices do not leak routes hidden by the active filter", () => {
  assert.deepEqual(
    providerIdsForSlice(["groq", "ollama"], ["groq"], "groq"),
    ["groq"],
  );
});

test("the unfiltered model registry retains every catalogued and observed route", () => {
  assert.deepEqual(
    providerIdsForSlice(["ollama", "groq"], ["groq", "custom"], "all"),
    ["custom", "groq", "ollama"],
  );
});
