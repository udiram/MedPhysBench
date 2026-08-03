import { taskAttemptKey } from "./forensicsNavigation.ts";
import { matchesSearchText, normalizeSearchText } from "./searchNormalization.ts";
import { normalizeForensicsOutcome } from "../types.ts";
import type { ForensicsOutcomeCategory, ModelResult, ModelTaskResult } from "../types.ts";

const OUTCOME_PRIORITY: Record<ForensicsOutcomeCategory, number> = {
  unsafe: 0,
  safe_failure: 1,
  unavailable: 2,
  inconclusive: 3,
  safe_success: 4,
};

export function matchesForensicsRunQuery(row: Pick<ModelResult, "comparison_group" | "execution_surface" | "harness_revision" | "model_name" | "provider" | "run_profile">, query: string) {
  const configurationHash = row.run_profile?.run_configuration_hash;
  const descriptiveConfiguration = isOpaqueIdentifier(configurationHash) ? null : configurationHash;
  const identityCandidate = [row.model_name, row.provider].filter(Boolean).join(" ");
  const contractCandidate = [
    row.harness_revision,
    row.run_profile?.harness_revision,
    descriptiveConfiguration,
    row.comparison_group,
    row.execution_surface,
  ]
    .filter(Boolean)
    .join(" ");
  return matchesCompositeSearch(identityCandidate, query)
    || matchesCompositeSearch(contractCandidate, query)
    || matchesProviderQualifiedContract(row.provider, contractCandidate, query)
    || matchesOpaqueIdentifier(configurationHash, query);
}

export function matchesForensicsTaskQuery(task: Pick<ModelTaskResult, "attempt_id" | "domain" | "error_type" | "failed_graders" | "failed_lanes" | "family_id" | "model_failure_kind" | "task_id" | "title">, query: string) {
  const descriptiveAttemptId = isOpaqueIdentifier(task.attempt_id) ? null : task.attempt_id;
  return matchesCompositeSearch(
    [
      task.title,
      task.task_id,
      task.family_id,
      task.domain,
      task.model_failure_kind,
      task.error_type,
      descriptiveAttemptId,
      ...(task.failed_lanes ?? []),
      ...(task.failed_graders ?? []),
    ]
      .filter(Boolean)
      .join(" "),
    query,
  ) || matchesOpaqueIdentifier(task.attempt_id, query);
}

export function sortForensicsTasks(tasks: readonly ModelTaskResult[]) {
  return [...tasks].sort(
    (left, right) =>
      outcomePriority(left) - outcomePriority(right) ||
      failureSignalCount(right) - failureSignalCount(left) ||
      left.domain.localeCompare(right.domain) ||
      left.title.localeCompare(right.title) ||
      (left.attempt_index ?? Number.POSITIVE_INFINITY) - (right.attempt_index ?? Number.POSITIVE_INFINITY) ||
      taskAttemptKey(left).localeCompare(taskAttemptKey(right)),
  );
}

export function selectForensicsTaskWindow(
  tasks: readonly ModelTaskResult[],
  limit: number,
  selectedTaskKey: string,
) {
  if (limit <= 0 || tasks.length <= limit) return [...tasks];
  const windowed = tasks.slice(0, limit);
  if (!selectedTaskKey) return windowed;
  const selectedIndex = tasks.findIndex((task) => taskAttemptKey(task) === selectedTaskKey);
  if (selectedIndex < 0 || selectedIndex < limit) return windowed;
  return [...windowed.slice(0, Math.max(0, limit - 1)), tasks[selectedIndex]];
}

function outcomePriority(task: Pick<ModelTaskResult, "capability_failure" | "outcome_category">) {
  const outcome = normalizeForensicsOutcome(task.outcome_category, task.capability_failure === true);
  return OUTCOME_PRIORITY[outcome];
}

function failureSignalCount(task: Pick<ModelTaskResult, "failed_graders" | "failed_lanes">) {
  return (task.failed_lanes?.length ?? 0) + (task.failed_graders?.length ?? 0);
}

function matchesCompositeSearch(candidate: string, query: string) {
  if (matchesSearchText(candidate, query)) return true;
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedQuery) return true;
  const normalizedCandidate = normalizeSearchText(candidate);
  const compactCandidate = normalizedCandidate.replaceAll(" ", "");
  return normalizedQuery.split(" ").every((token) => normalizedCandidate.includes(token) || compactCandidate.includes(token));
}

function matchesProviderQualifiedContract(provider: string, contractCandidate: string, query: string) {
  const normalizedProvider = normalizeSearchText(provider);
  const normalizedQuery = normalizeSearchText(query);
  if (!normalizedProvider || !normalizedQuery || normalizedQuery === normalizedProvider) return false;
  if (normalizedQuery.startsWith(`${normalizedProvider} `)) {
    return matchesCompositeSearch(contractCandidate, normalizedQuery.slice(normalizedProvider.length + 1));
  }
  if (normalizedQuery.endsWith(` ${normalizedProvider}`)) {
    return matchesCompositeSearch(
      contractCandidate,
      normalizedQuery.slice(0, -(normalizedProvider.length + 1)),
    );
  }
  return false;
}

function isOpaqueIdentifier(value: string | null | undefined) {
  return typeof value === "string" && /^(?:sha256:)?[a-f0-9]{32,}$/i.test(value);
}

function matchesOpaqueIdentifier(value: string | null | undefined, query: string) {
  if (!isOpaqueIdentifier(value)) return false;
  const compactQuery = normalizeSearchText(query).replaceAll(" ", "");
  if (compactQuery.length < 8) return false;
  return String(value).toLowerCase().replace(/^sha256:/, "").includes(compactQuery.toLowerCase());
}
