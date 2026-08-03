import assert from "node:assert/strict";
import test from "node:test";

import { compareModelRuns, modelRunKey, modelRunUrlSelection, releasedModelRunKey } from "../src/lib/modelRunKey.ts";

function run(overrides = {}) {
  return {
    provider: "ollama",
    model_name: "example:8b",
    model_revision: "sha256:model-a",
    harness_revision: "reference-json-v2",
    execution_surface: "common_harness",
    run_profile: { run_configuration_hash: "config-a" },
    ranking_eligible: true,
    safe_success_rate: 0.5,
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

test("released run keys keep same-release legacy and current rows independently renderable", () => {
  const current = releasedModelRunKey(run({ release_key: "core" }));
  const legacy = releasedModelRunKey(
    run({
      release_key: "core",
      harness_revision: "reference-json-v1",
      run_profile: { run_configuration_hash: "config-legacy" },
    }),
  );

  assert.notEqual(current, legacy);
  assert.match(current, /^core::ollama::example:8b::reference-json-v2::config-a$/);
  assert.match(legacy, /^core::ollama::example:8b::reference-json-v1::config-legacy$/);
});

test("run URL selection distinguishes same-release rows with different harness contracts", () => {
  const current = modelRunUrlSelection(run({ release_key: "core" }));
  const legacy = modelRunUrlSelection(
    run({
      release_key: "core",
      harness_revision: "reference-json-v1",
      run_profile: { run_configuration_hash: "config-legacy" },
    }),
  );

  assert.equal(current.runRelease, "core");
  assert.equal(legacy.runRelease, "core");
  assert.notEqual(current.runKey, legacy.runKey);
  assert.equal(current.runKey, modelRunKey(run({ release_key: "core" })));
});

test("current ranking contract is the default when legacy and v2 rows share a model", () => {
  const legacy = run({
    harness_revision: "reference-json-v1",
    run_profile: { run_configuration_hash: "config-legacy" },
    safe_success_rate: 0.9,
  });
  const current = run({ safe_success_rate: 0.5 });

  assert.deepEqual([legacy, current].sort(compareModelRuns), [current, legacy]);
});
