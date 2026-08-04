import { ExternalLink } from "lucide-react";
import { REPO_URL } from "../content";
import { spotlightRuns } from "../lib/evidenceSpotlight";
import { formatDuration, formatPercent, formatTokens, normalizeModelDisplayName, providerLabel } from "../lib/format";
import type { FleetStatus, Leaderboard, ReleaseEvidence, ReviewEvidence } from "../types";
import { EvidenceSpotlight, EvidenceSpotlightSources } from "./EvidenceSpotlight";

type Props = {
  data: Leaderboard | null;
  fleetStatus: FleetStatus | null;
  releaseEvidence: ReleaseEvidence | null;
  reviewEvidence: ReviewEvidence | null;
};

export function OverviewPage({ data, fleetStatus, releaseEvidence, reviewEvidence }: Props) {
  const runs = spotlightRuns(data);
  const preview = runs.slice(0, 6);
  return (
    <>
      <section className="overview-intro" aria-labelledby="overview-title">
        <div className="overview-copy">
          <h1 id="overview-title">See how a model handled the work.</h1>
          <p>
            MedPhysBench evaluates bounded medical-physics assistance with deterministic outcomes, explicit safety
            gates, and immutable run evidence. Start with one task and inspect the exact difference between answers.
          </p>
          <div className="overview-actions">
            <a className="primary-action" href="/results">View verified results</a>
            <a className="secondary-action" href="/explore">Explore task attempts</a>
          </div>
        </div>
        <dl className="overview-facts" aria-label="Current evidence summary">
          <div>
            <dt>Verified base models</dt>
            <dd>{fleetStatus?.summary.evaluated_base_models ?? "—"}</dd>
          </div>
          <div>
            <dt>Rankable base models</dt>
            <dd>{fleetStatus?.summary.ranked_base_models ?? "—"}</dd>
          </div>
          <div>
            <dt>Human baseline</dt>
            <dd>{humanState(releaseEvidence)}</dd>
          </div>
        </dl>
      </section>

      <EvidenceSpotlight data={data} releaseEvidence={releaseEvidence} reviewEvidence={reviewEvidence} />
      <EvidenceSpotlightSources />

      <section className="verified-preview" aria-labelledby="verified-preview-title">
        <div className="section-heading-row compact-heading">
          <div>
            <h2 id="verified-preview-title">Published runs</h2>
            <p>Every row below has a complete released attempt matrix. Planned models are not results.</p>
          </div>
          <a className="text-link" href="/results">All results and filters <span aria-hidden="true">→</span></a>
        </div>
        <div className="table-scroll" role="region" aria-label="Published model run preview" tabIndex={0}>
          <table className="verified-preview-table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Published outcome</th>
                <th>Comparison status</th>
                <th>Median time</th>
                <th>Median tokens</th>
              </tr>
            </thead>
            <tbody>
              {preview.map(({ key, row }) => (
                <tr key={key}>
                  <th scope="row">
                    <a href={`/explore?fx_model=${encodeURIComponent(key)}#forensics`}>
                      {normalizeModelDisplayName(row.model_name)}
                    </a>
                    <span>{providerLabel(row.provider)}</span>
                  </th>
                  <td>{formatPercent(row.safe_success_rate)}</td>
                  <td>{row.ranking_eligible ? "Official frozen group" : "Descriptive · no controlled peer"}</td>
                  <td>{formatDuration(row.median_duration_seconds)}</td>
                  <td>{row.token_usage?.complete ? formatTokens(row.token_usage.median_total_tokens) : "Unavailable"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="overview-paths" aria-labelledby="next-title">
        <h2 id="next-title">What do you want to do?</h2>
        <div className="path-list">
          <a href="/explore">
            <strong>Investigate a result</strong>
            <span>Search exact outputs, failed graders, hashes, time, and token evidence.</span>
          </a>
          <a href="/humans">
            <strong>Join the human benchmark</strong>
            <span>Read eligibility, study status, and the matched-evidence protocol.</span>
          </a>
          <a href="/run">
            <strong>Run or request a model</strong>
            <span>Use the public harness or request a reviewed evaluation.</span>
          </a>
          <a href={`${REPO_URL}/blob/main/docs/BENCHMARK_PAPER.md`} target="_blank" rel="noreferrer">
            <strong>Read the methods</strong>
            <span>Task construction, grading, uncertainty, governance, and limitations.</span>
            <ExternalLink aria-hidden="true" />
          </a>
        </div>
      </section>
    </>
  );
}

function humanState(evidence: ReleaseEvidence | null) {
  const state = evidence?.evidence.human_baseline;
  if (!state) return "Unavailable";
  return `${state.completed}/${state.target ?? "—"} · ${state.status.replaceAll("_", " ")}`;
}
