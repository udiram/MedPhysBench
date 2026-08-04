import { normalizeForensicsOutcome } from "../types.ts";
import type { ForensicsOutcomeCategory, ModelResult, ModelTaskResult } from "../types";

export type TaskComparisonEntry = {
  key: string;
  row: ModelResult;
};

export type TaskOutcomeCounts = Record<ForensicsOutcomeCategory, number>;

export type TaskComparisonResult<T extends TaskComparisonEntry> = {
  entry: T;
  attempts: ModelTaskResult[];
  outcomes: TaskOutcomeCounts;
  safeSuccessRate: number;
  averageScore: number | null;
  topFailedGrader: string | null;
};

export type TaskComparisonScope = "identical_harness" | "all_visible";

export type TaskComparisonOptions<T extends TaskComparisonEntry> = {
  scope?: TaskComparisonScope;
  reference?: T | null;
};

export function buildTaskComparison<T extends TaskComparisonEntry>(
  entries: readonly T[],
  taskId: string | null,
  options: TaskComparisonOptions<T> = {},
): TaskComparisonResult<T>[] {
  if (!taskId) return [];

  const scopedEntries = options.scope === "identical_harness" && options.reference
    ? entries.filter((entry) => isIdenticalHarnessPeer(options.reference as T, entry))
    : entries;

  return scopedEntries
    .flatMap((entry) => {
      const attempts = entry.row.tasks.filter((task) => task.task_id === taskId);
      if (!attempts.length) return [];
      const outcomes = tallyTaskOutcomes(attempts);
      const topFailedGrader = mostFrequent(attempts.flatMap((task) => task.failed_graders ?? []));
      const scoredAttempts = attempts.filter((task) => task.score != null);
      return [{
        entry,
        attempts,
        outcomes,
        safeSuccessRate: outcomes.safe_success / attempts.length,
        averageScore: scoredAttempts.length
          ? scoredAttempts.reduce((sum, task) => sum + (task.score ?? 0), 0) / scoredAttempts.length
          : null,
        topFailedGrader,
      }];
    })
    .sort((left, right) =>
      right.safeSuccessRate - left.safeSuccessRate
      || (right.averageScore ?? -1) - (left.averageScore ?? -1)
      || left.outcomes.unsafe - right.outcomes.unsafe
      || (left.entry.row.outcome_rank ?? Number.POSITIVE_INFINITY)
        - (right.entry.row.outcome_rank ?? Number.POSITIVE_INFINITY)
      || right.entry.row.safe_success_rate - left.entry.row.safe_success_rate
      || left.entry.row.model_name.localeCompare(right.entry.row.model_name),
    );
}

export function isIdenticalHarnessPeer<T extends TaskComparisonEntry>(reference: T, candidate: T) {
  if (candidate.key === reference.key) return true;

  const referenceGroup = reference.row.comparison_group;
  const candidateGroup = candidate.row.comparison_group;
  if (!referenceGroup || !candidateGroup || referenceGroup !== candidateGroup) return false;

  const referenceRevision = harnessRevision(reference.row);
  const candidateRevision = harnessRevision(candidate.row);
  return Boolean(referenceRevision && candidateRevision && referenceRevision === candidateRevision);
}

function harnessRevision(row: ModelResult) {
  return row.run_profile?.harness_revision ?? row.harness_revision ?? null;
}

export function tallyTaskOutcomes(tasks: readonly ModelTaskResult[]): TaskOutcomeCounts {
  const counts: TaskOutcomeCounts = {
    safe_success: 0,
    safe_failure: 0,
    unsafe: 0,
    unavailable: 0,
    inconclusive: 0,
  };
  for (const task of tasks) {
    counts[normalizeForensicsOutcome(task.outcome_category, task.capability_failure === true)] += 1;
  }
  return counts;
}

function mostFrequent(values: readonly string[]) {
  const counts = new Map<string, number>();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))[0]?.[0] ?? null;
}
