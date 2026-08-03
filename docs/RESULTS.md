# MedPhysBench results through the OpenKBP v0.6 pilot

## What was evaluated

On July 31, 2026, MedPhysBench froze two public development releases:

- `public-core-v0.4`: 64 original medical-physics calculation, interpretation,
  audit, and escalation tasks across 11 reported domain labels.
- `public-imaging-pilot-v0.4`: five attributed retrospective MRI, CT, and PET
  localization, coarse-segmentation, and source-label tasks.

Version 0.5 adds an 82-task hardening candidate and an independently authored,
18-task TG-263-aligned structure-naming pilot. The 82-task candidate is not yet
presented as a common-harness leaderboard: the frozen 64-task v0.4 table remains
the directly comparable model snapshot.

Version 0.6 adds a separate ten-task OpenKBP real-workflow pilot derived from
two patient families. It is reported independently from the core and original
five-image pilot.

The primary metric is safe task success: an attempt must pass every required
outcome grader and every explicit safety-lane gate. For patient-linked releases,
the deterministic family-cluster bootstrap is the primary interval and the Wilson
95% attempt interval remains a secondary sensitivity analysis. The v0.6 pilot has
only two patient families, far too few for external-validity claims.

## Public model-fleet status

The preregistered breadth target is 50 unique base model IDs, not 50 prompt or
provider variants. The frozen v1 panel contains 31 open-weight and 19 closed-
weight models, including 31 declared vision-capable entries across 11 stewards.
The machine-derived public status currently reports:

| Qualification gate | Unique base models | Meaning |
| --- | ---: | --- |
| Frozen panel | 50 | Selected before further score inspection |
| Published access/evidence | 24 | Some route-backed or native public evidence exists; this is not a common-harness gate |
| Attested common-harness evaluated | 18 | At least one submission-attested complete matrix satisfies the current manifest/scoring and execution-evidence contract |
| Rankable | 18 | At least two attested systems share an exact frozen comparison group |

The site exposes all 31 published system configurations and 49 release
rows. Six GPT-5.6 Sol effort settings remain six auditable configurations
of one base model, while the separately cataloged GPT-5.6 Terra system contributes
one additional base model and configuration. Groq-hosted and local routes of the same open-weight
base also count once toward breadth. Five legacy core-only base models remain
visible but no longer count as current-contract evaluated because their v1
artifacts predate grader hashes and scoring revisions. `deepseek-r1:1.5b` completed
all 30 Q2 attempts with an immutable Ollama artifact digest; 12 image-grid attempts
are explicit unsupported-modality failures rather than omitted requests.

## Historical core common-harness snapshot

These models completed the same 64 tasks through the Ollama adapter with
temperature 0 and seed 20260731. Their point estimates are preserved as a historical
snapshot, but current reporting withholds official ranks because the v1 artifacts
predate grader hashes and the scoring-revision field.

| Historical order | Model | Safe success | 95% CI | Safety gate | Valid output |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `qwen3:14b` | 73.44% | 61.52–82.70% | 98.44% | 100.00% |
| 2 | `qwen3:8b` | 57.81% | 45.61–69.13% | 98.44% | 100.00% |
| 3 | `qwen2.5:7b-instruct` | 50.00% | 38.10–61.90% | 96.88% | 100.00% |
| 4 | `llama3.2:3b` | 26.56% | 17.30–38.48% | 96.88% | 100.00% |
| 5 | `qwen3:1.7b` | 25.00% | 16.01–36.82% | 92.19% | 100.00% |

The 14B baseline missed 17 tasks in total, including one safety boundary. Its
errors span decay and attenuation arithmetic, uncertainty/statistics, DICOM
sets and size calculations, quantitative nuclear medicine, radiobiology, and
the plan-release boundary. The result is materially more informative than the
earlier 16-task release because no single item moves the score by more than
1.56 percentage points.

### Efficiency telemetry

| Model | Median tokens / attempt | Total tokens | Median wall time / attempt |
| --- | ---: | ---: | ---: |
| `qwen3:14b` | 507 | 33,073 | 9.813 s |
| `qwen3:8b` | 511 | 33,248 | 4.617 s |
| `qwen2.5:7b-instruct` | 497.5 | 32,528 | 4.218 s |
| `llama3.2:3b` | 504 | 32,631 | 2.476 s |
| `qwen3:1.7b` | 505 | 33,108 | 1.767 s |

Token counts are provider-reported and tokenizer-specific. Wall time is the
common-harness per-attempt duration, not total campaign duration and not
provider-side compute time. The website plots score
against tokens and time, shows 95% score intervals and the ranked Pareto frontier,
and preserves a complete table for readers who cannot use hover interactions.

During v0.5 hardening, an audit found that the v0.4 CLI recorded the requested
2,048-token budget but the Ollama adapter used its 1,024-token default. All five
common-harness runs used the same effective limit and every published response was
shorter than that limit, so no output was truncated; however, the v0.4 manifest
field is inaccurate. The runner now passes the declared seed, temperature, and
token limit into the adapter. This is a known public-development provenance defect,
and v0.5 runs must use the corrected path before any stronger comparison claim.

## GPT-5.6 native-surface pilot

Six `gpt-5.6-sol` configurations completed the exact sealed core runtime batch.
The batch SHA-256 was
`9a09159ecfa6368fff09aa375d58ae6a97ef9b8f3876f6417df87dde461763bb`;
all imports matched all 64 task IDs exactly and passed schema validation.

| Reasoning effort | Safe success | 95% CI | Safety gate | Rank status |
| --- | ---: | ---: | ---: | --- |
| low | 98.44% | 91.67–99.72% | 100.00% | Unranked native pilot |
| medium | 98.44% | 91.67–99.72% | 100.00% | Unranked native pilot |
| high | 100.00% | 94.34–100.00% | 100.00% | Unranked native pilot |
| xhigh | 98.44% | 91.67–99.72% | 100.00% | Unranked native pilot |
| max | 100.00% | 94.34–100.00% | 100.00% | Unranked native pilot |
| ultra | 100.00% | 94.34–100.00% | 100.00% | Unranked native pilot |

These are real model outputs but not common-harness scores. The native Codex
surface did not expose equivalent API sampling controls or process isolation,
so the reporting layer marks every row `unranked_native_pilot_surface`. No hidden
reasoning is stored. Low and medium missed the requested qualified-owner role on
one release-boundary task; xhigh missed one protocol-checklist set. High, max,
and ultra passed all 64 deterministic task contracts.

## Harder TG-263-aligned native pilot

The `public-tg263-pilot-v0.5` release contains 18 synthetic cases covering
conservative normalization, target grammar, missing or contradictory laterality,
case-insensitive collisions, unknown structures, and mandatory escalation. It uses
an independently authored rule subset and does not redistribute AAPM's worksheet.

| Native surface | Strict pilot safe success | 95% CI | Safety gate | Escalation accuracy | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| GPT-5.6 high | 27.78% | 12.50–50.87% | 100% | 100% | Unranked native pilot |
| GPT-5.6 ultra | 22.22% | 9.00–45.21% | 100% | 100% | Unranked native pilot |

The result demonstrates why a perfect score on one small public set is not a
general capability claim. The harder lane distinguishes strict schema-compliant
answers and safe abstention from exact structure-naming competence. High and ultra
both preserved every required escalation boundary, but neither achieved a high
outcome score. The rows remain unranked because they were collected on a native
conversation surface without comparable latency, token, or sampling telemetry.

### TG-263 audit on Saturday, August 1, 2026

An audit of the stored TG-263 native pilot outputs separated primary decision
correctness from benchmark-authored `reason_codes` label exactness. Under that
audit:

- GPT-5.6 high: `17/18` primary naming decisions correct (`94.44%`)
- GPT-5.6 ultra: `17/18` primary naming decisions correct (`94.44%`)
- strict pilot pass remained `5/18` for high and `4/18` for ultra because the
  pilot required one exact internal `reason_codes` vocabulary

The dominant failure mode was not incorrect action, incorrect canonical name,
or incorrect escalation. It was semantically correct but non-identical rationale
labels such as `alias_normalized`, `laterality_suffix_applied`, or
`valid_target_open_grammar` where the pilot expected one benchmark-authored code
such as `deterministic_normalization` or `valid_target_grammar`. One true
primary-decision miss remained in the case-insensitive collision task, where the
model escalated correctly but omitted the benchmark's retained proposed canonical
name. The public site now exposes this audit separately so the pilot can remain
auditable without overstating a weak strict score as weak TG-263 competence.

## Real-image pilot

The public image pilot uses a CC BY-SA 4.0 MSD hippocampus MRI, a CC BY 3.0
LIDC-IDRI chest CT, and a CC BY-NC 4.0 AutoPET-subset ENHANCE.PET MIP. Gold masks,
boxes, and the released PET source label remain outside the model-visible runtime.

| Surface | Model / effort | Safe success | Safety gate | Valid output | Status |
| --- | --- | ---: | ---: | ---: | --- |
| Ollama vision | `gemma3:4b` | 0/5 | 100% | 80% | Historical; current-contract rank withheld |
| Ollama vision | `qwen2.5vl:3b` | 0/5 | 100% | 100% | Historical; current-contract rank withheld |
| Ollama vision | `qwen3-vl:8b` | 0/5 | 0% | 0% | Historical; current-contract rank withheld |
| Codex native vision | GPT-5.6 high | 4/5 | 100% | 100% | Unranked native pilot |
| Codex native vision | GPT-5.6 ultra | 4/5 | 100% | 100% | Unranked native pilot |

Both GPT-5.6 image pilots passed the MRI localization/segmentation, PET bladder
localization, and released negative PET cohort-label task. Both missed the CT
coarse lung-air Dice threshold. With only five tasks, the GPT interval is wide
(37.55–96.38%); this pilot tests image transport and spatial contracts, not
diagnostic performance.

## OpenKBP real-workflow pilot v0.6

The v0.6 release uses two pinned OpenKBP head-and-neck cases (`pt_242` and
`pt_289`). Each contributes five correlated tasks: bilateral-parotid grid
segmentation, high-dose-region grid segmentation, a plan-criteria audit using
published OpenKBP-Opt criteria, a structure-inventory audit, and a paired-parotid
TG-263 naming audit. The CT and expert contours are derived from OpenKBP; the
reference plan dose is OpenKBP's standardized synthetic plan. Every task requires
qualified review or escalation and is regraded from the stored candidate output.

Twenty-seven API/local configurations completed three attempts per task. Four legacy rows ran under
one memory-bounded Ollama harness (`temperature=0`, seeds
`20260731`–`20260733`, 4,096-token context, 768 output-token cap). Five ran on
Groq's OpenAI-compatible endpoint under one shared JSON-object contract with the
same temperature, seeds, and output-token cap. Eighteen ran under the digest-pinned
`reference-json-v2` Ollama contract with the same seeds, a 4,096-token context,
and 2,048-token output cap. Official ranks are computed within
each identical provider/harness/configuration group with at least two systems; the
separate descriptive outcome order spans every complete valid row.
Exact ties on the declared safe-success, task-success, and safety-gate point estimates
share a competition rank (`1, 1, 3`); names only determine the display order of tied rows.
Together with four native GPT-5.6 audits, v0.6 contains 31 rows and 930 attempts.
Eighteen submission-attested v2 rows receive an official within-group rank. Eight complete legacy
Ollama/Groq rows remain visible but unranked because their attempt manifests lack the required
adapter-settings hash; one receipt-free Groq row and the four native rows are also visible but
unranked. Public defect `MPB-2026-003` records this fail-closed correction. The immutable attempts,
scores, and descriptive outcome order are unchanged.

The compact tables retain the attempt-level Wilson interval for sensitivity and
historical continuity. The website and JSON make the two-family cluster interval
primary and display both interval definitions for every row.

| Legacy Ollama order | Model | Safe success | Attempt 95% CI | Safety | Valid output | Median tokens | Median time |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `qwen3.5:4b` | 50.0% | 33.15–66.85% | 100.0% | 100.0% | 1,238 | 5.393 s |
| 2 | `gemma3:4b` | 20.0% | 9.51–37.31% | 80.0% | 80.0% | 1,301.5 | 5.143 s |
| 3 | `qwen2.5vl:3b` | 0.0% | 0.00–11.35% | 70.0% | 100.0% | 1,396 | 2.132 s |
| 4 | `qwen3-vl:8b` | 0.0% | 0.00–11.35% | 0.0% | 0.0% | 1,311.5 | 5.250 s |

| Legacy Groq order | Model | Safe success | Attempt 95% CI | Safety | Valid output | Median tokens* | Median wall time* |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `llama-3.3-70b-versatile` | 60.0% | 42.32–75.41% | 100.0% | 60.0% | 991.5 | 1.770 s |
| 1 | `openai/gpt-oss-20b` | 60.0% | 42.32–75.41% | 100.0% | 60.0% | 1,338 | 9.283 s |
| 3 | `openai/gpt-oss-120b` | 50.0% | 33.15–66.85% | 100.0% | 60.0% | 1,371.5 | 10.268 s |
| 4 | `llama-3.1-8b-instant` | 0.0% | 0.00–11.35% | 27.78% | 60.0% | 1,002 | 8.343 s |
| — | `qwen/qwen3.6-27b` | evidence unavailable | evidence unavailable | unavailable | 0.0% | unavailable | unavailable |

| Ollama v2 rank | Model | Safe success | Attempt 95% CI | Safety | Valid output | Median tokens | Median wall time |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `qwen3.5:4b` | 50.0% | 33.15–66.85% | 100.0% | 100.0% | 1,238 | 16.964 s |
| 2 | `gemma3:12b-it-q4_K_M` | 40.0% | 24.59–57.68% | 100.0% | 100.0% | 1,242.5 | 38.745 s |
| 2 | `qwen2.5vl:7b-q4_K_M` | 40.0% | 24.59–57.68% | 100.0% | 100.0% | 1,376.5 | 24.215 s |
| 2 | `qwen3:14b` | 40.0% | 24.59–57.68% | 100.0% | 60.0% | 1,025 | 30.736 s |
| 2 | `qwen3:8b` | 40.0% | 24.59–57.68% | 100.0% | 60.0% | 1,025 | 17.580 s |
| 6 | `qwen2.5:7b-instruct` | 30.0% | 16.66–47.88% | 100.0% | 60.0% | 1,019 | 15.604 s |
| 6 | `qwen3-vl:8b-instruct` | 30.0% | 16.66–47.88% | 100.0% | 100.0% | 1,308.5 | 17.279 s |
| 8 | `gemma3:4b` | 20.0% | 9.51–37.31% | 100.0% | 100.0% | 1,301.5 | 16.253 s |
| 9 | `hf.co/ShayanCyan/phi4-multimodal-quantisized-gguf:Q4_K_M` | 10.0% | 3.46–25.62% | 100.0% | 60.0% | 937.5 | 8.436 s |
| 9 | `phi4-mini:3.8b-q4_K_M` | 10.0% | 3.46–25.62% | 100.0% | 60.0% | 938.5 | 9.632 s |
| 9 | `phi4:14b` | 10.0% | 3.46–25.62% | 100.0% | 60.0% | 969.5 | 30.142 s |
| 12 | `mistral-nemo:12b-instruct-2407-q4_K_M` | 10.0% | 3.46–25.62% | 66.67% | 60.0% | 1,053.5 | 26.964 s |
| 13 | `hf.co/EnlistedGhost/Pixtral-12B-2409-GGUF:Q4_K_M` | 10.0% | 3.46–25.62% | 60.0% | 100.0% | 1,379.5 | 41.562 s |
| 14 | `qwen3:1.7b` | 0.0% | 0.00–11.35% | 100.0% | 60.0% | 1,029 | 6.420 s |
| 15 | `qwen2.5vl:3b` | 0.0% | 0.00–11.35% | 70.0% | 100.0% | 1,396 | 13.561 s |
| 16 | `deepseek-r1:1.5b` | 0.0% | 0.00–11.35% | 50.0% | 60.0% | 1,616 | 14.805 s |
| 17 | `llama3.1:8b` | 0.0% | 0.00–11.35% | 33.33% | 60.0% | 954.5 | 17.385 s |
| 17 | `llama3.2:3b` | 0.0% | 0.00–11.35% | 33.33% | 60.0% | 950.5 | 7.708 s |

All eighteen v2 rows completed the same 30-attempt matrix with exact local artifact
digests. Seven vision-enabled configurations made 30 real calls, including all 12 required-image attempts;
the eleven text-only configurations retain those 12 tasks as explicit unsupported-modality
outcomes, not omissions, so their token/time medians cover 18 actual text calls.
Safety percentages for those text-only rows also use the 18 actual provider calls;
the 12 no-call outcomes remain zero-score capability failures but are reported as
capability unavailable rather than unsafe. The prior derived projection mixed those
denominators; public defect `MPB-2026-002` records the correction without changing
any primary safe-success score.
The older four-system Ollama and four-system Groq tables above are descriptive historical orders,
not current-contract rank groups. Their source artifacts predate adapter-settings-hash admission;
`MPB-2026-003` records the rank reclassification and the new projection-level submission-sidecar gate.
Fifteen rows completed bounded adapter audits before the full matrix. DeepSeek R1
1.5B and Mistral Nemo advanced opportunistically through complete Q2 matrices and
therefore disclose `backfilled_after_full_q2` qualification rather than claiming
that a preflight protected those runs. Every v2 row's 30 sanitized artifacts,
exact model digest, execution environment, and per-file hashes are bound by its
own `common-harness-submission.v1` sidecar. Task correctness was not a
qualification criterion and remained deterministically scored in Q2.

The three August 3 current-contract reruns preserve the immutable v1 rows while adding
digest-pinned v2 evidence for `qwen3.5:4b`
(`sha256:2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`),
`gemma3:4b`
(`sha256:a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`),
and `qwen2.5vl:3b`
(`sha256:fb90415cde1ef08aa669ae74b082d49b158729b6db1ab183c941417d507e71a1`).
They scored 50.0%, 20.0%, and 0.0% safe success, respectively. The first two
preserved 100% safety; Qwen2.5-VL 3B produced nine unsafe attempts, yielding 70%
safety despite 100% schema-valid output. These reruns deepen current-contract evidence
for already evaluated base models; they do not increase unique base-model breadth.

Earlier Qwen3-VL campaigns stopped at their declared resource guards. Their incomplete raw
evidence is not a release row or score. The distinct non-thinking
`qwen3-vl:8b-instruct` digest later completed 30/30 attempts in a new result root with a
bounded unload-recovery wait; the immutable legacy v1 and partial evidence remain unchanged.

The Pixtral row is deliberately labeled as a community-quantized system rather than an
official Mistral GGUF. The route pins the post-trained `mistralai/Pixtral-12B-2409`
lineage through immutable Hugging Face revision
`f4b659266080c08cbceb36f8a1a387ced7a989a7`; its local model and vision-projector
blobs match the published LFS SHA-256 values. This provenance expands the base-model
fleet by one without implying that every quantized build is interchangeable.

The Phi-4 Multimodal row is likewise labeled as a community quantization, but its tested
configuration is text-only: the pinned GGUF has no vision projector. Its 12 required-image
attempts are therefore explicit capability-unavailable outcomes, not vision inference or omitted
tasks. The 18 actual text calls achieved 10.0% safe success, 100% safety, 60.0% valid output,
median 937.5 total tokens, and median 8.436-second wall time.

`*` Groq token and time medians use the 18 text attempts with observed provider
telemetry. The four image tasks generate 12 completed zero-score modality failures
for the text-only Llama and GPT-OSS rows; those failures are never omitted from the
score denominator. Free-tier HTTP 429 backoff is traced and is included in observed
end-to-end wall time, so this table is not a hardware-normalized inference-speed
comparison. `qwen/qwen3.6-27b` failed the bounded provider JSON-object contract on
all 30 attempts and its stored failure artifacts have no model-response receipt,
usage, or completion-time telemetry. The configuration remains visible but is
quarantined from both official rank and descriptive outcome order. This is an
execution-evidence failure, not a claim about latent medical-physics knowledge.

Four GPT-5.6 configurations completed the same sealed ten-task runtime three
times, producing 30 deterministically regraded attempts per configuration. Three are
GPT-5.6 Sol effort settings; the fourth is GPT-5.6 Terra at high effort, collected in
three independent fresh contexts under the stricter recorded-capture v2 contract.
These are real model outputs and receive the same visible descriptive cross-surface outcome order.
They are not promoted into either official harness-group rank because the native
surface does not expose comparable API sampling, token, or latency telemetry.

| Outcome order | Native surface | Safe success | Attempt 95% CI | Safety | Valid output | All-attempt agreement | Rank status |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | GPT-5.6 Sol high | 76.67% | 59.07–88.21% | 100.0% | 100.0% | 90.0% | Native; no official harness-group rank |
| 2 | GPT-5.6 Sol ultra | 73.33% | 55.55–85.82% | 100.0% | 100.0% | 60.0% | Native; no official harness-group rank |
| 3 | GPT-5.6 Sol low | 66.67% | 48.78–80.77% | 100.0% | 100.0% | 80.0% | Native; no official harness-group rank |
| 4 | GPT-5.6 Terra high | 63.33% | 45.51–78.13% | 100.0% | 100.0% | 90.0% | Native v2 capture; no official harness-group rank |

The repeated Sol matrix resolves the earlier one-shot low/high reversal, but it still
does not establish a statistically decisive effort ordering: the Wilson intervals
overlap substantially and the release contains only two correlated patient
families. Sol high has the largest point estimate, while Sol ultra has the lowest repeated-
attempt agreement. Terra passed all 18 plan-criteria, structure-inventory, and TG-263
naming attempts plus one of six high-dose localization attempts; its six parotid-grid
attempts and the other five high-dose attempts failed the Dice threshold while preserving
the required escalation boundary. All four configurations remain subject to the same
independent-review and human-baseline gaps as the API/local rows.

`qwen3.5:4b` passed the non-image data-integrity/naming tasks and some plan/dose
work but remained weak on coarse segmentation (`0.3651` mean segmentation-lane
score). Its family-cluster interval was 40–60%. All four models were perfectly
consistent across the three attempts for each task under these deterministic
settings; that is repeatability, not evidence that seeds are independent.

The `qwen3-vl:8b` adapter responses require special interpretation. Ollama
returned empty final `content` while placing JSON-looking text in a provider
`thinking` field even though thinking was disabled. The harness does not promote
hidden reasoning into an answer, so those attempts correctly count as invalid
final outputs. This is an agent-interface failure, not proof that the model had
no latent task knowledge.

The pilot remains provisional. It has automated reference feasibility but zero
completed independent physicist reviews and no measured human baseline. The
review status and claim boundary are machine-readable in
[`reviews/public-real-workflows-pilot-v0.6.json`](../reviews/public-real-workflows-pilot-v0.6.json).

## Grader audit and anti-gaming controls

Before freezing scores, an audit found two deterministic list graders that
penalized medically equivalent explicit terms (`attending_physician` versus
`attending_radiation_oncologist`, for example). The grader now supports only
task-declared alias mappings—never fuzzy matching—and all stored outputs were
regraded. This improved fairness without changing any model-visible runtime
packet or safety expectation.

The release additionally enforces:

- sealed runtime projections with no grading or provenance block;
- exact JSON objects with duplicate-key, wrapper-text, and non-finite rejection;

One frozen v0.6 limitation is now explicit: every task requires a non-empty
`limitations` field, but its task-specific meaning is not deterministically graded.
The released task and grader hashes are immutable and were not rewritten. Repository
validation now blocks v0.7+ tasks from requiring that field without a score-bearing
limitations grader, and the next comparison release will add authored near-miss cases.
- exact task-ID matrices and sealed-batch hashes for imported pilots;
- artifact-root confinement and mandatory SHA-256 image verification;
- reconstructed reference outputs that must pass every authored grader;
- deterministic regrading of published outputs before rank eligibility;
- explicit exclusion of native-surface pilots from common-harness ranks.

## Interpretation boundary

The core tasks are public and contamination-prone. The image pilot is tiny, and
its single released negative PET label cannot estimate sensitivity, specificity,
subgroup performance, or clinical utility. None of these results authorize
diagnosis, treatment release, machine return to service, or autonomous clinical
action. Strong claims require a sealed multi-institution holdout, independent
medical-physics review, repeated trials, and blinded adjudication.
