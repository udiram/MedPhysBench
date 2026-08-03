import type { ReleaseEvidence, ReleaseEvidenceIndex, ReleaseView } from "../types";

export type EvidenceTone = "good" | "warn" | "bad";

export function releaseEvidenceFor(
  index: ReleaseEvidenceIndex | null,
  releaseId: string | undefined,
): ReleaseEvidence | null {
  if (!index || index.schema_version !== "medphysbench.release-evidence-index.v1" || !releaseId) return null;
  const matches = index.releases.filter((entry) => entry.release_id === releaseId);
  return matches.length === 1 ? matches[0] : null;
}

export function maturityLabel(value: ReleaseEvidence["maturity"]): string {
  return value.replaceAll("_", "-");
}

export function interactionDepthLabel(value: ReleaseEvidence["interaction"]["depth"]): string {
  if (value === "stateful_workflow") return "Stateful workflow";
  if (value === "mixed") return "Mixed interaction";
  return "Single response";
}

export function evidenceStatusLabel(value: string): string {
  return value.replaceAll("_", " ");
}

export function countStateLabel(state: ReleaseEvidence["evidence"]["human_baseline"]): string {
  const count = state.target == null ? `${state.completed}` : `${state.completed}/${state.target}`;
  return `${count} · ${evidenceStatusLabel(state.status)}`;
}

export function countStateTone(state: ReleaseEvidence["evidence"]["human_baseline"]): EvidenceTone {
  if (state.status === "complete") return "good";
  if (state.status === "recruiting" || state.status === "pending") return "warn";
  return "bad";
}

export function evidenceClaimText(values: string[]): string {
  return values.join("; ");
}

export function releaseIdForView(releaseView: ReleaseView): string {
  if (releaseView === "core") return "public-core-v0.4";
  if (releaseView === "imaging") return "public-imaging-pilot-v0.4";
  if (releaseView === "tg263") return "public-tg263-pilot-v0.5";
  return "public-real-workflows-pilot-v0.6";
}

export function releaseTitleForView(releaseView: ReleaseView): string {
  if (releaseView === "core") return "MedPhysBench Public Core v0.4";
  if (releaseView === "imaging") return "MedPhysBench Imaging Pilot";
  if (releaseView === "tg263") return "MedPhysBench Public TG-263 Pilot v0.5";
  return "MedPhysBench OpenKBP Real-Data Workflow-View Pilot v0.6";
}

export function normalizeReleaseTitle(value: string | null | undefined, releaseView: ReleaseView): string {
  if (!value) return releaseTitleForView(releaseView);
  return releaseView === "real"
    ? value.replace("Real-Workflow", "Real-Data Workflow-View")
    : value;
}
