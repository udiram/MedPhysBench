# Fifty-model fleet protocol

Status: execution protocol; target matrix not yet complete  
Review date: 2026-08-02

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

### Q1 — three-task adapter contract

Run one schema task, one calculation/artifact task, and one required-escalation
task. Validate structured output, deterministic seeds where supported, token and
duration capture, request IDs, bounded retries, and secret redaction.

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

Hosted free-tier campaigns must snapshot live quotas before dispatch. HTTP 429,
retired handles, and weekly limits are access failures, not model failures. The
runner must resume missing immutable attempt keys without overwriting completed
artifacts and must never shorten the matrix to fit a quota.

## Current state

The public website currently exposes 20 model configurations across four release
surfaces, including five completed Groq configurations and six GPT-5.6 effort
configurations. These are not 20 unique base models. An Ollama Cloud access probe
for `qwen3.5:397b-cloud` on 2026-08-02 returned HTTP 429 before a scored artifact
was created. The lab-node hostname was not resolvable from the current Mac
network context. Neither event supports a model score.

The 50-model target therefore remains an execution objective. MedPhysBench must
publish the actual completed count and the access ledger until all 50 base-model
matrices exist; the site must never display a planned model as evaluated.

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
