# Reproducing the public release

## Environment

- Python 3.11 or newer
- `uv`
- Ollama for provider-backed execution
- Node.js 22 for the public website

```bash
git clone https://github.com/udiram/MedPhysBench.git
cd MedPhysBench
uv sync --extra dev --extra imaging
uv run pytest
uv run python scripts/validate_repository.py
uv run medphys-bench validate-release releases/public_core_v0_4.yaml
uv run medphys-bench validate-release releases/public_imaging_pilot_v0_4.yaml
```

## Run a model

```bash
uv run medphys-bench run-release \
  releases/public_core_v0_4.yaml \
  --adapter ollama \
  --model qwen3.5:4b \
  --results-dir runs \
  --attempts 1 \
  --seed 20260731 \
  --temperature 0 \
  --max-tokens 1024
```

Do not rename or remove individual attempt artifacts before summarizing. The release declares one
expected attempt per task; incomplete, duplicate, unknown-task, mixed-identity, or hash-drifted
sets are retained as unranked evidence.

## Recompute scores

```bash
uv run medphys-bench summarize \
  releases/public_core_v0_4.yaml \
  --results-dir runs \
  --output leaderboard.json
```

The summarizer recomputes deterministic grades from each output. Editing stored `passed`, `safe`,
`score`, or `grades` cannot produce a rankable result.

Before publishing a provider-backed package, remove provider reasoning while retaining response
digests and provenance, then validate the result tree:

```bash
uv run python scripts/sanitize_public_results.py results/releases/public-core-v0.4
uv run python scripts/sanitize_public_results.py --check results/releases/public-core-v0.4
uv run python scripts/validate_repository.py
```

For a non-API pilot, export the sealed runtime batch and collect strict task-ID-keyed JSON outputs:

```bash
uv run medphys-bench export-runtime releases/public_core_v0_4.yaml --output sealed.json
uv run medphys-bench score-recorded-batch \
  releases/public_core_v0_4.yaml recorded.json \
  --model MODEL --model-revision REVISION --reasoning-effort high \
  --results-dir runs
```

The recorded file must bind the exact sealed-batch SHA-256 and task ID set. These imports are
always marked `codex-native` and unranked; they are not substitutes for a qualified provider adapter.

## Build the website

```bash
cd web
npm ci
npm run build
```

## Comparing a replication

Report the repository commit, release ID and release-contract hash, complete model descriptor,
Ollama/provider version, hardware, operating system, seeds, sampling parameters, ranked and
unranked rows, error artifacts, and the generated leaderboard JSON. Do not compare ranks across
different task releases as if they were the same experiment.
