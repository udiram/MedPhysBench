"use client";

import { startTransition, useEffect, useState } from "react";
import { EvidenceSections } from "./components/EvidenceSections";
import { EfficiencyExplorer } from "./components/EfficiencyExplorer";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { LeaderboardExplorer } from "./components/LeaderboardExplorer";
import { useLeaderboard } from "./hooks/useLeaderboard";
import type { AccessStatus, ReleaseView } from "./types";

const LEADERBOARD_URL = "/data/leaderboard.json";
const IMAGING_LEADERBOARD_URL = "/data/imaging_leaderboard.json";
const TG263_LEADERBOARD_URL = "/data/tg263_leaderboard.json";
const ACCESS_STATUS_URL = "/data/access_status.json";
const REPO_URL = "https://github.com/udiram/MedPhysBench";

function App() {
  const core = useLeaderboard(LEADERBOARD_URL);
  const imaging = useLeaderboard(IMAGING_LEADERBOARD_URL);
  const tg263 = useLeaderboard(TG263_LEADERBOARD_URL);
  const [accessStatus, setAccessStatus] = useState<AccessStatus[]>([]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [releaseView, setReleaseView] = useState<ReleaseView>("core");
  const selected = releaseView === "core" ? core : releaseView === "tg263" ? tg263 : imaging;

  useEffect(() => {
    fetch(ACCESS_STATUS_URL)
      .then((response) => (response.ok ? (response.json() as Promise<AccessStatus[]>) : []))
      .then((payload) => {
        startTransition(() => setAccessStatus(payload));
      })
      .catch(() => setAccessStatus([]));
  }, []);

  return (
    <div className="site-shell">
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
        <Hero coreData={core.data} imagingData={imaging.data} repoUrl={REPO_URL} />
        <LeaderboardExplorer
          data={selected.data}
          accessStatus={releaseView === "core" ? accessStatus : []}
          loadError={selected.loadError}
          releaseView={releaseView}
          onReleaseViewChange={setReleaseView}
        />
        <EfficiencyExplorer data={selected.data} releaseView={releaseView} />
        <EvidenceSections data={core.data} accessStatus={accessStatus} />
      </main>
      <footer className="site-footer">
        <p>MedPhysBench is a research and evaluation platform. It is not a clinical decision-support system.</p>
        <p>
          Release artifacts, writeups, and contribution guidance live in{" "}
          <a href={`${REPO_URL}/tree/main/docs`} target="_blank" rel="noreferrer">the repository documentation</a>.
        </p>
      </footer>
    </div>
  );
}

export default App;
