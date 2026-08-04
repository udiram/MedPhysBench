# MedPhysBench

[![Public contract CI](https://github.com/udiram/MedPhysBench/actions/workflows/ci.yml/badge.svg)](https://github.com/udiram/MedPhysBench/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-064EDB)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/code-MIT-071B44)](LICENSE)
[![Tasks: CC0](https://img.shields.io/badge/public%20tasks-CC0-087A42)](tasks/public/)

MedPhysBench is a research-only benchmark for evaluating models and agents on
auditable medical-physics tasks with deterministic grading, explicit safety
gates, and sealed runtime task views.

The claim boundary is narrow on purpose:

> Under a declared task, tool, and policy configuration, can a model produce the
> right outcome and the right escalation behavior?

It is **not** a clinical decision-support product, a medical-device validation
package, or evidence of autonomous clinical competence.

## Current public release

- Live site: [overview](https://medphysbench.xs8psvkmj6.chatgpt.site/) ·
  [verified results](https://medphysbench.xs8psvkmj6.chatgpt.site/results) ·
  [attempt explorer](https://medphysbench.xs8psvkmj6.chatgpt.site/explore) ·
  [human benchmark](https://medphysbench.xs8psvkmj6.chatgpt.site/humans) ·
  [run or request a model](https://medphysbench.xs8psvkmj6.chatgpt.site/run)
- Public repository: `https://github.com/udiram/MedPhysBench`
- Scored core snapshot: `public-core-v0.4` (`64` tasks; five comparable local models)
- Hardening candidate: `public-core-v0.5` (`82` tasks, including `18` TG-263-aligned structure-naming tasks)
- TG-263 pilot: `public-tg263-pilot-v0.5` (`18` synthetic ambiguity, collision, normalization, and escalation tasks)
- TG-263 audit: `public-tg263-pilot-v0.5-audit` (separates primary naming decisions from exact benchmark reason-code labels)
- Real-image pilot: `public-imaging-pilot-v0.4` (`5` real MRI, CT, and PET tasks)
- OpenKBP real-data workflow-view pilot: `public-real-workflows-pilot-v0.6` (`10` one-response tasks from
  `2` patient families; `18` submission-attested Ollama v2 configurations with official ranks,
  `2` submission-attested Groq JSON-v2 configurations with official ranks, `1` attested singleton
  Groq configuration, `8` complete legacy Ollama/Groq configurations retained descriptively,
  `1` quarantined Groq configuration, and `4` GPT-5.6 native audits; `34` total rows—`20` ranked
  and `14` unranked—and `1,020` total attempt artifacts)
- Scored configurations through Monday, August 3, 2026: five common-harness local core models,
  six explicitly unranked GPT-5.6 core-effort pilots, two harder TG-263 native pilots,
  three local models on the original image pilot, thirty published API/local configurations on the
  OpenKBP pilot, and four GPT-5.6 OpenKBP audits with descriptive outcome ranks
- Browser-optimized leaderboard projection: [`web/public/data/leaderboard.json`](web/public/data/leaderboard.json)
- Frozen 50-base-model panel: [`fleet/public_fleet_v1.yaml`](fleet/public_fleet_v1.yaml)
- Reproducible fleet funnel: [`web/public/data/fleet_status.json`](web/public/data/fleet_status.json)
- Plot and rank semantics: [`docs/VISUALIZATION_METHODS.md`](docs/VISUALIZATION_METHODS.md)
- Frontier benchmark methods review: [`docs/BENCHMARK_METHODS_REVIEW.md`](docs/BENCHMARK_METHODS_REVIEW.md)
- Public reporting standard: [`docs/PUBLIC_REPORTING_STANDARD.md`](docs/PUBLIC_REPORTING_STANDARD.md)
- Core run package: [`results/releases/public-core-v0.4/`](results/releases/public-core-v0.4/)
- Imaging run package: [`results/releases/public-imaging-pilot-v0.4/`](results/releases/public-imaging-pilot-v0.4/)
- OpenKBP run package: [`results/releases/public-real-workflows-pilot-v0.6/`](results/releases/public-real-workflows-pilot-v0.6/)
- OpenKBP review ledger: [`reviews/public-real-workflows-pilot-v0.6.json`](reviews/public-real-workflows-pilot-v0.6.json)
- Canonical release evidence index: [`governance/release-evidence-index.json`](governance/release-evidence-index.json)
- Public defect ledger: [`governance/benchmark-defects.json`](governance/benchmark-defects.json)
- Descriptive-only evidence admissions:
  [`governance/descriptive-admissions-public-real-workflows-pilot-v0.6.json`](governance/descriptive-admissions-public-real-workflows-pilot-v0.6.json)
  and
  [`governance/descriptive-admissions-public-imaging-pilot-v0.4.json`](governance/descriptive-admissions-public-imaging-pilot-v0.4.json)
- Release writeup: [`docs/RESULTS.md`](docs/RESULTS.md)
- Benchmark card: [`docs/BENCHMARK_CARD.md`](docs/BENCHMARK_CARD.md)
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Public site source: [`web/`](web/)

## Start here

| If you want to… | Read or run |
| --- | --- |
| Understand the benchmark and current evidence | [Benchmark paper](docs/BENCHMARK_PAPER.md) · [Benchmark card](docs/BENCHMARK_CARD.md) |
| Inspect one model answer against a verified peer | [Attempt explorer](https://medphysbench.xs8psvkmj6.chatgpt.site/explore) |
| Take part in the human baseline | [Human benchmark](https://medphysbench.xs8psvkmj6.chatgpt.site/humans) · [protocol](docs/HUMAN_BASELINE_PROTOCOL.md) |
| Run the benchmark or request a model | [Run or request](https://medphysbench.xs8psvkmj6.chatgpt.site/run) · [submission guide](CONTRIBUTING.md#result-submission-requirements) |
| Audit the benchmark methodology and reporting contract | [Methods review](docs/BENCHMARK_METHODS_REVIEW.md) · [Public reporting standard](docs/PUBLIC_REPORTING_STANDARD.md) |
| Reproduce the public release | [Reproducibility guide](docs/REPRODUCIBILITY.md) · [Evaluation protocol](docs/EVALUATION_PROTOCOL.md) |
| Inspect what could invalidate a score | [Defect ledger](governance/benchmark-defects.json) · [Threat model](docs/THREAT_MODEL.md) · [Data statement](docs/DATA_STATEMENT.md) |
| Add a provider or model | [Adapter contract](docs/ADAPTER_CONTRACT.md) · [Provider routes](docs/PROVIDER_ROUTE_CONTRACTS.md) · [Model onboarding](docs/MODEL_ONBOARDING.md) |
| Submit auditable model results | [Contribution guide](CONTRIBUTING.md#result-submission-requirements) · [submission schema](schemas/common-harness-submission.v1.schema.json) |
| Propose a task | [Contribution guide](CONTRIBUTING.md) · [Task catalog](docs/TASK_CATALOG.md) |
| Understand the harder RT roadmap | [Benchmark hardening](docs/BENCHMARK_HARDENING.md) · [RT competency map](docs/RT_COMPETENCY_MAP.md) · [AAPM coverage](docs/AAPM_TASK_GROUP_COVERAGE.md) · [planning sandbox](docs/PLANNING_SANDBOX.md) · [TG-263 lane](docs/TG263_BENCHMARK.md) |
| Understand the stateful-agent promotion gate | [Stateful workflow contract](docs/STATEFUL_WORKFLOW_CONTRACT.md) |
| Audit the human-grounding claim | [Human baseline protocol](docs/HUMAN_BASELINE_PROTOCOL.md) · [review ledger](reviews/public-real-workflows-pilot-v0.6.json) |
| Run models at no software cost | [Free-model evaluation](docs/FREE_MODEL_EVALUATION.md) |
| Audit or run the 50-model expansion target | [Model fleet protocol](docs/MODEL_FLEET_PROTOCOL.md) · [campaign control plane](docs/CAMPAIGN_CONTROL_PLANE.md) |

## What is already real

- Versioned task, runtime-task, run, result, and release contracts in [`schemas/`](schemas/).
- A forward-looking [stateful workflow receipt schema](schemas/workflow-receipt.v1.schema.json)
  and validator that bind initial state, allowed tools, trajectory evidence, final-state artifacts,
  and grader-input completeness without upgrading any current one-response score.
- Run manifest v2 freezes credential-free adapter settings—including endpoint, context window,
  structured-output mode, retry policy, and local model residency controls—so `--resume` cannot
  silently continue under a changed execution configuration.
- A sealed `RuntimeTask` projection that excludes authoring-only grading and provenance data.
- A deterministic grading stack covering schema validity, safety gates, numeric tolerances,
  exact matches, unordered set matches, string constraints, bounding-box IoU, and grid-mask Dice.
- Rank eligibility that rejects missing, duplicate, or unresolved transport-error attempts; mixed model or run
  configurations; task-version or hash drift; malformed outputs; receipt-free or telemetry-free
  common-harness attempts; and stored grades that disagree with deterministic regrading.
- Strict provider-output parsing with no Markdown repair, substring extraction, duplicate JSON keys,
  non-finite numbers, or non-object roots.
- A runnable Ollama adapter and release runner that persist benchmark artifacts under [`runs/`](runs/).
- A schema-driven, serial campaign controller with memory/disk preflight, one child process per
  model, exact release/fleet binding, canonical-matrix verification, and hash-chained resume receipts;
  new v2 manifests bind every configuration to a frozen route and unexpired access receipt.
- Twenty-one attested current-contract base-model evaluations: 18 exact local-Ollama configurations
  in one rankable comparison group, a matched Groq group containing GPT-OSS 20B and Llama 3.3 70B,
  plus a corrected Groq Qwen3.6 configuration that is fully inspectable and outcome-orderable but
  has no ordinal rank until an exact-contract peer exists.
  Qwen3-VL 8B preserves the default Thinking artifact's non-scoring failed canary separately from a
  digest-pinned Instruct artifact that passed strict JSON/image preflight and the full 30-attempt matrix;
  route declarations and failed/partial campaigns still never create or count scores.
- Strict structured-output parsing: one exact JSON object, with no repair from Markdown wrappers,
  duplicate keys, trailing prose, or non-finite numbers.
- A 97-task public catalog spanning core physics, RT physics, brachytherapy,
  imaging, nuclear medicine, radiation safety, informatics, QA, research methods, and
  TG-263-aligned structure naming; the frozen 64-task v0.4 snapshot remains the core comparison.
- One additional development-only feasibility task is kept outside the public catalog; repository
  validation therefore covers 98 authored task contracts in total.
- Hash-pinned, attributed MRI, CT, PET, and OpenKBP fixtures with separately reported
  real-data pilots; image assets never carry hidden grader geometry into runtime.
- A provisional two-patient OpenKBP lane covering parotid localization, dose-region
  interpretation, published-criteria plan audit, structure inventory, and TG-263 naming,
  with three attempts per task/model and family-cluster uncertainty.
- One default all-published evidence surface for GPT-5.6, Groq, Ollama, and every other provider,
  plus one global `Official comparison only` scope. Harness-group ranks and cross-surface outcome
  order remain distinct metadata; the unified presentation never manufactures a cross-contract rank.
- Fail-closed admission for every public result row: officially ranked common-harness rows require
  exact submission sidecars, while historical descriptive-only common-harness rows require reviewed,
  content-addressed admission ledgers that pin identity, artifact tree, matrix, and known integrity gaps.
- Architecture, governance, evaluation, onboarding, and deployment documentation in [`docs/`](docs/).
- Repository-wide validation of all 23 JSON Schemas, every authored/runtime task projection,
  every artifact digest, constructed reference feasibility, and every published result artifact.
- A unified browser model index that exposes open/closed and provider filters, release-specific
  scores, task-level outcome facets, failed grader contracts, exact configuration hashes, and
  provenance while keeping raw provider responses, hidden expected values, and grader golds out
  of the public projection.
- A release-aware forensic surface built from deterministic regrading. Explicitly opted-in
  public-development releases expose only schema-filtered answers, per-attempt score/time/tokens,
  reduced deterministic verdicts, redacted receipts, failed-lane tallies, shareable URL state, and
  immutable hashes. Each current public-development attempt also carries a content-bound stable ID
  and exact source-artifact SHA-256 for audit navigation. Aggregate-only is the default; non-public
  and comparison-profile releases cannot opt in.
- A side-by-side task evidence view that resolves the complete sealed runtime input by release,
  task ID, and runtime hash, then compares the selected output with the strongest eligible model
  result for that task. Human output stays explicitly `Coming soon` until matched task-level
  participant evidence is reviewed; reference feasibility is never presented as human performance.
- A same-release score-certainty frontier joins the primary safe-success interval to median token or
  wall-time evidence, while keeping broader native/outcome-only rows opt-in and excluding incomplete
  telemetry from Pareto extraction.
- Versioned recorded-capture v2 contracts that bind a fresh-context native run to the exact release,
  sealed-batch hash, model revision, effort, attempt index, output-map digest, timestamps, declared
  transport tools, and all corresponding public result traces without storing hidden reasoning.
- A machine-derived evidence funnel that reports `50` frozen base IDs, `24` with some published
  access or native evidence, `21` validly evaluated under the attested current common-harness contract,
  and `20` rankable—without counting six
  GPT-5.6 effort settings as six models, treating historical legacy rows as current-contract evidence,
  or presenting a partial local campaign as a score.
- Eighteen digest-pinned `reference-json-v2` OpenKBP rows now carry attested common-harness
  submission sidecars. Three reruns migrate Qwen3.5 4B, Gemma 3 4B, and Qwen2.5-VL 3B onto the
  current contract without increasing unique-base-model breadth; the distinct Qwen3-VL 8B Instruct
  artifact and text-only community Phi-4 Multimodal configuration each add one newly completed base
  model. The latter has no vision projector, so its 12 image-required tasks remain explicit unavailable outcomes.
- Two Groq JSON-v2 reruns carry separate attested submission sidecars and form their own exact
  provider/harness/settings comparison group. Their immutable directories do not overwrite the
  older Groq configurations of the same base models.
- Workflow-qualified accounting now separately reports which planned models have actually completed
  a repeated-trial workflow release instead of letting smaller pilot surfaces overstate benchmark
  breadth.
- A machine-readable public defect ledger binds confirmed issues to exact releases and tasks, states
  whether scores remain provisional, withdrawn, fixed, or regraded, and never silently rewrites an
  immutable published result.

## Quick start

```bash
uv sync --extra dev --extra imaging
uv run pytest
uv run python scripts/validate_repository.py
uv run medphys-bench validate-release releases/public_core_v0_4.yaml
uv run medphys-bench validate-campaign campaigns/public_real_workflows_groq_v1.yaml
uv run medphys-bench run-campaign campaigns/public_real_workflows_groq_v1.yaml --dry-run
uv run medphys-bench run-release \
  releases/public_core_v0_4.yaml \
  --adapter ollama \
  --model qwen3.5:4b \
  --results-dir runs \
  --resume
uv run medphys-bench summarize \
  releases/public_core_v0_4.yaml \
  --results-dir runs \
  --expected-attempts 1 \
  --output web/public/data/leaderboard.json
```

## Repository map

```text
docs/                    Architecture, governance, protocol, and release docs
campaigns/               Frozen, secret-free, serial multi-model execution manifests
fleet/                   Frozen base-model selection and executable route manifests
receipts/access/         Immutable route-probe evidence; never score artifacts
releases/                Immutable benchmark release manifests
results/releases/        Published release artifacts and leaderboard inputs
schemas/                 Versioned task, runtime, run, result, route, campaign, fleet, and release schemas
src/medphys_agentbench/  Loader, contracts, graders, adapters, prompts, runner, reporting
tasks/                   Development and public task packs
tests/                   Contract, regression, and summary tests
web/                     Deployable benchmark website and public data bundle
```

## Product boundaries

| In scope | Out of scope |
| --- | --- |
| Research, procurement, offline validation, and shadow-eval methodology | Autonomous patient-specific clinical decisions |
| Synthetic and public benchmark fixtures | PHI transfer to model providers |
| Deterministic outcome and escalation measurement | A single universal “best model” claim |
| Native-model and common-harness comparison | Live PACS, TPS, OIS, delivery, or scanner control |

## Design principles

1. Outcome over prose.
2. Safety is a gate, not a side metric.
3. Every run should carry enough provenance to be replayed or honestly labeled non-replayable.
4. Public development tasks and sealed/private evaluation material are different products.
5. Benchmark performance is evidence about bounded assistance behavior, not clinical authorization.

## Publication integrity

`summarize` does not trust stored leaderboard fields. It reconstructs grades from each recorded
output and the release task contract, verifies the expected task/attempt matrix, checks identity
and hash consistency, and ranks only eligible run sets within identical harness groups. Unsupported
modalities and output-contract failures count as completed zero-score attempts; unresolved transport
errors remain in the evidence package and invalidate the official campaign rank.

The public projection builder applies a second admission boundary. A ranked common-harness row must
resolve to one strictly validated submission sidecar. A descriptive-only common-harness row must
resolve to one release-specific admission entry whose identity, exact result directory, artifact
count/tree hash, complete matrix, and declared integrity errors still match. Native recorded captures
remain governed by their separate sealed-batch capture contract.

## Status note

Version 0.6 is a **public workflow pilot and hardening candidate** layered on the frozen v0.4 score snapshot. It is
runnable and auditable, but it is not yet a sealed multi-institution benchmark or clinical
validation study. Native GPT-5.6 rows now receive a visible descriptive outcome order but no
official harness-group rank until reproduced through a qualified common adapter; perfect scores on
the earlier public core are treated as evidence of saturation, not a claim of autonomous competence.
On Saturday, August 1, 2026, a TG-263 pilot audit further showed
that the very low strict pilot score largely reflected benchmark-authored `reason_codes` label
exactness rather than incorrect naming decisions; the audited decision rate was `17/18` for both
native GPT-5.6 effort settings, while the strict label-dependent pass rate remained `5/18` and
`4/18`.
