"use client";

import { startTransition, useEffect, useState } from "react";
import { REPO_URL } from "./content";
import { CapabilityExplorer } from "./components/CapabilityExplorer";
import { EvidenceSections } from "./components/EvidenceSections";
import { EfficiencyExplorer } from "./components/EfficiencyExplorer";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { LeaderboardExplorer } from "./components/LeaderboardExplorer";
import { PublicModelIndex } from "./components/PublicModelIndex";
import { useLeaderboard } from "./hooks/useLeaderboard";
import type { AccessStatus, ModelCatalogEntry, ReleaseView, Tg263Audit } from "./types";

const LEADERBOARD_URL = "/data/leaderboard.json";
const IMAGING_LEADERBOARD_URL = "/data/imaging_leaderboard.json";
const REAL_WORKFLOWS_LEADERBOARD_URL = "/data/public-real-workflows-pilot-v0.6.json";
const TG263_LEADERBOARD_URL = "/data/tg263_leaderboard.json";
const TG263_AUDIT_URL = "/data/public-tg263-pilot-v0.5-audit.json";
const ACCESS_STATUS_URL = "/data/access_status.json";
const MODEL_CATALOG_URL = "/data/model_catalog.json";

function App() {
  const core = useLeaderboard(LEADERBOARD_URL);
  const imaging = useLeaderboard(IMAGING_LEADERBOARD_URL);
  const realWorkflows = useLeaderboard(REAL_WORKFLOWS_LEADERBOARD_URL);
  const tg263 = useLeaderboard(TG263_LEADERBOARD_URL);
  const [tg263Audit, setTg263Audit] = useState<Tg263Audit | null>(null);
  const [accessStatus, setAccessStatus] = useState<AccessStatus[]>([]);
  const [modelCatalog, setModelCatalog] = useState<ModelCatalogEntry[]>([]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [releaseView, setReleaseView] = useState<ReleaseView>("core");
  const selected =
    releaseView === "core"
      ? core
      : releaseView === "imaging"
        ? imaging
        : releaseView === "tg263"
          ? tg263
          : realWorkflows;

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

  useEffect(() => {
    const controller = new AbortController();
    fetch(MODEL_CATALOG_URL, { signal: controller.signal })
      .then((response) => (response.ok ? (response.json() as Promise<ModelCatalogEntry[]>) : []))
      .then((payload) => {
        startTransition(() => setModelCatalog(payload));
      })
      .catch(() => setModelCatalog([]));
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
        <PublicModelIndex
          catalog={modelCatalog}
          datasets={[
            { key: "core", label: "Core v0.4", data: core.data },
            { key: "imaging", label: "Imaging pilot", data: imaging.data },
            { key: "tg263", label: "TG-263 pilot", data: tg263.data },
            { key: "real", label: "OpenKBP real-workflow pilot", data: realWorkflows.data },
          ]}
        />
        <LeaderboardExplorer
          data={selected.data}
          accessStatus={accessStatus}
          modelCatalog={modelCatalog}
          loadError={selected.loadError}
          releaseView={releaseView}
          tg263Audit={tg263Audit}
        />
        <CapabilityExplorer
          data={selected.data}
          loadError={selected.loadError}
          releaseView={releaseView}
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
