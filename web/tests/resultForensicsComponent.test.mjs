import assert from "node:assert/strict";
import { after, afterEach, before, test } from "node:test";

import react from "@vitejs/plugin-react";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let server;
let ResultForensics;
let modelRunKey;
let taskAttemptKey;

before(async () => {
  server = await createServer({
    appType: "custom",
    configFile: false,
    logLevel: "silent",
    plugins: [react()],
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true },
  });
  ({ ResultForensics } = await server.ssrLoadModule("/src/components/ResultForensics.tsx"));
  ({ modelRunKey } = await server.ssrLoadModule("/src/lib/modelRunKey.ts"));
  ({ taskAttemptKey } = await server.ssrLoadModule("/src/lib/forensicsNavigation.ts"));
});

afterEach(() => {
  delete globalThis.window;
});

after(async () => {
  await server?.close();
});

function task({ attempt, model, outcome, runtime, score, taskId, title }) {
  return {
    attempt_id: attempt.repeat(64),
    attempt_index: attempt === "b" ? 1 : 0,
    domain: "radiation_therapy",
    duration_seconds: 2.4,
    failed_graders: outcome === "safe_success" ? [] : ["deterministic.answer"],
    failed_lanes: outcome === "safe_success" ? [] : ["decision"],
    grader_results: [{
      grader_id: "deterministic.answer",
      lane: "decision",
      passed: outcome === "safe_success",
      rationale: outcome === "safe_success" ? "Matched the frozen contract." : "Outside tolerance.",
      required_for_pass: true,
      score,
      severity: "major",
    }],
    outcome_category: outcome,
    output: { evidence_marker: model, requires_escalation: outcome !== "safe_success" },
    runtime_task_hash: runtime,
    safe: true,
    score,
    seed: 41,
    task_id: taskId,
    title,
    token_usage: { available: true, input_tokens: 100, output_tokens: 20, total_tokens: 120 },
    track: "workflow",
  };
}

function row({ modelName, provider, rankingEligible, tasks }) {
  return {
    attempt_count: tasks.length,
    completed_count: tasks.length,
    comparison_group: "controlled-group",
    error_count: 0,
    expected_attempt_count: tasks.length,
    harness_name: "medphysbench-test",
    harness_revision: "reference-json-v2",
    integrity: { integrity_errors: [], missing_attempt_keys: 0, observed_attempt_keys: tasks.length, unexpected_attempt_keys: 0 },
    median_duration_seconds: 2.4,
    model_name: modelName,
    model_revision: "immutable-test-revision",
    outcome_order_eligible: true,
    provider,
    rank: rankingEligible ? 1 : null,
    ranking_eligible: rankingEligible,
    safe_success_rate: rankingEligible ? 1 : 0,
    score_evidence_available: true,
    tasks,
    token_usage: { available_attempts: tasks.length, median_total_tokens: 120 },
  };
}

function fixture() {
  const selectedTasks = [
    task({ attempt: "a", model: "FIRST_OUTPUT", outcome: "unsafe", runtime: "runtime-first", score: 0, taskId: "task-first", title: "First unsafe check" }),
    task({ attempt: "b", model: "URL_SELECTED_OUTPUT", outcome: "safe_failure", runtime: "runtime-selected", score: 0.4, taskId: "task-selected", title: "Deep-linked calibration audit" }),
  ];
  const leaderTasks = [
    task({ attempt: "c", model: "LEADER_FIRST_OUTPUT", outcome: "safe_success", runtime: "runtime-first", score: 1, taskId: "task-first", title: "First unsafe check" }),
    { ...task({ attempt: "d", model: "OFFICIAL_TASK_LEADER", outcome: "safe_success", runtime: "runtime-selected", score: 1, taskId: "task-selected", title: "Deep-linked calibration audit" }), attempt_index: 1, seed: 41 },
  ];
  const selected = row({ modelName: "gpt-5.6-sol", provider: "codex-native", rankingEligible: false, tasks: selectedTasks });
  const leader = row({ modelName: "Verified Leader", provider: "groq", rankingEligible: true, tasks: leaderTasks });
  return {
    catalog: {
      schema_version: "medphysbench.public-task-inputs.v1",
      releases: [{
        release_id: "release-a",
        tasks: [{
          runtime_task_hash: "runtime-selected",
          task_id: "task-selected",
          runtime_task: {
            allowed_tools: [],
            context_artifacts: [],
            domain: "radiation_therapy",
            expected_output_schema: { type: "object" },
            input_payload: { chamber_reading: 48.7 },
            instructions: "Use the sealed chamber reading 48.7 and document the discrepancy.",
            risk_tier: "tier_2_review_required",
            safety: {},
            stop_conditions: {},
            task_id: "task-selected",
            track: "workflow",
          },
        }],
      }],
    },
    data: {
      models: [leader],
      release: { public_attempt_detail: "sanitized_output", release_id: "release-a" },
      unranked_models: [selected],
    },
    leader,
    selected,
    selectedTask: selectedTasks[1],
  };
}

function renderFixture({ catalogLoaded = true, catalogOverride, resultsScope = "descriptive" } = {}) {
  const data = fixture();
  const query = new URLSearchParams({
    fx_model: modelRunKey(data.selected),
    fx_peer: modelRunKey(data.leader),
    fx_task: taskAttemptKey(data.selectedTask),
  });
  globalThis.window = { location: new URL(`https://example.test/explore?${query}`) };
  const html = renderToStaticMarkup(React.createElement(ResultForensics, {
    data: data.data,
    defectLedger: null,
    modelCatalog: [
      { model_name: "gpt-5.6-sol", openness: "closed", provider: "codex-native" },
      { model_name: "Verified Leader", openness: "open", provider: "groq" },
    ],
    releaseView: "real",
    reviewEvidence: null,
    reviewEvidenceLoaded: true,
    resultsScope,
    releaseEvidence: { evidence: { human_baseline: { completed: 0, status: "not_started", target: 30 } } },
    taskInputCatalog: catalogOverride === undefined ? data.catalog : catalogOverride,
    taskInputCatalogLoaded: catalogLoaded,
  }));
  return { data, html };
}

test("deep-linked compare state resolves one exact model, task, input, and official task leader", () => {
  const { html } = renderFixture();

  assert.match(html, /Showing GPT-5\.6, task Deep-linked calibration audit, attempt 2\./);
  assert.match(html, /Use the sealed chamber reading 48\.7 and document the discrepancy/);
  assert.match(html, /URL_SELECTED_OUTPUT/);
  assert.match(html, /OFFICIAL_TASK_LEADER/);
  assert.match(html, /Best verified model: Verified Leader/);
  assert.match(html, /Best verified human response/);
});

test("an unresolved runtime hash fails closed instead of substituting a nearby task input", () => {
  const { data, html } = renderFixture({ catalogOverride: { ...fixture().catalog, releases: [] } });

  assert.match(html, /Exact input unavailable/);
  assert.match(html, /URL_SELECTED_OUTPUT/);
  assert.doesNotMatch(html, /Use the sealed chamber reading 48\.7/);
  assert.equal(data.selectedTask.runtime_task_hash, "runtime-selected");
});

test("catalog loading remains distinct from a missing exact input", () => {
  const { html } = renderFixture({ catalogLoaded: false, catalogOverride: null });

  assert.match(html, /Loading the exact runtime-visible task input/);
  assert.doesNotMatch(html, /Exact input unavailable/);
  assert.match(html, /URL_SELECTED_OUTPUT/);
});

test("official scope excludes a stale deep link to descriptive native evidence", () => {
  const { html } = renderFixture({ resultsScope: "official" });

  assert.doesNotMatch(html, /URL_SELECTED_OUTPUT/);
  assert.doesNotMatch(html, /Selected model: GPT-5\.6 Sol/);
  assert.match(html, /Verified Leader/);
});
