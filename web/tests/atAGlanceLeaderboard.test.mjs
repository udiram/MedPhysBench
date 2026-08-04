import assert from "node:assert/strict";
import test from "node:test";

import { atAGlanceRows } from "../src/lib/atAGlanceLeaderboard.ts";

function row(name, rank, overrides = {}) {
  return {
    model_name: name,
    provider: "test",
    outcome_rank: rank,
    outcome_order_eligible: true,
    ranking_eligible: true,
    completed_count: 1,
    expected_attempt_count: 1,
    error_count: 0,
    safe_success_rate: 1 - rank / 10,
    safety_gate_rate: 1,
    valid_output_rate: 1,
    integrity: { missing_attempt_keys: 0 },
    ...overrides,
  };
}

test("glance rows preserve signed order, source filtering, completeness, and base-model deduplication", () => {
  const data = {
    models: [
      row("closed-first", 1),
      row("open-best-route", 2),
      row("open-duplicate-route", 3),
      row("incomplete", 4, { completed_count: 0 }),
    ],
    unranked_models: [],
  };
  const catalog = [
    { provider: "test", model_name: "closed-first", base_model_id: "closed", openness: "closed" },
    { provider: "test", model_name: "open-best-route", base_model_id: "open", openness: "open" },
    { provider: "test", model_name: "open-duplicate-route", base_model_id: "open", openness: "open" },
    { provider: "test", model_name: "incomplete", base_model_id: "incomplete", openness: "open" },
  ];

  assert.deepEqual(atAGlanceRows(data, catalog, "descriptive", "all").map((entry) => entry.model_name), [
    "closed-first",
    "open-best-route",
  ]);
  assert.deepEqual(atAGlanceRows(data, catalog, "descriptive", "open").map((entry) => entry.model_name), [
    "open-best-route",
  ]);
});
