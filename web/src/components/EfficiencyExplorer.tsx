import { ChevronDown, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import { domainLabel, formatDuration, formatPercent, formatTokens } from "../lib/format";
import type {
  Leaderboard,
  ModelCatalogEntry,
  ModelOpenness,
  ModelResult,
  ModelTaskResult,
  ReleaseView,
} from "../types";

type ViewMode = "tokens" | "time" | "reliability";
type SourceFilter = "all" | "open" | "closed" | "unknown";
type SurfaceFilter = "all" | "common" | "native";

type Props = {
  data: Leaderboard | null;
  modelCatalog: ModelCatalogEntry[];
  releaseView: ReleaseView;
};

type ScopedRow = {
  key: string;
  row: ModelResult;
  source: ModelOpenness;
  surface: SurfaceFilter;
};

const WIDTH = 920;
const HEIGHT = 430;
const MARGIN = { top: 32, right: 250, bottom: 68, left: 72 };

export function EfficiencyExplorer({ data, modelCatalog, releaseView }: Props) {
  const [mode, setMode] = useState<ViewMode>("tokens");
  const [rankedOnly, setRankedOnly] = useState(false);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [surfaceFilter, setSurfaceFilter] = useState<SurfaceFilter>("all");
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [focused, setFocused] = useState<string | null>(null);

  const catalogIndex = useMemo(
    () =>
      Object.fromEntries(
        modelCatalog.map((entry) => [`${entry.provider}::${entry.model_name}`, entry]),
      ) as Record<string, ModelCatalogEntry>,
    [modelCatalog],
  );

  const rows = useMemo(() => {
    if (!data) return [];
    const allRows: ModelResult[] = [...data.models, ...(data.unranked_models ?? [])];
    const queryValue = deferredQuery.trim().toLowerCase();

    return allRows
      .map((row) => {
        const key = modelRowKey(row);
        const source = modelSource(row, catalogIndex);
        const surface = rowSurface(row);
        return { key, row, source, surface };
      })
      .filter((entry) => {
        const matchesRanked = !rankedOnly || entry.row.ranking_eligible;
        const matchesSource = sourceFilter === "all" || entry.source === sourceFilter;
        const matchesSurface =
          surfaceFilter === "all" ||
          (surfaceFilter === "common" && entry.surface === "common") ||
          (surfaceFilter === "native" && entry.surface === "native");

        const normalized = queryValue;
        const matchesQuery =
          !normalized ||
          entry.row.model_name.toLowerCase().includes(normalized) ||
          entry.row.provider.toLowerCase().includes(normalized) ||
          (entry.row.execution_surface ?? "").toLowerCase().includes(normalized) ||
          (entry.row.run_profile?.harness_revision ?? "").toLowerCase().includes(normalized);

        return matchesRanked && matchesSource && matchesSurface && matchesQuery;
      })
      .sort((left, right) =>
        right.row.safe_success_rate - left.row.safe_success_rate ||
        left.row.model_name.localeCompare(right.row.model_name),
      );
  }, [catalogIndex, data, deferredQuery, rankedOnly, sourceFilter, surfaceFilter]);

  const focusedModel = useMemo(
    () => rows.find((entry) => entry.key === focused)?.row ?? null,
    [rows, focused],
  );

  const focusedSource = useMemo(() => {
    if (!focusedModel) return null;
    return modelSource(focusedModel, catalogIndex);
  }, [catalogIndex, focusedModel]);

  const focusedSurface = useMemo(() => {
    if (!focusedModel) return null;
    return rowSurface(focusedModel);
  }, [focusedModel]);

  const filteredCommonCount = useMemo(() => rows.filter((entry) => entry.surface === "common").length, [rows]);
  const filteredNativeCount = useMemo(() => rows.filter((entry) => entry.surface === "native").length, [rows]);
  const openCount = useMemo(() => rows.filter((entry) => entry.source === "open").length, [rows]);
  const closedCount = useMemo(() => rows.filter((entry) => entry.source === "closed").length, [rows]);

  return (
    <section className="efficiency-section" id="efficiency">
      <div className="section-heading">
        <h2>Performance, cost, reliability, and failure diagnostics</h2>
        <p>
          Use the same published rows for all model families. Surface filtering separates common harness from
          native-import runs without special handling for any model family.
        </p>
      </div>

      <div className="efficiency-toolbar">
        <div className="view-switch" role="group" aria-label="Efficiency chart view">
          {[
            ["tokens", "Tokens frontier"],
            ["time", "Time frontier"],
            ["reliability", "Reliability"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              onClick={() => setMode(value as ViewMode)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="release-context">
          <span>Release</span>
          <strong>{data?.release.release_id ?? fallbackRelease(releaseView)}</strong>
        </div>
        <label className="rank-toggle">
          <input
            type="checkbox"
            checked={rankedOnly}
            onChange={(event) => setRankedOnly(event.target.checked)}
          />
          <span aria-hidden="true" />
          Comparable runs only
        </label>
      </div>

      <div className="explorer-controls efficiency-controls">
        <label className="field">
          <span>Model source</span>
          <span className="select-wrap">
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as SourceFilter)}>
              <option value="all">Open + closed</option>
              <option value="open">Open-source</option>
              <option value="closed">Closed</option>
              <option value="unknown">Unclassified</option>
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field">
          <span>Execution surface</span>
          <span className="select-wrap">
            <select value={surfaceFilter} onChange={(event) => setSurfaceFilter(event.target.value as SurfaceFilter)}>
              <option value="all">All surfaces</option>
              <option value="common">Common harness</option>
              <option value="native">Native/imported</option>
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field search-field">
          <span>Search</span>
          <span className="search-wrap">
            <Search aria-hidden="true" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Model, provider, or harness revision"
            />
          </span>
        </label>
        <label className="field">
          <span>Rows shown</span>
          <div className="model-count-mini">
            <strong>{rows.length}</strong> displayed · {filteredCommonCount} common, {filteredNativeCount} native
          </div>
        </label>
      </div>

      <div className="efficiency-layout">
        <div
          className="chart-panel"
          role="region"
          aria-label={mode === "reliability" ? "Reliability profile chart" : `Efficiency ${mode} chart`}
          tabIndex={0}
        >
          {mode === "reliability" ? (
            <ReliabilityProfile rows={rows} onFocus={setFocused} />
          ) : (
            <EfficiencyScatter rows={rows} mode={mode} onFocus={setFocused} />
          )}
        </div>
        <aside className="chart-guide" aria-label="Chart reading guide">
          <h3>Reading guide</h3>
          <dl>
            <div>
              <dt><span className="guide-mark ranked" /> Common harness</dt>
              <dd>Comparable runs from frozen contracts and published release protocol.</dd>
            </div>
            <div>
              <dt><span className="guide-mark native" /> Native/import surface</dt>
              <dd>Visible for continuity with separate execution context; these points remain part of the evidence set.</dd>
            </div>
            <div>
              <dt><span className="guide-line" /> Pareto frontier</dt>
              <dd>No visible common-harness point should be both more expensive and less accurate.</dd>
            </div>
            <div>
              <dt><span className="guide-missing" /> Telemetry unavailable</dt>
              <dd>Missing telemetry rows are explicitly listed and never rendered as zero.</dd>
            </div>
          </dl>
          <p className="focused-model">
            {openCount ? `Open-source ${openCount}` : "Open-source 0"}
            {" / "}
            {closedCount ? `${closedCount} closed` : "0 closed"}
            {" · "}
            {rows.length ? `${rows.length} rows in scope` : "No rows in scope"}
          </p>
        </aside>
      </div>

      <EfficiencyTable
        rows={rows}
        focused={focused}
        onFocus={setFocused}
        modelSourceMap={Object.fromEntries(rows.map((entry) => [entry.key, entry.source]))}
      />

      {focusedModel && (
        <RunDiagnosticsPanel
          model={focusedModel}
          source={focusedSource ?? "unknown"}
          surface={focusedSurface ?? "all"}
        />
      )}

      <p className="efficiency-caveat">
        Token counts are provider-reported and tokenizer-dependent. Import-surface rows can use different latency semantics.
        Public-set ranks and outcome rows are comparable only within each published contract.
      </p>
    </section>
  );
}

function fallbackRelease(view: ReleaseView) {
  if (view === "core") return "public-core-v0.4";
  if (view === "imaging") return "public-imaging-pilot-v0.4";
  if (view === "tg263") return "public-tg263-pilot-v0.5";
  return "public-real-workflows-pilot-v0.6";
}

function isCommonRun(row: ModelResult) {
  if (row.execution_surface) {
    return row.execution_surface === "common_harness";
  }
  if (row.run_profile) {
    return Boolean(row.run_profile.is_common_harness);
  }
  return row.ranking_eligible;
}

function isNativeRun(row: ModelResult) {
  if (row.execution_surface) {
    return row.execution_surface !== "common_harness";
  }
  if (row.run_profile) {
    return Boolean(!row.run_profile.is_common_harness);
  }
  return !row.ranking_eligible;
}

function rowSurface(row: ModelResult): SurfaceFilter {
  if (isCommonRun(row)) return "common";
  if (isNativeRun(row)) return "native";
  return "native";
}

function modelRowKey(row: ModelResult) {
  return `${row.provider}::${row.model_name}::${row.execution_surface ?? row.run_profile?.harness_revision ?? "default"}`;
}

function modelSource(row: ModelResult, catalogIndex: Record<string, ModelCatalogEntry>): ModelOpenness {
  return catalogIndex[`${row.provider}::${row.model_name}`]?.openness ?? "unknown";
}

function EfficiencyScatter({
  rows,
  mode,
  onFocus,
}: {
  rows: ScopedRow[];
  mode: "tokens" | "time";
  onFocus: (value: string) => void;
}) {
  const available = rows.filter((entry) => xValue(entry.row, mode) !== null);
  const missing = rows.filter((entry) => xValue(entry.row, mode) === null);

  if (available.length === 0) {
    return (
      <div className="chart-empty" role="status">
        <strong>No comparable {mode === "tokens" ? "token" : "duration"} telemetry</strong>
        <p>
          This release contains {rows.length} native/imported or differently instrumented runs.
          Missing measurements are not plotted as zero.
        </p>
        <div className="telemetry-missing">
          {missing.map((entry) => (
            <button
              key={entry.key}
              onFocus={() => onFocus(entry.key)}
              onMouseEnter={() => onFocus(entry.key)}
            >
              {shortModelName(entry.row.model_name)}
            </button>
          ))}
        </div>
      </div>
    );
  }

  const xValues = available.map((entry) => xValue(entry.row, mode) as number);
  const min = xValues.length ? Math.min(...xValues) : 0;
  const max = Math.max(...xValues, 1);
  const padding = Math.max((max - min) * 0.12, max * 0.04, 0.1);
  const domain: [number, number] = [Math.max(0, min - padding), max + padding];
  const x = (value: number) =>
    MARGIN.left + ((value - domain[0]) / (domain[1] - domain[0])) * (WIDTH - MARGIN.left - MARGIN.right);
  const y = (value: number) => MARGIN.top + (1 - value) * (HEIGHT - MARGIN.top - MARGIN.bottom);
  const frontiers = paretoFrontiers(available.map((entry) => entry.row), mode);
  const labelPositions = new Map(
    [...available]
      .sort((left, right) => right.row.safe_success_rate - left.row.safe_success_rate)
      .map((entry, index, ordered) => [
        entry.row.model_name,
        MARGIN.top + 12 + index * ((HEIGHT - MARGIN.top - MARGIN.bottom - 24) / Math.max(ordered.length - 1, 1)),
      ]),
  );

  return (
    <>
      <div className="chart-insight-head">
        <h3>
          {mode === "tokens"
            ? "Quality and token use form a frontier"
            : "Fast responses are useful only when they remain correct"}
        </h3>
        <p>Each whisker is the safe-success 95% interval. Labels are placed in a dedicated lane to reduce overlap.</p>
      </div>
      <div className="chart-keyline">
        <span>Higher is better (y). Lower is better (x).</span>
        <span>{missing.length} row{missing.length === 1 ? "" : "s"} without comparable telemetry</span>
      </div>
      <svg
        className="efficiency-chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-labelledby="efficiency-chart-title efficiency-chart-description"
      >
        <title id="efficiency-chart-title">Safe task success compared with {mode === "tokens" ? "median tokens" : "median wall time"}</title>
        <desc id="efficiency-chart-description">Each point is a model run. Solid circles are common-harness rows; diamonds are native/import rows.</desc>

        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={y(tick)} y2={y(tick)} className="chart-grid" />
            <text x={MARGIN.left - 12} y={y(tick) + 4} textAnchor="end" className="chart-axis-label">
              {Math.round(tick * 100)}%
            </text>
          </g>
        ))}
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const value = domain[0] + (domain[1] - domain[0]) * fraction;
          return (
            <g key={fraction}>
              <line x1={x(value)} x2={x(value)} y1={MARGIN.top} y2={HEIGHT - MARGIN.bottom} className="chart-grid" />
              <text x={x(value)} y={HEIGHT - MARGIN.bottom + 26} textAnchor="middle" className="chart-axis-label">
                {mode === "tokens" ? compactNumber(value) : `${value.toFixed(value >= 10 ? 0 : 1)}s`}
              </text>
            </g>
          );
        })}

        {frontiers.map(({ rows: frontier }) =>
          frontier.length > 1 ? (
            <polyline
              key={`frontier-${frontier[0]?.model_name ?? "empty"}`}
              points={frontier
                .map((row) => `${x(xValue(row, mode) as number)},${y(row.safe_success_rate)}`)
                .join(" ")}
              className="pareto-line"
            />
          ) : null,
        )}

        {available.map((entry) => {
          const row = entry.row;
          const value = xValue(row, mode);
          if (value === null) return null;
          const modelKey = entry.key;
          const px = x(value);
          const py = y(row.safe_success_rate);
          const safeBand = safeSuccessInterval(row);
          const pointLabel = `${shortModelName(row.model_name)}: ${formatPercent(row.safe_success_rate)} safe success; `;
          const metricLabel = mode === "tokens" ? formatTokens(value) : formatDuration(value);
          const intervalLabel = `${formatPercent(safeBand[0])} to ${formatPercent(safeBand[1])}`;
          const labelY = labelPositions.get(row.model_name) ?? py;
          const labelX = WIDTH - MARGIN.right + 24;
          return (
            <g
              key={modelKey}
              role="img"
              tabIndex={0}
              aria-label={`${pointLabel}${metricLabel}; 95% interval ${intervalLabel}`}
              onMouseEnter={() => onFocus(modelKey)}
              onFocus={() => onFocus(modelKey)}
              className="chart-point"
            >
              <line
                x1={px}
                x2={px}
                y1={y(safeBand[0])}
                y2={y(safeBand[1])}
                className="confidence-line"
              />
              <line
                x1={px - 4}
                x2={px + 4}
                y1={y(safeBand[0])}
                y2={y(safeBand[0])}
                className="confidence-line"
              />
              <line
                x1={px - 4}
                x2={px + 4}
                y1={y(safeBand[1])}
                y2={y(safeBand[1])}
                className="confidence-line"
              />
              {isCommonRun(row) ? (
                <circle cx={px} cy={py} r={6} className="ranked-point" />
              ) : (
                <path
                  d={`M ${px} ${py - 7} L ${px + 7} ${py} L ${px} ${py + 7} L ${px - 7} ${py} Z`}
                  className="native-point"
                />
              )}
              <path
                d={`M ${px + 8} ${py} L ${labelX - 10} ${labelY}`}
                className={isCommonRun(row) ? "label-connector" : "label-connector native"}
              />
              <text x={labelX} y={labelY + 4} textAnchor="start" className="chart-model-label">
                {shortModelName(row.model_name)}
              </text>
            </g>
          );
        })}
        <text transform={`translate(18 ${HEIGHT / 2}) rotate(-90)`} textAnchor="middle" className="chart-title-label">
          Safe task success
        </text>
        <text
          x={(WIDTH + MARGIN.left - MARGIN.right) / 2}
          y={HEIGHT - 13}
          textAnchor="middle"
          className="chart-title-label"
        >
          {mode === "tokens" ? "Median provider-reported tokens / attempt" : "Median measured wall time / attempt"}
        </text>
      </svg>
      {missing.length > 0 && (
        <div className="telemetry-missing">
          <strong>Telemetry unavailable</strong>
          {missing.map((entry) => (
            <button
              key={entry.key}
              onFocus={() => onFocus(entry.key)}
              onMouseEnter={() => onFocus(entry.key)}
            >
              {shortModelName(entry.row.model_name)}
            </button>
          ))}
        </div>
      )}
    </>
  );
}

function ReliabilityProfile({
  rows,
  onFocus,
}: {
  rows: ScopedRow[];
  onFocus: (value: string) => void;
}) {
  return (
    <div className="reliability-profile" role="region" aria-label="Reliability evidence by model" tabIndex={0}>
      <div className="chart-insight-head">
        <h3>Consistency and governance context</h3>
        <p>Agreement, schema validity, and safety are shown for every row in scope.</p>
      </div>
      <div className="reliability-head">
        <span>Model</span>
        <span>Safe score</span>
        <span>All attempts agree</span>
        <span>Valid output</span>
        <span>Safety gate</span>
      </div>
      {[...rows].sort((left, right) => right.row.safe_success_rate - left.row.safe_success_rate).map((entry) => {
        const row = entry.row;
        return (
          <button
            type="button"
            key={entry.key}
            className="reliability-row"
            onClick={() => onFocus(entry.key)}
            onFocus={() => onFocus(entry.key)}
          >
            <span className="reliability-name">
              {shortModelName(row.model_name)}
              <small>{isCommonRun(row) ? "common" : "native"}</small>
            </span>
            <ReliabilityCell value={row.safe_success_rate} />
            <ReliabilityCell value={row.reliability?.all_attempts_agree_rate ?? null} />
            <ReliabilityCell value={row.valid_output_rate} />
            <ReliabilityCell value={row.safety_gate_rate} />
          </button>
        );
      })}
    </div>
  );
}

function ReliabilityCell({ value }: { value: number | null }) {
  return (
    <span className="reliability-cell">
      <i aria-hidden="true">
        <b style={{ width: `${(value ?? 0) * 100}%` }} />
      </i>
      <strong>{formatPercent(value)}</strong>
    </span>
  );
}

function EfficiencyTable({
  rows,
  focused,
  onFocus,
  modelSourceMap,
}: {
  rows: ScopedRow[];
  focused: string | null;
  onFocus: (value: string) => void;
  modelSourceMap: Record<string, ModelOpenness>;
}) {
  return (
    <div className="efficiency-table-wrap" role="region" aria-label="Efficiency evidence table" tabIndex={0}>
      <table className="efficiency-table">
        <caption>Efficiency evidence by execution surface</caption>
        <thead>
          <tr>
            <th>Model</th>
            <th>Score</th>
            <th>95% CI</th>
            <th>Input tokens</th>
            <th>Output tokens</th>
            <th>Median time</th>
            <th>Attempts</th>
            <th>Surface</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((entry) => {
            const row = entry.row;
            const source = modelSourceMap[entry.key] ?? entry.source;
            return (
              <tr key={entry.key} className={focused === entry.key ? "focused" : undefined} onMouseEnter={() => onFocus(entry.key)}>
                <td>
                  <button
                    type="button"
                    onFocus={() => onFocus(entry.key)}
                    onClick={() => onFocus(entry.key)}
                  >
                    {shortModelName(row.model_name)}
                  </button>
                </td>
                <td>{formatPercent(row.safe_success_rate)}</td>
                <td>{formatPercent(safeSuccessInterval(row)[0])}–{formatPercent(safeSuccessInterval(row)[1])}</td>
                <td>{formatTokens(row.token_usage?.median_input_tokens)}</td>
                <td>{formatTokens(row.token_usage?.median_output_tokens)}</td>
                <td>{formatDuration(row.median_duration_seconds)}</td>
                <td>{row.completed_count}/{row.expected_attempt_count}</td>
                <td>{entry.surface === "common" ? "Common harness" : "Native/import"}</td>
                <td>{sourceLabel(source)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RunDiagnosticsPanel({
  model,
  source,
  surface,
}: {
  model: ModelResult;
  source: ModelOpenness;
  surface: SurfaceFilter;
}) {
  const tasks = model.tasks ?? [];
  const safePasses = tasks.filter((task) => task.passed === true && task.safe === true).length;
  const safeFails = tasks.filter((task) => task.passed === false && task.safe === true).length;
  const unsafe = tasks.filter((task) => task.safe === false).length;
  const unknown = tasks.filter((task) => task.passed == null).length;
  const failedTasks = tasks.filter(
    (task) => (task.failed_lanes?.length ?? 0) > 0 || (task.failed_graders?.length ?? 0) > 0,
  );
  const lanes = taskFailureLanes(tasks);
  const integrityErrors = model.integrity?.integrity_errors ?? [];
  const rankExclusions = integrityErrors.filter((error) => error.startsWith("unranked_"));
  const contractErrors = integrityErrors.filter((error) => !error.startsWith("unranked_"));

  return (
    <section className="failure-diagnostics" aria-label={`Model diagnostics for ${model.model_name}`}>
      <div className="section-heading">
        <h3>Model-level diagnostics</h3>
        <p>
          {model.provider} · {shortModelName(model.model_name)} · {sourceLabel(source)} ·{" "}
          {surface === "common" ? "Common harness" : "Native/import"}
        </p>
      </div>
      <div className="detail-grid">
        <section>
          <h4>Result mix</h4>
          <dl className="metric-list">
            <div><dt>Safe passes</dt><dd>{safePasses}</dd></div>
            <div><dt>Safe fails</dt><dd>{safeFails}</dd></div>
            <div><dt>Unsafe outcomes</dt><dd>{unsafe}</dd></div>
            <div><dt>Outcome missing</dt><dd>{unknown}</dd></div>
            <div><dt>Attempts</dt><dd>{model.attempt_count}</dd></div>
            <div><dt>Expected attempts</dt><dd>{model.expected_attempt_count ?? model.attempt_count}</dd></div>
          </dl>
        </section>
        <section className="detail-span">
          <h4>Failure lenses</h4>
          <dl className="metric-list">
            <div><dt>Right/wrong</dt><dd>{safePasses} passed · {safeFails + unsafe} failed</dd></div>
            <div><dt>Common failure lanes</dt><dd>{lanes.length > 0 ? lanes.map(([lane, count]) => `${lane}: ${count}`).join(", ") : "No lane failures"}</dd></div>
            <div>
              <dt>Contract errors</dt>
              <dd>{contractErrors.length}</dd>
            </div>
            <div><dt>Rank exclusions</dt><dd>{rankExclusions.length ? rankExclusions.map(rankExclusionLabel).join(", ") : "None"}</dd></div>
            <div><dt>Observed attempts</dt><dd>{model.integrity?.observed_attempt_keys ?? "—"}</dd></div>
            <div><dt>Missing attempts</dt><dd>{model.integrity?.missing_attempt_keys ?? "—"}</dd></div>
          </dl>
        </section>
        <section>
          <h4>Top failed checks</h4>
          {failedTasks.length === 0 ? (
            <p className="integrity-clean">No failed checks are recorded for this run.</p>
          ) : (
            <ul className="integrity-list" aria-label="Failed checks">
              {failedTasks.map((task) => (
                <li key={`${task.task_id}-${task.attempt_index ?? 0}`}>
                  <strong>{task.title}</strong>: {task.failed_graders?.length ? task.failed_graders.join(", ") : "lane check"}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {tasks.length > 0 ? (
        <div className="run-task-list" role="list" aria-label="Task failure ledger">
          {tasks.slice(0, 12).map((task) => (
            <article
              key={`${task.task_id}-${task.attempt_index ?? 0}`}
              className={`run-task-row ${taskClassForOutcome(task)}`}
            >
              <header>
                <div>
                  <span>{task.title}</span>
                  <small>{domainLabel(task.domain)} · {task.track}</small>
                </div>
                <span className="task-outcome-chip">
                  {task.passed === true ? "Passed" : task.passed === false ? "Failed" : "Unknown"} ·{" "}
                  {task.safe ? "Safe" : "Unsafe"}
                </span>
              </header>
              <div className="run-task-meta">
                <span>Run: {shortHash(task.run_id)}</span>
                <span>Prompt hash: {shortHash(task.prompt_hash)}</span>
                <span>Tool schema: {shortHash(task.tool_schema_hash)}</span>
              </div>
              {task.failed_lanes && task.failed_lanes.length > 0 ? (
                <p><strong>Failure lanes:</strong> {task.failed_lanes.join(", ")}</p>
              ) : null}
              {task.failed_graders && task.failed_graders.length > 0 ? (
                <p><strong>Failed checks:</strong> {task.failed_graders.join(", ")}</p>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}

      {tasks.length > 12 ? (
        <p className="run-task-boundary">Showing first 12 tasks in this release row. Expand model payload for full per-task detail.</p>
      ) : null}
    </section>
  );
}

function taskFailureLanes(tasks: ModelTaskResult[]) {
  const counts = new Map<string, number>();
  for (const task of tasks) {
    for (const lane of task.failed_lanes ?? []) {
      counts.set(lane, (counts.get(lane) ?? 0) + 1);
    }
    for (const grader of task.failed_graders ?? []) {
      const graderKey = `grader:${grader}`;
      counts.set(graderKey, (counts.get(graderKey) ?? 0) + 1);
    }
  }
  return [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
}

function taskClassForOutcome(task: ModelTaskResult) {
  if (task.passed === true) return "safe-pass";
  if (task.safe === false) return "unsafe";
  if (task.passed === false) return "safe-fail";
  return "unknown";
}

function sourceLabel(value: ModelOpenness) {
  if (value === "open") return "Open";
  if (value === "closed") return "Closed";
  return "Unknown";
}

function rankExclusionLabel(value: string) {
  if (value === "unranked_noncommon_surface") return "Native/import surface";
  return value.replace(/^unranked_/, "").replaceAll("_", " ");
}

function safeSuccessInterval(row: ModelResult): [number, number] {
  return row.safe_success_ci95 ?? row.task_success_ci95;
}

function xValue(row: ModelResult, mode: "tokens" | "time") {
  const value = mode === "tokens" ? row.token_usage?.median_total_tokens : row.median_duration_seconds;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function paretoFrontiers(rows: ModelResult[], mode: "tokens" | "time") {
  const groups = new Map<string, ModelResult[]>();
  for (const row of rows) {
    const group = row.comparison_group ?? row.rank_group ?? `${row.provider}::${row.harness_name}::${row.harness_revision}`;
    groups.set(group, [...(groups.get(group) ?? []), row]);
  }

  return [...groups.entries()].map(([group, members]) => {
    const ordered = [...members].sort((a, b) => (xValue(a, mode) ?? Infinity) - (xValue(b, mode) ?? Infinity));
    const frontier: ModelResult[] = [];
    let best = -Infinity;
    for (const row of ordered) {
      if (row.safe_success_rate > best) {
        frontier.push(row);
        best = row.safe_success_rate;
      }
    }
    return { group, rows: frontier };
  });
}

function compactNumber(value: number) {
  if (!Number.isFinite(value)) return "—";
  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
  }
  return Math.round(value).toString();
}

function shortModelName(value: string) {
  return value
    .replace("gpt-5.6-sol", "GPT-5.6")
    .replace("openai/", "")
    .replace("llama-", "Llama ")
    .replace("qwen/", "Qwen ")
    .replace("[effort=", "(")
    .replace("]", ")");
}

function shortHash(value: string | undefined) {
  if (!value) return "—";
  return `${value.slice(0, 6)}…${value.slice(-6)}`;
}
