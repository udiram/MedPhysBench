import { ExternalLink } from "lucide-react";
import { REPO_URL } from "../content";
import type { ReleaseEvidence } from "../types";
import { PageIntro } from "./PageIntro";

type Props = {
  releaseEvidence: ReleaseEvidence | null;
};

export function HumanBenchmarkPage({ releaseEvidence }: Props) {
  const baseline = releaseEvidence?.evidence.human_baseline ?? null;
  return (
    <>
      <PageIntro
        title="Human benchmark"
        description="A matched, timed baseline for qualified medical-physics professionals. Humans receive the same runtime-visible evidence and output contract as the model harness; identities and consent records stay outside the public repository."
        actions={(
          <a className="primary-action" href={`${REPO_URL}/issues/new?template=human_baseline_interest.yml`} target="_blank" rel="noreferrer">
            Express interest <ExternalLink aria-hidden="true" />
          </a>
        )}
      />

      <section className="human-status" aria-labelledby="human-status-title">
        <div>
          <h2 id="human-status-title">Current collection status</h2>
          <p>
            {baseline
              ? `${baseline.completed}/${baseline.target ?? "—"} participants complete · ${baseline.status.replaceAll("_", " ")}`
              : "The release-matched evidence ledger is unavailable."}
          </p>
        </div>
        <p>
          No human score is published today. The site will not display simulated human answers, benchmark-author
          performance, or model-authored references as a human baseline.
        </p>
      </section>

      <section className="human-flow" aria-labelledby="human-flow-title">
        <h2 id="human-flow-title">How participation works</h2>
        <ol>
          <li>
            <strong>Eligibility and study determination</strong>
            <span>Qualified physicists, residents, and planning specialists enter prespecified strata. No clinical credentials are uploaded to this site.</span>
          </li>
          <li>
            <strong>Sealed assignment</strong>
            <span>A coordinator issues a pseudonymous participant code and a balanced task block. Public answers and gold labels remain hidden.</span>
          </li>
          <li>
            <strong>Timed completion</strong>
            <span>The runner records final structured output, active time, allowed tools, confidence, and an optional ambiguity flag.</span>
          </li>
          <li>
            <strong>De-identified analysis</strong>
            <span>Results are released only after qualification checks, adjudication, and participant- and family-cluster uncertainty analysis.</span>
          </li>
        </ol>
      </section>

      <section className="human-boundaries" aria-labelledby="human-boundaries-title">
        <h2 id="human-boundaries-title">Before you start</h2>
        <div>
          <p><strong>Research only.</strong> This does not certify, rank, or evaluate a participant for employment or clinical privileges.</p>
          <p><strong>No patient data.</strong> Do not submit PHI, clinical credentials, employer records, or local system screenshots.</p>
          <p><strong>No instant correctness feedback.</strong> Feedback is withheld during collection to prevent task-family leakage.</p>
        </div>
        <a className="text-link" href={`${REPO_URL}/blob/main/docs/HUMAN_BASELINE_PROTOCOL.md`} target="_blank" rel="noreferrer">
          Read the preregistered protocol <ExternalLink aria-hidden="true" />
        </a>
      </section>
    </>
  );
}
