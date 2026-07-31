# MedPhysBench v0.5 results and v0.4 scored snapshot

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

The primary metric is safe task success: an attempt must pass every outcome
grader and avoid every critical safety failure. Wilson 95% intervals describe
binary attempt uncertainty. They do not correct for public-set contamination or
task-family dependence.

## Core common-harness leaderboard

These models completed the same 64 tasks through the Ollama adapter with
temperature 0 and seed 20260731. They are the only ranked v0.4 core rows.

| Rank | Model | Safe success | 95% CI | Safety gate | Valid output |
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
common harness duration, not provider-side compute time. The website plots score
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

| Native surface | Safe success | 95% CI | Safety gate | Escalation accuracy | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| GPT-5.6 high | 27.78% | 12.50–50.87% | 100% | 100% | Unranked native pilot |
| GPT-5.6 ultra | 22.22% | 9.00–45.21% | 100% | 100% | Unranked native pilot |

The result demonstrates why a perfect score on one small public set is not a
general capability claim. The harder lane distinguishes strict schema-compliant
answers and safe abstention from exact structure-naming competence. High and ultra
both preserved every required escalation boundary, but neither achieved a high
outcome score. The rows remain unranked because they were collected on a native
conversation surface without comparable latency, token, or sampling telemetry.

## Real-image pilot

The public image pilot uses a CC BY-SA 4.0 MSD hippocampus MRI, a CC BY 3.0
LIDC-IDRI chest CT, and a CC BY-NC 4.0 AutoPET-subset ENHANCE.PET MIP. Gold masks,
boxes, and the released PET source label remain outside the model-visible runtime.

| Surface | Model / effort | Safe success | Safety gate | Valid output | Status |
| --- | --- | ---: | ---: | ---: | --- |
| Ollama vision | `gemma3:4b` | 0/5 | 100% | 80% | Ranked common harness |
| Ollama vision | `qwen2.5vl:3b` | 0/5 | 100% | 100% | Ranked common harness |
| Ollama vision | `qwen3-vl:8b` | 0/5 | 0% | 0% | Ranked common harness |
| Codex native vision | GPT-5.6 high | 4/5 | 100% | 100% | Unranked native pilot |
| Codex native vision | GPT-5.6 ultra | 4/5 | 100% | 100% | Unranked native pilot |

Both GPT-5.6 image pilots passed the MRI localization/segmentation, PET bladder
localization, and released negative PET cohort-label task. Both missed the CT
coarse lung-air Dice threshold. With only five tasks, the GPT interval is wide
(37.55–96.38%); this pilot tests image transport and spatial contracts, not
diagnostic performance.

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
