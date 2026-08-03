import { useMemo } from "react";
import { domainLabel, formatPercent, normalizeModelDisplayName, providerLabel } from "../lib/format";
import { taskAttemptKey } from "../lib/forensicsNavigation";
import { inferExecutionSurface, surfaceLabel } from "../lib/runSurface";
import {
  buildTaskFingerprintMatrix,
  fingerprintCellLabel,
  type FingerprintInputRow,
  type TaskFingerprintCell,
} from "../lib/taskFingerprintMatrix";

type Props = {
  rows: readonly FingerprintInputRow[];
  selectedRowKey: string | null;
  onSelect: (rowKey: string, attemptKey: string) => void;
};

export function TaskFingerprintMatrix({ rows, selectedRowKey, onSelect }: Props) {
  const matrix = useMemo(() => buildTaskFingerprintMatrix(rows), [rows]);

  if (!matrix.rows.length || !matrix.columns.length) return null;

  return (
    <section className="task-fingerprint-panel" aria-labelledby="task-fingerprint-title">
      <header className="task-fingerprint-heading">
        <div>
          <h3 id="task-fingerprint-title">Task fingerprint matrix</h3>
          <p>
            Hardest task views appear first. Every cell aggregates attempts for one exact run set and task view;
            select a cell to open its highest-severity attempt below.
          </p>
        </div>
        <p className="task-fingerprint-count">
          {matrix.rows.length} run set{matrix.rows.length === 1 ? "" : "s"} × {matrix.columns.length} task view{matrix.columns.length === 1 ? "" : "s"}
        </p>
      </header>

      <div className="task-fingerprint-legend" aria-label="Task fingerprint outcome legend">
        <span><i className="safe_success" />All attempts passed safely</span>
        <span><i className="mixed" />Mixed pass/fail</span>
        <span><i className="safe_failure" />Safe failure</span>
        <span><i className="unsafe" />Unsafe outcome present</span>
        <span><i className="unavailable" />Capability unavailable</span>
        <span><i className="inconclusive" />Inconclusive</span>
      </div>

      <div className="task-fingerprint-wrap" role="region" aria-label="Model by task fingerprint matrix" tabIndex={0}>
        <table className="task-fingerprint-table">
          <thead>
            <tr>
              <th scope="col" className="task-fingerprint-run-heading">Run set</th>
              {matrix.columns.map((column) => (
                <th key={column.taskId} scope="col" title={`${column.title} · ${column.taskId}`}>
                  <strong>{column.title}</strong>
                  <small>{domainLabel(column.domain)}</small>
                  <small>{formatPercent(column.safeSuccessRate)} across visible attempts</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((entry) => (
              <tr key={entry.key} className={entry.key === selectedRowKey ? "selected" : undefined}>
                <th scope="row">
                  <strong>{normalizeModelDisplayName(entry.row.model_name)}</strong>
                  <small>{providerLabel(entry.row.provider)} · {surfaceLabel(inferExecutionSurface(entry.row))}</small>
                  <small>{entry.row.harness_revision ?? "Harness revision unavailable"}</small>
                </th>
                {matrix.columns.map((column) => {
                  const cell = entry.cells.get(column.taskId);
                  return (
                    <td key={`${entry.key}::${column.taskId}`}>
                      {cell ? (
                        <FingerprintCellButton
                          cell={cell}
                          onSelect={() => onSelect(entry.key, taskAttemptKey(cell.focusAttempt))}
                        />
                      ) : (
                        <span className="task-fingerprint-missing" aria-label={`${column.title}: no attempt evidence`}>—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="task-fingerprint-note">
        Task views from the same declared family are correlated and are not independent patients or cases. This matrix
        is diagnostic across execution surfaces; official ranks still require an identical frozen comparison group.
      </p>
    </section>
  );
}

function FingerprintCellButton({
  cell,
  onSelect,
}: {
  cell: TaskFingerprintCell;
  onSelect: () => void;
}) {
  const label = `${cell.title}: ${fingerprintCellLabel(cell)}`;
  return (
    <button
      type="button"
      className={`task-fingerprint-cell ${cell.status}`}
      aria-label={`${label}. Inspect highest-severity attempt.`}
      title={label}
      onClick={onSelect}
    >
      <strong>{cell.safeSuccess}/{cell.attempts}</strong>
      <small>{cellDetail(cell)}</small>
    </button>
  );
}

function cellDetail(cell: TaskFingerprintCell) {
  const details: string[] = [];
  if (cell.unsafe) details.push(`${cell.unsafe} unsafe`);
  if (cell.unavailable) details.push(`${cell.unavailable} unavailable`);
  if (cell.safeFailure) details.push(`${cell.safeFailure} fail`);
  if (cell.inconclusive) details.push(`${cell.inconclusive} inconclusive`);
  return details.join(" · ") || "safe pass";
}
