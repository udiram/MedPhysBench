import assert from "node:assert/strict";
import test from "node:test";

import {
  buildSpotlightSelection,
  defaultSpotlightRunKey,
  spotlightRuns,
} from "../src/lib/evidenceSpotlight.ts";

function task(taskId, outcome, value, attemptIndex = 0) {
  return {
    task_id: taskId,
    title: `Task ${taskId}`,
    domain: "radiation_therapy_physics",
    track: "qa",
    outcome_category: outcome,
    safe: outcome !== "unsafe",
    attempt_index: attemptIndex,
    seed: 20260731 + attemptIndex,
    runtime_task_hash: `${taskId}-runtime`,
    output: { value },
    failed_graders: outcome === "safe_success" ? [] : ["exact_match.value"],
  };
}

function row(name, score, tasks, overrides = {}) {
  return {
    model_name: name,
    provider: "test",
    model_revision: "revision",
    attempt_count: tasks.length,
    completed_count: tasks.length,
    error_count: 0,
    expected_attempt_count: tasks.length,
    safe_success_rate: score,
    task_success_rate: score,
    task_success_ci95: [score, score],
    safety_gate_rate: 1,
    valid_output_rate: 1,
    appropriate_escalation_rate: null,
    critical_unsafe_action_rate: 0,
    any_pass_rate: score,
    all_pass_rate: score,
    average_duration_seconds: 1,
    median_duration_seconds: 1,
    lane_scores: {},
    domain_safe_success: {},
    ranking_eligible: true,
    outcome_order_eligible: true,
    comparison_group: "group-a",
    run_profile: { harness_revision: "harness-v2" },
    integrity: { observed_attempt_keys: tasks.length, missing_attempt_keys: 0, unexpected_attempt_keys: 0, integrity_errors: [] },
    tasks,
    ...overrides,
  };
}

function leaderboard(models, unrankedModels = []) {
  return {
    models,
    unranked_models: unrankedModels,
    tasks: [],
    release: {},
    integrity: {},
    methodology: {},
  };
}

test("default spotlight selects the second model in the strongest controlled group", () => {
  const best = row("Best", 0.8, [task("a", "safe_success", 8)]);
  const contrast = row("Contrast", 0.6, [task("a", "safe_failure", 7)]);
  const runs = spotlightRuns(leaderboard([best, contrast]));
  assert.equal(defaultSpotlightRunKey(runs), runs.find((run) => run.row.model_name === "Contrast").key);
});

test("spotlight finds a contrasting task and a safe identical-harness peer", () => {
  const best = row("Best", 0.8, [task("same", "safe_success", 8), task("other", "safe_failure", 2)]);
  const selected = row("Selected", 0.6, [task("same", "safe_failure", 7), task("other", "safe_success", 2)]);
  const state = buildSpotlightSelection(leaderboard([best, selected]));

  assert.equal(state.selected.row.model_name, "Selected");
  assert.equal(state.selectedAttempt.task.task_id, "same");
  assert.equal(state.selectedAttempt.outcome, "safe_failure");
  assert.equal(state.bestPeer.row.model_name, "Best");
  assert.equal(state.bestPeerAttempt.outcome, "safe_success");
  assert.equal(state.bestPeerSafeSuccessRate, 1);
});

test("native rows remain visible but do not gain a fabricated controlled peer", () => {
  const native = row("Native", 0.9, [task("a", "safe_success", 8)], {
    ranking_eligible: false,
    comparison_group: null,
    run_profile: { harness_revision: "native-v1" },
  });
  const common = row("Common", 0.8, [task("a", "safe_success", 8)]);
  const nativeKey = spotlightRuns(leaderboard([common], [native])).find((run) => run.row.model_name === "Native").key;
  const state = buildSpotlightSelection(leaderboard([common], [native]), nativeKey, "a");

  assert.equal(state.selected.row.model_name, "Native");
  assert.equal(state.bestPeer, null);
  assert.equal(state.bestPeerAttempt, null);
});

test("peer evidence matches the selected attempt contract exactly", () => {
  const best = row("Best", 0.8, [task("a", "safe_success", 8, 0), task("a", "safe_success", 8, 1)]);
  const selected = row("Selected", 0.6, [task("a", "safe_failure", 7, 1)]);
  const selectedKey = spotlightRuns(leaderboard([best, selected])).find((run) => run.row.model_name === "Selected").key;
  const state = buildSpotlightSelection(leaderboard([best, selected]), selectedKey, "a");

  assert.equal(state.selectedAttempt.task.attempt_index, 1);
  assert.equal(state.bestPeerAttempt.task.attempt_index, 1);
  assert.equal(state.bestPeerAttempt.task.seed, state.selectedAttempt.task.seed);
  assert.equal(state.bestPeerAttempt.task.runtime_task_hash, state.selectedAttempt.task.runtime_task_hash);
});

test("a missing exact peer attempt leaves the peer output unavailable", () => {
  const best = row("Best", 0.8, [task("a", "safe_success", 8, 0)]);
  const selected = row("Selected", 0.6, [task("a", "safe_failure", 7, 1)]);
  const selectedKey = spotlightRuns(leaderboard([best, selected])).find((run) => run.row.model_name === "Selected").key;
  const state = buildSpotlightSelection(leaderboard([best, selected]), selectedKey, "a");

  assert.equal(state.bestPeer.row.model_name, "Best");
  assert.equal(state.bestPeerAttempt, null);
  assert.equal(state.bestPeerSafeSuccessRate, 1);
});

test("incomplete and outcome-ineligible rows are excluded", () => {
  const complete = row("Complete", 0.8, [task("a", "safe_success", 8)]);
  const incomplete = row("Incomplete", 0.9, [task("a", "safe_success", 8)], { completed_count: 0 });
  const quarantined = row("Quarantined", 1, [task("a", "safe_success", 8)], { outcome_order_eligible: false });

  assert.deepEqual(
    spotlightRuns(leaderboard([complete, incomplete, quarantined])).map((run) => run.row.model_name),
    ["Complete"],
  );
});
