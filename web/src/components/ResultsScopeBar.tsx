import type { Leaderboard } from "../types";
import { resultsScopeCounts, type ResultsScope } from "../lib/resultsScope";

type Props = {
  data: Leaderboard | null;
  onChange: (value: ResultsScope) => void;
  value: ResultsScope;
};

export function ResultsScopeBar({ data, onChange, value }: Props) {
  const counts = resultsScopeCounts(data);
  const description = value === "official"
    ? `Showing ${counts.official} rank-eligible rows. Every rank stays inside one frozen harness contract.`
    : `Showing all ${counts.published} published rows: ${counts.official} official and ${counts.descriptive} descriptive. Cross-contract rank is disabled.`;

  return (
    <section className={`results-scope-bar ${value}`} aria-labelledby="results-scope-title">
      <div className="results-scope-copy">
        <strong id="results-scope-title">Evidence scope</strong>
        <p id="results-scope-description">{description}</p>
      </div>
      <div
        className="results-scope-switch"
        role="group"
        aria-label="Results visibility scope"
        aria-describedby="results-scope-description"
      >
        <button type="button" aria-pressed={value === "descriptive"} onClick={() => onChange("descriptive")}>
          <span>All published evidence</span>
          <small>{counts.published} rows</small>
        </button>
        <button type="button" aria-pressed={value === "official"} onClick={() => onChange("official")}>
          <span>Official comparison only</span>
          <small>{counts.official} rows</small>
        </button>
      </div>
    </section>
  );
}
