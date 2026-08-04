import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import react from "@vitejs/plugin-react";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let server;
let TaskEvidenceComparison;

before(async () => {
  server = await createServer({
    appType: "custom",
    configFile: false,
    logLevel: "silent",
    plugins: [react()],
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true },
  });
  ({ TaskEvidenceComparison } = await server.ssrLoadModule("/src/components/TaskEvidenceComparison.tsx"));
});

after(async () => {
  await server?.close();
});

function task(modelValue, outcome, score) {
  return {
    attempt_id: modelValue.repeat(64).slice(0, 64),
    attempt_index: 0,
    domain: "radiation_therapy",
    duration_seconds: 2.4,
    grader_results: [{
      grader_id: "deterministic.answer",
      lane: "decision",
      passed: outcome === "safe_success",
      rationale: outcome === "safe_success" ? "Matched the reference contract." : "Dose value was outside tolerance.",
      required_for_pass: true,
      score,
      severity: "major",
    }],
    outcome_category: outcome,
    output: { answer_gy: modelValue === "a" ? 47.5 : 50, requires_escalation: false },
    runtime_task_hash: "runtime-a",
    safe: true,
    score,
    task_id: "task-a",
    title: "Independent dose check",
    token_usage: { available: true, input_tokens: 100, output_tokens: 20, total_tokens: 120 },
    track: "workflow",
  };
}

function entry(key, name, modelTask, rankingEligible) {
  return {
    key,
    row: {
      completed_count: 1,
      error_count: 0,
      expected_attempt_count: 1,
      integrity: { missing_attempt_keys: 0 },
      model_name: name,
      outcome_order_eligible: true,
      provider: "test-provider",
      ranking_eligible: rankingEligible,
      safe_success_rate: modelTask.outcome_category === "safe_success" ? 1 : 0,
      tasks: [modelTask],
    },
  };
}

function props(publicOutputs = true) {
  const selectedTask = task("a", "safe_failure", 0.4);
  const leaderTask = task("b", "safe_success", 1);
  const selected = entry("selected-run", "GPT-5.6", selectedTask, false);
  const leader = entry("leader-run", "Verified Leader", leaderTask, true);
  return {
    catalog: {
      schema_version: "medphysbench.public-task-inputs.v1",
      releases: [{
        release_id: "public-core-v0.4",
        tasks: [{
          runtime_task_hash: "runtime-a",
          task_id: "task-a",
          runtime_task: {
            allowed_tools: [],
            context_artifacts: [],
            domain: "radiation_therapy",
            expected_output_schema: { type: "object" },
            input_payload: { measured_dose_gy: 50 },
            instructions: "Check the independent dose and report the result.",
            risk_tier: "tier_2_review_required",
            safety: {},
            stop_conditions: {},
            task_id: "task-a",
            track: "workflow",
          },
        }],
      }],
    },
    catalogLoaded: true,
    entries: [selected, leader],
    publicOutputs,
    releaseEvidence: {
      evidence: {
        human_baseline: { completed: 0, note: "Not started", status: "not_started", target: 30 },
      },
    },
    releaseId: "public-core-v0.4",
    resultsScope: "descriptive",
    selected,
    selectedTask,
  };
}

test("comparison component renders exact input, selected output, verified leader, and human placeholder together", () => {
  const html = renderToStaticMarkup(React.createElement(TaskEvidenceComparison, props()));

  assert.match(html, /Check the independent dose and report the result/);
  assert.match(html, /GPT-5\.6/);
  assert.match(html, /Verified Leader/);
  assert.match(html, /Best verified model/);
  assert.match(html, /Coming soon/);
  assert.match(html, /No verified task-level human response is published/);
  assert.match(html, /answer gy/);
  assert.match(html, /View exact structured output/);
});

test("comparison component suppresses output bodies when the release is aggregate-only", () => {
  const html = renderToStaticMarkup(React.createElement(TaskEvidenceComparison, props(false)));
  const matches = html.match(/Output is not public for this release/g) ?? [];

  assert.equal(matches.length, 2);
  assert.doesNotMatch(html, /View exact structured output/);
});
