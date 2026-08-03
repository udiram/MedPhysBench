import type { Leaderboard, ModelResult } from "../types";

export type ResultsScope = "descriptive" | "official";

export function rowVisibleInResultsScope(row: ModelResult, scope: ResultsScope) {
  return scope === "descriptive" || row.ranking_eligible === true;
}

export function rowsForResultsScope(rows: readonly ModelResult[], scope: ResultsScope) {
  return rows.filter((row) => rowVisibleInResultsScope(row, scope));
}

export function resultsScopeCounts(data: Leaderboard | null) {
  const rows = data ? [...data.models, ...(data.unranked_models ?? [])] : [];
  const official = rows.filter((row) => row.ranking_eligible === true).length;
  return {
    published: rows.length,
    official,
    descriptive: rows.length - official,
  };
}

export function effectiveComparisonScope(
  scope: ResultsScope,
  localScope: "identical_harness" | "all_visible",
) {
  return scope === "official" ? "identical_harness" : localScope;
}
