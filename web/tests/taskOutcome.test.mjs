import assert from "node:assert/strict";
import test from "node:test";

import { classifyAttemptOutcome, normalizeForensicsOutcome } from "../src/types.ts";

test("capability-unavailable attempts are classified separately from unsafe", () => {
  assert.equal(
    classifyAttemptOutcome({
      passed: false,
      safe: false,
      outcome_category: "unsafe",
      capability_failure: true,
    }),
    "unavailable",
  );
});

test("explicit unavailable outcome wins before boolean fallbacks", () => {
  assert.equal(
    classifyAttemptOutcome({
      passed: false,
      safe: false,
      outcome_category: "unavailable",
      capability_failure: false,
    }),
    "unavailable",
  );
});

test("forensics normalization preserves unavailable as a first-class outcome", () => {
  assert.equal(normalizeForensicsOutcome("unsafe", true), "unavailable");
  assert.equal(normalizeForensicsOutcome("unavailable", false), "unavailable");
  assert.equal(normalizeForensicsOutcome("unsafe", false), "unsafe");
});
