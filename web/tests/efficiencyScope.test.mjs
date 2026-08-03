import assert from "node:assert/strict";
import test from "node:test";

import {
  buildComparisonScopes,
  limitEvidenceRows,
  runComparisonScopeKey,
} from "../src/lib/efficiencyScope.ts";

function run(overrides = {}) {
  return {
    provider: "ollama",
    model_name: "example:8b",
    harness_name: "reference-json",
    harness_revision: "reference-json-v2",
    execution_surface: "common_harness",
    ranking_eligible: true,
    safe_success_rate: 0.5,
    ...overrides,
  };
}

test("comparison scopes preserve frozen harness identity", () => {
  const current = run({ comparison_group: "local-v2" });
  const legacy = run({ comparison_group: "local-v1", harness_revision: "reference-json-v1" });
  const native = run({
    provider: "codex-native",
    comparison_group: undefined,
    execution_surface: "native",
    harness_name: "recorded-batch",
    harness_revision: "codex-native-pilot-v1",
  });

  assert.equal(runComparisonScopeKey(current), "local-v2");
  assert.notEqual(runComparisonScopeKey(current), runComparisonScopeKey(legacy));
  assert.match(runComparisonScopeKey(native), /^native::codex-native::recorded-batch::/);

  const scopes = buildComparisonScopes([
    current,
    legacy,
    run({ model_name: "second:8b", comparison_group: "local-v2" }),
    native,
  ]);
  assert.equal(scopes.length, 3);
  assert.equal(scopes[0].key, "local-v2");
  assert.equal(scopes[0].rows.length, 2);
});

test("dense evidence views default to a bounded row count without deleting data", () => {
  const rows = Array.from({ length: 29 }, (_, index) => index);
  assert.deepEqual(limitEvidenceRows(rows, false, 14), rows.slice(0, 14));
  assert.deepEqual(limitEvidenceRows(rows, true, 14), rows);
  assert.deepEqual(rows, Array.from({ length: 29 }, (_, index) => index));
});
