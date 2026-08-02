export const REPO_URL = "https://github.com/udiram/MedPhysBench";
export const DOC_LINKS = [
  ["Benchmark paper", `${REPO_URL}/blob/main/docs/BENCHMARK_PAPER.md`],
  ["Methods review", `${REPO_URL}/blob/main/docs/BENCHMARK_METHODS_REVIEW.md`],
  ["Reporting standard", `${REPO_URL}/blob/main/docs/PUBLIC_REPORTING_STANDARD.md`],
  ["Results writeup", `${REPO_URL}/blob/main/docs/RESULTS.md`],
  ["Evaluation protocol", `${REPO_URL}/blob/main/docs/EVALUATION_PROTOCOL.md`],
  ["Reproducibility", `${REPO_URL}/blob/main/docs/REPRODUCIBILITY.md`],
  ["Human baseline", `${REPO_URL}/blob/main/docs/HUMAN_BASELINE_PROTOCOL.md`],
  ["50-model fleet protocol", `${REPO_URL}/blob/main/docs/MODEL_FLEET_PROTOCOL.md`],
  ["All documentation", `${REPO_URL}/tree/main/docs`],
] as const;

export const workflow = [
  {
    number: "01",
    title: "Task contract",
    description: "Inputs, constraints, risk tier, artifacts, and acceptance criteria.",
  },
  {
    number: "02",
    title: "Sealed runtime view",
    description: "Gold answers, graders, provenance, and author identity stay out.",
  },
  {
    number: "03",
    title: "Model + sandbox",
    description: "A frozen harness controls prompts, tools, budgets, and provider identity.",
  },
  {
    number: "04",
    title: "Deterministic grading",
    description: "Outcome, artifact, and declared state are checked without stylistic judging.",
  },
  {
    number: "05",
    title: "Safety gate",
    description: "Critical escalation failures remain visible and cannot be averaged away.",
  },
  {
    number: "06",
    title: "Run manifest",
    description: "Every score retains model revision, seed, hashes, latency, traces, and errors.",
  },
] as const;

export const domainDescriptions: Record<string, string> = {
  core_physics: "Foundations, attenuation, dosimetry, and unit reasoning.",
  radiation_therapy_physics: "Planning, delivery, brachytherapy, radiobiology, and release boundaries.",
  brachytherapy_physics: "Source handling, decay, and applicator-side calculation work.",
  imaging_physics: "CT, MR, image quality, protocol review, and quantitative analysis.",
  nuclear_medicine_physics: "Activity, decay, imaging, therapy, and contamination control.",
  radiation_safety: "Shielding, monitoring, dose constraints, and escalation obligations.",
  informatics: "DICOM, data integrity, interoperability, and benchmark-safe automation.",
  quality_assurance: "Commissioning, QA/QC, trend review, and refusal behavior.",
  research_and_leadership: "Evidence synthesis, statistics, and claim discipline.",
  research_informatics: "Source-packet verification, reproducibility, and benchmark documentation work.",
};

export const laneDescriptions = [
  {
    title: "Outcome",
    description: "Correct result against task-specific deterministic graders.",
  },
  {
    title: "Artifact / state",
    description: "Valid JSON, files, tables, and final sandbox state.",
  },
  {
    title: "Safety / escalation",
    description: "Abstention, policy boundaries, and critical gate failures.",
  },
  {
    title: "Reproducibility",
    description: "Frozen prompts, versions, seeds, manifests, traces, and hashes.",
  },
] as const;

export const evidenceItems = [
  "Versioned task release",
  "Frozen prompt and output schemas",
  "Provider and model revision",
  "Seed and sampling parameters",
  "Deterministic grader outputs",
  "Safety-gate failures",
  "Run IDs, latency, traces, and hashes",
] as const;
