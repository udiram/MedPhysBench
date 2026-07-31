export type LaneScores = {
  artifact?: number;
  outcome?: number;
  safety?: number;
};

export type ModelResult = {
  rank: number;
  model_name: string;
  provider: string;
  model_revision: string;
  attempt_count: number;
  completed_count: number;
  error_count: number;
  task_success_rate: number;
  task_success_ci95: [number, number];
  safe_success_rate: number;
  safety_gate_rate: number;
  valid_output_rate: number;
  appropriate_escalation_rate: number | null;
  critical_unsafe_action_rate: number;
  any_pass_rate: number;
  all_pass_rate: number;
  average_duration_seconds: number;
  median_duration_seconds: number;
  lane_scores: LaneScores;
  domain_safe_success: Record<string, number>;
  tasks: Array<{
    task_id: string;
    title: string;
    domain: string;
    passed: boolean;
    safe: boolean;
    duration_seconds: number;
  }>;
};

export type Leaderboard = {
  generated_at: string;
  release: {
    release_id: string;
    title: string;
    description: string;
  };
  models: ModelResult[];
  tasks: Array<{
    task_id: string;
    title: string;
    domain: string;
    risk_tier: string;
    track: string;
    expected_escalation: boolean;
  }>;
  methodology: Record<string, string>;
};
