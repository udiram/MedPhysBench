import { ArrowDownToLine, ChevronDown, Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { AccessStatus, Leaderboard, ModelResult } from "../types";
import { domainLabel, formatDuration, formatPercent, shortHash } from "../lib/format";

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
};

const SORT_KEYS: Array<{ key: SortKey; label: string }> = [
  { key: "model_name", label: "Model" },
  { key: "safe_success_rate", label: "Safe success" },
  { key: "task_success_rate", label: "Task success" },
  { key: "safety_gate_rate", label: "Safety" },
  { key: "valid_output_rate", label: "Output" },
  { key: "appropriate_escalation_rate", label: "Escalation" },
  { key: "median_duration_seconds", label: "Median duration" },
];

export function LeaderboardExplorer({ data, accessStatus, loadError }: LeaderboardExplorerProps) {
  const [query, setQuery] = useState("");
  const [domainFilter, setDomainFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("safe_success_rate");
  const [sortDirection, setSortDirection] = useState<"desc" | "asc">("desc");
  const [expanded, setExpanded] = useState<string | null>(null);

  const domains = useMemo(() => {
    const values = new Set<string>();
    data?.tasks.forEach((task) => values.add(task.domain));
    return [...values].sort();
  }, [data]);

  const rows = useMemo(() => {
    if (!data) return [];
    return [...data.models, ...(data.unranked_models ?? [])]
      .filter((model) => {
        const q = query.trim().toLowerCase();
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
  }, [data, domainFilter, query, sortDirection, sortKey, statusFilter]);

  const blocked = accessStatus.filter((item) => item.status !== "available");

  return (
    <section className="leaderboard-section" id="leaderboard">
      <div className="section-heading section-heading-row">
        <div>
          <h2>Public leaderboard</h2>
          <p>Common-harness results on the open development release. Scores are reproducibility evidence, not clinical validation.</p>
        </div>
        <a className="download-link" href="/data/leaderboard.json" download>
          <ArrowDownToLine aria-hidden="true" /> Download JSON
        </a>
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
              <option value="review">Integrity review required</option>
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
            <caption className="sr-only">MedPhysBench public leaderboard</caption>
            <thead>
              <tr>
                <th>Rank</th>
                {SORT_KEYS.map((item) => (
                  <th
                    key={item.key}
                    aria-sort={sortKey === item.key ? (sortDirection === "asc" ? "ascending" : "descending") : "none"}
                  >
                    <button
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
                  model={model}
                  domainFilter={domainFilter}
                  expanded={expanded === model.model_name}
                  onToggle={() => setExpanded((value) => (value === model.model_name ? null : model.model_name))}
                />
              ))}
            </tbody>
          </table>
          {data && rows.length === 0 && (
            <p className="table-state" role="status">No model runs match the current filters.</p>
          )}
          {!data && !loadError && <p className="table-state" role="status">Loading verified run artifacts…</p>}
          {loadError && <p className="table-state table-error" role="alert">Leaderboard data is unavailable. The repository still contains the current release package.</p>}
        </div>
      </div>

      {blocked.length > 0 && (
        <div className="access-panel">
          <div className="section-heading">
            <h3>Unavailable handles stay separate from scored results</h3>
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
        <td>{model.ranking_eligible ? "Ranked" : "Review"}</td>
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
                        <strong>{task.safe ? "Safe" : "Unsafe"}</strong>
                      </header>
                      <p>{domainLabel(task.domain)}</p>
                      <dl>
                        <div><dt>Run</dt><dd>{shortHash(task.run_id)}</dd></div>
                        <div><dt>Prompt</dt><dd>{shortHash(task.prompt_hash)}</dd></div>
                        <div><dt>Tools</dt><dd>{shortHash(task.tool_schema_hash)}</dd></div>
                        <div><dt>Runtime</dt><dd>{shortHash(task.runtime_task_hash)}</dd></div>
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
  if (leftValue !== rightValue) {
    return direction * ((leftValue ?? -1) - (rightValue ?? -1));
  }
  return String(left.model_name).localeCompare(String(right.model_name));
}

function comparableMetric(model: ModelResult, sortKey: SortKey, domainFilter: string) {
  if (sortKey === "model_name") return model.model_name;
  if (sortKey === "safe_success_rate" && domainFilter !== "all") {
    return model.domain_safe_success[domainFilter] ?? 0;
  }
  return model[sortKey] ?? 0;
}

function metricForDomain(model: ModelResult, domainFilter: string) {
  return domainFilter === "all" ? model.safe_success_rate : model.domain_safe_success[domainFilter] ?? 0;
}
