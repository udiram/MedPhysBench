# Changelog

## 0.6.0 - 2026-08-01

- Added the ten-task OpenKBP real-workflow pilot across two pinned head-and-neck cases, covering coarse segmentation, dose localization, plan-criteria audit, structure inventory, and TG-263 naming.
- Ran four locally reachable vision models for three attempts per task under one memory-bounded Ollama harness and published 120 sanitized, deterministically regraded attempt artifacts with timing and token telemetry.
- Added unranked GPT-5.6 low, high, and ultra recorded-output audits on the same sealed runtime batch without presenting native-surface results as common-harness ranks.
- Added family-cluster uncertainty, `pass@k` and `pass^k`, agreement and within-task variance, grader hashes, scoring revisions, scoring lanes, immutable release profiles, and a machine-readable independent-review/human-baseline ledger.
- Added source-grounded AAPM task-group coverage, an open-source planning-sandbox integration plan, a 30-participant human-baseline protocol, and explicit ABR/RAPHEX copyright and exam-integrity boundaries.
- Rebuilt the public site around the ranked/common-harness versus native-audit distinction, with responsive score/time/token visualizations, task-level evidence, blocked-access disclosure, and no zero-imputation of missing telemetry.
- Added sequential Ollama residency controls and a bounded OpenKBP fixture builder to prevent benchmark work from exhausting a developer workstation.

## 0.5.0 - 2026-07-31

- Published an 82-task hardening candidate and a dedicated 18-task TG-263-aligned structure-naming pilot with ambiguity, collision, laterality, target-grammar, and escalation cases.
- Added an independently authored TG-263 rule engine and 30 negative, metamorphic, immutability, and executable-reference tests without redistributing the copyrighted AAPM worksheet.
- Added a 20-phase radiation-therapy competency map, open-source planner integration ladder, AAPM TG/MPPG coverage map, contamination controls, rotating holdouts, paired counterfactuals, multi-seed reporting, and saturation criteria.
- Expanded the comparable public-core table to five local common-harness models, ranging from 25.00% to 73.44% safe success.
- Added input/output/total token aggregation, honest unavailable telemetry for native pilots, score-versus-token and score-versus-time charts, Pareto frontiers, confidence intervals, and a no-hover evidence table.
- Fixed the Ollama release runner so declared seed, temperature, and token limits are passed to the adapter; the v0.4 development snapshot retains a documented metadata discrepancy while v0.5 uses the corrected path.
- Stress-tested GPT-5.6 on the new structure-naming lane as unranked native-surface evidence rather than treating saturated v0.4 results as a common-harness rank.

## 0.4.0 - 2026-07-31

- Expanded the public core release from 16 to 64 original tasks across 11 domain labels, with 18 escalation-boundary cases and executable reference-feasibility checks for every authored task.
- Added deterministic bounding-box IoU and coarse-grid Dice graders plus hash-pinned artifact resolution for native multimodal adapters.
- Added attributed, reduced real-image fixtures from MSD MRI, LIDC-IDRI CT, and ENHANCE.PET, with a separately reported five-task localization, segmentation, and retrospective source-label pilot.
- Added sealed-runtime export and recorded-output scoring with exact task-set and batch-hash validation for six GPT-5.6 reasoning-effort pilots; native-surface results are explicitly unranked.
- Published a new 64-task common-harness Qwen baseline, real-image vision baselines, expanded source/licensing policy, and release-switching website UI.
- Hardened repository validation to verify every image digest, rebuild a grader-accepted reference output, and reject unsupported or self-inconsistent authoring contracts.
- Added task-declared exact alias normalization and an auditable bulk regrader after a pre-freeze fairness audit found two medically equivalent list labels; fuzzy matching remains disallowed.

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
