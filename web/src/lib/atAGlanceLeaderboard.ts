import { scoreEvidenceAvailable } from "./resultEvidence.ts";
import { rowVisibleInResultsScope, type ResultsScope } from "./resultsScope.ts";
import type { Leaderboard, ModelCatalogEntry, ModelResult } from "../types";

export type AtAGlanceSource = "all" | "open" | "closed";

export function atAGlanceRows(
  data: Leaderboard | null,
  modelCatalog: readonly ModelCatalogEntry[],
  resultsScope: ResultsScope,
  source: AtAGlanceSource,
  limit = 10,
): ModelResult[] {
  if (!data) return [];
  const catalogIndex = new Map(modelCatalog.map((entry) => [`${entry.provider}::${entry.model_name}`, entry]));
  const ordered = [...data.models, ...(data.unranked_models ?? [])]
    .filter((row) =>
      rowVisibleInResultsScope(row, resultsScope)
      && scoreEvidenceAvailable(row)
      && row.completed_count === row.expected_attempt_count
      && row.error_count === 0
      && row.integrity.missing_attempt_keys === 0
    )
    .filter((row) => {
      if (source === "all") return true;
      return catalogIndex.get(`${row.provider}::${row.model_name}`)?.openness === source;
    })
    .sort(compareOutcomeRows);
  const seen = new Set<string>();
  return ordered.filter((row) => {
    const baseId = catalogIndex.get(`${row.provider}::${row.model_name}`)?.base_model_id
      ?? `${row.provider}::${row.model_name}`;
    if (seen.has(baseId)) return false;
    seen.add(baseId);
    return true;
  }).slice(0, limit);
}

function compareOutcomeRows(left: ModelResult, right: ModelResult) {
  return (left.outcome_rank ?? Number.POSITIVE_INFINITY) - (right.outcome_rank ?? Number.POSITIVE_INFINITY)
    || right.safe_success_rate - left.safe_success_rate
    || right.safety_gate_rate - left.safety_gate_rate
    || right.valid_output_rate - left.valid_output_rate
    || left.model_name.localeCompare(right.model_name);
}
