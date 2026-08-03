import assert from "node:assert/strict";
import test from "node:test";

import {
  buildScoreCertaintyFrontierRows,
  scoreMetricValue,
  certaintyRowLabel,
} from "../src/lib/scoreCertaintyFrontier.ts";

function row(overrides) {
  return {
    model_name: "model-a",
    provider: "ollama",
    execution_surface: "common_harness",
    run_profile: { is_common_harness: true },
    harness_name: "reference-json",
    harness_revision: "reference-json-v2",
    ranking_eligible: true,
    safe_success_rate: 0.6,
    token_usage: { median_total_tokens: 100, complete: true },
    duration_telemetry: { complete: true, observed_attempts: 30, expected_attempts: 30 },
    median_duration_seconds: 15,
    comparison_group: "group-a",
    ...overrides,
  };
}

test("default score-certainty slice keeps official, common-harness rows only", () => {
  const official = row({
    model_name: "official",
    family_cluster_safe_success_ci95: [0.4, 0.8],
    safe_success_rate: 0.5,
  });
  const commonUnranked = row({
    model_name: "common-unranked",
    ranking_eligible: false,
    family_cluster_safe_success_ci95: [0.2, 0.6],
  });
  const native = row({
    model_name: "native",
    provider: "codex-native",
    execution_surface: "recorded_output_import",
    run_profile: { is_common_harness: false },
    family_cluster_safe_success_ci95: [0.3, 0.8],
  });

  const result = buildScoreCertaintyFrontierRows([official, commonUnranked, native], "tokens", false);
  assert.equal(result.rows.length, 1);
  assert.equal(result.completeRows.length, 1);
  assert.equal(result.partialRows.length, 0);
  assert.equal(result.missingRows.length, 0);
  assert.equal(certaintyRowLabel(result.rows[0].kind), "Official comparison");
});

test("descriptive mode expands to outcome-only common and native rows", () => {
  const official = row({
    model_name: "official",
    family_cluster_safe_success_ci95: [0.4, 0.7],
  });
  const commonUnranked = row({
    model_name: "common-unranked",
    ranking_eligible: false,
    family_cluster_safe_success_ci95: [0.2, 0.8],
    token_usage: { median_total_tokens: 200, complete: true },
  });
  const partialNative = row({
    model_name: "native",
    provider: "codex-native",
    execution_surface: "recorded_output_import",
    run_profile: { is_common_harness: false },
    token_usage: { median_total_tokens: 300, complete: false },
    family_cluster_safe_success_ci95: [0.55, 0.95],
    rank_group: "native",
  });

  const result = buildScoreCertaintyFrontierRows([official, commonUnranked, partialNative], "tokens", true);
  assert.equal(result.rows.length, 3);
  assert.equal(result.completeRows.length, 2);
  assert.equal(result.partialRows.length, 1);
  assert.equal(result.missingRows.length, 0);
  assert.equal(result.frontierGroups.length, 1);
  assert.equal(result.rows[0].kind, "official");
  assert.equal(result.rows[1].kind, "common_unranked");
  assert.equal(result.rows[2].kind, "native_descriptive");
});

test("score-certainty frontier excludes dominated points within a comparison group", () => {
  const highEfficiency = row({
    model_name: "efficient-high",
    comparison_group: "frontier-group",
    token_usage: { median_total_tokens: 100, complete: true },
    safe_success_rate: 0.5,
    family_cluster_safe_success_ci95: [0.48, 0.52],
  });
  const dominated = row({
    model_name: "dominated",
    comparison_group: "frontier-group",
    token_usage: { median_total_tokens: 200, complete: true },
    safe_success_rate: 0.4,
    family_cluster_safe_success_ci95: [0.35, 0.45],
  });
  const frontierBetter = row({
    model_name: "frontier-better",
    comparison_group: "frontier-group",
    token_usage: { median_total_tokens: 250, complete: true },
    safe_success_rate: 0.7,
    family_cluster_safe_success_ci95: [0.65, 0.75],
  });

  const result = buildScoreCertaintyFrontierRows([highEfficiency, dominated, frontierBetter], "tokens", false);
  assert.equal(result.frontierGroups.length, 1);
  const frontier = result.frontierGroups[0].rows.map((item) => item.row.model_name);
  assert.deepEqual(frontier, ["efficient-high", "frontier-better"]);
});

test("metric mapping returns null for missing values", () => {
  assert.equal(
    scoreMetricValue(row({ token_usage: { median_total_tokens: null, complete: true }, median_duration_seconds: NaN }), "tokens"),
    null,
  );
  assert.equal(
    scoreMetricValue(row({ median_duration_seconds: 12, token_usage: { median_total_tokens: 999, complete: true } }), "time"),
    12,
  );
});
