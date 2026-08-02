import { useMemo, useState } from "react";
import { formatDuration, formatPercent, formatTokens } from "../lib/format";
import type { Leaderboard, ModelResult, ReleaseView } from "../types";

type ViewMode = "tokens" | "time" | "reliability";
type Props = { data: Leaderboard | null; releaseView: ReleaseView };

const WIDTH = 920;
const HEIGHT = 430;
const MARGIN = { top: 32, right: 210, bottom: 68, left: 72 };

export function EfficiencyExplorer({ data, releaseView }: Props) {
  const [mode, setMode] = useState<ViewMode>("tokens");
  const [rankedOnly, setRankedOnly] = useState(false);
  const [focused, setFocused] = useState<string | null>(null);
  const rows = useMemo(() => {
    const combined = data ? [...data.models, ...(data.unranked_models ?? [])] : [];
    return rankedOnly ? combined.filter((model) => model.ranking_eligible) : combined;
  }, [data, rankedOnly]);

  return (
    <section className="efficiency-section" id="efficiency">
      <div className="section-heading">
        <h2>Performance, cost, and reliability</h2>
        <p>Frontier views pair the outcome metric with token and wall-time cost; the reliability view shows whether an average score survives repeated attempts.</p>
      </div>
      <div className="efficiency-toolbar">
        <div className="view-switch" role="group" aria-label="Efficiency chart view">
          {([
            ["tokens", "Tokens frontier"],
            ["time", "Time frontier"],
            ["reliability", "Reliability"],
          ] as const).map(([value, label]) => (
            <button key={value} type="button" aria-pressed={mode === value} onClick={() => setMode(value)}>{label}</button>
          ))}
        </div>
        <div className="release-context">
          <span>Release</span>
          <strong>{data?.release.release_id ?? fallbackRelease(releaseView)}</strong>
        </div>
        <label className="rank-toggle">
          <input type="checkbox" checked={rankedOnly} onChange={(event) => setRankedOnly(event.target.checked)} />
          <span aria-hidden="true" />
          Official only
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
            <ReliabilityProfile rows={rows} focused={focused} onFocus={setFocused} />
          ) : (
            <EfficiencyScatter rows={rows} mode={mode} focused={focused} onFocus={setFocused} />
          )}
        </div>
        <aside className="chart-guide" aria-label="Chart reading guide">
          <h3>Reading guide</h3>
          <dl>
            <div><dt><span className="guide-mark ranked" /> Official harness group</dt><dd>Ranks are calculated only within an identical provider, adapter, and release contract.</dd></div>
            <div><dt><span className="guide-mark native" /> Native outcome</dt><dd>Same frozen task release, different execution surface. Kept visible, but not assigned a cross-surface official rank.</dd></div>
            <div><dt><span className="guide-line" /> Pareto frontier</dt><dd>No official point on the line is both less efficient and less accurate.</dd></div>
            <div><dt><span className="guide-missing" /> Telemetry unavailable</dt><dd>Missing provider usage or native latency is shown as missing—never as zero.</dd></div>
          </dl>
          {focused && <p className="focused-model">Focused model: <strong>{shortModelName(focused)}</strong></p>}
        </aside>
      </div>
      <EfficiencyTable rows={rows} focused={focused} onFocus={setFocused} />
      <p className="efficiency-caveat">Token counts are provider-reported and tokenizer-specific. Imported native pilots do not expose comparable model latency or usage. Public-set ranks remain descriptive, not clinical validation.</p>
    </section>
  );
}

function fallbackRelease(view: ReleaseView) {
  if (view === "core") return "public-core-v0.4";
  if (view === "imaging") return "public-imaging-pilot-v0.4";
  if (view === "tg263") return "public-tg263-pilot-v0.5";
  return "public-real-workflows-pilot-v0.6";
}

function EfficiencyScatter({ rows, mode, focused, onFocus }: { rows: ModelResult[]; mode: "tokens" | "time"; focused: string | null; onFocus: (value: string) => void }) {
  const available = rows.filter((row) => xValue(row, mode) !== null);
  const missing = rows.filter((row) => xValue(row, mode) === null);
  if (available.length === 0) {
    return <div className="chart-empty" role="status">
      <strong>No comparable {mode === "tokens" ? "token" : "duration"} telemetry</strong>
      <p>This release contains {rows.length} native or differently instrumented run{rows.length === 1 ? "" : "s"}. Missing measurements are not plotted as zero.</p>
      <div className="telemetry-missing">{missing.map((row) => <button key={row.model_name} onFocus={() => onFocus(row.model_name)} onMouseEnter={() => onFocus(row.model_name)}>{shortModelName(row.model_name)}</button>)}</div>
    </div>;
  }
  const xValues = available.map((row) => xValue(row, mode) as number);
  const min = xValues.length ? Math.min(...xValues) : 0;
  const max = Math.max(...xValues, 1);
  const padding = Math.max((max - min) * 0.12, max * 0.04, 0.1);
  const domain: [number, number] = [Math.max(0, min - padding), max + padding];
  const x = (value: number) => MARGIN.left + ((value - domain[0]) / (domain[1] - domain[0])) * (WIDTH - MARGIN.left - MARGIN.right);
  const y = (value: number) => MARGIN.top + (1 - value) * (HEIGHT - MARGIN.top - MARGIN.bottom);
  const frontiers = paretoFrontiers(available.filter((row) => row.ranking_eligible), mode);
  const labelPositions = new Map(
    [...available]
      .sort((left, right) => right.safe_success_rate - left.safe_success_rate)
      .map((row, index, ordered) => [
        row.model_name,
        MARGIN.top + 12 + index * ((HEIGHT - MARGIN.top - MARGIN.bottom - 24) / Math.max(ordered.length - 1, 1)),
      ]),
  );

  return (
    <>
      <div className="chart-insight-head">
        <h3>{mode === "tokens" ? "Quality and token use form a frontier" : "Fast responses are useful only when they remain correct"}</h3>
        <p>Each whisker is the safe-success 95% interval; labels are placed in a dedicated lane to avoid overlap.</p>
      </div>
      <div className="chart-keyline"><span>Higher is better (y). Lower is better (x).</span><span>{missing.length} row{missing.length === 1 ? "" : "s"} without comparable telemetry</span></div>
      <svg className="efficiency-chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-labelledby="efficiency-chart-title efficiency-chart-description">
        <title id="efficiency-chart-title">Safe task success compared with {mode === "tokens" ? "median tokens" : "median wall time"}</title>
        <desc id="efficiency-chart-description">Each point is a model run. Solid circles are official harness-group rows; diamonds are complete native outcomes. Vertical lines show the safe-success confidence interval.</desc>
        {[0, .25, .5, .75, 1].map((tick) => <g key={tick}><line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={y(tick)} y2={y(tick)} className="chart-grid" /><text x={MARGIN.left - 12} y={y(tick) + 4} textAnchor="end" className="chart-axis-label">{Math.round(tick * 100)}%</text></g>)}
        {[0, .25, .5, .75, 1].map((fraction) => {
          const value = domain[0] + (domain[1] - domain[0]) * fraction;
          return <g key={fraction}><line x1={x(value)} x2={x(value)} y1={MARGIN.top} y2={HEIGHT - MARGIN.bottom} className="chart-grid" /><text x={x(value)} y={HEIGHT - MARGIN.bottom + 26} textAnchor="middle" className="chart-axis-label">{mode === "tokens" ? compactNumber(value) : `${value.toFixed(value >= 10 ? 0 : 1)}s`}</text></g>;
        })}
        {frontiers.map(({ group, rows: frontier }) => frontier.length > 1 && (
          <polyline key={group} points={frontier.map((row) => `${x(xValue(row, mode) as number)},${y(row.safe_success_rate)}`).join(" ")} className="pareto-line" />
        ))}
        {available.map((row) => {
          const px = x(xValue(row, mode) as number);
          const py = y(row.safe_success_rate);
          const active = focused === row.model_name;
          const labelY = labelPositions.get(row.model_name) ?? py;
          const labelX = WIDTH - MARGIN.right + 24;
          return <g
            key={row.model_name}
            role="img"
            tabIndex={0}
            aria-label={`${shortModelName(row.model_name)}: ${formatPercent(row.safe_success_rate)} safe success; ${mode === "tokens" ? formatTokens(xValue(row, mode)) : formatDuration(xValue(row, mode))}; 95% interval ${formatPercent(safeSuccessInterval(row)[0])} to ${formatPercent(safeSuccessInterval(row)[1])}`}
            onMouseEnter={() => onFocus(row.model_name)}
            onFocus={() => onFocus(row.model_name)}
            className={active ? "chart-point active" : "chart-point"}
          >
            <line x1={px} x2={px} y1={y(safeSuccessInterval(row)[0])} y2={y(safeSuccessInterval(row)[1])} className="confidence-line" />
            <line x1={px - 4} x2={px + 4} y1={y(safeSuccessInterval(row)[0])} y2={y(safeSuccessInterval(row)[0])} className="confidence-line" />
            <line x1={px - 4} x2={px + 4} y1={y(safeSuccessInterval(row)[1])} y2={y(safeSuccessInterval(row)[1])} className="confidence-line" />
            {row.ranking_eligible ? <circle cx={px} cy={py} r={active ? 8 : 6} className="ranked-point" /> : <path d={`M ${px} ${py - 7} L ${px + 7} ${py} L ${px} ${py + 7} L ${px - 7} ${py} Z`} className="native-point" />}
            <path d={`M ${px + 8} ${py} L ${labelX - 10} ${labelY}`} className={row.ranking_eligible ? "label-connector" : "label-connector native"} />
            <text x={labelX} y={labelY + 4} textAnchor="start" className="chart-model-label">{shortModelName(row.model_name)}</text>
          </g>;
        })}
        <text transform={`translate(18 ${HEIGHT / 2}) rotate(-90)`} textAnchor="middle" className="chart-title-label">Safe task success</text>
        <text x={(WIDTH + MARGIN.left - MARGIN.right) / 2} y={HEIGHT - 13} textAnchor="middle" className="chart-title-label">{mode === "tokens" ? "Median provider-reported tokens / attempt" : "Median measured wall time / attempt"}</text>
      </svg>
      {missing.length > 0 && <div className="telemetry-missing"><strong>Telemetry unavailable</strong>{missing.map((row) => <button key={row.model_name} onFocus={() => onFocus(row.model_name)} onMouseEnter={() => onFocus(row.model_name)}>{shortModelName(row.model_name)}</button>)}</div>}
    </>
  );
}

function ReliabilityProfile({ rows, focused, onFocus }: { rows: ModelResult[]; focused: string | null; onFocus: (value: string) => void }) {
  return <div className="reliability-profile" role="region" aria-label="Reliability evidence by model" tabIndex={0}>
    <div className="chart-insight-head"><h3>A high average is not the same as dependable repetition</h3><p>Agreement, schema validity, and safety remain visible beside the headline score.</p></div>
    <div className="reliability-head"><span>Model</span><span>Safe score</span><span>All attempts agree</span><span>Valid output</span><span>Safety gate</span></div>
    {[...rows].sort((left, right) => right.safe_success_rate - left.safe_success_rate).map((row) => (
      <button type="button" key={row.model_name} className={focused === row.model_name ? "reliability-row active" : "reliability-row"} onFocus={() => onFocus(row.model_name)} onMouseEnter={() => onFocus(row.model_name)}>
        <span className="reliability-name">{shortModelName(row.model_name)}<small>{row.ranking_eligible ? "official" : "native outcome"}</small></span>
        <ReliabilityCell value={row.safe_success_rate} />
        <ReliabilityCell value={row.reliability?.all_attempts_agree_rate ?? null} />
        <ReliabilityCell value={row.valid_output_rate} />
        <ReliabilityCell value={row.safety_gate_rate} />
      </button>
    ))}
  </div>;
}

function ReliabilityCell({ value }: { value: number | null }) {
  return <span className="reliability-cell"><i aria-hidden="true"><b style={{ width: `${(value ?? 0) * 100}%` }} /></i><strong>{formatPercent(value)}</strong></span>;
}

function EfficiencyTable({ rows, focused, onFocus }: { rows: ModelResult[]; focused: string | null; onFocus: (value: string) => void }) {
  return <div className="efficiency-table-wrap" role="region" aria-label="Efficiency evidence table" tabIndex={0}><table className="efficiency-table"><caption>Efficiency evidence by execution surface</caption><thead><tr><th>Model</th><th>Score</th><th>95% CI</th><th>Input tokens</th><th>Output tokens</th><th>Median time</th><th>Attempts</th><th>Harness status</th></tr></thead><tbody>{rows.map((row) => <tr key={row.model_name} className={focused === row.model_name ? "focused" : undefined} onMouseEnter={() => onFocus(row.model_name)}><td><button type="button" onFocus={() => onFocus(row.model_name)}>{shortModelName(row.model_name)}</button></td><td>{formatPercent(row.safe_success_rate)}</td><td>{formatPercent(safeSuccessInterval(row)[0])}–{formatPercent(safeSuccessInterval(row)[1])}</td><td>{formatTokens(row.token_usage?.median_input_tokens)}</td><td>{formatTokens(row.token_usage?.median_output_tokens)}</td><td>{formatDuration(row.median_duration_seconds)}</td><td>{row.completed_count}/{row.expected_attempt_count}</td><td>{row.ranking_eligible ? "Official harness group" : "Native outcome order"}</td></tr>)}</tbody></table></div>;
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
    for (const row of ordered) if (row.safe_success_rate > best) { frontier.push(row); best = row.safe_success_rate; }
    return { group, rows: frontier };
  });
}

function compactNumber(value: number) { return value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k` : Math.round(value).toString(); }
function shortModelName(value: string) { return value.replace("gpt-5.6-sol", "GPT-5.6").replace("qwen", "Qwen").replace("[effort=", "(").replace("]", ")"); }
