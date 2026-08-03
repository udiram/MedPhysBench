import type { ModelResult } from "../types";
import { isCommonHarnessRun, isNativeRun } from "./runSurface.ts";
import { modelRunKey } from "./modelRunKey.ts";
import { scoreEvidenceAvailable } from "./resultEvidence.ts";
import { hasComparableTelemetry } from "./format.ts";

export type CertaintyMetric = "tokens" | "time";
export type CertaintyRowKind = "official" | "common_unranked" | "native_descriptive";
export type TelemetryCoverage = "complete" | "partial" | "missing";

export type CertaintyFrontierRow = {
  key: string;
  row: ModelResult;
  kind: CertaintyRowKind;
  value: number;
  coverage: TelemetryCoverage;
};

export type CertaintyFrontierGroup = {
  group: string;
  rows: CertaintyFrontierRow[];
};

export type CertaintyFrontierResult = {
  rows: CertaintyFrontierRow[];
  completeRows: CertaintyFrontierRow[];
  partialRows: CertaintyFrontierRow[];
  missingRows: CertaintyFrontierRow[];
  frontierGroups: CertaintyFrontierGroup[];
};

export function scoreMetricValue(row: ModelResult, metric: CertaintyMetric): number | null {
  const value = metric === "tokens" ? row.token_usage?.median_total_tokens : row.median_duration_seconds;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function certaintyScopeKind(row: ModelResult, includeDescriptive: boolean): CertaintyRowKind | null {
  if (!scoreEvidenceAvailable(row)) return null;

  const isCommon = isCommonHarnessRun(row);
  const isNative = isNativeRun(row) || !isCommon;

  if (isCommon && row.ranking_eligible) return "official";
  if (includeDescriptive && isCommon && !row.ranking_eligible) return "common_unranked";
  if (includeDescriptive && isNative) return "native_descriptive";
  return null;
}

function rowGroup(row: ModelResult) {
  return row.comparison_group ?? row.rank_group ?? `${row.provider}::${row.harness_name}::${row.harness_revision}`;
}

export function buildScoreCertaintyFrontierRows(
  rows: ModelResult[],
  metric: CertaintyMetric,
  includeDescriptive: boolean,
): CertaintyFrontierResult {
  const prepared = rows
    .map((row) => {
      const kind = certaintyScopeKind(row, includeDescriptive);
      if (!kind) return null;
      const value = scoreMetricValue(row, metric);
      if (value == null) {
        return {
          row,
          kind,
          value: Number.NaN,
          coverage: "missing" as const,
          key: modelRunKey(row),
        };
      }
      const coverage = hasComparableTelemetry(row, metric) ? "complete" : "partial";
      return {
        row,
        kind,
        value,
        coverage,
        key: modelRunKey(row),
      };
    })
    .filter((entry): entry is CertaintyFrontierRow => entry !== null);

  const completeRows = prepared.filter((entry) => entry.coverage === "complete");
  const partialRows = prepared.filter((entry) => entry.coverage === "partial");
  const missingRows = prepared.filter((entry) => entry.coverage === "missing");

  const frontierGroups = buildFrontierGroups(completeRows);

  return {
    rows: prepared,
    completeRows,
    partialRows,
    missingRows,
    frontierGroups,
  };
}

function buildFrontierGroups(rows: CertaintyFrontierRow[]) {
  const grouped = new Map<string, CertaintyFrontierRow[]>();
  for (const entry of rows) {
    const group = rowGroup(entry.row);
    grouped.set(group, [...(grouped.get(group) ?? []), entry]);
  }

  const frontierRows: CertaintyFrontierGroup[] = [];
  for (const [group, members] of grouped) {
    const ordered = [...members].sort((left, right) => left.value - right.value);
    const frontier: CertaintyFrontierRow[] = [];
    let bestScore = -Infinity;
    for (const entry of ordered) {
      if (!Number.isFinite(entry.row.safe_success_rate)) continue;
      if (entry.row.safe_success_rate > bestScore) {
        frontier.push(entry);
        bestScore = entry.row.safe_success_rate;
      }
    }
    if (frontier.length > 0) {
      frontierRows.push({ group, rows: frontier });
    }
  }
  return frontierRows;
}

export function certaintyRowLabel(kind: CertaintyRowKind) {
  if (kind === "official") return "Official comparison";
  if (kind === "common_unranked") return "Common harness (outcome-only)";
  return "Native / outcome-only";
}
