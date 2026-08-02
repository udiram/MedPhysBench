import type { ModelResult } from "../types";

export function formatPercent(value: number | null | undefined) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

export function domainLabel(value: string) {
  return value
    .replace(/_physics$/, "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function artifactDirectory(modelName: string) {
  return modelName.replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

export function formatDuration(seconds: number | null | undefined) {
  if (seconds == null || !Number.isFinite(seconds)) return "Unavailable";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${(seconds / 60).toFixed(1)}m`;
}

export function formatTokens(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value);
}

export function shortHash(value: string | undefined) {
  if (!value) return "—";
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

export function providerLabel(provider: string): string {
  if (provider === "codex-native") return "OpenAI";
  if (provider === "groq") return "Groq";
  if (provider === "ollama") return "Ollama";
  return provider;
}

export function formatCoverage(observed: number | null | undefined, expected: number | null | undefined) {
  if (observed == null || expected == null || expected <= 0) return "Coverage unavailable";
  return `${observed}/${expected} calls (${((observed / expected) * 100).toFixed(0)}%)`;
}

export function primaryScoreInterval(row: ModelResult): [number, number] {
  return row.family_cluster_safe_success_ci95 ?? row.safe_success_ci95 ?? row.task_success_ci95;
}

export function secondaryScoreInterval(row: ModelResult): [number, number] | null {
  if (!row.family_cluster_safe_success_ci95) return null;
  return row.safe_success_ci95 ?? row.task_success_ci95;
}

export function primaryScoreIntervalLabel(row: ModelResult) {
  return row.family_cluster_safe_success_ci95 ? "Family-cluster 95% interval" : "Wilson 95% interval";
}

export function hasComparableTelemetry(row: ModelResult, mode: "tokens" | "time") {
  if (mode === "tokens") {
    return row.token_usage?.complete === true && Number.isFinite(row.token_usage.median_total_tokens);
  }
  return row.duration_telemetry?.complete === true && Number.isFinite(row.median_duration_seconds);
}
