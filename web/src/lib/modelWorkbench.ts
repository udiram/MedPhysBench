import { domainLabel } from "./format.ts";
import { compareModelRuns, modelRunKey } from "./modelRunKey.ts";
import { isCommonHarnessRun } from "./runSurface.ts";
import { classifyAttemptOutcome } from "../types.ts";
import type { ModelResult, ModelTaskResult } from "../types.ts";

type WorkbenchRun = Pick<
  ModelResult,
  | "attempt_count"
  | "comparison_group"
  | "completed_count"
  | "duration_telemetry"
  | "execution_surface"
  | "expected_attempt_count"
  | "harness_name"
  | "harness_revision"
  | "integrity"
  | "median_duration_seconds"
  | "model_name"
  | "model_revision"
  | "provider"
  | "rank"
  | "rank_group"
  | "ranking_eligible"
  | "run_profile"
  | "safe_success_rate"
  | "safety_gate_rate"
  | "tasks"
  | "token_usage"
  | "valid_output_rate"
> & {
  release_id?: string | null;
  release_key?: string | null;
  release_title?: string | null;
};

export type OutcomeCounts = {
  safePass: number;
  safeFail: number;
  unsafe: number;
  unavailable: number;
  unknown: number;
  total: number;
};

export type TaskFamilyMatrixRow = {
  key: string;
  familyId: string;
  taskId: string;
  title: string;
  domain: string;
  attempts: number;
  safePass: number;
  safeFail: number;
  unsafe: number;
  unavailable: number;
  unknown: number;
  agreementLabel: string;
  topLane: string | null;
  topGrader: string | null;
};

export type RunWorkbenchSummary<T extends WorkbenchRun = WorkbenchRun> = {
  key: string;
  run: T;
  outcomes: OutcomeCounts;
  mixedFamilies: number;
  taskFamilies: TaskFamilyMatrixRow[];
  failureDomains: Array<[string, number]>;
  failureLanes: Array<[string, number]>;
  failureGraders: Array<[string, number]>;
  surfaceLabel: string;
  harnessLabel: string;
  configLabel: string;
  outcomeMixLabel: string;
  topFailureSignal: string;
  tokenCoverageLabel: string;
  durationCoverageLabel: string;
};

export type ModelWorkbenchSummary<T extends WorkbenchRun = WorkbenchRun> = {
  overview: OutcomeCounts & {
    runCount: number;
    familyCount: number;
    mixedFamilies: number;
  };
  failureDomains: Array<[string, number]>;
  failureLanes: Array<[string, number]>;
  failureGraders: Array<[string, number]>;
  runSummaries: Array<RunWorkbenchSummary<T>>;
};

export function compactWorkbenchIdentity(value: string | null | undefined, maxLength = 26) {
  if (!value) return "Unavailable";
  if (value.length <= maxLength) return value;
  const tailLength = Math.min(6, Math.max(3, Math.floor(maxLength / 4)));
  const leadLength = Math.max(6, maxLength - tailLength - 1);
  return `${value.slice(0, leadLength)}…${value.slice(-tailLength)}`;
}

export function buildModelWorkbench<T extends WorkbenchRun>(runs: readonly T[]): ModelWorkbenchSummary<T> {
  const runSummaries = [...runs]
    .sort(compareModelRuns)
    .map((run) => buildRunWorkbenchSummary(run));

  const overview = runSummaries.reduce<ModelWorkbenchSummary<T>["overview"]>(
    (accumulator, summary) => ({
      safePass: accumulator.safePass + summary.outcomes.safePass,
      safeFail: accumulator.safeFail + summary.outcomes.safeFail,
      unsafe: accumulator.unsafe + summary.outcomes.unsafe,
      unavailable: accumulator.unavailable + summary.outcomes.unavailable,
      unknown: accumulator.unknown + summary.outcomes.unknown,
      total: accumulator.total + summary.outcomes.total,
      runCount: accumulator.runCount + 1,
      familyCount: accumulator.familyCount + summary.taskFamilies.length,
      mixedFamilies: accumulator.mixedFamilies + summary.mixedFamilies,
    }),
    {
      safePass: 0,
      safeFail: 0,
      unsafe: 0,
      unavailable: 0,
      unknown: 0,
      total: 0,
      runCount: 0,
      familyCount: 0,
      mixedFamilies: 0,
    },
  );

  const allTasks = runSummaries.flatMap((summary) => summary.run.tasks);
  return {
    overview,
    failureDomains: topCounts(
      allTasks.filter((task) => taskOutcome(task) !== "safe-pass").map((task) => domainLabel(task.domain)),
      4,
    ),
    failureLanes: topCounts(
      allTasks.filter((task) => taskOutcome(task) !== "safe-pass").flatMap((task) => task.failed_lanes ?? []),
      4,
    ),
    failureGraders: topCounts(
      allTasks.filter((task) => taskOutcome(task) !== "safe-pass").flatMap((task) => task.failed_graders ?? []),
      4,
    ),
    runSummaries,
  };
}

export function buildRunWorkbenchSummary<T extends WorkbenchRun>(run: T): RunWorkbenchSummary<T> {
  const outcomes = countOutcomes(run.tasks);
  const taskFamilies = buildTaskFamilies(run.tasks);
  return {
    key: modelRunKey(run),
    run,
    outcomes,
    mixedFamilies: taskFamilies.filter((family) => family.agreementLabel !== "Unanimous").length,
    taskFamilies,
    failureDomains: topCounts(
      run.tasks.filter((task) => taskOutcome(task) !== "safe-pass").map((task) => domainLabel(task.domain)),
      4,
    ),
    failureLanes: topCounts(
      run.tasks.filter((task) => taskOutcome(task) !== "safe-pass").flatMap((task) => task.failed_lanes ?? []),
      4,
    ),
    failureGraders: topCounts(
      run.tasks.filter((task) => taskOutcome(task) !== "safe-pass").flatMap((task) => task.failed_graders ?? []),
      4,
    ),
    surfaceLabel: isCommonHarnessRun(run) ? "Common harness" : "Native surface",
    harnessLabel: [run.harness_name ?? "Harness unavailable", run.harness_revision ?? "Revision unavailable"].join(" · "),
    configLabel: run.run_profile?.run_configuration_hash ?? run.comparison_group ?? "Unavailable",
    outcomeMixLabel: `${outcomes.safePass}/${outcomes.total || 0} safe pass`,
    topFailureSignal: firstSignal(taskFamilies),
    tokenCoverageLabel: telemetryCoverage(run.token_usage?.observed_attempts, run.token_usage?.expected_attempts),
    durationCoverageLabel: telemetryCoverage(
      run.duration_telemetry?.observed_attempts,
      run.duration_telemetry?.expected_attempts,
    ),
  };
}

function buildTaskFamilies(tasks: readonly ModelTaskResult[]): TaskFamilyMatrixRow[] {
  const grouped = new Map<string, TaskFamilyMatrixRow & { failedLanes: string[]; failedGraders: string[]; labels: string[] }>();
  for (const task of tasks) {
    const familyId = task.family_id ?? task.task_id;
    const current = grouped.get(familyId) ?? {
      key: familyId,
      familyId,
      taskId: task.task_id,
      title: task.title,
      domain: domainLabel(task.domain),
      attempts: 0,
      safePass: 0,
      safeFail: 0,
      unsafe: 0,
      unavailable: 0,
      unknown: 0,
      agreementLabel: "Unanimous",
      topLane: null,
      topGrader: null,
      failedLanes: [],
      failedGraders: [],
      labels: [],
    };
    const outcome = taskOutcome(task);
    current.attempts += 1;
    current.labels.push(outcome);
    if (outcome === "safe-pass") current.safePass += 1;
    else if (outcome === "safe-fail") current.safeFail += 1;
    else if (outcome === "unsafe") current.unsafe += 1;
    else if (outcome === "unavailable") current.unavailable += 1;
    else current.unknown += 1;
    current.failedLanes.push(...(task.failed_lanes ?? []));
    current.failedGraders.push(...(task.failed_graders ?? []));
    grouped.set(familyId, current);
  }

  return [...grouped.values()]
    .map((family) => ({
      key: family.key,
      familyId: family.familyId,
      taskId: family.taskId,
      title: family.title,
      domain: family.domain,
      attempts: family.attempts,
      safePass: family.safePass,
      safeFail: family.safeFail,
      unsafe: family.unsafe,
      unavailable: family.unavailable,
      unknown: family.unknown,
      agreementLabel: agreementLabel(family.labels),
      topLane: topCounts(family.failedLanes, 1)[0]?.[0] ?? null,
      topGrader: topCounts(family.failedGraders, 1)[0]?.[0] ?? null,
    }))
    .sort(
      (left, right) =>
        failureCount(right) - failureCount(left) ||
        right.unsafe - left.unsafe ||
        right.unavailable - left.unavailable ||
        right.safeFail - left.safeFail ||
        left.title.localeCompare(right.title),
    );
}

function countOutcomes(tasks: readonly ModelTaskResult[]): OutcomeCounts {
  return tasks.reduce<OutcomeCounts>(
    (accumulator, task) => {
      const outcome = taskOutcome(task);
      if (outcome === "safe-pass") accumulator.safePass += 1;
      else if (outcome === "safe-fail") accumulator.safeFail += 1;
      else if (outcome === "unsafe") accumulator.unsafe += 1;
      else if (outcome === "unavailable") accumulator.unavailable += 1;
      else accumulator.unknown += 1;
      accumulator.total += 1;
      return accumulator;
    },
    { safePass: 0, safeFail: 0, unsafe: 0, unavailable: 0, unknown: 0, total: 0 },
  );
}

function firstSignal(taskFamilies: readonly TaskFamilyMatrixRow[]) {
  const firstFailure = taskFamilies.find((family) => failureCount(family) > 0);
  if (!firstFailure) return "No repeated failures";
  if (firstFailure.topLane) return firstFailure.topLane;
  if (firstFailure.topGrader) return firstFailure.topGrader;
  return firstFailure.agreementLabel;
}

function failureCount(row: Pick<TaskFamilyMatrixRow, "safeFail" | "unsafe" | "unavailable" | "unknown">) {
  return row.safeFail + row.unsafe + row.unavailable + row.unknown;
}

function agreementLabel(labels: string[]) {
  const unique = [...new Set(labels)];
  if (unique.length <= 1) return "Unanimous";
  if (unique.includes("unsafe")) return "Mixed, includes unsafe";
  if (unique.includes("unavailable")) return "Mixed, includes unavailable";
  if (unique.includes("safe-pass") && unique.includes("safe-fail")) return "Mixed pass/fail";
  return "Mixed";
}

function telemetryCoverage(observed?: number, expected?: number) {
  if (observed == null || expected == null) return "Unavailable";
  return `${observed}/${expected}`;
}

function topCounts(values: readonly string[], limit = 2) {
  const counts = new Map<string, number>();
  for (const value of values) {
    if (!value) continue;
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, limit);
}

function taskOutcome(task: ModelTaskResult) {
  return classifyAttemptOutcome(task);
}
