import assert from "node:assert/strict";
import test from "node:test";

import {
  buildModelWorkbench,
  buildRunWorkbenchSummary,
  compactWorkbenchIdentity,
} from "../src/lib/modelWorkbench.ts";

function task({
  task_id,
  family_id = task_id,
  title,
  domain = "radiation_therapy_physics",
  passed,
  safe = true,
  outcome_category,
  capability_failure = false,
  failed_lanes = [],
  failed_graders = [],
  attempt_index = 0,
  seed = 0,
}) {
  return {
    task_id,
    family_id,
    title,
    domain,
    track: "public-core",
    passed,
    safe,
    outcome_category,
    capability_failure,
    failed_lanes,
    failed_graders,
    attempt_index,
    seed,
  };
}

function run(overrides = {}) {
  return {
    provider: "ollama",
    model_name: "example:8b",
    ranking_eligible: true,
    safe_success_rate: 0.5,
    safety_gate_rate: 0.75,
    valid_output_rate: 0.8,
    execution_surface: "common_harness",
    harness_name: "reference-json",
    harness_revision: "reference-json-v2",
    comparison_group: "common-v2",
    run_profile: {
      run_configuration_hash: "config-a",
      harness_revision: "reference-json-v2",
      is_common_harness: true,
    },
    median_duration_seconds: 12,
    duration_telemetry: { observed_attempts: 4, expected_attempts: 4 },
    token_usage: { median_total_tokens: 1200, observed_attempts: 4, expected_attempts: 4 },
    attempt_count: 4,
    completed_count: 4,
    expected_attempt_count: 4,
    release_id: "public-core-v0.6",
    release_key: "core",
    release_title: "Core release",
    tasks: [],
    ...overrides,
  };
}

test("run workbench summary builds a task-family outcome matrix and failure distributions", () => {
  const summary = buildRunWorkbenchSummary(
    run({
      tasks: [
        task({ task_id: "task-a", family_id: "family-a", title: "Plan review", passed: true, attempt_index: 0 }),
        task({
          task_id: "task-a",
          family_id: "family-a",
          title: "Plan review",
          passed: false,
          safe: true,
          outcome_category: "safe_failure",
          failed_lanes: ["decision"],
          failed_graders: ["schema"],
          attempt_index: 1,
        }),
        task({
          task_id: "task-b",
          family_id: "family-b",
          title: "Dose audit",
          passed: false,
          safe: false,
          outcome_category: "unsafe",
          failed_lanes: ["safety"],
          failed_graders: ["dose"],
        }),
        task({
          task_id: "task-c",
          family_id: "family-c",
          title: "Segmentation import",
          passed: false,
          safe: true,
          capability_failure: true,
          outcome_category: "unavailable",
        }),
      ],
    }),
  );

  assert.deepEqual(summary.outcomes, {
    safePass: 1,
    safeFail: 1,
    unsafe: 1,
    unavailable: 1,
    unknown: 0,
    total: 4,
  });
  assert.equal(summary.mixedFamilies, 1);
  assert.equal(summary.topFailureSignal, "safety");

  const familyA = summary.taskFamilies.find((family) => family.familyId === "family-a");
  const familyB = summary.taskFamilies.find((family) => family.familyId === "family-b");

  assert.ok(familyA);
  assert.ok(familyB);
  assert.equal(familyA.agreementLabel, "Mixed pass/fail");
  assert.equal(familyA.topLane, "decision");
  assert.equal(familyA.topGrader, "schema");
  assert.equal(familyB.unsafe, 1);
  assert.equal(summary.failureDomains[0][0], "Radiation Therapy");
  assert.equal(summary.failureLanes[0][0], "decision");
  assert.equal(summary.failureGraders[0][0], "dose");
});

test("model workbench keeps multiple harness runs of the same model separately comparable", () => {
  const legacy = run({
    harness_revision: "reference-json-v1",
    comparison_group: "legacy-v1",
    run_profile: {
      run_configuration_hash: "config-legacy",
      harness_revision: "reference-json-v1",
      is_common_harness: true,
    },
    safe_success_rate: 0.9,
    release_id: "public-core-v0.4",
    tasks: [task({ task_id: "task-a", title: "Plan review", passed: true })],
  });
  const current = run({
    safe_success_rate: 0.5,
    release_id: "public-core-v0.6",
    tasks: [
      task({ task_id: "task-a", title: "Plan review", passed: true }),
      task({
        task_id: "task-b",
        title: "Dose audit",
        passed: false,
        safe: true,
        outcome_category: "safe_failure",
        failed_lanes: ["decision"],
      }),
    ],
    attempt_count: 2,
    completed_count: 2,
    expected_attempt_count: 2,
    duration_telemetry: { observed_attempts: 2, expected_attempts: 2 },
    token_usage: { median_total_tokens: 1400, observed_attempts: 2, expected_attempts: 2 },
  });

  const workbench = buildModelWorkbench([legacy, current]);

  assert.equal(workbench.runSummaries.length, 2);
  assert.equal(workbench.runSummaries[0].run.harness_revision, "reference-json-v2");
  assert.equal(workbench.runSummaries[1].run.harness_revision, "reference-json-v1");
  assert.equal(workbench.runSummaries[0].configLabel, "config-a");
  assert.equal(workbench.runSummaries[1].configLabel, "config-legacy");
  assert.equal(workbench.overview.runCount, 2);
  assert.equal(workbench.overview.total, 3);
  assert.equal(workbench.overview.safePass, 2);
  assert.equal(workbench.overview.safeFail, 1);
});

test("compact workbench identities remain stable without dropping exact source data", () => {
  const exact = "recorded-output-provider-native-gpt-5-6-high-effort";

  assert.equal(compactWorkbenchIdentity("short-id", 22), "short-id");
  assert.equal(compactWorkbenchIdentity(undefined, 22), "Unavailable");
  assert.equal(compactWorkbenchIdentity(exact, 22), "recorded-output-…ffort");
  assert.equal(exact.startsWith(compactWorkbenchIdentity(exact, 22).split("…")[0]), true);
  assert.equal(exact.endsWith(compactWorkbenchIdentity(exact, 22).split("…")[1]), true);
});
