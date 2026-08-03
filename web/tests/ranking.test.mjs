import assert from "node:assert/strict";
import test from "node:test";

import { comparePointEstimateRows, competitionRankMap } from "../src/lib/ranking.ts";

function row(model_name, safe_success_rate, task_success_rate, safety_gate_rate, provider = "test") {
  return { model_name, provider, safe_success_rate, task_success_rate, safety_gate_rate };
}

test("exact point-estimate ties receive shared competition ranks", () => {
  const beta = row("beta", 0.8, 0.8, 1);
  const alpha = row("alpha", 0.8, 0.8, 1);
  const next = row("next", 0.7, 0.7, 1);
  const ranks = competitionRankMap([beta, next, alpha]);

  assert.equal(ranks.get(alpha), 1);
  assert.equal(ranks.get(beta), 1);
  assert.equal(ranks.get(next), 3);
  assert.deepEqual([beta, next, alpha].sort(comparePointEstimateRows).map((item) => item.model_name), [
    "alpha",
    "beta",
    "next",
  ]);
});

test("declared secondary metrics break a headline-score tie", () => {
  const safer = row("safer", 0.5, 0.5, 1);
  const lessSafe = row("less-safe", 0.5, 0.5, 0.8);
  const ranks = competitionRankMap([lessSafe, safer]);

  assert.equal(ranks.get(safer), 1);
  assert.equal(ranks.get(lessSafe), 2);
});
