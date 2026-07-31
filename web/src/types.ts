export type LaneScores = {
  artifact?: number;
  outcome?: number;
  safety?: number;
  reproducibility?: number;
  localization?: number;
  segmentation?: number;
};

export type ReleaseView = "core" | "tg263" | "imaging";

export type ModelTaskResult = {
  task_id: string;
  title: string;
  domain: string;
  run_id?: string;
  seed?: number;
  attempt_index?: number;
  prompt_hash?: string;
  tool_schema_hash?: string;
  runtime_task_hash?: string;
  safe: boolean;
};

export type ModelResult = {
  rank?: number | null;
  model_name: string;
  provider: string;
  model_revision: string;
  harness_name?: string;
  harness_revision?: string;
  attempt_count: number;
  completed_count: number;
  error_count: number;
  expected_attempt_count: number;
  task_success_rate: number;
  task_success_ci95: [number, number];
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
  domain_safe_success: Record<string, number>;
  ranking_eligible: boolean;
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
  };
  integrity: {
    expected_attempts_per_task?: number;
    expected_attempt_count?: number;
    ranked_model_count?: number;
    unranked_model_count?: number;
    release_contract_hash?: string;
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
  status: string;
  surface: string;
  date: string;
  note: string;
};

export type AccessStatus = AccessStatusEntry;
