import assert from "node:assert/strict";
import test from "node:test";

import { buildTaskComparison, tallyTaskOutcomes } from "../src/lib/taskComparison.ts";

function attempt(outcome, failedGraders = [], capabilityFailure = false, overrides = {}) {
  return {
    task_id: "task-a",
    title: "Task A",
    domain: "radiation_therapy_physics",
    outcome_category: outcome,
    capability_failure: capabilityFailure,
    failed_graders: failedGraders,
    ...overrides,
  };
}

function entry(key, modelName, tasks, overrides = {}) {
  return {
    key,
    source: "open",
    row: {
      model_name: modelName,
      provider: "test",
      tasks,
      ...overrides,
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

test("identical-harness comparison excludes mixed groups and native rows by default", () => {
  const reference = entry("reference", "Model A", [attempt("safe_success")], {
    comparison_group: "group-a",
    run_profile: { harness_revision: "harness-v2" },
  });
  const peer = entry("peer", "Model B", [attempt("safe_failure")], {
    comparison_group: "group-a",
    run_profile: { harness_revision: "harness-v2" },
  });
  const oldHarness = entry("old", "Model C", [attempt("safe_success")], {
    comparison_group: "group-a",
    run_profile: { harness_revision: "harness-v1" },
  });
  const otherGroup = entry("other", "Model D", [attempt("safe_success")], {
    comparison_group: "group-b",
    run_profile: { harness_revision: "harness-v2" },
  });
  const native = entry("native", "Model E", [attempt("safe_success")], {
    comparison_group: null,
    run_profile: { harness_revision: "native-import" },
  });

  const controlled = buildTaskComparison(
    [reference, peer, oldHarness, otherGroup, native],
    "task-a",
    { scope: "identical_harness", reference },
  );
  const broader = buildTaskComparison(
    [reference, peer, oldHarness, otherGroup, native],
    "task-a",
    { scope: "all_visible", reference },
  );

  assert.deepEqual(controlled.map((row) => row.entry.key), ["reference", "peer"]);
  assert.equal(broader.length, 5);
});

test("native reference has no implied controlled peers", () => {
  const reference = entry("native-a", "Native A", [attempt("safe_success")], {
    comparison_group: null,
    run_profile: { harness_revision: "native-import" },
  });
  const anotherNative = entry("native-b", "Native B", [attempt("safe_success")], {
    comparison_group: null,
    run_profile: { harness_revision: "native-import" },
  });

  const controlled = buildTaskComparison(
    [reference, anotherNative],
    "task-a",
    { scope: "identical_harness", reference },
  );

  assert.deepEqual(controlled.map((row) => row.entry.key), ["native-a"]);
});

test("task comparison can be pinned to one immutable runtime task hash", () => {
  const exact = entry("exact", "Exact", [
    attempt("safe_success", [], false, { runtime_task_hash: "runtime-a" }),
    attempt("safe_failure", [], false, { runtime_task_hash: "runtime-b" }),
  ]);
  const wrong = entry("wrong", "Wrong", [
    attempt("safe_success", [], false, { runtime_task_hash: "runtime-b" }),
  ]);

  const results = buildTaskComparison([exact, wrong], "task-a", { runtimeTaskHash: "runtime-a" });

  assert.equal(results.length, 1);
  assert.equal(results[0].entry.key, "exact");
  assert.equal(results[0].attempts.length, 1);
});
