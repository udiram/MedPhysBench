import type { BenchmarkDefect, DefectLedger } from "../types";

export function defectsForTask(ledger: DefectLedger | null, taskId: string): BenchmarkDefect[] {
  if (!ledger || !taskId) return [];
  const byId = new Map(ledger.entries.map((entry) => [entry.defect_id, entry]));
  const indexedIds = ledger.task_index?.[taskId];
  const defectIds = indexedIds ?? ledger.entries
    .filter((entry) => entry.affected_task_ids.includes(taskId))
    .map((entry) => entry.defect_id);
  return [...new Set(defectIds)]
    .sort()
    .map((defectId) => byId.get(defectId))
    .filter((entry): entry is BenchmarkDefect => entry !== undefined);
}
