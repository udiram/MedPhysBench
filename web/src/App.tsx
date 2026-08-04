"use client";

import { startTransition, useCallback, useEffect, useState } from "react";
import { REPO_URL } from "./content";
import { CapabilityExplorer } from "./components/CapabilityExplorer";
import { AtAGlanceLeaderboard } from "./components/AtAGlanceLeaderboard";
import { EvalCatalogPage } from "./components/EvalCatalogPage";
import { EvidenceSections } from "./components/EvidenceSections";
import { EfficiencyExplorer } from "./components/EfficiencyExplorer";
import { Header } from "./components/Header";
import { HumanBenchmarkPage } from "./components/HumanBenchmarkPage";
import { LeaderboardExplorer } from "./components/LeaderboardExplorer";
import { OverviewPage } from "./components/OverviewPage";
import { PageIntro } from "./components/PageIntro";
import { ReleaseSelector } from "./components/ReleaseSelector";
import { ResultForensics } from "./components/ResultForensics";
import { ResultsScopeBar } from "./components/ResultsScopeBar";
import { RunBenchmarkPage } from "./components/RunBenchmarkPage";
import { useLeaderboard } from "./hooks/useLeaderboard";
import { releaseEvidenceFor, releaseIdForView } from "./lib/releaseEvidence";
import { versionedDataUrl } from "./lib/dataAssets";
import type { ResultsScope } from "./lib/resultsScope";
import { readEnumParam, setUrlParams } from "./lib/urlState";
import type { AccessStatus, DefectLedger, FleetStatus, ItemDiagnosticsArtifact, ModelCatalogEntry, PublicTaskInputCatalog, ReleaseEvidenceIndex, ReleaseView, ReviewEvidence, Tg263Audit } from "./types";

const LEADERBOARD_URL = versionedDataUrl("/data/leaderboard.json");
const IMAGING_LEADERBOARD_URL = versionedDataUrl("/data/imaging_leaderboard.json");
const REAL_WORKFLOWS_LEADERBOARD_URL = versionedDataUrl("/data/public-real-workflows-pilot-v0.6.json");
const TG263_LEADERBOARD_URL = versionedDataUrl("/data/tg263_leaderboard.json");
const TG263_AUDIT_URL = versionedDataUrl("/data/public-tg263-pilot-v0.5-audit.json");
const ACCESS_STATUS_URL = versionedDataUrl("/data/access_status.json");
const MODEL_CATALOG_URL = versionedDataUrl("/data/model_catalog.json");
const FLEET_STATUS_URL = versionedDataUrl("/data/fleet_status.json");
const RELEASE_EVIDENCE_URL = versionedDataUrl("/data/release_evidence.json");
const DEFECT_LEDGER_URL = versionedDataUrl("/data/benchmark-defects.json");
const REAL_WORKFLOWS_REVIEW_URL = versionedDataUrl("/data/public-real-workflows-pilot-v0.6-review.json");
const PUBLIC_TASK_INPUTS_URL = versionedDataUrl("/data/public_task_inputs.json");
const REAL_WORKFLOWS_DIAGNOSTICS_URL = versionedDataUrl("/data/public-real-workflows-pilot-v0.6-diagnostics.json");

export type AppPage = "overview" | "results" | "evals" | "explore" | "humans" | "run" | "methods";

type AppProps = {
  page?: AppPage;
};

function App({ page = "overview" }: AppProps) {
  const core = useLeaderboard(LEADERBOARD_URL);
  const imaging = useLeaderboard(IMAGING_LEADERBOARD_URL);
  const realWorkflows = useLeaderboard(REAL_WORKFLOWS_LEADERBOARD_URL);
  const tg263 = useLeaderboard(TG263_LEADERBOARD_URL);
  const [tg263Audit, setTg263Audit] = useState<Tg263Audit | null>(null);
  const [accessStatus, setAccessStatus] = useState<AccessStatus[]>([]);
  const [modelCatalog, setModelCatalog] = useState<ModelCatalogEntry[]>([]);
  const [fleetStatus, setFleetStatus] = useState<FleetStatus | null>(null);
  const [releaseEvidenceIndex, setReleaseEvidenceIndex] = useState<ReleaseEvidenceIndex | null>(null);
  const [realWorkflowReview, setRealWorkflowReview] = useState<ReviewEvidence | null>(null);
  const [realWorkflowReviewLoaded, setRealWorkflowReviewLoaded] = useState(false);
  const [defectLedger, setDefectLedger] = useState<DefectLedger | null>(null);
  const [publicTaskInputs, setPublicTaskInputs] = useState<PublicTaskInputCatalog | null>(null);
  const [publicTaskInputsLoaded, setPublicTaskInputsLoaded] = useState(false);
  const [realWorkflowDiagnostics, setRealWorkflowDiagnostics] = useState<ItemDiagnosticsArtifact | null>(null);
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
    if (page !== "evals") return;
    const controller = new AbortController();
    fetch(REAL_WORKFLOWS_DIAGNOSTICS_URL, { signal: controller.signal })
      .then((response) => (response.ok ? (response.json() as Promise<ItemDiagnosticsArtifact>) : null))
      .then((payload) => startTransition(() => setRealWorkflowDiagnostics(payload)))
      .catch(() => {
        if (!controller.signal.aborted) setRealWorkflowDiagnostics(null);
      });
    return () => controller.abort();
  }, [page]);

  useEffect(() => {
    const controller = new AbortController();
    fetch(PUBLIC_TASK_INPUTS_URL, { signal: controller.signal })
      .then((response) => (response.ok ? (response.json() as Promise<PublicTaskInputCatalog>) : null))
      .then((payload) => startTransition(() => setPublicTaskInputs(payload)))
      .catch(() => {
        if (!controller.signal.aborted) setPublicTaskInputs(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setPublicTaskInputsLoaded(true);
      });
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
      .then((payload) => startTransition(() => setRealWorkflowReview(payload)))
      .catch(() => {
        if (!controller.signal.aborted) setRealWorkflowReview(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setRealWorkflowReviewLoaded(true);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetch(RELEASE_EVIDENCE_URL, { signal: controller.signal })
      .then((response) => (response.ok ? (response.json() as Promise<ReleaseEvidenceIndex>) : null))
      .then((payload) => startTransition(() => setReleaseEvidenceIndex(payload)))
      .catch(() => {
        if (!controller.signal.aborted) setReleaseEvidenceIndex(null);
      })
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

  const closeMobileNavigation = useCallback(() => setMobileOpen(false), []);
  const toggleMobileNavigation = useCallback(() => setMobileOpen((value) => !value), []);

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
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <Header
        currentPage={page}
        mobileOpen={mobileOpen}
        onToggle={toggleMobileNavigation}
        onClose={closeMobileNavigation}
        repoUrl={REPO_URL}
      />
      <main id="main-content" tabIndex={-1}>
        {page === "overview" ? (
          <OverviewPage
            data={realWorkflows.data}
            fleetStatus={fleetStatus}
            modelCatalog={modelCatalog}
            releaseEvidence={releaseEvidenceFor(releaseEvidenceIndex, releaseIdForView("real"))}
            reviewEvidence={realWorkflowReview}
          />
        ) : null}
        {page === "results" ? (
          <>
            <ReleaseSelector data={selected.data} onChange={handleReleaseViewChange} value={releaseView} />
            <ResultsScopeBar data={selected.data} onChange={handleResultsScopeChange} value={resultsScope} />
            <AtAGlanceLeaderboard data={selected.data} modelCatalog={modelCatalog} resultsScope={resultsScope} />
            <details className="full-analysis-disclosure">
              <summary>
                <span>Open full analysis</span>
                <small>Intervals, filters, domain scores, time, tokens, and downloadable evidence</small>
              </summary>
              <div>
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
              </div>
            </details>
          </>
        ) : null}
        {page === "evals" ? (
          <>
            <PageIntro
              title="The evals"
              description="Browse the released medical-physics tasks, inspect the sealed input a model receives, and jump directly to scored answers."
              actions={<a className="secondary-action" href="/explore">Compare model answers</a>}
            />
            <ReleaseSelector data={selected.data} onChange={handleReleaseViewChange} value={releaseView} />
            <EvalCatalogPage
              catalog={publicTaskInputs}
              catalogLoaded={publicTaskInputsLoaded}
              data={selected.data}
              diagnostics={realWorkflowDiagnostics}
              releaseView={releaseView}
            />
          </>
        ) : null}
        {page === "explore" ? (
          <>
            <ReleaseSelector data={selected.data} onChange={handleReleaseViewChange} value={releaseView} />
            <ResultsScopeBar data={selected.data} onChange={handleResultsScopeChange} value={resultsScope} />
            <ResultForensics
              data={selected.data}
              defectLedger={defectLedger}
              modelCatalog={modelCatalog}
              releaseView={releaseView}
              reviewEvidence={releaseView === "real" ? realWorkflowReview : null}
              reviewEvidenceLoaded={releaseView === "real" ? realWorkflowReviewLoaded : true}
              resultsScope={resultsScope}
              releaseEvidence={selectedEvidence}
              taskInputCatalog={publicTaskInputs}
              taskInputCatalogLoaded={publicTaskInputsLoaded}
            />
          </>
        ) : null}
        {page === "humans" ? <HumanBenchmarkPage releaseEvidence={releaseEvidenceFor(releaseEvidenceIndex, releaseIdForView("real"))} /> : null}
        {page === "run" ? <RunBenchmarkPage fleetStatus={fleetStatus} /> : null}
        {page === "methods" ? (
          <>
            <PageIntro
              title="Methods and evidence"
              description="Release maturity, task coverage, uncertainty, benchmark defects, claim boundaries, and public governance evidence."
            />
            <ReleaseSelector data={selected.data} onChange={handleReleaseViewChange} value={releaseView} />
            <CapabilityExplorer
              data={selected.data}
              loadError={selected.loadError}
              releaseView={releaseView}
              modelCatalog={modelCatalog}
              releaseEvidence={selectedEvidence}
              resultsScope={resultsScope}
            />
            <EvidenceSections
              accessStatus={accessStatus}
              data={selected.data}
              defectLedger={defectLedger}
              releaseView={releaseView}
              releaseEvidence={selectedEvidence}
            />
          </>
        ) : null}
      </main>
      <footer className="site-footer">
        <p>MedPhysBench is a research and evaluation platform. It is not a clinical decision-support system.</p>
        <p>
          <a href="/methods">Methods and evidence</a> · Release artifacts, writeups, and contribution guidance live in{" "}
          <a href={`${REPO_URL}/tree/main/docs`} target="_blank" rel="noreferrer">
            the repository documentation
          </a>.
        </p>
      </footer>
    </div>
  );
}

export default App;
