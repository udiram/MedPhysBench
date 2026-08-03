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

## Receipt integrity

The original [`openai_access_probe.py`](../scripts/probes/openai_access_probe.py) remains byte-frozen
because historical receipts bind its exact SHA-256. New dialect routes use
[`openai_access_probe_v2.py`](../scripts/probes/openai_access_probe_v2.py), which records and verifies
an exact dependency set covering the v1 probe, runtime request helper, strict JSON decoder, and
route/receipt validator. The receipt loader rejects missing, extra, substituted, or modified
dependencies and checks the same bytes in both the worktree and claimed source commit.

After committing the route and probe sources, qualify one route at a time:

```bash
python scripts/probes/openai_access_probe_v2.py \
  fleet/provider_expansion_routes_v2.yaml \
  --route-id google-gemini-3.6-flash
```

The probe sends only a fixed JSON canary. It never loads a benchmark task, grader, expected answer,
or patient artifact. Provider response bodies and credentials are not written to the receipt.

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
