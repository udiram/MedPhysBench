import { ChevronDown, Search } from "lucide-react";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import {
  domainLabel,
  formatCoverage,
  formatDuration,
  formatPercent,
  formatTokens,
  hasComparableTelemetry,
  normalizeModelDisplayName,
  primaryScoreInterval,
  primaryScoreIntervalLabel,
  providerLabel,
  secondaryScoreInterval,
} from "../lib/format";
import { isCommonHarnessRun, isNativeRun, surfaceKind } from "../lib/runSurface";
import { navigateToRunForensics } from "../lib/forensicsNavigation";
import { modelRunKey } from "../lib/modelRunKey";
import { scoreEvidenceAvailable, scoreEvidenceKind } from "../lib/resultEvidence";
import { getUrlParam, readEnumParam, setUrlParams } from "../lib/urlState";
import { classifyAttemptOutcome } from "../types";
import type {
  Leaderboard,
  FleetStatus,
  ModelCatalogEntry,
  ModelOpenness,
  ModelResult,
  ModelTaskResult,
  ReleaseView,
} from "../types";

type ViewMode = "score" | "tokens" | "time" | "reliability";
type SourceFilter = "all" | "open" | "closed" | "unknown";
type SurfaceFilter = "all" | "common" | "native";

type Props = {
  data: Leaderboard | null;
  fleetStatus: FleetStatus | null;
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
const PROVIDER_SWATCHES: Record<string, string> = {
  "codex-native": "#70b8c4",
  groq: "#89c596",
  ollama: "#d9a441",
};

export function EfficiencyExplorer({ data, fleetStatus, modelCatalog, releaseView }: Props) {
  const [mode, setMode] = useState<ViewMode>("score");
  const [rankedOnly, setRankedOnly] = useState(false);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [providerFilter, setProviderFilter] = useState("all");
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
  const allRows: ModelResult[] = useMemo(() => (data ? [...data.models, ...(data.unranked_models ?? [])] : []), [data]);
  const availableProviders = useMemo(
    () => [...new Set([
      ...allRows.map((row) => row.provider),
      ...modelCatalog.map((entry) => entry.provider),
    ])].sort((left, right) => left.localeCompare(right)),
    [allRows, modelCatalog],
  );

  const rows = useMemo(() => {
    if (!data) return [];
    const queryValue = deferredQuery.trim().toLowerCase();

    return allRows
      .map((row) => {
        const key = modelRunKey(row);
        const source = modelSource(row, catalogIndex);
        const surface = resolveSurface(row);
        return { key, row, source, surface };
      })
      .filter((entry) => {
        const matchesRanked = !rankedOnly || entry.row.ranking_eligible;
        const matchesSource = sourceFilter === "all" || entry.source === sourceFilter;
        const matchesProvider = providerFilter === "all" || entry.row.provider === providerFilter;
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

        return matchesRanked && matchesSource && matchesSurface && matchesQuery && matchesProvider;
      })
      .sort((left, right) =>
        right.row.safe_success_rate - left.row.safe_success_rate ||
        left.row.model_name.localeCompare(right.row.model_name),
      );
  }, [allRows, catalogIndex, deferredQuery, rankedOnly, sourceFilter, surfaceFilter, providerFilter]);

  useEffect(() => {
    if (!data) return;
    if (providerFilter === "all") return;
    if (!availableProviders.includes(providerFilter)) {
      setProviderFilter("all");
      setUrlParams({ eff_provider: null });
    }
  }, [availableProviders, data, providerFilter]);

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
    return resolveSurface(focusedModel);
  }, [focusedModel]);

  const filteredCommonCount = useMemo(() => rows.filter((entry) => entry.surface === "common").length, [rows]);
  const filteredNativeCount = useMemo(() => rows.filter((entry) => entry.surface === "native").length, [rows]);
  const openCount = useMemo(() => rows.filter((entry) => entry.source === "open").length, [rows]);
  const closedCount = useMemo(() => rows.filter((entry) => entry.source === "closed").length, [rows]);
  const providerLegend = useMemo(
    () =>
      availableProviders
        .filter((provider) => rows.some((entry) => entry.row.provider === provider))
        .map((provider) => ({
          provider,
          label: providerLabel(provider),
          color: providerColor(provider),
          count: rows.filter((entry) => entry.row.provider === provider).length,
        })),
    [availableProviders, rows],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const syncFromUrl = () => {
      setMode(readEnumParam("eff_mode", ["score", "tokens", "time", "reliability"] as const, "score"));
      setSourceFilter(readEnumParam("eff_source", ["all", "open", "closed", "unknown"] as const, "all"));
      setProviderFilter(getUrlParam("eff_provider") ?? "all");
      setSurfaceFilter(readEnumParam("eff_surface", ["all", "common", "native"] as const, "all"));
      setRankedOnly(getUrlParam("eff_ranked") === "1");
      setQuery(getUrlParam("eff_query") ?? "");
      setFocused(getUrlParam("eff_focus"));
    };
    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);
    return () => window.removeEventListener("popstate", syncFromUrl);
  }, []);

  useEffect(() => {
    if (data && focused && !rows.some((entry) => entry.key === focused)) {
      setFocused(null);
      setUrlParams({ eff_focus: null });
    }
  }, [data, focused, rows]);

  const selectRow = (key: string) => {
    setFocused(key);
    setUrlParams({ eff_focus: key }, { history: "push" });
  };

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
            ["score", "Score intervals"],
            ["tokens", "Tokens frontier"],
            ["time", "Time frontier"],
            ["reliability", "Reliability"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              onClick={() => {
                const nextMode = value as ViewMode;
                setMode(nextMode);
                setUrlParams({ eff_mode: nextMode === "score" ? null : nextMode }, { history: "push" });
              }}
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
            onChange={(event) => {
              const checked = event.target.checked;
              setRankedOnly(checked);
              setUrlParams({ eff_ranked: checked ? "1" : null }, { history: "push" });
            }}
          />
          <span aria-hidden="true" />
          Official group-ranked rows only
        </label>
      </div>

      <div className="explorer-controls efficiency-controls">
        <label className="field">
          <span>Openness</span>
          <span className="select-wrap">
            <select value={sourceFilter} onChange={(event) => {
              const value = event.target.value as SourceFilter;
              setSourceFilter(value);
              setUrlParams({ eff_source: value === "all" ? null : value }, { history: "push" });
            }}>
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
              const value = event.target.value;
              setProviderFilter(value);
              setUrlParams({ eff_provider: value === "all" ? null : value }, { history: "push" });
            }}>
              <option value="all">All providers</option>
              {availableProviders.map((value) => (
                  <option key={value} value={value}>
                    {providerLabel(value)}
                  </option>
                ))}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field">
          <span>Execution surface</span>
          <span className="select-wrap">
            <select value={surfaceFilter} onChange={(event) => {
              const value = event.target.value as SurfaceFilter;
              setSurfaceFilter(value);
              setUrlParams({ eff_surface: value === "all" ? null : value }, { history: "push" });
            }}>
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
              onChange={(event) => {
                const value = event.target.value;
                setQuery(value);
                setUrlParams({ eff_query: value || null });
              }}
              placeholder="Model, provider, or harness revision"
            />
          </span>
        </label>
        <label className="field">
          <span>Rows shown</span>
          <div className="model-count-mini" role="status" aria-live="polite">
            <strong>{rows.length}</strong> displayed · {filteredCommonCount} common, {filteredNativeCount} native
            {fleetStatus ? (
              <small>
                {fleetStatus.summary.evaluated_base_models}/{fleetStatus.summary.planned_base_models} frozen-panel base
                models evaluated · {fleetStatus.summary.planned_base_models - fleetStatus.summary.evaluated_base_models}{" "}
                awaiting common-harness evidence
              </small>
            ) : null}
          </div>
        </label>
      </div>

      <div className="efficiency-layout">
        <div
          className="chart-panel"
          role="region"
          aria-label={
            mode === "score"
              ? "Score interval chart"
              : mode === "reliability"
                ? "Reliability profile chart"
                : `Efficiency ${mode} chart`
          }
        >
          {mode === "score" ? (
            <ScoreIntervalPlot rows={rows} onFocus={setFocused} onSelect={selectRow} focused={focused} />
          ) : mode === "reliability" ? (
            <ReliabilityProfile rows={rows} onFocus={setFocused} />
          ) : (
            <EfficiencyScatter rows={rows} mode={mode} onFocus={setFocused} focused={focused} />
          )}
        </div>
        <aside className="chart-guide" aria-label="Chart reading guide">
          <h3>Reading guide</h3>
          <dl>
            <div>
              <dt><span className="guide-mark ranked" /> Official rank group</dt>
              <dd>Complete common-harness rows eligible for comparison inside one frozen contract.</dd>
            </div>
            <div>
              <dt><span className="guide-mark common-unranked" /> Common, unranked</dt>
              <dd>Same adapter class, but missing evidence or peer comparability prevents an official rank.</dd>
            </div>
            <div>
              <dt><span className="guide-mark native" /> Native/import surface</dt>
              <dd>Shown in the same view with a distinct execution context; it never inherits a common-harness rank.</dd>
            </div>
            <div>
              {mode === "score" ? (
                <>
                  <dt><span className="guide-line interval" /> 95% interval</dt>
                  <dd>The release-declared primary interval; family-cluster intervals are used when available.</dd>
                </>
              ) : mode === "reliability" ? (
                <>
                  <dt><span className="guide-line profile" /> Rate profile</dt>
                  <dd>Safe success, repeat agreement, schema validity, and safety retain separate denominators.</dd>
                </>
              ) : (
                <>
                  <dt><span className="guide-line" /> Pareto frontier</dt>
                  <dd>Built only from complete telemetry inside one frozen comparison group.</dd>
                </>
              )}
            </div>
            <div>
              <dt><span className="guide-missing" /> Measurement unavailable</dt>
              <dd>Missing score, token, or time evidence is labeled unavailable and never rendered as zero.</dd>
            </div>
          </dl>
          {providerLegend.length > 0 ? (
            <div className="chart-provider-list" aria-label="Providers in scope">
              {providerLegend.map((entry) => (
                <span key={entry.provider}>
                  <i style={{ background: entry.color }} aria-hidden="true" />
                  {entry.label} · {entry.count}
                </span>
              ))}
            </div>
          ) : null}
          <p className="focused-model">
            {openCount ? `Open-weight ${openCount}` : "Open-weight 0"}
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
        onSelect={selectRow}
        modelSourceMap={Object.fromEntries(rows.map((entry) => [entry.key, entry.source]))}
      />

      {focusedModel && (
        <RunDiagnosticsPanel
          model={focusedModel}
          source={focusedSource ?? "unknown"}
          surface={focusedSurface ?? "all"}
          onInspectAttempts={() => focusRunForensics(focusedModel)}
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
function resolveSurface(row: ModelResult): SurfaceFilter {
  if (isCommonHarnessRun(row)) return "common";
  if (isNativeRun(row) || surfaceKind(row) === "native") return "native";
  return "native";
}

function modelSource(row: ModelResult, catalogIndex: Record<string, ModelCatalogEntry>): ModelOpenness {
  return catalogIndex[`${row.provider}::${row.model_name}`]?.openness ?? "unknown";
}

function ScoreIntervalPlot({
  rows,
  onFocus,
  onSelect,
  focused,
}: {
  rows: ScopedRow[];
  onFocus: (value: string) => void;
  onSelect: (value: string) => void;
  focused: string | null;
}) {
  const ordered = [...rows].sort(
    (left, right) =>
      Number(scoreEvidenceAvailable(right.row)) - Number(scoreEvidenceAvailable(left.row)) ||
      right.row.safe_success_rate - left.row.safe_success_rate ||
      left.row.model_name.localeCompare(right.row.model_name),
  );

  if (ordered.length === 0) {
    return (
      <div className="chart-empty" role="status">
        <strong>No score rows match this slice</strong>
        <p>Change a provider, openness, execution-surface, or comparability filter to restore rows.</p>
      </div>
    );
  }

  const width = 920;
  const margin = { top: 42, right: 105, bottom: 48, left: 260 };
  const rowHeight = 34;
  const height = margin.top + margin.bottom + ordered.length * rowHeight;
  const x = (value: number) => margin.left + value * (width - margin.left - margin.right);
  const officialGroups = new Set(
    ordered
      .filter((entry) => entry.row.ranking_eligible)
      .map((entry) => entry.row.comparison_group ?? entry.row.rank_group ?? entry.row.harness_revision),
  ).size;

  return (
    <>
      <div className="chart-insight-head">
        <h3>Every visible system on one evidence scale</h3>
        <p>
          Point estimates and primary 95% intervals share one scale. Ordering across frozen comparison groups is
          descriptive; official ranks remain group-specific.
        </p>
      </div>
      <div className="chart-keyline">
        <span>Higher is better. Wider intervals mean less precise evidence.</span>
        <span>{ordered.length} rows · {officialGroups} official groups · {ordered.reduce((sum, entry) => sum + entry.row.attempt_count, 0)} attempts</span>
      </div>
      <svg
        className="score-interval-chart"
        viewBox={`0 0 ${width} ${height}`}
        aria-hidden="true"
        focusable="false"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line
              x1={x(tick)}
              x2={x(tick)}
              y1={margin.top - 10}
              y2={height - margin.bottom}
              className="chart-grid"
            />
            <text x={x(tick)} y={height - 15} textAnchor="middle" className="chart-axis-label">
              {Math.round(tick * 100)}%
            </text>
          </g>
        ))}
        {ordered.map((entry, index) => {
          const row = entry.row;
          const centerY = margin.top + index * rowHeight + rowHeight / 2;
          const scoreAvailable = scoreEvidenceAvailable(row);
          const interval = scoreAvailable ? safeSuccessInterval(row) : null;
          const color = providerColor(row.provider);
          const mark = row.ranking_eligible ? "ranked" : entry.surface === "common" ? "common-unranked" : "native";
          const label = shortModelName(row.model_name);
          return (
            <g
              key={entry.key}
              className={`score-interval-row ${mark}${focused === entry.key ? " active" : ""}`}
              onMouseEnter={() => onFocus(entry.key)}
              onClick={() => onSelect(entry.key)}
            >
              {focused === entry.key ? (
                <rect
                  x={8}
                  y={centerY - rowHeight / 2 + 2}
                  width={width - 16}
                  height={rowHeight - 4}
                  className="score-row-focus"
                />
              ) : null}
              <line x1={16} x2={width - 16} y1={centerY + rowHeight / 2} y2={centerY + rowHeight / 2} className="score-row-rule" />
              <text x={16} y={centerY - 2} className="score-model-label">
                {label}
              </text>
              <text x={16} y={centerY + 11} className="score-model-context">
                {providerLabel(row.provider)} · {entry.source === "open" ? "open weights" : entry.source === "closed" ? "closed" : "source unclassified"} · {comparisonGroupLabel(row)}
              </text>
              {scoreAvailable && interval ? (
                <>
                  <line x1={x(interval[0])} x2={x(interval[1])} y1={centerY} y2={centerY} className="score-ci" style={{ stroke: color }} />
                  <line x1={x(interval[0])} x2={x(interval[0])} y1={centerY - 5} y2={centerY + 5} className="score-ci" style={{ stroke: color }} />
                  <line x1={x(interval[1])} x2={x(interval[1])} y1={centerY - 5} y2={centerY + 5} className="score-ci" style={{ stroke: color }} />
                  {mark === "ranked" ? (
                    <circle cx={x(row.safe_success_rate)} cy={centerY} r={5.5} className="score-mark ranked" style={{ fill: color }} />
                  ) : mark === "common-unranked" ? (
                    <circle cx={x(row.safe_success_rate)} cy={centerY} r={5.5} className="score-mark common-unranked" style={{ stroke: color }} />
                  ) : (
                    <path
                      d={`M ${x(row.safe_success_rate)} ${centerY - 6} L ${x(row.safe_success_rate) + 6} ${centerY} L ${x(row.safe_success_rate)} ${centerY + 6} L ${x(row.safe_success_rate) - 6} ${centerY} Z`}
                      className="score-mark native"
                      style={{ stroke: color }}
                    />
                  )}
                </>
              ) : null}
              <text x={width - 16} y={centerY + 4} textAnchor="end" className="score-value-label">
                {scoreAvailable ? formatPercent(row.safe_success_rate) : "Evidence unavailable"}
              </text>
            </g>
          );
        })}
      </svg>
      <ol className="score-interval-mobile-list" aria-label="Safe task success interval rows">
        {ordered.map((entry) => {
          const row = entry.row;
          const scoreAvailable = scoreEvidenceAvailable(row);
          const interval = scoreAvailable ? safeSuccessInterval(row) : null;
          const label = shortModelName(row.model_name);
          const context = `${providerLabel(row.provider)} · ${comparisonGroupLabel(row)}`;
          const ariaLabel = scoreAvailable && interval
            ? `${label}, ${formatPercent(row.safe_success_rate)} safe success, interval ${formatPercent(interval[0])} to ${formatPercent(interval[1])}, ${context}`
            : `${label}, score evidence unavailable, ${context}`;
          return (
            <li key={entry.key}>
              <button
                type="button"
                aria-label={ariaLabel}
                aria-pressed={focused === entry.key}
                onFocus={() => onFocus(entry.key)}
                onClick={() => onSelect(entry.key)}
              >
                <span className="score-mobile-heading">
                  <strong>{label}</strong>
                  <b>{scoreAvailable ? formatPercent(row.safe_success_rate) : "Evidence unavailable"}</b>
                </span>
                <small>{context}</small>
                {scoreAvailable && interval ? (
                  <span className="score-mobile-track" aria-hidden="true">
                    <i style={{ left: `${interval[0] * 100}%`, width: `${(interval[1] - interval[0]) * 100}%` }} />
                    <b style={{ left: `${row.safe_success_rate * 100}%`, background: providerColor(row.provider) }} />
                  </span>
                ) : (
                  <span className="score-mobile-missing">Open the row to inspect the integrity failure.</span>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </>
  );
}

function EfficiencyScatter({
  rows,
  mode,
  onFocus,
  focused,
}: {
  rows: ScopedRow[];
  mode: "tokens" | "time";
  onFocus: (value: string) => void;
  focused: string | null;
}) {
  const available = rows.filter((entry) => xValue(entry.row, mode) !== null);
  const missing = rows.filter((entry) => xValue(entry.row, mode) === null);
  const partial = available.filter((entry) => !hasComparableTelemetry(entry.row, mode));

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
  const frontierKeys = new Set(
    frontiers.flatMap(({ rows: frontier }) => frontier.map((row) => modelRunKey(row))),
  );
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
        <p>Each whisker is the primary safe-success 95% interval. Labels are placed in a dedicated lane to reduce overlap.</p>
        <p>Only frontier rows and the focused row are labeled so provider-hosted variants stay legible.</p>
      </div>
      <div className="chart-keyline">
        <span>Higher is better (y). Lower is better (x).</span>
        <span>
          {missing.length} missing · {partial.length} partial row{partial.length === 1 ? "" : "s"} excluded from frontier
        </span>
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
          const pointColor = providerColor(row.provider);
          const highlight = frontierKeys.has(modelKey) || focused === modelKey;
          return (
            <g
              key={modelKey}
              role="img"
              tabIndex={0}
              aria-label={`${pointLabel}${metricLabel}; 95% interval ${intervalLabel}`}
              onMouseEnter={() => onFocus(modelKey)}
              onFocus={() => onFocus(modelKey)}
              className={`chart-point${hasComparableTelemetry(row, mode) ? "" : " partial-telemetry"}${focused === modelKey ? " active" : ""}`}
            >
              <line
                x1={px}
                x2={px}
                y1={y(safeBand[0])}
                y2={y(safeBand[1])}
                className="confidence-line"
                style={{ stroke: pointColor }}
              />
              <line
                x1={px - 4}
                x2={px + 4}
                y1={y(safeBand[0])}
                y2={y(safeBand[0])}
                className="confidence-line"
                style={{ stroke: pointColor }}
              />
              <line
                x1={px - 4}
                x2={px + 4}
                y1={y(safeBand[1])}
                y2={y(safeBand[1])}
                className="confidence-line"
                style={{ stroke: pointColor }}
              />
              {isCommonHarnessRun(row) ? (
                <circle cx={px} cy={py} r={6} className="ranked-point" style={{ fill: pointColor }} />
              ) : (
                <path
                  d={`M ${px} ${py - 7} L ${px + 7} ${py} L ${px} ${py + 7} L ${px - 7} ${py} Z`}
                  className="native-point"
                  style={{ fill: pointColor, stroke: pointColor }}
                />
              )}
              {highlight ? (
                <>
                  <path
                    d={`M ${px + 8} ${py} L ${labelX - 10} ${labelY}`}
                    className={isCommonHarnessRun(row) ? "label-connector" : "label-connector native"}
                    style={{ stroke: pointColor }}
                  />
                  <text x={labelX} y={labelY + 4} textAnchor="start" className="chart-model-label">
                    {shortModelName(row.model_name)}
                  </text>
                </>
              ) : null}
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
      {partial.length > 0 && (
        <div className="telemetry-missing telemetry-partial">
          <strong>Partial telemetry · plotted, excluded from Pareto frontier</strong>
          {partial.map((entry) => (
            <button
              key={entry.key}
              onFocus={() => onFocus(entry.key)}
              onMouseEnter={() => onFocus(entry.key)}
            >
              {shortModelName(entry.row.model_name)} · {telemetryCoverageLabel(entry.row, mode)}
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
      {[...rows].sort((left, right) =>
        Number(scoreEvidenceAvailable(right.row)) - Number(scoreEvidenceAvailable(left.row)) ||
        right.row.safe_success_rate - left.row.safe_success_rate,
      ).map((entry) => {
        const row = entry.row;
        const scoreAvailable = scoreEvidenceAvailable(row);
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
              <small>{isCommonHarnessRun(row) ? "common" : "native"}</small>
            </span>
            <ReliabilityCell value={scoreAvailable ? row.safe_success_rate : null} />
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
  onSelect,
  modelSourceMap,
}: {
  rows: ScopedRow[];
  focused: string | null;
  onFocus: (value: string) => void;
  onSelect: (value: string) => void;
  modelSourceMap: Record<string, ModelOpenness>;
}) {
  return (
    <div className="efficiency-table-wrap" role="region" aria-label="Efficiency evidence table" tabIndex={0}>
      <table className="efficiency-table">
        <caption>Efficiency evidence by execution surface</caption>
        <thead>
          <tr>
            <th>Model</th>
            <th>Provider</th>
            <th>Score</th>
            <th>95% CI</th>
            <th>Input tokens</th>
            <th>Output tokens</th>
            <th>Median time</th>
            <th>Telemetry coverage</th>
            <th>Attempts</th>
            <th>Status</th>
            <th>Surface</th>
            <th>Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((entry) => {
            const row = entry.row;
            const source = modelSourceMap[entry.key] ?? entry.source;
            const scoreAvailable = scoreEvidenceAvailable(row);
            return (
              <tr key={entry.key} className={focused === entry.key ? "focused" : undefined} onMouseEnter={() => onFocus(entry.key)}>
                <td>
                  <button
                    type="button"
                    onFocus={() => onFocus(entry.key)}
                    onClick={() => onSelect(entry.key)}
                  >
                    {shortModelName(row.model_name)}
                  </button>
                </td>
                <td>{providerLabel(row.provider)}</td>
                <td>{scoreAvailable ? formatPercent(row.safe_success_rate) : "Evidence unavailable"}</td>
                <td>
                  {scoreAvailable ? (
                    <>
                      {formatPercent(safeSuccessInterval(row)[0])}–{formatPercent(safeSuccessInterval(row)[1])}
                      <small>{primaryScoreIntervalLabel(row)}</small>
                      {secondaryScoreInterval(row) ? (
                        <small>
                          Wilson {formatPercent(secondaryScoreInterval(row)?.[0])}–
                          {formatPercent(secondaryScoreInterval(row)?.[1])}
                        </small>
                      ) : null}
                    </>
                  ) : (
                    <small>Integrity checks prevent a performance interval.</small>
                  )}
                </td>
                <td>{formatTokens(row.token_usage?.median_input_tokens)}</td>
                <td>{formatTokens(row.token_usage?.median_output_tokens)}</td>
                <td>{formatDuration(row.median_duration_seconds)}</td>
                <td>
                  <span>Tokens: {formatCoverage(row.token_usage?.observed_attempts, row.token_usage?.expected_attempts)}</span>
                  <small>Time: {formatCoverage(row.duration_telemetry?.observed_attempts, row.duration_telemetry?.expected_attempts)}</small>
                </td>
                <td>{row.completed_count}/{row.expected_attempt_count}</td>
                <td>{rowEvidenceStatus(row)}</td>
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
  onInspectAttempts,
}: {
  model: ModelResult;
  source: ModelOpenness;
  surface: SurfaceFilter;
  onInspectAttempts: () => void;
}) {
  const tasks = model.tasks ?? [];
  const safePasses = tasks.filter((task) => taskClassForOutcome(task) === "safe-pass").length;
  const safeFails = tasks.filter((task) => taskClassForOutcome(task) === "safe-fail").length;
  const unavailable = tasks.filter((task) => taskClassForOutcome(task) === "unavailable").length;
  const unsafe = tasks.filter((task) => taskClassForOutcome(task) === "unsafe").length;
  const unknown = tasks.filter((task) => taskClassForOutcome(task) === "unknown").length;
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
        <div className="section-actions">
          <button type="button" onClick={onInspectAttempts}>
            Inspect attempts and graders
          </button>
          <button
            type="button"
            onClick={() => downloadTaskLedger(model, "csv")}
          >
            Export task ledger (CSV)
          </button>
          <button
            type="button"
            onClick={() => downloadTaskLedger(model, "json")}
          >
            Export task ledger (JSON)
          </button>
        </div>
      </div>
      <div className="detail-grid">
        <section>
          <h4>Result mix</h4>
          <dl className="metric-list">
            <div><dt>Safe passes</dt><dd>{safePasses}</dd></div>
            <div><dt>Safe fails</dt><dd>{safeFails}</dd></div>
            <div><dt>Unsafe outcomes</dt><dd>{unsafe}</dd></div>
            <div><dt>Capability unavailable</dt><dd>{unavailable}</dd></div>
            <div><dt>Outcome missing</dt><dd>{unknown}</dd></div>
            <div><dt>Attempts</dt><dd>{model.attempt_count}</dd></div>
            <div><dt>Expected attempts</dt><dd>{model.expected_attempt_count ?? model.attempt_count}</dd></div>
          </dl>
        </section>
        <section className="detail-span">
          <h4>Failure lenses</h4>
          <dl className="metric-list">
            <div><dt>Right/wrong</dt><dd>{safePasses} passed · {safeFails + unsafe} failed · {unavailable} unavailable</dd></div>
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

function focusRunForensics(model: ModelResult) {
  navigateToRunForensics(model);
}

function downloadTaskLedger(model: ModelResult, format: "csv" | "json") {
  const safeName = `${model.model_name.replaceAll(" ", "_").replaceAll("[", "-").replaceAll("]", "")}-${model.provider}`;
  const filename = `${safeName}-task-ledger.${format}`;

  if (format === "json") {
    const payload = {
      model: model.model_name,
      provider: model.provider,
      safe_success_rate: model.safe_success_rate,
      task_success_rate: model.task_success_rate,
      tasks: model.tasks,
    };
    triggerDownload(filename, JSON.stringify(payload, null, 2), "application/json;charset=utf-8");
    return;
  }

  const header = [
    "task_id",
    "title",
    "domain",
    "track",
    "attempt_index",
    "passed",
    "safe",
    "outcome",
    "run_id",
    "prompt_hash",
    "tool_schema_hash",
    "runtime_task_hash",
    "scoring_revision",
    "failed_lanes",
    "failed_graders",
  ];

  const rows = model.tasks.map((task) => {
    const outcome = taskClassForOutcome(task);
    return [
      task.task_id,
      task.title,
      task.domain,
      task.track,
      task.attempt_index ?? "",
      task.passed == null ? "unknown" : task.passed ? "passed" : "failed",
      task.safe ? "safe" : "unsafe",
      outcome,
      task.run_id ?? "",
      task.prompt_hash ?? "",
      task.tool_schema_hash ?? "",
      task.runtime_task_hash ?? "",
      task.scoring_revision ?? "",
      (task.failed_lanes ?? []).join("|"),
      (task.failed_graders ?? []).join("|"),
    ];
  });
  const csv = [header, ...rows]
    .map((row) =>
      row
        .map((value) => `"${String(value).replaceAll('"', '""')}"`)
        .join(","),
    )
    .join("\n");
  triggerDownload(filename, csv, "text/csv;charset=utf-8");
}

function triggerDownload(filename: string, text: string, mimeType: string) {
  const blob = new Blob([text], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
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
  return classifyAttemptOutcome(task);
}

function sourceLabel(value: ModelOpenness) {
  if (value === "open") return "Open";
  if (value === "closed") return "Closed";
  return "Unknown";
}

function rankExclusionLabel(value: string) {
  if (value === "unranked_noncommon_surface") return "Native/import surface";
  if (value === "unranked_singleton_comparison_group") return "No peer with identical frozen harness contract";
  return value.replace(/^unranked_/, "").replaceAll("_", " ");
}

function safeSuccessInterval(row: ModelResult): [number, number] {
  return primaryScoreInterval(row);
}

function comparisonGroupLabel(row: ModelResult) {
  if (isNativeRun(row)) return "native/import";
  if (row.harness_revision === "reference-json-v1") return "local JSON v1";
  if (row.harness_revision === "reference-json-v2") return "local JSON v2";
  if (row.harness_revision?.includes("openai-chat-json-v1")) return "hosted JSON v1";
  return row.comparison_group ? "frozen comparison group" : "no comparison group";
}

function rowEvidenceStatus(row: ModelResult) {
  const kind = scoreEvidenceKind(row, isNativeRun(row));
  if (kind === "incomplete") return "Evidence incomplete";
  if (kind === "official") return `Official · ${comparisonGroupLabel(row)}`;
  if (kind === "native_descriptive") return "Native descriptive";
  return "Common harness · unranked";
}

function xValue(row: ModelResult, mode: "tokens" | "time") {
  const value = mode === "tokens" ? row.token_usage?.median_total_tokens : row.median_duration_seconds;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function paretoFrontiers(rows: ModelResult[], mode: "tokens" | "time") {
  const groups = new Map<string, ModelResult[]>();
  for (const row of rows.filter((candidate) => hasComparableTelemetry(candidate, mode))) {
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

function telemetryCoverageLabel(row: ModelResult, mode: "tokens" | "time") {
  const telemetry = mode === "tokens" ? row.token_usage : row.duration_telemetry;
  return formatCoverage(telemetry?.observed_attempts, telemetry?.expected_attempts);
}

function compactNumber(value: number) {
  if (!Number.isFinite(value)) return "—";
  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
  }
  return Math.round(value).toString();
}

function providerColor(provider: string) {
  return PROVIDER_SWATCHES[provider] ?? "#9aa0a7";
}

function shortModelName(value: string) {
  return normalizeModelDisplayName(value)
    .replace(/^hf\.co\/EnlistedGhost\/Pixtral-12B-2409-GGUF:Q4_K_M$/i, "Pixtral 12B Q4_K_M")
    .replace(/^openai\//i, "")
    .replace(/^llama-/i, "Llama ")
    .replace(/^llama(?=\d)/i, "Llama ")
    .replace(/^qwen\//i, "Qwen ")
    .replace(/^qwen(?=\d)/i, "Qwen ")
    .replace(/^gemma(?=\d)/i, "Gemma ")
    .replace(/^phi4(?=[:.-])/i, "Phi-4")
    .replace(/^mistral-nemo/i, "Mistral Nemo")
    .replace(/^deepseek-r1/i, "DeepSeek R1")
    .replace("[effort=", "(")
    .replace("]", ")");
}

function shortHash(value: string | undefined) {
  if (!value) return "—";
  return `${value.slice(0, 6)}…${value.slice(-6)}`;
}
