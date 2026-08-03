import { ExternalLink } from "lucide-react";
import {
  countStateLabel,
  evidenceClaimText,
  interactionDepthLabel,
  maturityLabel,
  normalizeReleaseTitle,
  releaseIdForView,
} from "../lib/releaseEvidence";
import type { Leaderboard, ReleaseEvidence, ReleaseView } from "../types";

type HeroProps = {
  data: Leaderboard | null;
  onReleaseViewChange: (value: ReleaseView) => void;
  releaseView: ReleaseView;
  releaseEvidence: ReleaseEvidence | null;
  releaseEvidenceLoaded: boolean;
  repoUrl: string;
};

export function Hero({ data, onReleaseViewChange, releaseView, releaseEvidence, releaseEvidenceLoaded, repoUrl }: HeroProps) {
  const rankedCount = data ? data.integrity?.ranked_model_count ?? data.models.length : null;
  const reviewCount = data ? data.integrity?.unranked_model_count ?? data.unranked_models?.length ?? 0 : null;
  const taskCount = data?.tasks.length ?? null;
  const familyCount = data?.release.family_count ?? null;
  const attempts = data?.release.expected_attempts_per_task ?? null;
  const boundary = releaseBoundary(releaseEvidence, releaseEvidenceLoaded);

  return (
    <section className="hero" id="benchmark">
      <div className="hero-meta-strip" aria-label="Selected release metadata">
        <span>Release</span>
        <strong>{data?.release.release_id ?? fallbackReleaseId(releaseView)}</strong>
        <span>Generated {formatArtifactDate(data?.generated_at)}</span>
      </div>
      <div className="release-switch hero-release-switch" role="group" aria-label="Benchmark release family">
        <button
          type="button"
          aria-pressed={releaseView === "core"}
          onClick={() => onReleaseViewChange("core")}
        >
          Core v0.4
        </button>
        <button
          type="button"
          aria-pressed={releaseView === "imaging"}
          onClick={() => onReleaseViewChange("imaging")}
        >
          Imaging
        </button>
        <button
          type="button"
          aria-pressed={releaseView === "tg263"}
          onClick={() => onReleaseViewChange("tg263")}
        >
          TG-263
        </button>
        <button
          type="button"
          aria-pressed={releaseView === "real"}
          onClick={() => onReleaseViewChange("real")}
        >
          Real-data pilot
        </button>
      </div>
      <div className="release-decision">
        <div className="hero-copy">
          <div className="release-title-row">
            <div>
              <p className="hero-release-title">{normalizeReleaseTitle(data?.release.title, releaseView)}</p>
              <h1>What this release can support</h1>
            </div>
            <span className={`release-maturity ${boundary.tone}`}>{boundary.status}</span>
          </div>
          <p className="hero-body">{boundary.allowed}</p>
          <p className="claim-prohibited"><strong>Cannot support:</strong> {boundary.prohibited}</p>
          <div className="hero-links" aria-label="Primary benchmark links">
            <a href="#model-index">Compare models</a>
            <a href="#forensics">Inspect failures</a>
            <a href="#methodology">Methods</a>
            <a href="/data/release_evidence.json" download>Evidence JSON</a>
            <a href={`${repoUrl}/tree/main/docs`} target="_blank" rel="noreferrer">
              Docs <ExternalLink aria-hidden="true" />
            </a>
          </div>
        </div>
        <dl className="release-facts">
          <div>
            <dt>Public tasks</dt>
            <dd>{taskCount ?? "—"}</dd>
          </div>
          <div>
            <dt>Independent families</dt>
            <dd>{familyCount ?? "Not declared"}</dd>
          </div>
          <div>
            <dt>Attempts / task</dt>
            <dd>{attempts ?? "—"}</dd>
          </div>
          <div>
            <dt>Official rows</dt>
            <dd>{rankedCount ?? "—"}</dd>
          </div>
          <div>
            <dt>Descriptive-only rows</dt>
            <dd>{reviewCount ?? "—"}</dd>
          </div>
          <div>
            <dt>Human baseline</dt>
            <dd>{humanBaselineLabel(releaseEvidence, releaseEvidenceLoaded)}</dd>
          </div>
          <div>
            <dt>Interaction depth</dt>
            <dd>{releaseEvidence ? interactionDepthLabel(releaseEvidence.interaction.depth) : releaseEvidenceLoaded ? "Evidence unavailable" : "Loading evidence…"}</dd>
          </div>
        </dl>
      </div>
      <div className="contract-note" aria-label="Benchmark contract notes">
        <span>Official ranks compare only identical frozen harness groups.</span>
        <span>Complete native runs receive a visible descriptive outcome order.</span>
        <span>Unavailable latency or token telemetry remains unavailable, never zero-filled.</span>
        <span>Research benchmark only. No autonomous clinical authority.</span>
      </div>
    </section>
  );
}

function humanBaselineLabel(releaseEvidence: ReleaseEvidence | null, releaseEvidenceLoaded: boolean) {
  if (!releaseEvidence) return releaseEvidenceLoaded ? "Evidence unavailable" : "Loading evidence…";
  return countStateLabel(releaseEvidence.evidence.human_baseline);
}

function fallbackReleaseId(releaseView: ReleaseView) {
  return releaseIdForView(releaseView);
}

function releaseBoundary(releaseEvidence: ReleaseEvidence | null, releaseEvidenceLoaded: boolean) {
  if (!releaseEvidenceLoaded) return {
    status: "loading-evidence",
    tone: "loading",
    allowed: "Loading the canonical release-evidence record before presenting maturity and validation claims.",
    prohibited: "Claims remain pending until the release-evidence record has loaded.",
  };
  if (!releaseEvidence) return {
    status: "evidence-unavailable",
    tone: "bad",
    allowed: "Release-level claim evidence could not be loaded. Scores remain visible as artifacts, but no maturity or validation claim is inferred.",
    prohibited: "Any claim that depends on review, human-baseline, holdout, audit, or workflow evidence until the canonical evidence record is available.",
  };
  return {
    status: maturityLabel(releaseEvidence.maturity),
    tone: releaseEvidence.maturity === "externally_replicated"
      ? "good"
      : releaseEvidence.maturity === "protected_comparison" || releaseEvidence.maturity === "human_baselined" || releaseEvidence.maturity === "domain_reviewed"
        ? "neutral"
        : "warn",
    allowed: evidenceClaimText(releaseEvidence.claim_boundary.allowed),
    prohibited: evidenceClaimText(releaseEvidence.claim_boundary.prohibited),
  };
}

function formatArtifactDate(value: string | undefined) {
  if (!value) return "artifact date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "artifact date unavailable";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}
