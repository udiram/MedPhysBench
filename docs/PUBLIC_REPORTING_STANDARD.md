# Public reporting standard

Status: active, 2026-08-01

This document defines how MedPhysBench presents model results in the website, release writeups, plots, tables, and machine-readable artifacts. Its purpose is to make misinterpretation difficult.

## Reading order

Every public release report should answer these questions in order:

1. **What can this release support?** Show maturity, task count, independent family count, attempts per task, review state, human-baseline state, rights state, and holdout state.
2. **Which rows are comparable?** Partition exact provider/adapter/harness/revision groups from native or observational runs before displaying rank.
3. **How uncertain is the result?** Show the primary point estimate with its declared interval and the independence unit.
4. **Where does performance fail?** Show task-family capability and mutually exclusive outcome partitions, not only an overall number.
5. **What did performance cost?** Show duration, input/output tokens, and frozen-price cost only when measurement coverage and semantics are comparable.
6. **Can the result be audited?** Link the release contract, system description, attempt matrix, hashes, artifacts, defect history, and changelog.

## Release header

The header must include:

- release identifier and artifact date;
- maturity label: `public-development`, `public-pilot`, `domain-reviewed`, `human-baselined`, `protected-comparison`, or `externally-replicated`;
- task count and independent family count as separate values;
- expected attempts per task;
- official comparison rows and observational/native rows;
- one allowed-claim sentence and one prohibited-claim sentence.

Missing evidence is shown as `not declared`, `not collected`, or `pending`; never as zero or an empty success state.

## Ranking and comparison

- Official ranks exist only inside identical frozen comparison groups containing at least two systems.
- A comparison group freezes provider, adapter, harness revision, exact model revision, adapter-settings
  hash, sampling/token contract, and attempt-index seed policy. A singleton remains visible in descriptive
  outcome order but cannot manufacture a rank of one.
- A provider alias is not an identity. Persist provider, exact model revision, date, adapter, harness revision, effort/sampling settings, and system description.
- Native-system results may receive a descriptive outcome order only when the attempt matrix is complete and internally consistent.
- Never display native and common-harness rows as one official ordinal leaderboard.
- Default the public page to the release with the strongest broadly interpretable evidence, not the newest or highest-scoring lane.
- A perfect score on a public development set is a saturation signal, not proof of clinical or autonomous competence.

## Fleet breadth and qualification

- Count unique frozen base model IDs, not effort settings, quantizations, provider routes, aliases, or agent scaffolds.
- Report the qualification funnel as separate planned, access-qualified, evaluated, and rankable counts.
- A planned or live-access model never appears as evaluated until a complete immutable attempt matrix is published
  under the current manifest/scoring contract. Historical rows with missing hashes remain visible but do not inflate
  current-contract evaluated or rankable counts.
- A complete native/import row is presented in the same model explorer as common-harness rows, with execution surface as metadata; it may be outcome-orderable without receiving a false common-harness rank.
- Every public system configuration maps to one explicit `base_model_id`. Multiple configurations remain separately auditable but increment the base-model breadth count only once.

## Score and uncertainty

- The primary metric is safe task success: outcome success with all critical safety gates satisfied.
- Show the numerator/denominator or attempts beside the percentage.
- Use Wilson intervals for binomial attempt-level summaries.
- When tasks share a patient, case, machine, or source packet, also show a family-cluster interval or explicitly state that the task-level interval is descriptive.
- Do not rank by interval endpoints, suppress uncertainty, or imply a meaningful difference from point estimates alone.
- For repeated trials, publish `pass@1`, `pass@k`, `pass^k`, all-attempt agreement, and within-task variance where defined.
- Human comparison requires its own sampling design and uncertainty; it cannot be inferred from reference-solution feasibility.

## Capability and failure reporting

The primary statistical drill-down unit is a declared task family, not a raw attempt. A display may also group task types into descriptive capability areas, but it must label those separately and must not imply that capability areas are independent patients, cases, or families. Each cell should show safe success and the number of attempts. Raw attempts remain available in provenance views.

The website may partition attempts into the following mutually exclusive categories:

1. safe success;
2. safe task failure;
3. unsafe outcome.

Output validity, escalation correctness, integrity failures, and telemetry coverage can overlap those outcomes and therefore must be shown as separate diagnostic rates rather than stacked into the same 100% bar.

No chart should imply that correlated task views are independent patients.

## Efficiency reporting

- Tokens are provider-reported and tokenizer-specific. Compare them only inside a declared measurement context.
- Duration must name the measurement kind: model latency, harness wall time, or end-to-end elapsed time.
- Missing telemetry is excluded and labeled; it is never imputed as zero.
- Pareto frontiers are drawn only within valid comparison groups.
- Cost requires a frozen `pricing_snapshot_id`, source URL, currency, effective date, and route/model mapping.
- Report per-attempt cost and cost per safe success only when token/price coverage is complete.
- Hardware and local inference results include device, precision/quantization, serving stack, concurrency, and power method when energy is reported.

## Visual rules

- Prefer directly labeled dot-and-whisker plots for scores and intervals.
- Prefer heatmap tables for repeated model-by-family comparisons.
- Prefer horizontal bars for mutually exclusive outcome composition.
- Use logarithmic axes for token/time ranges spanning orders of magnitude and label them explicitly.
- Do not use pie or donut charts, dual axes, truncated score axes, 3-D marks, or decorative gradients.
- Use a monotone funnel only for actual qualification gates; keep the common denominator visible so attrition cannot be mistaken for performance.
- Never encode an official/native distinction by color alone. Use labels, grouping, and marker shape or table sections.
- Every chart has a semantic table or list fallback on small screens.
- Interactive controls have visible focus, pressed/selected state, accessible names, and a useful loading/empty/error state.
- The first viewport should communicate release maturity and claim limits before any leaderboard number.

## Provenance and change control

Every public result must link or resolve to:

- release manifest and release hash;
- task, prompt, tool, runtime-task, grader, and scoring revisions;
- exact model/system description;
- expected and observed attempt matrix;
- deterministic regrade state and integrity findings;
- telemetry availability and measurement semantics;
- review evidence and evidence-maturity level;
- result bundle, changelog, and defect/invalidation record.

The tested-system disclosure also reports the allowed budget: turns, tool calls, input/output tokens,
attempts and retries, wall-clock limit, and cost when observed. A result must not be described as a
model-only comparison when differences in scaffolding, tool access, retry policy, or context management
could explain the difference. This follows the claim/system/budget/elicitation/validity separation in
the [trustworthy third-party evaluation playbook](https://openai.com/index/trustworthy-third-party-evaluations-foundations/).

Confirmed defects never disappear silently. The public ledger records `reported`, `confirmed`, `fixed`, `withdrawn`, or `regraded`, the affected release/result identifiers, the reason, and the replacement artifact when one exists.

## Claim boundary

The following language is prohibited unless a future, separately governed validation program establishes it:

- clinically validated;
- safe for patient-specific use;
- autonomous medical physicist;
- release-to-treat capable;
- human-level or superhuman medical-physics performance;
- best model overall when rows do not share a comparison group.

Public results are evidence about bounded research tasks under declared contracts. They are not clinical authorization.
