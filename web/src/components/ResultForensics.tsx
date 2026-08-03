import { ChevronDown } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { domainLabel, formatDuration, formatPercent, formatTokens, providerLabel, shortHash } from "../lib/format";
import { defectsForTask } from "../lib/defects";
import { inferExecutionSurface, surfaceLabel } from "../lib/runSurface";
import { modelRunKey } from "../lib/modelRunKey";
import { buildTaskComparison } from "../lib/taskComparison";
import { getUrlParam, readEnumParam, setUrlParams } from "../lib/urlState";
import { normalizeForensicsOutcome } from "../types";
import type { DefectLedger, ForensicsOutcomeCategory, Leaderboard, ModelCatalogEntry, ModelResult, ModelTaskResult, ReleaseView } from "../types";

type SourceFilter = "all" | "open" | "closed" | "unknown";
type OutcomeFilter = "all" | "safe_success" | "safe_failure" | "unsafe" | "unavailable" | "inconclusive" | "capability_failure";

type Props = {
  data: Leaderboard | null;
  defectLedger: DefectLedger | null;
  modelCatalog: ModelCatalogEntry[];
  releaseView: ReleaseView;
};

type OutcomeKey = ForensicsOutcomeCategory;

type VisibleRow = {
  key: string;
  row: ModelResult;
  source: SourceFilter;
};

type DomainSummaryRow = {
  domain: string;
  attempts: number;
  safeSuccess: number;
  safeFailure: number;
  unsafe: number;
  unavailable: number;
  inconclusive: number;
  topLane: string | null;
  topGrader: string | null;
};

const OUTCOME_ORDER: OutcomeKey[] = ["safe_success", "safe_failure", "unsafe", "unavailable", "inconclusive"];

export function ResultForensics({ data, defectLedger, modelCatalog, releaseView }: Props) {
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>(() => readEnumParam("fx_source", ["all", "open", "closed", "unknown"] as const, "all"));
  const [providerFilter, setProviderFilter] = useState(() => getUrlParam("fx_provider") ?? "all");
  const [modelKey, setModelKey] = useState<string>(() => getUrlParam("fx_model") ?? "");
  const [domainFilter, setDomainFilter] = useState(() => getUrlParam("fx_domain") ?? "all");
  const [outcomeFilter, setOutcomeFilter] = useState<OutcomeFilter>(() => readEnumParam("fx_outcome", ["all", "safe_success", "safe_failure", "unsafe", "unavailable", "inconclusive", "capability_failure"] as const, "all"));
  const [selectedTaskKey, setSelectedTaskKey] = useState<string>(() => getUrlParam("fx_task") ?? "");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handlePopState = () => {
      setSourceFilter(readEnumParam("fx_source", ["all", "open", "closed", "unknown"] as const, "all"));
      setProviderFilter(getUrlParam("fx_provider") ?? "all");
      setModelKey(getUrlParam("fx_model") ?? "");
      setDomainFilter(getUrlParam("fx_domain") ?? "all");
      setOutcomeFilter(readEnumParam("fx_outcome", ["all", "safe_success", "safe_failure", "unsafe", "unavailable", "inconclusive", "capability_failure"] as const, "all"));
      setSelectedTaskKey(getUrlParam("fx_task") ?? "");
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

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
      .filter((row) => row.tasks.some((task) => task.outcome_category || task.capability_failure))
      .map((row) => {
        const source = catalogIndex[`${row.provider}::${row.model_name}`]?.openness ?? "unknown";
        return { key: modelRunKey(row), row, source };
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
    if (!data) return;
    if (!visibleRows.length) {
      setModelKey("");
      setUrlParams({ fx_model: null });
      return;
    }
    if (!visibleRows.some((entry) => entry.key === modelKey)) {
      const next = visibleRows[0].key;
      setModelKey(next);
      setUrlParams({ fx_model: next });
    }
  }, [data, modelKey, visibleRows]);

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
      const normalizedOutcome = normalizeForensicsOutcome(task.outcome_category, task.capability_failure === true);
      const matchesOutcome = outcomeFilter === "all"
        || (outcomeFilter === "capability_failure"
          ? task.capability_failure === true
          : normalizedOutcome === outcomeFilter);
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
  const selectedTaskUnavailable = selectedTask
    ? normalizeForensicsOutcome(selectedTask.outcome_category, selectedTask.capability_failure === true) === "unavailable"
    : false;
  const selectedTaskDefects = useMemo(
    () => defectsForTask(defectLedger, selectedTask?.task_id ?? ""),
    [defectLedger, selectedTask?.task_id],
  );
  const taskComparison = useMemo(() => {
    return buildTaskComparison(visibleRows, selectedTask?.task_id ?? null);
  }, [selectedTask, visibleRows]);

  useEffect(() => {
    if (!selectedRow) return;
    if (!selectedTask) {
      setSelectedTaskKey("");
      setUrlParams({ fx_task: null });
      return;
    }
    const key = taskKey(selectedTask, filteredTasks.indexOf(selectedTask));
    if (key !== selectedTaskKey) {
      setSelectedTaskKey(key);
      setUrlParams({ fx_task: key });
    }
  }, [filteredTasks, selectedRow, selectedTask, selectedTaskKey]);

  const failedLanes = useMemo(() => tallyStrings(filteredTasks.flatMap((task) => task.failed_lanes ?? [])), [filteredTasks]);
  const failedGraders = useMemo(() => tallyStrings(filteredTasks.flatMap((task) => task.failed_graders ?? [])), [filteredTasks]);
  const domainSummary = useMemo<DomainSummaryRow[]>(() => {
    return domainBuckets.map(({ domain, tasks }) => {
      const counts = tallyOutcomes(tasks);
      const lanes = tallyStrings(tasks.flatMap((task) => task.failed_lanes ?? []));
      const graders = tallyStrings(tasks.flatMap((task) => task.failed_graders ?? []));
      return {
        domain,
        attempts: tasks.length,
        safeSuccess: counts.safe_success,
        safeFailure: counts.safe_failure,
        unsafe: counts.unsafe,
        unavailable: counts.unavailable,
        inconclusive: counts.inconclusive,
        topLane: lanes[0]?.[0] ?? null,
        topGrader: graders[0]?.[0] ?? null,
      };
    }).sort(
      (left, right) =>
        right.unsafe - left.unsafe ||
        right.unavailable - left.unavailable ||
        right.safeFailure - left.safeFailure ||
        right.attempts - left.attempts ||
        left.domain.localeCompare(right.domain),
    );
  }, [domainBuckets]);
  const providers = useMemo(
    () => [...new Set([
      ...(data ? [...data.models, ...(data.unranked_models ?? [])] : []).map((row) => row.provider),
      ...modelCatalog.map((entry) => entry.provider),
    ])].sort(),
    [data, modelCatalog],
  );

  const supportsForensics = forensicRows.length > 0;
  const showsPublicOutputs = data?.release.public_attempt_detail === "sanitized_output";

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
            Inspect where a model went right or wrong at the task level. This view uses deterministic regrading,
            failure contracts, immutable hashes, and—only when the release explicitly permits it—schema-filtered
            public-development outputs. Legacy manifest gaps remain visible and cannot receive a current-contract rank.
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
              <span>Openness</span>
              <span className="select-wrap">
                <select
                  value={sourceFilter}
                  onChange={(event) => {
                    const next = event.target.value as SourceFilter;
                    setSourceFilter(next);
                    setProviderFilter("all");
                    setUrlParams(
                      { fx_source: next === "all" ? null : next, fx_provider: null },
                      { history: "push" },
                    );
                  }}
                >
                  <option value="all">All systems</option>
                  <option value="open">Open weights</option>
                  <option value="closed">Closed models</option>
                  <option value="unknown">Unclassified</option>
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
            <label className="field">
              <span>Provider</span>
              <span className="select-wrap">
                <select value={providerFilter} onChange={(event) => {
                  const next = event.target.value;
                  setProviderFilter(next);
                  setUrlParams({ fx_provider: next === "all" ? null : next }, { history: "push" });
                }}>
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
                <select value={modelKey} onChange={(event) => {
                  setModelKey(event.target.value);
                  setUrlParams({ fx_model: event.target.value }, { history: "push" });
                }}>
                  {visibleRows.map((entry) => (
                    <option key={entry.key} value={entry.key}>
                      {entry.row.model_name} · {entry.row.harness_revision ?? inferExecutionSurface(entry.row)}
                    </option>
                  ))}
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
            <label className="field">
              <span>Domain</span>
              <span className="select-wrap">
                <select value={domainFilter} onChange={(event) => {
                  const next = event.target.value;
                  setDomainFilter(next);
                  setUrlParams({ fx_domain: next === "all" ? null : next }, { history: "push" });
                }}>
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
                <select value={outcomeFilter} onChange={(event) => {
                  const next = event.target.value as OutcomeFilter;
                  setOutcomeFilter(next);
                  setUrlParams({ fx_outcome: next === "all" ? null : next }, { history: "push" });
                }}>
                  <option value="all">All outcomes</option>
                  <option value="safe_success">Safe success</option>
                  <option value="safe_failure">Safe failure</option>
                  <option value="unsafe">Unsafe</option>
                  <option value="unavailable">Capability unavailable</option>
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
                    {filteredTasks.length === 0 ? (
                      <div className="forensics-empty compact" role="status">
                        <strong>No task attempts match this filter combination.</strong>
                        <p>Change the domain or outcome filter to restore task-level evidence.</p>
                        <button
                          type="button"
                          onClick={() => {
                            setDomainFilter("all");
                            setOutcomeFilter("all");
                            setUrlParams({ fx_domain: null, fx_outcome: null }, { history: "push" });
                          }}
                        >
                          Reset task filters
                        </button>
                      </div>
                    ) : null}
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
                              const taskDefectCount = defectsForTask(defectLedger, task.task_id).length;
                              return (
                              <button
                                key={currentKey}
                                type="button"
                                className={`forensics-task-card ${outcomeClassName(task.outcome_category, task.capability_failure === true)}${selectedTask && currentKey === taskKey(selectedTask, filteredTasks.indexOf(selectedTask)) ? " selected" : ""}`}
                                onClick={() => {
                                  setSelectedTaskKey(currentKey);
                                  setUrlParams({ fx_task: currentKey }, { history: "push" });
                                }}
                              >
                                <span>{task.title}</span>
                                <small>{task.task_id}</small>
                                <small>
                                  Attempt {task.attempt_index != null ? task.attempt_index + 1 : "—"}
                                  {task.seed != null ? ` · seed ${task.seed}` : ""}
                                </small>
                                {task.model_failure_kind ? <small>{failureKindLabel(task.model_failure_kind)}</small> : null}
                                {taskDefectCount > 0 ? (
                                  <small className="forensics-task-qa">QA history · {taskDefectCount} disclosed</small>
                                ) : null}
                                <em>{outcomeLabel(task.outcome_category, task.capability_failure === true)}</em>
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

                  <section className="forensics-panel">
                    <h3>Domain breakdown in current slice</h3>
                    {domainSummary.length > 0 ? (
                      <div className="forensics-domain-summary">
                        {domainSummary.map((domainRow) => (
                          <button
                            key={domainRow.domain}
                            type="button"
                            className={`forensics-domain-summary-row${domainFilter === domainRow.domain ? " selected" : ""}`}
                            onClick={() => {
                              const next = domainFilter === domainRow.domain ? "all" : domainRow.domain;
                              setDomainFilter(next);
                              setUrlParams({ fx_domain: next === "all" ? null : next }, { history: "push" });
                            }}
                          >
                            <div>
                              <strong>{domainLabel(domainRow.domain)}</strong>
                              <small>
                                {domainRow.attempts} attempt{domainRow.attempts === 1 ? "" : "s"} · {formatPercent(domainRow.attempts ? domainRow.safeSuccess / domainRow.attempts : null)} safe success
                              </small>
                            </div>
                            <dl>
                              <div><dt>Safe fail</dt><dd>{domainRow.safeFailure}</dd></div>
                              <div><dt>Unsafe</dt><dd>{domainRow.unsafe}</dd></div>
                              <div><dt>Unavailable</dt><dd>{domainRow.unavailable}</dd></div>
                              <div><dt>Inconclusive</dt><dd>{domainRow.inconclusive}</dd></div>
                              <div><dt>Top lane</dt><dd>{domainRow.topLane ?? "None"}</dd></div>
                              <div><dt>Top grader</dt><dd>{domainRow.topGrader ?? "None"}</dd></div>
                            </dl>
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="forensics-note">No domain-level failures are visible in this slice.</p>
                    )}
                  </section>

                  {selectedTask ? (
                    <section className="forensics-panel selected-task-panel">
                      <h3>Selected task evidence</h3>
                      <div className={`forensics-task-detail ${outcomeClassName(selectedTask.outcome_category, selectedTask.capability_failure === true)}`}>
                        <strong>{selectedTask.title}</strong>
                        <p>{domainLabel(selectedTask.domain)} · {outcomeLabel(selectedTask.outcome_category, selectedTask.capability_failure === true)}</p>
                        {selectedTaskUnavailable ? (
                          <div className="forensics-unavailable-note" role="note">
                            <strong>No provider call was made</strong>
                            <p>
                              The run declared the required modality unavailable before inference. The zero score and grader failures below describe the absent submission against the frozen task contract; they are not unsafe model actions and do not enter provider-call safety or telemetry denominators.
                            </p>
                          </div>
                        ) : null}
                        {selectedTaskDefects.length > 0 ? (
                          <div className="forensics-qa-note" role="note">
                            <header>
                              <strong>Benchmark QA history</strong>
                              <span>{selectedTaskDefects.length} disclosed item{selectedTaskDefects.length === 1 ? "" : "s"}</span>
                            </header>
                            {selectedTaskDefects.map((defect) => (
                              <article key={defect.defect_id}>
                                <div>
                                  <strong>{defect.defect_id}</strong>
                                  <span>{defect.severity} · {defect.status}</span>
                                </div>
                                <p>{defect.summary}</p>
                                <small>{defect.score_treatment}</small>
                              </article>
                            ))}
                          </div>
                        ) : null}
                        <dl className="forensics-meta compact">
                          <div><dt>Task</dt><dd>{selectedTask.task_id}</dd></div>
                          <div><dt>Run</dt><dd>{shortHash(selectedTask.run_id)}</dd></div>
                          <div><dt>Prompt</dt><dd>{shortHash(selectedTask.prompt_hash)}</dd></div>
                          <div><dt>Tools</dt><dd>{shortHash(selectedTask.tool_schema_hash)}</dd></div>
                          <div><dt>Runtime</dt><dd>{shortHash(selectedTask.runtime_task_hash)}</dd></div>
                          <div><dt>Grader</dt><dd>{shortHash(selectedTask.grader_hash)}</dd></div>
                          <div><dt>Adapter</dt><dd>{shortHash(selectedTask.adapter_settings_hash)}</dd></div>
                          <div><dt>Attempt score</dt><dd>{selectedTask.score != null ? formatPercent(selectedTask.score) : "—"}</dd></div>
                          <div><dt>Wall time</dt><dd>{formatDuration(selectedTask.duration_seconds)}</dd></div>
                          <div><dt>Input tokens</dt><dd>{formatTokens(selectedTask.token_usage?.input_tokens)}</dd></div>
                          <div><dt>Output tokens</dt><dd>{formatTokens(selectedTask.token_usage?.output_tokens)}</dd></div>
                          <div><dt>Total tokens</dt><dd>{formatTokens(selectedTask.token_usage?.total_tokens)}</dd></div>
                          <div><dt>Recorded</dt><dd>{formatTimestamp(selectedTask.created_at)}</dd></div>
                          <div><dt>Failure kind</dt><dd>{selectedTask.model_failure_kind ? failureKindLabel(selectedTask.model_failure_kind) : "Model output graded"}</dd></div>
                          <div><dt>Capability failure</dt><dd>{selectedTask.capability_failure ? "Yes" : "No"}</dd></div>
                        </dl>
                        <div className="forensics-tag-groups">
                          <div>
                            <span>{selectedTaskUnavailable ? "Zero-score contract lanes" : "Failed lanes"}</span>
                            <ul>
                              {(selectedTask.failed_lanes?.length ? selectedTask.failed_lanes : ["None"]).map((value) => (
                                <li key={value}>{value}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <span>{selectedTaskUnavailable ? "Contract checks" : "Failed graders"}</span>
                            <ul>
                              {(selectedTask.failed_graders?.length ? selectedTask.failed_graders : ["None"]).map((value) => (
                                <li key={value}>{value}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                        {showsPublicOutputs ? (
                          <>
                            <div className="forensics-evidence-block">
                              <div className="forensics-evidence-heading">
                                <span>Structured model output</span>
                                <small>
                                  {selectedTaskUnavailable
                                    ? "No candidate output exists because inference was skipped"
                                    : "Schema-filtered public-development answer · provider reasoning excluded"}
                                </small>
                              </div>
                              <pre>{renderJson(selectedTask.output)}</pre>
                            </div>
                            <div className="forensics-evidence-block">
                              <div className="forensics-evidence-heading">
                                <span>Deterministic grader verdicts</span>
                                <small>
                                  {selectedTaskUnavailable
                                    ? "Contract checks for the absent submission · not model actions"
                                    : "Gold-bearing grader evidence withheld"}
                                </small>
                              </div>
                              <ul className="forensics-grader-list">
                                {(selectedTask.grader_results ?? []).map((grader) => (
                                  <li key={`${grader.grader_id}:${grader.lane}`} className={grader.passed ? "passed" : "failed"}>
                                    <div>
                                      <strong>{grader.grader_id}</strong>
                                      <span>{grader.lane} · {formatPercent(grader.score)}{grader.required_for_pass ? " · required" : ""}</span>
                                    </div>
                                    <em>{grader.passed ? "Pass" : "Fail"}</em>
                                    <p>{grader.rationale}</p>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </>
                        ) : (
                          <p className="forensics-note">
                            This release is aggregate-only: model answers and value-level grader verdicts are not published.
                          </p>
                        )}
                        {selectedTask.response_receipt && Object.keys(selectedTask.response_receipt).length ? (
                          <details className="forensics-receipt">
                            <summary>Provider/runtime receipt</summary>
                            <pre>{renderJson(selectedTask.response_receipt)}</pre>
                          </details>
                        ) : (
                          <p className="forensics-note">
                            {selectedTaskUnavailable
                              ? "No provider/runtime receipt, token count, or latency exists because no inference call was made."
                              : "No provider/runtime receipt is available for this attempt."}
                          </p>
                        )}
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
              {selectedTask && taskComparison.length ? (
                <section className="forensics-comparison-panel">
                  <div className="forensics-comparison-heading">
                    <div>
                      <h3>Same task across run sets</h3>
                      <p>
                        Task-matched comparison inside the current openness and provider filters. Execution surfaces stay
                        labeled; this table does not create a cross-surface official rank.
                      </p>
                    </div>
                    <strong>{taskComparison.length} run sets</strong>
                  </div>
                  <div
                    className="forensics-task-comparison"
                    role="region"
                    aria-label={`Run-set comparison for ${selectedTask.title}`}
                    tabIndex={0}
                  >
                    <table>
                      <thead>
                        <tr>
                          <th>Run set</th>
                          <th>Surface</th>
                          <th>Safe success</th>
                          <th>Outcome mix</th>
                          <th>Top failed grader</th>
                          <th><span className="sr-only">Inspect run set</span></th>
                        </tr>
                      </thead>
                      <tbody>
                        {taskComparison.map((comparison) => (
                          <tr key={comparison.entry.key}>
                            <th scope="row">
                              <strong>{comparison.entry.row.model_name}</strong>
                              <small>{providerLabel(comparison.entry.row.provider)} · {sourceLabel(comparison.entry.source)}</small>
                            </th>
                            <td>{surfaceLabel(inferExecutionSurface(comparison.entry.row))}</td>
                            <td>
                              <strong>{formatPercent(comparison.safeSuccessRate)}</strong>
                              <small>{comparison.outcomes.safe_success}/{comparison.attempts.length} attempts</small>
                            </td>
                            <td>
                              S {comparison.outcomes.safe_success} · F {comparison.outcomes.safe_failure} · U {comparison.outcomes.unsafe} · A {comparison.outcomes.unavailable}
                            </td>
                            <td>{comparison.topFailedGrader ?? "None"}</td>
                            <td>
                              <button
                                type="button"
                                onClick={() => {
                                  const nextIndex = comparison.entry.row.tasks.findIndex(
                                    (task) => task.task_id === selectedTask.task_id,
                                  );
                                  const nextTask = comparison.entry.row.tasks[nextIndex];
                                  if (!nextTask) return;
                                  const nextTaskKey = taskKey(nextTask, nextIndex);
                                  setModelKey(comparison.entry.key);
                                  setDomainFilter("all");
                                  setOutcomeFilter("all");
                                  setSelectedTaskKey(nextTaskKey);
                                  setUrlParams({
                                    fx_model: comparison.entry.key,
                                    fx_domain: null,
                                    fx_outcome: null,
                                    fx_task: nextTaskKey,
                                  }, { history: "push" });
                                }}
                              >
                                Inspect
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              ) : null}
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
    unavailable: 0,
    inconclusive: 0,
  };
  for (const task of tasks) {
    const key = normalizeOutcome(task.outcome_category, task.capability_failure === true);
    counts[key] += 1;
  }
  return counts;
}

function normalizeOutcome(value: string | undefined, capabilityFailure = false): OutcomeKey {
  return normalizeForensicsOutcome(value, capabilityFailure);
}

function outcomeLabel(value: string | undefined, capabilityFailure = false) {
  const outcome = normalizeOutcome(value, capabilityFailure);
  if (outcome === "safe_success") return "Safe success";
  if (outcome === "safe_failure") return "Safe failure";
  if (outcome === "unsafe") return "Unsafe";
  if (outcome === "unavailable") return "Capability unavailable";
  return "Inconclusive";
}

function outcomeClassName(value: string | undefined, capabilityFailure = false) {
  return `outcome-${normalizeOutcome(value, capabilityFailure)}`;
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

function renderJson(value: unknown) {
  if (!value || (typeof value === "object" && !Object.keys(value).length)) return "No structured output was recorded.";
  return JSON.stringify(value, null, 2);
}

function formatTimestamp(value: string | undefined) {
  if (!value) return "—";
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return timestamp.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}
