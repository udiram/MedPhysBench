import type { ModelResult } from "../types";

export const DEFAULT_CHART_ROW_LIMIT = 14;
export const DEFAULT_TABLE_ROW_LIMIT = 16;

export type ComparisonScope = {
  key: string;
  rows: ModelResult[];
};

export function runComparisonScopeKey(row: ModelResult) {
  return (
    row.comparison_group ??
    row.rank_group ??
    [
      row.execution_surface ?? "unknown-surface",
      row.provider,
      row.harness_name ?? "unknown-harness",
      row.harness_revision ?? "unknown-revision",
    ].join("::")
  );
}

export function buildComparisonScopes(rows: ModelResult[]): ComparisonScope[] {
  const grouped = new Map<string, ModelResult[]>();
  for (const row of rows) {
    const key = runComparisonScopeKey(row);
    grouped.set(key, [...(grouped.get(key) ?? []), row]);
  }
  return [...grouped.entries()]
    .map(([key, members]) => ({ key, rows: members }))
    .sort(
      (left, right) =>
        right.rows.length - left.rows.length ||
        left.key.localeCompare(right.key),
    );
}

export function limitEvidenceRows<T>(rows: T[], expanded: boolean, limit: number) {
  return expanded ? rows : rows.slice(0, limit);
}
