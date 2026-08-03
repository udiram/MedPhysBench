# No-cost and free-tier model evaluation

Status checked: 2026-08-03. Provider plans, model catalogs, quotas, data-use terms, regions, and authentication
requirements can change without notice. Recheck every linked official page immediately before a run.

“Free” here means no provider invoice within a current allowance. It does not mean costless: local hardware,
electricity, engineering time, network access, and model-license obligations still apply. A route appearing below is
not evidence that MedPhysBench ran or scored a model. Only immutable result records produced by the declared harness
may support a benchmark claim.

## Route supported by this repository

### Local Ollama

Ollama documents local installation on macOS, Windows, and Linux, and exposes a local chat API at the default
`http://localhost:11434` endpoint ([official quickstart](https://docs.ollama.com/quickstart)). MedPhysBench currently
ships an Ollama adapter, so this is the direct no-per-request-fee path:

```bash
ollama pull <exact-model-id>
medphys-bench run-release releases/public_core_v0_4.yaml \
  --adapter ollama \
  --model <exact-model-id> \
  --results-dir runs
```

Before treating the run as comparable:

- record the exact Ollama and model identifiers, request settings, harness revision, and run date;
- preserve provider-native token and latency telemetry when returned;
- check the selected model's license and redistribution terms independently;
- record insufficient RAM/VRAM, timeouts, and provider failures as failed/error attempts rather than deleting them;
- do not send restricted, patient-identifiable, credentialed, or live-clinical-system data to the model.

Local execution avoids a hosted inference bill, but the operator bears compute and energy costs. Ollama Cloud is a
different service and must not be described as free based on the local route.

For a memory-constrained workstation, run one model campaign at a time, set
`OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`, and `OLLAMA_MAX_QUEUE=1`,
use a declared context window, and set `--ollama-keep-alive 0` or explicitly
`ollama stop <exact-model-id>` between campaigns. The v0.6 public runs used a
4,096-token context and were monitored with a 30% free-memory stop threshold.

### Groq and generic OpenAI-compatible APIs

The repository now ships a strict OpenAI-compatible Chat Completions adapter and
a Groq preset. It preserves the exact provider/model ID, response format,
reasoning setting when supported, usage metadata, request IDs, and errors. A
Groq run requires `GROQ_API_KEY`; the [official free-plan limits](https://console.groq.com/docs/rate-limits)
are model-specific and mutable. On 2026-08-01, four chat-model IDs completed rankable
public OpenKBP v0.6 matrices: `llama-3.1-8b-instant`,
`llama-3.3-70b-versatile`, `openai/gpt-oss-20b`, and `openai/gpt-oss-120b`. A
Qwen route reached all 30 task attempts but failed the provider output contract and remained
unranked. The historical request is preserved; the corrected
[`groq_reasoning_routes_v2.yaml`](../fleet/groq_reasoning_routes_v2.yaml) contract uses Groq's
documented `reasoning_effort: none` and `reasoning_format: hidden` fields and still needs a fresh
successful receipt plus complete rerun before promotion.

```bash
GROQ_API_KEY=... medphys-bench run-release \
  releases/public_real_workflows_pilot_v0_6.yaml \
  --adapter groq \
  --model <exact-groq-model-id> \
  --attempts 3 \
  --response-format json_object \
  --best-effort-schema \
  --results-dir runs
```

The shared `json_object` contract was used because structured `json_schema` mode
was not available across all five models. The harness still applies each task's
deterministic JSON Schema grader after parsing. HTTP 429 responses receive bounded,
traced backoff. Unsupported required modalities and provider JSON-generation
failures count as completed zero-score model failures; exhausted transport failures
remain campaign-invalidating errors. The benchmark never stores the key. A free-plan
quota that cannot complete the declared attempt matrix yields an unranked partial
package, not a shortened rank.

Groq's current deprecation schedule also matters for reproducibility: Llama 3.1 8B Instant and
Llama 3.3 70B Versatile are scheduled to shut down on 2026-08-16, while Qwen3-32B and Llama 4 Scout
were retired on 2026-07-17 ([official deprecations](https://console.groq.com/docs/deprecations)).
Historical rows remain auditable, but a retired handle is not a present-day rerun route.

## Declared hosted routes that still require access evidence

The generic OpenAI-compatible adapter can execute the frozen Gemini/Cohere and corrected Groq route
contracts in [`fleet/`](../fleet/), but a declaration is not proof of access. Each route must produce
a fresh content-addressed canary receipt and a complete evidence-bound campaign before it can add a score.

### Gemini API free tier

Google states that new accounts begin on a Free Tier that exposes certain Gemini API and AI Studio models up to each
model's free-tier rate limits ([official billing guide](https://ai.google.dev/gemini-api/docs/billing),
[official rate-limit guide](https://ai.google.dev/gemini-api/docs/rate-limits)). An eligible Google project and API key
are required. Availability is model- and region-dependent; preview models can have tighter limits. Confirm current
data-use and billing terms for the exact project before sending benchmark content. Enabling billing changes the cost
boundary, so keep paid use disabled when the intent is a no-cost run.

## Retired surfaces

### GitHub Models — retired, not an evaluation route

GitHub retired the Models playground, catalog, inference API, and BYOK service for all customers on
2026-07-30 ([official retirement notice](https://docs.github.com/en/github-models)). The endpoint now
returns HTTP 410 and must not be advertised as a free fleet-expansion path. GitHub Copilot is a separate
product, not a substitute reproducible inference API for this benchmark.

## Current hosted allowances that require adapter or route work

The services below remain candidates, not completed integrations or benchmark results. A new route must
preserve the sealed runtime task, immutable run manifest, exact provider/model revision, raw usage metadata,
errors, and safety boundary before any scored run.

### Hugging Face Inference Providers credits

Hugging Face currently documents a small monthly credit for free users, explicitly marked subject to change, for
routed Inference Providers requests. Routed calls use a Hugging Face User Access Token, and continued use after the
credit is exhausted requires purchased credits ([official pricing and billing page](https://huggingface.co/docs/inference-providers/en/pricing)).
Treat this as an experimental allowance, not a guarantee that a full release fits within the credit. Pin the selected
underlying provider and exact model; do not pool unlike backends under one model label.

### OpenRouter free-model routing

OpenRouter documents a `:free` model variant and a changing catalog of free models, together with account-level
request limits ([official free-variant guide](https://openrouter.ai/docs/guides/routing/model-variants/free),
[official limits reference](https://openrouter.ai/docs/api/reference/limits)). An adapter must pin the exact resolved
model and upstream provider rather than publishing the rotating router alias as if it were one stable system. Treat
rate-limit exhaustion and upstream substitution as provenance events, and do not combine them into one model row.

## Credential and quota rules

- Keep API keys and access tokens outside the repository and result artifacts. Use environment variables or an
  approved secret store, never task context or model prompts.
- Check the live quota before dispatch. A complete release must retain every expected attempt key; quota exhaustion
  is an error state, not permission to publish a partial run as complete.
- Do not silently switch provider, model, quantization, context window, reasoning setting, or paid tier mid-run.
- If free capacity cannot finish the declared release under one immutable configuration, stop and publish no rank.
- Never use a free hosted route for restricted or patient-derived tasks unless governance, agreements, and the task's
  access policy explicitly authorize that provider. Public synthetic/de-identified eligibility does not itself waive
  provider terms or institutional review.

## Analytics without fabricated telemetry

Build a separate analytics artifact from existing result records:

```bash
PYTHONPATH=src python scripts/build_leaderboard_analytics.py \
  results/releases/public-core-v0.4 \
  --leaderboard results/releases/public-core-v0.4/leaderboard.json \
  --output /tmp/public-core-v0.4-analytics.json
```

The analytics layer reports token, latency, and throughput values only when observed. Missing usage remains `null`
with explicit sample and missing counts; it is never converted to zero. Recorded-output pilot import time is not model
latency, and leaderboard-ineligible pilot surfaces are excluded from Pareto frontiers.
