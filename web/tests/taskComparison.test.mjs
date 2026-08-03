import assert from "node:assert/strict";
import test from "node:test";

import { buildTaskComparison, tallyTaskOutcomes } from "../src/lib/taskComparison.ts";

function attempt(outcome, failedGraders = [], capabilityFailure = false) {
  return {
    task_id: "task-a",
    title: "Task A",
    domain: "radiation_therapy_physics",
    outcome_category: outcome,
    capability_failure: capabilityFailure,
    failed_graders: failedGraders,
  };
}

function entry(key, modelName, tasks) {
  return {
    key,
    source: "open",
    row: {
      model_name: modelName,
      provider: "test",
      tasks,
    },
  };
}

test("task comparison sorts by safe success and preserves filtered run metadata", () => {
  const rows = [
    entry("lower", "Model B", [attempt("safe_success"), attempt("safe_failure", ["dice"])]),
    entry("higher", "Model A", [attempt("safe_success"), attempt("safe_success")]),
    entry("other", "Model C", [{ ...attempt("unsafe"), task_id: "task-b" }]),
  ];

  const comparison = buildTaskComparison(rows, "task-a");

  assert.deepEqual(comparison.map((row) => row.entry.key), ["higher", "lower"]);
  assert.equal(comparison[0].safeSuccessRate, 1);
  assert.equal(comparison[1].safeSuccessRate, 0.5);
  assert.equal(comparison[1].topFailedGrader, "dice");
  assert.equal(comparison[1].entry.source, "open");
});

test("capability failures remain unavailable rather than unsafe in task comparisons", () => {
  const counts = tallyTaskOutcomes([
    attempt("safe_failure", ["schema"], true),
    attempt("unsafe", ["safety"]),
    attempt(undefined),
  ]);

  assert.deepEqual(counts, {
    safe_success: 0,
    safe_failure: 0,
    unsafe: 1,
    unavailable: 1,
    inconclusive: 1,
  });
});

test("task comparison returns no rows when no task is selected", () => {
  assert.deepEqual(buildTaskComparison([], null), []);
});
