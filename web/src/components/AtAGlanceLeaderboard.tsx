import { useMemo, useState } from "react";
import { formatPercent, normalizeModelDisplayName, providerLabel } from "../lib/format";
import { atAGlanceRows, type AtAGlanceSource } from "../lib/atAGlanceLeaderboard";
import { modelRunKey } from "../lib/modelRunKey";
import type { ResultsScope } from "../lib/resultsScope";
import type { Leaderboard, ModelCatalogEntry } from "../types";

type Props = {
  data: Leaderboard | null;
  modelCatalog: ModelCatalogEntry[];
  resultsScope: ResultsScope;
};

export function AtAGlanceLeaderboard({ data, modelCatalog, resultsScope }: Props) {
  const [source, setSource] = useState<AtAGlanceSource>("all");
  const catalogIndex = useMemo(
    () => new Map(modelCatalog.map((entry) => [`${entry.provider}::${entry.model_name}`, entry])),
    [modelCatalog],
  );
  const rows = useMemo(() => {
    return atAGlanceRows(data, modelCatalog, resultsScope, source);
  }, [data, modelCatalog, resultsScope, source]);

  return (
    <section className="glance-board" aria-labelledby="glance-board-title">
      <header className="glance-board-heading">
        <div>
          <h2 id="glance-board-title">Best published outcomes</h2>
          <p>The strongest released configuration for each base model. Select a model to inspect every scored task and exact public output.</p>
        </div>
        <div className="source-switch" role="group" aria-label="Filter by model source">
          {(["all", "open", "closed"] as const).map((value) => (
            <button key={value} type="button" aria-pressed={source === value} onClick={() => setSource(value)}>
              {value === "all" ? "All" : value === "open" ? "Open weights" : "Closed"}
            </button>
          ))}
        </div>
      </header>

      {!data ? (
        <p className="glance-empty" role="status">Loading released results…</p>
      ) : rows.length ? (
        <ol className="glance-ranking">
          {rows.map((row, index) => {
            const runKey = modelRunKey(row);
            const sourceLabel = catalogIndex.get(`${row.provider}::${row.model_name}`)?.openness;
            return (
              <li key={runKey}>
                <span className="glance-position" aria-label={`Published outcome position ${row.outcome_rank ?? index + 1}`}>{row.outcome_rank ?? index + 1}</span>
                <div className="glance-model">
                  <a href={`/explore?fx_model=${encodeURIComponent(runKey)}#exact-task-comparison`}>
                    {normalizeModelDisplayName(row.model_name)}
                  </a>
                  <span>{providerLabel(row.provider)}{sourceLabel ? ` · ${sourceLabel === "open" ? "open weights" : sourceLabel}` : ""}</span>
                </div>
                <div className="glance-score" aria-label={`${formatPercent(row.safe_success_rate)} safe success`}>
                  <i style={{ width: `${Math.max(0, Math.min(1, row.safe_success_rate)) * 100}%` }} />
                </div>
                <strong>{formatPercent(row.safe_success_rate)}</strong>
                <span className="glance-status">
                  {row.ranking_eligible && row.rank ? `Official #${row.rank}` : "Descriptive"}
                </span>
                <a className="glance-inspect" href={`/explore?fx_model=${encodeURIComponent(runKey)}#exact-task-comparison`}>
                  View tasks
                </a>
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="glance-empty" role="status">No complete released rows match this source filter.</p>
      )}

      <footer className="glance-board-note">
        <p>Published outcome order spans released configurations; duplicate routes for one base model are collapsed here. “Official” ranks only compare identical frozen harness contracts.</p>
        <a href="/explore">Compare exact task responses <span aria-hidden="true">→</span></a>
      </footer>
    </section>
  );
}
