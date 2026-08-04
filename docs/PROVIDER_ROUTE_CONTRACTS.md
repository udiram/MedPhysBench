# Provider Route and Request-Dialect Contracts

## Why this exists

“OpenAI-compatible” does not mean byte-identical requests. A provider can expose the same
`/chat/completions` path while using a different completion-limit key, structured-output envelope,
sampling policy, or reasoning field. MedPhysBench freezes those differences as part of the tested
system rather than silently retrying with whatever payload happens to work.

A route declaration is **not** evidence that a model is accessible, benchmarked, or rankable. A
model reaches a scored campaign only after the declared route produces a fresh, content-addressed
access receipt and the campaign completes the same immutable run, submission, and integrity gates
as every other model.

## Declared dialect

All fields are optional. Their absence preserves the legacy Groq/OpenAI behavior and therefore the
existing route, campaign, harness, and adapter-setting hashes.

| Field | Legacy default | Meaning |
| --- | --- | --- |
| `send_temperature` | `true` | Include the declared temperature in the provider request. |
| `send_seed` | `true` | Include the per-attempt seed in the provider request. |
| `completion_limit_field` | `max_completion_tokens` | Select exactly one provider completion-limit key. |
| `response_format_dialect` | `openai` | Use the OpenAI envelope, Cohere envelope, or omit the provider field. |
| `send_reasoning_effort` | `true` | Include `reasoning_effort` only when a value is declared. |
| `reasoning_format` | omitted | Freeze provider-native reasoning transport as `hidden`, `parsed`, or `raw`; it is part of route and campaign identity. |

When sampling fields are omitted, the immutable run manifest records `null`; it does not pretend
that a seed or temperature reached the model. `strict_schema: true` is invalid when response format
is omitted, and a route cannot declare a reasoning effort while suppressing that request field.
An omitted response-format field may be useful for adapter development, but a parseable JSON reply
does not prove provider-enforced structured output: the v2 access probe records that case as
`contract_unsupported`, so it cannot enter an evidence-bound comparison campaign.

## Frozen expansion routes

[`provider_expansion_routes_v2.yaml`](../fleet/provider_expansion_routes_v2.yaml) declares six
Gemini bases and Cohere Command A+ without changing the five frozen Groq routes.

| Surface | Frozen behavior | Primary evidence |
| --- | --- | --- |
| Gemini OpenAI compatibility | OpenAI structured-output envelope; `max_completion_tokens`; temperature omitted for Gemini 3.6 Flash and 3.5 Flash-Lite | Google documents the compatibility base URL, structured outputs, and reasoning-effort mapping. Its July 2026 model guidance says the two new models require deprecated sampling parameters such as temperature to be removed. [Compatibility](https://ai.google.dev/gemini-api/docs/openai) · [latest models](https://ai.google.dev/gemini-api/docs/latest-model) |
| Cohere compatibility | `max_tokens`; `{type: json_object, schema: ...}`; temperature and seed included | Cohere documents the compatibility URL, exact structured-output envelope, supported request fields, and the `none`/`high` reasoning restriction. [Compatibility API](https://docs.cohere.com/docs/compatibility-api) · [Command A+](https://docs.cohere.com/docs/command-a-plus) |
| NVIDIA build endpoint | Not yet in this route set | NVIDIA documents an OpenAI-compatible endpoint and a free Llama 3.2 90B Vision route using `max_tokens`, but the current frozen fleet declares that base only for self-hosting. It needs a new fleet/route contract and fresh evidence rather than an in-place rewrite. [NVIDIA model endpoint](https://build.nvidia.com/meta/llama-3.2-90b-vision-instruct/build) |

[`groq_reasoning_routes_v2.yaml`](../fleet/groq_reasoning_routes_v2.yaml) freezes a corrected
Qwen 3.6 27B route without rewriting the historical Groq route used by prior attempts. Groq's
current model contract documents text and image input, JSON-object mode, `reasoning_effort: none`,
and `reasoning_format: hidden`; those fields therefore form part of the new route identity rather
than an undocumented retry heuristic. [Groq Qwen 3.6 model contract](https://console.groq.com/docs/model/qwen/qwen3.6-27b)

[`groq_gpt_oss_routes_v3.yaml`](../fleet/groq_gpt_oss_routes_v3.yaml) separately freezes GPT-OSS
20B and 120B at low reasoning effort with strict JSON Schema output. It does not rewrite the
published JSON-v2 comparison group. Groq documents both bases as strict-structured-output models,
states that best-effort JSON modes can return HTTP 400, and recommends enough completion budget for
reasoning output. The paired v3 routes therefore use the same 4,096-token scoring cap and can form
one controlled group only after both routes independently qualify and complete the full matrix.
The route declarations themselves are not access or score evidence.
[Groq GPT-OSS 120B](https://console.groq.com/docs/model/openai/gpt-oss-120b) ·
[Groq structured outputs](https://console.groq.com/docs/structured-outputs) ·
[Groq reasoning](https://console.groq.com/docs/reasoning)

[`local_ollama_routes_v1.yaml`](../fleet/local_ollama_routes_v1.yaml) freezes 16 existing,
submission-attested local configurations. A separate
[`local_ollama_candidate_routes_v1.yaml`](../fleet/local_ollama_candidate_routes_v1.yaml) isolates
the digest-pinned default Qwen3-VL 8B tag so its failed strict-output probe remains reproducible.
That artifact declares Ollama's `qwen3-vl-thinking` renderer and is not promoted as the frozen
Instruct base. [`local_ollama_candidate_routes_v2.yaml`](../fleet/local_ollama_candidate_routes_v2.yaml)
separately pins the non-thinking `qwen3-vl:8b-instruct` artifact and its
`qwen3-vl-instruct` renderer; the variants never share a route identity or receipt. Each route binds the mutable Ollama
tag to its observed immutable artifact digest, exact base-model ID, 4,096-token context,
JSON-schema output, and `keep_alive=0`. The separate
[`local_ollama_candidate_routes_v3.yaml`](../fleet/local_ollama_candidate_routes_v3.yaml)
pins the community Q4_K_M Phi-4 Multimodal artifact to its observed Ollama manifest digest.
Ollama exposes that imported GGUF as text-only because no vision projector is present, so the
route declares only `text`; required-image tasks must remain explicit capability-unavailable
outcomes unless a separately frozen projector-backed route is qualified. These candidate route
sets do not add scores: they make the already-published current-contract local lane and explicit
unevaluated candidates addressable
by the same receipt-bound control plane used for hosted providers. The Qwen3-VL Instruct route must still
produce a fresh access receipt, complete campaign, and attested submission before it can affect
evaluated breadth or any score surface.

[`ollama_cloud_routes_v1.yaml`](../fleet/ollama_cloud_routes_v1.yaml) isolates the installed
`gpt-oss:120b-cloud` handle as a provider-hosted configuration of the already frozen
`openai/gpt-oss-120b` base. The route pins the exact snapshot identifier exposed by the local
Ollama proxy and declares only the text capability returned by `/api/show`. That identifier is
replay evidence for the observed hosted route, not a claim that Ollama exposes an immutable weight
artifact. Calls leave the workstation for Ollama Cloud even though the transport endpoint is the
local Ollama API. The configuration therefore requires a fresh canary receipt, an explicit quota
assessment, the full 30-attempt matrix, deterministic regrading, and a submission attestation before
it can appear as scored evidence. It strengthens one existing base-model record and never increments
the 50-model denominator as a second model.

Cloud handles use the separately versioned
[`ollama_cloud_access_probe_v2.py`](../scripts/probes/ollama_cloud_access_probe_v2.py). Unlike the
immutable local-runtime probe, it never treats local proxy availability as sufficient hosted quota:
a successful canary retains `quota.status: unknown`, HTTP 429 is `rate_limited` with insufficient
quota, and HTTP 401/403 is an authentication failure. Provider error bodies are consumed and
discarded rather than persisted.

## Receipt integrity

The original [`openai_access_probe.py`](../scripts/probes/openai_access_probe.py) remains byte-frozen
because historical receipts bind its exact SHA-256. New dialect routes use
[`openai_access_probe_v2.py`](../scripts/probes/openai_access_probe_v2.py), which records and verifies
an exact dependency set covering the v1 probe, runtime request helper, strict JSON decoder, and
route/receipt validator. The receipt loader rejects missing, extra, substituted, or modified
dependencies and checks the same bytes in both the worktree and claimed source commit.

The GPT-OSS schema routes use a new, separately hashed
[`openai_access_probe_v3.py`](../scripts/probes/openai_access_probe_v3.py) rather than changing the
published v2 implementation. Its fixed non-benchmark canary uses a 512-token ceiling so a
reasoning model is not rejected by an unrealistically small access check, proves the declared
strict-schema response contract, and classifies sanitized HTTP 400 provider codes as contract
failures instead of network failures. It records neither the provider body nor the credential.

The reviewed [`ollama_access_probe.py`](../scripts/probes/ollama_access_probe.py) applies the same
principle to the local runtime. It verifies `/api/tags` against the exact route digest, checks
declared text/vision capability through `/api/show`, and sends a 64-token strict-JSON canary through
`/api/chat`. It records only sanitized capability, digest, timing, and outcome metadata. It never
loads a benchmark task or retains a response body, and `keep_alive=0` unloads the probed model after
the request.

After committing the route and probe sources, qualify one route at a time:

```bash
uv run python -m scripts.probes.openai_access_probe_v2 \
  fleet/provider_expansion_routes_v2.yaml \
  --route-id google-gemini-3.6-flash

# Qwen's corrected Groq request contract. Requires GROQ_API_KEY in the process
# environment; the value is never accepted as a CLI argument or written.
uv run python -m scripts.probes.openai_access_probe_v2 \
  fleet/groq_reasoning_routes_v2.yaml \
  --route-id groq-qwen-3.6-27b-json-v2

# Three distinct frozen base models sharing one current comparison contract.
# Probe each route independently before generating a multi-model campaign.
uv run python -m scripts.probes.openai_access_probe_v2 \
  fleet/groq_standard_routes_v2.yaml \
  --route-id groq-gpt-oss-20b-json-v2

# Versioned GPT-OSS strict-schema qualification. Qualify both routes before
# generating a paired campaign; a failed receipt remains non-scoring evidence.
uv run python -m scripts.probes.openai_access_probe_v3 \
  fleet/groq_gpt_oss_routes_v3.yaml \
  --route-id groq-gpt-oss-120b-schema-v3

# Local, digest-pinned example. Run one route at a time on the machine that
# actually hosts Ollama; the probe is non-scoring and memory bounded.
uv run python scripts/probes/ollama_access_probe.py \
  fleet/local_ollama_routes_v1.yaml \
  --route-id ollama-deepseek-r1-1-5b
```

The probe sends only a fixed JSON canary. It never loads a benchmark task, grader, expected answer,
or patient artifact. Provider response bodies and credentials are not written to the receipt.
An `auth_missing`, quota, or contract-failure receipt documents the blocked route but cannot be
promoted into a scoring campaign. After an `available` receipt exists, use the evidence-bound
`generate-campaign` workflow in [REPRODUCIBILITY.md](REPRODUCIBILITY.md); do not hand-author a
replacement score row.

## Promotion gate

For each unique base model:

1. commit the exact route/probe/fleet bytes;
2. create a fresh receipt with outcome `available` and sufficient quota, or an explicit recorded
   unknown-quota override;
3. generate an evidence-bound `campaign.v2` manifest from that receipt;
4. run the frozen release serially with process isolation and memory/disk guards;
5. require the exact task-by-attempt matrix, complete telemetry, deterministic regrading, immutable
   submission sidecar, and artifact-tree attestation;
6. publish the model in the same table and forensic workbench as every other provider, while keeping
   incompatible harness/settings groups visibly distinct.

Aliases, quantizations, provider mirrors, retries, and reasoning settings remain tested
configurations—not additional unique base models.
