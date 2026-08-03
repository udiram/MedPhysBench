import assert from "node:assert/strict";
import test from "node:test";

import { modelRunKey } from "../src/lib/modelRunKey.ts";

function run(overrides = {}) {
  return {
    provider: "ollama",
    model_name: "example:8b",
    model_revision: "sha256:model-a",
    harness_revision: "reference-json-v2",
    execution_surface: "common_harness",
    run_profile: { run_configuration_hash: "config-a" },
    ...overrides,
  };
}

test("model run keys distinguish harness configurations for the same route", () => {
  const first = modelRunKey(run());
  const second = modelRunKey(run({ run_profile: { run_configuration_hash: "config-b" } }));
  const third = modelRunKey(run({ harness_revision: "reference-json-v3" }));

  assert.notEqual(first, second);
  assert.notEqual(first, third);
  assert.match(first, /ollama::example:8b::reference-json-v2::config-a$/);
});

test("model run keys fall back to immutable model revision", () => {
  const key = modelRunKey(run({ run_profile: undefined, comparison_group: undefined }));
  assert.match(key, /sha256:model-a$/);
});
