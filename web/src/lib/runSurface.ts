import type { ModelResult } from "../types";

export type ResolvedExecutionSurface = "common_harness" | "recorded_output_import";
export type SurfaceSummaryKind = "common" | "native";
type ExecutionSurfaceInput = Pick<
  ModelResult,
  | "execution_surface"
  | "run_profile"
  | "harness_name"
  | "harness_revision"
  | "ranking_eligible"
  | "provider"
  | "comparison_group"
  | "rank_group"
  | "integrity"
  | "rank"
>;

function hasNativeMarker(value: unknown): boolean {
  if (typeof value !== "string") return false;
  const lowered = value.toLowerCase();
  return (
    lowered.includes("recorded") ||
    lowered.includes("native") ||
    lowered.includes("medphysbench-recorded-output")
  );
}

export function inferExecutionSurface(row: ExecutionSurfaceInput): ResolvedExecutionSurface {
  if (row.execution_surface === "common_harness" || row.execution_surface === "recorded_output_import") {
    return row.execution_surface;
  }

  if (row.run_profile && typeof row.run_profile.is_common_harness === "boolean") {
    return row.run_profile.is_common_harness ? "common_harness" : "recorded_output_import";
  }
  if (row.run_profile && typeof row.run_profile.is_recorded_import_surface === "boolean" && row.run_profile.is_recorded_import_surface) {
    return "recorded_output_import";
  }

  const errors = row.integrity?.integrity_errors ?? [];
  if (Array.isArray(errors)) {
    if (errors.some((error) => error === "unranked_noncommon_surface" || error === "unranked_native_pilot_surface")) {
      return "recorded_output_import";
    }
  }

  if (row.provider === "codex-native") {
    return "recorded_output_import";
  }

  if (hasNativeMarker(row.harness_name) || hasNativeMarker(row.harness_revision)) {
    return "recorded_output_import";
  }

  if (row.ranking_eligible || row.comparison_group || row.rank_group || row.rank != null) {
    return "common_harness";
  }

  return row.execution_surface === "recorded_output_import" ? "recorded_output_import" : "common_harness";
}

export function isCommonHarnessRun(row: ExecutionSurfaceInput): boolean {
  return inferExecutionSurface(row) === "common_harness";
}

export function isNativeRun(row: ExecutionSurfaceInput): boolean {
  return inferExecutionSurface(row) === "recorded_output_import";
}

export function surfaceKind(row: ExecutionSurfaceInput): SurfaceSummaryKind {
  return inferExecutionSurface(row) === "common_harness" ? "common" : "native";
}

export function surfaceLabel(surface: ResolvedExecutionSurface) {
  return surface === "common_harness" ? "Common harness" : "Native / imported";
}
