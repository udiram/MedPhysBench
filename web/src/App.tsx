"use client";

import { startTransition, useEffect, useState } from "react";
import { REPO_URL } from "./content";
import { CapabilityExplorer } from "./components/CapabilityExplorer";
import { EvidenceSections } from "./components/EvidenceSections";
import { EfficiencyExplorer } from "./components/EfficiencyExplorer";
import { FleetCoverage } from "./components/FleetCoverage";
import { Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { LeaderboardExplorer } from "./components/LeaderboardExplorer";
import { PublicModelIndex } from "./components/PublicModelIndex";
import { ResultForensics } from "./components/ResultForensics";
import { useLeaderboard } from "./hooks/useLeaderboard";
import { readEnumParam, setUrlParams } from "./lib/urlState";
import type { AccessStatus, DefectLedger, FleetStatus, ModelCatalogEntry, ReleaseView, ReviewEvidence, Tg263Audit } from "./types";

const LEADERBOARD_URL = "/data/leaderboard.json";
const IMAGING_LEADERBOARD_URL = "/data/imaging_leaderboard.json";
const REAL_WORKFLOWS_LEADERBOARD_URL = "/data/public-real-workflows-pilot-v0.6.json";
const TG263_LEADERBOARD_URL = "/data/tg263_leaderboard.json";
const TG263_AUDIT_URL = "/data/public-tg263-pilot-v0.5-audit.json";
const ACCESS_STATUS_URL = "/data/access_status.json";
const MODEL_CATALOG_URL = "/data/model_catalog.json";
const FLEET_STATUS_URL = "/data/fleet_status.json";
const REAL_WORKFLOWS_REVIEW_URL = "/data/public-real-workflows-pilot-v0.6-review.json";
const DEFECT_LEDGER_URL = "/data/benchmark-defects.json";

function App() {
  const core = useLeaderboard(LEADERBOARD_URL);
  const imaging = useLeaderboard(IMAGING_LEADERBOARD_URL);
  const realWorkflows = useLeaderboard(REAL_WORKFLOWS_LEADERBOARD_URL);
  const tg263 = useLeaderboard(TG263_LEADERBOARD_URL);
  const [tg263Audit, setTg263Audit] = useState<Tg263Audit | null>(null);
  const [accessStatus, setAccessStatus] = useState<AccessStatus[]>([]);
  const [modelCatalog, setModelCatalog] = useState<ModelCatalogEntry[]>([]);
  const [fleetStatus, setFleetStatus] = useState<FleetStatus | null>(null);
  const [realWorkflowsReview, setRealWorkflowsReview] = useState<ReviewEvidence | null>(null);
  const [defectLedger, setDefectLedger] = useState<DefectLedger | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [releaseView, setReleaseView] = useState<ReleaseView>("real");
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
    fetch(DEFECT_LEDGER_URL, { signal: controller.signal })
      .then((response) => (response.ok ? (response.json() as Promise<DefectLedger>) : null))
      .then((payload) => startTransition(() => setDefectLedger(payload)))
      .catch(() => setDefectLedger(null));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetch(REAL_WORKFLOWS_REVIEW_URL, { signal: controller.signal })
      .then((response) => (response.ok ? (response.json() as Promise<ReviewEvidence>) : null))
      .then((payload) => startTransition(() => setRealWorkflowsReview(payload)))
      .catch(() => setRealWorkflowsReview(null));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetch(FLEET_STATUS_URL, { signal: controller.signal })
      .then((response) => (response.ok ? (response.json() as Promise<FleetStatus>) : null))
      .then((payload) => startTransition(() => setFleetStatus(payload)))
      .catch(() => setFleetStatus(null));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handlePopState = () => {
      setReleaseView(readEnumParam("release", ["core", "imaging", "tg263", "real"] as const, "real"));
    };
    handlePopState();
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const handleReleaseViewChange = (value: ReleaseView) => {
    setReleaseView(value);
    setUrlParams({ release: value === "real" ? null : value }, { history: "push" });
  };

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
          onReleaseViewChange={handleReleaseViewChange}
          releaseView={releaseView}
          reviewEvidence={releaseView === "real" ? realWorkflowsReview : null}
          repoUrl={REPO_URL}
        />
        <FleetCoverage data={fleetStatus} />
        <PublicModelIndex
          catalog={modelCatalog}
          fleetStatus={fleetStatus}
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
          modelCatalog={modelCatalog}
          reviewEvidence={releaseView === "real" ? realWorkflowsReview : null}
        />
        <ResultForensics
          data={selected.data}
          defectLedger={defectLedger}
          modelCatalog={modelCatalog}
          releaseView={releaseView}
        />
        <EfficiencyExplorer
          data={selected.data}
          modelCatalog={modelCatalog}
          releaseView={releaseView}
        />
        <EvidenceSections
          accessStatus={accessStatus}
          data={selected.data}
          defectLedger={defectLedger}
          releaseView={releaseView}
          reviewEvidence={releaseView === "real" ? realWorkflowsReview : null}
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
