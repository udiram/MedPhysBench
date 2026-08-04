import { modelRunKey } from "./modelRunKey.ts";
import { scoreEvidenceAvailable } from "./resultEvidence.ts";
import { isIdenticalHarnessPeer } from "./taskComparison.ts";
import { normalizeForensicsOutcome } from "../types.ts";
import type { ForensicsOutcomeCategory, Leaderboard, ModelResult, ModelTaskResult } from "../types.ts";

export type SpotlightRun = {
  key: string;
  row: ModelResult;
};

export type SpotlightAttempt = {
  task: ModelTaskResult;
  outcome: ForensicsOutcomeCategory;
};

export type SpotlightSelection = {
  runs: SpotlightRun[];
  selected: SpotlightRun | null;
  taskIds: string[];
  taskTitle: string | null;
  selectedAttempt: SpotlightAttempt | null;
  bestPeer: SpotlightRun | null;
  bestPeerAttempt: SpotlightAttempt | null;
  bestPeerSafeSuccessRate: number | null;
};

export function spotlightRuns(data: Leaderboard | null): SpotlightRun[] {
  if (!data) return [];
  return [...data.models, ...(data.unranked_models ?? [])]
    .filter((row) =>
      scoreEvidenceAvailable(row)
      && row.completed_count === row.expected_attempt_count
      && row.error_count === 0
      && row.integrity.missing_attempt_keys === 0
      && row.tasks.some((task) => task.output && Object.keys(task.output).length > 0)
    )
    .map((row) => ({ key: modelRunKey(row), row }))
    .sort(
      (left, right) =>
        right.row.safe_success_rate - left.row.safe_success_rate
        || left.row.model_name.localeCompare(right.row.model_name),
    );
}

export function defaultSpotlightRunKey(runs: readonly SpotlightRun[]) {
  const groups = new Map<string, SpotlightRun[]>();
  for (const run of runs) {
    if (!run.row.comparison_group || run.row.ranking_eligible !== true) continue;
    const key = `${run.row.comparison_group}::${harnessRevision(run.row) ?? "unknown"}`;
    const group = groups.get(key) ?? [];
    group.push(run);
    groups.set(key, group);
  }
  const candidates = [...groups.values()]
    .filter((group) => group.length > 1)
    .sort((left, right) => right[0].row.safe_success_rate - left[0].row.safe_success_rate);
  return candidates[0]?.[1]?.key ?? runs[0]?.key ?? "";
}

export function buildSpotlightSelection(
  data: Leaderboard | null,
  requestedRunKey = "",
  requestedTaskId = "",
): SpotlightSelection {
  const runs = spotlightRuns(data);
  const selected = runs.find((run) => run.key === requestedRunKey)
    ?? runs.find((run) => run.key === defaultSpotlightRunKey(runs))
    ?? null;
  if (!selected) return emptySelection(runs);

  const taskIds = uniqueTaskIds(selected.row.tasks);
  const peers = runs.filter((run) =>
    run.key !== selected.key
    && run.row.ranking_eligible === true
    && isIdenticalHarnessPeer(selected, run)
  );
  const taskId = taskIds.includes(requestedTaskId)
    ? requestedTaskId
    : chooseContrastTaskId(selected, peers, taskIds);
  const selectedAttempts = selected.row.tasks.filter((task) => task.task_id === taskId);
  const selectedAttempt = chooseRepresentativeAttempt(selectedAttempts, "selected");

  const rankedPeers = peers
    .map((peer) => {
      const attempts = peer.row.tasks.filter((task) => task.task_id === taskId);
      const safeSuccesses = attempts.filter((task) => attemptOutcome(task) === "safe_success").length;
      return {
        peer,
        attempts,
        rate: attempts.length ? safeSuccesses / attempts.length : -1,
      };
    })
    .filter((candidate) => candidate.attempts.length > 0)
    .sort(
      (left, right) =>
        right.rate - left.rate
        || right.peer.row.safe_success_rate - left.peer.row.safe_success_rate
        || left.peer.row.model_name.localeCompare(right.peer.row.model_name),
    );
  const bestPeer = rankedPeers[0] ?? null;
  const bestPeerAttempt = bestPeer && selectedAttempt
    ? matchExactPeerAttempt(bestPeer.attempts, selectedAttempt.task)
    : null;

  return {
    runs,
    selected,
    taskIds,
    taskTitle: selectedAttempts[0]?.title ?? null,
    selectedAttempt,
    bestPeer: bestPeer?.peer ?? null,
    bestPeerAttempt,
    bestPeerSafeSuccessRate: bestPeer?.rate ?? null,
  };
}

function emptySelection(runs: SpotlightRun[]): SpotlightSelection {
  return {
    runs,
    selected: null,
    taskIds: [],
    taskTitle: null,
    selectedAttempt: null,
    bestPeer: null,
    bestPeerAttempt: null,
    bestPeerSafeSuccessRate: null,
  };
}

function chooseContrastTaskId(
  selected: SpotlightRun,
  peers: readonly SpotlightRun[],
  taskIds: readonly string[],
) {
  const contrast = taskIds.find((taskId) => {
    const selectedAttempts = selected.row.tasks.filter((task) => task.task_id === taskId);
    const selectedHasFailure = selectedAttempts.some((task) => attemptOutcome(task) !== "safe_success");
    const peerHasSuccess = peers.some((peer) =>
      peer.row.tasks.some((task) => task.task_id === taskId && attemptOutcome(task) === "safe_success")
    );
    return selectedHasFailure && peerHasSuccess;
  });
  return contrast ?? taskIds[0] ?? "";
}

function chooseRepresentativeAttempt(
  attempts: readonly ModelTaskResult[],
  role: "selected",
): SpotlightAttempt | null {
  if (!attempts.length) return null;
  const preferred = role === "selected"
    ? attempts.find((task) => attemptOutcome(task) !== "safe_success")
    : null;
  const task = preferred ?? attempts[0];
  return { task, outcome: attemptOutcome(task) };
}

function matchExactPeerAttempt(
  attempts: readonly ModelTaskResult[],
  reference: ModelTaskResult,
): SpotlightAttempt | null {
  const exact = attempts.filter((task) =>
    task.task_id === reference.task_id
    && task.attempt_index === reference.attempt_index
    && task.seed === reference.seed
    && task.runtime_task_hash === reference.runtime_task_hash
  );
  if (exact.length !== 1) return null;
  return { task: exact[0], outcome: attemptOutcome(exact[0]) };
}

function attemptOutcome(task: ModelTaskResult) {
  return normalizeForensicsOutcome(task.outcome_category, task.capability_failure === true);
}

function uniqueTaskIds(tasks: readonly ModelTaskResult[]) {
  const seen = new Set<string>();
  const values: string[] = [];
  for (const task of tasks) {
    if (seen.has(task.task_id)) continue;
    seen.add(task.task_id);
    values.push(task.task_id);
  }
  return values;
}

function harnessRevision(row: ModelResult) {
  return row.run_profile?.harness_revision ?? row.harness_revision ?? null;
}
