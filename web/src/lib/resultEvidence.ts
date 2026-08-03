import type { ModelResult } from "../types";

type ScoreEvidenceInput = Pick<ModelResult, "outcome_order_eligible" | "ranking_eligible">;

export type ScoreEvidenceKind = "official" | "native_descriptive" | "common_unranked" | "incomplete";

export function scoreEvidenceAvailable(row: ScoreEvidenceInput) {
  return row.outcome_order_eligible !== false;
}

export function scoreEvidenceKind(row: ScoreEvidenceInput, nativeSurface: boolean): ScoreEvidenceKind {
  if (!scoreEvidenceAvailable(row)) return "incomplete";
  if (row.ranking_eligible) return "official";
  return nativeSurface ? "native_descriptive" : "common_unranked";
}
