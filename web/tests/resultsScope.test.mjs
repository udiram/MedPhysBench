import assert from "node:assert/strict";
import test from "node:test";

import {
  effectiveComparisonScope,
  resultsScopeCounts,
  rowVisibleInResultsScope,
  rowsForResultsScope,
} from "../src/lib/resultsScope.ts";

const official = { model_name: "official", ranking_eligible: true };
const descriptive = { model_name: "descriptive", ranking_eligible: false };
const undeclared = { model_name: "undeclared" };

test("descriptive scope keeps every published row on one surface", () => {
  assert.deepEqual(rowsForResultsScope([official, descriptive, undeclared], "descriptive"), [
    official,
    descriptive,
    undeclared,
  ]);
});

test("official scope admits only explicitly rank-eligible rows", () => {
  assert.equal(rowVisibleInResultsScope(official, "official"), true);
  assert.equal(rowVisibleInResultsScope(descriptive, "official"), false);
  assert.equal(rowVisibleInResultsScope(undeclared, "official"), false);
  assert.deepEqual(rowsForResultsScope([official, descriptive, undeclared], "official"), [official]);
});

test("scope counts never relabel descriptive rows as official", () => {
  assert.deepEqual(
    resultsScopeCounts({ models: [official], unranked_models: [descriptive, undeclared] }),
    { published: 3, official: 1, descriptive: 2 },
  );
  assert.deepEqual(resultsScopeCounts(null), { published: 0, official: 0, descriptive: 0 });
});

test("official scope overrides a broader local peer comparison", () => {
  assert.equal(effectiveComparisonScope("official", "all_visible"), "identical_harness");
  assert.equal(effectiveComparisonScope("descriptive", "all_visible"), "all_visible");
});
