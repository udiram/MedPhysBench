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

## Run a frozen multi-model campaign

The v1 campaign controller makes the documented laptop safety policy executable. A
manifest binds the exact release-contract hash, frozen fleet, base-model identity,
provider route, model revision, structured-output mode, sampling settings, result
directory, and resource floors. It accepts environment-variable names but has no
field capable of storing a credential value.

```bash
uv run medphys-bench validate-campaign \
  campaigns/public_real_workflows_groq_v1.yaml

uv run medphys-bench run-campaign \
  campaigns/public_real_workflows_groq_v1.yaml \
  --dry-run

# Requires GROQ_API_KEY in the process environment. The value is never printed
# or written to campaign state.
uv run medphys-bench run-campaign \
  campaigns/public_real_workflows_groq_v1.yaml
```

Execution is always one model at a time and one child process per model. The
controller checks memory and disk before the campaign and before every model,
then delegates each configuration to the same immutable `run-release --resume`
path used for direct runs. A zero child exit is insufficient: all canonical
task/attempt files must exist and match the declared model name, revision, task,
and attempt index. Missing matrices, transport errors, resource pressure, and
nonzero exits are recorded without being converted into scores.

The immutable `campaign.json` binds resume to the manifest and release hashes.
`events.jsonl` is append-only and hash-chained. These files are operational
receipts; scored result artifacts remain the source of truth. Changing the
manifest, release contract, route, revision, sampling settings, or output root
requires a new campaign ID/results directory.

New campaigns should use the evidence-bound v2 generator. It requires one exact
route-to-receipt binding per selected route and an explicit generation instant,
so expiration decisions are reproducible. The example paths below are schematic;
the repository intentionally does not ship fabricated successful receipts.

```bash
# Reads only the route's declared credential environment variable. It uses a
# generic JSON canary, never a benchmark task, and persists no raw provider body.
uv run python scripts/probes/openai_access_probe.py \
  fleet/model_routes_v1.yaml \
  --route-id groq-gpt-oss-20b

# Local qualification verifies the installed digest and a strict JSON canary
# only. It does not load benchmark tasks or write a score.
uv run python scripts/probes/ollama_access_probe.py \
  fleet/local_ollama_routes_v1.yaml \
  --route-id ollama-deepseek-r1-1-5b

uv run medphys-bench generate-campaign \
  fleet/model_routes_v1.yaml \
  releases/public_real_workflows_pilot_v0_6.yaml \
  --route-id groq-gpt-oss-20b \
  --receipt groq-gpt-oss-20b=receipts/access/groq-gpt-oss-20b/<probe>.json \
  --campaign-id groq-gpt-oss-20b-q2-v2 \
  --results-dir runs/groq-gpt-oss-20b-q2-v2 \
  --as-of 2026-08-03T12:00:00Z \
  --minimum-available-memory-fraction 0.35 \
  --minimum-available-memory-gib 6 \
  --minimum-free-disk-gib 10 \
  --output campaigns/groq-gpt-oss-20b-q2-v2.yaml
```

The generator refuses expired, future-dated, tampered, identity-mismatched,
unavailable, insufficient-quota, or mixed credential-surface inputs. Unknown
quota also fails closed unless `--allow-unknown-quota` is explicitly recorded in
the generated manifest. Generation contacts no provider and creates no run state.
The memory and disk flags are frozen into the campaign instead of being runtime-only
operator switches, so a resumed run cannot quietly weaken its safety floor.
The probe emits typed access failures (missing authorization, model not found,
quota exhausted, rate limited, unsupported contract, or network error) as
non-scoring receipts. A successful receipt proves the route's declared JSON
contract and binds the exact reviewed probe implementation bytes.

## Run a model

```bash
uv run medphys-bench run-release \
  releases/public_core_v0_4.yaml \
  --adapter ollama \
  --model qwen3.5:4b \
  --results-dir runs \
  --resume \
  --seed 20260731 \
  --temperature 0 \
  --max-tokens 1024
```

The attempt count defaults to the frozen release contract. `--resume` validates every existing
checkpoint, including its model descriptor, attempt key, sampling settings, immutable hashes, and
deterministic regrade, before requesting only missing keys. Run manifest v2 additionally freezes a
credential-free hash of adapter settings: endpoint, timeout, structured-output mode, strictness,
reasoning effort, retry limit, artifact transport, and (for Ollama) context window and `keep_alive`.
Changing any of these values aborts resume before a provider request. URLs containing user-info,
query parameters, or fragments are rejected rather than persisted. Without `--resume`, an existing artifact
is an immutable-overwrite error. Do not rename or remove individual attempt artifacts before
summarizing; incomplete, duplicate, unknown-task, mixed-identity, or hash-drifted sets are retained
as unranked evidence.

The command above is the `public-core-v0.4` example; its 1,024-token cap is not the
OpenKBP comparison contract. A run intended to join the current
`public-real-workflows-pilot-v0.6` Ollama `reference-json-v2` group must use the
group's exact 2,048-token cap and adapter settings. For the published Mistral Nemo
artifact, that command shape is:

```bash
uv run medphys-bench run-release \
  releases/public_real_workflows_pilot_v0_6.yaml \
  --adapter ollama \
  --model mistral-nemo:12b-instruct-2407-q4_K_M \
  --model-revision sha256:daf6737417121831e572a9c482e92a221ee0c33537f35f1f857c7b4f7191df55 \
  --results-dir runs/openkb-mistral-nemo \
  --resume \
  --seed 20260731 \
  --temperature 0 \
  --max-tokens 2048 \
  --timeout 300 \
  --ollama-num-ctx 4096 \
  --ollama-keep-alive 0
```

The published multimodal Gemma 3 12B campaign used the same command with
`--model gemma3:12b-it-q4_K_M`, revision
`sha256:f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a`, and
`--results-dir runs/openkb-gemma3-12b`. Its first pass added `--attempts 1` as a
10-task adapter/modality preflight; the full command then omitted that flag and
used `--resume` to validate those checkpoints before requesting attempts two and
three.

The published text-only Phi-4 14B campaign used the same preflight-then-resume
sequence with `--model phi4:14b`, revision
`sha256:ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba`, and
`--results-dir runs/openkb-phi4-14b`. Its 12 required-image attempts are explicit
no-call capability failures; the remaining 18 attempts have complete provider
receipts, duration, and token telemetry.

The published Llama 3.1 8B campaign used the same exact-source sequence with
`--model llama3.1:8b`, revision
`sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`,
and a fresh `runs/openkb-llama3-1-8b-v2` directory. A ten-task `--attempts 1`
preflight preceded the immutable `--resume` to 30 attempts. The result is a
second provider route for the already cataloged Llama 3.1 base model, not a new
base-model completion.

The August 3 current-contract reruns used the same preflight-then-resume sequence and
separate result roots for `qwen3.5:4b`, `gemma3:4b`, and `qwen2.5vl:3b`, pinned to
revisions `sha256:2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`,
`sha256:a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`,
and `sha256:fb90415cde1ef08aa669ae74b082d49b158729b6db1ab183c941417d507e71a1`,
respectively. Their 90 canonical attempts and three submission sidecars are new v2
evidence; the earlier v1 artifacts remain immutable historical rows. The original
`qwen3-vl:8b` Thinking artifact and interrupted Qwen3-VL campaigns remain non-scoring.
A distinct `qwen3-vl:8b-instruct` artifact, pinned to
`sha256:0533d74300e4f9bc367d675d4e64ffd073d50ff16a2b4096cc2e8a1cf8c96319`,
completed a new 30-attempt matrix in a separate result root after the campaign froze
a 30-second unload-recovery wait without weakening its 35% and 6 GiB memory floors.

The summarizer still decides comparability from the frozen manifest hashes; matching
the visible flags alone does not override a different harness revision, adapter
contract, seed policy, or model digest.

Run manifest v1 remains readable for published history, but it is deliberately not resumable: it
did not freeze the adapter-runtime settings needed to prove a campaign continued unchanged. Start a
new results directory/revision when migrating an interrupted v1 campaign.

Provider/network failures are retained under the model's append-only
`_transport_errors` ledger while the canonical attempt key remains absent. A
later `--resume` can retry that key without deleting the outage record. Declared
modality limitations and provider output-contract failures are model outcomes,
not transport errors, and are deterministically scored in the canonical matrix.

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

Repository validation also applies schema-removal and targeted grader mutations to every task. A
release cannot validate when a declared grader accepts its corresponding deterministic mutation or
when a required grader failure does not block overall success.

For a non-API pilot, export the sealed runtime batch and collect strict task-ID-keyed JSON outputs:

```bash
uv run medphys-bench export-runtime releases/public_core_v0_4.yaml --output sealed.json
uv run medphys-bench score-recorded-batch \
  releases/public_core_v0_4.yaml recorded.json \
  --model MODEL --model-revision REVISION --reasoning-effort high \
  --results-dir runs
```

The recorded file must bind the exact sealed-batch SHA-256 and task ID set. New evidence packages
use `medphysbench.recorded-batch.v2`, which additionally binds the release ID, exact model revision,
reasoning effort, one-based attempt index, stable output-map digest, capture timestamps, fresh-context
isolation, sealed-batch delivery mode, final-JSON-only response capture, declared transport tools, and
the fact that hidden reasoning was not stored. The CLI rejects any disagreement between the capture,
command line, sealed runtime projection, and result destination. Version 1 remains readable for
historical imports but does not make these stronger capture claims.

Committed v2 capture records live under `captures/recorded/<release>/<configuration>/`. Repository
validation resolves every capture back to all expected public result files, verifies byte-semantic
output equality, and requires both the result trace and redacted runtime receipt to carry the same
capture ID. These imports are always marked `codex-native` and unranked; they are not substitutes for
a qualified provider adapter and do not gain invented token or latency telemetry.

## Build the website

```bash
cd web
npm ci
npm run build
```

Rebuild the public model-fleet projection before a site release:

```bash
uv run python scripts/build_fleet_status.py
git diff --exit-code web/public/data/fleet_status.json
```

The projection counts a base model as evaluated only when at least one public row has its exact
expected attempt count, no canonical errors, no missing or unexpected attempt keys, and no
integrity issue beyond a declared cross-surface comparability annotation. Access probes and partial
campaigns never increment the evaluated or ranked counts.

Every contributed common-harness result bundle must also pass the artifact-level submission
validator:

```bash
uv run python scripts/common_harness_submission.py validate-all
```

The committed sidecar inventory covers the full result directory, including any append-only
transport-error ledger. Its canonical tree hash prevents omitted failures, inserted artifacts, or
post-hoc byte edits from passing CI unnoticed. Ranking additionally requires a real model-response
trace, non-empty provider/runtime receipt, and per-call token and duration telemetry; declared
unsupported-modality preflight outcomes use their explicit capability trace instead.
Every complete `reference-json-v2` row must also have a matching available Q2 access entry whose
promotion basis is `attested_complete_q2`, whose chronology says whether preflight preceded the
full matrix, and whose evidence points to that exact sidecar. The fleet projection, submission
validator, and repository-wide validator all enforce this binding.

The current public inventory contains seventeen such attested v2 sidecars. Sidecar count
is configuration evidence, not unique-model breadth: three are current-contract reruns
of base models already counted by the fleet funnel.

Historical common-harness rows that are visible but ineligible for official rank pass a separate
descriptive-publication gate:

```bash
uv run python scripts/descriptive_admission.py \
  governance/descriptive-admissions-public-real-workflows-pilot-v0.6.json
uv run python scripts/descriptive_admission.py \
  governance/descriptive-admissions-public-imaging-pilot-v0.4.json
```

These ledgers must exactly cover the release's descriptive common-harness rows and bind each row to
its direct result directory, full expected attempt matrix, artifact-tree hash, and exact accepted
integrity-error set. They grant visibility only; they never restore rank eligibility or current-
contract fleet credit. Repository validation and the public projection builder both enforce them.

The OpenKBP leaderboard has three byte-identical published projections plus the derived fleet
status. Rebuild them together, or make CI prove that no copy drifted:

```bash
make rebuild-openkb
make check-openkb-projection
```

## Comparing a replication

Report the repository commit, release ID and release-contract hash, complete model descriptor,
Ollama/provider version, hardware, operating system, seeds, sampling parameters, ranked and
unranked rows, error artifacts, and the generated leaderboard JSON. Do not compare ranks across
different task releases as if they were the same experiment.
