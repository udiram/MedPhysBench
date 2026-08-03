import { useMemo, useState } from "react";
import { domainLabel, formatPercent, normalizeModelDisplayName, providerLabel } from "../lib/format";
import { isCommonHarnessRun } from "../lib/runSurface";
import type { Leaderboard, ModelCatalogEntry, ModelResult, ReleaseView, ReviewEvidence } from "../types";

type ViewMode = "capability" | "failures" | "evidence";
type ScopeMode = "official" | "native" | "all";
type SourceFilter = "all" | "open" | "closed" | "unknown";

type Props = {
  data: Leaderboard | null;
  loadError?: boolean;
  releaseView: ReleaseView;
  modelCatalog: ModelCatalogEntry[];
  reviewEvidence: ReviewEvidence | null;
};

type Family = {
  id: string;
  label: string;
  taskIds: Set<string>;
  domain?: string;
};

export function CapabilityExplorer({ data, loadError = false, releaseView, modelCatalog, reviewEvidence }: Props) {
  const [view, setView] = useState<ViewMode>("capability");
  const [scope, setScope] = useState<ScopeMode>("all");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [providerFilter, setProviderFilter] = useState("all");
  const effectiveScope = scope;

  const rows = useMemo(() => {
    const catalogIndex = Object.fromEntries(
      modelCatalog.map((entry) => [`${entry.provider}::${entry.model_name}`, entry]),
    );
    const combined = data ? [...data.models, ...(data.unranked_models ?? [])] : [];
    return combined
      .filter((row) => {
        const surfaceMatch =
          effectiveScope === "all" ||
          (effectiveScope === "official" ? isCommonHarnessRow(row) : !isCommonHarnessRow(row));
        const source = modelSource(row, catalogIndex);
        const sourceMatch = sourceFilter === "all" || source === sourceFilter;
        const providerMatch = providerFilter === "all" || row.provider === providerFilter;
        return surfaceMatch && sourceMatch && providerMatch;
      })
      .sort((a, b) => {
        if (effectiveScope === "official") {
          return rankGroup(a).localeCompare(rankGroup(b)) || (a.rank ?? Infinity) - (b.rank ?? Infinity);
        }
        return (a.outcome_rank ?? Infinity) - (b.outcome_rank ?? Infinity);
      });
  }, [data, effectiveScope, modelCatalog, sourceFilter, providerFilter]);
  const families = useMemo(() => buildFamilies(data, rows), [data, rows]);

  if (!data) {
    return (
      <section className="capability-section" id="capabilities" aria-busy={!loadError}>
        <div className="section-heading">
          <h2>Where performance breaks</h2>
          <p>Capability and failure evidence appears only after the signed public result bundle is available.</p>
        </div>
        <p className="table-state" role={loadError ? "alert" : "status"}>
          {loadError
            ? "Capability evidence could not be loaded. No missing values have been interpreted as zero."
            : "Loading capability and evidence-maturity records…"}
        </p>
      </section>
    );
  }

  return (
    <section className="capability-section" id="capabilities">
      <div className="section-heading section-heading-row">
        <div>
          <h2>Where performance breaks</h2>
          <p>
            Aggregate attempts into interpretable capability groups. The matrix shows safe success;
            the failure view partitions every recorded attempt without double counting.
          </p>
        </div>
        <p className="coverage-summary">{families.length} capability group{families.length === 1 ? "" : "s"} · {rows.length} visible rows</p>
      </div>

      <div className="capability-toolbar">
        <div className="view-switch" role="group" aria-label="Capability analysis view">
          {([
            ["capability", "Capability profile"],
            ["failures", "Failure modes"],
            ["evidence", "Evidence quality"],
          ] as const).map(([value, label]) => (
            <button key={value} type="button" aria-pressed={view === value} onClick={() => setView(value)}>
              {label}
            </button>
          ))}
        </div>
        <div className="scope-switch" role="group" aria-label="Result comparison scope">
          {([
            ["all", "All visible"],
            ["official", "Common harness"],
            ["native", "Native / imported"],
          ] as const).map(([value, label]) => (
            <button key={value} type="button" aria-pressed={effectiveScope === value} onClick={() => setScope(value)}>
              {label}
            </button>
          ))}
        </div>
        <label className="field">
          <span>Openness</span>
          <span className="select-wrap">
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as SourceFilter)}>
              <option value="all">All systems</option>
              <option value="open">Open weights</option>
              <option value="closed">Closed models</option>
              <option value="unknown">Unclassified</option>
            </select>
          </span>
        </label>
        <label className="field">
          <span>Provider</span>
          <span className="select-wrap">
            <select value={providerFilter} onChange={(event) => setProviderFilter(event.target.value)}>
              <option value="all">All providers</option>
              {[...new Set(
                [
                  ...(data ? [...data.models, ...(data.unranked_models ?? [])] : []).map((row) => row.provider),
                  ...modelCatalog.map((entry) => entry.provider),
                ],
              )]
                .sort((left, right) => left.localeCompare(right))
                .map((providerValue) => (
                  <option key={providerValue} value={providerValue}>
                    {providerLabel(providerValue)}
                  </option>
                ))}
            </select>
          </span>
        </label>
      </div>

      {view === "capability" && <CapabilityMatrix rows={rows} families={families} scope={effectiveScope} />}
      {view === "failures" && <FailureBreakdown rows={rows} />}
      {view === "evidence" && <EvidenceQuality data={data} releaseView={releaseView} reviewEvidence={reviewEvidence} />}
    </section>
  );
}

function CapabilityMatrix({ rows, families, scope }: { rows: ModelResult[]; families: Family[]; scope: ScopeMode }) {
  if (rows.length === 0 || families.length === 0) {
    return <EmptyState title="No capability evidence in this scope" body="Choose another comparison scope or release." />;
  }
  return (
    <>
      <div className="capability-table-wrap" role="region" aria-label="Safe success by model and capability group" tabIndex={0}>
        <table className="capability-table">
          <caption>Safe success rate by model and descriptive capability group</caption>
          <thead>
            <tr>
              <th>Model</th>
              {families.map((family) => <th key={family.id}>{family.label}</th>)}
              <th>Overall</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.model_name}>
                <th scope="row">
                  <strong>{shortModel(row.model_name)}</strong>
                  <span>{row.ranking_eligible ? `${rankGroupLabel(row)} #${row.rank ?? "—"}` : `Outcome #${row.outcome_rank ?? "—"} · native`}</span>
                </th>
                {families.map((family) => {
                  const attempts = row.tasks.filter((task) => family.taskIds.has(task.task_id));
                  const labelled = attempts.filter((task) => typeof task.passed === "boolean");
                  const safePasses = labelled.filter((task) => task.passed === true && task.safe).length;
                  const derivedRate = labelled.length === attempts.length && attempts.length ? safePasses / attempts.length : null;
                  const aggregateRate = family.domain ? row.domain_safe_success[family.domain] : undefined;
                  const rate = derivedRate ?? aggregateRate ?? null;
                  const evidence = derivedRate != null
                    ? `${safePasses}/${attempts.length} attempts`
                    : rate != null
                      ? `${attempts.length} task${attempts.length === 1 ? "" : "s"} · aggregate`
                      : "n/a";
                  return (
                    <td key={family.id} className={heatClass(rate)}>
                      <strong>{formatPercent(rate)}</strong>
                      <span>{evidence}</span>
                    </td>
                  );
                })}
                <td className={heatClass(row.safe_success_rate)}>
                  <strong>{formatPercent(row.safe_success_rate)}</strong>
                  <span>{row.completed_count}/{row.expected_attempt_count} attempts</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="capability-footnote">
        Capability groups organize related task types for interpretation; they are not the independent patient or case family count. {" "}
        {scope === "all"
          ? "Official and native rows are shown together for descriptive inspection only; ranks do not cross execution surfaces."
          : scope === "native"
            ? "Native audits use the frozen task pack on a different execution surface and do not receive an official cross-surface rank."
            : "Rows are ordered only within their identical provider, adapter, harness revision, and release comparison group."}
      </p>
    </>
  );
}

function isCommonHarnessRow(row: ModelResult): boolean {
  return isCommonHarnessRun(row);
}

function modelSource(
  row: ModelResult,
  catalogIndex: Record<string, ModelCatalogEntry>,
): "open" | "closed" | "unknown" {
  const modelKey = `${row.provider}::${row.model_name}`;
  const catalog = catalogIndex[modelKey];
  return catalog?.openness ?? "unknown";
}

function FailureBreakdown({ rows }: { rows: ModelResult[] }) {
  if (rows.length === 0) return <EmptyState title="No failure evidence in this scope" body="Choose another comparison scope or release." />;
  const completeRows = rows.filter((row) => row.tasks.length > 0 && row.tasks.every((task) => typeof task.passed === "boolean"));
  if (completeRows.length === 0) {
    return <EmptyState title="Attempt-level outcome partition unavailable" body="This legacy projection publishes aggregate scores but not the pass label needed to derive mutually exclusive failure categories. No categories are imputed." />;
  }
  return (
    <div className="failure-panel">
      <div className="failure-legend" aria-label="Failure mode legend">
        <span><i className="failure-success" /> Safe success</span>
        <span><i className="failure-safe" /> Safe task failure</span>
        <span><i className="failure-unsafe" /> Unsafe outcome</span>
        <span><i className="failure-unavailable" /> Capability unavailable</span>
      </div>
      <div className="failure-rows">
        {completeRows.map((row) => {
          const total = row.tasks.length;
          const success = row.tasks.filter((task) => task.passed === true && task.safe).length;
          const unavailable = row.tasks.filter((task) => task.outcome_category === "unavailable" || task.capability_failure === true).length;
          const unsafe = row.tasks.filter(
            (task) => task.safe === false && task.outcome_category !== "unavailable" && task.capability_failure !== true,
          ).length;
          const safeFailure = Math.max(0, total - success - unsafe - unavailable);
          return (
            <article key={row.model_name} className="failure-row">
              <header>
                <strong>{shortModel(row.model_name)}</strong>
                <span>{total} recorded attempts</span>
              </header>
              <div className="failure-stack" aria-label={`${row.model_name}: ${success} safe successes, ${safeFailure} safe failures, ${unsafe} unsafe outcomes, ${unavailable} capability-unavailable outcomes`}>
                <i className="failure-success" style={{ width: `${share(success, total)}%` }} />
                <i className="failure-safe" style={{ width: `${share(safeFailure, total)}%` }} />
                <i className="failure-unsafe" style={{ width: `${share(unsafe, total)}%` }} />
                <i className="failure-unavailable" style={{ width: `${share(unavailable, total)}%` }} />
              </div>
              <dl>
                <div><dt>Safe success</dt><dd>{success}/{total}</dd></div>
                <div><dt>Safe fail</dt><dd>{safeFailure}/{total}</dd></div>
                <div><dt>Unsafe</dt><dd>{unsafe}/{total}</dd></div>
                <div><dt>Unavailable</dt><dd>{unavailable}/{total}</dd></div>
                <div><dt>Valid output</dt><dd>{formatPercent(row.valid_output_rate)}</dd></div>
                <div><dt>Escalation</dt><dd>{formatPercent(row.appropriate_escalation_rate)}</dd></div>
              </dl>
            </article>
          );
        })}
      </div>
      <p className="capability-footnote">The stacked categories are mutually exclusive. Capability-unavailable attempts are counted separately from unsafe outcomes. Output validity and escalation are shown separately because they can overlap those outcomes.{completeRows.length < rows.length ? ` ${rows.length - completeRows.length} row(s) without attempt-level pass labels are omitted.` : ""}</p>
    </div>
  );
}

function EvidenceQuality({ data, releaseView, reviewEvidence }: Pick<Props, "data" | "releaseView" | "reviewEvidence">) {
  const officialRows = data?.models ?? [];
  const completeRows = officialRows.filter((row) => row.completed_count === row.expected_attempt_count).length;
  const repeats = data?.release.expected_attempts_per_task ?? 1;
  const families = data?.release.family_count;
  const maxFamilyShare = data?.release.max_family_share;
  const releaseMeta = evidenceFor(releaseView, reviewEvidence);
  const rows = [
    {
      label: "Comparable harness",
      state: officialRows.length > 0 ? "Available" : "Unavailable",
      tone: officialRows.length > 0 ? "good" : "bad",
      detail: officialRows.length > 0 ? `${officialRows.length} official row(s); ranks stay inside frozen comparison groups.` : "No official comparison group is published.",
    },
    {
      label: "Complete attempt matrices",
      state: officialRows.length > 0 && completeRows === officialRows.length ? "Complete" : "Partial",
      tone: officialRows.length > 0 && completeRows === officialRows.length ? "good" : "warn",
      detail: `${completeRows}/${officialRows.length} official rows have every declared attempt artifact.`,
    },
    {
      label: "Repeated trials",
      state: repeats >= 5 ? "Comparison-grade" : repeats >= 3 ? "Pilot-grade" : "Single-shot",
      tone: repeats >= 5 ? "good" : repeats >= 3 ? "warn" : "bad",
      detail: `${repeats} declared attempt${repeats === 1 ? "" : "s"} per task; headline stochastic comparisons target at least five.`,
    },
    {
      label: "Independent families",
      state: families == null ? "Not declared" : families >= 10 ? "Broad" : "Limited",
      tone: families != null && families >= 10 ? "good" : "warn",
      detail: families == null ? "No family structure is declared for this release." : `${families} independent family unit${families === 1 ? "" : "s"}; correlated task views are not counted as independent patients.`,
    },
    {
      label: "Family concentration guard",
      state: maxFamilyShare == null ? "Not declared" : "Enforced",
      tone: maxFamilyShare == null ? "warn" : "good",
      detail: maxFamilyShare == null
        ? "This historical projection does not publish a task-family cap."
        : `No family may contribute more than ${formatPercent(maxFamilyShare)} of tasks without an explicit reviewed override.`,
    },
    ...releaseMeta,
  ];
  return (
    <div className="evidence-quality">
      {rows.map((row) => (
        <article key={row.label}>
          <h3>{row.label}</h3>
          <p className={`evidence-state ${row.tone}`}><i aria-hidden="true" />{row.state}</p>
          <p>{row.detail}</p>
        </article>
      ))}
      <div className="claim-boundary-panel">
        <div>
          <strong>What this release can support</strong>
          <p>{claimBoundary(releaseView).allowed}</p>
        </div>
        <div>
          <strong>What it cannot support</strong>
          <p>{claimBoundary(releaseView).prohibited}</p>
        </div>
      </div>
    </div>
  );
}

function buildFamilies(data: Leaderboard | null, visibleRows: ModelResult[]): Family[] {
  const tasks = data?.tasks ?? [];
  const buckets = new Map<string, Family>();
  const exposesAttemptOutcomes = visibleRows.some((row) => row.tasks.some((task) => typeof task.passed === "boolean"));
  for (const task of tasks) {
    if (!exposesAttemptOutcomes) {
      const bucket = buckets.get(task.domain) ?? {
        id: task.domain,
        label: domainLabel(task.domain),
        domain: task.domain,
        taskIds: new Set<string>(),
      };
      bucket.taskIds.add(task.task_id);
      buckets.set(task.domain, bucket);
      continue;
    }
    const [id, label] = familyForTask(task.task_id, task.track);
    const bucket = buckets.get(id) ?? { id, label, taskIds: new Set<string>() };
    bucket.taskIds.add(task.task_id);
    buckets.set(id, bucket);
  }
  return [...buckets.values()].sort((a, b) => a.label.localeCompare(b.label));
}

function familyForTask(taskId: string, track: string): [string, string] {
  if (taskId.includes("parotid-segmentation")) return ["structure-localization", "Structure localization"];
  if (taskId.includes("high-dose-segmentation")) return ["dose-localization", "Dose localization"];
  if (taskId.includes("plan-criteria")) return ["plan-criteria", "Plan criteria"];
  if (taskId.includes("structure-inventory")) return ["data-integrity", "Data integrity"];
  if (taskId.includes("tg263") || track.includes("tg263")) return ["tg263", "TG-263 naming"];
  const label = track.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
  return [track, label];
}

function evidenceFor(view: ReleaseView, reviewEvidence: ReviewEvidence | null) {
  if (view === "real") {
    if (!reviewEvidence) {
      return [
        { label: "Release review ledger", state: "Unavailable", tone: "bad", detail: "The signed public review ledger could not be loaded; no review or human-baseline claim is inferred." },
      ];
    }
    const domainReview = reviewEvidence.independent_domain_review;
    const humanBaseline = reviewEvidence.human_baseline;
    const rights = reviewEvidence.data_rights_review;
    return [
      { label: "Independent domain review", state: `${domainReview.completed}/${domainReview.target} · ${domainReview.status}`, tone: domainReview.status === "complete" ? "good" : "bad", detail: domainReview.note },
      { label: "Human baseline", state: `${humanBaseline.completed}/${humanBaseline.target} · ${humanBaseline.status}`, tone: humanBaseline.status === "complete" ? "good" : "bad", detail: humanBaseline.note },
      { label: "Publication rights review", state: rights.status.replaceAll("_", " "), tone: rights.status === "documented" ? "good" : "warn", detail: rights.note },
      { label: "Protected holdout", state: "Not operating", tone: "bad", detail: "This public pilot is a development surface and is vulnerable to direct optimization." },
    ];
  }
  if (view === "imaging") {
    return [
      { label: "Independent domain review", state: "Not complete", tone: "bad", detail: "The public imaging pilot has not yet cleared external physicist and imaging-expert review." },
      { label: "Human baseline", state: "Not published", tone: "bad", detail: "No human-reader or contouring baseline is published for this pilot." },
      { label: "Protected holdout", state: "Not operating", tone: "bad", detail: "The released imaging fixtures are public and development-facing, not contamination-resistant." },
    ];
  }
  return [
    { label: "Independent domain review", state: "Not complete", tone: "bad", detail: "The public development lane has not passed an external physicist review gate." },
    { label: "Human baseline", state: "Not published", tone: "bad", detail: "Scores are model-only research evidence and must not be described as human-level performance." },
    { label: "Protected holdout", state: "Not operating", tone: "bad", detail: "Public tasks, prompts, and gold contracts are inspectable; use this lane for development and regression only." },
  ];
}

function claimBoundary(view: ReleaseView) {
  if (view === "real") return {
    allowed: "Provisional, repeated-trial comparison on two pinned OpenKBP families under declared frozen harness groups.",
    prohibited: "Clinical validation, autonomous planning competence, ten independent-patient claims, or human-level performance.",
  };
  if (view === "tg263") return {
    allowed: "Public development evidence for collision-aware TG-263 decisions and grader-contract auditing.",
    prohibited: "Cross-surface native ranking, treatment-system naming validation, or autonomous structure approval.",
  };
  if (view === "imaging") return {
    allowed: "Research-only evaluation on frozen public imaging fixtures and benchmark-authored segmentation or interpretation contracts.",
    prohibited: "Diagnostic validation, clinical contouring authority, or prospective reader-performance claims.",
  };
  return {
    allowed: "Public development and regression evidence across medical-physics knowledge, calculations, artifact checks, and escalation.",
    prohibited: "Contamination-resistant frontier ranking, clinical competence, or human-level performance.",
  };
}

function heatClass(rate: number | null) {
  if (rate == null) return "heat-na";
  if (rate >= 0.8) return "heat-high";
  if (rate >= 0.5) return "heat-mid";
  return "heat-low";
}

function rankGroup(row: ModelResult) {
  return row.comparison_group ?? row.rank_group ?? row.provider;
}

function rankGroupLabel(row: ModelResult) {
  return providerLabel(row.provider);
}

function shortModel(value: string) {
  return normalizeModelDisplayName(value)
    .replace("[effort=", " · ")
    .replace("]", "")
    .replace("llama-", "Llama ")
    .replace("qwen", "Qwen")
    .replace("gemma", "Gemma");
}

function share(value: number, total: number) {
  return total > 0 ? (value / total) * 100 : 0;
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return <div className="analysis-empty" role="status"><strong>{title}</strong><p>{body}</p></div>;
}
