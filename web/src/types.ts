export type LaneScores = {
  artifact?: number;
  completeness?: number;
  decision?: number;
  dose_localization?: number;
  outcome?: number;
  safety?: number;
  reproducibility?: number;
  localization?: number;
  segmentation?: number;
};

export type ReleaseView = "core" | "imaging" | "tg263" | "real";

export type ItemDiagnosticsArtifact = {
  schema_version: "medphysbench.item-diagnostics.v1";
  release_id: string;
  source: {
    leaderboard_file: string;
    leaderboard_sha256: string;
    results_directory: string;
    result_record_count: number;
    result_manifest_sha256: string;
  };
  item_diagnostics: {
    status: "available";
    reason: null;
    groups: Array<{
      comparison_group: string;
      model_count: number;
      task_count: number;
      family_count: number;
      attempt_count: number;
      tasks: Array<{
        task_id: string;
        family_id: string;
        model_count: number;
        attempt_count: number;
        safe_success_count: number;
        safe_success_rate: number;
        response_entropy_bits: number;
        discrimination: number | null;
        discrimination_model_count: number;
      }>;
      summary: {
        best_system_safe_success_rate: number | null;
        median_task_safe_success_rate: number | null;
        median_task_discrimination: number | null;
        discrimination_task_count: number;
        panel_solved_family_count: number;
        panel_solved_family_fraction: number | null;
        near_zero_entropy_family_count: number;
        near_zero_entropy_family_fraction: number | null;
        watch: boolean;
        watch_signals: Array<{ code: string; observed: number }>;
        governance_status: "public_development_diagnostic_only";
      };
    }>;
    methodology: Record<string, string>;
  };
};

export type ReviewState = {
  status: "complete" | "recruiting" | "pending" | "blocked" | "not_started";
  completed: number;
  target: number;
  note: string;
};

export type ReviewEvidence = {
  schema_version: "medphysbench.review-evidence.v1";
  release_id: string;
  release_status: "provisional" | "reviewed" | "retired";
  reference_feasibility: {
    status: "passed" | "failed" | "pending";
    method: string;
  };
  independent_domain_review: ReviewState;
  human_baseline: ReviewState;
  paired_counterfactuals: ReviewState;
  negative_controls: ReviewState;
  data_rights_review: {
    status: "documented" | "pending_independent_confirmation" | "blocked";
    note: string;
  };
  claim_boundary: {
    allowed: string[];
    prohibited: string[];
  };
  task_reviews: Array<{
    task_id: string;
    reference_feasibility: "automated_pass" | "failed" | "pending";
    domain_review: "approved" | "revision_required" | "pending";
  }>;
};

export type EvidenceCountState = {
  status: "complete" | "recruiting" | "pending" | "not_started" | "blocked" | "not_applicable";
  completed: number;
  target: number | null;
  note: string;
};

export type ReleaseEvidence = {
  release_id: string;
  manifest_path: string;
  manifest_sha256: string;
  release_contract_hash_v2: string;
  task_count: number;
  family_count: number;
  max_family_share_observed: number;
  expected_attempts_per_task: number;
  integrity_profile: "development" | "pilot" | "comparison";
  allow_access_classes: Array<"public" | "gated" | "restricted" | "private">;
  public_attempt_detail: "aggregate_only" | "sanitized_output";
  maturity:
    | "public_development"
    | "public_pilot"
    | "domain_reviewed"
    | "human_baselined"
    | "protected_comparison"
    | "externally_replicated"
    | "retired";
  exposure: {
    task_access: "public" | "restricted" | "private";
    contamination_risk: "high" | "managed" | "low";
    protected_holdout: {
      status: "operating" | "not_operating" | "retired";
      note: string;
    };
  };
  interaction: {
    depth: "single_response" | "stateful_workflow" | "mixed";
    trajectory_capture: "none" | "partial" | "complete";
    final_state_grading: boolean;
    note: string;
  };
  evidence: {
    reference_feasibility: {
      status: "passed" | "partial" | "pending" | "failed";
      note: string;
    };
    independent_domain_review: EvidenceCountState;
    human_baseline: EvidenceCountState;
    paired_counterfactuals: EvidenceCountState;
    negative_controls: EvidenceCountState;
    data_rights_review: {
      status: "documented" | "pending_independent_confirmation" | "blocked" | "not_applicable";
      note: string;
    };
    artifact_audit: {
      status: "internal_complete" | "independent_complete" | "partial" | "pending" | "blocked";
      note: string;
    };
    independent_replication: {
      status: "complete" | "partial" | "not_started" | "blocked";
      note: string;
    };
  };
  defect_count: number;
  defect_ids: string[];
  review_ledger: {
    path: string;
    sha256: string;
  } | null;
  claim_boundary: {
    allowed: string[];
    prohibited: string[];
  };
};

export type ReleaseEvidenceIndex = {
  schema_version: "medphysbench.release-evidence-index.v1";
  updated_at: string;
  releases: ReleaseEvidence[];
};

export type BenchmarkDefect = {
  defect_id: string;
  reported_at: string;
  status: "reported" | "confirmed" | "fixed" | "withdrawn" | "regraded";
  severity: "low" | "medium" | "high" | "critical";
  category: string;
  summary: string;
  impact: string;
  score_treatment: string;
  affected_release_ids: string[];
  affected_task_ids: string[];
  resolution: {
    status: "planned" | "in_progress" | "complete" | "not_applicable";
    target_release_id: string | null;
    replacement_artifact: string | null;
  };
  evidence: string[];
};

export type DefectLedger = {
  schema_version: "medphysbench.defect-ledger.v1";
  updated_at: string;
  task_index?: Record<string, string[]>;
  entries: BenchmarkDefect[];
};

export type PublicReleaseKey = "core" | "imaging" | "tg263" | "real";

export type ModelOpenness = "open" | "closed" | "unknown";

export type ModelCatalogEntry = {
  provider: string;
  model_name: string;
  base_model_id: string;
  openness: ModelOpenness;
  steward: string;
  family: string;
  artifact_provenance?: {
    kind: "provider_hosted" | "official_local_build" | "community_quantization" | "native_agent_surface";
    label: string;
    source_url?: string;
    source_revision?: string;
    quantization?: string;
    artifacts?: Array<{
      role: string;
      sha256: string;
      bytes?: number;
    }>;
  };
  notes?: string;
};

export type Tg263AuditModel = {
  model_name: string;
  provider: string;
  model_revision: string;
  attempt_count: number;
  strict_safe_success_rate: number;
  primary_decision_rate: number;
  reason_code_exact_rate: number;
  label_only_mismatch_count: number;
  primary_failure_count: number;
  label_only_mismatches: Array<{
    task_id: string;
    failed_graders: string[];
    output: Record<string, unknown>;
  }>;
  primary_failures: Array<{
    task_id: string;
    failed_graders: string[];
    output: Record<string, unknown>;
  }>;
};

export type Tg263Audit = {
  generated_at: string;
  release_id: string;
  scope: string;
  primary_graders: string[];
  reason_grader: string;
  models: Tg263AuditModel[];
};

export type ModelTaskResult = {
  attempt_id?: string;
  artifact_path?: string | null;
  artifact_sha256?: string;
  task_id: string;
  family_id?: string | null;
  title: string;
  domain: string;
  track: string;
  run_id?: string;
  seed?: number;
  attempt_index?: number;
  prompt_hash?: string;
  tool_schema_hash?: string;
  runtime_task_hash?: string;
  grader_hash?: string;
  adapter_settings_hash?: string;
  scoring_revision?: string;
  created_at?: string;
  status?: string;
  score?: number;
  duration_seconds?: number | null;
  token_usage?: {
    available: boolean;
    input_tokens: number | null;
    output_tokens: number | null;
    total_tokens: number | null;
  };
  output?: Record<string, unknown>;
  grader_results?: Array<{
    grader_id: string;
    lane: string;
    passed: boolean;
    score: number;
    required_for_pass: boolean;
    severity: string;
    rationale: string;
  }>;
  response_receipt?: Record<string, unknown>;
  passed?: boolean;
  safe: boolean;
  outcome_category?: string;
  capability_failure?: boolean;
  model_failure_kind?: string | null;
  error_type?: string | null;
  failed_graders?: string[];
  failed_lanes?: string[];
};

export type AttemptOutcomeClass = "safe-pass" | "safe-fail" | "unsafe" | "unavailable" | "unknown";

export type ForensicsOutcomeCategory =
  | "safe_success"
  | "safe_failure"
  | "unsafe"
  | "unavailable"
  | "inconclusive";

export function classifyAttemptOutcome(
  task: Pick<ModelTaskResult, "passed" | "safe" | "outcome_category" | "capability_failure">,
): AttemptOutcomeClass {
  if (task.outcome_category === "unavailable" || task.capability_failure === true) return "unavailable";
  if (task.passed == null) return task.safe === false ? "unsafe" : "unknown";
  if (task.passed === true && task.safe === true) return "safe-pass";
  if (task.safe === false) return "unsafe";
  if (task.passed === false) return "safe-fail";
  return "unknown";
}

export function normalizeForensicsOutcome(
  value: string | undefined,
  capabilityFailure = false,
): ForensicsOutcomeCategory {
  if (value === "unavailable" || capabilityFailure) return "unavailable";
  if (
    value === "safe_success"
    || value === "safe_failure"
    || value === "unsafe"
    || value === "inconclusive"
  ) {
    return value;
  }
  return "inconclusive";
}

export type ModelResult = {
  rank?: number | null;
  rank_group?: string | null;
  comparison_group?: string | null;
  outcome_rank?: number | null;
  outcome_rank_status?: string;
  model_name: string;
  provider: string;
  model_revision: string;
  execution_surface?: string;
  execution_surface_label?: string;
  run_profile?: {
    provider: string;
    harness_name: string;
    harness_revision: string;
    run_configuration_hash?: string;
    is_common_harness: boolean;
    is_recorded_import_surface: boolean;
  };
  harness_name?: string;
  harness_revision?: string;
  attempt_count: number;
  completed_count: number;
  error_count: number;
  expected_attempt_count: number;
  task_success_rate: number;
  task_success_ci95: [number, number];
  safe_success_ci95?: [number, number];
  family_cluster_safe_success_ci95?: [number, number] | null;
  family_count?: number;
  safe_success_rate: number;
  safety_gate_rate: number;
  valid_output_rate: number;
  appropriate_escalation_rate: number | null;
  critical_unsafe_action_rate: number;
  any_pass_rate: number;
  all_pass_rate: number;
  average_duration_seconds: number | null;
  median_duration_seconds: number | null;
  duration_telemetry?: {
    available: boolean;
    complete?: boolean;
    kind: string;
    observed_attempts: number;
    expected_attempts: number;
  };
  token_usage?: {
    available: boolean;
    complete: boolean;
    observed_attempts: number;
    expected_attempts: number;
    observed_input_attempts?: number;
    observed_output_attempts?: number;
    observed_total_attempts?: number;
    input_complete?: boolean;
    output_complete?: boolean;
    total_complete?: boolean;
    campaign_attempts?: number;
    capability_unavailable_attempts?: number;
    provider_output_contract_failure_attempts?: number;
    usage_unavailable_attempts?: number;
    total_input_tokens: number | null;
    total_output_tokens: number | null;
    total_tokens: number | null;
    median_input_tokens: number | null;
    median_output_tokens: number | null;
    median_total_tokens: number | null;
  };
  lane_scores: LaneScores;
  reliability?: {
    all_attempts_agree_rate: number;
    mean_within_task_variance: number;
    pass_at_k: Record<string, number>;
    pass_power_k: Record<string, number>;
  };
  domain_safe_success: Record<string, number>;
  ranking_eligible: boolean;
  outcome_order_eligible?: boolean;
  ranking_status?: string;
  eligible_for_ranking?: boolean;
  release_complete?: boolean;
  missing_attempts?: string[];
  duplicate_attempts?: string[];
  invalid_task_ids?: string[];
  integrity_issues?: string[];
  integrity: {
    observed_attempt_keys: number;
    missing_attempt_keys: number;
    unexpected_attempt_keys: number;
    integrity_errors: string[];
  };
  tasks: ModelTaskResult[];
};

export type LeaderboardTask = {
  task_id: string;
  title: string;
  domain: string;
  risk_tier: string;
  track: string;
  access_class: string;
  expected_escalation: boolean;
  context_artifact_count: number;
  prompt_hash: string;
  tool_schema_hash: string;
};

export type PublicRuntimeTask = {
  schema_version: "medeval.task.v1";
  task_id: string;
  version: string;
  title: string;
  domain: string;
  track: string;
  risk_tier: string;
  instructions: string;
  input_payload: Record<string, unknown>;
  context_artifacts: Array<Record<string, unknown>>;
  allowed_tools: Array<Record<string, unknown>>;
  expected_output_schema: Record<string, unknown>;
  safety: Record<string, unknown>;
  stop_conditions: Record<string, unknown>;
};

export type PublicTaskInput = {
  task_id: string;
  runtime_task_hash: string;
  runtime_task: PublicRuntimeTask;
};

export type PublicTaskInputCatalog = {
  schema_version: "medphysbench.public-task-inputs.v1";
  releases: Array<{
    release_id: string;
    tasks: PublicTaskInput[];
  }>;
};

export type TaskCatalogEntry = LeaderboardTask;

export type CoverageRow = {
  domain: string;
  task_count: number;
  expected_escalation_count: number;
};

export type Leaderboard = {
  generated_at: string;
  release: {
    schema_version: string;
    release_id: string;
    title: string;
    description: string;
    task_files: string[];
    allow_access_classes: string[];
    expected_attempts_per_task?: number;
    integrity_profile?: "development" | "pilot" | "comparison";
    public_attempt_detail?: "aggregate_only" | "sanitized_output";
    family_count?: number;
    max_family_share?: number;
  };
  integrity: {
    expected_attempts_per_task?: number;
    expected_attempt_count?: number;
    ranked_model_count?: number;
    unranked_model_count?: number;
    release_contract_hash?: string;
    release_contract_hash_v2?: string;
  };
  release_integrity?: {
    expected_attempt_count_per_model?: number;
    ranked_model_count?: number;
    integrity_review_required_count?: number;
  };
  models: ModelResult[];
  unranked_models?: ModelResult[];
  tasks: LeaderboardTask[];
  coverage?: CoverageRow[];
  methodology: Record<string, string>;
};

export type AccessStatusEntry = {
  model: string;
  provider?: string;
  base_model_id?: string;
  qualification_stage?: "q0" | "q1" | "q2" | "q3";
  status: string;
  surface: string;
  date: string;
  note: string;
};

export type AccessStatus = AccessStatusEntry;

export type FleetStatusSummary = {
  planned_base_models: number;
  access_qualified_base_models: number;
  evaluated_base_models: number;
  ranked_base_models: number;
  workflow_view_evaluated_base_models: number;
  workflow_view_ranked_base_models: number;
  published_system_configurations: number;
  published_release_rows: number;
  open_planned_models: number;
  closed_planned_models: number;
  vision_planned_models: number;
  steward_count: number;
  evaluated_open_base_models: number;
  evaluated_closed_base_models: number;
  evaluated_vision_base_models: number;
  evaluated_image_route_base_models: number;
  evaluated_steward_count: number;
  evaluated_size_tiers: Array<"small" | "medium" | "large" | "frontier" | "undisclosed">;
  route_set_count: number;
  declared_route_count: number;
};

export type FleetStatusModel = {
  base_model_id: string;
  display_name: string;
  steward: string;
  family: string;
  openness: "open" | "closed";
  modalities: Array<"text" | "image">;
  evaluated_modalities: Array<"text" | "image">;
  size_tier: "small" | "medium" | "large" | "frontier" | "undisclosed";
  planned_routes: Array<"anthropic" | "aws_bedrock" | "codex_native" | "cohere" | "google" | "groq" | "ollama" | "openai" | "self_hosted" | "xai">;
  access_qualified: boolean;
  qualification_stage: "q0" | "q1" | "q2" | "q3" | null;
  evaluated: boolean;
  ranked: boolean;
  workflow_view_evaluated: boolean;
  workflow_view_ranked: boolean;
  system_configuration_count: number;
  published_release_count: number;
  published_row_count: number;
  readiness_state: "route_planned" | "access_qualified" | "evaluated" | "workflow_view_evaluated";
  next_gate: "q0_access" | "q2_common_harness" | "q2_workflow_view" | "q3_comparison";
  readiness_note: string;
  access_evidence: Array<{
    provider: string | null;
    model: string;
    status: string;
    qualification_stage: "q0" | "q1" | "q2" | "q3" | null;
    surface: string;
    date: string;
    promotion_basis: "attested_complete_q2" | null;
    qualification_evidence: {
      kind: "common_harness_submission";
      submission_id: string;
      manifest_path: string;
    } | null;
    access_probe_receipt?: {
      path: string;
      sha256: string;
    };
    note: string;
  }>;
};

type FleetNumericCompletionGate = {
  required: number;
  observed: number;
  satisfied: boolean;
  remaining: number;
};

export type FleetCompletionGate = {
  required_base_model_count: number;
  observed_base_model_count: number;
  satisfied_base_model_count: number;
  remaining_base_model_count: number;
  required_base_model_ids: string[];
  observed_base_model_ids: string[];
  satisfied_base_model_ids: string[];
  remaining_base_model_ids: string[];
  composition: {
    open_base_models: FleetNumericCompletionGate;
    closed_base_models: FleetNumericCompletionGate;
    vision_capable_base_models: FleetNumericCompletionGate;
    steward_count: FleetNumericCompletionGate;
    size_tiers: {
      required: FleetStatusModel["size_tier"][];
      observed: FleetStatusModel["size_tier"][];
      satisfied: boolean;
      remaining: FleetStatusModel["size_tier"][];
    };
  };
  satisfied: boolean;
};

export type FleetStatus = {
  schema_version: "medphysbench.fleet-status.v3";
  generated_at: string;
  fleet_id: string;
  summary: FleetStatusSummary;
  completion_gate?: FleetCompletionGate;
  models: FleetStatusModel[];
};
