import { ArrowDownToLine, ChevronDown, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import type { AccessStatus, Leaderboard, ModelResult, ReleaseView, Tg263Audit } from "../types";
import { domainLabel, formatDuration, formatPercent, formatTokens, shortHash } from "../lib/format";

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
  loadError: boolean;
  releaseView: ReleaseView;
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
  core: "/data/leaderboard.json",
  tg263: "/data/tg263_leaderboard.json",
  real: "/data/public-real-workflows-pilot-v0.6.json",
};

export function LeaderboardExplorer({
  data,
  accessStatus,
  loadError,
  releaseView,
  tg263Audit,
}: LeaderboardExplorerProps) {
  const [query, setQuery] = useState("");
  const [domainFilter, setDomainFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("safe_success_rate");
  const [sortDirection, setSortDirection] = useState<"desc" | "asc">("desc");
  const [expanded, setExpanded] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query);
  const allRows = useMemo(
    () => withDerivedOutcomeRanks(data ? [...data.models, ...(data.unranked_models ?? [])] : []),
    [data],
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
          statusFilter === "all" ||
          (statusFilter === "ranked" && model.ranking_eligible) ||
          (statusFilter === "review" && !model.ranking_eligible);
        return matchesQuery && matchesStatus;
      })
      .sort((left, right) => compareRows(left, right, sortKey, sortDirection, domainFilter));
  }, [allRows, deferredQuery, domainFilter, sortDirection, sortKey, statusFilter]);

  const rankedRows = allRows.filter((model) => model.ranking_eligible);
  const reviewRows = allRows
    .filter((model) => !model.ranking_eligible)
    .sort((left, right) => (left.outcome_rank ?? Infinity) - (right.outcome_rank ?? Infinity));
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
            <OutcomeIntervalPlot data={data} />
          )}
        </article>
        <aside className="results-summary">
          <div className="results-summary-head">
            <div>
              <h3>Official harness-group ranks</h3>
              <p>{data ? `${data.tasks.length} public tasks` : "Loading release contract"}</p>
            </div>
          </div>
          {!data ? (
            <div className="summary-empty summary-loading" role="status">
              <strong>Loading the signed release bundle…</strong>
              <p>Release identity is known; scored rows appear after integrity-checked JSON is available.</p>
            </div>
          ) : rankedRows.length > 0 ? (
            <div className="summary-table-wrap" role="region" aria-label="Ranked summary table" tabIndex={0}>
              <table className="summary-table">
                <thead>
                  <tr>
                    <th>Official</th>
                    <th>Model</th>
                    <th>Score</th>
                    <th>95% CI</th>
                  </tr>
                </thead>
                <tbody>
                  {rankedRows.map((model) => (
                    <tr key={model.model_name}>
                      <td>{model.rank ? `${rankGroupLabel(model)} #${model.rank}` : "—"}</td>
                      <td>{model.model_name}</td>
                      <td>{formatPercent(model.safe_success_rate)}</td>
                      <td>{formatPercent(safeSuccessInterval(model)[0])}–{formatPercent(safeSuccessInterval(model)[1])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="summary-empty" role="status">
              <strong>No official harness-group ranking published for this release.</strong>
              <p>Complete native runs remain visible in the descriptive outcome order below.</p>
            </div>
          )}

          <div className="native-audit-panel">
            <div className="native-audit-copy">
              <strong>{releaseView === "tg263" ? "Native GPT audit" : "Native-surface outcome order"}</strong>
              <p>
                {releaseView === "tg263"
                  ? "Primary decision quality and rationale-label exactness are split. Native rows stay separate until a comparable common harness exists."
                  : "Complete native runs use the same frozen task pack but a different execution surface. They receive a descriptive outcome order, while official harness-group ranks stay separate. Missing latency or token telemetry stays unavailable."}
              </p>
            </div>
            <div className="native-audit-rows">
              {releaseView === "tg263" && tg263Audit
                ? tg263Audit.models.map((model) => (
                    <div key={model.model_name} className="native-audit-row">
                      <span>{model.model_name}</span>
                      <span>{formatPercent(model.primary_decision_rate)} audited</span>
                      <span>{formatPercent(model.strict_safe_success_rate)} strict</span>
                      <span>{model.label_only_mismatch_count} label-only mismatches</span>
                    </div>
                  ))
                : reviewRows.slice(0, 3).map((model) => (
                    <div key={model.model_name} className="native-audit-row">
                      <span>{model.model_name}</span>
                      <span>Outcome #{model.outcome_rank ?? "—"}</span>
                      <span>{formatPercent(model.safe_success_rate)} score</span>
                      <span>{formatDuration(model.median_duration_seconds)}</span>
                    </div>
                  ))}
            </div>
          </div>

          <p className="summary-footnote">
            Score is safe task success from the current release artifact. Unavailable telemetry is left unavailable and is not imputed for charts or tables.
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
          <span>Ranking state</span>
          <span className="select-wrap">
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">All runs</option>
                <option value="ranked">Official only</option>
                <option value="review">Native outcome only</option>
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
              placeholder="Search model or provider"
            />
          </span>
        </label>
      </div>

      <div className="table-frame">
        <div className="table-scroll" role="region" aria-label="Model leaderboard" tabIndex={0}>
          <table className="leaderboard-table">
            <caption className="sr-only">
              MedPhysBench {releaseTitle(releaseView)}
            </caption>
            <thead>
              <tr>
                <th>Official</th>
                <th>Outcome</th>
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
                <th>95% CI</th>
                <th>Attempts</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((model) => (
                <ModelDetailRow
                  key={model.model_name}
                  domainFilter={domainFilter}
                  expanded={expanded === model.model_name}
                  model={model}
                  onToggle={() => setExpanded((value) => (value === model.model_name ? null : model.model_name))}
                />
              ))}
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

function OutcomeIntervalPlot({ data }: { data: Leaderboard | null }) {
  if (!data) {
    return (
      <div className="visual-empty visual-loading" role="status">
        <strong>Loading verified outcome evidence…</strong>
        <p>The public release identifier is available; model rows are being read from the immutable result bundle.</p>
      </div>
    );
  }
  const allRows = withDerivedOutcomeRanks([...(data?.models ?? []), ...(data?.unranked_models ?? [])]);
  const rows = allRows
    .filter((row) => row.outcome_rank != null)
    .sort((left, right) => (left.outcome_rank ?? Infinity) - (right.outcome_rank ?? Infinity));
  const omitted = allRows.length - rows.length;

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
  const height = 82 + rows.length * rowHeight;
  const margin = { top: 50, right: 28, bottom: 32, left: 222 };
  const scaleX = (value: number) => margin.left + value * (width - margin.left - margin.right);
  const intervalFor = (row: ModelResult) => row.safe_success_ci95 ?? row.task_success_ci95;
  const leadingIntervalsOverlap = rows.length > 1 && intervalFor(rows[0])[0] <= intervalFor(rows[1])[1];
  const insightTitle = leadingIntervalsOverlap
    ? "The leading intervals still overlap"
    : `${shortModelLabel(rows[0].model_name)} leads the outcome order`;

  return (
    <>
      <div className="results-visual-head">
        <div>
          <h3>{insightTitle}</h3>
          <p>Point estimate and Wilson 95% interval for safe task success. Direct labels replace a detached legend.</p>
        </div>
        <span className="results-inline-note">Official rank and cross-surface outcome order remain distinct</span>
      </div>
      <svg className="results-chart outcome-interval-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="results-chart-title results-chart-description">
        <title id="results-chart-title">Safe task success with 95 percent confidence intervals</title>
        <desc id="results-chart-description">Models are ordered by their descriptive outcome rank. Circles are official harness-group rows and diamonds are complete native-surface rows. Horizontal lines show Wilson confidence intervals.</desc>
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line x1={scaleX(tick)} x2={scaleX(tick)} y1={margin.top - 18} y2={height - margin.bottom} className="chart-grid" />
            <text x={scaleX(tick)} y={margin.top - 28} textAnchor="middle" className="chart-axis-label">
              {Math.round(tick * 100)}%
            </text>
          </g>
        ))}
        {rows.map((row, index) => {
          const y = margin.top + index * rowHeight + rowHeight / 2;
          const interval = intervalFor(row);
          const markerX = scaleX(row.safe_success_rate);
          return (
            <g key={row.model_name} className={row.ranking_eligible ? "interval-row common" : "interval-row native"}>
              <text x={margin.left - 18} y={y - 3} textAnchor="end" className="interval-model-label">{shortModelLabel(row.model_name)}</text>
              <text x={margin.left - 18} y={y + 14} textAnchor="end" className="interval-rank-label">
                {row.ranking_eligible ? `${rankGroupLabel(row)} #${row.rank}` : `outcome #${row.outcome_rank} · native`}
              </text>
              <line x1={scaleX(interval[0])} x2={scaleX(interval[1])} y1={y} y2={y} className="interval-whisker" />
              <line x1={scaleX(interval[0])} x2={scaleX(interval[0])} y1={y - 5} y2={y + 5} className="interval-cap" />
              <line x1={scaleX(interval[1])} x2={scaleX(interval[1])} y1={y - 5} y2={y + 5} className="interval-cap" />
              {row.ranking_eligible ? (
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
        {rows.map((row) => {
          const interval = intervalFor(row);
          return (
            <li key={row.model_name}>
              <div>
                <strong>{shortModelLabel(row.model_name)}</strong>
                <span>{formatPercent(row.safe_success_rate)}</span>
              </div>
              <p>{row.ranking_eligible ? `${rankGroupLabel(row)} #${row.rank}` : `Outcome #${row.outcome_rank} · native audit`}</p>
              <div className="mobile-interval-track" aria-hidden="true">
                <i style={{ left: `${interval[0] * 100}%`, width: `${(interval[1] - interval[0]) * 100}%` }} />
                <b style={{ left: `${row.safe_success_rate * 100}%` }} />
              </div>
              <small>95% CI {formatPercent(interval[0])}–{formatPercent(interval[1])}</small>
            </li>
          );
        })}
      </ol>
      <div className="outcome-plot-key" aria-label="Plot key">
        <span><i className="outcome-key-common" /> Official harness-group row</span>
        <span><i className="outcome-key-native" /> Complete native-surface row</span>
        <span>Whisker = Wilson 95% interval</span>
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
          <article key={model.model_name} className="audit-bar-row">
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
}: {
  model: ModelResult;
  domainFilter: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  const tasks = domainFilter === "all" ? model.tasks : model.tasks.filter((task) => task.domain === domainFilter);

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
            <small>{model.provider}</small>
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
        <td>{model.ranking_eligible ? "Official harness group" : "Native outcome order"}</td>
      </tr>
      {expanded && (
        <tr className="detail-row">
          <td colSpan={12}>
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
                </dl>
              </section>
              <section className="detail-span">
                <h4>Task-by-task results</h4>
                <div className="task-grid">
                  {tasks.map((task) => (
                    <article key={`${task.task_id}-${task.attempt_index ?? 0}`}>
                      <header>
                        <span>{task.title}</span>
                        <strong>{task.passed === true ? "Passed" : task.passed === false ? "Failed" : "Outcome unavailable"} · {task.safe ? "Safe" : "Unsafe"}</strong>
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
                    </article>
                  ))}
                </div>
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
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="integrity-clean">No integrity findings recorded for this run set.</p>
                )}
              </section>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function releaseTitle(view: ReleaseView) {
  if (view === "core") return "Core release results";
  if (view === "tg263") return "TG-263 naming pilot";
  return "OpenKBP real-workflow pilot";
}

function releaseSummary(view: ReleaseView) {
  if (view === "core") {
    return "Original medical-physics calculations, bounded interpretation, deterministic artifact checks, and escalation boundaries on the public core.";
  }
  if (view === "tg263") {
    return "Collision-aware structure naming where audited native GPT decision correctness stays separate from strict pilot rationale-label exactness.";
  }
  return "A two-patient, ten-task OpenKBP pilot spanning image localization, dose interpretation, plan review, data integrity, and TG-263 naming. Official ranks are provisional within each identical frozen harness group.";
}

function fallbackReleaseId(view: ReleaseView) {
  if (view === "core") return "public-core-v0.4";
  if (view === "tg263") return "public-tg263-pilot-v0.5";
  return "public-real-workflows-pilot-v0.6";
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
  return model.safe_success_ci95 ?? model.task_success_ci95;
}

function shortModelLabel(value: string) {
  return value
    .replace("gpt-5.6-sol", "GPT-5.6")
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
        finding === "unranked_noncommon_surface" || finding === "unranked_native_pilot_surface",
      );
    })
    .sort((left, right) =>
      right.safe_success_rate - left.safe_success_rate
      || right.task_success_rate - left.task_success_rate
      || right.safety_gate_rate - left.safety_gate_rate
      || left.model_name.localeCompare(right.model_name),
    );
  const fallbackRanks = new Map(eligible.map((row, index) => [row.model_name, index + 1]));
  return rows.map((row) => ({ ...row, outcome_rank: row.outcome_rank ?? fallbackRanks.get(row.model_name) ?? null }));
}
