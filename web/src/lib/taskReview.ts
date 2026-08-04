import type { ReviewEvidence } from "../types";

export type TaskReviewRecord = ReviewEvidence["task_reviews"][number];

export function taskReviewFor(
  evidence: ReviewEvidence | null,
  taskId: string | null | undefined,
): TaskReviewRecord | null {
  if (!evidence || !taskId) return null;
  const matches = evidence.task_reviews.filter((record) => record.task_id === taskId);
  return matches.length === 1 ? matches[0] : null;
}

export function taskReviewLabel(record: TaskReviewRecord | null): string {
  if (!record) return "Review evidence unavailable";
  if (record.domain_review === "approved") return "Physicist reviewed";
  if (record.domain_review === "revision_required") return "Revision required";
  return "Physicist review pending";
}

export function feasibilityLabel(record: TaskReviewRecord | null): string {
  if (!record) return "Reference feasibility unavailable";
  if (record.reference_feasibility === "automated_pass") return "Automated feasibility passed";
  if (record.reference_feasibility === "failed") return "Reference feasibility failed";
  return "Reference feasibility pending";
}

export function taskReviewTone(record: TaskReviewRecord | null): "good" | "warn" | "bad" | "neutral" {
  if (!record) return "neutral";
  if (record.domain_review === "revision_required" || record.reference_feasibility === "failed") return "bad";
  if (record.domain_review === "approved" && record.reference_feasibility === "automated_pass") return "good";
  return "warn";
}
