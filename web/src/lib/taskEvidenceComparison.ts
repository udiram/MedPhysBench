import { exactPeerAttempt } from "./forensicsNavigation.ts";
import { scoreEvidenceAvailable } from "./resultEvidence.ts";
import { buildTaskComparison, isIdenticalHarnessPeer } from "./taskComparison.ts";
import type { TaskComparisonEntry, TaskComparisonResult } from "./taskComparison";
import type { ModelTaskResult } from "../types";

export type TaskAttemptMatch = "exact_attempt" | "same_runtime_input";

export type BestTaskEvidence<T extends TaskComparisonEntry> = {
  comparison: TaskComparisonResult<T>;
  attempt: ModelTaskResult;
  attemptMatch: TaskAttemptMatch;
  comparisonKind: "selected_is_leader" | "controlled_peer" | "descriptive_cross_contract";
};

export function bestPublishedTaskEvidence<T extends TaskComparisonEntry>(
  entries: readonly T[],
  selected: T | null,
  referenceTask: ModelTaskResult | null,
): BestTaskEvidence<T> | null {
  if (!referenceTask?.runtime_task_hash) return null;
  const eligible = entries.filter((entry) =>
    scoreEvidenceAvailable(entry.row)
    && entry.row.completed_count === entry.row.expected_attempt_count
    && entry.row.error_count === 0
    && entry.row.integrity.missing_attempt_keys === 0
  );
  const comparisons = buildTaskComparison(eligible, referenceTask.task_id, {
    scope: "all_visible",
    reference: selected,
  });
  for (const comparison of comparisons) {
    const match = representativeAttempt(comparison.attempts, referenceTask);
    if (!match) continue;
    return {
      comparison,
      attempt: match.attempt,
      attemptMatch: match.kind,
      comparisonKind: comparison.entry.key === selected?.key
        ? "selected_is_leader"
        : selected && isIdenticalHarnessPeer(selected, comparison.entry)
          ? "controlled_peer"
          : "descriptive_cross_contract",
    };
  }
  return null;
}

export function representativeAttempt(
  attempts: readonly ModelTaskResult[],
  referenceTask: ModelTaskResult,
): { attempt: ModelTaskResult; kind: TaskAttemptMatch } | null {
  const exact = exactPeerAttempt(attempts, referenceTask);
  if (exact) return { attempt: exact, kind: "exact_attempt" };
  if (!referenceTask.runtime_task_hash) return null;
  const sameInput = attempts
    .filter((attempt) =>
      attempt.task_id === referenceTask.task_id
      && attempt.runtime_task_hash === referenceTask.runtime_task_hash
    )
    .sort((left, right) =>
      Number(right.outcome_category === "safe_success") - Number(left.outcome_category === "safe_success")
      || (right.score ?? -1) - (left.score ?? -1)
      || (left.attempt_index ?? Number.POSITIVE_INFINITY) - (right.attempt_index ?? Number.POSITIVE_INFINITY)
    )[0];
  return sameInput ? { attempt: sameInput, kind: "same_runtime_input" } : null;
}
