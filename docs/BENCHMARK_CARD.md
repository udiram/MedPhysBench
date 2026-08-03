# MedPhysBench Benchmark Card

## Intended use

MedPhysBench is a research benchmark for evaluating bounded medical-physics assistance behavior
under explicit task, tool, and policy constraints. It is intended for:

- model and adapter comparison under a common harness;
- benchmark and task-design iteration;
- offline procurement-style review of structured reasoning behavior;
- research on abstention, escalation, and artifact validity.

It is **not** intended for:

- patient-specific clinical decision-making;
- autonomous plan approval, treatment release, or scanner control;
- medical-device validation or regulatory claims;
- claims of general medical-physics competence from public-development results alone.

## Unit of evaluation

Each scored attempt is a versioned task contract executed through a sealed runtime task view. A
run is judged on:

- outcome correctness;
- structured artifact validity;
- safety and escalation behavior;
- reproducibility metadata sufficient to audit the attempt.

## Ranking rule

The public leaderboard ranks only model runs that are both:

1. complete for the declared release and expected attempts; and
2. composed of completed attempts with no unresolved transport/provider-service errors; and
3. internally consistent across model, harness, run configuration, task versions, and hashes.

Eligible runs are ranked only within an identical provider, harness, and harness-revision group.
Exact ties on the declared safe-success, task-success, and safety-gate point estimates share
a competition rank (`1, 1, 3`); names are a display-order key, not a performance tie-breaker.
Incomplete or inconsistent runs remain publishable artifacts but are omitted from ranking.
Stored pass/safety labels are not trusted: the release summarizer reconstructs grades from each
recorded output and rejects any disagreement.

Unsupported required modalities and provider structured-output generation failures are completed
zero-score attempts. They are model/interface outcomes, not missing attempts, and cannot disappear
from the denominator.

## Data and task scope

The public suite combines synthetic/source-grounded development tasks with separately reported
real-data pilots. The OpenKBP v0.6 pilot has ten tasks but only two patient families and pending
independent domain and publication-rights review. It is suitable for harness qualification and a
provisional baseline comparison, but it is contamination-prone and too small for generalization,
human-parity, or clinical-performance claims.

Complete native recorded-output audits receive a clearly labeled descriptive outcome order. They
are excluded from official harness-group ranks when their harness or telemetry differs from the
declared API/local release surface.

## Safety positioning

Safety is a gate, not a styling preference or side metric. Critical escalation failures are kept
visible and cannot be averaged away by success on other graders.

## Known limitations

- The public release is small relative to the breadth of medical physics.
- Most current tasks are deterministic JSON-output tasks rather than full artifact or interactive tool-state tasks.
- The public suite is open and therefore unsuitable as the sole basis for headline capability claims.
- Published access coverage is constrained by the models actually reachable at evaluation time.
- No measured human baseline is currently published; deterministic reference feasibility is not
  a substitute for human performance evidence.

## Required reporting practice

Any public score report should include:

- the release identifier;
- the task count and expected attempts per task;
- the primary metric definition;
- the fact that this is a research benchmark, not clinical validation;
- whether any checked models were blocked, rate-limited, or retired;
- links to the underlying release artifact package.
