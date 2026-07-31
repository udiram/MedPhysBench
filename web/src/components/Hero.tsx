import { ArrowRight, ExternalLink } from "lucide-react";
import type { Leaderboard } from "../types";

type HeroProps = {
  coreData: Leaderboard | null;
  imagingData: Leaderboard | null;
  repoUrl: string;
};

export function Hero({ coreData, imagingData, repoUrl }: HeroProps) {
  const rankedCount = coreData?.integrity?.ranked_model_count ?? coreData?.models.length ?? 0;

  return (
    <section className="hero" id="top">
      <div className="release-rail" aria-label="Current release summary">
        <span>{coreData?.tasks.length ?? 64} core tasks</span>
        <span>{imagingData?.tasks.length ?? 5} real-image pilot tasks</span>
        <span>{rankedCount} common-harness ranks</span>
        <span>research evaluation only</span>
      </div>
      <div className="hero-copy">
        <h1>Can AI do the work—and know when to stop?</h1>
        <p className="hero-body">
          A reproducible benchmark for medical-physics reasoning, tools, artifacts, and safe escalation.
        </p>
        <div className="hero-actions">
          <a className="button button-primary" href="#leaderboard">
            View leaderboard <ArrowRight aria-hidden="true" />
          </a>
          <a className="button button-secondary" href={`${repoUrl}/blob/main/docs/BENCHMARK_PAPER.md`} target="_blank" rel="noreferrer">
            Read the benchmark paper <ExternalLink aria-hidden="true" />
          </a>
        </div>
        <div className="contract-note" aria-label="Benchmark contract notes">
          <span>Only complete, internally consistent run sets receive a public rank.</span>
          <span>Gold answers, graders, and provenance remain outside the evaluated runtime.</span>
        </div>
      </div>
    </section>
  );
}
