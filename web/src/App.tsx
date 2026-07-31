"use client";

import { startTransition, useEffect, useState } from "react";
import { EvidenceSections } from "./components/EvidenceSections";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { LeaderboardExplorer } from "./components/LeaderboardExplorer";
import { useLeaderboard } from "./hooks/useLeaderboard";
import type { AccessStatus, Leaderboard } from "./types";

const LEADERBOARD_URL = "/data/leaderboard.json";
const ACCESS_STATUS_URL = "/data/access_status.json";
const REPO_URL = "https://github.com/udiram/MedPhysBench";

function App() {
  const { data, loadError } = useLeaderboard(LEADERBOARD_URL);
  const [accessStatus, setAccessStatus] = useState<AccessStatus[]>([]);
  const [mobileOpen, setMobileOpen] = useState(false);

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
        <Hero data={data} repoUrl={REPO_URL} />
        <LeaderboardExplorer data={data} accessStatus={accessStatus} loadError={loadError} />
        <EvidenceSections data={data} accessStatus={accessStatus} />
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
