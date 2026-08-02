import { ChevronDown, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import { domainLabel, formatDuration, formatPercent, formatTokens, shortHash } from "../lib/format";
import type {
  Leaderboard,
  ModelCatalogEntry,
  ModelOpenness,
  ModelResult,
  ModelTaskResult,
  PublicReleaseKey,
} from "../types";

type ReleaseDataset = {
  key: PublicReleaseKey;
  label: string;
  data: Leaderboard | null;
};

type PublicModelIndexProps = {
  catalog: ModelCatalogEntry[];
  datasets: ReleaseDataset[];
};

type PublicRun = ModelResult & {
  release_key: PublicReleaseKey;
  release_id: string;
  release_title: string;
  task_count: number;
};

type ModelGroup = {
  key: string;
  model_name: string;
  provider: string;
  catalog: ModelCatalogEntry | null;
  runs: PublicRun[];
  release_count: number;
  best_safe_success_rate: number;
  official_count: number;
  native_count: number;
};

export function PublicModelIndex({ catalog, datasets }: PublicModelIndexProps) {
  const [query, setQuery] = useState("");
  const [openness, setOpenness] = useState<ModelOpenness | "all">("all");
  const [provider, setProvider] = useState<string>("all");
  const [release, setRelease] = useState<PublicReleaseKey | "all">("all");
  const [surface, setSurface] = useState<"all" | "common" | "native">("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query);

  const catalogMap = useMemo(
    () => new Map(catalog.map((entry) => [`${entry.provider}::${entry.model_name}`, entry])),
    [catalog],
  );

  const runs = useMemo(() => {
    const flattened: PublicRun[] = [];
    for (const dataset of datasets) {
      if (!dataset.data) continue;
      const rows = [...dataset.data.models, ...(dataset.data.unranked_models ?? [])];
      for (const row of rows) {
        flattened.push({
          ...row,
          release_key: dataset.key,
          release_id: dataset.data.release.release_id,
          release_title: dataset.label,
          task_count: dataset.data.tasks.length,
        });
      }
    }
    return flattened.sort(
      (left, right) =>
        right.safe_success_rate - left.safe_success_rate ||
        left.model_name.localeCompare(right.model_name) ||
        left.release_id.localeCompare(right.release_id),
    );
  }, [datasets]);

  const providers = useMemo(() => [...new Set(runs.map((row) => row.provider))].sort(), [runs]);

  const filteredRuns = useMemo(() => {
    const normalized = deferredQuery.trim().toLowerCase();
    return runs.filter((row) => {
      const entry = catalogMap.get(`${row.provider}::${row.model_name}`) ?? null;
      const matchesQuery =
        !normalized ||
        row.model_name.toLowerCase().includes(normalized) ||
        row.provider.toLowerCase().includes(normalized) ||
        row.release_id.toLowerCase().includes(normalized) ||
        entry?.family.toLowerCase().includes(normalized) === true;
      const matchesOpenness = openness === "all" || (entry?.openness ?? "unknown") === openness;
      const matchesProvider = provider === "all" || row.provider === provider;
      const matchesRelease = release === "all" || row.release_key === release;
      const matchesSurface =
        surface === "all" ||
        (surface === "common" && row.ranking_eligible) ||
        (surface === "native" && !row.ranking_eligible);
      return matchesQuery && matchesOpenness && matchesProvider && matchesRelease && matchesSurface;
    });
  }, [catalogMap, deferredQuery, openness, provider, release, runs, surface]);

  const groups = useMemo(() => {
    const grouped = new Map<string, ModelGroup>();
    for (const row of filteredRuns) {
      const key = `${row.provider}::${row.model_name}`;
      const current = grouped.get(key);
      if (current) {
        current.runs.push(row);
        current.release_count = new Set(current.runs.map((item) => item.release_id)).size;
        current.best_safe_success_rate = Math.max(current.best_safe_success_rate, row.safe_success_rate);
        current.official_count += row.ranking_eligible ? 1 : 0;
        current.native_count += row.ranking_eligible ? 0 : 1;
      } else {
        grouped.set(key, {
          key,
          model_name: row.model_name,
          provider: row.provider,
          catalog: catalogMap.get(key) ?? null,
          runs: [row],
          release_count: 1,
          best_safe_success_rate: row.safe_success_rate,
          official_count: row.ranking_eligible ? 1 : 0,
          native_count: row.ranking_eligible ? 0 : 1,
        });
      }
    }
    return [...grouped.values()].sort(
      (left, right) =>
        right.best_safe_success_rate - left.best_safe_success_rate ||
        right.release_count - left.release_count ||
        left.model_name.localeCompare(right.model_name),
    );
  }, [catalogMap, filteredRuns]);

  const loadedReleaseCount = datasets.filter((dataset) => dataset.data).length;
  const openCount = groups.filter((group) => (group.catalog?.openness ?? "unknown") === "open").length;
  const closedCount = groups.filter((group) => (group.catalog?.openness ?? "unknown") === "closed").length;
  const groqCount = groups.filter((group) => group.provider === "groq").length;

  return (
    <section className="model-index-section" id="model-index">
      <div className="section-heading">
        <h2>All public model systems</h2>
        <p>
          Every shipped public run stays in one index. Filters change the slice; they do not hide execution-surface differences or
          invent cross-release comparability.
        </p>
      </div>

      <div className="model-index-kpis">
        <article>
          <span>Model systems</span>
          <strong>{groups.length}</strong>
          <small>{loadedReleaseCount} public releases loaded</small>
        </article>
        <article>
          <span>Open-weight</span>
          <strong>{openCount}</strong>
          <small>Catalogued as open source / open weight</small>
        </article>
        <article>
          <span>Closed</span>
          <strong>{closedCount}</strong>
          <small>Provider-native or closed deployment surface</small>
        </article>
        <article>
          <span>Groq-hosted</span>
          <strong>{groqCount}</strong>
          <small>Visible in the same index as every other system</small>
        </article>
      </div>

      <div className="model-index-controls">
        <label className="field search-field">
          <span>Search</span>
          <span className="search-wrap">
            <Search aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Model, family, provider, or release"
            />
          </span>
        </label>
        <label className="field">
          <span>Openness</span>
          <span className="select-wrap">
            <select value={openness} onChange={(event) => setOpenness(event.target.value as ModelOpenness | "all")}>
              <option value="all">All systems</option>
              <option value="open">Open source / open weight</option>
              <option value="closed">Closed source</option>
              <option value="unknown">Unclassified</option>
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field">
          <span>Provider</span>
          <span className="select-wrap">
            <select value={provider} onChange={(event) => setProvider(event.target.value)}>
              <option value="all">All providers</option>
              {providers.map((value) => (
                <option key={value} value={value}>
                  {providerLabel(value)}
                </option>
              ))}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field">
          <span>Release</span>
          <span className="select-wrap">
            <select value={release} onChange={(event) => setRelease(event.target.value as PublicReleaseKey | "all")}>
              <option value="all">All public releases</option>
              {datasets.map((dataset) => (
                <option key={dataset.key} value={dataset.key}>
                  {dataset.label}
                </option>
              ))}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field">
          <span>Execution surface</span>
          <span className="select-wrap">
            <select value={surface} onChange={(event) => setSurface(event.target.value as "all" | "common" | "native")}>
              <option value="all">All surfaces</option>
              <option value="common">Common harness</option>
              <option value="native">Native / recorded surface</option>
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
      </div>

      <div className="table-frame">
        <div className="table-scroll" role="region" aria-label="All public model systems" tabIndex={0}>
          <table className="leaderboard-table model-index-table">
            <thead>
              <tr>
                <th>Model system</th>
                <th>Source</th>
                <th>Provider</th>
                <th>Family</th>
                <th>Releases</th>
                <th>Best score</th>
                <th>Official</th>
                <th>Native</th>
              </tr>
            </thead>
            <tbody>
              {groups.map((group) => (
                <ModelRegistryRow
                  key={group.key}
                  expanded={expanded === group.key}
                  group={group}
                  onToggle={() => setExpanded((value) => (value === group.key ? null : group.key))}
                />
              ))}
            </tbody>
          </table>
          {groups.length === 0 && (
            <p className="table-state" role="status">
              No public model systems match the current filters.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function ModelRegistryRow({
  group,
  expanded,
  onToggle,
}: {
  group: ModelGroup;
  expanded: boolean;
  onToggle: () => void;
}) {
  const sortedRuns = [...group.runs].sort(
    (left, right) =>
      right.safe_success_rate - left.safe_success_rate ||
      left.release_id.localeCompare(right.release_id),
  );

  return (
    <>
      <tr className={expanded ? "model-row expanded" : "model-row"}>
        <td>
          <button
            type="button"
            className="row-toggle"
            onClick={onToggle}
            aria-expanded={expanded}
            aria-label={`${expanded ? "Collapse" : "Expand"} ${group.model_name} public run details`}
          >
            <span>{group.model_name}</span>
            <small>{group.catalog?.steward ?? "Catalog pending"}</small>
          </button>
        </td>
        <td>{opennessLabel(group.catalog?.openness ?? "unknown")}</td>
        <td>{providerLabel(group.provider)}</td>
        <td>{group.catalog?.family ?? "Unknown"}</td>
        <td>{group.release_count}</td>
        <td>{formatPercent(group.best_safe_success_rate)}</td>
        <td>{group.official_count}</td>
        <td>{group.native_count}</td>
      </tr>
      {expanded && (
        <tr className="detail-row">
          <td colSpan={8}>
            <div className="model-registry-detail">
              <section>
                <h4>Registry summary</h4>
                <dl className="metric-list">
                  <div>
                    <dt>Model family</dt>
                    <dd>{group.catalog?.family ?? "Unknown"}</dd>
                  </div>
                  <div>
                    <dt>Provider</dt>
                    <dd>{providerLabel(group.provider)}</dd>
                  </div>
                  <div>
                    <dt>Source class</dt>
                    <dd>{opennessLabel(group.catalog?.openness ?? "unknown")}</dd>
                  </div>
                  <div>
                    <dt>Public releases</dt>
                    <dd>{group.release_count}</dd>
                  </div>
                  <div>
                    <dt>Official rows</dt>
                    <dd>{group.official_count}</dd>
                  </div>
                  <div>
                    <dt>Native rows</dt>
                    <dd>{group.native_count}</dd>
                  </div>
                </dl>
              </section>
              <section className="detail-span">
                <h4>Release-by-release evidence</h4>
                <div className="registry-run-grid">
                  {sortedRuns.map((run) => {
                    const failures = run.tasks.filter((task) => taskOutcome(task) !== "safe-pass");
                    const safePasses = run.tasks.length - failures.length;
                    return (
                      <article key={`${run.release_id}-${run.model_name}`} className="registry-run-card">
                        <header>
                          <div>
                            <strong>{run.release_title}</strong>
                            <p>{run.release_id}</p>
                          </div>
                          <div className="registry-run-badges">
                            <span className={run.ranking_eligible ? "result-chip common" : "result-chip native"}>
                              {run.ranking_eligible ? "Common harness" : "Native surface"}
                            </span>
                            <span className="result-chip score">{formatPercent(run.safe_success_rate)}</span>
                          </div>
                        </header>
                        <dl className="metric-list registry-metrics">
                          <div>
                            <dt>95% CI</dt>
                            <dd>
                              {formatPercent((run.safe_success_ci95 ?? run.task_success_ci95)[0])}–
                              {formatPercent((run.safe_success_ci95 ?? run.task_success_ci95)[1])}
                            </dd>
                          </div>
                          <div>
                            <dt>Safety</dt>
                            <dd>{formatPercent(run.safety_gate_rate)}</dd>
                          </div>
                          <div>
                            <dt>Output valid</dt>
                            <dd>{formatPercent(run.valid_output_rate)}</dd>
                          </div>
                          <div>
                            <dt>Median tokens</dt>
                            <dd>{formatTokens(run.token_usage?.median_total_tokens)}</dd>
                          </div>
                          <div>
                            <dt>Median time</dt>
                            <dd>{formatDuration(run.median_duration_seconds)}</dd>
                          </div>
                          <div>
                            <dt>Tasks</dt>
                            <dd>{run.task_count}</dd>
                          </div>
                        </dl>
                        <div className="registry-outcome-strip">
                          <span>{safePasses} safe passes</span>
                          <span>{failures.length} non-pass outcomes</span>
                          <span>{run.comparison_group ?? run.harness_revision ?? "Recorded native surface"}</span>
                        </div>
                        {failures.length === 0 ? (
                          <p className="integrity-clean">All published tasks safely passed in this run.</p>
                        ) : (
                          <div className="registry-failure-list">
                            {failures.map((task) => (
                              <article key={`${run.release_id}-${task.task_id}-${task.attempt_index ?? 0}`}>
                                <header>
                                  <strong>{task.title}</strong>
                                  <span>{outcomeLabel(task)}</span>
                                </header>
                                <p>{domainLabel(task.domain)}</p>
                                <dl>
                                  <div>
                                    <dt>Task</dt>
                                    <dd>{task.task_id}</dd>
                                  </div>
                                  <div>
                                    <dt>Run</dt>
                                    <dd>{shortHash(task.run_id)}</dd>
                                  </div>
                                  <div>
                                    <dt>Prompt</dt>
                                    <dd>{shortHash(task.prompt_hash)}</dd>
                                  </div>
                                  <div>
                                    <dt>Tools</dt>
                                    <dd>{shortHash(task.tool_schema_hash)}</dd>
                                  </div>
                                </dl>
                              </article>
                            ))}
                          </div>
                        )}
                      </article>
                    );
                  })}
                </div>
              </section>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function taskOutcome(task: ModelTaskResult) {
  if (task.safe && task.passed !== false) return "safe-pass";
  if (task.safe === false) return "unsafe";
  if (task.passed === false) return "safe-fail";
  return "unknown";
}

function outcomeLabel(task: ModelTaskResult) {
  const status = taskOutcome(task);
  if (status === "safe-pass") return "Safe pass";
  if (status === "unsafe") return "Unsafe";
  if (status === "safe-fail") return "Safe failure";
  return "Outcome unavailable";
}

function providerLabel(provider: string) {
  if (provider === "codex-native") return "Codex native";
  if (provider === "groq") return "Groq";
  if (provider === "ollama") return "Ollama";
  return provider;
}

function opennessLabel(value: ModelOpenness) {
  if (value === "open") return "Open";
  if (value === "closed") return "Closed";
  return "Unknown";
}
