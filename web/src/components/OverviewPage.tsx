import { ExternalLink } from "lucide-react";
import { REPO_URL } from "../content";
import type { FleetStatus, Leaderboard, ModelCatalogEntry, ReleaseEvidence, ReviewEvidence } from "../types";
import { AtAGlanceLeaderboard } from "./AtAGlanceLeaderboard";
import { EvidenceSpotlight, EvidenceSpotlightSources } from "./EvidenceSpotlight";

type Props = {
  data: Leaderboard | null;
  fleetStatus: FleetStatus | null;
  modelCatalog: ModelCatalogEntry[];
  releaseEvidence: ReleaseEvidence | null;
  reviewEvidence: ReviewEvidence | null;
};

export function OverviewPage({ data, fleetStatus, modelCatalog, releaseEvidence, reviewEvidence }: Props) {
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

      <AtAGlanceLeaderboard data={data} modelCatalog={modelCatalog} resultsScope="descriptive" />

      <details className="overview-example">
        <summary>
          <span>See one answer-level example</span>
          <small>Exact output, verified peer, failed checks, and human evidence status</small>
        </summary>
        <div>
          <EvidenceSpotlight data={data} releaseEvidence={releaseEvidence} reviewEvidence={reviewEvidence} />
          <EvidenceSpotlightSources />
        </div>
      </details>

      <section className="overview-paths" aria-labelledby="next-title">
        <h2 id="next-title">What do you want to do?</h2>
        <div className="path-list">
          <a href="/explore">
            <strong>Investigate a result</strong>
            <span>Search exact outputs, failed graders, hashes, time, and token evidence.</span>
          </a>
          <a href="/evals">
            <strong>Browse the evals</strong>
            <span>See released task contracts, domains, inputs, tools, and response shapes.</span>
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
