# Fifty-model fleet protocol

Status: execution protocol; target matrix not yet complete  
Review date: 2026-08-03

Machine-readable artifacts:

- frozen selection: [`../fleet/public_fleet_v1.yaml`](../fleet/public_fleet_v1.yaml);
- executable route candidates: [`../fleet/model_routes_v1.yaml`](../fleet/model_routes_v1.yaml);
- digest-pinned local routes: [`../fleet/local_ollama_routes_v1.yaml`](../fleet/local_ollama_routes_v1.yaml);
- public derived status: [`../web/public/data/fleet_status.json`](../web/public/data/fleet_status.json);
- deterministic builder: [`../scripts/build_fleet_status.py`](../scripts/build_fleet_status.py).

This protocol defines what “50 models evaluated” means for MedPhysBench. It is a
publication gate, not permission to inflate the count with prompt variants,
partial campaigns, provider aliases, or imported third-party scores.

## Counting unit

The target is **50 unique base model identifiers** with completed MedPhysBench
attempt matrices. Reasoning-effort settings, quantizations, providers, context
windows, and native scaffolds are useful system configurations, but they do not
count as new base models. Every configuration remains a separate immutable row.

A model counts toward the target only when:

1. the provider, exact model ID/revision, request date, adapter revision, prompt,
   tools, runtime task, grader, scoring revision, settings, and response metadata
   are pinned;
2. every declared task/attempt key is present exactly once;
3. deterministic regrading agrees with stored grades;
4. unsupported modalities are explicit capability failures rather than omitted
   tasks;
5. transport or quota failures are resolved without changing the configuration,
   or the campaign remains unranked;
6. the public projection passes redaction and aggregate-reproduction tests.

## Target panel composition

The 50-model panel should be selected before scores are inspected:

| Stratum | Minimum target | Purpose |
| --- | ---: | --- |
| Open-weight base models | 30 | Reproducible local/lab baselines across parameter scales |
| Closed-weight hosted models | 15 | Frontier and production-hosted comparison |
| Remaining flexible slots | 5 | New releases, domain models, or independent replications |
| Vision-capable systems | 15 across strata | Image localization, segmentation, and artifact understanding |
| At least five steward families | required | Prevent one vendor/model family from dominating the panel |
| Small, medium, and large compute tiers | required | Show scaling and efficiency tradeoffs |

The same base model served by two providers may appear twice as a system row but
counts once toward the 50-base-model target. Provider substitutions, rotating
router aliases, and undisclosed upstream fallbacks are prohibited.

## Qualification funnel

### Q0 — access audit

Resolve the exact endpoint/model ID, live status, terms, data boundary, context
and modality support, rate limits, and whether the route can complete a frozen
matrix without paid overage. Record failures in `access_status.json`; do not
create a score row.

An executable route is not access evidence. `model-route.v1` freezes the exact
adapter/provider/model configuration and its revision basis. A successful route
probe produces a content-addressed `access-probe-receipt.v1` under
`receipts/access/`; only an unexpired receipt with matching route/fleet/model
identity and sufficient quota can feed the evidence-bound campaign generator.
Failure receipts are useful operational evidence but never increment evaluated or
ranked counts.

The ledger is validated against `access-status.v1`: available routes must bind a
provider, exact handle or base-level native surface, frozen base-model ID, and
qualification stage; blocked routes cannot claim a stage. An attested Q2
promotion additionally requires a resolvable common-harness submission sidecar.
The derived website projection carries that sidecar reference into the model's
readiness drawer so the evidence is inspectable without treating access as a score.

### Q1 — three-task adapter contract

Run one schema task, one calculation/artifact task, and one required-escalation
task. Validate structured output, deterministic seeds where supported, token and
duration capture, request IDs, bounded retries, and secret redaction.
For the local Ollama surface, the runtime has one declared request attempt, no
adapter retry loop, and no provider-issued request ID; the immutable MedPhysBench
`run_id`, exact artifact digest, receipt hash, trace, and usage record supply the
available execution identity. This provider limitation must remain explicit and
must not be represented as a missing receipt or invented request ID.
Q1 is an operational publication gate rather than a correctness threshold: a
model may fail the clinical-physics outcome while still proving that its adapter
records an honest, complete attempt. Normally Q1 precedes Q2 so an invalid
adapter is stopped before the expensive campaign. A complete, ranking-eligible,
attested Q2 matrix is a machine-verifiable superset of that adapter evidence and
may backfill qualification after an opportunistic full run. The access ledger
must disclose either `preflight_before_full_q2` or
`backfilled_after_full_q2`, use promotion basis `attested_complete_q2`, and
reference the exact `common-harness-submission.v1` sidecar. This exception does
not retroactively claim that Q1 protected the cost of the run.

### Q2 — ten-task real-workflow pilot

Run `public-real-workflows-pilot-v0.6` with three predeclared attempts per task.
This is 30 attempts per configuration. Publish only the complete matrix. Because
its ten tasks come from two patient families, uncertainty and claims remain
family-aware and explicitly provisional.

### Q3 — comparison release

Qualified systems advance to a larger family-diverse release with at least five
attempts per task, paired counterfactuals, negative controls, external physics
review, and a human baseline. Only identical frozen harness groups receive an
official ordinal rank.

## Budget and scheduling

The Q2 target requires at least 1,500 model attempts for 50 configurations before
infrastructure retries. Campaigns run serially on memory-constrained hosts with
`OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_QUEUE=1`, a
declared context window, and `keep_alive=0`. GPU/lab campaigns may parallelize
only across isolated workers with fixed per-worker resource ceilings.

`medeval.campaign.v1` now enforces that policy for managed laptop runs. The
controller requires `max_parallel_models=1`, process isolation, immutable resume,
an exact release-contract hash, explicit base-model IDs from the frozen fleet,
and memory/disk floors. It launches one typed, shell-free child command per
configuration, rechecks pressure before every model, and verifies the complete
canonical attempt matrix before recording completion. Alternate revisions or
reasoning settings with the same provider model handle use separate campaigns so
they cannot collide in one result directory or inflate the 50-base-model count.

For new campaigns, `medeval.campaign.v2` additionally binds every model entry to
an exact route hash and immutable access-receipt hash. Generation is byte-stable
for the same selected routes, receipts, release, sampling policy, and declared
generation instant. It refuses mixed credential surfaces, expired/future/tampered
receipts, insufficient quota, and unrecorded unknown-quota assumptions before any
model request is possible.

Hosted free-tier campaigns must snapshot live quotas before dispatch. HTTP 429,
retired handles, and weekly limits are access failures, not model failures. The
runner must resume missing immutable attempt keys without overwriting completed
artifacts and must never shorten the matrix to fit a quota. `run-release --resume`
validates every existing checkpoint against the frozen task, model descriptor,
attempt index, seed, sampling settings, prompt/tool/runtime/grader hashes, scoring
revision, and deterministic regrade before it sends any new request. A mismatched
or tampered checkpoint aborts the campaign instead of being skipped.
Provider/network exceptions are written to an append-only `_transport_errors`
side ledger and do not occupy the canonical task/attempt path. A later
`--resume` therefore retries the still-missing immutable key while preserving
the outage evidence. Model capability failures and output-contract failures are
scored outcomes and remain canonical attempts; they are not transport retries.

## Current state

The public website currently exposes 31 model configurations representing 24
unique base model identifiers across 50 release rows and four release surfaces, including five
completed Groq configurations, six GPT-5.6 Sol effort configurations, and one
GPT-5.6 Terra configuration. These are not 31 unique base models. An Ollama Cloud access probe
for `qwen3.5:397b-cloud` on 2026-08-02 returned HTTP 429 before a scored artifact
was created. The lab-node hostname was not resolvable from the current Mac
network context. Neither event supports a model score.

The frozen v1 target panel contains exactly 50 unique base IDs: 31 open-weight,
19 closed-weight, 31 declared vision-capable, and 11 stewards. After enforcing
the current grader/scoring manifest contract, the derived funnel reports 24 base models with
some published access or native evidence, 19 attested common-harness evaluated, and 18 officially
rankable base models. Eight complete legacy Ollama/Groq configurations remain visible but are excluded
from current-contract rank because their attempt manifests lack adapter-settings hashes; four of the
affected base IDs have no separate v2 row and therefore leave the evaluated/ranked fleet funnel. One
historical Qwen3.6 Groq row remains excluded because its provider-output failure artifacts lack
model-response receipts and telemetry, while a separately frozen corrected route now contributes
complete, attested evidence for that base model without receiving an ordinal rank as a singleton group.
GPT-5.6 Sol and Terra complete native rows remain visible in the same
model index and attempt forensics, but do not inflate that common-harness funnel.

The public `fleet-status.v3` projection now gives every frozen base ID a
machine-derived readiness state, next gate, explanatory note, and any exact
base-model-bound access evidence, including a direct attested-submission link when
one exists. It also separates the planned-panel composition from the actually
evaluated slice: the current common-harness slice contains 18 open-weight and zero
closed-weight base models, seven base identities whose source model is vision-capable, six
image-capable evaluated routes, six stewards, and two
size tiers. The OpenKBP field is explicitly a one-response workflow-view gate, not
stateful workflow qualification. “Planned route” means no Q0 evidence is
committed; it is not a claim that an API handle, free quota, local artifact, or
compatible hardware is currently available. The website can therefore filter the
remaining 32 models by openness, route, and missing gate without inventing access
reasons or confusing native GPT-5.6 evidence with common-harness qualification.
Seven frozen route sets now declare 32 executable configurations. Eighteen are digest-pinned Ollama
routes corresponding exactly to current-contract submission sidecars, including the Phi-4 Multimodal
route that records the text-only capability actually exposed by its community GGUF under Ollama. The remaining routes cover
Groq and hosted-provider expansion candidates. Route presence is operational readiness metadata,
not a score, an access claim, or a unique-base-model completion.
`deepseek-r1:1.5b` completed a fresh 30-attempt Q2 matrix with artifact digest
`sha256:e0979632db5a88d1a53884cb2a941772d10ff5d055aabaa6801c4e36f3a6c2d7`.
Its 12 required-image attempts are explicit unsupported-modality outcomes and all
18 text attempts produced schema-valid outputs. Five additional digest-pinned local
models completed the identical 30-attempt contract: Qwen 3 1.7B, 8B, and 14B;
Qwen 2.5 7B Instruct; and Llama 3.2 3B. Five of the six completed the three-task
adapter audit before Q2, with schema-valid output and complete duration/token
telemetry. DeepSeek's complete Q2 matrix was audited and attested after the run.
That initial six-system `reference-json-v2` comparison group became officially
rankable within that frozen configuration only.
Phi-4 Mini then completed the same digest-pinned Q1 and 30-attempt Q2 process as a
seventh local text system. Its exact Ollama artifact revision, complete artifact set,
execution window, environment, and per-file hashes are bound by the first committed
`common-harness-submission.v1` sidecar. The route maps the frozen
[`microsoft/Phi-4-mini-instruct`](https://huggingface.co/microsoft/Phi-4-mini-instruct)
base ID to the exact official
[`phi4-mini:3.8b-q4_K_M`](https://ollama.com/library/phi4-mini/tags) Ollama artifact;
the published row retains the full resolved manifest digest rather than relying on the
mutable tag alone.
Qwen2.5-VL 7B then completed four Q1 calls—including a real-image transport
smoke test—and the full 30-attempt Q2 matrix through exact Ollama artifact
`sha256:5ced39dfa4bac325dc183dd1e4febaa1c46b3ea28bce48896c8e69c1e79611cc`.
Unlike the text-only v2 rows, its twelve image-grid attempts were real model
calls rather than unsupported-modality preflight outcomes. The sanitized
artifact set and every file digest are bound by a second
`common-harness-submission.v1` sidecar.
Mistral Nemo 12B then completed the same 30-attempt v2 matrix through exact Ollama
artifact `sha256:daf6737417121831e572a9c482e92a221ee0c33537f35f1f857c7b4f7191df55`.
Its first complete development run used a non-comparable 1,024-token cap and is
retained outside the public release as candidate evidence. The published rerun uses
the frozen 2,048-token v2 cap, joins the existing comparison group, and binds all 30
sanitized artifacts to an attested submission sidecar.
Gemma 3 12B IT then completed a 10-task first-attempt preflight and resumed the
same immutable campaign to 30 attempts through exact multimodal Ollama artifact
`sha256:f4031aab637d1ffa37b42570452ae0e4fad0314754d17ded67322e4b95836f8a`.
It made real model calls on all 12 required-image attempts, retained complete
receipts and token/time telemetry, achieved 40.0% safe success with 100% safety
and valid-output rates, and passed a zero-change deterministic regrade.
Microsoft Phi-4 14B then completed the same exact-source preflight and immutable
30-attempt Q2 campaign through Ollama artifact
`sha256:ac896e5b8b34a1f4efa7b14d7520725140d5512484457fab45d2a4ea14c69dba`.
The text-only route made 18 provider calls and retained the 12 required-image
attempts as capability-unavailable zeroes. It achieved 10.0% safe success, 100%
safety over evaluable calls, 60% valid output, and complete provider-call token
and duration telemetry; its attested artifact tree is
`sha256:14d6100f45f5254f40a262ff2a9683bd20117c16e84548a7da90110e4eed92d9`.
Meta Llama 3.1 8B Instruct then completed the same exact-source preflight and
30-attempt campaign through Ollama artifact
`sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`.
It achieved 0% safe success and 33.33% safety over 18 text calls: correct naming
or inventory actions were repeatedly paired with an unsafe refusal to escalate.
The route is a second configuration of the already evaluated Llama 3.1 base model,
so it expands system evidence without inflating the 50-base-model completion count.
Its attested artifact tree is
`sha256:85e99ed20a2ade2ad8be287d365a906bf0ac1bc1825dad389f9471f3e1723a25`.
Pixtral 12B then completed the same preflight and 30-attempt multimodal matrix through
Ollama manifest `sha256:bf98f2143bd35a699805b018855a12db0d5ddda0ce694772d4dd3c6b843a3286`.
Because the tested GGUF is community-published, the catalog pins the immutable source
revision, identifies the post-trained Mistral parent, and records separate SHA-256 and
byte-size evidence for the model weights and F32 vision projector. It made 30 real calls,
including all 12 image-grid attempts, achieved 10.0% safe success, 60.0% safety, and
100% schema validity, and passed a zero-change deterministic regrade. The attested public
artifact tree is
`sha256:6959930732876ef1b1bdf9e1a8da009be1cd79a0c31d38860e1e8fa42f0f4437`.
Phi-4 Multimodal Instruct then completed the same 30-attempt matrix through community Ollama
artifact `sha256:3c73f00ac73b1f77b914aec830fbf2e2570aac6f538dd474e2d19dcb6cc9d62f`.
The catalog pins the community repository revision and model-weight SHA-256. The imported GGUF has
no vision projector, so it made 18 text calls and retained 12 image-required tasks as explicit
capability-unavailable outcomes. It achieved 10.0% safe success, 100% safety over evaluable calls,
60% valid output, median 937.5 total tokens, and median 8.436-second wall time. Its attested public
artifact tree is `sha256:ffc91ad3e878e1b4130e5b78ba2416c3ab773b72de97334d98627517b795f698`.
All nineteen current-contract rows
now have their own sidecar with exact source commits, execution window, model
identity, environment, and a SHA-256 inventory of every result artifact. The
access ledger records whether qualification preceded the matrix or was backfilled
from the complete attested matrix.
Three August 3 reruns added current-contract evidence for Qwen3.5 4B, Gemma 3 4B,
and Qwen2.5-VL 3B without adding a unique base model. Their exact revisions are
`sha256:2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`,
`sha256:a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`, and
`sha256:fb90415cde1ef08aa669ae74b082d49b158729b6db1ab183c941417d507e71a1`.
They achieved 50%, 20%, and 0% safe success with safety rates of 100%, 100%, and
70%, respectively. Earlier Qwen3-VL runs stopped at resource guards and remain
unranked raw evidence. The distinct digest-pinned `qwen3-vl:8b-instruct` artifact
later completed a clean 30-attempt matrix with 30.0% safe success, 100% safety,
and 100% schema validity under a frozen bounded unload-recovery policy.

The officially rankable current v2 Ollama group contains eighteen exact model configurations.
The corrected Groq Qwen3.6 configuration is separately attested and outcome-orderable, but remains
unranked until a second system shares its exact provider, adapter-settings, and seed contract. A complete
campaign with any other token cap, adapter-settings hash, harness revision, or seed
policy remains visible evidence but cannot enter that ranking group.

Run manifest v2 now freezes and hashes credential-free adapter runtime settings.
Resume rejects a context-window, endpoint, strict-schema, retry-policy, reasoning-
effort, artifact-transport, or model-residency change before sending a request.
Unexpected harness exceptions are fatal internal campaign errors; only declared
provider/transport failures enter the append-only transport side ledger.

The 50-model target therefore remains an execution objective. MedPhysBench must
publish the actual completed count and the access ledger until all 50 base-model
matrices exist; the site must never display a planned model as evaluated.
`web/public/data/fleet_status.json` now carries the derived completion gate with
the exact satisfied and remaining base IDs plus open/closed, vision, steward, and
size-tier minima. Progress builds remain allowed, while claim-bearing release jobs
must run `uv run python scripts/build_fleet_status.py --require-complete`; that command
exits nonzero and writes nothing until the frozen 50-model objective and its composition
constraints are genuinely satisfied.

## Release report

Every fleet release publishes:

- completed base-model count and system-configuration count;
- open/closed, provider, modality, and size-tier coverage;
- per-model safe success, interval, safety, validity, escalation, consistency,
  tokens, duration, and cost when observed;
- task/family failure matrices and deterministic failed-grader facets;
- access failures and invalid campaigns outside scored results;
- exact JSON artifacts and a reproducible environment manifest.

This protocol expands breadth without changing the research-only boundary. It
does not establish clinical competence, diagnostic validity, treatment-planning
suitability, or authorization for patient care.
