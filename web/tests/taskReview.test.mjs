import assert from "node:assert/strict";
import test from "node:test";

import {
  feasibilityLabel,
  taskReviewFor,
  taskReviewLabel,
  taskReviewTone,
} from "../src/lib/taskReview.ts";

const pending = {
  task_id: "public.rt.example-001",
  reference_feasibility: "automated_pass",
  domain_review: "pending",
};

const evidence = {
  task_reviews: [pending],
};

test("task review lookup resolves one exact task and fails closed on missing evidence", () => {
  assert.equal(taskReviewFor(evidence, pending.task_id), pending);
  assert.equal(taskReviewFor(evidence, "public.rt.missing"), null);
  assert.equal(taskReviewFor(null, pending.task_id), null);
});

test("duplicate task-review records fail closed instead of choosing one", () => {
  assert.equal(taskReviewFor({ task_reviews: [pending, { ...pending }] }, pending.task_id), null);
});

test("pending physicist review stays distinct from automated feasibility", () => {
  assert.equal(taskReviewLabel(pending), "Physicist review pending");
  assert.equal(feasibilityLabel(pending), "Automated feasibility passed");
  assert.equal(taskReviewTone(pending), "warn");
});

test("revision-required review is surfaced as a blocking task-quality signal", () => {
  const revisionRequired = { ...pending, domain_review: "revision_required" };
  assert.equal(taskReviewLabel(revisionRequired), "Revision required");
  assert.equal(taskReviewTone(revisionRequired), "bad");
});
