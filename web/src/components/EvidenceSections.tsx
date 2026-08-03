import { ExternalLink } from "lucide-react";
import { DOC_LINKS, domainDescriptions, workflow } from "../content";
import { domainLabel, formatPercent, shortHash } from "../lib/format";
import { countStateLabel, evidenceStatusLabel, interactionDepthLabel, maturityLabel, releaseIdForView } from "../lib/releaseEvidence";
import type { AccessStatus, DefectLedger, Leaderboard, ReleaseEvidence, ReleaseView } from "../types";

type EvidenceSectionsProps = {
  accessStatus: AccessStatus[];
  data: Leaderboard | null;
  defectLedger: DefectLedger | null;
  releaseView: ReleaseView;
  releaseEvidence: ReleaseEvidence | null;
};

export function EvidenceSections({ accessStatus, data, defectLedger, releaseView, releaseEvidence }: EvidenceSectionsProps) {
  const coverage = data?.coverage ?? buildCoverage(data?.tasks ?? []);
  const integrity = data?.integrity;
  const blocked = accessStatus.filter((item) => item.status !== "available");
  const rankedCount = data ? integrity?.ranked_model_count ?? data.models.length : null;
  const reviewCount = data ? integrity?.unranked_model_count ?? data.unranked_models?.length ?? 0 : null;
  const trackMix = buildTrackMix(data?.tasks ?? []);
  const selectedReleaseId = data?.release.release_id ?? fallbackReleaseId(releaseView);
  const affectedDefects = defectLedger?.entries.filter((entry) =>
    entry.affected_release_ids.includes(selectedReleaseId),
  ) ?? [];

  return (
    <>
      <section className="coverage-section" id="coverage">
        <div className="section-heading section-heading-row">
          <div>
            <h2>Task surface and contract</h2>
            <p>Selected-release composition, task mix, and reproducibility boundaries from the live JSON package.</p>
          </div>
          <p className="coverage-summary">
            {data?.tasks.length ?? "—"} public tasks · {data?.release.release_id ?? fallbackReleaseId(releaseView)}
          </p>
        </div>

        <div className="board-grid">
          <article className="board-panel">
            <h3>Benchmark composition</h3>
            <ul className="board-list">
              <li><strong>{data?.tasks.length ?? "—"}</strong> public tasks in the selected release</li>
              <li><strong>{rankedCount ?? "—"}</strong> official harness-group row{rankedCount === 1 ? "" : "s"}</li>
              <li><strong>{reviewCount ?? "—"}</strong> descriptive-only row{reviewCount === 1 ? "" : "s"}</li>
              {data?.release.family_count != null && <li><strong>{data.release.family_count}</strong> independent patient/task families</li>}
              <li><strong>Human baseline</strong> {humanBaselineSummary(releaseEvidence)}</li>
              <li><strong>Counterfactuals</strong> {comparisonStateSummary(releaseEvidence?.evidence.paired_counterfactuals)}</li>
              <li><strong>Negative controls</strong> {comparisonStateSummary(releaseEvidence?.evidence.negative_controls)}</li>
              <li><strong>Evidence maturity</strong> {releaseEvidence ? maturityLabel(releaseEvidence.maturity) : "unavailable"}</li>
              <li><strong>Interaction depth</strong> {releaseEvidence ? interactionDepthLabel(releaseEvidence.interaction.depth) : "unavailable"}</li>
            </ul>
          </article>

          <article className="board-panel board-panel-wide">
            <h3>Domain matrix</h3>
            <div className="domain-matrix">
              <div className="domain-matrix-head">
                <span>Domain</span>
                <span>Tasks</span>
                <span>Escalation</span>
                <span>Focus</span>
              </div>
              {coverage.map((row) => (
                <div className="domain-matrix-row" key={row.domain}>
                  <span>{domainLabel(row.domain)}</span>
                  <span>{row.task_count}</span>
                  <span>{row.expected_escalation_count}</span>
                  <span>{domainDescriptions[row.domain] ?? "Release-defined benchmark tasks."}</span>
                </div>
              ))}
            </div>
          </article>

          <article className="board-panel">
            <h3>Track mix</h3>
            <div className="stack-list">
              {trackMix.slice(0, 6).map((item) => (
                <div className="stack-row" key={item.track}>
                  <span>{formatTrackLabel(item.track)}</span>
                  <strong>{item.count}</strong>
                </div>
              ))}
            </div>
          </article>

          <article className="board-panel">
            <h3>Methods & reproducibility</h3>
            <ul className="board-list">
              <li>Primary metric: <strong>{data?.methodology.primary_metric ?? "safe task success rate"}</strong></li>
              <li>Ranking rule: <strong>{data?.methodology.ranking_rule ?? "complete and internally consistent runs only"}</strong></li>
              <li>Release hash: <strong className="mono-copy">{shortHash(integrity?.release_contract_hash_v2 ?? integrity?.release_contract_hash)}</strong></li>
              {data?.methodology.family_dependence && <li>Family analysis: <strong>{data.methodology.family_dependence}</strong></li>}
              <li>Blocked access handles remain listed separately from scored rows.</li>
            </ul>
          </article>
        </div>
      </section>

      <section className="evidence-section" id="methodology">
        <div className="section-heading">
          <h2>How a score is made</h2>
          <p>
            The benchmark asks whether a model can finish bounded task work, produce valid artifacts, and escalate when it should.
            It does not authorize treatment, planning, or patient-specific action.
          </p>
        </div>
        <div className="boundary-grid">
          <article>
            <h3>Runtime boundary</h3>
            <p>Models receive instructions, inputs, tools, and an output schema. Gold answers and graders stay outside the sandbox.</p>
          </article>
          <article>
            <h3>Deterministic regrading</h3>
            <p>Stored pass labels are rechecked from artifacts so a tampered result file cannot silently improve a public score.</p>
          </article>
          <article>
            <h3>Harder by construction</h3>
            <p>Saturated public lanes trigger protected holdouts, counterfactual variants, and state-graded workflow tasks rather than more headline ranking.</p>
          </article>
        </div>
        <ol className="workflow-rail">
          {workflow.map((step) => (
            <li key={step.number}>
              <strong>{step.number}</strong>
              <span>{step.title}</span>
              <p>{step.description}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="governance-section" id="governance">
        <div className="boundary">
          <h2>Research benchmark, not clinical authority</h2>
          <p>
            MedPhysBench evaluates research-grade assistance and escalation behavior. It is not a medical device,
            a release-to-treat system, or evidence of autonomous patient-specific decision-making.
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
            <p>{data?.release.release_id ?? fallbackReleaseId(releaseView)}</p>
            <p>{data?.release.description ?? ""}</p>
          </article>
          <article>
            <h3>Expected attempts</h3>
            <p>{data?.release.expected_attempts_per_task ?? integrity?.expected_attempts_per_task ?? "—"} per task in the current public release.</p>
          </article>
          <article>
            <h3>Official / descriptive</h3>
            <p>{rankedCount} official harness-group rows and {reviewCount} descriptive-only rows currently visible.</p>
          </article>
          {data?.release.family_count != null && (
            <article>
              <h3>Independence unit</h3>
              <p>{data.release.family_count} declared families; task views are not counted as independent patients.</p>
            </article>
          )}
          {data?.release.max_family_share != null && (
            <article>
              <h3>Family concentration guard</h3>
              <p>No one family may exceed {formatPercent(data.release.max_family_share)} of release tasks without an explicit reviewed override.</p>
            </article>
          )}
          <article>
            <h3>Access status</h3>
            <p>{blocked.length} blocked or retired handles kept separate from scored results.</p>
          </article>
          <article>
            <h3>External evidence</h3>
            {releaseEvidence ? (
              <p>
                Domain review {countStateLabel(releaseEvidence.evidence.independent_domain_review)}; independent replication {evidenceStatusLabel(releaseEvidence.evidence.independent_replication.status)}.
              </p>
            ) : (
              <p>Canonical evidence unavailable; no review or replication claim is inferred.</p>
            )}
          </article>
          <article>
            <h3>Comparison gate</h3>
            {releaseEvidence ? (
              <p>
                Holdout {evidenceStatusLabel(releaseEvidence.exposure.protected_holdout.status)} · counterfactuals {countStateLabel(releaseEvidence.evidence.paired_counterfactuals)} · negative controls {countStateLabel(releaseEvidence.evidence.negative_controls)}.
              </p>
            ) : (
              <p>Canonical evidence unavailable; no comparison-readiness claim is inferred.</p>
            )}
          </article>
          <article className={affectedDefects.length ? "integrity-defect-card active" : "integrity-defect-card"}>
            <h3>Public defect ledger</h3>
            {!defectLedger ? (
              <p>Ledger loading or unavailable; no clean-bill claim is inferred.</p>
            ) : affectedDefects.length ? (
              <>
                <p><strong>{affectedDefects.length} disclosed item{affectedDefects.length === 1 ? "" : "s"}</strong> affect this release.</p>
                {affectedDefects.map((defect) => (
                  <details key={defect.defect_id}>
                    <summary>{defect.defect_id} · {defect.severity} · {defect.status}</summary>
                    <p>{defect.summary}</p>
                    <p>{defect.score_treatment}</p>
                  </details>
                ))}
              </>
            ) : (
              <p>No confirmed ledger entry currently targets this release.</p>
            )}
          </article>
        </div>
      </section>
    </>
  );
}

function humanBaselineSummary(releaseEvidence: ReleaseEvidence | null) {
  if (!releaseEvidence) return "evidence unavailable";
  return countStateLabel(releaseEvidence.evidence.human_baseline);
}

function comparisonStateSummary(state: ReleaseEvidence["evidence"]["paired_counterfactuals"] | undefined) {
  if (!state) return "not declared";
  return countStateLabel(state);
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

function buildTrackMix(tasks: Leaderboard["tasks"]) {
  const counts = new Map<string, number>();
  for (const task of tasks) {
    counts.set(task.track, (counts.get(task.track) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([track, count]) => ({ track, count }))
    .sort((left, right) => right.count - left.count || left.track.localeCompare(right.track));
}

function formatTrackLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function fallbackReleaseId(releaseView: ReleaseView) {
  return releaseIdForView(releaseView);
}
