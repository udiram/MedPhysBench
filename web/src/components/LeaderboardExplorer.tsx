import { ArrowDownToLine, ChevronDown, Search } from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { classifyAttemptOutcome } from "../types";
import type { AccessStatus, Leaderboard, ModelCatalogEntry, ModelResult, ReleaseView, Tg263Audit } from "../types";
import {
  domainLabel,
  formatDuration,
  formatPercent,
  formatTokens,
  primaryScoreInterval,
  primaryScoreIntervalLabel,
  normalizeModelDisplayName,
  providerLabel,
  secondaryScoreInterval,
  shortHash,
} from "../lib/format";
import { modelRunKey } from "../lib/modelRunKey";
import {
  DEFAULT_CHART_ROW_LIMIT,
  DEFAULT_TABLE_ROW_LIMIT,
  limitEvidenceRows,
} from "../lib/efficiencyScope";
import { releaseIdForView } from "../lib/releaseEvidence";
import { versionedDataUrl } from "../lib/dataAssets";
import { inferExecutionSurface, surfaceLabel } from "../lib/runSurface";
import { competitionRankMap } from "../lib/ranking";
import { rowVisibleInResultsScope, type ResultsScope } from "../lib/resultsScope";
import { navigateToRunForensics } from "../lib/forensicsNavigation";

type SortKey =
  | "model_name"
  | "safe_success_rate"
  | "task_success_rate"
  | "safety_gate_rate"
  | "valid_output_rate"
  | "appropriate_escalation_rate"
  | "median_duration_seconds";

type LeaderboardExplorerProps = {
  data: Leaderboard | null;
  accessStatus: AccessStatus[];
  modelCatalog: ModelCatalogEntry[];
  loadError: boolean;
  releaseView: ReleaseView;
  resultsScope: ResultsScope;
  tg263Audit: Tg263Audit | null;
};

const SORT_KEYS: Array<{ key: SortKey; label: string }> = [
  { key: "model_name", label: "Model" },
  { key: "safe_success_rate", label: "Score" },
  { key: "task_success_rate", label: "Task success" },
  { key: "safety_gate_rate", label: "Safety" },
  { key: "valid_output_rate", label: "Output" },
  { key: "appropriate_escalation_rate", label: "Escalation" },
  { key: "median_duration_seconds", label: "Median time" },
];

const RELEASE_DOWNLOAD: Record<ReleaseView, string> = {
  core: versionedDataUrl("/data/leaderboard.json"),
  imaging: versionedDataUrl("/data/imaging_leaderboard.json"),
  tg263: versionedDataUrl("/data/tg263_leaderboard.json"),
  real: versionedDataUrl("/data/public-real-workflows-pilot-v0.6.json"),
};

type ModelOpenness = "open" | "closed" | "unknown";

function catalogIndexForModelRow(model: ModelResult, catalogIndex: Record<string, ModelCatalogEntry>) {
  return catalogIndex[`${model.provider}::${model.model_name}`] ?? null;
}

function modelSourceRow(model: ModelResult, catalogEntry: ModelCatalogEntry | null): ModelOpenness {
  return catalogEntry?.openness ?? "unknown";
}

function modelSourceLabel(value: ModelOpenness) {
  if (value === "open") return "Open";
  if (value === "closed") return "Closed";
  return "Unknown";
}

function integrityLabel(value: string) {
  if (value === "unranked_noncommon_surface") return "Official rank withheld: native/import surface";
  if (value === "unranked_native_pilot_surface") return "Official rank withheld: native pilot surface";
  if (value === "unranked_singleton_comparison_group") return "Official rank withheld: no peer with identical frozen harness contract";
  if (value === "mixed_run_configuration_manifest") return "Integrity failure: mixed runtime configuration";
  if (value === "mixed_seed_policy_manifest") return "Integrity failure: mixed seed policy";
  if (value === "missing_execution_trace") return "Integrity failure: execution trace absent";
  if (value === "missing_model_response_trace") return "Integrity failure: model-response event absent";
  if (value === "missing_provider_receipt") return "Integrity failure: provider/runtime receipt absent";
  if (value === "missing_usage_telemetry") return "Integrity failure: provider usage telemetry absent";
  if (value === "missing_duration_telemetry") return "Integrity failure: positive call duration absent";
  return value.replaceAll("_", " ");
}

function failureLanes(tasks: readonly LeaderboardExplorerTask[]) {
  const laneCounts = new Map<string, number>();
  for (const task of tasks) {
    for (const lane of task.failed_lanes ?? []) {
      laneCounts.set(lane, (laneCounts.get(lane) ?? 0) + 1);
    }
  }
  if (laneCounts.size === 0) {
    return "No recorded lane-level failures.";
  }
  return [...laneCounts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .map(([lane, count]) => `${lane}: ${count}`)
    .join(", ");
}

type LeaderboardExplorerTask = {
  failed_lanes?: string[];
  failed_graders?: string[];
};

export function LeaderboardExplorer({
  data,
  accessStatus,
  modelCatalog,
  loadError,
  releaseView,
  resultsScope,
  tg263Audit,
}: LeaderboardExplorerProps) {
  const [query, setQuery] = useState("");
  const [domainFilter, setDomainFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState<"all" | "open" | "closed" | "unknown">("all");
  const [providerFilter, setProviderFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("safe_success_rate");
  const [sortDirection, setSortDirection] = useState<"desc" | "asc">("desc");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  useEffect(() => setSummaryExpanded(false), [data?.release.release_id]);
  const deferredQuery = useDeferredValue(query);
  const effectiveStatusFilter = resultsScope === "official" ? "ranked" : statusFilter;
  const allRows = useMemo(
    () => withDerivedOutcomeRanks(data ? [...data.models, ...(data.unranked_models ?? [])] : []),
    [data],
  );
  const catalogIndex = useMemo(
    () =>
      Object.fromEntries(
        modelCatalog.map((entry) => [`${entry.provider}::${entry.model_name}`, entry]),
      ) as Record<string, ModelCatalogEntry>,
    [modelCatalog],
  );

  const domains = useMemo(() => {
    const values = new Set<string>();
    data?.tasks.forEach((task) => values.add(task.domain));
    return [...values].sort();
  }, [data]);

  const rows = useMemo(() => {
    return allRows
      .filter((model) => {
        const q = deferredQuery.trim().toLowerCase();
        const matchesQuery =
          !q ||
          model.model_name.toLowerCase().includes(q) ||
          model.provider.toLowerCase().includes(q);
        const matchesStatus =
          effectiveStatusFilter === "all" ||
          (effectiveStatusFilter === "ranked" && model.ranking_eligible) ||
          (effectiveStatusFilter === "review" && !model.ranking_eligible);
        const source = modelSourceRow(model, catalogIndexForModelRow(model, catalogIndex));
        const matchesSource = sourceFilter === "all" || source === sourceFilter;
        const matchesProvider = providerFilter === "all" || model.provider === providerFilter;
        return rowVisibleInResultsScope(model, resultsScope)
          && matchesQuery
          && matchesStatus
          && matchesSource
          && matchesProvider;
      })
      .sort((left, right) => compareRows(left, right, sortKey, sortDirection, domainFilter));
  }, [
    allRows,
    catalogIndex,
    deferredQuery,
    domainFilter,
    sortDirection,
    sortKey,
    effectiveStatusFilter,
    sourceFilter,
    providerFilter,
    resultsScope,
  ]);

  const summaryRows = allRows.filter((row) => rowVisibleInResultsScope(row, resultsScope)).sort(
    (left, right) =>
      (left.outcome_rank ?? Infinity) - (right.outcome_rank ?? Infinity) ||
      left.model_name.localeCompare(right.model_name),
  );
  const visibleSummaryRows = limitEvidenceRows(summaryRows, summaryExpanded, DEFAULT_TABLE_ROW_LIMIT);
  const blocked = accessStatus.filter((item) => item.status !== "available");

  return (
    <section className="leaderboard-section" id="leaderboard">
      <div className="results-meta-row">
        <div className="section-heading">
          <h2>{releaseTitle(releaseView)}</h2>
          <p>{releaseSummary(releaseView)}</p>
        </div>
        <div className="results-meta-actions">
          <p className="results-release-stamp">
            {data?.release.release_id ?? fallbackReleaseId(releaseView)}
            <span>{formatArtifactDate(data?.generated_at)}</span>
          </p>
          <a className="download-link" href={RELEASE_DOWNLOAD[releaseView]} download>
            <ArrowDownToLine aria-hidden="true" /> Download JSON
          </a>
        </div>
      </div>

      <div className="results-workbench">
        <article className="results-visual">
          {releaseView === "tg263" ? (
            <Tg263AuditChart audit={tg263Audit} />
          ) : (
            <OutcomeIntervalPlot
              key={`${data?.release.release_id ?? releaseView}-${resultsScope}`}
              data={data}
              resultsScope={resultsScope}
            />
          )}
        </article>
        <aside className="results-summary">
          <div className="results-summary-head">
            <div>
              <h3>Published outcomes</h3>
              <p>
                {data
                  ? `${summaryExpanded ? summaryRows.length : `Top ${visibleSummaryRows.length} of ${summaryRows.length}`} run sets · ${data.tasks.length} public tasks`
                  : "Loading release contract"}
              </p>
            </div>
          </div>
          {!data ? (
            <div className="summary-empty summary-loading" role="status">
              <strong>Loading the signed release bundle…</strong>
              <p>Release identity is known; scored rows appear after integrity-checked JSON is available.</p>
            </div>
          ) : summaryRows.length > 0 ? (
            <div className="summary-table-wrap" role="region" aria-label="Published outcome summary" tabIndex={0}>
              <table className="summary-table">
                <thead>
                <tr>
                  <th>Outcome</th>
                  <th>Model</th>
                  <th>Score</th>
                  <th>Primary 95% interval</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleSummaryRows.map((model) => (
                    <tr key={modelRunKey(model)}>
                      <td>#{model.outcome_rank ?? "—"}</td>
                      <td>
                        {model.model_name}
                        <small>
                          {model.rank ? `${rankGroupLabel(model)} official #${model.rank}` : "No official group rank"}
                          {` · ${model.harness_revision ?? surfaceLabel(inferExecutionSurface(model))}`}
                        </small>
                      </td>
                      <td>{formatPercent(model.safe_success_rate)}</td>
                      <td>
                        {formatPercent(primaryScoreInterval(model)[0])}–{formatPercent(primaryScoreInterval(model)[1])}
                        <small>{primaryScoreIntervalLabel(model)}</small>
                        {secondaryScoreInterval(model) ? (
                          <small>
                            Wilson {formatPercent(secondaryScoreInterval(model)?.[0])}–
                            {formatPercent(secondaryScoreInterval(model)?.[1])}
                          </small>
                        ) : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="summary-empty" role="status">
              <strong>No complete outcome rows are published for this release.</strong>
              <p>Incomplete or integrity-invalid runs remain outside the descriptive outcome order.</p>
            </div>
          )}

          {summaryRows.length > DEFAULT_TABLE_ROW_LIMIT ? (
            <button
              className="evidence-overflow-control"
              type="button"
              aria-expanded={summaryExpanded}
              onClick={() => setSummaryExpanded((value) => !value)}
            >
              {summaryExpanded ? "Show the leading outcome rows" : `Show all ${summaryRows.length} outcome rows`}
            </button>
          ) : null}

          <p className="summary-footnote">
            Outcome order is descriptive across complete rows. Exact point-estimate ties share a rank; names only order tied rows. Family-cluster intervals are primary when patient-family IDs are available; Wilson attempt-level intervals remain visible as a secondary sensitivity analysis. Official rank is shown only within identical frozen harness groups.
          </p>
        </aside>
      </div>

      <div className="explorer-controls">
        <label className="field">
          <span>Domain</span>
          <span className="select-wrap">
            <select value={domainFilter} onChange={(event) => setDomainFilter(event.target.value)}>
              <option value="all">All domains</option>
              {domains.map((domain) => (
                <option key={domain} value={domain}>
                  {domainLabel(domain)}
                </option>
              ))}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field">
          <span>Run set</span>
          <span className="select-wrap">
            <select
              value={effectiveStatusFilter}
              disabled={resultsScope === "official"}
              aria-describedby={resultsScope === "official" ? "leaderboard-scope-lock" : undefined}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="all">All runs</option>
                <option value="ranked">Comparable runs</option>
                <option value="review">Outcome-only runs</option>
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
          {resultsScope === "official" ? <small id="leaderboard-scope-lock">Locked by evidence scope</small> : null}
        </label>
        <label className="field">
          <span>Openness</span>
          <span className="select-wrap">
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as typeof sourceFilter)}>
              <option value="all">All systems</option>
              <option value="open">Open weights</option>
              <option value="closed">Closed models</option>
              <option value="unknown">Unclassified</option>
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field">
          <span>Execution provider</span>
          <span className="select-wrap">
            <select value={providerFilter} onChange={(event) => setProviderFilter(event.target.value)}>
              <option value="all">All execution providers</option>
              {[...new Set(allRows.map((row) => row.provider))]
                .sort((left, right) => left.localeCompare(right))
                .map((value) => (
                  <option key={value} value={value}>
                    {providerLabel(value)}
                  </option>
                ))}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field search-field">
          <span>Model search</span>
          <span className="search-wrap">
            <Search aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search model or execution provider"
            />
          </span>
        </label>
      </div>

      <div className="table-frame">
        <p className="table-scroll-hint">
          <span aria-hidden="true">↔</span>
          Swipe to compare safety, timing, and provenance.
        </p>
        <div className="table-scroll" role="region" aria-label="Model leaderboard" tabIndex={0}>
          <table className="leaderboard-table">
            <caption className="sr-only">
              MedPhysBench {releaseTitle(releaseView)}
            </caption>
            <thead>
              <tr>
                <th>Comparable rank</th>
                <th>Outcome rank</th>
                {SORT_KEYS.map((item) => (
                  <th
                    key={item.key}
                    aria-sort={sortKey === item.key ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
                  >
                    <button
                      type="button"
                      className="sort-button"
                      onClick={() => {
                        if (sortKey === item.key) {
                          setSortDirection((value) => (value === "desc" ? "asc" : "desc"));
                        } else {
                          setSortKey(item.key);
                          setSortDirection(item.key === "model_name" ? "asc" : "desc");
                        }
                      }}
                    >
                      {item.label}
                      {sortKey === item.key && (
                        <span className="sr-only">, sorted {sortDirection === "asc" ? "ascending" : "descending"}</span>
                      )}
                    </button>
                  </th>
                ))}
                <th>Primary 95% CI</th>
                <th>Attempts</th>
                <th>Execution</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((model) => {
                const runKey = modelRunKey(model);
                return (
                  <ModelDetailRow
                    key={runKey}
                    domainFilter={domainFilter}
                    expanded={expanded === runKey}
                    source={modelSourceRow(model, catalogIndexForModelRow(model, catalogIndex))}
                    model={model}
                    onToggle={() => setExpanded((value) => (value === runKey ? null : runKey))}
                  />
                );
              })}
            </tbody>
          </table>
          {data && rows.length === 0 && (
            <p className="table-state" role="status">No model runs match the current filters.</p>
          )}
          {!data && !loadError && <p className="table-state" role="status">Loading verified run artifacts…</p>}
          {loadError && (
            <p className="table-state table-error" role="alert">
              Leaderboard data is unavailable. The repository still contains the current release package.
            </p>
          )}
        </div>
      </div>

      {blocked.length > 0 && (
        <div className="access-panel">
          <div className="section-heading">
            <h3>Unavailable handles stay outside scored results</h3>
            <p>Provider retirement and quota blocks remain in the public record instead of silently disappearing from the benchmark surface.</p>
          </div>
          <div className="access-table">
            {blocked.map((item) => (
              <article key={`${item.model}-${item.date}`}>
                <h4>{item.model}</h4>
                <p>{item.surface.replaceAll("_", " ")}</p>
                <p>{item.date}</p>
                <p>{item.note}</p>
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function OutcomeIntervalPlot({ data, resultsScope }: { data: Leaderboard | null; resultsScope: ResultsScope }) {
  const [expanded, setExpanded] = useState(false);
  if (!data) {
    return (
      <div className="visual-empty visual-loading" role="status">
        <strong>Loading verified outcome evidence…</strong>
        <p>The public release identifier is available; model rows are being read from the immutable result bundle.</p>
      </div>
    );
  }
  const allRows = withDerivedOutcomeRanks([...(data?.models ?? []), ...(data?.unranked_models ?? [])])
    .filter((row) => rowVisibleInResultsScope(row, resultsScope));
  const rows = allRows
    .filter((row) => row.outcome_rank != null)
    .sort((left, right) => (left.outcome_rank ?? Infinity) - (right.outcome_rank ?? Infinity));
  const omitted = allRows.length - rows.length;
  const visibleRows = limitEvidenceRows(rows, expanded, DEFAULT_CHART_ROW_LIMIT);

  if (rows.length === 0) {
    return (
      <div className="visual-empty" role="status">
        <strong>No complete outcome evidence</strong>
        <p>This release does not yet contain a complete, integrity-checked run matrix.</p>
      </div>
    );
  }

  const width = 760;
  const rowHeight = 46;
  const height = 82 + visibleRows.length * rowHeight;
  const margin = { top: 50, right: 28, bottom: 32, left: 222 };
  const scaleX = (value: number) => margin.left + value * (width - margin.left - margin.right);
  const intervalFor = (row: ModelResult) => primaryScoreInterval(row);
  const usesFamilyIntervals = rows.some((row) => row.family_cluster_safe_success_ci95 != null);
  const leadingIntervalsOverlap = rows.length > 1 && intervalFor(rows[0])[0] <= intervalFor(rows[1])[1];
  const insightTitle = leadingIntervalsOverlap
    ? "The leading intervals still overlap"
    : `${shortModelLabel(rows[0].model_name)} leads the outcome order`;

  return (
    <>
      <div className="results-visual-head">
        <div>
          <h3>{insightTitle}</h3>
          <p>
            Point estimate and {usesFamilyIntervals ? "patient-family-cluster" : "Wilson"} 95% interval for safe task
            success. {usesFamilyIntervals ? "Attempt-level Wilson intervals remain in the evidence table." : ""}
          </p>
        </div>
        <span className="results-inline-note">
          {resultsScope === "official"
            ? "Every rank remains local to one frozen harness group"
            : "Official rank and cross-surface outcome order remain distinct"}
        </span>
      </div>
      <svg className="results-chart outcome-interval-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="results-chart-title results-chart-description">
        <title id="results-chart-title">Safe task success with 95 percent confidence intervals</title>
        <desc id="results-chart-description">
          {resultsScope === "official"
            ? "Rank-eligible models are shown within their frozen harness groups. Horizontal lines show the primary confidence interval, clustered by patient family when available."
            : "Models are ordered by their descriptive outcome rank. Circles are official harness-group rows and diamonds are complete native-surface rows. Horizontal lines show the primary confidence interval, clustered by patient family when available."}
        </desc>
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line x1={scaleX(tick)} x2={scaleX(tick)} y1={margin.top - 18} y2={height - margin.bottom} className="chart-grid" />
            <text x={scaleX(tick)} y={margin.top - 28} textAnchor="middle" className="chart-axis-label">
              {Math.round(tick * 100)}%
            </text>
          </g>
        ))}
        {visibleRows.map((row, index) => {
          const y = margin.top + index * rowHeight + rowHeight / 2;
          const interval = intervalFor(row);
          const markerX = scaleX(row.safe_success_rate);
          return (
            <g
              key={modelRunKey(row)}
              className={inferExecutionSurface(row) === "common_harness" ? "interval-row common" : "interval-row native"}
            >
              <text x={margin.left - 18} y={y - 3} textAnchor="end" className="interval-model-label">{shortModelLabel(row.model_name)}</text>
              <text x={margin.left - 18} y={y + 14} textAnchor="end" className="interval-rank-label">
                {inferExecutionSurface(row) === "common_harness"
                  ? `${rankGroupLabel(row)} #${row.rank ?? "—"}`
                  : `outcome #${row.outcome_rank ?? "—"} · ${surfaceLabel("recorded_output_import")}`}
              </text>
              <line x1={scaleX(interval[0])} x2={scaleX(interval[1])} y1={y} y2={y} className="interval-whisker" />
              <line x1={scaleX(interval[0])} x2={scaleX(interval[0])} y1={y - 5} y2={y + 5} className="interval-cap" />
              <line x1={scaleX(interval[1])} x2={scaleX(interval[1])} y1={y - 5} y2={y + 5} className="interval-cap" />
              {inferExecutionSurface(row) === "common_harness" ? (
                <circle cx={markerX} cy={y} r="6" className="ranked-point" />
              ) : (
                <path d={`M ${markerX} ${y - 7} L ${markerX + 7} ${y} L ${markerX} ${y + 7} L ${markerX - 7} ${y} Z`} className="native-point" />
              )}
              <text x={Math.min(markerX + 11, width - margin.right - 2)} y={y - 10} textAnchor={markerX > width - 100 ? "end" : "start"} className="chart-percent-label">
                {formatPercent(row.safe_success_rate)}
              </text>
            </g>
          );
        })}
      </svg>
      <ol className="mobile-interval-list" aria-label="Safe success interval summary">
        {visibleRows.map((row) => {
          const interval = intervalFor(row);
          return (
            <li key={modelRunKey(row)}>
              <div>
                <strong>{shortModelLabel(row.model_name)}</strong>
                <span>{formatPercent(row.safe_success_rate)}</span>
              </div>
              <p>
                {inferExecutionSurface(row) === "common_harness"
                  ? `${rankGroupLabel(row)} #${row.rank ?? "—"}`
                  : `Outcome #${row.outcome_rank ?? "—"} · ${surfaceLabel("recorded_output_import")}`}
              </p>
              <div className="mobile-interval-track" aria-hidden="true">
                <i style={{ left: `${interval[0] * 100}%`, width: `${(interval[1] - interval[0]) * 100}%` }} />
                <b style={{ left: `${row.safe_success_rate * 100}%` }} />
              </div>
              <small>{primaryScoreIntervalLabel(row)} {formatPercent(interval[0])}–{formatPercent(interval[1])}</small>
              {secondaryScoreInterval(row) ? (
                <small>
                  Wilson sensitivity {formatPercent(secondaryScoreInterval(row)?.[0])}–
                  {formatPercent(secondaryScoreInterval(row)?.[1])}
                </small>
              ) : null}
            </li>
          );
        })}
      </ol>
      {rows.length > DEFAULT_CHART_ROW_LIMIT ? (
        <button
          className="evidence-overflow-control"
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "Show the leading interval rows" : `Show all ${rows.length} rows in the interval plot`}
        </button>
      ) : null}
      <div className="outcome-plot-key" aria-label="Plot key">
        <span><i className="outcome-key-common" /> Common-harness comparable row</span>
        <span><i className="outcome-key-native" /> Native/import row</span>
        <span>Whisker = primary 95% interval{usesFamilyIntervals ? " (family-clustered)" : " (Wilson)"}</span>
        {usesFamilyIntervals ? <span>Only two patient families: intervals and order are provisional</span> : null}
        {omitted > 0 && <span>{omitted} incomplete or invalid row(s) omitted</span>}
      </div>
    </>
  );
}

function Tg263AuditChart({ audit }: { audit: Tg263Audit | null }) {
  if (!audit) {
    return (
      <div className="visual-empty" role="status">
        <strong>Audit artifact unavailable</strong>
        <p>The TG-263 native audit summary could not be loaded from the current release package.</p>
      </div>
    );
  }

  return (
    <>
      <div className="results-visual-head">
        <div>
          <h3>TG-263 audit split</h3>
          <p>{audit.scope}</p>
        </div>
      </div>
      <div className="audit-bars" role="img" aria-label="Strict pilot score compared with audited decision correctness">
        {audit.models.map((model) => (
          <article key={`${model.provider}::${model.model_name}::${model.model_revision}`} className="audit-bar-row">
            <header>
              <strong>{model.model_name}</strong>
              <span>{model.attempt_count} attempts</span>
            </header>
            <div className="audit-bar-stack">
              <div>
                <span>Strict pilot score</span>
                <div className="audit-bar-track">
                  <i className="audit-bar-strict" style={{ width: `${model.strict_safe_success_rate * 100}%` }} />
                </div>
                <strong>{formatPercent(model.strict_safe_success_rate)}</strong>
              </div>
              <div>
                <span>Audited decision rate</span>
                <div className="audit-bar-track">
                  <i className="audit-bar-primary" style={{ width: `${model.primary_decision_rate * 100}%` }} />
                </div>
                <strong>{formatPercent(model.primary_decision_rate)}</strong>
              </div>
            </div>
          </article>
        ))}
      </div>
      <p className="results-inline-footnote">
        Reason-code exactness remains separate because the pilot used a benchmark-authored rationale vocabulary that is stricter than the audited action/escalation decision.
      </p>
    </>
  );
}

function ModelDetailRow({
  model,
  domainFilter,
  expanded,
  onToggle,
  source,
}: {
  model: ModelResult;
  domainFilter: string;
  expanded: boolean;
  onToggle: () => void;
  source: ModelOpenness;
}) {
  const tasks = domainFilter === "all" ? model.tasks : model.tasks.filter((task) => task.domain === domainFilter);
  const failedTasks = tasks.filter((task) => (task.failed_graders?.length ?? 0) > 0);
  const safePasses = tasks.filter((task) => classifyAttemptOutcome(task) === "safe-pass").length;
  const safeFails = tasks.filter((task) => classifyAttemptOutcome(task) === "safe-fail").length;
  const unsafeOutcomes = tasks.filter((task) => classifyAttemptOutcome(task) === "unsafe").length;
  const unavailableOutcomes = tasks.filter((task) => classifyAttemptOutcome(task) === "unavailable").length;

  return (
    <>
      <tr className={expanded ? "model-row expanded" : "model-row"}>
        <td>{model.rank ? `${rankGroupLabel(model)} #${model.rank}` : "—"}</td>
        <td>{model.outcome_rank ? `#${model.outcome_rank}` : "—"}</td>
        <td>
          <button
            type="button"
            className="row-toggle"
            onClick={onToggle}
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${model.model_name} run details`}
          >
            <span>{model.model_name}</span>
            <small>
              {providerLabel(model.provider)} · {model.harness_revision ?? surfaceLabel(inferExecutionSurface(model))}
            </small>
          </button>
        </td>
        <td>{formatPercent(metricForDomain(model, domainFilter))}</td>
        <td>{formatPercent(model.task_success_rate)}</td>
        <td>{formatPercent(model.safety_gate_rate)}</td>
        <td>{formatPercent(model.valid_output_rate)}</td>
        <td>{formatPercent(model.appropriate_escalation_rate)}</td>
        <td>{formatDuration(model.median_duration_seconds)}</td>
        <td>{formatPercent(safeSuccessInterval(model)[0])} to {formatPercent(safeSuccessInterval(model)[1])}</td>
        <td>{model.attempt_count} / {model.expected_attempt_count ?? model.attempt_count}</td>
        <td>{surfaceLabel(inferExecutionSurface(model))}</td>
        <td>{modelSourceLabel(source)}</td>
      </tr>
      {expanded && (
        <tr className="detail-row">
          <td colSpan={13}>
            <div className="detail-grid">
              <section>
                <h4>Run summary</h4>
                <dl className="metric-list">
                  <div><dt>Safe success</dt><dd>{formatPercent(model.safe_success_rate)}</dd></div>
                  <div><dt>Task success</dt><dd>{formatPercent(model.task_success_rate)}</dd></div>
                  <div><dt>Escalation</dt><dd>{formatPercent(model.appropriate_escalation_rate)}</dd></div>
                  <div><dt>Output validity</dt><dd>{formatPercent(model.valid_output_rate)}</dd></div>
                  <div><dt>Median duration</dt><dd>{formatDuration(model.median_duration_seconds)}</dd></div>
                  <div><dt>Critical unsafe</dt><dd>{formatPercent(model.critical_unsafe_action_rate)}</dd></div>
                  <div><dt>Official rank status</dt><dd>{model.rank ? `${rankGroupLabel(model)} #${model.rank}` : "No official rank assigned"}</dd></div>
                  <div><dt>Outcome order</dt><dd>{model.outcome_rank ? `#${model.outcome_rank}` : "Not ordered"}</dd></div>
                </dl>
              </section>
                  <section className="detail-span">
                <h4>Task-by-task results</h4>
                <div className="task-grid">
                  {tasks.map((task) => (
                    <article key={`${task.task_id}-${task.attempt_index ?? 0}`}>
                      <header>
                        <span>{task.title}</span>
                        <strong>{taskDetailOutcomeLabel(task)}</strong>
                      </header>
                      <p>{domainLabel(task.domain)}</p>
                      <dl>
                        <div><dt>Run</dt><dd>{shortHash(task.run_id)}</dd></div>
                        <div><dt>Prompt</dt><dd>{shortHash(task.prompt_hash)}</dd></div>
                        <div><dt>Tools</dt><dd>{shortHash(task.tool_schema_hash)}</dd></div>
                        <div><dt>Runtime</dt><dd>{shortHash(task.runtime_task_hash)}</dd></div>
                        <div><dt>Grader</dt><dd>{shortHash(task.grader_hash)}</dd></div>
                        <div><dt>Scoring</dt><dd>{task.scoring_revision ?? "—"}</dd></div>
                      </dl>
                      {task.failed_lanes && task.failed_lanes.length > 0 ? (
                        <p>
                          <strong>Failure lanes:</strong> {task.failed_lanes.join(", ")}
                        </p>
                      ) : null}
                      {task.failed_graders && task.failed_graders.length > 0 ? (
                        <p>
                          <strong>Failed checks:</strong> {task.failed_graders.join(", ")}
                        </p>
                      ) : null}
                    </article>
                  ))}
                </div>
              </section>
              <section>
                <h4>Failure diagnostics</h4>
                <dl className="metric-list">
                  <div><dt>Right/wrong</dt><dd>{safePasses} correct · {safeFails + unsafeOutcomes} incorrect · {unavailableOutcomes} unavailable</dd></div>
                  <div><dt>Failed checks</dt><dd>{failedTasks.length} task attempt(s)</dd></div>
                  <div><dt>Common failure lanes</dt><dd>{failureLanes(tasks)}</dd></div>
                </dl>
                {failedTasks.length > 0 && (
                  <ul className="integrity-list">
                    {failedTasks.map((task) => (
                      <li key={`${task.task_id}-${task.attempt_index ?? 0}`}>
                        {task.title}: {task.failed_graders?.join(", ")}
                      </li>
                    ))}
                  </ul>
                )}
                {failedTasks.length === 0 ? <p className="integrity-clean">No failed check identifiers are recorded for this run.</p> : null}
              </section>
              <section>
                <h4>Integrity</h4>
                <dl className="metric-list">
                  <div><dt>Observed attempts</dt><dd>{model.integrity?.observed_attempt_keys ?? "—"}</dd></div>
                  <div><dt>Missing attempts</dt><dd>{model.integrity?.missing_attempt_keys ?? "—"}</dd></div>
                  <div><dt>Unexpected attempts</dt><dd>{model.integrity?.unexpected_attempt_keys ?? "—"}</dd></div>
                </dl>
                {model.integrity?.integrity_errors?.length ? (
                  <ul className="integrity-list">
                    {model.integrity.integrity_errors.map((item) => (
                      <li key={item}>{integrityLabel(item)}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="integrity-clean">No integrity findings recorded for this run set.</p>
                )}
              </section>
              <section className="detail-span registry-run-actions">
                <button
                  type="button"
                  aria-label={`Open full attempt forensics for ${normalizeModelDisplayName(model.model_name)} on ${providerLabel(model.provider)} (${model.harness_revision ?? surfaceLabel(inferExecutionSurface(model))})`}
                  onClick={() => navigateToRunForensics(model)}
                >
                  Open full attempt forensics
                </button>
              </section>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function taskDetailOutcomeLabel(task: ModelResult["tasks"][number]) {
  const outcome = classifyAttemptOutcome(task);
  if (outcome === "safe-pass") return "Passed · Safe";
  if (outcome === "safe-fail") return "Failed · Safe";
  if (outcome === "unsafe") return "Failed · Unsafe";
  if (outcome === "unavailable") return "Capability unavailable";
  return "Outcome unavailable";
}

function releaseTitle(view: ReleaseView) {
  if (view === "core") return "Core release results";
  if (view === "imaging") return "Imaging pilot";
  if (view === "tg263") return "TG-263 naming pilot";
  return "OpenKBP real-data workflow-view pilot";
}

function releaseSummary(view: ReleaseView) {
  if (view === "core") {
    return "Original medical-physics calculations, bounded interpretation, deterministic artifact checks, and escalation boundaries on the public core.";
  }
  if (view === "imaging") {
    return "Public imaging and segmentation tasks on frozen fixtures, with common-harness open models and comparable native GPT rows shown in the same result surface.";
  }
  if (view === "tg263") {
    return "Collision-aware structure naming where audited native GPT decision correctness stays separate from strict pilot rationale-label exactness.";
  }
  return "A two-patient, ten-task OpenKBP workflow-view pilot spanning image localization, dose interpretation, plan review, data integrity, and TG-263 naming. Official ranks are provisional within each identical frozen harness group.";
}

function fallbackReleaseId(view: ReleaseView) {
  return releaseIdForView(view);
}

function formatArtifactDate(value: string | undefined) {
  if (!value) return "artifact date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "artifact date unavailable";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function compareRows(
  left: ModelResult,
  right: ModelResult,
  sortKey: SortKey,
  sortDirection: "desc" | "asc",
  domainFilter: string,
) {
  const direction = sortDirection === "desc" ? -1 : 1;
  const leftValue = comparableMetric(left, sortKey, domainFilter);
  const rightValue = comparableMetric(right, sortKey, domainFilter);
  if (typeof leftValue === "string" || typeof rightValue === "string") {
    return direction * String(leftValue).localeCompare(String(rightValue));
  }
  const leftMissing = leftValue == null || Number.isNaN(leftValue);
  const rightMissing = rightValue == null || Number.isNaN(rightValue);
  if (leftMissing !== rightMissing) return leftMissing ? 1 : -1;
  if (leftValue !== rightValue) {
    return direction * ((leftValue ?? 0) - (rightValue ?? 0));
  }
  return String(left.model_name).localeCompare(String(right.model_name));
}

function comparableMetric(model: ModelResult, sortKey: SortKey, domainFilter: string) {
  if (sortKey === "model_name") return model.model_name;
  if (sortKey === "safe_success_rate" && domainFilter !== "all") {
    return model.domain_safe_success[domainFilter] ?? null;
  }
  return model[sortKey] ?? null;
}

function metricForDomain(model: ModelResult, domainFilter: string) {
  return domainFilter === "all" ? model.safe_success_rate : model.domain_safe_success[domainFilter] ?? null;
}

function safeSuccessInterval(model: ModelResult): [number, number] {
  return primaryScoreInterval(model);
}

function shortModelLabel(value: string) {
  return normalizeModelDisplayName(value)
    .replace("openai/", "")
    .replace("llama-", "Llama ")
    .replace("qwen/qwen", "Qwen ")
    .replace("[effort=", "(")
    .replace("]", ")");
}

function rankGroupLabel(model: ModelResult) {
  if (model.provider === "groq") return "Groq";
  if (model.provider === "ollama") return "Ollama";
  return model.provider;
}

function withDerivedOutcomeRanks(rows: ModelResult[]) {
  const eligible = rows
    .filter((row) => {
      if (row.outcome_order_eligible === false) return false;
      if (row.outcome_order_eligible === true || row.ranking_eligible) return true;
      const findings = row.integrity?.integrity_errors ?? [];
      return findings.length > 0 && findings.every((finding) =>
        finding === "unranked_noncommon_surface"
        || finding === "unranked_native_pilot_surface"
        || finding === "unranked_singleton_comparison_group",
      );
    });
  const fallbackRanks = competitionRankMap(eligible);
  return rows.map((row) => ({ ...row, outcome_rank: row.outcome_rank ?? fallbackRanks.get(row) ?? null }));
}
