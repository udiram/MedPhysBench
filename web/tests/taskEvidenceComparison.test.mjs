import assert from "node:assert/strict";
import test from "node:test";

import { bestPublishedTaskEvidence, representativeAttempt } from "../src/lib/taskEvidenceComparison.ts";

function attempt(outcome, score, attemptIndex = 0, runtimeHash = "runtime-a") {
  return {
    task_id: "task-a",
    title: "Task A",
    runtime_task_hash: runtimeHash,
    attempt_index: attemptIndex,
    seed: 100 + attemptIndex,
    outcome_category: outcome,
    score,
  };
}

function entry(key, modelName, tasks, overrides = {}) {
  return {
    key,
    row: {
      model_name: modelName,
      provider: "test",
      completed_count: tasks.length,
      expected_attempt_count: tasks.length,
      error_count: 0,
      safe_success_rate: 0.5,
      outcome_order_eligible: true,
      ranking_eligible: true,
      integrity: { missing_attempt_keys: 0 },
      tasks,
      ...overrides,
    },
  };
}

test("best task evidence uses task performance before overall leaderboard performance", () => {
  const reference = entry("selected", "Selected", [attempt("safe_failure", 0.8)]);
  const taskLeader = entry("leader", "Task leader", [attempt("safe_success", 1)], { safe_success_rate: 0.4 });
  const overallLeader = entry("overall", "Overall leader", [attempt("safe_failure", 0.9)], { safe_success_rate: 0.9 });
  const best = bestPublishedTaskEvidence([reference, taskLeader, overallLeader], reference, reference.row.tasks[0]);

  assert.equal(best.comparison.entry.key, "leader");
  assert.equal(best.attemptMatch, "exact_attempt");
});

test("representative attempt falls back only to the same sealed runtime input", () => {
  const reference = attempt("safe_failure", 0.5, 2);
  const sameInput = attempt("safe_success", 1, 0);
  const wrongInput = attempt("safe_success", 1, 2, "runtime-b");

  assert.deepEqual(representativeAttempt([wrongInput, sameInput], reference), {
    attempt: sameInput,
    kind: "same_runtime_input",
  });
  assert.equal(representativeAttempt([wrongInput], reference), null);
});

test("incomplete and outcome-ineligible rows cannot become the task leader", () => {
  const reference = entry("selected", "Selected", [attempt("safe_failure", 0.5)]);
  const quarantined = entry("bad", "Quarantined", [attempt("safe_success", 1)], {
    outcome_order_eligible: false,
  });
  const best = bestPublishedTaskEvidence([reference, quarantined], reference, reference.row.tasks[0]);
  assert.equal(best.comparison.entry.key, "selected");
});
