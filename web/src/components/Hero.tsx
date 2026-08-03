import { ExternalLink } from "lucide-react";
import type { Leaderboard, ReleaseView, ReviewEvidence } from "../types";

type HeroProps = {
  data: Leaderboard | null;
  onReleaseViewChange: (value: ReleaseView) => void;
  releaseView: ReleaseView;
  reviewEvidence: ReviewEvidence | null;
  repoUrl: string;
};

export function Hero({ data, onReleaseViewChange, releaseView, reviewEvidence, repoUrl }: HeroProps) {
  const rankedCount = data ? data.integrity?.ranked_model_count ?? data.models.length : null;
  const reviewCount = data ? data.integrity?.unranked_model_count ?? data.unranked_models?.length ?? 0 : null;
  const taskCount = data?.tasks.length ?? null;
  const familyCount = data?.release.family_count ?? null;
  const attempts = data?.release.expected_attempts_per_task ?? null;
  const boundary = releaseBoundary(releaseView);

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
              <p className="hero-release-title">{data?.release.title ?? fallbackReleaseTitle(releaseView)}</p>
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
            <dt>Native outcome rows</dt>
            <dd>{reviewCount ?? "—"}</dd>
          </div>
          <div>
            <dt>Human baseline</dt>
            <dd>{humanBaselineLabel(releaseView, reviewEvidence)}</dd>
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

function humanBaselineLabel(releaseView: ReleaseView, reviewEvidence: ReviewEvidence | null) {
  if (releaseView !== "real") return "Not published";
  if (!reviewEvidence) return "Evidence unavailable";
  const state = reviewEvidence.human_baseline;
  if (state.status === "complete") return `${state.completed}/${state.target} complete`;
  return `${state.completed}/${state.target} · ${state.status}`;
}

function fallbackReleaseId(releaseView: ReleaseView) {
  if (releaseView === "core") return "public-core-v0.4";
  if (releaseView === "imaging") return "public-imaging-pilot-v0.4";
  if (releaseView === "tg263") return "public-tg263-pilot-v0.5";
  return "public-real-workflows-pilot-v0.6";
}

function fallbackReleaseTitle(releaseView: ReleaseView) {
  if (releaseView === "core") return "MedPhysBench Public Core v0.4";
  if (releaseView === "imaging") return "MedPhysBench Imaging Pilot";
  if (releaseView === "tg263") return "MedPhysBench Public TG-263 Pilot v0.5";
  return "MedPhysBench OpenKBP Real-Workflow Pilot v0.6";
}

function releaseBoundary(releaseView: ReleaseView) {
  if (releaseView === "real") return {
    status: "public-pilot",
    tone: "warn",
    allowed: "Repeated-trial, research-only comparison on two pinned OpenKBP patient families within identical frozen harness groups.",
    prohibited: "clinical validation, autonomous treatment planning, ten independent-patient claims, or human-level performance.",
  };
  if (releaseView === "tg263") return {
    status: "public-development",
    tone: "warn",
    allowed: "Public development evidence for collision-aware TG-263 decisions and grader-contract auditing.",
    prohibited: "cross-surface native ranking, clinical naming approval, or treatment-system validation.",
  };
  if (releaseView === "imaging") return {
    status: "public-pilot",
    tone: "neutral",
    allowed: "Research-only imaging and segmentation evidence on frozen public fixtures and native-image task contracts.",
    prohibited: "diagnostic validation, clinical contouring authority, or claims of prospective reader performance.",
  };
  return {
    status: "public-development",
    tone: "neutral",
    allowed: "Development and regression evidence across calculations, bounded interpretation, artifact checks, and escalation behavior.",
    prohibited: "contamination-resistant frontier ranking, clinical competence, or human-level performance.",
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
