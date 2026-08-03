import type { ModelResult } from "../types";

type PointEstimateRow = Pick<
  ModelResult,
  "model_name" | "provider" | "safe_success_rate" | "task_success_rate" | "safety_gate_rate"
>;

function samePointEstimate(left: PointEstimateRow, right: PointEstimateRow) {
  return left.safe_success_rate === right.safe_success_rate
    && left.task_success_rate === right.task_success_rate
    && left.safety_gate_rate === right.safety_gate_rate;
}

export function comparePointEstimateRows(left: PointEstimateRow, right: PointEstimateRow) {
  return right.safe_success_rate - left.safe_success_rate
    || right.task_success_rate - left.task_success_rate
    || right.safety_gate_rate - left.safety_gate_rate
    || left.model_name.localeCompare(right.model_name)
    || left.provider.localeCompare(right.provider);
}

export function competitionRankMap<T extends PointEstimateRow>(rows: readonly T[]) {
  const ordered = [...rows].sort(comparePointEstimateRows);
  const ranks = new Map<T, number>();
  let previous: T | null = null;
  let rank = 0;

  ordered.forEach((row, index) => {
    if (previous === null || !samePointEstimate(row, previous)) {
      rank = index + 1;
    }
    ranks.set(row, rank);
    previous = row;
  });

  return ranks;
}
