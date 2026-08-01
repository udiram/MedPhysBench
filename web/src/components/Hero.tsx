import { ExternalLink } from "lucide-react";
import type { Leaderboard, ReleaseView } from "../types";

type HeroProps = {
  data: Leaderboard | null;
  onReleaseViewChange: (value: ReleaseView) => void;
  releaseView: ReleaseView;
  repoUrl: string;
};

export function Hero({ data, onReleaseViewChange, releaseView, repoUrl }: HeroProps) {
  const rankedCount = data ? data.integrity?.ranked_model_count ?? data.models.length : null;
  const reviewCount = data ? data.integrity?.unranked_model_count ?? data.unranked_models?.length ?? 0 : null;
  const taskCount = data?.tasks.length ?? null;

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
      <div className="hero-grid">
        <div className="hero-copy">
          <p className="hero-release-title">{data?.release.title ?? fallbackReleaseTitle(releaseView)}</p>
          <h1>Measure the work. Preserve the boundary.</h1>
          <p className="hero-body">{releaseSummary(releaseView)}</p>
          <div className="hero-links" aria-label="Primary benchmark links">
            <a href="#leaderboard">Results</a>
            <a href="#methodology">Methods</a>
            <a href={`${repoUrl}/tree/main/docs`} target="_blank" rel="noreferrer">
              Docs <ExternalLink aria-hidden="true" />
            </a>
          </div>
        </div>
        <dl className="hero-stats">
          <div>
            <dt>Public tasks</dt>
            <dd>{taskCount ?? "—"}</dd>
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
            <dd>Recruiting</dd>
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

function fallbackReleaseId(releaseView: ReleaseView) {
  if (releaseView === "core") return "public-core-v0.4";
  if (releaseView === "tg263") return "public-tg263-pilot-v0.5";
  return "public-real-workflows-pilot-v0.6";
}

function fallbackReleaseTitle(releaseView: ReleaseView) {
  if (releaseView === "core") return "MedPhysBench Public Core v0.4";
  if (releaseView === "tg263") return "MedPhysBench Public TG-263 Pilot v0.5";
  return "MedPhysBench OpenKBP Real-Workflow Pilot v0.6";
}

function releaseSummary(releaseView: ReleaseView) {
  if (releaseView === "core") {
    return "Research-grade medical-physics calculations, bounded interpretation, artifact checks, and escalation decisions under a common public harness.";
  }
  if (releaseView === "tg263") {
    return "A collision-heavy structure-naming pilot where audited native GPT decision quality is reported separately from benchmark-authored rationale-label exactness.";
  }
  return "Ten tasks across two pinned OpenKBP head-and-neck cases: structure localization, dose interpretation, plan-criteria audit, data integrity, and TG-263 naming. Results are provisional research evidence, not clinical validation.";
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
