import { useMemo, useState } from "react";
import { formatDuration, formatPercent, formatTokens } from "../lib/format";
import type { Leaderboard, ModelResult, ReleaseView } from "../types";

type ViewMode = "tokens" | "time" | "profile";
type Props = { data: Leaderboard | null; releaseView: ReleaseView };

const WIDTH = 840;
const HEIGHT = 430;
const MARGIN = { top: 32, right: 32, bottom: 68, left: 72 };

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
        <h2>Telemetry detail</h2>
        <p>Use the deeper telemetry view to compare token use, wall time, and missing-measurement boundaries on the selected release package.</p>
      </div>
      <div className="efficiency-toolbar">
        <div className="view-switch" role="group" aria-label="Efficiency chart view">
          {([
            ["tokens", "Score vs tokens"],
            ["time", "Score vs time"],
            ["profile", "Token profile"],
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
          Ranked only
        </label>
      </div>
      <div className="efficiency-layout">
        <div className="chart-panel">
          {mode === "profile" ? (
            <TokenProfile rows={rows} focused={focused} onFocus={setFocused} />
          ) : (
            <EfficiencyScatter rows={rows} mode={mode} focused={focused} onFocus={setFocused} />
          )}
        </div>
        <aside className="chart-guide" aria-label="Chart reading guide">
          <h3>Reading guide</h3>
          <dl>
            <div><dt><span className="guide-mark ranked" /> Ranked common harness</dt><dd>Comparable rows share the frozen release and adapter contract.</dd></div>
            <div><dt><span className="guide-mark native" /> Native pilot</dt><dd>Visible for evidence, excluded from the common-harness rank.</dd></div>
            <div><dt><span className="guide-line" /> Pareto frontier</dt><dd>No ranked point on the line is both less efficient and less accurate.</dd></div>
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
  const frontier = paretoFrontier(available.filter((row) => row.ranking_eligible), mode);

  return (
    <>
      <div className="chart-keyline"><span>Higher is better (y). Lower is better (x).</span><span>{missing.length} row{missing.length === 1 ? "" : "s"} without comparable telemetry</span></div>
      <svg className="efficiency-chart" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-labelledby="efficiency-chart-title efficiency-chart-description">
        <title id="efficiency-chart-title">Safe task success compared with {mode === "tokens" ? "median tokens" : "median wall time"}</title>
        <desc id="efficiency-chart-description">Each point is a model run. Solid circles are ranked common-harness rows; diamonds are unranked native pilots. Vertical lines show the task-success confidence interval.</desc>
        {[0, .25, .5, .75, 1].map((tick) => <g key={tick}><line x1={MARGIN.left} x2={WIDTH - MARGIN.right} y1={y(tick)} y2={y(tick)} className="chart-grid" /><text x={MARGIN.left - 12} y={y(tick) + 4} textAnchor="end" className="chart-axis-label">{Math.round(tick * 100)}%</text></g>)}
        {[0, .25, .5, .75, 1].map((fraction) => {
          const value = domain[0] + (domain[1] - domain[0]) * fraction;
          return <g key={fraction}><line x1={x(value)} x2={x(value)} y1={MARGIN.top} y2={HEIGHT - MARGIN.bottom} className="chart-grid" /><text x={x(value)} y={HEIGHT - MARGIN.bottom + 26} textAnchor="middle" className="chart-axis-label">{mode === "tokens" ? compactNumber(value) : `${value.toFixed(value >= 10 ? 0 : 1)}s`}</text></g>;
        })}
        {frontier.length > 1 && <polyline points={frontier.map((row) => `${x(xValue(row, mode) as number)},${y(row.safe_success_rate)}`).join(" ")} className="pareto-line" />}
        {available.map((row, index) => {
          const px = x(xValue(row, mode) as number);
          const py = y(row.safe_success_rate);
          const active = focused === row.model_name;
          const labelOnLeft = index % 2 === 1;
          return <g key={row.model_name} aria-hidden="true" onMouseEnter={() => onFocus(row.model_name)} className={active ? "chart-point active" : "chart-point"}>
            <line x1={px} x2={px} y1={y(row.task_success_ci95[0])} y2={y(row.task_success_ci95[1])} className="confidence-line" />
            {row.ranking_eligible ? <circle cx={px} cy={py} r={active ? 8 : 6} className="ranked-point" /> : <path d={`M ${px} ${py - 7} L ${px + 7} ${py} L ${px} ${py + 7} L ${px - 7} ${py} Z`} className="native-point" />}
            <text x={px + (labelOnLeft ? -12 : 12)} y={py + (labelOnLeft ? 22 : -12)} textAnchor={labelOnLeft ? "end" : "start"} className="chart-model-label">{shortModelName(row.model_name)}</text>
          </g>;
        })}
        <text transform={`translate(18 ${HEIGHT / 2}) rotate(-90)`} textAnchor="middle" className="chart-title-label">Safe task success</text>
        <text x={(WIDTH + MARGIN.left - MARGIN.right) / 2} y={HEIGHT - 13} textAnchor="middle" className="chart-title-label">{mode === "tokens" ? "Median provider-reported tokens / attempt" : "Median common-harness wall time / attempt"}</text>
      </svg>
      {missing.length > 0 && <div className="telemetry-missing"><strong>Telemetry unavailable</strong>{missing.map((row) => <button key={row.model_name} onFocus={() => onFocus(row.model_name)} onMouseEnter={() => onFocus(row.model_name)}>{shortModelName(row.model_name)}</button>)}</div>}
    </>
  );
}

function TokenProfile({ rows, focused, onFocus }: { rows: ModelResult[]; focused: string | null; onFocus: (value: string) => void }) {
  const available = rows.filter((row) => row.token_usage?.median_input_tokens != null && row.token_usage?.median_output_tokens != null);
  const max = Math.max(...available.map((row) => row.token_usage?.median_total_tokens ?? 0), 1);
  return <div className="token-profile" role="img" aria-label="Median input and output token profile by model">
    <div className="profile-legend"><span><i className="input-token" /> Input</span><span><i className="output-token" /> Output</span></div>
    {available.map((row) => {
      const input = row.token_usage?.median_input_tokens ?? 0;
      const output = row.token_usage?.median_output_tokens ?? 0;
      return <button type="button" key={row.model_name} className={focused === row.model_name ? "profile-row active" : "profile-row"} onFocus={() => onFocus(row.model_name)} onMouseEnter={() => onFocus(row.model_name)}><span className="profile-name">{shortModelName(row.model_name)}</span><span className="profile-bar"><i className="input-token" style={{ width: `${(input / max) * 100}%` }} /><i className="output-token" style={{ width: `${(output / max) * 100}%` }} /></span><span className="profile-value">{formatTokens(input + output)}</span></button>;
    })}
    {rows.length > available.length && <p className="profile-missing">{rows.length - available.length} native or provider row(s) have no comparable token telemetry.</p>}
  </div>;
}

function EfficiencyTable({ rows, focused, onFocus }: { rows: ModelResult[]; focused: string | null; onFocus: (value: string) => void }) {
  return <div className="efficiency-table-wrap" role="region" aria-label="Efficiency evidence table" tabIndex={0}><table className="efficiency-table"><caption>Evidence table; common harness unless noted</caption><thead><tr><th>Model</th><th>Score</th><th>95% CI</th><th>Input tokens</th><th>Output tokens</th><th>Median time</th><th>Attempts</th><th>Harness status</th></tr></thead><tbody>{rows.map((row) => <tr key={row.model_name} className={focused === row.model_name ? "focused" : undefined} onMouseEnter={() => onFocus(row.model_name)}><td><button type="button" onFocus={() => onFocus(row.model_name)}>{shortModelName(row.model_name)}</button></td><td>{formatPercent(row.safe_success_rate)}</td><td>{formatPercent(row.task_success_ci95[0])}–{formatPercent(row.task_success_ci95[1])}</td><td>{formatTokens(row.token_usage?.median_input_tokens)}</td><td>{formatTokens(row.token_usage?.median_output_tokens)}</td><td>{formatDuration(row.median_duration_seconds)}</td><td>{row.completed_count}/{row.expected_attempt_count}</td><td>{row.ranking_eligible ? "Common harness · ranked" : "Native/different harness · unranked"}</td></tr>)}</tbody></table></div>;
}

function xValue(row: ModelResult, mode: "tokens" | "time") {
  const value = mode === "tokens" ? row.token_usage?.median_total_tokens : row.median_duration_seconds;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function paretoFrontier(rows: ModelResult[], mode: "tokens" | "time") {
  const ordered = [...rows].sort((a, b) => (xValue(a, mode) ?? Infinity) - (xValue(b, mode) ?? Infinity));
  const frontier: ModelResult[] = [];
  let best = -Infinity;
  for (const row of ordered) if (row.safe_success_rate > best) { frontier.push(row); best = row.safe_success_rate; }
  return frontier;
}

function compactNumber(value: number) { return value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1)}k` : Math.round(value).toString(); }
function shortModelName(value: string) { return value.replace("gpt-5.6-sol", "GPT-5.6").replace("qwen", "Qwen").replace("[effort=", "(").replace("]", ")"); }
