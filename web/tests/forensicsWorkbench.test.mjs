import assert from "node:assert/strict";
import test from "node:test";

import {
  matchesForensicsRunQuery,
  matchesForensicsTaskQuery,
  selectForensicsTaskWindow,
  sortForensicsTasks,
} from "../src/lib/forensicsWorkbench.ts";

function task(overrides = {}) {
  return {
    task_id: "task-a",
    title: "Plan review",
    domain: "radiation_therapy",
    track: "workflow",
    safe: true,
    attempt_index: 0,
    failed_lanes: [],
    failed_graders: [],
    ...overrides,
  };
}

test("run query matches model/provider/harness identity across separators", () => {
  const row = {
    provider: "openai",
    model_name: "gpt-5.6-sol",
    harness_revision: "reference-json-v2",
    comparison_group: "common-v2",
    execution_surface: "common_harness",
    run_profile: {
      harness_revision: "reference-json-v2",
      run_configuration_hash: "cfg-a",
    },
  };

  assert.equal(matchesForensicsRunQuery(row, "gpt 5.6 sol"), true);
  assert.equal(matchesForensicsRunQuery(row, "openai cfg-a"), true);
  assert.equal(matchesForensicsRunQuery(row, "common harness"), true);
  assert.equal(matchesForensicsRunQuery(row, "anthropic"), false);
});

test("opaque configuration hashes cannot satisfy short model-version tokens", () => {
  const row = {
    provider: "ollama",
    model_name: "qwen3.5:4b",
    harness_revision: "reference-json-v2",
    comparison_group: "real-pilot-v0.6",
    execution_surface: "common_harness",
    run_profile: {
      harness_revision: "reference-json-v2",
      run_configuration_hash: "bf8cca6e670e07b89164dc216cfa0365b0600bcf3412783c08065d42c036cdff",
    },
  };

  assert.equal(matchesForensicsRunQuery(row, "qwen 3.6"), false);
  assert.equal(matchesForensicsRunQuery(row, "bf8cca6e670e"), true);
});

test("task query matches family, failure lane, grader, and failure kind", () => {
  const row = task({
    task_id: "rt-plan-001",
    family_id: "rt-plan",
    title: "VMAT plan review",
    failed_lanes: ["decision"],
    failed_graders: ["dose_bounds"],
    model_failure_kind: "provider_output_contract_failure",
    error_type: "schema_violation",
  });

  assert.equal(matchesForensicsTaskQuery(row, "rt plan"), true);
  assert.equal(matchesForensicsTaskQuery(row, "dose bounds"), true);
  assert.equal(matchesForensicsTaskQuery(row, "provider output"), true);
  assert.equal(matchesForensicsTaskQuery(row, "segmentation"), false);
});

test("opaque attempt IDs require a deliberate long identifier query", () => {
  const row = task({
    attempt_id: "c92e7fe3f86cb994b205ef27736166bacc10dc3c99969c88266959c2aa92a46c",
  });

  assert.equal(matchesForensicsTaskQuery(row, "92 46"), false);
  assert.equal(matchesForensicsTaskQuery(row, "c92e7fe3f86c"), true);
});

test("task sorting prioritizes unsafe and failing attempts before successes", () => {
  const ordered = sortForensicsTasks([
    task({ task_id: "safe", title: "Safe success", outcome_category: "safe_success", passed: true }),
    task({ task_id: "unavailable", title: "Unavailable", outcome_category: "unavailable", capability_failure: true }),
    task({
      task_id: "unsafe",
      title: "Unsafe",
      outcome_category: "unsafe",
      safe: false,
      failed_lanes: ["safety", "decision"],
      failed_graders: ["dose"],
    }),
    task({
      task_id: "safe-fail",
      title: "Safe fail",
      outcome_category: "safe_failure",
      passed: false,
      failed_lanes: ["decision"],
    }),
  ]);

  assert.deepEqual(
    ordered.map((entry) => entry.task_id),
    ["unsafe", "safe-fail", "unavailable", "safe"],
  );
});

test("task window keeps a deep-linked selected attempt even beyond the render limit", () => {
  const tasks = [
    task({ task_id: "task-1", attempt_id: "attempt-1", title: "Task 1" }),
    task({ task_id: "task-2", attempt_id: "attempt-2", title: "Task 2" }),
    task({ task_id: "task-3", attempt_id: "attempt-3", title: "Task 3" }),
  ];

  const windowed = selectForensicsTaskWindow(tasks, 2, "attempt-3");

  assert.equal(windowed.length, 2);
  assert.deepEqual(
    windowed.map((entry) => entry.attempt_id),
    ["attempt-1", "attempt-3"],
  );
});
