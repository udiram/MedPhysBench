import assert from "node:assert/strict";
import test from "node:test";

import {
  countStateLabel,
  evidenceClaimText,
  interactionDepthLabel,
  normalizeReleaseTitle,
  releaseIdForView,
  releaseEvidenceFor,
  releaseTitleForView,
} from "../src/lib/releaseEvidence.ts";

const evidence = {
  release_id: "release-a",
  interaction: { depth: "single_response" },
  evidence: {
    human_baseline: { status: "not_started", completed: 0, target: null, note: "None." },
    paired_counterfactuals: { status: "not_started", completed: 0, target: null, note: "None." },
    negative_controls: { status: "not_started", completed: 0, target: null, note: "None." },
  },
  claim_boundary: { allowed: ["Bounded research comparison", "Regression testing"] },
};

test("release evidence resolves only one exact release record", () => {
  const index = {
    schema_version: "medphysbench.release-evidence-index.v1",
    releases: [evidence],
  };

  assert.equal(releaseEvidenceFor(index, "release-a"), evidence);
  assert.equal(releaseEvidenceFor(index, "missing"), null);
  assert.equal(releaseEvidenceFor(null, "release-a"), null);
});

test("duplicate release evidence fails closed instead of choosing a claim", () => {
  const index = {
    schema_version: "medphysbench.release-evidence-index.v1",
    releases: [evidence, { ...evidence }],
  };

  assert.equal(releaseEvidenceFor(index, "release-a"), null);
});

test("reader-facing evidence labels preserve missingness and interaction depth", () => {
  assert.equal(countStateLabel(evidence.evidence.human_baseline), "0 · not started");
  assert.equal(interactionDepthLabel(evidence.interaction.depth), "Single response");
  assert.equal(
    evidenceClaimText(evidence.claim_boundary.allowed),
    "Bounded research comparison; Regression testing",
  );
});

test("release helpers keep view-level fallback IDs and titles consistent", () => {
  assert.equal(releaseIdForView("core"), "public-core-v0.4");
  assert.equal(releaseIdForView("real"), "public-real-workflows-pilot-v0.6");
  assert.equal(releaseTitleForView("real"), "MedPhysBench OpenKBP Real-Data Workflow-View Pilot v0.6");
  assert.equal(
    normalizeReleaseTitle("MedPhysBench OpenKBP Real-Workflow Pilot v0.6", "real"),
    "MedPhysBench OpenKBP Real-Data Workflow-View Pilot v0.6",
  );
  assert.equal(normalizeReleaseTitle(null, "imaging"), "MedPhysBench Imaging Pilot");
});
