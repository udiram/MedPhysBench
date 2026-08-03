import { normalizeForensicsOutcome } from "../types.ts";
import type { ForensicsOutcomeCategory, ModelResult, ModelTaskResult } from "../types.ts";

export type FingerprintInputRow = {
  key: string;
  row: ModelResult;
};

export type FingerprintCellStatus =
  | "safe_success"
  | "mixed"
  | "safe_failure"
  | "unsafe"
  | "unavailable"
  | "inconclusive";

export type TaskFingerprintCell = {
  taskId: string;
  title: string;
  familyId: string | null;
  attempts: number;
  safeSuccess: number;
  safeFailure: number;
  unsafe: number;
  unavailable: number;
  inconclusive: number;
  safeSuccessRate: number;
  status: FingerprintCellStatus;
  focusAttempt: ModelTaskResult;
};

export type TaskFingerprintColumn = {
  taskId: string;
  title: string;
  familyId: string | null;
  domain: string;
  track: string;
  observedRunSets: number;
  observedAttempts: number;
  safeSuccessRate: number;
};

export type TaskFingerprintRow = FingerprintInputRow & {
  cells: Map<string, TaskFingerprintCell>;
};

export type TaskFingerprintMatrix = {
  columns: TaskFingerprintColumn[];
  rows: TaskFingerprintRow[];
};

const OUTCOME_PRIORITY: Record<ForensicsOutcomeCategory, number> = {
  unsafe: 0,
  unavailable: 1,
  safe_failure: 2,
  inconclusive: 3,
  safe_success: 4,
};

export function buildTaskFingerprintMatrix(inputRows: readonly FingerprintInputRow[]): TaskFingerprintMatrix {
  const columnState = new Map<string, TaskFingerprintColumn & { safeSuccess: number }>();
  const rows = inputRows.map((entry) => {
    const grouped = new Map<string, ModelTaskResult[]>();
    for (const task of entry.row.tasks) {
      const tasks = grouped.get(task.task_id) ?? [];
      tasks.push(task);
      grouped.set(task.task_id, tasks);
    }

    const cells = new Map<string, TaskFingerprintCell>();
    for (const [taskId, tasks] of grouped) {
      const cell = buildCell(taskId, tasks);
      cells.set(taskId, cell);

      const first = tasks[0];
      const current = columnState.get(taskId) ?? {
        taskId,
        title: first?.title ?? taskId,
        familyId: first?.family_id ?? null,
        domain: first?.domain ?? "unknown",
        track: first?.track ?? "unknown",
        observedRunSets: 0,
        observedAttempts: 0,
        safeSuccess: 0,
        safeSuccessRate: 0,
      };
      current.observedRunSets += 1;
      current.observedAttempts += cell.attempts;
      current.safeSuccess += cell.safeSuccess;
      current.safeSuccessRate = current.observedAttempts
        ? current.safeSuccess / current.observedAttempts
        : 0;
      columnState.set(taskId, current);
    }

    return { ...entry, cells };
  });

  const columns = [...columnState.values()]
    .map(({ safeSuccess: _safeSuccess, ...column }) => column)
    .sort(
      (left, right) =>
        left.safeSuccessRate - right.safeSuccessRate ||
        left.title.localeCompare(right.title) ||
        left.taskId.localeCompare(right.taskId),
    );

  return { columns, rows };
}

export function fingerprintCellLabel(cell: TaskFingerprintCell) {
  const parts = [`${cell.safeSuccess}/${cell.attempts} safe success`];
  if (cell.safeFailure) parts.push(`${cell.safeFailure} safe failure`);
  if (cell.unsafe) parts.push(`${cell.unsafe} unsafe`);
  if (cell.unavailable) parts.push(`${cell.unavailable} capability unavailable`);
  if (cell.inconclusive) parts.push(`${cell.inconclusive} inconclusive`);
  return parts.join(", ");
}

function buildCell(taskId: string, tasks: readonly ModelTaskResult[]): TaskFingerprintCell {
  const first = tasks[0];
  if (!first) {
    throw new Error(`Cannot build a task fingerprint cell without attempts: ${taskId}`);
  }
  const counts: Record<ForensicsOutcomeCategory, number> = {
    safe_success: 0,
    safe_failure: 0,
    unsafe: 0,
    unavailable: 0,
    inconclusive: 0,
  };
  for (const task of tasks) {
    counts[normalizeForensicsOutcome(task.outcome_category, task.capability_failure === true)] += 1;
  }
  const focusAttempt = [...tasks].sort((left, right) => {
    const leftOutcome = normalizeForensicsOutcome(left.outcome_category, left.capability_failure === true);
    const rightOutcome = normalizeForensicsOutcome(right.outcome_category, right.capability_failure === true);
    return (
      OUTCOME_PRIORITY[leftOutcome] - OUTCOME_PRIORITY[rightOutcome] ||
      (left.attempt_index ?? Number.POSITIVE_INFINITY) - (right.attempt_index ?? Number.POSITIVE_INFINITY) ||
      (left.seed ?? Number.POSITIVE_INFINITY) - (right.seed ?? Number.POSITIVE_INFINITY)
    );
  })[0] ?? first;

  return {
    taskId,
    title: first?.title ?? taskId,
    familyId: first?.family_id ?? null,
    attempts: tasks.length,
    safeSuccess: counts.safe_success,
    safeFailure: counts.safe_failure,
    unsafe: counts.unsafe,
    unavailable: counts.unavailable,
    inconclusive: counts.inconclusive,
    safeSuccessRate: tasks.length ? counts.safe_success / tasks.length : 0,
    status: cellStatus(counts, tasks.length),
    focusAttempt,
  };
}

function cellStatus(counts: Record<ForensicsOutcomeCategory, number>, total: number): FingerprintCellStatus {
  if (counts.unsafe > 0) return "unsafe";
  if (counts.unavailable > 0) return "unavailable";
  if (counts.safe_success === total && total > 0) return "safe_success";
  if (counts.safe_success > 0) return "mixed";
  if (counts.safe_failure > 0) return "safe_failure";
  return "inconclusive";
}
