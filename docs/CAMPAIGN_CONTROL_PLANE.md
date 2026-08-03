# Campaign control plane

## Purpose

MedPhysBench separates the control plane from the scoring plane. The scoring
plane already produces immutable, deterministically regradable task/attempt
artifacts. The campaign layer schedules many exact system configurations without
weakening those contracts, inventing missing attempts, or allowing a laptop model
sweep to exhaust the host.

This design follows three useful benchmark precedents:

- [SWE-bench](https://github.com/SWE-bench/SWE-bench) uses isolated evaluation
  environments, explicit run IDs, logs, and resource guidance for reproducible
  system evaluation.
- [MLPerf Inference submissions](https://docs.mlcommons.org/inference/submission/)
  require declared configurations, complete required scenarios, structured result
  packages, accuracy validation, and a submission checker rather than accepting a
  headline number alone.
- [METR's time-horizon work](https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/)
  publishes raw data and analysis code and models dependence across task families;
  MedPhysBench likewise retains attempt evidence and family-aware uncertainty.

The analogies are methodological, not claims that MedPhysBench has their scale,
review history, or institutional maturity.

## Frozen manifest

`medeval.campaign.v1` requires:

- a stable campaign ID;
- a repository-relative release file, release ID, and exact release-contract v2
  hash;
- a frozen fleet file and fleet ID;
- a repository-relative `runs/` destination, kept separate from reviewed public
  result packages;
- the full release attempt count;
- serial, process-isolated, immutable-resume execution;
- absolute and fractional memory floors plus a disk floor; and
- one or more explicit system configurations with base-model ID, provider,
  adapter, declared provider model handle/revision string, response contract, sampling
  settings, timeout, and token cap.

Hosted configurations store only the name of the credential environment variable.
URLs with user-info, query parameters, or fragments are rejected. Ollama entries
must use `keep_alive=0`, declare a context window, and may not declare an API key.
Provider model handles must map to unique result directories inside a campaign;
alternate revisions and effort settings get a different campaign/results root.

`medeval.campaign.v2` adds a qualification boundary before execution. Every model
entry binds an exact `model-route.v1` route and one immutable
`access-probe-receipt.v1` by path and SHA-256. The receipt binds the route hash,
fleet/base-model identity, provider handle/revision basis, reviewed probe
implementation path/hash and source commit, timestamps, typed access outcome,
the route's required response contract, observed versus inferred
capabilities, sanitized metadata, and quota assessment. Raw response bodies and
secret-like fields are invalid receipt metadata.

The deterministic `generate-campaign` command requires an explicit RFC 3339
`--as-of` instant, one receipt per selected route, and one provider/adapter/
credential surface per manifest. It rejects stale, future-dated, hash-tampered,
identity-mismatched, unavailable, or insufficient-quota receipts. Unknown quota
fails closed unless the v2 manifest records an explicit override. Generation
writes only the requested manifest; it does not contact a provider or create
scored or run-state artifacts.

## Execution sequence

```text
validate schema and paths
  -> bind release hash and frozen base-model IDs
  -> check credential presence, memory, and disk
  -> acquire one campaign lock
  -> for each model in manifest order
       -> recheck memory and disk
       -> append hash-chained model-start receipt
       -> launch one typed child process
       -> run existing immutable run-release --resume
       -> verify every canonical task/attempt key
       -> open provider-wide quota circuit when new bounded-retry evidence is 429/quota exhaustion
       -> append completion or failure receipt
  -> append campaign completion receipt
```

There is no shell interpolation and no user-authored command field. A fresh child
process prevents client/runtime objects from accumulating across models. The
child receives only a small runtime allowlist (`PATH`, locale, temporary directory,
certificate/proxy settings, and similar process essentials) plus that model's one
declared credential variable; unrelated API keys in the parent process are not
inherited. The
control plane does not shorten the release after rate limits or resource pressure.
A transport failure remains in `_transport_errors`, the canonical attempt stays
missing, and the configuration is not complete.

Only transport-error files created by the current child are considered for the
provider circuit breaker. A 429, explicit quota exhaustion, rate-limit exhaustion,
or usage-limit receipt blocks later configurations on that provider for the same
campaign and records each skip; unrelated providers remain eligible. Historical
retry receipts do not by themselves block a successful resumed matrix, and raw
provider error bodies are not copied into campaign events.

A missing credential stops before state is created. A measurable resource
preflight failure writes only the immutable state header and a hash-chained
`campaign_preflight_failed` receipt; it starts no model and creates no scored
artifact.

## Resume and tamper evidence

The first real run creates:

```text
runs/<campaign>/_campaigns/<campaign-id>/campaign.json
runs/<campaign>/_campaigns/<campaign-id>/events.jsonl
```

`campaign.json` is created exclusively and binds the campaign manifest hash,
release-contract hash, fleet, release, and result root. It is never treated as a
score ledger. Each JSONL event contains a sequence number, previous-event hash,
manifest hash, timestamp, event ID, type, details, and its own content hash. Any
edit, deletion, reordering, or cross-manifest reuse breaks validation before new
work begins.

The canonical result tree remains authoritative. After every zero-exit child, the
controller rejects missing or unexpected canonical files and rechecks status,
attempt index, provider/model/harness identity, declared revision, adapter settings
and hash, sampling settings, every task-contract hash, scoring revision, run ID,
and deterministic grades, pass/safety flags, and score. The completion record also
includes the same canonical artifact inventory count and tree hash used by the public
submission contract, so the hash-chained `model_completed` event binds the exact files
that passed verification. `run-release --resume`
performs the same class of validation before skipping any immutable attempt.

## Honest limits

The controller does not create provider access, guarantee free quota, or turn the
50-model frozen target into 50 evaluated models. The repository does not commit
invented successful probe receipts. Provider-specific probe implementations
remain adapter work where they do not implement the reviewed OpenAI-compatible
probe, because providers expose materially different identity and quota surfaces.
Today the committed v1 manifest proves a safe, reproducible
150-attempt Groq campaign plan for five frozen base models; it reports missing
credentials in dry-run output without contacting Groq. The committed route set
makes those handles executable candidates, but they cannot be emitted into a v2
campaign without fresh receipt evidence.

Hosted model names may still be mutable provider aliases. The route contract labels
that limit as `revision_basis: provider_alias`; neither an access receipt nor
campaign v2 transforms an alias into an immutable weight revision. Dated receipts,
served-model metadata when exposed, and exact run metadata remain visible. An
immutable digest is claimed only when the provider or runtime supplies one.

Public promotion still requires a complete common-harness submission, artifact
tree hash, exact environment and model provenance, and the existing qualification
checks. A campaign completion receipt is necessary operational evidence, not a
leaderboard admission decision.
