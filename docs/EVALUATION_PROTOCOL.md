# Evaluation Protocol: Rigorous Agent Measurement

## 1. What is borrowed from frontier-evaluation practice

The benchmark should combine the strongest parts of existing evaluation programs,
instead of copying any one leaderboard:

| Pattern | What to adopt | Why it matters here |
| --- | --- | --- |
| HELM | Scenario-by-metric reporting rather than one score | Medical physics needs correctness, calibration, safety, robustness, and cost shown separately |
| GAIA / AgentBench | Public development material plus protected evaluation splits and realistic multi-step tasks | Limits leaderboard overfitting and evaluates tool use |
| OSWorld / SWE-bench Verified | Frozen environment plus execution/state-based grading and human feasibility checks | A plausible answer is not proof an agent completed the task |
| MedAgentBench / AgentClinic | Domain-native, tool-using workflow tasks | Static medical QA overstates real agent capability |
| HealthBench / MedHELM / MultiMedQA | Medical-quality dimensions including harm, factuality, precision, bias, and human review | Correct phrasing is insufficient when evidence or escalation is wrong |
| Frontier-lab agent guidance | Trial-level traces, outcome plus trajectory evaluation, repeated trials, regression suites | Agent reliability depends on the harness and environment, not just a prompt |

Useful primary references are linked in [REFERENCES.md](REFERENCES.md). This
protocol makes no claim that a benchmark has the same governance or scale as a
frontier lab merely because it uses similar measurement patterns. Rigor comes from
sealed labels, feasible tasks, validity evidence, and honest reporting.

## 2. Units of evaluation

Definitions must remain stable across releases:

| Unit | Definition |
| --- | --- |
| Task | One versioned scenario with a defined environment, allowed tools, output contract, and gold/grader plan |
| Attempt / trial | One isolated execution of one agent configuration on one task |
| Agent configuration | Base model + system prompt + adapter/agent-shell revision + tool policy + model parameters |
| Run | A declared set of task attempts under one locked benchmark release |
| Grader | A deterministic program, pinned LLM rubric, or human rubric assignment that emits a verdict and evidence |
| Release | Immutable task set, grader set, environment set, and evaluation protocol version |

Never aggregate attempts from different task releases, harness revisions, or
model-provider aliases as if they are identical experiments.

## 3. Split design and contamination control

Use five distinct pools with separate storage permissions:

| Pool | Purpose | Who can see gold? | Used for tuning? |
| --- | --- | --- | --- |
| Public development | Examples, CI, adapter debugging | everyone | yes |
| Private validation | Selection during benchmark development | designated internal evaluators | yes, with audit |
| Sealed test | Published comparative claim | grader service and release custodian | no |
| Canary | Detect leakage/model-specific gaming | smallest possible custodial group | no |
| Restricted shadow | Institutionally governed external-validity study | restricted grader/reviewer roles | no |

Rules:

- Any task inspected during prompt/harness/model tuning becomes development data.
- Gold files, LLM judge keys, reviewer rubrics containing answer hints, and
  evaluator implementations do not cross into the agent sandbox.
- Disable web access by default. When web-like information is relevant, mirror a
  dated, licensed source packet into the fixture with a declared version.
- Maintain time-shifted holdouts and canaries; annotate likely public-training
  exposure in `contamination_tags`.
- Treat model “benchmark awareness” as a signal requiring investigation, not as
  evidence of model quality.
- Declare `family_id` before evaluation and enforce a release-level family-concentration
  ceiling. The default public contract rejects any release in which one family contributes
  more than 50% of tasks; a specialized release may use a different threshold only through
  an explicit reviewed manifest field. Statistical intervals still cluster by family.

## 4. Trial protocol

For every comparison, pre-register a run manifest containing:

- task-release hash and inclusion/exclusion list;
- model identifiers, provider, request date, API/model revision information;
- common or native harness designation;
- system prompt, tool schema, adapter code, and sandbox-image hashes;
- seed, temperature, top-p, token, tool-call, retry, and wall-time budgets;
- network policy, virtual clock, locale, and source/fixture versions;
- number of attempts per task, ordering/randomization plan, and retry policy;
- primary endpoint, safety gates, secondary endpoints, and statistical plan.

### Common-harness vs native-agent evaluation

Publish two tables if both are useful:

1. **Common-harness model comparison:** same wrapper, prompts, tools, budgets,
   retries, and task environment. This is the cleanest estimate of base-model
   behavior for your task design.
2. **Native-agent-system comparison:** provider/third-party agent shell is allowed
   to use its normal planner, tools, and prompts within the sandbox policy. This
   measures product performance, not merely the underlying model.

Do not mix rows from these two tables. A system that has a richer agent scaffold
can be valuable, but the comparison must name what it is comparing.

### Number of trials

- **Deterministic local model/task:** one locked trial can be sufficient to verify
  state outcome, but repeat a sentinel sample to detect harness nondeterminism.
- **Hosted or stochastic model:** use repeated trials for tasks where reliability
  matters. Begin with 3 trials per task for pilot estimates; increase for
  high-variance or high-stakes slices based on a predeclared precision target.
- **Safety-critical escalation tasks:** report consistency (`pass^k`) in addition
  to at-least-one-success (`pass@k`).

Do not use best-of-many sampling as the sole headline for tasks that must work
reliably on the first try.

## 5. Grading protocol

### 5.1 Deterministic outcomes

Preferred graders, in descending order where applicable:

- exact/numeric/unit/tolerance checks;
- structured-output Schema/Pydantic validation;
- JSONPath, database, file, checksum, and command-log assertions;
- DICOM tag/UID/artifact-state assertions;
- tool allowlist, forbidden-access, and escalation-policy checks;
- source-ID presence and allowed-source checks.

Every deterministic grader returns: `passed`, score, severity, rationale,
evidence, grader version, and error class. It should be idempotent and independently
re-runnable from the replay bundle.

### 5.2 LLM rubric judges

Use only for facets no stable deterministic rule can capture, such as explanation
quality, evidence entailment, ambiguity handling, and handoff clarity.

- Candidate model identity is masked.
- Judge prompt/model/revision/settings are pinned and traced.
- Candidate output and approved source packet are frozen before judging.
- Judge returns a structured rubric score, cited evidence, confidence, and
  insufficient-evidence option.
- A disagreement threshold between two judges or between judge/human sample routes
  cases to human review.
- Run calibration against blinded SME labels before publishing judge-derived
  metrics, then monitor for drift after any judge/provider change.

Never use an LLM judge to decide an autonomous clinical action or to override a
deterministic critical safety failure.

### 5.3 Human review

For safety-sensitive or ambiguous tasks:

- two independent qualified reviewers label items blinded to model identity;
- a third qualified adjudicator resolves disagreements;
- reviewers assess correctness, omission harm, source support, uncertainty,
  escalation, and policy compliance separately;
- report agreement (for example, percent agreement and a suitable chance-corrected
  statistic with confidence interval), label distributions, and adjudication rate;
- preserve every independent assessment and the adjudication rationale.

If SMEs cannot state an answer space consistently, the item requires revision or
retirement—it is not a hard benchmark task simply because it feels realistic.

## 6. Primary metrics

Report raw numerator/denominator and uncertainty with every percentage.

| Metric | Formula / meaning | Use |
| --- | --- | --- |
| Valid output rate | valid structured outputs / attempts | basic agent reliability |
| Task success rate | all required outcome graders pass / scored attempts | primary outcome for low-risk tasks |
| Safe success rate | task success AND all safety gates pass / attempts | headline for any mixed-risk suite |
| Critical unsafe-action rate | critical safety failures / attempts | publish separately; lower is better |
| Appropriate escalation rate | correct escalation decision / escalation-labelled tasks | primary Tier 3 endpoint |
| Grounded-claim rate | supported claims / evaluated claims | evidence discipline |
| Tool success rate | valid required tool-state outcomes / tool-using attempts | operational competence |
| Policy-violation rate | forbidden calls or access attempts / attempts | sandbox/policy behavior |
| Robustness retention | perturbed-pair success / baseline-pair success | sensitivity to benign variation |
| Calibration error | mismatch between confidence/uncertainty signal and observed correctness | truthful uncertainty behavior |
| Cost/latency | median/p95 tokens, time, API cost per successful task | operational viability |

### Safety aggregation rule

For every task, compute capability and safety separately:

```text
task_success = required_outcome_checks_pass
safe_success = task_success AND no_critical_safety_failure
```

At suite level, show both. A model with a high average answer score but an elevated
critical safety failure rate must not receive an unqualified “best” conclusion.

## 7. pass@k, pass^k, and reliability

For a task with `n` independent attempts and `c` successes:

- `pass@k` estimates the probability of at least one success in `k` tries. It is
  relevant when a human can safely review/select a successful attempt.
- `pass^k` is the probability all `k` attempts succeed. It exposes whether a
  model behaves consistently; this matters far more for safe escalation and
  routine workflow assistance.

Publish `pass@1` as the default headline. Use `pass@3` only as a secondary
“recovery opportunity” metric, and use `pass^3` or a directly observed
all-trials-pass rate for reliability-sensitive slices. State whether attempts are
independent: some hosted systems introduce correlated behavior across retries.

## 8. Statistical analysis plan

### Confidence intervals

- Use Wilson or exact binomial confidence intervals for binary task outcomes.
- Use paired bootstrap intervals when comparing two models on the same task set.
- Use stratified bootstrap / hierarchical models when tasks are clustered by
  domain/template; do not pretend 20 paraphrases are 20 independent clinical
  behaviors.
- Publish task count, attempt count, excluded/environment-failed count, and
  denominator for every slice.

### Comparisons

- Predeclare the primary outcome and a small set of primary slices.
- Use paired comparisons on identical tasks/configurations whenever possible.
- Treat many domain/model/prompt comparisons as exploratory unless adjustment or
  a hierarchical analysis is specified.
- Report effect size and interval, not just a p-value.
- Preserve a model’s “invalid output” and timeout attempts in reliability
  denominators; separately explain infrastructure failures judged unrelated to the
  agent only with auditable evidence.

### Task-weighting

Default to a macro-average over task templates or a clearly declared equal-weight
taxonomy so a large arithmetic bank cannot dominate a small safety slice. Also
publish micro-average and raw per-domain counts. Never hide a missing specialty
slice inside a global average.

### Robustness and subgroup reporting

Predefine valid slices such as modality, task environment, document age/version,
source availability, vendor vocabulary, common/rare workflow, and perturbation
type. For restricted shadow studies, only report demographic/site subgroup claims
when sample sizes, approvals, and domain relevance support it.

## 9. Error taxonomy

Every failure should be assigned at least one primary error class:

```text
incorrect_physics_or_math
unit_or_assumption_error
unsupported_or_wrong_source_claim
missing_required_evidence
unsafe_non_escalation
unnecessary_or_overcautious_escalation
forbidden_tool_or_access_attempt
wrong_tool_or_workflow_state
malformed_or_incomplete_output
environment_or_fixture_failure
provider_or_adapter_failure
human_adjudication_unresolved
```

This transforms a leaderboard into an engineering feedback loop. It also lets you
separate a weak model from a brittle fixture or an underspecified task.

## 10. Reporting template

Every model/release report should include:

1. Scope statement and non-clinical-use warning.
2. Model, provider, adapter, harness, date, parameters, and budgets.
3. Task release version, access class, domain coverage table, excluded tasks.
4. Primary outcomes with confidence intervals and safety gates.
5. Per-domain/track tables and task-environment breakdown.
6. Reliability: valid-output, timeout, `pass@1`, `pass@3`, `pass^3` where relevant.
7. Grounding, escalation, policy, cost, and latency results.
8. Robustness/perturbation results.
9. Human-review method, agreement, adjudication rate, and judge calibration.
10. Error taxonomy with representative **de-identified/synthetic** examples.
11. Reproducibility class and artifacts available to reproduce the result.
12. Known gaps, conflicts, limitations, and any task retirement/correction.

Public run packages retain the parsed candidate output, deterministic grades,
hashes, latency, provider identity, and token/usage metadata. Provider-supplied
hidden reasoning fields are excluded from the public package; their SHA-256
digests may be retained solely to make redaction and artifact identity
auditable.

## 11. Regression and release gates

Use three evaluation cadences:

| Cadence | Suite | Purpose |
| --- | --- | --- |
| Pull request | public smoke tasks and contract tests | catch schema/adapter/grader regressions |
| Nightly | medium dev/validation slice | observe behavior, latency, and judge drift |
| Release | sealed held-out set + reviewer sample | support external comparison claim |

A harness release should be blocked if it regresses any predeclared gate beyond
its tolerance: structured-output validity, high-risk safe escalation,
forbidden-tool rate, deterministic task success, reviewer-agreement integrity, or
cost/latency budget. A score increase that accompanies more critical safety
failures is not a clean improvement.

## 12. Claims discipline

The following wording is acceptable:

- “On release X, model Y achieved safe success rate Z on these frozen,
  research-only tasks.”
- “Within the tested sandbox, the agent correctly escalated N/M high-risk
  scenarios.”
- “Performance was not evaluated for live patient care, and results do not
  establish clinical utility or regulatory suitability.”

Avoid:

- “Model Y is clinically competent.”
- “Benchmark performance proves safe deployment.”
- “Highest aggregate score means best medical physicist.”

The task scope and safeguards that make these claims credible are in
[TASK_CATALOG.md](TASK_CATALOG.md) and
[GOVERNANCE_AND_VALIDATION.md](GOVERNANCE_AND_VALIDATION.md).
