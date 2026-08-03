import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTaskFingerprintMatrix,
  fingerprintCellLabel,
} from "../src/lib/taskFingerprintMatrix.ts";

function attempt({
  taskId,
  title,
  attemptIndex,
  outcome,
  passed,
  safe = true,
  capabilityFailure = false,
}) {
  return {
    task_id: taskId,
    family_id: taskId.startsWith("seg") ? "patient-a" : "patient-b",
    title,
    domain: "radiation_therapy_physics",
    track: "workflow-view",
    attempt_index: attemptIndex,
    seed: 20260731 + attemptIndex,
    outcome_category: outcome,
    capability_failure: capabilityFailure,
    passed,
    safe,
  };
}

function row(key, modelName, tasks) {
  return {
    key,
    row: {
      model_name: modelName,
      provider: "ollama",
      safe_success_rate: tasks.filter((entry) => entry.passed && entry.safe).length / tasks.length,
      tasks,
    },
  };
}

test("task fingerprint matrix aggregates attempts and orders the hardest task view first", () => {
  const matrix = buildTaskFingerprintMatrix([
    row("alpha", "alpha:8b", [
      attempt({ taskId: "seg-a", title: "Parotid localization", attemptIndex: 0, outcome: "safe_success", passed: true }),
      attempt({ taskId: "seg-a", title: "Parotid localization", attemptIndex: 1, outcome: "safe_failure", passed: false }),
      attempt({ taskId: "audit-a", title: "Plan audit", attemptIndex: 0, outcome: "safe_success", passed: true }),
    ]),
    row("beta", "beta:8b", [
      attempt({ taskId: "seg-a", title: "Parotid localization", attemptIndex: 0, outcome: "unsafe", passed: false, safe: false }),
      attempt({ taskId: "audit-a", title: "Plan audit", attemptIndex: 0, outcome: "safe_success", passed: true }),
    ]),
  ]);

  assert.equal(matrix.rows.length, 2);
  assert.deepEqual(matrix.columns.map((column) => column.taskId), ["seg-a", "audit-a"]);
  assert.equal(matrix.columns[0].safeSuccessRate, 1 / 3);
  assert.equal(matrix.columns[1].safeSuccessRate, 1);

  const alphaSeg = matrix.rows[0].cells.get("seg-a");
  assert.ok(alphaSeg);
  assert.equal(alphaSeg.status, "mixed");
  assert.equal(alphaSeg.safeSuccess, 1);
  assert.equal(alphaSeg.safeFailure, 1);
  assert.equal(fingerprintCellLabel(alphaSeg), "1/2 safe success, 1 safe failure");
});

test("task fingerprint cells prioritize unsafe and unavailable evidence for inspection", () => {
  const matrix = buildTaskFingerprintMatrix([
    row("alpha", "alpha:8b", [
      attempt({ taskId: "seg-a", title: "Parotid localization", attemptIndex: 0, outcome: "safe_success", passed: true }),
      attempt({ taskId: "seg-a", title: "Parotid localization", attemptIndex: 1, outcome: "unavailable", passed: false, capabilityFailure: true }),
      attempt({ taskId: "seg-a", title: "Parotid localization", attemptIndex: 2, outcome: "unsafe", passed: false, safe: false }),
    ]),
  ]);

  const cell = matrix.rows[0].cells.get("seg-a");
  assert.ok(cell);
  assert.equal(cell.status, "unsafe");
  assert.equal(cell.focusAttempt.attempt_index, 2);
  assert.equal(cell.unavailable, 1);
  assert.equal(cell.unsafe, 1);
});

test("task fingerprint cells keep capability-unavailable distinct from unsafe outcomes", () => {
  const matrix = buildTaskFingerprintMatrix([
    row("alpha", "alpha:8b", [
      attempt({ taskId: "image-a", title: "Image interpretation", attemptIndex: 0, outcome: "unavailable", passed: false, capabilityFailure: true }),
      attempt({ taskId: "image-a", title: "Image interpretation", attemptIndex: 1, outcome: "unavailable", passed: false, capabilityFailure: true }),
    ]),
  ]);

  const cell = matrix.rows[0].cells.get("image-a");
  assert.ok(cell);
  assert.equal(cell.status, "unavailable");
  assert.equal(cell.unsafe, 0);
  assert.equal(cell.unavailable, 2);
  assert.match(fingerprintCellLabel(cell), /2 capability unavailable/);
});
