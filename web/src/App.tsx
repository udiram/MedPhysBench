"use client";

import { startTransition, useEffect, useState } from "react";
import { REPO_URL } from "./content";
import { EvidenceSections } from "./components/EvidenceSections";
import { EfficiencyExplorer } from "./components/EfficiencyExplorer";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { LeaderboardExplorer } from "./components/LeaderboardExplorer";
import { useLeaderboard } from "./hooks/useLeaderboard";
import type { AccessStatus, ReleaseView, Tg263Audit } from "./types";

const LEADERBOARD_URL = "/data/leaderboard.json";
const REAL_WORKFLOWS_LEADERBOARD_URL = "/data/public-real-workflows-pilot-v0.6.json";
const TG263_LEADERBOARD_URL = "/data/tg263_leaderboard.json";
const TG263_AUDIT_URL = "/data/public-tg263-pilot-v0.5-audit.json";
const ACCESS_STATUS_URL = "/data/access_status.json";

function App() {
  const core = useLeaderboard(LEADERBOARD_URL);
  const realWorkflows = useLeaderboard(REAL_WORKFLOWS_LEADERBOARD_URL);
  const tg263 = useLeaderboard(TG263_LEADERBOARD_URL);
  const [tg263Audit, setTg263Audit] = useState<Tg263Audit | null>(null);
  const [accessStatus, setAccessStatus] = useState<AccessStatus[]>([]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [releaseView, setReleaseView] = useState<ReleaseView>("real");
  const selected = releaseView === "core" ? core : releaseView === "tg263" ? tg263 : realWorkflows;

  useEffect(() => {
    const controller = new AbortController();
    fetch(TG263_AUDIT_URL, { signal: controller.signal })
      .then((response) => (response.ok ? (response.json() as Promise<Tg263Audit>) : null))
      .then((payload) => {
        if (payload) {
          startTransition(() => setTg263Audit(payload));
        }
      })
      .catch(() => setTg263Audit(null));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetch(ACCESS_STATUS_URL, { signal: controller.signal })
      .then((response) => (response.ok ? (response.json() as Promise<AccessStatus[]>) : []))
      .then((payload) => {
        startTransition(() => setAccessStatus(payload));
      })
      .catch(() => setAccessStatus([]));
    return () => controller.abort();
  }, []);

  return (
    <div className="site-shell" id="top">
      <a className="skip-link" href="#leaderboard">
        Skip to leaderboard
      </a>
      <Header
        mobileOpen={mobileOpen}
        onToggle={() => setMobileOpen((value) => !value)}
        onClose={() => setMobileOpen(false)}
        repoUrl={REPO_URL}
      />
      <main>
        <Hero
          data={selected.data}
          onReleaseViewChange={setReleaseView}
          releaseView={releaseView}
          repoUrl={REPO_URL}
        />
        <LeaderboardExplorer
          data={selected.data}
          accessStatus={accessStatus}
          loadError={selected.loadError}
          releaseView={releaseView}
          tg263Audit={tg263Audit}
        />
        <EfficiencyExplorer data={selected.data} releaseView={releaseView} />
        <EvidenceSections
          accessStatus={accessStatus}
          data={selected.data}
          releaseView={releaseView}
        />
      </main>
      <footer className="site-footer">
        <p>MedPhysBench is a research and evaluation platform. It is not a clinical decision-support system.</p>
        <p>
          Release artifacts, writeups, and contribution guidance live in{" "}
          <a href={`${REPO_URL}/tree/main/docs`} target="_blank" rel="noreferrer">
            the repository documentation
          </a>.
        </p>
      </footer>
    </div>
  );
}

export default App;
