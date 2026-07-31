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

- Live site: `https://62fd19716942a2a0f8.v2.appdeploy.ai/`
- Public repository: `https://github.com/udiram/MedPhysBench`
- Core release: `public-core-v0.4` (`64` tasks)
- Real-image pilot: `public-imaging-pilot-v0.4` (`5` real MRI, CT, and PET tasks)
- Scored configurations on Friday, July 31, 2026: three common-harness local models,
  six explicitly unranked GPT-5.6 native-effort pilots, and three local vision models
- Browser-optimized leaderboard projection: [`web/public/data/leaderboard.json`](web/public/data/leaderboard.json)
- Core run package: [`results/releases/public-core-v0.4/`](results/releases/public-core-v0.4/)
- Imaging run package: [`results/releases/public-imaging-pilot-v0.4/`](results/releases/public-imaging-pilot-v0.4/)
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
- A 64-task public core suite spanning core physics, RT physics, brachytherapy, imaging,
  nuclear medicine, radiation safety, informatics, QA, and research methods.
- Hash-pinned, attributed MRI, CT, and PET fixtures with a separately reported five-task
  real-image pilot; image assets never carry hidden grader geometry into runtime.
- Ranked-only release summaries: incomplete or manifest-inconsistent runs remain published but are
  excluded from leaderboard ranking.
- Architecture, governance, evaluation, onboarding, and deployment documentation in [`docs/`](docs/).
- Repository-wide validation of all five JSON Schemas, every authored/runtime task projection,
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

Version 0.4 is a **public development benchmark** with a larger core suite and a licensed
real-image pilot. It is runnable and auditable, but it is not yet a sealed multi-institution
benchmark or clinical validation study. The GPT-5.6 rows are native-surface pilots and remain
unranked until reproduced through a qualified common adapter.
