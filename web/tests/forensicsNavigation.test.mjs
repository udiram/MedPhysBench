import assert from "node:assert/strict";
import test from "node:test";

import { publicArtifactHref, taskAttemptKey } from "../src/lib/forensicsNavigation.ts";

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
