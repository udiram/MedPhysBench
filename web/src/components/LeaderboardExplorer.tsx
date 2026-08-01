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

  const domains = useMemo(() => {
    const values = new Set<string>();
    data?.tasks.forEach((task) => values.add(task.domain));
    return [...values].sort();
  }, [data]);

  const rows = useMemo(() => {
    if (!data) return [];
    return [...data.models, ...(data.unranked_models ?? [])]
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
  }, [data, deferredQuery, domainFilter, sortDirection, sortKey, statusFilter]);

  const rankedRows = data?.models ?? [];
  const reviewRows = data?.unranked_models ?? [];
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
            <ReleaseScatter data={data} />
          )}
        </article>
        <aside className="results-summary">
          <div className="results-summary-head">
            <div>
              <h3>Ranked results (common harness)</h3>
              <p>{data?.tasks.length ?? 0} public tasks</p>
            </div>
          </div>
          {rankedRows.length > 0 ? (
            <div className="summary-table-wrap" role="region" aria-label="Ranked summary table" tabIndex={0}>
              <table className="summary-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Model</th>
                    <th>Score</th>
                    <th>95% CI</th>
                    <th>Safety</th>
                    <th>Tokens</th>
                    <th>Median time</th>
                  </tr>
                </thead>
                <tbody>
                  {rankedRows.slice(0, 8).map((model) => (
                    <tr key={model.model_name}>
                      <td>{model.rank ?? "—"}</td>
                      <td>{model.model_name}</td>
                      <td>{formatPercent(model.safe_success_rate)}</td>
                      <td>{formatPercent(model.task_success_ci95[0])}–{formatPercent(model.task_success_ci95[1])}</td>
                      <td>{formatPercent(model.safety_gate_rate)}</td>
                      <td>{formatTokens(model.token_usage?.median_total_tokens)}</td>
                      <td>{formatDuration(model.median_duration_seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="summary-empty" role="status">
              <strong>No common-harness ranking published for this release.</strong>
              <p>Audited native rows stay visible below without being promoted into a comparable rank table.</p>
            </div>
          )}

          <div className="native-audit-panel">
            <div className="native-audit-copy">
              <strong>{releaseView === "tg263" ? "Native GPT audit" : "Unranked native audit"}</strong>
              <p>
                {releaseView === "tg263"
                  ? "Primary decision quality and rationale-label exactness are split. Native rows stay separate until a comparable common harness exists."
                  : "Recorded-output native runs remain visible as review evidence. Missing latency or token telemetry is preserved as unavailable."}
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
                      <span>{formatPercent(model.safe_success_rate)} score</span>
                      <span>{formatDuration(model.median_duration_seconds)}</span>
                      <span>{formatTokens(model.token_usage?.median_total_tokens)}</span>
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
              <option value="ranked">Ranked only</option>
              <option value="review">Review / native only</option>
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
                <th>Rank</th>
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

function ReleaseScatter({ data }: { data: Leaderboard | null }) {
  const rows = data?.models.filter((row) => row.median_duration_seconds != null) ?? [];
  const missing = (data?.unranked_models ?? []).filter((row) => row.median_duration_seconds == null);

  if (rows.length === 0) {
    return (
      <div className="visual-empty" role="status">
        <strong>No comparable time telemetry</strong>
        <p>This release currently exposes native or differently instrumented rows without comparable median wall time.</p>
      </div>
    );
  }

  const width = 720;
  const height = 430;
  const margin = { top: 36, right: 28, bottom: 56, left: 68 };
  const times = rows.map((row) => row.median_duration_seconds as number);
  const scores = rows.map((row) => row.safe_success_rate);
  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const minDomain = Math.pow(10, Math.floor(Math.log10(Math.max(0.1, minTime))));
  const maxDomain = Math.pow(10, Math.ceil(Math.log10(Math.max(1, maxTime))));
  const scaleX = (value: number) => {
    const left = Math.log10(minDomain);
    const right = Math.log10(maxDomain);
    return margin.left + ((Math.log10(value) - left) / Math.max(0.0001, right - left)) * (width - margin.left - margin.right);
  };
  const lowScore = Math.max(0, Math.floor((Math.min(...scores) - 0.05) * 4) / 4);
  const highScore = Math.min(1, Math.max(0.25, Math.ceil((Math.max(...scores) + 0.05) * 4) / 4));
  const scaleY = (value: number) =>
    margin.top + (1 - (value - lowScore) / Math.max(0.0001, highScore - lowScore)) * (height - margin.top - margin.bottom);
  const yTicks = [0, 0.25, 0.5, 0.75, 1].filter((tick) => tick >= lowScore && tick <= highScore);
  const xTicks = [0.1, 1, 10, 100, 1000].filter((tick) => tick >= minDomain && tick <= maxDomain);

  return (
    <>
      <div className="results-visual-head">
        <div>
          <h3>Decision correctness vs. median time</h3>
          <p>Score = safe task success across all public tasks in the selected release.</p>
        </div>
        {missing.length > 0 && <span className="results-inline-note">{missing.length} native row(s) unplotted: latency unavailable</span>}
      </div>
      <svg className="results-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby="results-chart-title results-chart-description">
        <title id="results-chart-title">Safe task success compared with median time per task</title>
        <desc id="results-chart-description">Each point is one ranked common-harness model row. Rows with unavailable latency are listed separately rather than plotted at zero.</desc>
        {yTicks.map((tick) => (
          <g key={tick}>
            <line x1={margin.left} x2={width - margin.right} y1={scaleY(tick)} y2={scaleY(tick)} className="chart-grid" />
            <text x={margin.left - 14} y={scaleY(tick) + 4} textAnchor="end" className="chart-axis-label">
              {Math.round(tick * 100)}
            </text>
          </g>
        ))}
        {xTicks.map((tick) => (
          <g key={tick}>
            <line x1={scaleX(tick)} x2={scaleX(tick)} y1={margin.top} y2={height - margin.bottom} className="chart-grid" />
            <text x={scaleX(tick)} y={height - margin.bottom + 22} textAnchor="middle" className="chart-axis-label">
              {tick < 1 ? "10^-1" : tick.toString()}
            </text>
          </g>
        ))}
        {rows.map((row, index) => (
          <g key={row.model_name}>
            <circle cx={scaleX(row.median_duration_seconds as number)} cy={scaleY(row.safe_success_rate)} r="5.5" className="ranked-point" />
            <text
              x={scaleX(row.median_duration_seconds as number) + (index % 2 === 0 ? 12 : -12)}
              y={scaleY(row.safe_success_rate) + (index % 2 === 0 ? -12 : 18)}
              textAnchor={index % 2 === 0 ? "start" : "end"}
              className="chart-model-label"
            >
              {row.model_name}
            </text>
            <text
              x={scaleX(row.median_duration_seconds as number) + (index % 2 === 0 ? 12 : -12)}
              y={scaleY(row.safe_success_rate) + (index % 2 === 0 ? 8 : 38)}
              textAnchor={index % 2 === 0 ? "start" : "end"}
              className="chart-percent-label"
            >
              {formatPercent(row.safe_success_rate)}
            </text>
          </g>
        ))}
        <text transform={`translate(18 ${height / 2}) rotate(-90)`} textAnchor="middle" className="chart-title-label">
          Safe task success (%)
        </text>
        <text x={(width + margin.left - margin.right) / 2} y={height - 10} textAnchor="middle" className="chart-title-label">
          Median time per task (s)
        </text>
      </svg>
      {missing.length > 0 && (
        <div className="telemetry-missing">
          <strong>Latency unavailable</strong>
          {missing.map((row) => (
            <span key={row.model_name}>{row.model_name}</span>
          ))}
        </div>
      )}
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
        <td>{model.rank ?? "—"}</td>
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
        <td>{formatPercent(model.task_success_ci95[0])} to {formatPercent(model.task_success_ci95[1])}</td>
        <td>{model.attempt_count} / {model.expected_attempt_count ?? model.attempt_count}</td>
        <td>{model.ranking_eligible ? "Ranked" : "Native / review"}</td>
      </tr>
      {expanded && (
        <tr className="detail-row">
          <td colSpan={11}>
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
  return "A two-patient, ten-task OpenKBP pilot spanning image localization, dose interpretation, plan review, data integrity, and TG-263 naming. Model ranks are provisional within this frozen harness.";
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
