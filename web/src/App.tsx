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
import { ResultsScopeBar } from "./components/ResultsScopeBar";
import { useLeaderboard } from "./hooks/useLeaderboard";
import { releaseEvidenceFor, releaseIdForView } from "./lib/releaseEvidence";
import type { ResultsScope } from "./lib/resultsScope";
import { readEnumParam, setUrlParams } from "./lib/urlState";
import type { AccessStatus, DefectLedger, FleetStatus, ModelCatalogEntry, ReleaseEvidenceIndex, ReleaseView, Tg263Audit } from "./types";

const LEADERBOARD_URL = "/data/leaderboard.json";
const IMAGING_LEADERBOARD_URL = "/data/imaging_leaderboard.json";
const REAL_WORKFLOWS_LEADERBOARD_URL = "/data/public-real-workflows-pilot-v0.6.json";
const TG263_LEADERBOARD_URL = "/data/tg263_leaderboard.json";
const TG263_AUDIT_URL = "/data/public-tg263-pilot-v0.5-audit.json";
const ACCESS_STATUS_URL = "/data/access_status.json";
const MODEL_CATALOG_URL = "/data/model_catalog.json";
const FLEET_STATUS_URL = "/data/fleet_status.json";
const RELEASE_EVIDENCE_URL = "/data/release_evidence.json";
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
  const [releaseEvidenceIndex, setReleaseEvidenceIndex] = useState<ReleaseEvidenceIndex | null>(null);
  const [defectLedger, setDefectLedger] = useState<DefectLedger | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [releaseView, setReleaseView] = useState<ReleaseView>("real");
  const [resultsScope, setResultsScope] = useState<ResultsScope>("descriptive");
  const selected =
    releaseView === "core"
      ? core
      : releaseView === "imaging"
        ? imaging
        : releaseView === "tg263"
          ? tg263
          : realWorkflows;
  const selectedReleaseId = selected.data?.release.release_id ?? releaseIdForView(releaseView);
  const selectedEvidence = releaseEvidenceFor(releaseEvidenceIndex, selectedReleaseId);

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
    fetch(RELEASE_EVIDENCE_URL, { signal: controller.signal })
      .then((response) => (response.ok ? (response.json() as Promise<ReleaseEvidenceIndex>) : null))
      .then((payload) => startTransition(() => setReleaseEvidenceIndex(payload)))
      .catch(() => setReleaseEvidenceIndex(null));
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
      setResultsScope(readEnumParam("results_scope", ["descriptive", "official"] as const, "descriptive"));
    };
    handlePopState();
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const handleReleaseViewChange = (value: ReleaseView) => {
    setReleaseView(value);
    setUrlParams({ release: value === "real" ? null : value }, { history: "push" });
  };

  const handleResultsScopeChange = (value: ResultsScope) => {
    setResultsScope(value);
    const updates: Record<string, string | null> = {
      results_scope: value === "descriptive" ? null : value,
    };
    if (value === "official") updates.fx_compare = null;
    setUrlParams(updates, { history: "push" });
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
          releaseEvidence={selectedEvidence}
          repoUrl={REPO_URL}
        />
        <PublicModelIndex
          activeRelease={releaseView}
          catalog={modelCatalog}
          fleetStatus={fleetStatus}
          datasets={[
            { key: "core", label: "Core v0.4", data: core.data },
            { key: "imaging", label: "Imaging pilot", data: imaging.data },
            { key: "tg263", label: "TG-263 pilot", data: tg263.data },
            { key: "real", label: "OpenKBP real-data workflow-view pilot", data: realWorkflows.data },
          ]}
        />
        <nav className="results-subnav" aria-label="Results views">
          <span>Results views</span>
          <a href="#leaderboard">Leaderboard</a>
          <a href="#efficiency">Plots</a>
          <a href="#forensics">Attempt forensics</a>
        </nav>
        <ResultsScopeBar data={selected.data} onChange={handleResultsScopeChange} value={resultsScope} />
        <LeaderboardExplorer
          data={selected.data}
          accessStatus={accessStatus}
          modelCatalog={modelCatalog}
          loadError={selected.loadError}
          releaseView={releaseView}
          resultsScope={resultsScope}
          tg263Audit={tg263Audit}
        />
        <EfficiencyExplorer
          data={selected.data}
          fleetStatus={fleetStatus}
          modelCatalog={modelCatalog}
          releaseView={releaseView}
          resultsScope={resultsScope}
        />
        <CapabilityExplorer
          data={selected.data}
          loadError={selected.loadError}
          releaseView={releaseView}
          modelCatalog={modelCatalog}
          releaseEvidence={selectedEvidence}
          resultsScope={resultsScope}
        />
        <ResultForensics
          data={selected.data}
          defectLedger={defectLedger}
          modelCatalog={modelCatalog}
          releaseView={releaseView}
          resultsScope={resultsScope}
        />
        <FleetCoverage data={fleetStatus} />
        <EvidenceSections
          accessStatus={accessStatus}
          data={selected.data}
          defectLedger={defectLedger}
          releaseView={releaseView}
          releaseEvidence={selectedEvidence}
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
