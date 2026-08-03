import assert from "node:assert/strict";
import test from "node:test";

import { formatIntegrityIssue, groupIntegrityIssues, integrityIssueHeadline } from "../src/lib/integrity.ts";

test("legacy hash findings become readable task and attempt evidence", () => {
  assert.deepEqual(
    formatIntegrityIssue("missing_grader_hash:public.brachy.dwell-time-scaling-001:0"),
    {
      code: "missing_grader_hash",
      label: "Grader hash missing",
      detail: "public.brachy.dwell-time-scaling-001 · attempt 1",
    },
  );
});

test("integrity headlines distinguish legacy gaps from comparison exclusions", () => {
  assert.equal(
    integrityIssueHeadline(["missing_grader_hash:a:0", "missing_prompt_hash:b:1"]),
    "Legacy contract gaps · 2 findings",
  );
  assert.equal(
    integrityIssueHeadline(["unranked_native_surface"]),
    "Comparison exclusions · 1 finding",
  );
});

test("unknown integrity codes remain readable without hiding detail", () => {
  assert.deepEqual(formatIntegrityIssue("unexpected_attempt_key:task-x:2:seed-3"), {
    code: "unexpected_attempt_key",
    label: "Unexpected attempt key",
    detail: "task-x · attempt 3 · seed-3",
  });
  assert.equal(integrityIssueHeadline([]), "Integrity checks passed");
});

test("large manifests group repeated findings without losing counts or examples", () => {
  assert.deepEqual(
    groupIntegrityIssues([
      "missing_grader_hash:task-a:0",
      "missing_grader_hash:task-b:1",
      "missing_grader_hash:task-c:2",
      "unranked_noncommon_surface",
    ]),
    [
      {
        code: "missing_grader_hash",
        label: "Grader hash missing",
        count: 3,
        examples: ["task-a · attempt 1", "task-b · attempt 2"],
      },
      {
        code: "unranked_noncommon_surface",
        label: "Non-common harness row is outcome-only",
        count: 1,
        examples: [],
      },
    ],
  );
});
