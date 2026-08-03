export type IntegrityIssueView = {
  code: string;
  label: string;
  detail: string;
};

export type IntegrityIssueGroup = {
  code: string;
  label: string;
  count: number;
  examples: string[];
};

const ISSUE_LABELS: Record<string, string> = {
  missing_adapter_settings_hash: "Adapter settings hash missing",
  missing_grader_hash: "Grader hash missing",
  missing_prompt_hash: "Prompt hash missing",
  missing_run_configuration_hash: "Run configuration hash missing",
  missing_runtime_task_hash: "Runtime task hash missing",
  missing_scoring_revision: "Scoring revision missing",
  missing_tool_schema_hash: "Tool schema hash missing",
  stored_grades_disagree_with_regrade: "Stored grade differs from deterministic regrade",
  unranked_comparison_profile: "Comparison profile is not rankable",
  unranked_incomplete_release: "Release matrix is incomplete",
  unranked_legacy_manifest: "Legacy manifest is not rankable",
  unranked_native_surface: "Native/import surface is outcome-only",
  unranked_native_pilot_surface: "Native pilot is outcome-only",
  unranked_noncommon_surface: "Non-common harness row is outcome-only",
};

export function formatIntegrityIssue(issue: string): IntegrityIssueView {
  const [code = "integrity_finding", taskId, attemptIndex, ...rest] = issue.split(":");
  const label = ISSUE_LABELS[code] ?? sentenceCase(code);
  const detailParts: string[] = [];
  if (taskId) detailParts.push(taskId);
  if (attemptIndex && /^\d+$/.test(attemptIndex)) {
    detailParts.push(`attempt ${Number(attemptIndex) + 1}`);
  } else if (attemptIndex) {
    detailParts.push(attemptIndex);
  }
  if (rest.length) detailParts.push(rest.join(":"));
  return {
    code,
    label,
    detail: detailParts.join(" · ") || "Run-level finding",
  };
}

export function groupIntegrityIssues(issues: string[], maxExamples = 2): IntegrityIssueGroup[] {
  const grouped = new Map<string, IntegrityIssueGroup>();
  for (const issue of issues) {
    const finding = formatIntegrityIssue(issue);
    const current = grouped.get(finding.code) ?? {
      code: finding.code,
      label: finding.label,
      count: 0,
      examples: [],
    };
    current.count += 1;
    if (finding.detail !== "Run-level finding" && !current.examples.includes(finding.detail) && current.examples.length < maxExamples) {
      current.examples.push(finding.detail);
    }
    grouped.set(finding.code, current);
  }
  return [...grouped.values()].sort(
    (left, right) => right.count - left.count || left.label.localeCompare(right.label),
  );
}

export function integrityIssueHeadline(issues: string[]) {
  const count = issues.length;
  if (count === 0) return "Integrity checks passed";
  const findingLabel = `${count} finding${count === 1 ? "" : "s"}`;
  if (issues.every((issue) => issue.startsWith("missing_"))) {
    return `Legacy contract gaps · ${findingLabel}`;
  }
  if (issues.every((issue) => issue.startsWith("unranked_"))) {
    return `Comparison exclusions · ${findingLabel}`;
  }
  return `Integrity review · ${findingLabel}`;
}

function sentenceCase(value: string) {
  const normalized = value.replaceAll("_", " ").trim();
  if (!normalized) return "Integrity finding";
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}
