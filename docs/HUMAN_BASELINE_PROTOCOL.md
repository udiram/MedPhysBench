# Human Baseline and Domain-Review Protocol

**Status:** preregistration draft; recruiting; no human score is currently published

Ground truth and human performance are different evidence. MedPhysBench currently
has deterministic reference solutions derived from frozen fixtures and published
research criteria. Those prove feasibility; they do not establish how practicing
physicists perform, whether items are unambiguous in practice, or whether model
scores are meaningfully hard.

## Questions

1. Can qualified humans solve each task from the same runtime-visible evidence?
2. How much time and tool interaction does the task require?
3. Which task families are ambiguous or have low inter-reviewer agreement?
4. How do model error types compare with human error types under matched conditions?

The study is not designed to certify people, predict board performance, or
validate clinical use.

## Participants

Target pilot enrollment is 30 participants:

- at least 15 board-certified or locally equivalent radiation-therapy medical
  physicists;
- up to 10 accredited medical-physics residents for a training-stage stratum;
- up to 5 certified medical dosimetrists for planning-specific secondary analyses.

The primary human reference for physics-wide claims uses qualified physicists
only. Residents and dosimetrists are reported in separate prespecified strata;
they are not pooled simply to increase `n`. Expertise, years in role, modality
experience, and prior OpenKBP exposure are collected as coarse non-identifying
covariates.

Before recruitment, the study owner documents whether institutional review or an
exemption/not-human-subjects determination is required. No patient data, clinical
credentials, personnel evaluation, or employment decision enters the study.

## Review phases

### Phase A — item validation

Two independent qualified physicists solve every professional/expert or risk-3
task from the sealed runtime view. They separately rate relevance, solvability,
ambiguity, evidence sufficiency, output contract, and safety boundary. A third
qualified reviewer adjudicates disagreements. Items are revised or retired when
reviewers cannot converge; disagreement is not converted into artificial task
difficulty.

### Phase B — timed baseline

Participants receive the identical prompt, artifacts, allowed tools, and output
schema used by the common model harness. They are blinded to model names, model
outputs, gold labels, grader code, and other human responses. The interface
records final structured output, elapsed active time, allowed tool actions,
confidence, and an optional ambiguity flag.

Two conditions are reported separately:

1. **Closed fixture:** only supplied artifacts and calculator/code tools declared
   by the task.
2. **Source-assisted:** the exact versioned source packet declared by the task.

Open-web searching is not mixed into either condition. Breaks and inactive time
are excluded by a declared pause policy rather than silently trimmed after data
collection.

## Assignment and leakage control

- Tasks are sampled in balanced blocks by family, track, difficulty, and risk.
- A participant receives at most one answer-equivalent variant from a task
  family, preventing memory transfer across cosmetic perturbations.
- For patient-linked tasks, analyses cluster by patient `family_id`; five views
  of one OpenKBP case remain one patient family.
- Order is randomized with a recorded seed. Participants cannot revisit prior
  blocks after gold-dependent feedback; no correctness feedback is shown during
  collection.
- The public development set is suitable for workflow validation, not a blinded
  estimate of expert performance. A meaningful human-model comparison requires
  a separately governed validation/test set.

## Endpoints

Primary endpoints:

- safe task success rate;
- critical unsafe-action rate;
- appropriate escalation rate for escalation-labelled tasks.

Secondary endpoints:

- valid structured-output rate;
- median and interquartile active time per successful task;
- confidence calibration;
- false-positive and false-negative defect flags;
- family/track-specific performance;
- error taxonomy and ambiguity rate.

For domain review, report raw agreement, an appropriate chance-corrected
agreement statistic with uncertainty, and adjudication rate. For performance,
report participant- and family-cluster bootstrap intervals. Do not treat task
views, repeated trials, or participants' correlated answers as independent
Bernoulli observations.

## Human-model comparison

Model and human denominators must use the same frozen task release. Comparisons
are paired by task family where possible and show effect sizes with intervals.
Time comparisons label the surface: human active time is not equated to API wall
time, and human reading time is not equated to model token use. Tokens, latency,
cost, and human minutes are displayed as different axes.

No “human parity” statement is allowed when:

- the human baseline uses public development items seen during benchmark design;
- fewer than two independent patient families support a slice;
- domain review or rights review is incomplete;
- model/human tools or evidence differ;
- confidence intervals are too wide for the claimed difference;
- model selection or prompt tuning used the evaluated labels.

## Evidence package

The publishable, de-identified baseline package contains:

```text
human-study-manifest.json
participant-strata.json             # aggregate counts only
assignment-manifest.json            # task/family blocks and randomization seed
responses/<pseudonymous-id>/*.json  # structured output, timestamps, confidence
independent-reviews/*.json
adjudications/*.json
analysis-plan.md
analysis-code/
baseline-summary.json
```

Every correction creates a new immutable analysis artifact. Raw identity or
consent records are stored outside the benchmark repository.

## Current status

The machine-readable ledger at
[`reviews/public-real-workflows-pilot-v0.6.json`](../reviews/public-real-workflows-pilot-v0.6.json)
records zero completed independent domain reviews and zero human baseline
participants. Until that changes, the site reports “Recruiting” and must not
substitute model-authored reference outputs, benchmark author performance, or
LLM adjudication for human results.
