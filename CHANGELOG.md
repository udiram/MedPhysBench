# Changelog

## 0.3.0 - 2026-07-31

- Rebuilt the public website around a data-dense benchmark layout with a stronger leaderboard explorer, explicit release evidence strip, methodology and integrity sections, and a responsive view that preserves benchmark context.
- Tightened the structured-output contract: provider responses must now decode as exactly one JSON object with no Markdown fences, trailing text, duplicate keys, or non-finite numbers.
- Expanded run-manifest integrity coverage with separate `system_prompt_hash` and `runtime_task_hash` fields while retaining the legacy instruction hash for release comparability.
- Added release-level completeness and consistency checks so only complete, internally consistent model runs are ranked; ineligible runs remain published but unranked.
- Prevented complete matrices of provider-error attempts from receiving ranks and rejected mixed sampling, token-budget, sandbox, or tool-environment configurations.
- Added repository-wide JSON Schema validation across five versioned contracts, 17 authored/runtime task projections, and 224 public result artifacts.
- Re-ran all 11 locally reachable models under the frozen harness, sanitized 176 provider-backed outputs, and regenerated the public leaderboard from deterministic regrading.
- Extended regression coverage with strict parser, hash-drift, incomplete-run, mixed-configuration, repository-wide schema-validation, and property-based JSON-decoder tests.

## 0.2.0 - 2026-07-31

- Published the first public MedPhysBench development release with 16 tasks, deterministic graders, sealed runtime task views, a runnable Ollama harness, and a deployable public leaderboard site.
