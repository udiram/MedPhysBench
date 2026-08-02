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

export type PublicReleaseKey = "core" | "imaging" | "tg263" | "real";

export type ModelOpenness = "open" | "closed" | "unknown";

export type ModelCatalogEntry = {
  provider: string;
  model_name: string;
  base_model_id: string;
  openness: ModelOpenness;
  steward: string;
  family: string;
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
  task_id: string;
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
  scoring_revision?: string;
  passed?: boolean;
  safe: boolean;
  outcome_category?: string;
  failed_graders?: string[];
  failed_lanes?: string[];
};

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
    family_count?: number;
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
  published_system_configurations: number;
  published_release_rows: number;
  open_planned_models: number;
  closed_planned_models: number;
  vision_planned_models: number;
  steward_count: number;
};

export type FleetStatusModel = {
  base_model_id: string;
  display_name: string;
  steward: string;
  family: string;
  openness: "open" | "closed";
  modalities: Array<"text" | "image">;
  access_qualified: boolean;
  qualification_stage: "q0" | "q1" | "q2" | "q3" | null;
  evaluated: boolean;
  ranked: boolean;
  system_configuration_count: number;
  published_release_count: number;
  published_row_count: number;
};

export type FleetStatus = {
  schema_version: "medphysbench.fleet-status.v1";
  generated_at: string;
  fleet_id: string;
  summary: FleetStatusSummary;
  models: FleetStatusModel[];
};
