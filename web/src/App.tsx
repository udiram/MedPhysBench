"use client";

import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  Code2,
  ExternalLink,
  FileCheck2,
  Github,
  LockKeyhole,
  Menu,
  ShieldAlert,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Logo } from "./Logo";
import type { Leaderboard, ModelResult } from "./types";

const DATA_URL = "/data/leaderboard.json";
const REPO_URL = "https://github.com/udiram/MedPhysBench";

const domains = [
  ["Core physics", "Foundations, units, attenuation, and dosimetry."],
  ["Radiation therapy", "Planning, delivery, brachytherapy, and radiobiology."],
  ["Imaging", "CT, MR, image quality, protocol review, and quantitative analysis."],
  ["Nuclear medicine", "Activity, decay, imaging, therapy, and contamination controls."],
  ["Radiation safety", "Protection, shielding, monitoring, and escalation."],
  ["Informatics", "DICOM, data integrity, interoperability, and automation."],
  ["Quality assurance", "Commissioning, QA/QC, trend review, and safe refusal."],
  ["Research & leadership", "Evidence synthesis, statistics, reproducibility, and claims."],
];

const workflow = [
  ["01", "Task contract", "Inputs, constraints, risk tier, artifacts, and acceptance criteria."],
  ["02", "Sealed runtime view", "Gold answers, graders, provenance, and author identity stay out."],
  ["03", "Model + sandbox", "A frozen harness controls prompts, tools, budgets, and provider identity."],
  ["04", "Deterministic grading", "Outcome, artifact, and declared state are checked without stylistic judging."],
  ["05", "Safety gate", "Critical escalation failures remain visible and cannot be averaged away."],
  ["06", "Run manifest", "Every score retains model revision, seed, hashes, latency, traces, and errors."],
];

function formatPercent(value: number | null | undefined) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function App() {
  const [data, setData] = useState<Leaderboard | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [domainFilter, setDomainFilter] = useState("all");
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    fetch(DATA_URL)
      .then((response) => {
        if (!response.ok) throw new Error("Leaderboard data unavailable");
        return response.json() as Promise<Leaderboard>;
      })
      .then(setData)
      .catch(() => setLoadError(true));
  }, []);

  const visibleModels = useMemo(() => {
    if (!data) return [];
    if (domainFilter === "all") return data.models;
    return [...data.models].sort(
      (a, b) =>
        (b.domain_safe_success[domainFilter] ?? 0) -
        (a.domain_safe_success[domainFilter] ?? 0),
    );
  }, [data, domainFilter]);

  const filterDomains = useMemo(() => {
    const values = new Set<string>();
    data?.tasks.forEach((task) => values.add(task.domain));
    return [...values].sort();
  }, [data]);

  const closeMenu = () => setMobileOpen(false);

  return (
    <div className="site-shell">
      <header className="topbar">
        <a href="#top" aria-label="MedPhysBench home" onClick={closeMenu}>
          <Logo />
        </a>
        <button
          className="menu-button"
          aria-label="Toggle navigation"
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen((value) => !value)}
        >
          {mobileOpen ? <X /> : <Menu />}
        </button>
        <nav className={mobileOpen ? "nav-links nav-open" : "nav-links"} aria-label="Primary">
          <a href="#leaderboard" onClick={closeMenu}>Leaderboard</a>
          <a href="#tasks" onClick={closeMenu}>Tasks</a>
          <a href="#methodology" onClick={closeMenu}>Methodology</a>
          <a href="#governance" onClick={closeMenu}>Governance</a>
          <a href={`${REPO_URL}/tree/main/docs`} onClick={closeMenu}>Docs</a>
          <a href={REPO_URL} target="_blank" rel="noreferrer" onClick={closeMenu}>
            <Github aria-hidden="true" /> GitHub
          </a>
        </nav>
      </header>

      <main id="top">
        <section className="hero">
          <div className="hero-copy">
            <h1>Can AI do the work—and know when to stop?</h1>
            <p>
              A reproducible benchmark for medical-physics reasoning, tools, artifacts,
              and safe escalation.
            </p>
            <div className="hero-actions">
              <a className="button button-primary" href="#leaderboard">
                View leaderboard <ArrowRight aria-hidden="true" />
              </a>
              <a className="button button-secondary" href={`${REPO_URL}/blob/main/docs/BENCHMARK_PAPER.md`}>
                Read the benchmark paper <ExternalLink aria-hidden="true" />
              </a>
            </div>
          </div>
          <div className="calibration-figure" aria-label="Abstract calibration grid">
            <div className="grid-lines" />
            <div className="axis axis-x" />
            <div className="axis axis-y" />
            <span className="ring ring-one" />
            <span className="ring ring-two" />
            <span className="ring ring-three" />
            <span className="isocenter" />
            <span className="figure-note">CALIBRATION GRID · 1 cm</span>
          </div>
        </section>

        <section className="leaderboard-section" id="leaderboard">
          <div className="section-heading section-heading-row">
            <div>
              <h2>Public leaderboard</h2>
              <p>
                Common-harness results on the open development release. Scores are
                reproducibility evidence, not clinical validation.
              </p>
            </div>
            <a className="text-link" href={DATA_URL} download>
              <ArrowDownToLine aria-hidden="true" /> Download JSON
            </a>
          </div>

          <div className="leaderboard-controls">
            <label>
              Release
              <span className="control-static">
                {data?.release.release_id ?? "Loading…"}
              </span>
            </label>
            <label>
              Domain
              <span className="select-wrap">
                <select value={domainFilter} onChange={(event) => setDomainFilter(event.target.value)}>
                  <option value="all">All domains</option>
                  {filterDomains.map((domain) => (
                    <option key={domain} value={domain}>{domain.replaceAll("_", " ")}</option>
                  ))}
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
            <div className="release-meta">
              <span>Harness</span>
              <strong>reference-json-v1</strong>
            </div>
            <div className="release-meta">
              <span>Tasks</span>
              <strong>{data?.tasks.length ?? "—"}</strong>
            </div>
          </div>

          <div className="table-frame">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Model</th>
                    <th>Overall</th>
                    <th>Safety</th>
                    <th>Output</th>
                    <th>Escalation</th>
                    <th>95% CI</th>
                    <th>Trials</th>
                    <th><span className="sr-only">Details</span></th>
                  </tr>
                </thead>
                <tbody>
                  {visibleModels.map((model, index) => (
                    <ModelRow
                      key={model.model_name}
                      model={model}
                      displayRank={domainFilter === "all" ? model.rank : index + 1}
                      expanded={expanded === model.model_name}
                      onToggle={() =>
                        setExpanded((value) => value === model.model_name ? null : model.model_name)
                      }
                    />
                  ))}
                </tbody>
              </table>
              {!data && !loadError && <div className="table-state">Loading verified run artifacts…</div>}
              {loadError && (
                <div className="table-state table-error">
                  Leaderboard artifact unavailable. See the repository for the current run package.
                </div>
              )}
            </div>
          </div>
          {data && (
            <p className="data-note">
              Generated {new Date(data.generated_at).toLocaleString()} · {data.models.length} models ·
              {" "}{data.tasks.length} public tasks · one attempt per task unless the manifest states otherwise.
            </p>
          )}
        </section>

        <section className="method-section" id="methodology">
          <div className="section-heading">
            <h2>Built around real work</h2>
            <p>
              The public release begins with auditable calculation, evidence, checklist,
              and escalation tasks. Tool-state and artifact lanes use the same contract.
            </p>
          </div>
          <ol className="workflow">
            {workflow.map(([number, title, description]) => (
              <li key={number}>
                <span>{number}</span>
                <h3>{title}</h3>
                <p>{description}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="taxonomy-section" id="tasks">
          <div className="domain-index">
            <div className="section-heading">
              <h2>Eight medical-physics domains</h2>
              <p>One framework, domain-specific acceptance criteria.</p>
            </div>
            <div className="domain-list">
              {domains.map(([title, description], index) => (
                <div className="domain-row" key={title}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{title}</strong>
                  <p>{description}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="grading-lanes">
            <div className="section-heading">
              <h2>Four grading lanes</h2>
              <p>A single average never hides a critical unsafe action.</p>
            </div>
            <div className="lane">
              <span>1</span><FileCheck2 aria-hidden="true" />
              <div><h3>Outcome</h3><p>Correct result against task-specific deterministic graders.</p></div>
            </div>
            <div className="lane">
              <span>2</span><Code2 aria-hidden="true" />
              <div><h3>Artifact / state</h3><p>Valid JSON, files, tables, and final sandbox state.</p></div>
            </div>
            <div className="lane">
              <span>3</span><ShieldAlert aria-hidden="true" />
              <div><h3>Safety / escalation</h3><p>Abstention, policy boundaries, and critical gate failures.</p></div>
            </div>
            <div className="lane">
              <span>4</span><LockKeyhole aria-hidden="true" />
              <div><h3>Reproducibility</h3><p>Frozen prompts, versions, seeds, manifests, traces, and hashes.</p></div>
            </div>
          </div>
        </section>

        <section className="governance-section" id="governance">
          <div className="boundary">
            <ShieldAlert aria-hidden="true" />
            <h2>Research benchmark, not clinical authority</h2>
            <p>
              MedPhysBench evaluates research-grade assistance and escalation behavior.
              It is not a medical device, a release-to-treat system, or evidence of
              autonomous clinical competence.
            </p>
            <div className="boundary-rule">
              No autonomous patient-specific decisions. No unapproved PHI. No live treatment control.
            </div>
          </div>
          <div className="evidence">
            <h2>Every public score ships with its evidence</h2>
            <ul>
              {[
                "Versioned task release",
                "Frozen prompt and output schemas",
                "Provider and model revision",
                "Seed and sampling parameters",
                "Deterministic grader outputs",
                "Safety-gate failures",
                "Run IDs, latency, traces, and hashes",
              ].map((item) => <li key={item}><Check aria-hidden="true" />{item}</li>)}
            </ul>
          </div>
        </section>

        <section className="contribute-section">
          <div className="section-heading">
            <h2>Contribute a task</h2>
            <p>
              Public tasks require a solvable contract, reference result, leakage review,
              and two independent domain-expert approvals before they can support claims.
            </p>
          </div>
          <div className="contribution-flow" aria-label="Task contribution workflow">
            {["Propose", "Dual expert review", "Reference run", "Leakage review", "Public or sealed release"].map(
              (step, index) => (
                <div key={step}>
                  <span>{index + 1}</span>
                  <strong>{step}</strong>
                </div>
              ),
            )}
          </div>
          <a className="button button-primary" href={`${REPO_URL}/issues`}>
            Propose a task <ArrowRight aria-hidden="true" />
          </a>
        </section>
      </main>

      <footer>
        <Logo />
        <div className="footer-links">
          <a href={REPO_URL}><Github aria-hidden="true" /> GitHub</a>
          <a href={`${REPO_URL}/tree/main/docs`}><BookOpen aria-hidden="true" /> Documentation</a>
          <a href={`${REPO_URL}/blob/main/docs/EVALUATION_PROTOCOL.md`}>Evaluation protocol</a>
          <a href={`${REPO_URL}/blob/main/docs/GOVERNANCE_AND_VALIDATION.md`}>Governance</a>
          <a href={`${REPO_URL}/blob/main/CITATION.cff`}>Citation</a>
          <a href={`${REPO_URL}/blob/main/LICENSE`}>MIT License</a>
        </div>
        <p>© 2026 MedPhysBench contributors. Research use only.</p>
      </footer>
    </div>
  );
}

function ModelRow({
  model,
  displayRank,
  expanded,
  onToggle,
}: {
  model: ModelResult;
  displayRank: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr className={expanded ? "model-row row-expanded" : "model-row"}>
        <td className="rank-cell">{displayRank}</td>
        <td>
          <strong>{model.model_name}</strong>
          <span className="cell-subtitle">{model.provider}</span>
        </td>
        <td><strong>{formatPercent(model.safe_success_rate)}</strong></td>
        <td className={model.safety_gate_rate < 1 ? "metric-alert" : ""}>
          {formatPercent(model.safety_gate_rate)}
        </td>
        <td>{formatPercent(model.valid_output_rate)}</td>
        <td>{formatPercent(model.appropriate_escalation_rate)}</td>
        <td className="ci-cell">
          {formatPercent(model.task_success_ci95[0])}–{formatPercent(model.task_success_ci95[1])}
        </td>
        <td>{model.attempt_count}</td>
        <td>
          <button
            className="row-toggle"
            aria-expanded={expanded}
            aria-label={`${expanded ? "Hide" : "Show"} details for ${model.model_name}`}
            onClick={onToggle}
          >
            <ChevronDown aria-hidden="true" />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="detail-row">
          <td colSpan={9}>
            <div className="model-detail">
              <div>
                <span>Model revision</span>
                <strong>{model.model_revision}</strong>
              </div>
              <div>
                <span>Task pass</span>
                <strong>{formatPercent(model.task_success_rate)}</strong>
              </div>
              <div>
                <span>Any pass</span>
                <strong>{formatPercent(model.any_pass_rate)}</strong>
              </div>
              <div>
                <span>All pass</span>
                <strong>{formatPercent(model.all_pass_rate)}</strong>
              </div>
              <div>
                <span>Critical unsafe</span>
                <strong>{formatPercent(model.critical_unsafe_action_rate)}</strong>
              </div>
              <div>
                <span>Median latency</span>
                <strong>{model.median_duration_seconds.toFixed(2)} s</strong>
              </div>
              <div>
                <span>Completed / errors</span>
                <strong>{model.completed_count} / {model.error_count}</strong>
              </div>
              <div>
                <span>Run package</span>
                <a href={REPO_URL}>Browse artifacts <ExternalLink aria-hidden="true" /></a>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default App;
