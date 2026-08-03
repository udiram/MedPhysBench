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
import {
  buildComparisonScopes,
  DEFAULT_CHART_ROW_LIMIT,
  DEFAULT_TABLE_ROW_LIMIT,
  limitEvidenceRows,
  runComparisonScopeKey,
} from "../lib/efficiencyScope";
import { modelRunKey } from "../lib/modelRunKey";
import { scoreEvidenceAvailable, scoreEvidenceKind } from "../lib/resultEvidence";
import { ScoreCertaintyFrontier } from "./ScoreCertaintyFrontier";
import { getUrlParam, readEnumParam, setUrlParams } from "../lib/urlState";
import { classifyAttemptOutcome } from "../types";
import type {
  AttemptOutcomeClass,
  Leaderboard,
  FleetStatus,
  ModelCatalogEntry,
  ModelOpenness,
  ModelResult,
  ModelTaskResult,
  ReleaseView,
} from "../types";

type ViewMode = "score" | "tokens" | "time" | "reliability" | "certainty";
type SourceFilter = "all" | "open" | "closed" | "unknown";
type SurfaceFilter = "all" | "common" | "native";
type SortDirection = "asc" | "desc";
type TableSort = "safe_success" | "model" | "provider" | "attempts" | "surface" | "source" | "status";

type TableScopeStats = {
  totalRows: number;
  commonRows: number;
  nativeRows: number;
  openRows: number;
  closedRows: number;
  unknownRows: number;
  totalAttempts: number;
  providerCounts: Record<string, number>;
  ranked: number;
  unranked: number;
  nativeStatus: number;
};

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
  const [comparisonFilter, setComparisonFilter] = useState("all");
  const [tableSort, setTableSort] = useState<TableSort>("safe_success");
  const [tableSortDirection, setTableSortDirection] = useState<SortDirection>("desc");
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

  const scopedRows = useMemo(() => {
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
        const matchesRanked = mode === "certainty" || !rankedOnly || entry.row.ranking_eligible;
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
  }, [allRows, catalogIndex, deferredQuery, mode, rankedOnly, sourceFilter, surfaceFilter, providerFilter]);

  const comparisonScopes = useMemo(
    () => buildComparisonScopes(scopedRows.map((entry) => entry.row)),
    [scopedRows],
  );

  const rows = useMemo(
    () =>
      comparisonFilter === "all"
        ? scopedRows
        : scopedRows.filter((entry) => runComparisonScopeKey(entry.row) === comparisonFilter),
    [comparisonFilter, scopedRows],
  );

  const tableRows = useMemo(
    () => [...rows].sort((left, right) => compareRowsForTableSort(left, right, tableSort, tableSortDirection)),
    [rows, tableSort, tableSortDirection],
  );

  const scopeStats = useMemo<TableScopeStats>(() => {
    const providerCounts: Record<string, number> = {};
    let commonRows = 0;
    let nativeRows = 0;
    let openRows = 0;
    let closedRows = 0;
    let unknownRows = 0;
    let totalAttempts = 0;
    let ranked = 0;
    let unranked = 0;
    let nativeStatus = 0;

    for (const entry of rows) {
      if (entry.surface === "common") {
        commonRows += 1;
      } else {
        nativeRows += 1;
        nativeStatus += 1;
      }
      providerCounts[entry.row.provider] = (providerCounts[entry.row.provider] ?? 0) + 1;
      if (entry.row.ranking_eligible) {
        ranked += 1;
      } else if (entry.surface === "common") {
        unranked += 1;
      }
      if (entry.source === "open") {
        openRows += 1;
      } else if (entry.source === "closed") {
        closedRows += 1;
      } else {
        unknownRows += 1;
      }
      totalAttempts += entry.row.attempt_count;
    }

    return {
      totalRows: rows.length,
      commonRows,
      nativeRows,
      openRows,
      closedRows,
      unknownRows,
      totalAttempts,
      providerCounts,
      ranked,
      unranked,
      nativeStatus,
    };
  }, [rows]);

  useEffect(() => {
    if (!data) return;
    if (providerFilter === "all") return;
    if (!availableProviders.includes(providerFilter)) {
      setProviderFilter("all");
      setUrlParams({ eff_provider: null });
    }
  }, [availableProviders, data, providerFilter]);

  useEffect(() => {
    if (comparisonFilter === "all") return;
    if (!comparisonScopes.some((scope) => scope.key === comparisonFilter)) {
      setComparisonFilter("all");
      setUrlParams({ eff_group: null });
    }
  }, [comparisonFilter, comparisonScopes]);

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

  const providerLegend = useMemo(
    () =>
      availableProviders
        .filter((provider) => provider in scopeStats.providerCounts)
        .map((provider) => ({
          provider,
          label: providerLabel(provider),
          color: providerColor(provider),
          count: scopeStats.providerCounts[provider] ?? 0,
        })),
    [availableProviders, scopeStats.providerCounts],
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const syncFromUrl = () => {
      const nextMode = readEnumParam("eff_mode", ["score", "tokens", "time", "reliability", "certainty"] as const, "score");
      setMode(nextMode);
      setSourceFilter(readEnumParam("eff_source", ["all", "open", "closed", "unknown"] as const, "all"));
      setProviderFilter(getUrlParam("eff_provider") ?? "all");
      setSurfaceFilter(readEnumParam("eff_surface", ["all", "common", "native"] as const, "all"));
      setComparisonFilter(getUrlParam("eff_group") ?? "all");
      setTableSort(readEnumParam("eff_sort", ["safe_success", "model", "provider", "attempts", "surface", "source", "status"] as const, "safe_success"));
      setTableSortDirection(readEnumParam("eff_sort_dir", ["asc", "desc"] as const, "desc"));
      setRankedOnly(nextMode === "certainty" ? false : getUrlParam("eff_ranked") === "1");
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

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handle = setTimeout(() => {
      const canonicalQuery = deferredQuery.trim();
      setUrlParams({ eff_query: canonicalQuery || null }, { history: "replace" });
    }, 180);
    return () => clearTimeout(handle);
  }, [deferredQuery]);

  const requestTableSort = (next: TableSort) => {
    const nextDirection = next === tableSort ? (tableSortDirection === "asc" ? "desc" : "asc") : "desc";
    setTableSort(next);
    setTableSortDirection(nextDirection);
    setUrlParams(
      {
        eff_sort: next === "safe_success" ? null : next,
        eff_sort_dir: nextDirection === "desc" ? null : nextDirection,
      },
      { history: "push" },
    );
  };

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
            ["certainty", "Score-certainty frontier"],
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
                if (nextMode === "certainty") setRankedOnly(false);
                setUrlParams(
                  {
                    eff_mode: nextMode === "score" ? null : nextMode,
                    eff_ranked: nextMode === "certainty" ? null : rankedOnly ? "1" : null,
                  },
                  { history: "push" },
                );
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
        {mode === "certainty" ? (
          <div className="model-count-mini">
            <strong>Official rows by default</strong>
            <small>Broader evidence requires the chart-level descriptive opt-in</small>
          </div>
        ) : (
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
        )}
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
        <label className="field">
          <span>Comparison contract</span>
          <span className="select-wrap">
            <select value={comparisonFilter} onChange={(event) => {
              const value = event.target.value;
              setComparisonFilter(value);
              setUrlParams({ eff_group: value === "all" ? null : value }, { history: "push" });
            }}>
              <option value="all">All contracts · descriptive view</option>
              {comparisonScopes.map((scope) => (
                <option key={scope.key} value={scope.key}>
                  {comparisonScopeLabel(scope.rows[0])} · {scope.rows.length} row{scope.rows.length === 1 ? "" : "s"}
                </option>
              ))}
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
              }}
              placeholder="Model, provider, or harness revision"
            />
          </span>
        </label>
        <label className="field">
          <span>Rows shown</span>
          <div className="model-count-mini" role="status" aria-live="polite">
            <strong>{scopeStats.totalRows}</strong> displayed · {scopeStats.commonRows} common, {scopeStats.nativeRows} native · {scopeStats.totalAttempts} attempts
            <small>
              {scopeStats.ranked} rankable · {scopeStats.unranked} common-harness unranked · {scopeStats.nativeStatus} native/import status
            </small>
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
              : mode === "certainty"
                ? "Score-certainty frontier chart"
              : mode === "reliability"
                ? "Reliability profile chart"
                : `Efficiency ${mode} chart`
          }
        >
          {mode === "score" ? (
            <ScoreIntervalPlot rows={rows} onFocus={setFocused} onSelect={selectRow} focused={focused} />
          ) : mode === "certainty" ? (
            <ScoreCertaintyFrontier rows={rows} onFocus={setFocused} onSelect={selectRow} focused={focused} />
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
              ) : mode === "certainty" ? (
                <>
                  <dt><span className="guide-line" /> Frontier path by median tokens or time</dt>
                  <dd>Default slice is official comparison-eligible common-harness rows; other rows are opt-in.</dd>
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
            {scopeStats.openRows ? `Open-weight ${scopeStats.openRows}` : "Open-weight 0"}
            {" / "}
            {scopeStats.closedRows ? `${scopeStats.closedRows} closed` : "0 closed"}
            {scopeStats.unknownRows ? ` (${scopeStats.unknownRows} unknown)` : ""}
            {" · "}
            {scopeStats.totalRows ? `${scopeStats.totalRows} rows in scope` : "No rows in scope"}
          </p>
        </aside>
      </div>

      <EfficiencyTable
        rows={tableRows}
        tableSort={tableSort}
        tableSortDirection={tableSortDirection}
        focused={focused}
        onFocus={setFocused}
        onSelect={selectRow}
        modelSourceMap={Object.fromEntries(rows.map((entry) => [entry.key, entry.source]))}
        onSort={requestTableSort}
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
  const [expanded, setExpanded] = useState(false);
  const ordered = [...rows].sort(
    (left, right) =>
      Number(scoreEvidenceAvailable(right.row)) - Number(scoreEvidenceAvailable(left.row)) ||
      right.row.safe_success_rate - left.row.safe_success_rate ||
      left.row.model_name.localeCompare(right.row.model_name),
  );
  const visibleRows = limitEvidenceRows(ordered, expanded, DEFAULT_CHART_ROW_LIMIT);

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
  const height = margin.top + margin.bottom + visibleRows.length * rowHeight;
  const x = (value: number) => margin.left + value * (width - margin.left - margin.right);
  const officialGroups = new Set(
    ordered
      .filter((entry) => entry.row.ranking_eligible)
      .map((entry) => entry.row.comparison_group ?? entry.row.rank_group ?? entry.row.harness_revision),
  ).size;

  return (
    <>
      <div className="chart-insight-head">
        <h3>Score intervals expose uncertainty before rank</h3>
        <p>
          Rows share a zero-to-one outcome scale, but official comparisons remain confined to identical frozen
          contracts. Use the comparison-contract filter for a valid head-to-head view.
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
        {visibleRows.map((entry, index) => {
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
        {visibleRows.map((entry) => {
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
      {ordered.length > DEFAULT_CHART_ROW_LIMIT ? (
        <button className="evidence-overflow-control" type="button" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Show the most relevant rows" : `Show all ${ordered.length} rows in the chart`}
        </button>
      ) : null}
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
        entry.key,
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
              key={`frontier-${frontier[0] ? modelRunKey(frontier[0]) : "empty"}`}
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
          const labelY = labelPositions.get(modelKey) ?? py;
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
  tableSort,
  tableSortDirection,
  focused,
  onFocus,
  onSelect,
  onSort,
  modelSourceMap,
}: {
  rows: ScopedRow[];
  tableSort: TableSort;
  tableSortDirection: SortDirection;
  focused: string | null;
  onFocus: (value: string) => void;
  onSelect: (value: string) => void;
  onSort: (next: TableSort) => void;
  modelSourceMap: Record<string, ModelOpenness>;
}) {
  const [expanded, setExpanded] = useState(false);
  const visibleRows = limitEvidenceRows(rows, expanded, DEFAULT_TABLE_ROW_LIMIT);
  const sortGlyph = tableSortDirection === "asc" ? "▴" : "▾";
  const ariaSort = (column: TableSort) =>
    tableSort === column ? (tableSortDirection === "asc" ? "ascending" : "descending") : "none";
  return (
    <div className="efficiency-table-block">
      <div className="efficiency-table-wrap" role="region" aria-label="Efficiency evidence table" tabIndex={0}>
        <table className="efficiency-table">
          <caption>Efficiency evidence by execution surface</caption>
        <thead>
          <tr>
            <th aria-sort={ariaSort("model")}>
              <button type="button" className="sort-button" onClick={() => onSort("model")}>
                Model {tableSort === "model" ? sortGlyph : ""}
              </button>
            </th>
            <th aria-sort={ariaSort("provider")}>
              <button type="button" className="sort-button" onClick={() => onSort("provider")}>
                Provider {tableSort === "provider" ? sortGlyph : ""}
              </button>
            </th>
            <th aria-sort={ariaSort("safe_success")}>
              <button type="button" className="sort-button" onClick={() => onSort("safe_success")}>
                Score {tableSort === "safe_success" ? sortGlyph : ""}
              </button>
            </th>
            <th>95% CI</th>
            <th aria-sort={ariaSort("attempts")}>
              <button type="button" className="sort-button" onClick={() => onSort("attempts")}>
                Attempts {tableSort === "attempts" ? sortGlyph : ""}
              </button>
            </th>
            <th>Input tokens</th>
            <th>Output tokens</th>
            <th>Median time</th>
            <th>Telemetry coverage</th>
            <th aria-sort={ariaSort("status")}>
              <button type="button" className="sort-button" onClick={() => onSort("status")}>
                Status {tableSort === "status" ? sortGlyph : ""}
              </button>
            </th>
            <th aria-sort={ariaSort("surface")}>
              <button type="button" className="sort-button" onClick={() => onSort("surface")}>
                Surface {tableSort === "surface" ? sortGlyph : ""}
              </button>
            </th>
            <th aria-sort={ariaSort("source")}>
              <button type="button" className="sort-button" onClick={() => onSort("source")}>
                Source {tableSort === "source" ? sortGlyph : ""}
              </button>
            </th>
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((entry) => {
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
                <td>{row.completed_count}/{row.expected_attempt_count}</td>
                <td>{formatTokens(row.token_usage?.median_input_tokens)}</td>
                <td>{formatTokens(row.token_usage?.median_output_tokens)}</td>
                <td>{formatDuration(row.median_duration_seconds)}</td>
                <td>
                  <span>Tokens: {formatCoverage(row.token_usage?.observed_attempts, row.token_usage?.expected_attempts)}</span>
                  <small>Time: {formatCoverage(row.duration_telemetry?.observed_attempts, row.duration_telemetry?.expected_attempts)}</small>
                </td>
                <td>{rowEvidenceStatus(row)}</td>
                <td>{entry.surface === "common" ? "Common harness" : "Native/import"}</td>
                <td>{sourceLabel(source)}</td>
              </tr>
            );
          })}
        </tbody>
        </table>
      </div>
      {rows.length > DEFAULT_TABLE_ROW_LIMIT ? (
        <button className="evidence-overflow-control" type="button" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Collapse evidence table" : `Show all ${rows.length} evidence rows`}
        </button>
      ) : null}
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
  const outcome = tasks.map(taskClassForOutcome);
  const outcomeCounts = tallyAttemptOutcomes(outcome);
  const safePasses = outcomeCounts["safe-pass"];
  const safeFails = outcomeCounts["safe-fail"];
  const unavailable = outcomeCounts.unavailable;
  const unsafe = outcomeCounts.unsafe;
  const unknown = outcomeCounts.unknown;
  const wrongCount = safeFails + unsafe;
  const rightPercent = tasks.length ? Math.round((safePasses / tasks.length) * 100) : 0;
  const wrongPercent = tasks.length ? Math.round((wrongCount / tasks.length) * 100) : 0;
  const unavailableCount = unavailable + unknown;
  const failedTasks = tasks.filter(
    (task) => (task.failed_lanes?.length ?? 0) > 0 || (task.failed_graders?.length ?? 0) > 0,
  );
  const lanes = taskFailureLanes(tasks.filter((task) => taskClassForOutcome(task) !== "safe-pass"));
  const topFailedDomains = taskDomainFailures(tasks);
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
            <div><dt>Right/wrong</dt><dd>{safePasses} passed ({rightPercent}%) · {wrongCount} failed ({wrongPercent}%) · {unavailableCount} unavailable</dd></div>
            <div><dt>Common failure lanes</dt><dd>{lanes.length > 0 ? lanes.map(([lane, count]) => `${lane}: ${count}`).join(", ") : "No lane failures"}</dd></div>
            <div>
              <dt>Contract errors</dt>
              <dd>{contractErrors.length}</dd>
            </div>
            <div><dt>Top failed domains</dt><dd>{topFailedDomains.length > 0 ? topFailedDomains[0]?.[0] : "None"} ({topFailedDomains.length ? topFailedDomains[0]?.[1] : "0"} failed tasks)</dd></div>
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
  const safeSegment = (value: string) => value.toLowerCase().replaceAll(/[^a-z0-9._-]+/g, "-").replaceAll(/^-+|-+$/g, "");
  const contract = model.run_profile?.run_configuration_hash
    ?? model.model_revision
    ?? model.comparison_group
    ?? "unversioned";
  const safeName = [model.model_name, model.provider, model.harness_revision ?? "recorded", contract]
    .map((value) => safeSegment(value))
    .join("-");
  const filename = `${safeName}-task-ledger.${format}`;

  if (format === "json") {
    const payload = {
      model: model.model_name,
      provider: model.provider,
      model_revision: model.model_revision,
      harness_name: model.harness_name,
      harness_revision: model.harness_revision,
      comparison_group: model.comparison_group,
      run_configuration_hash: model.run_profile?.run_configuration_hash,
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

function tallyAttemptOutcomes(outcomes: AttemptOutcomeClass[]): Record<AttemptOutcomeClass, number> {
  const counts: Record<AttemptOutcomeClass, number> = {
    "safe-pass": 0,
    "safe-fail": 0,
    unsafe: 0,
    unavailable: 0,
    unknown: 0,
  };
  for (const outcome of outcomes) counts[outcome] += 1;
  return counts;
}

function taskDomainFailures(tasks: ModelTaskResult[]) {
  const counts = new Map<string, number>();
  for (const task of tasks) {
    if (taskClassForOutcome(task) === "safe-pass") continue;
    const label = domainLabel(task.domain);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return [...counts.entries()].sort(
    (left, right) => right[1] - left[1] || left[0].localeCompare(right[0]),
  );
}

function compareRowsForTableSort(
  left: ScopedRow,
  right: ScopedRow,
  sortBy: TableSort,
  sortDirection: SortDirection,
) {
  const direction = sortDirection === "asc" ? 1 : -1;
  let leftKey = 0;
  let rightKey = 0;

  switch (sortBy) {
    case "model":
      return direction * left.row.model_name.localeCompare(right.row.model_name);
    case "provider":
      return direction * left.row.provider.localeCompare(right.row.provider);
    case "attempts":
      leftKey = left.row.attempt_count;
      rightKey = right.row.attempt_count;
      break;
    case "surface":
      leftKey = left.surface === "common" ? 1 : 0;
      rightKey = right.surface === "common" ? 1 : 0;
      break;
    case "source":
      leftKey = left.source === "open" ? 2 : left.source === "closed" ? 1 : 0;
      rightKey = right.source === "open" ? 2 : right.source === "closed" ? 1 : 0;
      break;
    case "status":
      leftKey = left.row.ranking_eligible ? 2 : left.surface === "common" ? 1 : 0;
      rightKey = right.row.ranking_eligible ? 2 : right.surface === "common" ? 1 : 0;
      break;
    case "safe_success":
    default:
      leftKey = left.row.safe_success_rate;
      rightKey = right.row.safe_success_rate;
      break;
  }

  if (leftKey === rightKey) {
    return direction * left.row.model_name.localeCompare(right.row.model_name);
  }
  return direction * (leftKey - rightKey);
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

function comparisonScopeLabel(row: ModelResult) {
  return `${comparisonGroupLabel(row)} · ${providerLabel(row.provider)}`;
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
