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

- Live site: `https://medphysbench.xs8psvkmj6.chatgpt.site/`
- Public repository: `https://github.com/udiram/MedPhysBench`
- Scored core snapshot: `public-core-v0.4` (`64` tasks; five comparable local models)
- Hardening candidate: `public-core-v0.5` (`82` tasks, including `18` TG-263-aligned structure-naming tasks)
- TG-263 pilot: `public-tg263-pilot-v0.5` (`18` synthetic ambiguity, collision, normalization, and escalation tasks)
- TG-263 audit: `public-tg263-pilot-v0.5-audit` (separates primary naming decisions from exact benchmark reason-code labels)
- Real-image pilot: `public-imaging-pilot-v0.4` (`5` real MRI, CT, and PET tasks)
- OpenKBP real-workflow pilot: `public-real-workflows-pilot-v0.6` (`10` tasks from
  `2` patient families; `4` ranked common-harness local models with `120` attempts;
  `3` unranked GPT-5.6 native audits with `30` additional recorded outputs)
- Scored configurations through Saturday, August 1, 2026: five common-harness local core models,
  six explicitly unranked GPT-5.6 core-effort pilots, two harder TG-263 native pilots,
  three local models on the original image pilot, four local models on the OpenKBP pilot,
  and three explicitly unranked GPT-5.6 OpenKBP effort audits
- Browser-optimized leaderboard projection: [`web/public/data/leaderboard.json`](web/public/data/leaderboard.json)
- Core run package: [`results/releases/public-core-v0.4/`](results/releases/public-core-v0.4/)
- Imaging run package: [`results/releases/public-imaging-pilot-v0.4/`](results/releases/public-imaging-pilot-v0.4/)
- OpenKBP run package: [`results/releases/public-real-workflows-pilot-v0.6/`](results/releases/public-real-workflows-pilot-v0.6/)
- OpenKBP review ledger: [`reviews/public-real-workflows-pilot-v0.6.json`](reviews/public-real-workflows-pilot-v0.6.json)
- Release writeup: [`docs/RESULTS.md`](docs/RESULTS.md)
- Benchmark card: [`docs/BENCHMARK_CARD.md`](docs/BENCHMARK_CARD.md)
- Changelog: [`CHANGELOG.md`](CHANGELOG.md)
- Public site source: [`web/`](web/)

## Start here

| If you want to… | Read or run |
| --- | --- |
| Understand the benchmark and current evidence | [Benchmark paper](docs/BENCHMARK_PAPER.md) · [Benchmark card](docs/BENCHMARK_CARD.md) |
| Reproduce the public release | [Reproducibility guide](docs/REPRODUCIBILITY.md) · [Evaluation protocol](docs/EVALUATION_PROTOCOL.md) |
| Inspect what could invalidate a score | [Threat model](docs/THREAT_MODEL.md) · [Data statement](docs/DATA_STATEMENT.md) |
| Add a provider or model | [Adapter contract](docs/ADAPTER_CONTRACT.md) · [Model onboarding](docs/MODEL_ONBOARDING.md) |
| Propose a task | [Contribution guide](CONTRIBUTING.md) · [Task catalog](docs/TASK_CATALOG.md) |
| Understand the harder RT roadmap | [Benchmark hardening](docs/BENCHMARK_HARDENING.md) · [RT competency map](docs/RT_COMPETENCY_MAP.md) · [AAPM coverage](docs/AAPM_TASK_GROUP_COVERAGE.md) · [planning sandbox](docs/PLANNING_SANDBOX.md) · [TG-263 lane](docs/TG263_BENCHMARK.md) |
| Audit the human-grounding claim | [Human baseline protocol](docs/HUMAN_BASELINE_PROTOCOL.md) · [review ledger](reviews/public-real-workflows-pilot-v0.6.json) |
| Run models at no software cost | [Free-model evaluation](docs/FREE_MODEL_EVALUATION.md) |

## What is already real

- Versioned task, runtime-task, run, result, and release contracts in [`schemas/`](schemas/).
- A sealed `RuntimeTask` projection that excludes authoring-only grading and provenance data.
- A deterministic grading stack covering schema validity, safety gates, numeric tolerances,
  exact matches, unordered set matches, string constraints, bounding-box IoU, and grid-mask Dice.
- Rank eligibility that rejects missing, duplicate, or non-completed attempts; mixed model or run
  configurations; task-version or hash drift; malformed outputs; and stored grades that disagree
  with deterministic regrading.
- Strict provider-output parsing with no Markdown repair, substring extraction, duplicate JSON keys,
  non-finite numbers, or non-object roots.
- A runnable Ollama adapter and release runner that persist benchmark artifacts under [`runs/`](runs/).
- Strict structured-output parsing: one exact JSON object, with no repair from Markdown wrappers,
  duplicate keys, trailing prose, or non-finite numbers.
- A 97-task public catalog spanning core physics, RT physics, brachytherapy,
  imaging, nuclear medicine, radiation safety, informatics, QA, research methods, and
  TG-263-aligned structure naming; the frozen 64-task v0.4 snapshot remains the core comparison.
- Hash-pinned, attributed MRI, CT, PET, and OpenKBP fixtures with separately reported
  real-data pilots; image assets never carry hidden grader geometry into runtime.
- A provisional two-patient OpenKBP lane covering parotid localization, dose-region
  interpretation, published-criteria plan audit, structure inventory, and TG-263 naming,
  with three attempts per task/model and family-cluster uncertainty.
- Ranked-only release summaries: incomplete or manifest-inconsistent runs remain published but are
  excluded from leaderboard ranking.
- Architecture, governance, evaluation, onboarding, and deployment documentation in [`docs/`](docs/).
- Repository-wide validation of all six JSON Schemas, every authored/runtime task projection,
  every artifact digest, constructed reference feasibility, and every published result artifact.
- A compact browser leaderboard that exposes scores, integrity state, task labels, and contract
  hashes while keeping attempt outputs and grader evidence in the immutable release result files.

## Quick start

```bash
uv sync --extra dev --extra imaging
uv run pytest
uv run python scripts/validate_repository.py
uv run medphys-bench validate-release releases/public_core_v0_4.yaml
uv run medphys-bench run-release \
  releases/public_core_v0_4.yaml \
  --adapter ollama \
  --model qwen3.5:4b \
  --results-dir runs
uv run medphys-bench summarize \
  releases/public_core_v0_4.yaml \
  --results-dir runs \
  --expected-attempts 1 \
  --output web/public/data/leaderboard.json
```

## Repository map

```text
docs/                    Architecture, governance, protocol, and release docs
releases/                Immutable benchmark release manifests
results/releases/        Published release artifacts and leaderboard inputs
schemas/                 Versioned task, runtime, run, result, and release schemas
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
and hash consistency, and ranks only eligible run sets. Provider errors remain in the evidence
package and cannot silently disappear from a denominator.

## Status note

Version 0.5 is a **public hardening candidate** layered on the frozen v0.4 score snapshot. It is
runnable and auditable, but it is not yet a sealed multi-institution benchmark or clinical
validation study. Native GPT-5.6 rows remain unranked until reproduced through a qualified common
adapter; perfect scores on the earlier public core are treated as evidence of saturation, not a
claim of autonomous competence. On Saturday, August 1, 2026, a TG-263 pilot audit further showed
that the very low strict pilot score largely reflected benchmark-authored `reason_codes` label
exactness rather than incorrect naming decisions; the audited decision rate was `17/18` for both
native GPT-5.6 effort settings, while the strict label-dependent pass rate remained `5/18` and
`4/18`.
