import { ExternalLink } from "lucide-react";
import { DOC_LINKS } from "../content";
import { domainLabel, shortHash } from "../lib/format";
import type { AccessStatus, Leaderboard } from "../types";

type EvidenceSectionsProps = {
  data: Leaderboard | null;
  accessStatus: AccessStatus[];
};

export function EvidenceSections({ data, accessStatus }: EvidenceSectionsProps) {
  const coverage = data?.coverage ?? buildCoverage(data?.tasks ?? []);
  const blocked = accessStatus.filter((item) => item.status !== "available");
  const integrity = data?.integrity;

  return (
    <>
      <section className="evidence-section" id="methodology">
        <div className="section-heading">
          <h2>How a score is made</h2>
          <p>
            The benchmark asks whether a model can finish task work under professional constraints
            and escalate when it should. It is not a claim of autonomous clinical competence.
          </p>
        </div>
        <div className="boundary-grid">
          <article>
            <h3>Runtime boundary</h3>
            <p>Models receive instructions, inputs, tool contracts, and an output schema. Gold answers and graders stay outside the sandbox.</p>
          </article>
          <article>
            <h3>Deterministic regrading</h3>
            <p>Stored pass labels are rechecked from the output artifact so a tampered result file cannot silently improve a public score.</p>
          </article>
          <article>
            <h3>Ranking rule</h3>
            <p>Only release-complete, internally consistent run sets are ranked. Review rows remain visible beside the public table.</p>
          </article>
        </div>
        <ol className="workflow-rail">
          <li>Author task and reference solution</li>
          <li>Seal the model-visible runtime packet</li>
          <li>Run one fixed harness per model</li>
          <li>Regrade outputs and safety gates deterministically</li>
          <li>Publish hashes, metrics, and integrity notes</li>
        </ol>
      </section>

      <section className="coverage-section" id="coverage">
        <div className="section-heading section-heading-row">
          <div>
            <h2>Task coverage</h2>
          </div>
          <p className="coverage-summary">
            {data?.tasks.length ?? 0} public tasks across {coverage.length} medical-physics domains.
          </p>
        </div>
        <div className="coverage-table">
          <div className="coverage-header">
            <span>Domain</span>
            <span>Tasks</span>
            <span>Escalation-boundary tasks</span>
          </div>
          {coverage.map((row) => (
            <div className="coverage-row" key={row.domain}>
              <span>{domainLabel(row.domain)}</span>
              <span>{row.task_count}</span>
              <span>{row.expected_escalation_count}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="governance-section" id="governance">
        <div className="boundary">
          <h2>Research benchmark, not clinical authority</h2>
          <p>
            MedPhysBench evaluates research-grade assistance and escalation behavior. It is not a
            medical device, a release-to-treat system, or evidence of autonomous patient-specific
            decision-making.
          </p>
          <div className="boundary-rule">
            No live clinical systems. No hidden gold in runtime context. No autonomous release-to-treat claims.
          </div>
        </div>
        <div className="doc-grid">
          {DOC_LINKS.map(([label, href]) => (
            <a key={label} href={href} target="_blank" rel="noreferrer">
              <div>
                <strong>{label}</strong>
                <span>{href.split("/").at(-1)?.replace(".md", "").replaceAll("_", " ")}</span>
              </div>
              <ExternalLink aria-hidden="true" />
            </a>
          ))}
        </div>
      </section>

      <section className="integrity-section" id="integrity">
        <div className="section-heading">
          <h2>Integrity controls</h2>
          <p>Complete attempt matrices, immutable contracts, and output-derived grading keep publication claims auditable.</p>
        </div>
        <div className="integrity-grid">
          <article>
            <h3>Release contract</h3>
            <p>{data?.release.release_id ?? "public-core-v0.4"}</p>
            <p>{data?.release.description ?? ""}</p>
          </article>
          <article>
            <h3>Expected attempts</h3>
            <p>{data?.release.expected_attempts_per_task ?? integrity?.expected_attempts_per_task ?? "—"} per task in the current public release.</p>
          </article>
          <article>
            <h3>Ranked / review</h3>
            <p>{integrity?.ranked_model_count ?? data?.models.length ?? 0} ranked and {integrity?.unranked_model_count ?? data?.unranked_models?.length ?? 0} review rows currently visible.</p>
          </article>
          <article>
            <h3>Release hash</h3>
            <p className="mono-copy">{shortHash(integrity?.release_contract_hash)}</p>
            <p>Frozen task list and prompt/tool contract for this release package.</p>
          </article>
        </div>
        {blocked.length > 0 && (
          <p className="integrity-note">
            {blocked.length} blocked or retired access handles are listed separately from scored
            results so provider availability does not quietly disappear from the public record.
          </p>
        )}
      </section>
    </>
  );
}

function buildCoverage(tasks: Leaderboard["tasks"]) {
  const buckets = new Map<string, { domain: string; task_count: number; expected_escalation_count: number }>();
  for (const task of tasks) {
    const current = buckets.get(task.domain) ?? {
      domain: task.domain,
      task_count: 0,
      expected_escalation_count: 0,
    };
    current.task_count += 1;
    current.expected_escalation_count += Number(Boolean(task.expected_escalation));
    buckets.set(task.domain, current);
  }
  return [...buckets.values()].sort((left, right) => left.domain.localeCompare(right.domain));
}
