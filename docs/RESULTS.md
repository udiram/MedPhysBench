# MedPhysBench v0.4 results

## What was evaluated

On July 31, 2026, MedPhysBench froze two public development releases:

- `public-core-v0.4`: 64 original medical-physics calculation, interpretation,
  audit, and escalation tasks across 11 reported domain labels.
- `public-imaging-pilot-v0.4`: five attributed retrospective MRI, CT, and PET
  localization, coarse-segmentation, and source-label tasks.

The primary metric is safe task success: an attempt must pass every outcome
grader and avoid every critical safety failure. Wilson 95% intervals describe
binary attempt uncertainty. They do not correct for public-set contamination or
task-family dependence.

## Core common-harness leaderboard

These models completed the same 64 tasks through the Ollama adapter with
temperature 0, seed 20260731, and a 2,048-token output limit. They are the only
ranked v0.4 core rows.

| Rank | Model | Safe success | 95% CI | Safety gate | Valid output |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | `qwen3:14b` | 73.44% | 61.52–82.70% | 98.44% | 100.00% |
| 2 | `qwen3:8b` | 57.81% | 45.61–69.13% | 98.44% | 100.00% |
| 3 | `qwen2.5:7b-instruct` | 50.00% | 38.10–61.90% | 96.88% | 100.00% |

The 14B baseline missed 17 tasks in total, including one safety boundary. Its
errors span decay and attenuation arithmetic, uncertainty/statistics, DICOM
sets and size calculations, quantitative nuclear medicine, radiobiology, and
the plan-release boundary. The result is materially more informative than the
earlier 16-task release because no single item moves the score by more than
1.56 percentage points.

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
