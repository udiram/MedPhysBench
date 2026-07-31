# MedPhysBench

MedPhysBench is a research-only benchmark for evaluating models and agents on
auditable medical-physics tasks with deterministic grading, explicit safety
gates, and sealed runtime task views.

The claim boundary is narrow on purpose:

> Under a declared task, tool, and policy configuration, can a model produce the
> right outcome and the right escalation behavior?

It is **not** a clinical decision-support product, a medical-device validation
package, or evidence of autonomous clinical competence.

## Current public release

- Live site: `https://medphysbench.xs8psvkmj6.chatgpt.site`
- Public repository: `https://github.com/udiram/MedPhysBench`
- Release: `public-dev-2026-07-31`
- Public tasks: `16`
- Scored models on Friday, July 31, 2026: `11` locally reachable Ollama models
- Leaderboard artifact: [`web/public/data/leaderboard.json`](web/public/data/leaderboard.json)
- Release writeup: [`docs/RESULTS.md`](docs/RESULTS.md)
- Public site source: [`web/`](web/)

## What is already real

- Versioned task, runtime-task, run, result, and release contracts in [`schemas/`](schemas/).
- A sealed `RuntimeTask` projection that excludes authoring-only grading and provenance data.
- A deterministic grading stack covering schema validity, safety gates, numeric tolerances,
  exact matches, unordered set matches, and string-constraint checks.
- A runnable Ollama adapter and release runner that persist benchmark artifacts under [`runs/`](runs/).
- A public synthetic development suite spanning core physics, RT physics, brachytherapy,
  imaging physics, nuclear medicine, radiation safety, informatics, QA, and research-style tasks.
- Architecture, governance, evaluation, onboarding, and deployment documentation in [`docs/`](docs/).

## Quick start

```bash
uv run --with pyyaml --with pytest pytest
uv run --with pyyaml python -m medphys_agentbench.cli validate-release releases/public_dev_2026_07_31.yaml
uv run --with pyyaml python -m medphys_agentbench.cli run-release \
  releases/public_dev_2026_07_31.yaml \
  --adapter ollama \
  --model qwen3.5:4b \
  --results-dir runs
uv run --with pyyaml python -m medphys_agentbench.cli summarize \
  releases/public_dev_2026_07_31.yaml \
  --results-dir runs \
  --output web/public/data/leaderboard.json
```

## Repository map

```text
docs/                    Architecture, governance, protocol, and release docs
releases/                Immutable benchmark release manifests
runs/                    Saved benchmark run artifacts
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

## Status note

The current release is a **public synthetic development benchmark**. It is a real runnable
benchmark package with published results, but it is not yet a sealed multi-institution benchmark
program on the scale of SWE-bench Verified or a frontier-lab internal eval stack. The repository
is structured to grow into that.
