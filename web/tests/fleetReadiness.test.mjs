import assert from "node:assert/strict";
import test from "node:test";

import {
  filterFleetModels,
  fleetNextGateLabel,
  fleetRouteLabel,
  hasAttestedQualification,
} from "../src/lib/fleetReadiness.ts";

const rows = [
  {
    base_model_id: "open/model-a",
    display_name: "Model A",
    steward: "Open Lab",
    family: "A",
    openness: "open",
    modalities: ["text"],
    size_tier: "small",
    planned_routes: ["groq"],
    access_qualified: true,
    qualification_stage: "q2",
    evaluated: true,
    ranked: true,
    workflow_view_evaluated: true,
    workflow_view_ranked: true,
    system_configuration_count: 1,
    published_release_count: 1,
    published_row_count: 1,
    readiness_state: "workflow_view_evaluated",
    next_gate: "q3_comparison",
    readiness_note: "Complete one-response OpenKBP workflow-view evidence exists.",
    access_evidence: [{
      provider: "groq",
      model: "model-a-route",
      status: "available",
      qualification_stage: "q2",
      surface: "openai_compatible",
      date: "2026-08-03",
      promotion_basis: "attested_complete_q2",
      qualification_evidence: {
        kind: "common_harness_submission",
        submission_id: "model-a-workflow-20260803",
        manifest_path: "submissions/model-a-workflow-20260803.json",
      },
      note: "Complete provider route evidence.",
    }],
  },
  {
    base_model_id: "closed/model-b",
    display_name: "Model B",
    steward: "Closed Lab",
    family: "B",
    openness: "closed",
    modalities: ["text", "image"],
    size_tier: "frontier",
    planned_routes: ["codex_native"],
    access_qualified: true,
    qualification_stage: "q2",
    evaluated: false,
    ranked: false,
    workflow_view_evaluated: false,
    workflow_view_ranked: false,
    system_configuration_count: 1,
    published_release_count: 1,
    published_row_count: 1,
    readiness_state: "access_qualified",
    next_gate: "q2_common_harness",
    readiness_note: "Native evidence exists; common-harness evidence does not.",
    access_evidence: [{
      provider: "codex-native",
      model: "model-b-native",
      status: "available",
      qualification_stage: "q2",
      surface: "recorded_output_import",
      date: "2026-08-03",
      promotion_basis: null,
      qualification_evidence: null,
      note: "Fresh-context sealed-batch capture.",
    }],
  },
  {
    base_model_id: "closed/model-c",
    display_name: "Model C",
    steward: "Closed Lab",
    family: "C",
    openness: "closed",
    modalities: ["text"],
    size_tier: "undisclosed",
    planned_routes: ["openai"],
    access_qualified: false,
    qualification_stage: null,
    evaluated: false,
    ranked: false,
    workflow_view_evaluated: false,
    workflow_view_ranked: false,
    system_configuration_count: 0,
    published_release_count: 0,
    published_row_count: 0,
    readiness_state: "route_planned",
    next_gate: "q0_access",
    readiness_note: "No base-model-bound access evidence is committed.",
    access_evidence: [],
  },
];

test("fleet readiness filters preserve honest base-model stages", () => {
  assert.deepEqual(
    filterFleetModels(rows, { source: "all", stage: "workflow_view", route: "all", query: "" })
      .map((row) => row.base_model_id),
    ["open/model-a"],
  );
  assert.deepEqual(
    filterFleetModels(rows, { source: "closed", stage: "needs_evidence", route: "all", query: "" })
      .map((row) => row.base_model_id),
    ["closed/model-b", "closed/model-c"],
  );
  assert.deepEqual(
    filterFleetModels(rows, { source: "all", stage: "planned", route: "openai", query: "" })
      .map((row) => row.base_model_id),
    ["closed/model-c"],
  );
});

test("only common-harness sidecars count as attested qualification", () => {
  assert.equal(hasAttestedQualification(rows[0]), true);
  assert.equal(hasAttestedQualification(rows[1]), false);
  assert.equal(hasAttestedQualification(rows[2]), false);
});

test("fleet search reaches route evidence and readiness notes", () => {
  assert.deepEqual(
    filterFleetModels(rows, { source: "all", stage: "all", route: "all", query: "fresh-context" })
      .map((row) => row.base_model_id),
    ["closed/model-b"],
  );
  assert.deepEqual(
    filterFleetModels(rows, { source: "all", stage: "all", route: "all", query: "common-harness evidence does not" })
      .map((row) => row.base_model_id),
    ["closed/model-b"],
  );
  assert.deepEqual(
    filterFleetModels(rows, { source: "all", stage: "all", route: "all", query: "model-a-workflow-20260803" })
      .map((row) => row.base_model_id),
    ["open/model-a"],
  );
});

test("fleet gate and route labels stay reader-facing", () => {
  assert.equal(fleetNextGateLabel("q0_access"), "Q0 · verify exact access");
  assert.equal(fleetNextGateLabel("q2_common_harness"), "Q2 · common-harness matrix");
  assert.equal(fleetNextGateLabel("q2_workflow_view"), "Q2 · OpenKBP workflow-view matrix");
  assert.equal(fleetNextGateLabel("q3_comparison"), "Q3 · reviewed comparison");
  assert.equal(fleetRouteLabel("self_hosted"), "Self-hosted");
  assert.equal(fleetRouteLabel("openai"), "OpenAI API");
});
