import assert from "node:assert/strict";
import test from "node:test";

import { scoreEvidenceAvailable, scoreEvidenceKind } from "../src/lib/resultEvidence.ts";

test("integrity-ineligible output-contract failures never become zero-score evidence", () => {
  const row = { outcome_order_eligible: false, ranking_eligible: false, safe_success_rate: 0 };
  assert.equal(scoreEvidenceAvailable(row), false);
  assert.equal(scoreEvidenceKind(row, false), "incomplete");
});

test("official and native evidence remain distinct while sharing one display surface", () => {
  assert.equal(scoreEvidenceKind({ outcome_order_eligible: true, ranking_eligible: true }, false), "official");
  assert.equal(scoreEvidenceKind({ outcome_order_eligible: true, ranking_eligible: false }, true), "native_descriptive");
  assert.equal(scoreEvidenceKind({ outcome_order_eligible: true, ranking_eligible: false }, false), "common_unranked");
});
