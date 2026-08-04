import { ExternalLink } from "lucide-react";
import { REPO_URL } from "../content";
import type { FleetStatus } from "../types";
import { FleetCoverage } from "./FleetCoverage";
import { PageIntro } from "./PageIntro";

type Props = {
  fleetStatus: FleetStatus | null;
};

export function RunBenchmarkPage({ fleetStatus }: Props) {
  return (
    <>
      <PageIntro
        title="Run or request a model"
        description="Results are published only after the full attempt matrix, immutable identity, deterministic regrade, telemetry, and submission contract pass. Naming a model or completing a canary never creates a leaderboard row."
        actions={(
          <a className="primary-action" href={`${REPO_URL}/issues/new?template=model_evaluation_request.yml`} target="_blank" rel="noreferrer">
            Request an evaluation <ExternalLink aria-hidden="true" />
          </a>
        )}
      />

      <section className="run-paths" aria-labelledby="run-paths-title">
        <h2 id="run-paths-title">Choose a path</h2>
        <div className="run-path-list">
          <article>
            <h3>Run the public harness</h3>
            <p>Use a frozen release with a declared adapter and store the complete artifact matrix outside the repository until it passes validation.</p>
            <pre><code>{`uv sync --extra dev --extra imaging
uv run medphys-bench validate-release releases/public_core_v0_4.yaml
uv run medphys-bench run-release \\
  releases/public_core_v0_4.yaml \\
  --adapter ollama --model <model-id> \\
  --results-dir runs --resume`}</code></pre>
            <a className="text-link" href={`${REPO_URL}/blob/main/docs/REPRODUCIBILITY.md`} target="_blank" rel="noreferrer">
              Reproducibility guide <ExternalLink aria-hidden="true" />
            </a>
          </article>
          <article>
            <h3>Submit an auditable run</h3>
            <p>A submission must bind the exact model, provider, revision, harness, settings, task manifest, receipts, attempts, hashes, and telemetry.</p>
            <pre><code>{`uv run python scripts/common_harness_submission.py validate \\
  <submission-manifest.json>`}</code></pre>
            <a className="text-link" href={`${REPO_URL}/blob/main/docs/MODEL_ONBOARDING.md`} target="_blank" rel="noreferrer">
              Model onboarding contract <ExternalLink aria-hidden="true" />
            </a>
          </article>
        </div>
      </section>

      <section className="request-checklist" aria-labelledby="request-checklist-title">
        <h2 id="request-checklist-title">What a model request needs</h2>
        <ul>
          <li>Exact provider and deployment identifier—not a marketing family name.</li>
          <li>Version, retrieval date, modality support, and immutable artifact identity where available.</li>
          <li>A credential route that stays outside issues, commits, logs, and submission artifacts.</li>
          <li>Permission to publish the tested configuration, failures, telemetry coverage, and limitations.</li>
        </ul>
      </section>

      <section className="fleet-request-status" aria-labelledby="fleet-status-title">
        <div>
          <h2 id="fleet-status-title">Requested coverage</h2>
          <p>The frozen fleet is an acquisition backlog, not a results table.</p>
        </div>
        <dl>
          <div><dt>Planned base models</dt><dd>{fleetStatus?.summary.planned_base_models ?? "—"}</dd></div>
          <div><dt>Evaluated</dt><dd>{fleetStatus?.summary.evaluated_base_models ?? "—"}</dd></div>
          <div><dt>Remaining</dt><dd>{fleetStatus ? fleetStatus.summary.planned_base_models - fleetStatus.summary.evaluated_base_models : "—"}</dd></div>
        </dl>
        <a className="text-link" href={`${REPO_URL}/blob/main/docs/MODEL_FLEET_PROTOCOL.md`} target="_blank" rel="noreferrer">
          Inspect the frozen fleet protocol <ExternalLink aria-hidden="true" />
        </a>
      </section>

      <details className="full-analysis-disclosure qualification-backlog">
        <summary>
          <span>
            <strong>Inspect the 50-model qualification backlog</strong>
            <small>Filter frozen base models by source and evidence stage, then inspect exact access or submission evidence.</small>
          </span>
        </summary>
        <div>
          <FleetCoverage data={fleetStatus} />
        </div>
      </details>
    </>
  );
}
