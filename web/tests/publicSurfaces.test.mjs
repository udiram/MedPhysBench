import assert from "node:assert/strict";
import { after, before, test } from "node:test";

import react from "@vitejs/plugin-react";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let server;
let AtAGlanceLeaderboard;
let EvalCatalogPage;

before(async () => {
  server = await createServer({
    appType: "custom",
    configFile: false,
    logLevel: "silent",
    plugins: [react()],
    root: new URL("..", import.meta.url).pathname,
    server: { middlewareMode: true },
  });
  ({ AtAGlanceLeaderboard } = await server.ssrLoadModule("/src/components/AtAGlanceLeaderboard.tsx"));
  ({ EvalCatalogPage } = await server.ssrLoadModule("/src/components/EvalCatalogPage.tsx"));
});

after(async () => server?.close());

function row(name, rank, score) {
  return {
    model_name: name,
    provider: "test",
    model_revision: `${name}-revision`,
    outcome_rank: rank,
    outcome_order_eligible: true,
    ranking_eligible: rank === 1,
    rank: rank === 1 ? 1 : null,
    completed_count: 1,
    expected_attempt_count: 1,
    error_count: 0,
    safe_success_rate: score,
    safety_gate_rate: 1,
    valid_output_rate: 1,
    integrity: { missing_attempt_keys: 0 },
    tasks: [],
  };
}

test("at-a-glance board preserves signed outcome order and never renders planned models", () => {
  const html = renderToStaticMarkup(React.createElement(AtAGlanceLeaderboard, {
    data: { models: [row("Second", 2, 0.7), row("First", 1, 0.8)], unranked_models: [] },
    modelCatalog: [],
    resultsScope: "descriptive",
  }));
  assert.ok(html.indexOf("First") < html.indexOf("Second"));
  assert.match(html, /Official #1/);
  assert.match(html, /exact-task-comparison/);
});

test("at-a-glance board collapses duplicate routes for the same base model", () => {
  const html = renderToStaticMarkup(React.createElement(AtAGlanceLeaderboard, {
    data: { models: [row("Route A", 1, 0.8), row("Route B", 2, 0.7)], unranked_models: [] },
    modelCatalog: [
      { provider: "test", model_name: "Route A", base_model_id: "shared-base", openness: "open" },
      { provider: "test", model_name: "Route B", base_model_id: "shared-base", openness: "open" },
    ],
    resultsScope: "descriptive",
  }));
  assert.match(html, /Route A/);
  assert.doesNotMatch(html, /Route B/);
});

test("eval catalog renders a released sealed input and a direct answer link", () => {
  const runtimeTask = {
    title: "Review a CT protocol",
    task_id: "ct-review",
    domain: "imaging_physics",
    track: "workflow",
    risk_tier: "tier_2_review_required",
    instructions: "Review the supplied CT protocol.",
    input_payload: { kvp: 120 },
    allowed_tools: [],
    context_artifacts: [],
    expected_output_schema: { type: "object" },
    safety: {},
    stop_conditions: {},
  };
  const html = renderToStaticMarkup(React.createElement(EvalCatalogPage, {
    catalog: { releases: [{ release_id: "release-a", tasks: [{ task_id: "ct-review", runtime_task_hash: "runtime-a", runtime_task: runtimeTask }] }] },
    catalogLoaded: true,
    data: {
      release: { release_id: "release-a", title: "Imaging release", description: "Released imaging tasks" },
      models: [],
      unranked_models: [],
    },
    releaseView: "imaging",
  }));
  assert.match(html, /Review the supplied CT protocol/);
  assert.match(html, /&quot;kvp&quot;: 120/);
  assert.match(html, /See model answers/);
  assert.match(html, /fx_task_query=ct-review/);
});

test("eval catalog shows comparison-group benchmark power without manufacturing cross-provider statistics", () => {
  const diagnostics = {
    release_id: "release-a",
    item_diagnostics: {
      groups: [
        {
          comparison_group: "groq::exact-config-a",
          model_count: 2,
          task_count: 10,
          family_count: 2,
          attempt_count: 60,
          tasks: [{ safe_success_rate: 0 }, { safe_success_rate: 1 }],
          summary: {
            best_system_safe_success_rate: 0.6,
            median_task_safe_success_rate: 0.5,
            median_task_discrimination: null,
            discrimination_task_count: 0,
            panel_solved_family_count: 0,
            near_zero_entropy_family_count: 2,
            watch_signals: [{ code: "near_zero_family_entropy_above_half", observed: 1 }],
          },
        },
        {
          comparison_group: "ollama::exact-config-b",
          model_count: 18,
          task_count: 10,
          family_count: 2,
          attempt_count: 540,
          tasks: [{ safe_success_rate: 0 }, { safe_success_rate: 0.5 }],
          summary: {
            best_system_safe_success_rate: 0.5,
            median_task_safe_success_rate: 0.03,
            median_task_discrimination: 0.54,
            discrimination_task_count: 5,
            panel_solved_family_count: 0,
            near_zero_entropy_family_count: 2,
            watch_signals: [{ code: "near_zero_family_entropy_above_half", observed: 1 }],
          },
        },
      ],
    },
  };
  const html = renderToStaticMarkup(React.createElement(EvalCatalogPage, {
    catalog: { releases: [{ release_id: "release-a", tasks: [] }] },
    catalogLoaded: true,
    data: {
      release: { release_id: "release-a", title: "Workflow release", description: "Released workflow tasks" },
      models: [],
      unranked_models: [],
    },
    diagnostics,
    releaseView: "real",
  }));

  assert.match(html, /The public response matrix shows floor effects/);
  assert.match(html, /20<\/dd>/);
  assert.match(html, /600<\/dd>/);
  assert.match(html, /Groq/);
  assert.match(html, /Ollama/);
  assert.match(html, /Not estimable/);
  assert.match(html, /0\.54/);
  assert.match(html, /public-development diagnostics/);
});
