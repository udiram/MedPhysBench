import { ChevronDown } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { domainLabel, formatDuration, formatPercent, formatTokens, providerLabel, shortHash } from "../lib/format";
import { inferExecutionSurface, surfaceLabel } from "../lib/runSurface";
import type { Leaderboard, ModelCatalogEntry, ModelResult, ModelTaskResult, ReleaseView } from "../types";

type SourceFilter = "all" | "open" | "closed" | "unknown";
type OutcomeFilter = "all" | "safe_success" | "safe_failure" | "unsafe" | "inconclusive" | "capability_failure";

type Props = {
  data: Leaderboard | null;
  modelCatalog: ModelCatalogEntry[];
  releaseView: ReleaseView;
};

type OutcomeKey = "safe_success" | "safe_failure" | "unsafe" | "inconclusive";

type VisibleRow = {
  key: string;
  row: ModelResult;
  source: SourceFilter;
};

const OUTCOME_ORDER: OutcomeKey[] = ["safe_success", "safe_failure", "unsafe", "inconclusive"];

export function ResultForensics({ data, modelCatalog, releaseView }: Props) {
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [providerFilter, setProviderFilter] = useState("all");
  const [modelKey, setModelKey] = useState<string>("");
  const [domainFilter, setDomainFilter] = useState("all");
  const [outcomeFilter, setOutcomeFilter] = useState<OutcomeFilter>("all");
  const [selectedTaskKey, setSelectedTaskKey] = useState<string>("");

  const catalogIndex = useMemo(
    () =>
      Object.fromEntries(
        modelCatalog.map((entry) => [`${entry.provider}::${entry.model_name}`, entry]),
      ) as Record<string, ModelCatalogEntry>,
    [modelCatalog],
  );

  const forensicRows = useMemo<VisibleRow[]>(() => {
    if (!data) return [];
    const combined = [...data.models, ...(data.unranked_models ?? [])];
    return combined
      .filter((row) => row.tasks.some((task) => task.outcome_category))
      .map((row) => {
        const source = catalogIndex[`${row.provider}::${row.model_name}`]?.openness ?? "unknown";
        return { key: `${row.provider}::${row.model_name}`, row, source };
      })
      .sort((left, right) => {
        const leftRank = left.row.outcome_rank ?? left.row.rank ?? Number.POSITIVE_INFINITY;
        const rightRank = right.row.outcome_rank ?? right.row.rank ?? Number.POSITIVE_INFINITY;
        return leftRank - rightRank || right.row.safe_success_rate - left.row.safe_success_rate;
      });
  }, [catalogIndex, data]);

  const visibleRows = useMemo<VisibleRow[]>(() => {
    return forensicRows
      .filter((entry) => {
        const matchesSource = sourceFilter === "all" || entry.source === sourceFilter;
        const matchesProvider = providerFilter === "all" || entry.row.provider === providerFilter;
        return matchesSource && matchesProvider;
      });
  }, [forensicRows, providerFilter, sourceFilter]);

  useEffect(() => {
    if (!visibleRows.length) {
      setModelKey("");
      return;
    }
    if (!visibleRows.some((entry) => entry.key === modelKey)) {
      setModelKey(visibleRows[0].key);
    }
  }, [modelKey, visibleRows]);

  const selected = useMemo(() => visibleRows.find((entry) => entry.key === modelKey) ?? null, [modelKey, visibleRows]);
  const selectedRow = selected?.row ?? null;

  const domains = useMemo(() => {
    if (!selectedRow) return [];
    return [...new Set(selectedRow.tasks.map((task) => task.domain))].sort();
  }, [selectedRow]);

  const filteredTasks = useMemo(() => {
    if (!selectedRow) return [];
    return selectedRow.tasks.filter((task) => {
      const matchesDomain = domainFilter === "all" || task.domain === domainFilter;
      const matchesOutcome = outcomeFilter === "all"
        || (outcomeFilter === "capability_failure"
          ? task.capability_failure === true
          : task.outcome_category === outcomeFilter);
      return matchesDomain && matchesOutcome;
    });
  }, [domainFilter, outcomeFilter, selectedRow]);

  const domainBuckets = useMemo(() => groupTasksByDomain(filteredTasks), [filteredTasks]);
  const distribution = useMemo(() => tallyOutcomes(filteredTasks), [filteredTasks]);
  const allDistribution = useMemo(() => tallyOutcomes(selectedRow?.tasks ?? []), [selectedRow]);
  const selectedTask = useMemo(() => {
    if (!filteredTasks.length) return null;
    if (selectedTaskKey) {
      const match = filteredTasks.find((task, index) => taskKey(task, index) === selectedTaskKey);
      if (match) return match;
    }
    return filteredTasks[0];
  }, [filteredTasks, selectedTaskKey]);

  useEffect(() => {
    if (!selectedTask) {
      setSelectedTaskKey("");
      return;
    }
    const key = taskKey(selectedTask, filteredTasks.indexOf(selectedTask));
    if (key !== selectedTaskKey) {
      setSelectedTaskKey(key);
    }
  }, [filteredTasks, selectedTask, selectedTaskKey]);

  const failedLanes = useMemo(() => tallyStrings(filteredTasks.flatMap((task) => task.failed_lanes ?? [])), [filteredTasks]);
  const failedGraders = useMemo(() => tallyStrings(filteredTasks.flatMap((task) => task.failed_graders ?? [])), [filteredTasks]);
  const providers = useMemo(
    () => [...new Set((data ? [...data.models, ...(data.unranked_models ?? [])] : []).map((row) => row.provider))].sort(),
    [data],
  );

  const supportsForensics = forensicRows.length > 0;

  if (!data) {
    return (
      <section className="forensics-section" id="forensics">
        <div className="section-heading">
          <h2>Attempt-level forensics</h2>
          <p>Loading the signed release bundle before exposing attempt-level evidence.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="forensics-section" id="forensics">
      <div className="section-heading section-heading-row">
        <div>
          <h2>Attempt-level forensics</h2>
          <p>
            Inspect where a model went right or wrong at the task level. This view uses released outputs,
            deterministic regrading, grader traces, and immutable hashes from the public artifact; legacy manifest
            gaps remain visible and cannot receive a current-contract rank.
          </p>
        </div>
        <p className="coverage-summary">
          {supportsForensics
            ? `${visibleRows.length} rows with attempt labels · ${filteredTasks.length} tasks in current slice`
            : "Aggregate-only release"}
        </p>
      </div>

      {!supportsForensics ? (
        <div className="forensics-empty">
          <strong>No attempt-level forensic projection exists for {releaseLabel(releaseView)}.</strong>
          <p>
            This release publishes aggregate metrics only. MedPhysBench does not infer synthetic failure categories for
            older bundles that lack task-level outcome labels and grader traces.
          </p>
        </div>
      ) : (
        <>
          <div className="forensics-controls">
            <label className="field">
              <span>Model source</span>
              <span className="select-wrap">
                <select
                  value={sourceFilter}
                  onChange={(event) => {
                    setSourceFilter(event.target.value as SourceFilter);
                    setProviderFilter("all");
                  }}
                >
                  <option value="all">Open + closed</option>
                  <option value="open">Open weights</option>
                  <option value="closed">Closed</option>
                  <option value="unknown">Unclassified</option>
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
            <label className="field">
              <span>Provider</span>
              <span className="select-wrap">
                <select value={providerFilter} onChange={(event) => setProviderFilter(event.target.value)}>
                  <option value="all">All providers</option>
                  {providers.map((provider) => (
                    <option key={provider} value={provider}>
                      {providerLabel(provider)}
                    </option>
                  ))}
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
            <label className="field model-field">
              <span>Run set</span>
              <span className="select-wrap">
                <select value={modelKey} onChange={(event) => setModelKey(event.target.value)}>
                  {visibleRows.map((entry) => (
                    <option key={entry.key} value={entry.key}>
                      {entry.row.model_name}
                    </option>
                  ))}
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
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
              <span>Outcome</span>
              <span className="select-wrap">
                <select value={outcomeFilter} onChange={(event) => setOutcomeFilter(event.target.value as OutcomeFilter)}>
                  <option value="all">All outcomes</option>
                  <option value="safe_success">Safe success</option>
                  <option value="safe_failure">Safe failure</option>
                  <option value="unsafe">Unsafe</option>
                  <option value="inconclusive">Inconclusive</option>
                  <option value="capability_failure">Capability failure</option>
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
          </div>

          {selectedRow ? (
            <>
              <div className="forensics-kpis">
                {OUTCOME_ORDER.map((outcome) => (
                  <article key={outcome} className={`forensics-kpi ${outcomeClassName(outcome)}`}>
                    <span>{outcomeLabel(outcome)}</span>
                    <strong>{distribution[outcome]}</strong>
                    <small>
                      {filteredTasks.length ? formatPercent(distribution[outcome] / filteredTasks.length) : "—"} of filtered
                      slice
                    </small>
                  </article>
                ))}
              </div>

              <div className="forensics-layout">
                <article className="forensics-main">
                  <div className="forensics-domain-list">
                    {domainBuckets.map(({ domain, tasks }) => {
                      const counts = tallyOutcomes(tasks);
                      return (
                        <section key={domain} className="forensics-domain-group">
                          <header>
                            <div>
                              <h3>{domainLabel(domain)}</h3>
                              <p>{tasks.length} task{tasks.length === 1 ? "" : "s"} in current slice</p>
                            </div>
                            <div className="forensics-domain-bar" aria-label={`${domain}: outcome split`}>
                              {OUTCOME_ORDER.map((outcome) => (
                                <i
                                  key={outcome}
                                  className={outcomeClassName(outcome)}
                                  style={{ width: `${tasks.length ? (counts[outcome] / tasks.length) * 100 : 0}%` }}
                                />
                              ))}
                            </div>
                          </header>
                          <div className="forensics-task-grid">
                            {tasks.map((task, index) => {
                              const currentKey = taskKey(task, index);
                              return (
                              <button
                                key={currentKey}
                                type="button"
                                className={`forensics-task-card ${outcomeClassName(task.outcome_category)}${selectedTask && currentKey === taskKey(selectedTask, filteredTasks.indexOf(selectedTask)) ? " selected" : ""}`}
                                onClick={() => setSelectedTaskKey(currentKey)}
                              >
                                <span>{task.title}</span>
                                <small>{task.task_id}</small>
                                <small>
                                  Attempt {task.attempt_index != null ? task.attempt_index + 1 : "—"}
                                  {task.seed != null ? ` · seed ${task.seed}` : ""}
                                </small>
                                {task.model_failure_kind ? <small>{failureKindLabel(task.model_failure_kind)}</small> : null}
                                <em>{outcomeLabel(task.outcome_category)}</em>
                              </button>
                              );
                            })}
                          </div>
                        </section>
                      );
                    })}
                  </div>
                </article>

                <aside className="forensics-sidebar">
                  <section className="forensics-panel">
                    <h3>Selected run set</h3>
                    <dl className="forensics-meta">
                      <div><dt>Model</dt><dd>{selectedRow.model_name}</dd></div>
                      <div><dt>Provider</dt><dd>{providerLabel(selectedRow.provider)}</dd></div>
                      <div><dt>Source</dt><dd>{sourceLabel(selected?.source ?? "unknown")}</dd></div>
                      <div><dt>Surface</dt><dd>{surfaceLabel(inferExecutionSurface(selectedRow))}</dd></div>
                      <div><dt>Outcome order</dt><dd>#{selectedRow.outcome_rank ?? "—"}</dd></div>
                      <div><dt>Official rank</dt><dd>{selectedRow.rank ? `${selectedRow.rank}` : "Not assigned"}</dd></div>
                      <div><dt>Safe success</dt><dd>{formatPercent(selectedRow.safe_success_rate)}</dd></div>
                      <div><dt>Median time</dt><dd>{formatDuration(selectedRow.median_duration_seconds)}</dd></div>
                      <div><dt>Median tokens</dt><dd>{formatTokens(selectedRow.token_usage?.median_total_tokens)}</dd></div>
                    </dl>
                    <p className="forensics-note">
                      {selectedRow.ranking_eligible
                        ? "This row belongs to an official comparison group with an assigned rank."
                        : "This row is visible in descriptive outcome order only. It remains outside official rank groups."}
                    </p>
                  </section>

                  <section className="forensics-panel">
                    <h3>Failure anatomy in current slice</h3>
                    <div className="forensics-failure-columns">
                      <div>
                        <strong>Failed lanes</strong>
                        <ol>
                          {failedLanes.length ? (
                            failedLanes.slice(0, 6).map(([value, count]) => (
                              <li key={value}>
                                <span>{value}</span>
                                <em>{count}</em>
                              </li>
                            ))
                          ) : (
                            <li className="empty">No failed lanes recorded.</li>
                          )}
                        </ol>
                      </div>
                      <div>
                        <strong>Failed graders</strong>
                        <ol>
                          {failedGraders.length ? (
                            failedGraders.slice(0, 6).map(([value, count]) => (
                              <li key={value}>
                                <span>{value}</span>
                                <em>{count}</em>
                              </li>
                            ))
                          ) : (
                            <li className="empty">No failed graders recorded.</li>
                          )}
                        </ol>
                      </div>
                    </div>
                  </section>

                  {selectedTask ? (
                    <section className="forensics-panel">
                      <h3>Selected task evidence</h3>
                      <div className={`forensics-task-detail ${outcomeClassName(selectedTask.outcome_category)}`}>
                        <strong>{selectedTask.title}</strong>
                        <p>{domainLabel(selectedTask.domain)} · {outcomeLabel(selectedTask.outcome_category)}</p>
                        <dl className="forensics-meta compact">
                          <div><dt>Task</dt><dd>{selectedTask.task_id}</dd></div>
                          <div><dt>Run</dt><dd>{shortHash(selectedTask.run_id)}</dd></div>
                          <div><dt>Prompt</dt><dd>{shortHash(selectedTask.prompt_hash)}</dd></div>
                          <div><dt>Tools</dt><dd>{shortHash(selectedTask.tool_schema_hash)}</dd></div>
                          <div><dt>Runtime</dt><dd>{shortHash(selectedTask.runtime_task_hash)}</dd></div>
                          <div><dt>Grader</dt><dd>{shortHash(selectedTask.grader_hash)}</dd></div>
                          <div><dt>Failure kind</dt><dd>{selectedTask.model_failure_kind ? failureKindLabel(selectedTask.model_failure_kind) : "Model output graded"}</dd></div>
                          <div><dt>Capability failure</dt><dd>{selectedTask.capability_failure ? "Yes" : "No"}</dd></div>
                        </dl>
                        <div className="forensics-tag-groups">
                          <div>
                            <span>Failed lanes</span>
                            <ul>
                              {(selectedTask.failed_lanes?.length ? selectedTask.failed_lanes : ["None"]).map((value) => (
                                <li key={value}>{value}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <span>Failed graders</span>
                            <ul>
                              {(selectedTask.failed_graders?.length ? selectedTask.failed_graders : ["None"]).map((value) => (
                                <li key={value}>{value}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    </section>
                  ) : null}

                  <section className="forensics-panel">
                    <h3>Full-run outcome mix</h3>
                    <div className="forensics-domain-bar large" aria-label="Full-run outcome split">
                      {OUTCOME_ORDER.map((outcome) => (
                        <i
                          key={outcome}
                          className={outcomeClassName(outcome)}
                          style={{
                            width: `${selectedRow.tasks.length ? (allDistribution[outcome] / selectedRow.tasks.length) * 100 : 0}%`,
                          }}
                        />
                      ))}
                    </div>
                    <ul className="forensics-outcome-list">
                      {OUTCOME_ORDER.map((outcome) => (
                        <li key={outcome}>
                          <span>{outcomeLabel(outcome)}</span>
                          <em>{allDistribution[outcome]}</em>
                        </li>
                      ))}
                    </ul>
                  </section>
                </aside>
              </div>
            </>
          ) : (
            <div className="forensics-empty">
              <strong>No released run sets match this source and provider combination.</strong>
              <p>Change either filter to restore the attempt-level evidence view; the controls remain available.</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function releaseLabel(releaseView: ReleaseView) {
  if (releaseView === "real") return "the real-workflow release";
  if (releaseView === "tg263") return "the TG-263 pilot";
  if (releaseView === "imaging") return "the imaging pilot";
  return "the public core release";
}

function tallyOutcomes(tasks: readonly ModelTaskResult[]) {
  const counts: Record<OutcomeKey, number> = {
    safe_success: 0,
    safe_failure: 0,
    unsafe: 0,
    inconclusive: 0,
  };
  for (const task of tasks) {
    const key = normalizeOutcome(task.outcome_category);
    counts[key] += 1;
  }
  return counts;
}

function normalizeOutcome(value: string | undefined): OutcomeKey {
  if (value === "safe_success" || value === "safe_failure" || value === "unsafe" || value === "inconclusive") {
    return value;
  }
  return "inconclusive";
}

function outcomeLabel(value: string | undefined) {
  const outcome = normalizeOutcome(value);
  if (outcome === "safe_success") return "Safe success";
  if (outcome === "safe_failure") return "Safe failure";
  if (outcome === "unsafe") return "Unsafe";
  return "Inconclusive";
}

function outcomeClassName(value: string | undefined) {
  return `outcome-${normalizeOutcome(value)}`;
}

function groupTasksByDomain(tasks: readonly ModelTaskResult[]) {
  const buckets = new Map<string, ModelTaskResult[]>();
  for (const task of tasks) {
    const bucket = buckets.get(task.domain);
    if (bucket) {
      bucket.push(task);
    } else {
      buckets.set(task.domain, [task]);
    }
  }
  return [...buckets.entries()]
    .map(([domain, domainTasks]) => ({
      domain,
      tasks: [...domainTasks].sort((left, right) => left.title.localeCompare(right.title)),
    }))
    .sort((left, right) => left.domain.localeCompare(right.domain));
}

function tallyStrings(values: readonly string[]) {
  const counts = new Map<string, number>();
  for (const value of values) {
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
}

function sourceLabel(value: SourceFilter) {
  if (value === "open") return "Open weights";
  if (value === "closed") return "Closed";
  return "Unclassified";
}

function taskKey(task: ModelTaskResult, index: number) {
  return [
    task.task_id,
    task.attempt_index ?? index,
    task.seed ?? "noseed",
    task.run_id ?? "norun",
  ].join("::");
}

function failureKindLabel(value: string) {
  if (value === "unsupported_required_modality") return "Unsupported required modality";
  if (value === "provider_output_contract_failure") return "Provider output contract failure";
  return value.replaceAll("_", " ");
}
