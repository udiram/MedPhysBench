import assert from "node:assert/strict";
import test from "node:test";

import { publicTaskInputFor } from "../src/lib/publicTaskInputs.ts";

const task = {
  task_id: "task-a",
  runtime_task_hash: "runtime-a",
  runtime_task: { instructions: "Do the work", input_payload: { value: 1 } },
};

test("public task input lookup requires one exact release, task, and runtime hash", () => {
  const catalog = { releases: [{ release_id: "release-a", tasks: [task] }] };
  assert.equal(
    publicTaskInputFor(catalog, "release-a", { task_id: "task-a", runtime_task_hash: "runtime-a" }),
    task,
  );
  assert.equal(
    publicTaskInputFor(catalog, "release-a", { task_id: "task-a", runtime_task_hash: "wrong" }),
    null,
  );
});

test("duplicate input records fail closed", () => {
  const catalog = { releases: [{ release_id: "release-a", tasks: [task, { ...task }] }] };
  assert.equal(
    publicTaskInputFor(catalog, "release-a", { task_id: "task-a", runtime_task_hash: "runtime-a" }),
    null,
  );
});
