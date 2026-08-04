import assert from "node:assert/strict";
import test from "node:test";

import { exactPeerAttempt, publicArtifactHref, runForensicsAccessibleLabel, taskAttemptKey, taskForensicsSelection } from "../src/lib/forensicsNavigation.ts";

test("attempt IDs remain the canonical forensic navigation key", () => {
  const task = {
    attempt_id: "a".repeat(64),
    task_id: "rt-plan-001",
    title: "Plan review",
    domain: "radiation_therapy",
    track: "workflow",
    safe: true,
  };

  assert.equal(taskAttemptKey(task), "a".repeat(64));
});

test("legacy fallback does not depend on filtered-list position", () => {
  const task = {
    task_id: "rt-plan-001",
    title: "Plan review",
    domain: "radiation_therapy",
    track: "workflow",
    run_id: "run-1",
    seed: 42,
    runtime_task_hash: "runtime-hash",
    safe: true,
  };

  assert.equal(
    taskAttemptKey(task),
    "rt-plan-001::noattempt::42::run-1::runtime-hash",
  );
});

test("public artifact links accept only repository result JSON paths", () => {
  assert.equal(
    publicArtifactHref("results/releases/pilot/model/attempt.json"),
    "https://github.com/udiram/MedPhysBench/blob/main/results/releases/pilot/model/attempt.json",
  );
  assert.equal(publicArtifactHref("results/releases/../private/attempt.json"), null);
  assert.equal(publicArtifactHref("governance/private.json"), null);
  assert.equal(publicArtifactHref("results/releases/pilot/model/attempt.txt"), null);
});

test("exact peer navigation preserves task, attempt, seed, and runtime contract", () => {
  const reference = {
    task_id: "task-a",
    attempt_index: 1,
    seed: 11,
    runtime_task_hash: "runtime-a",
  };
  const tasks = [
    { ...reference, attempt_index: 0 },
    { ...reference },
    { ...reference, seed: 12 },
  ];
  assert.equal(exactPeerAttempt(tasks, reference), tasks[1]);
  assert.equal(exactPeerAttempt([...tasks, { ...reference }], reference), null);
});

test("task drilldown binds the exact run and attempt without carrying stale filters", () => {
  const row = {
    provider: "groq",
    model_name: "llama-3.3-70b-versatile",
    model_revision: "provider-version-1",
    harness_name: "medphysbench-openai-compatible",
    harness_revision: "reference-json-v2",
    attempt_count: 30,
    completed_count: 30,
    error_count: 0,
    expected_attempt_count: 30,
    task_success_rate: 0.6,
    task_success_ci95: [0.4, 0.75],
    safe_success_rate: 0.6,
    safety_gate_rate: 1,
    valid_output_rate: 1,
    appropriate_escalation_rate: 1,
    critical_unsafe_action_rate: 0,
    any_pass_rate: 0.6,
    all_pass_rate: 0.6,
    average_duration_seconds: 1,
    median_duration_seconds: 1,
    lane_scores: {},
    domain_safe_success: {},
    ranking_eligible: false,
    integrity: {
      observed_attempt_keys: 30,
      missing_attempt_keys: 0,
      unexpected_attempt_keys: 0,
      integrity_errors: [],
    },
    tasks: [],
  };
  const task = {
    attempt_id: "b".repeat(64),
    task_id: "rt-plan-001",
    title: "Plan review",
    domain: "radiation_therapy",
    track: "workflow",
    safe: true,
  };

  const selection = taskForensicsSelection(row, task);

  assert.equal(selection.fx_provider, "groq");
  assert.equal(selection.fx_task, "b".repeat(64));
  assert.match(selection.fx_model, /groq/);
  assert.equal(selection.fx_domain, null);
  assert.equal(selection.fx_outcome, null);
});

test("same-model reruns receive distinct forensic action names", () => {
  const shared = {
    provider: "groq",
    model_name: "openai/gpt-oss-20b",
    harness_revision: "openai-chat-json-v1",
  };
  const current = runForensicsAccessibleLabel({
    ...shared,
    comparison_group: "groq::harness::config=a2805525e3c98399",
  });
  const historical = runForensicsAccessibleLabel({
    ...shared,
    comparison_group: "groq::harness::config=bf8cca6e670e07b8",
  });

  assert.notEqual(current, historical);
  assert.match(current, /configuration a2805525e3c98399/);
  assert.match(historical, /configuration bf8cca6e670e07b8/);
});
