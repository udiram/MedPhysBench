# Benchmark Hardening: Freshness, Difficulty, and Statistical Validity

**Status:** methodology proposal for a research-only benchmark
**Source review date:** 2026-07-31

MedPhysBench should remain useful after public tasks, model outputs, prompts, and
leaderboard strategies become visible. This document defines the operational
controls required to make a comparative claim. It complements
[EVALUATION_PROTOCOL.md](EVALUATION_PROTOCOL.md): that document defines how a
frozen run is measured; this document defines how the item bank stays difficult,
fresh, and interpretable across releases.

The benchmark measures performance in declared, sandboxed tasks. It does not
measure authorization to practice medical physics and does not validate a model
for diagnosis, treatment planning, treatment approval, machine release, or any
other live clinical action.

## 1. Methods adopted from current benchmark practice

The controls below are adaptations, not claims of equivalence to the source
benchmarks.

| Source pattern | MedPhysBench adaptation | Limitation to preserve |
| --- | --- | --- |
| [LiveBench](https://livebench.ai/) adds recent, objectively gradable questions on a continuing cadence | Add newly authored task families from dated public sources and synthetic workflow changes; retire and publish old private items after their scoring life ends | Recent source material reduces exposure probability but does not prove absence from model training |
| [LiveCodeBench](https://github.com/LiveCodeBench/LiveCodeBench) versions continuously collected problems by date | Record source publication date, authoring date, first-evaluation date, and release window for every family | A dated item can still leak after first use |
| [SWE-bench Verified](https://openai.com/index/introducing-swe-bench-verified/) uses professional human review to remove infeasible or underspecified tasks | Require independent feasibility execution, gold-review, and environment validation before a private item can score a model | Human verification improves item validity; it does not make the set contamination-free |
| [HELM](https://crfm.stanford.edu/helm/latest/) reports scenarios across multiple metrics and makes missing coverage visible | Publish capability, safety, robustness, calibration, efficiency, and coverage separately; never hide a missing workflow behind one mean | A broad metric panel is not evidence of clinical validity |
| [Humanity's Last Exam](https://arxiv.org/abs/2501.14249) combines frontier-difficulty items with calibration measurement and a private component | Retain a difficult private tail, report calibration, and audit disputed expert items rather than calling ambiguity “difficulty” | Closed-ended expert knowledge is only one layer of an agent benchmark |
| [ARC-AGI-2](https://github.com/arcprize/ARC-AGI-2) separates public, semi-private, and private sets and calibrates their difficulty | Maintain public development, remotely scored semi-private, and custodian-only private pools linked by common anchor families | Comparable aggregate difficulty does not imply identical competency coverage |
| [tau-bench](https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html) grades final environment state and reports `pass^k` | Grade tool-using tasks from artifact/database state and report consistency over repeated trials | A simulated user and mock system remain approximations of work practice |

These sources support a combined design principle: use fresh and protected
items, objective outcome graders, repeated trials, human feasibility checks, and
multi-metric reporting. No single mechanism is a contamination detector or a
substitute for domain validation.

## 2. The task family is the independence unit

A **task family** is the underlying competency and causal template shared by all
surface variants. For example, changing names, units, file ordering, or a single
constraint does not create independent tasks if the same solution skeleton and
gold logic are reused.

All of the following stay in the same split and statistical cluster:

- the canonical item and its paraphrases;
- benign perturbations and adversarial variants;
- paired counterfactuals;
- translations or vendor/site vocabulary aliases;
- regenerated numeric instances from the same template;
- tasks sharing a distinctive source packet, reference calculation, or hidden
  failure injection.

This prevents a public variant from teaching the answer to its nominally private
sibling and prevents dozens of correlated variants from creating false precision.
The release manifest must include a non-secret `family_id`; the private family
membership and generation seed remain in the protected authoring registry.

## 3. Difficulty tiers

Difficulty is assigned from observed behavior after pilot calibration, not from
author intuition alone. Clinical risk is recorded separately: a simple task can
be safety-critical, and a hard task can be low risk.

| Tier | Operational definition | Typical RT example | Required grading |
| --- | --- | --- | --- |
| D0 — contract/kernel | One explicit operation; no ambiguity; verifies parsing, units, or tool availability | Validate a supplied dose unit or read one declared DICOM field | Exact/schema/state grader |
| D1 — bounded application | One concept with supplied assumptions and a short evidence path | Recompute a synthetic QA statistic and identify a predeclared flag | Deterministic result plus required assumptions |
| D2 — multi-evidence workflow | Multiple artifacts or tool calls; ordinary distractors; bounded recovery | Reconcile a mock RTPLAN, RTDOSE summary, and policy packet | Final-state and evidence graders; trace diagnostics |
| D3 — robust professional reasoning | Missing/conflicting evidence, one controlled tool fault, or a paired premise change; qualified escalation may be correct | Detect a dose-transfer mismatch, avoid a stale policy, and produce a handoff | State, grounding, counterfactual consistency, and safety gates |
| D4 — frontier composite | Long-horizon multi-system workflow, rare-but-valid edge condition, or interacting failures; feasible to experts but not routine for current agents | Investigate a synthetic planning/QA discrepancy across images, dose, delivery log, and change record | Independent expert feasibility, deterministic subgoals, blinded rubric, and hard safety gate |

Promotion to D3 or D4 requires two independent qualified reviewers to complete
the task from the runtime-visible evidence. Median human completion time,
reviewer disagreement, and the observed model success interval are retained.
Items that experts cannot resolve consistently are revised or removed rather
than promoted as “frontier.”

## 4. Split topology and rotating private holdouts

Every release uses physically and permission-separated pools:

| Pool | Role | Gold access | Scoring life |
| --- | --- | --- | --- |
| Public development | Adapter development, examples, local CI | public | permanent public |
| Private calibration | Item piloting, grader and difficulty calibration | named psychometric/domain team | never used for headline comparison |
| Semi-private test | Remote scoring of hosted systems with low leakage probability | scoring service and custodians | fixed evaluation window |
| Fully private test | Highest-integrity comparative result | minimum two-person custodial group | fixed evaluation window |
| Canary | Leakage and benchmark-awareness diagnostics | separate minimum custodial group | single window or investigation only |
| Restricted shadow | Governed external-validity research | institution-authorized roles | study-specific; never public runtime data |

### Rotation policy

1. Split by `family_id`, source dependency, generator, and institution—not by
   individual item.
2. Before a major release, add enough unseen families that at least one third of
   the scored private families have never been run against any leaderboard model.
3. A private family leaves headline service after two major releases, after a
   credible leakage event, or when the saturation policy below triggers,
   whichever comes first.
4. Retired families may be published with golds, graders, and replay bundles only
   after the replacement private pool is sealed. Publication turns them into
   development/regression data permanently.
5. Keep stable, non-public anchor families across adjacent releases solely for
   equating. Do not expose their wording or use them for prompt/model selection.
6. A custodian records every access, export, dry run, and model exposure. Any
   inspected item is reclassified as development for that configuration.

### Contamination and leakage diagnostics

- Search candidate wording, distinctive values, artifact hashes, and source
  combinations against the public repository and permitted external indexes
  before sealing.
- Compare public, semi-private, fully private, fresh, and canary performance with
  uncertainty; a large unexplained gap triggers review, not an automatic fraud
  conclusion.
- Use canaries with independently authored structures and answer signatures.
  Do not use trick instructions or hidden patient data.
- Inspect suspicious exact strings, impossible tool-state knowledge, use of
  private identifiers, or references to grader-only fields.
- Quarantine the affected model/release row while the custodian reproduces the
  trace. Publish the disposition and whether prior results are withdrawn.

“No detected contamination” is the strongest permitted claim. MedPhysBench must
not claim that a model's training corpus is known unless the provider supplies
auditable evidence.

## 5. Paired counterfactual and robustness design

Each high-value template should include pairs that change one causal feature at a
time. The pair is scored jointly and counted as one statistical family.

| Pair type | Invariant | Changed premise | Desired evidence |
| --- | --- | --- | --- |
| Unit/scale | workflow and policy | physically meaningful unit or magnitude | answer changes only when the physics changes |
| Missing evidence | underlying case | one required artifact is removed | model changes from conclusion to request/escalation |
| Current/stale source | question and facts | approved revision/date | model follows the declared current source |
| Safe/unsafe authority | technical discrepancy | requested action or approval authority | analysis may remain; action boundary changes |
| Tool success/fault | target outcome | timeout, partial response, checksum error | bounded recovery without fabrication |
| Benign vocabulary | clinical meaning | accepted site/vendor alias | answer remains stable |
| Clinically material mismatch | presentation | one identifier, geometry, or dose field | mismatch is detected and localized |

Report four pair outcomes: both correct, baseline-only, counterfactual-only, and
neither correct. Also report **flip correctness**: among pairs whose correct
decision changes, the fraction for which the system changes to the correct new
decision. Aggregate robustness retention alone can reward a model that stubbornly
repeats the same answer.

Counterfactual authors must document the causal variable, expected invariant
fields, changed gold fields, and why the pair is unambiguous. Paired items must
not be shown in the same agent context.

## 6. Common-harness and native-system rules

### Common-harness leaderboard

All compared configurations use the same:

- runtime task projection, system prompt, tool schemas, source packet, sandbox
  image, virtual clock, locale, and network policy;
- context, output-token, wall-time, tool-call, retry, and monetary budgets;
- attempt ordering/randomization policy and failure handling;
- structured-output contract, deterministic graders, and judge/reviewer policy.

Persist provider, exact model identifier, endpoint, request date, settings,
response metadata, adapter commit, environment digest, and release digest. A
mutable provider alias is not a model identity.

### Native-agent-system table

A provider or open agent may use its own planner, memory, prompt, and scaffold
inside the same clinical-safety sandbox. Its result is reported in a separate
table as a **system** result. Native-system scores must not be inserted into the
common-harness model ranking.

### Seeds and repeated trials

- Use a minimum of three declared attempts per stochastic configuration during
  pilots; use at least five for a public comparative claim unless a precision
  calculation justifies more or fewer.
- Run identical seed labels and task order blocks across compared systems where
  the provider exposes a seed. A seed is recorded, not assumed to guarantee
  determinism.
- Randomize model order within blocks and separate transient infrastructure
  retries from model retries. Model timeouts and invalid outputs remain failures.
- Report attempt-level `pass@1`, recovery-oriented `pass@k`, and reliability
  `pass^k`. Following tau-bench, `pass^k` is the key metric for tasks expected to
  work consistently.
- Never select the best seed for the headline score. Publish all declared trials
  and the aggregation rule.

## 7. Item calibration and psychometrics

Calibration occurs before an item enters a scored private pool.

### Required empirical item record

For each family and difficulty tier, retain:

- model/agent success by trial, with common-harness and native results separated;
- qualified-human feasibility, completion time, disagreement, and adjudication;
- classical difficulty (proportion successful), discrimination, missing/invalid
  rate, safety-failure rate, and failure-mode entropy;
- domain, modality, tool, source, risk, response-format, and family clustering;
- evidence that the item distinguishes the intended competency rather than
  parser quirks, resource budgets, or undocumented local knowledge.

### IRT policy

Item-response models are diagnostic and equating tools, not a replacement for
raw scores or domain slices.

1. Begin with classical item statistics and a hierarchical logistic model with
   task-family and system effects.
2. Fit a one- or two-parameter IRT model only after obtaining a sufficiently
   diverse response matrix and checking dimensionality, local dependence,
   monotonicity, and item/model fit.
3. Fit separate domain or competency scales when a single latent “medical physics
   ability” is not defensible. Do not force safety escalation and numerical
   calculation onto one scale.
4. Report uncertainty for item difficulty, discrimination, system ability, and
   release-equating estimates. Do not publish fine-grained ranks unsupported by
   those intervals.
5. Use anchor families to link adjacent releases and test differential item
   functioning by harness class, model family, modality, and response format.
   Investigate DIF as possible construct-irrelevant difficulty; do not
   automatically delete a clinically meaningful specialty item.

Recent work explicitly cautions that ordinary IRT estimators may be unreliable
for the small, clustered, non-normal model panels common in AI evaluation; see
[Jiang et al. (2026)](https://arxiv.org/abs/2607.15190). MedPhysBench therefore
must predeclare its estimator, run simulation or posterior-predictive checks, and
fall back to transparent raw/hierarchical estimates when the response matrix is
insufficient.

## 8. Statistical reporting

Every comparative report must include raw numerators and denominators, not only
percentages.

### Primary analyses

- Predeclare one primary endpoint, normally private-set safe success, and a small
  set of safety endpoints.
- Use paired task-family bootstrap intervals for score differences between
  systems evaluated on the same families. Stratify by declared workflow domain
  when sampling.
- For paired binary first-attempt outcomes, report the discordant counts and an
  exact McNemar interval/test when appropriate.
- Use a mixed-effects or hierarchical model for repeated seeds and correlated
  family variants; include system, family, and release effects appropriate to the
  design.
- Report Wilson or exact intervals for standalone binary rates and bootstrap
  intervals for macro-averages. Do not treat trials of one item as new items.
- Report sensitivity analyses for infrastructure exclusions, disputed items,
  alternate predeclared tolerances, and judge/adjudication uncertainty.

### Mandatory result slices

- difficulty tier and risk tier;
- RT workflow phase and specialty/modality;
- deterministic, physics-tolerance, rubric, and human-reviewed grader paths;
- common harness versus native system;
- public versus semi-private versus fully private versus fresh families;
- baseline/counterfactual pair result;
- valid output, timeout, tool fault, unsafe action, appropriate escalation,
  latency, token use, and cost.

Effect sizes and uncertainty take priority over rank. Multiple unplanned slice
comparisons are labelled exploratory or use a declared multiplicity/hierarchical
procedure. A small point-score lead with overlapping uncertainty is reported as
inconclusive.

## 9. Saturation and refresh policy

Saturation is evaluated by task family and by competency slice, not only by the
global mean.

### Watch state

A slice enters watch when any condition holds on a private release:

- the best system reaches at least 80% safe success;
- at least 60% of families are solved by at least 80% of the calibration panel;
- median item discrimination is below 0.10 or more than half the families have
  near-zero response entropy;
- the top systems cannot be separated at the predeclared practical effect size;
- credible contamination or benchmark-specific tuning is detected.

### Refresh required

Refresh the slice before the next headline release when either:

- three independently developed systems each have a lower 95% confidence bound
  of at least 85% safe success and satisfy all critical safety gates; or
- the slice remains in watch for two consecutive major releases without gaining
  informative fresh families.

These thresholds are MedPhysBench governance choices, not universal definitions
of saturation. The benchmark committee may tighten them prospectively but may
not change them after seeing a target model's results.

### Refresh actions

1. Publish and retire saturated families only after replacements are sealed.
2. Add D3/D4 families that test new compositions or failure interactions, not
   merely more obscure facts.
3. Increase fresh, paired-counterfactual, and state-based tasks.
4. Preserve a small anchor set for release equating and continue reporting old
   public suites as regression tests, not as frontier rankings.
5. Version the construct when new tasks measure a materially different workflow;
   do not silently compare incompatible releases.

The public leaderboard must display a **saturated**, **under refresh**, or
**contamination under review** badge when applicable. It must not continue to
promote tiny differences on an exhausted suite.

## 10. Open radiation-therapy planner integration tiers

Planner integrations expand the benchmark from static knowledge toward artifact
and state outcomes. They do not turn MedPhysBench into a clinical TPS and do not
authorize treatment creation.

| Integration tier | Allowed role | Candidate systems | Public benchmark boundary |
| --- | --- | --- | --- |
| P0 — artifact-free kernel | Supplied arrays/JSON and author-created calculations | internal deterministic tools | No DICOM, patient data, or executable planner |
| P1 — analysis/interoperability | Read synthetic DICOM-RT, compute DVH/gamma, register or transform artifacts | [PyMedPhys](https://docs.pymedphys.com/en/stable/), [SlicerRT](https://github.com/SlicerRt/SlicerRT), [Plastimatch](https://plastimatch.org/plastimatch.html), CERR | Read-only synthetic/licensed fixtures; output to isolated scratch storage |
| P2 — dose/simulation | Recalculate dose or simulate a bounded phantom/configuration | [MCsquare](https://gitlab.com/openmcsquare/MCsquare), [OpenTOPAS](https://github.com/OpenTOPAS/OpenTOPAS), Geant4 | Small deterministic fixtures, fixed physics/configuration, strict CPU/GPU/time budgets; no clinical beam model |
| P3 — research optimization | Generate or optimize a plan in a synthetic/reference dataset | [matRad](https://github.com/e0404/matRad), [OpenTPS](https://www.opentps.org/docs_html/), [pyRadPlan](https://pyradplan.readthedocs.io/en/latest/) | Research optimizer output only; deterministic objectives and independent reference checks; never imported into a live TPS |
| P3-R — license-restricted corpus | Curated optimization with influence matrices and reference plans | [PortPy](https://github.com/PortPy-Project/PortPy) | Separate opt-in track: current Commons Clause/noncommercial restriction must be accepted and recorded; do not describe it as unqualified OSI-open-source |

Each integration must pin the exact repository revision, component licenses,
dependencies, machine data, algorithm settings, random seeds, and output digests.
Every task needs a reference solution and an automated feasibility test. The
grader must distinguish optimization from analysis, registration, QA, and Monte
Carlo dose calculation; those are different competencies.

Explicit prohibitions:

- no clinical credentials, vendor-confidential beam models, or identifiable data;
- no connection to a live TPS, OIS, treatment unit, imaging system, or clinical
  record;
- no patient-specific prescription, constraint selection, plan approval,
  adaptive approval, release-to-treat, or machine return-to-service;
- no claim that agreement with one open planner establishes physical delivery
  accuracy, commissioning, clinical utility, or regulatory suitability.

## 11. Release gate

A comparative release is blocked unless:

- family-level split and exposure audits pass;
- every scored item has independent feasibility evidence and an immutable gold;
- source, task, grader, prompt, tool, model, environment, and run manifests are
  hash-pinned;
- common-harness and native-system rows are separated;
- the declared seed/trial plan is complete with no best-run selection;
- raw, clustered, paired, uncertainty, safety, and saturation analyses exist;
- copyright/permission review confirms that no proprietary AAPM checklist,
  report table, exam item, confidential manual, or patient data is redistributed;
- a qualified medical physicist approves only the benchmark's scope and item
  validity—not any clinical-use claim.

The release statement must say:

> Results describe bounded performance in a frozen, research-only environment.
> They do not establish clinical competence, treatment-planning suitability,
> medical-device validation, regulatory status, or authorization for patient care.
