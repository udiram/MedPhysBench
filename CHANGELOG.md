# Changelog

## 2026-08-02 — Tie-aware public ranking

- changed official and descriptive point-estimate orders to shared competition ranks for
  exact metric ties, preventing model-name display order from becoming a performance claim;
- added Python and frontend regression coverage for tie handling and secondary-metric ordering;
- documented that shared exact ranks do not imply significance and interval overlap alone is
  not treated as a tie.
- fixed provider-filtered model summaries so a Groq-only slice cannot retain an Ollama route
  label (or vice versa) after the underlying variants have been filtered.

## Unreleased

- Added a schema-driven serial campaign control plane that binds release and fleet hashes, rejects credential-bearing manifests and result-directory collisions, enforces memory/disk guards, runs one isolated child process per model, verifies complete canonical matrices, and writes immutable hash-chained resume receipts. The committed five-model Groq plan is dry-run verifiable without a credential and does not claim five new scores.
- Added a strict `recorded-batch.v2` capture contract and three independently captured, fresh-context GPT-5.6 Terra high-effort attempts over the exact sealed OpenKBP batch. All 30 outputs are deterministically regraded and trace-bound to their public captures; the resulting 63.33% safe-success row appears beside every other model while remaining outside common-harness rank groups.
- Added a task-first, cross-model forensics table with direct run-set switching, persistent provider discovery across zero-result releases, an explicit 20/50 common-harness denominator in plot controls, mobile-first selected-task evidence, and contrast-safe outcome tints.
- Preserved redacted HTTP receipts, request IDs when supplied, body digests, and measured wall time when a provider rejects generated structured output; the failed attempt remains a scored zero and stays unranked when token usage is unavailable instead of gaining invented telemetry.
- Added optional artifact-build provenance to model run contracts so official provider routes and community quantizations can be disclosed in the same forensic surface with pinned source revisions.
- Enforced a default 50% task-family concentration ceiling at release load time, exposed the reviewed threshold in public reporting, and added strict-boundary and deterministic-error regressions so one correlated case family cannot quietly dominate a score.
- Added a deterministic task-to-defect projection and task-level QA history in result forensics, including disclosed defect counts, severity, resolution state, and immutable score treatment without inferring release-wide defects onto unaffected tasks.
- Froze a machine-readable 50-base-model fleet and added a deterministic public qualification funnel: 23 access-qualified, 20 common-harness evaluated and rankable under the current manifest contract, 29 published system configurations, 44 release rows, and no count inflation from aliases, provider routes, or GPT-5.6 effort settings.
- Completed 390 digest-pinned OpenKBP attempts across thirteen exact local model configurations under the memory-bounded `reference-json-v2` harness, with preflight chronology, immutable resume, provider-call telemetry, and an attested artifact tree for every row.
- Added a fully completed Pixtral 12B multimodal campaign through a pinned community Q4_K_M GGUF plus F32 vision projector: 30/30 real calls, 10.0% safe success, 60.0% safety, 100% schema validity, 43,128 total tokens, 41.562-second median wall time, a zero-change regrade, and exact source/model/projector SHA-256 provenance without mislabeling the build as official Mistral weights.
- Published a second Llama 3.1 8B Instruct route through exact Ollama artifact `sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`: 30/30 attempts, 0% safe success, 33.33% safety over 18 calls, 12 explicit capability-unavailable image attempts, 18,369 total tokens, and a 17.385-second median wall time. It remains grouped with—not counted separately from—the Groq-hosted route for base-model fleet breadth.
- Added Microsoft Phi-4 14B as an evidence-complete local row: 30/30 attempts, 10.0% safe success, 100% safety over 18 evaluable provider calls, 12 explicit capability-unavailable image attempts, 18,126 total tokens, and a 30.142-second median provider-call wall time.
- Corrected public outcome semantics so no-call capability failures remain zero-score primary outcomes without being mislabeled as unsafe model actions; safety and telemetry now expose evaluable and unavailable denominators, with the change recorded as public defect `MPB-2026-002`.
- Replaced raw integrity-code dumps in expanded model rows with counted, human-readable evidence groups; capability-unavailable task drilldowns now state that no provider call occurred and distinguish absent-submission contract failures from unsafe model actions.
- Added a fully vision-enabled Qwen2.5-VL 7B matrix with 30 real model calls, 12 image-grid attempts, 100% safety and schema validity, exact Ollama SHA-256 provenance, and an artifact-tree-attested submission bundle.
- Added opt-in, schema-filtered public-development answers, score/time/token telemetry, reduced deterministic grader verdicts, redacted provider receipts, and exact run-configuration disclosures. Aggregate-only is the default, non-public releases cannot expose answers, and provider IDs/reasoning-like fields are denied.
- Made model and forensic filter changes browser-history navigable, matched searches against visible provider labels, added explicit zero-result recovery, persisted deep links, and fixed duplicate React keys in family-level attempt chips.
- Added a schema-validated, machine-readable public defect/invalidation ledger with release/task binding, evidence-path checks, explicit score treatment, resolution state, byte-exact website projection, and an in-page disclosure for affected releases.
- Added a schema-validated common-harness submission sidecar, canonical artifact-tree hash, per-file SHA-256 inventory, exact release/source/model/environment attestations, CI validation, and tamper regressions so omitted failures or edited result files cannot silently enter a contributed rank.
- Required per-call model-response traces, provider/runtime receipts, token counts, and positive duration for common-harness rank eligibility. This quarantined a receipt-free Groq Qwen output-contract batch while preserving all 30 attempts for inspection.
- Made family-cluster intervals primary for patient-linked releases, retained Wilson intervals as secondary evidence, and excluded partial token/time telemetry from Pareto frontiers while keeping those rows visible with explicit coverage.
- Made review completion evidence-backed: completed human/domain states require a matched release, completion timestamp, and repository-relative SHA-256 evidence package; the website now reads the canonical review ledger instead of hard-coded human-baseline and review counts.
- Prevented seedless common-harness matrices from receiving a rank and prevented complete native/import rows from inflating the common-harness fleet funnel while preserving GPT-5.6 in the same public model and forensic views.
- Disclosed that v0.6 requires but does not semantically grade the `limitations` field, and added a repository gate requiring v0.7+ tasks to declare a score-bearing limitations grader when that field is required.
- Unified GPT-5.6, Groq, and Ollama discovery, provider/source filtering, score intervals, efficiency plots, and task-level failure drilldowns while preserving execution surface only as a comparability annotation; the default release-scoped interval view now plots every visible row on one scale and deep-links directly into attempts and grader failures.
- Added run manifest v2 with a hashed, credential-free adapter-settings contract; resume now rejects context, endpoint, schema-mode, retry, reasoning-effort, artifact-transport, or model-residency drift.
- Made unexpected harness exceptions fatal internal campaign errors instead of misclassifying them as provider transport failures; then completed a digest-pinned 30-attempt DeepSeek R1 1.5B Q2 matrix with 12 explicit unsupported-modality outcomes and 18 schema-valid text calls.
- Added attempt-level source/provider/model/domain/outcome/capability filters, failure-lane and grader anatomy, immutable hash drilldowns, family agreement views, and honest legacy deterministic-regrade labels.
- Froze comparison groups by adapter-settings hash and seed policy, withheld singleton ranks, and aligned the bulk regrader with the canonical safety-lane and weighted-score functions.
- Made the fleet headline data-derived, kept forensic controls mounted across empty filter intersections, and constrained the complete site shell horizontally after expanded desktop/mobile task-evidence QA.
- Added 150 Groq-hosted v0.6 attempts across Llama 3.1 8B Instant, Llama 3.3 70B Versatile, GPT-OSS 20B, GPT-OSS 120B, and Qwen 3.6 27B, with bounded rate-limit backoff and no persisted provider credential.
- Expanded the GPT-5.6 OpenKBP audit from one to three attempts per task and effort, publishing 90 native-surface attempts with Wilson intervals, repeated-attempt agreement, and a descriptive outcome order.
- Split official ranks by identical provider/harness revision while retaining a clearly labeled cross-surface point-estimate order, so native evidence is visible without being misrepresented as API-equivalent.
- Replaced the primary time scatter with a direct-labeled outcome interval plot and added frontier and reliability views grounded in SWE-bench, MLPerf, METR, and Artificial Analysis conventions.
- Fixed safe-success confidence intervals, per-attempt seed drift, immutable result preflight, recorded attempt indexing, provider edge compatibility, and model-failure versus transport-failure classification.
- Added a repeatable Sites release packager for the repository's nested `web/` application so the validated build and hosting metadata deploy as one exact-source archive.

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
