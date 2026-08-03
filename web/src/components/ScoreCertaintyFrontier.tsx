import { useMemo, useState } from "react";
import { formatDuration, formatPercent, formatTokens, primaryScoreInterval } from "../lib/format";
import { buildScoreCertaintyFrontierRows, certaintyRowLabel, type CertaintyMetric } from "../lib/scoreCertaintyFrontier";
import type { ModelResult } from "../types";

type SurfaceFilter = "all" | "common" | "native";
type ScopedRow = {
  key: string;
  row: ModelResult;
  surface: SurfaceFilter;
};

const PROVIDER_SWATCHES: Record<string, string> = {
  "codex-native": "#70b8c4",
  groq: "#89c596",
  ollama: "#d9a441",
};

const WIDTH = 920;
const HEIGHT = 430;
const MARGIN = { top: 42, right: 250, bottom: 68, left: 72 };

export function ScoreCertaintyFrontier({
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
  const [metric, setMetric] = useState<CertaintyMetric>("tokens");
  const [includeDescriptive, setIncludeDescriptive] = useState(false);

  const modelRows = useMemo(
    () => rows.map((entry) => entry.row),
    [rows],
  );

  const frontier = useMemo(
    () => buildScoreCertaintyFrontierRows(modelRows, metric, includeDescriptive),
    [modelRows, metric, includeDescriptive],
  );
  const { rows: frontierRows, completeRows, partialRows, missingRows, frontierGroups } = frontier;

  const plottedRows = [...completeRows, ...partialRows];
  const frontierKeys = useMemo(
    () => new Set(frontierGroups.flatMap((entry) => entry.rows.map((entryRow) => entryRow.key))),
    [frontierGroups],
  );

  const xValues = plottedRows.map((entry) => entry.value);
  const minValue = xValues.length ? Math.min(...xValues) : 0;
  const maxValue = xValues.length ? Math.max(...xValues) : 0;
  const pad = xValues.length && maxValue > minValue
    ? Math.max((maxValue - minValue) * 0.12, maxValue * 0.04, 0.1)
    : 0.5;
  const domain = {
    left: xValues.length ? Math.max(0, minValue - pad) : 0,
    right: xValues.length ? maxValue + pad : 1,
  };

  const x = (value: number) =>
    MARGIN.left + ((value - domain.left) / Math.max(domain.right - domain.left, 1)) * (WIDTH - MARGIN.left - MARGIN.right);
  const y = (value: number) => MARGIN.top + (1 - value) * (HEIGHT - MARGIN.top - MARGIN.bottom);

  const labelPositions = useMemo(
    () =>
      new Map(
        [...plottedRows]
          .sort((left, right) => right.row.safe_success_rate - left.row.safe_success_rate)
          .map((entry, index, sorted) => [
            entry.key,
            MARGIN.top + 14 + (index * ((HEIGHT - MARGIN.top - MARGIN.bottom - 28) / Math.max(sorted.length - 1, 1))),
          ]),
      ),
    [plottedRows],
  );
  const modelLabelCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const entry of plottedRows) {
      const label = shortModelName(entry.row.model_name);
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
    return counts;
  }, [plottedRows]);

  if (plottedRows.length === 0) {
    return (
      <div className="chart-empty" role="status">
        <strong>No rows with comparable {metric === "tokens" ? "token" : "time"} telemetry</strong>
        <p>
          {frontierRows.length} rows are present in this slice. Telemetry is missing or non-comparable for all of them.
        </p>
        <div className="telemetry-missing">
          <strong>Missing telemetry</strong>
          {frontierRows.map((entry) => (
            <button key={entry.key} onMouseEnter={() => onFocus(entry.key)} onFocus={() => onFocus(entry.key)}>
              {shortModelName(entry.row.model_name)}
            </button>
          ))}
        </div>
      </div>
    );
  }

  const metricLabel = metric === "tokens" ? "Median provider-reported tokens / attempt" : "Median measured wall time / attempt";
  const metricValueLabel = (value: number) =>
    metric === "tokens" ? formatTokens(value) : formatDuration(value);

  return (
    <>
      <div className="chart-insight-head">
        <h3>Score-certainty frontier</h3>
        <p>
          Primary CI whiskers show uncertainty in safe-success score while the frontier tracks score against cost or latency.
          Rows are grouped by frozen comparison group before frontier extraction.
        </p>
        <p>
          Official comparison rows are filled circles; outcome-only common rows are outlined circles.
          Native or native-descriptive rows are rendered as diamonds when enabled.
        </p>
        <label className="field">
          <span>X-axis</span>
          <span className="select-wrap">
            <select
              value={metric}
              onChange={(event) => setMetric(event.target.value as CertaintyMetric)}
            >
              <option value="tokens">Median tokens</option>
              <option value="time">Median wall time</option>
            </select>
          </span>
        </label>
        <label className="rank-toggle">
          <input
            type="checkbox"
            checked={includeDescriptive}
            onChange={(event) => setIncludeDescriptive(event.target.checked)}
          />
          <span aria-hidden="true" />
          Include outcome-only / native rows (descriptive mode)
        </label>
      </div>
      <div className="chart-keyline">
        <span>Higher score better; lower x better. {frontierRows.length} rows in slice.</span>
        <span>
          {missingRows.length} missing telemetry · {partialRows.length} partial
        </span>
      </div>
      <svg
        className="efficiency-chart"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-labelledby="score-certainty-frontier-title score-certainty-frontier-description"
      >
        <title id="score-certainty-frontier-title">
          Safe task success compared with {metricLabel.toLowerCase()} (same-release frontier)
        </title>
        <desc id="score-certainty-frontier-description">
          Points with partial telemetry are rendered in dimmed style. Primary safe-success score uncertainty is shown as whiskers.
        </desc>
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
          <g key={tick}>
            <line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={y(tick)} y2={y(tick)} className="chart-grid" />
            <text x={MARGIN.left - 12} y={y(tick) + 4} textAnchor="end" className="chart-axis-label">
              {Math.round(tick * 100)}%
            </text>
          </g>
        ))}
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const value = domain.left + (domain.right - domain.left) * fraction;
          return (
            <g key={fraction}>
              <line x1={x(value)} x2={x(value)} y1={MARGIN.top} y2={HEIGHT - MARGIN.bottom} className="chart-grid" />
              <text x={x(value)} y={HEIGHT - MARGIN.bottom + 26} textAnchor="middle" className="chart-axis-label">
                {metricLabel.includes("tokens") ? formatCompactNumber(value) : `${value.toFixed(value >= 10 ? 0 : 1)}s`}
              </text>
            </g>
          );
        })}
        {frontierGroups.map((group, index) => (
          group.rows.length > 1 ? (
            <polyline
              key={`frontier-${group.group}-${index}`}
              points={group.rows.map((entry) => `${x(entry.value)},${y(entry.row.safe_success_rate)}`).join(" ")}
              className="pareto-line"
            />
          ) : null
        ))}
        {plottedRows.map((entry, index) => {
          const row = entry.row;
          const cx = x(entry.value);
          const cy = y(row.safe_success_rate);
          const confidence = primaryScoreInterval(row);
          const color = providerColor(row.provider);
          const rowKey = entry.key;
          const modelLabel = shortModelName(row.model_name);
          const harnessSuffix = (modelLabelCounts.get(modelLabel) ?? 0) > 1
            ? ` · ${shortHarnessName(row.run_profile?.harness_revision ?? row.harness_revision)}`
            : "";
          const labelText = `${modelLabel}${harnessSuffix} · ${formatPercent(row.safe_success_rate)} safe success`;
          const tooltip = `${labelText}; ${certaintyRowLabel(entry.kind)}; x: ${metricValueLabel(entry.value)}; CI ${formatPercent(confidence[0])} to ${formatPercent(confidence[1])}`;
          const highlighted = frontierKeys.has(rowKey) || focused === rowKey;
          const labelY = labelPositions.get(rowKey) ?? cy;
          const labelX = WIDTH - MARGIN.right + 20;
          return (
            <g
              key={rowKey}
              className={`chart-point${entry.coverage === "partial" ? " partial-telemetry" : ""}${focused === rowKey ? " active" : ""}`}
              role="img"
              tabIndex={0}
              aria-label={tooltip}
              onMouseEnter={() => onFocus(rowKey)}
              onFocus={() => onFocus(rowKey)}
              onClick={() => onSelect(rowKey)}
            >
              <line
                x1={cx}
                x2={cx}
                y1={y(confidence[0])}
                y2={y(confidence[1])}
                className="confidence-line"
                style={{ stroke: color }}
              />
              <line x1={cx - 4} x2={cx + 4} y1={y(confidence[0])} y2={y(confidence[0])} className="confidence-line" style={{ stroke: color }} />
              <line x1={cx - 4} x2={cx + 4} y1={y(confidence[1])} y2={y(confidence[1])} className="confidence-line" style={{ stroke: color }} />
              {entry.kind === "native_descriptive" ? (
                <path
                  d={`M ${cx} ${cy - 7} L ${cx + 7} ${cy} L ${cx} ${cy + 7} L ${cx - 7} ${cy} Z`}
                  className="native-point"
                  style={{ fill: color, stroke: color }}
                />
              ) : (
                <circle
                  cx={cx}
                  cy={cy}
                  r={6}
                  className="ranked-point"
                  style={{ fill: entry.kind === "official" ? color : "transparent", stroke: color, strokeWidth: 2 }}
                />
              )}
              {highlighted ? (
                <>
                  <path
                    d={`M ${cx + 8} ${cy} L ${labelX - 12} ${labelY}`}
                    className={entry.kind === "native_descriptive" ? "label-connector native" : "label-connector"}
                  />
                  <text x={labelX} y={labelY + 4} textAnchor="start" className="chart-model-label">
                    {modelLabel}{harnessSuffix} · {shortEvidenceLabel(entry.kind)}
                  </text>
                </>
              ) : null}
              <title>{tooltip}</title>
            </g>
          );
        })}
        <text transform={`translate(18 ${HEIGHT / 2}) rotate(-90)`} textAnchor="middle" className="chart-title-label">
          Safe task success score
        </text>
        <text x={(WIDTH + MARGIN.left - MARGIN.right) / 2} y={HEIGHT - 13} textAnchor="middle" className="chart-title-label">
          {metricLabel}
        </text>
      </svg>
      {missingRows.length > 0 && (
        <div className="telemetry-missing">
          <strong>Missing telemetry</strong>
          {missingRows.map((entry) => (
            <button key={entry.key} onMouseEnter={() => onFocus(entry.key)} onFocus={() => onFocus(entry.key)}>
              {shortModelName(entry.row.model_name)}
            </button>
          ))}
        </div>
      )}
      {partialRows.length > 0 && (
        <div className="telemetry-missing telemetry-partial">
          <strong>Partial telemetry · shown on axis, excluded from frontier</strong>
          {partialRows.map((entry) => (
            <button key={entry.key} onMouseEnter={() => onFocus(entry.key)} onFocus={() => onFocus(entry.key)}>
              {shortModelName(entry.row.model_name)}
            </button>
          ))}
        </div>
      )}
    </>
  );
}

function formatCompactNumber(value: number) {
  if (!Number.isFinite(value)) return "—";
  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k`;
  }
  return `${Math.round(value)}`;
}

function shortModelName(value: string) {
  return value
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

function shortHarnessName(value: string | undefined) {
  if (!value) return "unknown harness";
  const reference = value.match(/^reference-json-v(\d+)/i);
  if (reference) return `JSON v${reference[1]}`;
  const hosted = value.match(/^openai-chat-json-v(\d+)/i);
  if (hosted) return `hosted JSON v${hosted[1]}`;
  return value.length > 18 ? `${value.slice(0, 17)}…` : value;
}

function shortEvidenceLabel(kind: "official" | "common_unranked" | "native_descriptive") {
  if (kind === "official") return "official";
  if (kind === "common_unranked") return "outcome-only";
  return "native descriptive";
}

function providerColor(provider: string) {
  return PROVIDER_SWATCHES[provider] ?? "#9aa0a7";
}
