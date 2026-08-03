import assert from "node:assert/strict";
import test from "node:test";

import { defectsForTask } from "../src/lib/defects.ts";

const entries = [
  { defect_id: "MPB-2026-002", affected_task_ids: ["task-a"] },
  { defect_id: "MPB-2026-001", affected_task_ids: ["task-a", "task-b"] },
];

test("task defect lookup follows the deterministic public index", () => {
  const ledger = {
    entries,
    task_index: { "task-a": ["MPB-2026-002", "MPB-2026-001", "MPB-2026-002"] },
  };
  assert.deepEqual(
    defectsForTask(ledger, "task-a").map((entry) => entry.defect_id),
    ["MPB-2026-001", "MPB-2026-002"],
  );
});

test("legacy ledgers fall back to explicit affected task IDs", () => {
  assert.deepEqual(
    defectsForTask({ entries }, "task-b").map((entry) => entry.defect_id),
    ["MPB-2026-001"],
  );
  assert.deepEqual(defectsForTask({ entries }, "task-missing"), []);
  assert.deepEqual(defectsForTask(null, "task-a"), []);
});
