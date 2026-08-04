import assert from "node:assert/strict";
import test from "node:test";

import { bestVerifiedTaskEvidence, publishedTaskEvidence, representativeAttempt, summarizeEvidenceValue } from "../src/lib/taskEvidenceComparison.ts";

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
  const best = bestVerifiedTaskEvidence([reference, taskLeader, overallLeader], reference, reference.row.tasks[0]);

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
  const best = bestVerifiedTaskEvidence([reference, quarantined], reference, reference.row.tasks[0]);
  assert.equal(best.comparison.entry.key, "selected");
});

test("task leader excludes descriptive rows even when they have the best output", () => {
  const reference = entry("selected", "Selected", [attempt("safe_failure", 0.5)]);
  const descriptive = entry("descriptive", "Descriptive", [attempt("safe_success", 1)], {
    ranking_eligible: false,
  });
  const verified = entry("verified", "Verified", [attempt("safe_success", 0.9)]);

  const best = bestVerifiedTaskEvidence([reference, descriptive, verified], reference, reference.row.tasks[0]);

  assert.equal(best.comparison.entry.key, "verified");
});

test("descriptive rows remain available as explicit exact-input comparison peers", () => {
  const reference = entry("selected", "Selected", [attempt("safe_failure", 0.5)]);
  const descriptive = entry("descriptive", "Descriptive", [attempt("safe_success", 1)], {
    ranking_eligible: false,
  });
  const verified = entry("verified", "Verified", [attempt("safe_success", 0.9)]);

  assert.deepEqual(
    publishedTaskEvidence([reference, descriptive, verified], reference, reference.row.tasks[0])
      .map((result) => result.comparison.entry.key),
    ["descriptive", "verified", "selected"],
  );
  assert.equal(bestVerifiedTaskEvidence([reference, descriptive, verified], reference, reference.row.tasks[0]).comparison.entry.key, "verified");
});

test("task leader rate uses only attempts with the exact runtime task hash", () => {
  const referenceTask = attempt("safe_failure", 0.5, 0, "runtime-a");
  const reference = entry("selected", "Selected", [referenceTask]);
  const exactLeader = entry("exact", "Exact leader", [
    attempt("safe_success", 1, 0, "runtime-a"),
    attempt("safe_failure", 0, 1, "runtime-b"),
  ]);
  const wrongRuntime = entry("wrong", "Wrong runtime", [
    attempt("safe_success", 1, 0, "runtime-b"),
    attempt("safe_success", 1, 1, "runtime-b"),
  ]);

  const best = bestVerifiedTaskEvidence([reference, exactLeader, wrongRuntime], reference, referenceTask);

  assert.equal(best.comparison.entry.key, "exact");
  assert.equal(best.comparison.attempts.length, 1);
  assert.equal(best.comparison.safeSuccessRate, 1);
});

test("output summaries stay readable without replacing exact JSON evidence", () => {
  assert.equal(summarizeEvidenceValue(true), "Yes");
  assert.equal(summarizeEvidenceValue([]), "None");
  assert.equal(
    summarizeEvidenceValue([[1, 2], [3, 4], [5, 6]], 2),
    "[1, 2] · [3, 4] · +1 more",
  );
});
