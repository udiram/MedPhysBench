# Implementation Plan

## Executive sequence

Build MedPhys-AgentBench as a series of claims that can be proven, in this order:

1. A task can be authored, sealed, executed, and deterministically scored.
2. A model/agent can use safe virtual tools in an isolated sandbox.
3. A run can be replayed, inspected, and statistically compared with another run.
4. Experts can author and adjudicate domain-valid tasks with measured agreement.
5. Restricted shadow evaluation can be conducted without making clinical-use claims.
6. A public benchmark release can withstand leakage, gaming, and reproducibility
   scrutiny.

Do **not** start with a leaderboard, a model selection claim, or live software
integration. Those are outputs of a validated platform, not its foundation.

## Program charter — first decision gate

Before the next engineering sprint, produce and sign a two-page charter.

| Decision | Recommended v1 answer |
| --- | --- |
| Name | MedPhys-AgentBench (working name) |
| Intended use | Research, education, procurement research, and offline/shadow evaluation |
| Non-intended use | Patient-specific recommendation, release-to-treat, autonomous imaging/procedure/QA control |
| First modalities | Radiation therapy physics plus imaging physics core; nuclear medicine and radiation safety after governance review |
| Initial risk scope | Tier 1 public tasks and a small Tier 2 shadow-only tranche |
| Public deliverable | Dev set, task spec, harness, scoring protocol, model cards, aggregate report |
| Private deliverable | Sealed test and canary set, restricted shadow suite, raw model traces where permitted |
| Governing success claim | “Auditable safe-task performance under this benchmark release,” never “clinical competence” |

**Gate 0 acceptance criteria**

- An accountable benchmark lead and domain leads are named.
- A data/rights policy, prohibited-use policy, disclosure policy, and incident path
  exist.
- Tier definitions and mandatory escalation language are agreed before task
  drafting.
- The institution’s privacy/IRB/compliance route for retrospective shadow data is
  mapped—even if Phase 1 uses only public/synthetic material.

## Workstreams

The work is parallelizable, but release decisions are sequential.

| Workstream | Owner profile | Main deliverable | Starts |
| --- | --- | --- | --- |
| W1 Charter and governance | CQMP lead + privacy/compliance partner | signed evaluation charter and release policy | immediately |
| W2 Harness kernel | platform engineer | task contracts, sealed projections, runner, deterministic grading | immediately |
| W3 Sandboxing/tool fixtures | systems engineer + domain engineer | isolated execution and virtual medical-physics tool environments | after W2 contract draft |
| W4 Task authoring | domain panels | SME-reviewed, feasible task packs | immediately, but release only after W2 |
| W5 Data/provenance | data steward + privacy reviewer | asset ledger and dataset release workflow | immediately |
| W6 Model adapters | AI engineer | provider-neutral-but-fidelity-preserving adapters | after W2 |
| W7 Validation science | biostatistician + eval lead | sampling plan, metrics, judge calibration, report protocol | immediately |
| W8 Observability/review | full-stack engineer | trace explorer and blinded review queue | after W2 |
| W9 Security/operations | security/SRE | environments, identities, backup/restore, incident drills | after W2 |
| W10 Publication/community | scientific editor + open-source maintainer | benchmark card, contributor guide, release archive | after pilot results |

For a focused initial build, one strong platform engineer, one AI/evaluation
engineer, a part-time security/SRE partner, and 4–8 compensated domain experts
can make a credible v1. Domain review—not code—is usually the long pole.

## Phase 1 — Kernel and public development suite

**Goal:** prove the basic evaluation contract on synthetic/public materials.

### Build

- Finish the current Python package as a properly tested library/CLI.
- Replace loose dictionaries at production boundaries with Pydantic v2 models and
  versioned JSON Schema validation.
- Split authored task bundle, runtime projection, and hidden gold storage.
- Add a `TaskRelease` record with content hashes and review sign-off.
- Add deterministic graders: required fields, numeric tolerance, unit checks,
  citation-ID checks, JSONPath rules, file checks, and safety escalation gates.
- Add result JSON Schema and a machine-readable benchmark report format.
- Add dev fixtures covering pass, malformed-output, timeout, forbidden-tool, and
  unsafe-escalation failure paths.
- Implement test CI: unit tests, schema tests, reference-solution feasibility,
  linter, dependency scan, and public-fixture license scan.

### Task content

Start with 30–60 public development tasks, all small enough to be reviewed
deeply. Suggested mix:

- 12 calculation / unit / uncertainty tasks;
- 8 source-grounded evidence and policy-extraction tasks;
- 8 QA/checklist / discrepancy-classification tasks;
- 6 documentation/provenance tasks; and
- 6 safety/escalation and ambiguity tasks.

Every task needs a reference solution, rationale, gold artifact, mandatory
escalation behavior, known ambiguity, provenance ledger entry, and one test that
the reference solution passes.

### Exit gate

- The runner completes a public suite without a manual data fix.
- Gold labels cannot be observed in the agent runtime projection (automated test).
- A task with malformed JSON is marked invalid without grader crash.
- A forbidden network/tool call is denied and recorded.
- Every released task has a passing reference solution and confirmed license/
  provenance record.
- No clinical system, PHI, or vendor-restricted source is present.

## Phase 2 — Sandboxed tool-use evaluation

**Goal:** test agent behavior, not merely medical-physics prose.

### Build

- Add a sandbox executor: rootless containers, read-only root filesystem, scoped
  inputs/outputs, resource quotas, and network off by default.
- Add a tool gateway with declarative allowlists and audit events.
- Add fixture modes: local function, CLI, HTTP mock, file system, database, and
  DICOM service.
- Add seeded Orthanc/DICOMweb fixture packs for non-PHI DICOM workflow tasks.
- Add a safe code-execution profile for calculations, parsing, and report
  generation. It has no host mounts, package installation, credentials, or
  internet access.
- Add deterministic state graders for generated files, DICOM tags, SQL state,
  command logs, and tool-policy compliance.
- Add an execution replay bundle: task projection, tool data, image digest,
  config, output, trace, and verifier result.

### Candidate task types

- inspect a frozen DICOM study and extract permitted metadata;
- recognize a missing/contradictory tag and request escalation;
- calculate a supplied QA quantity with units and uncertainty;
- complete a synthetic chart-review checklist from bounded inputs;
- find an inconsistency across several frozen SOP fragments;
- create a validated structured report without inventing a tolerance or approval.

### Exit gate

- At least three task families use state-based deterministic grading.
- One DICOM virtual-tool task passes for the reference agent and fails safely when
  a tool policy is violated.
- A recovered/replayed run produces the same deterministic grade with the same
  artifacts.
- Pen-test-style attempts to reach host files or the internet are blocked.

## Phase 3 — Evaluation platform and model adapters

**Goal:** run fair, inspectable comparisons across frontier and open models.

### Build

- Introduce a durable workflow engine (Temporal recommended) for queueing,
  retries, timeouts, batch fan-out, and human-review pauses.
- Add first-party adapters for each evaluated provider and an OpenAI-compatible
  local endpoint adapter. Preserve raw provider event artifacts and normalize only
  after capture.
- Add model registry records with provider, exact model ID, stated revision,
  request date, parameters, tool settings, adapter revision, and policy version.
- Add PostgreSQL metadata, MinIO/S3 artifact store, OpenTelemetry spans, and a
  trace explorer.
- Build a read-only reviewer dashboard: result slices, task state, artifacts,
  grader rationale, model identity masking, and review queue.
- Implement per-task repeated trials, random ordering, warm-up policy, provider
  backoff policy, and cost/latency capture.
- Add a LLM-rubric service only for explicitly non-deterministic dimensions;
  pin its model/prompt, blind candidate identity, and route disagreement to
  humans.

### Experimental design controls

- Common-harness results: same system prompt, tools, token budget, retry rules,
  and environment for every base model.
- Native-agent results: allowed, but reported separately with exact agent-shell
  description; never mix them into common-harness ranking.
- Freeze task release before submitting run requests.
- Treat any task used during tuning as development data, never holdout data.
- Shuffle task ordering and record concurrency to detect provider/load artifacts.

### Exit gate

- A full run across two adapters produces complete manifests and replay bundles.
- Report includes confidence intervals, task counts, failure denominators, and
  missing/invalid attempts—not only averages.
- Review UI permits a blinded human to adjudicate a flagged item without seeing
  the candidate model identity.
- Judge-vs-human calibration analysis is available before any LLM-derived score
  is published.

## Phase 4 — Domain-valid pilot benchmark

**Goal:** create evidence that the benchmark measures useful medical-physics
work, rather than simply prompt familiarity.

### Task-development protocol

1. Domain lead proposes a job-relevant task template.
2. Two independent experts author or review the task and answer space.
3. A reference agent/human executes it in the frozen environment.
4. An adversarial reviewer tries to find ambiguity, hidden assumptions, and
   harmful interpretation paths.
5. Authors revise; third expert adjudicates remaining disagreement.
6. A data/rights reviewer confirms provenance and release class.
7. Item is labelled development, validation, sealed-test, canary, or retired.

Begin a private pilot with approximately 120–200 items distributed across core
physics, radiotherapy, imaging, documentation/operations, and safety/escalation.
Do not chase breadth at the expense of inter-rater agreement. Track and report
which roles, modalities, and vendors are **not** represented.

### Exit gate

- Each domain slice reaches a pre-declared expert-agreement threshold appropriate
  to the task type; weak items are retired rather than forced into a score.
- At least 20% of pilot items are held out from prompt/harness tuning.
- The holdout is physically/permission separated from the development set.
- A red-team exercise demonstrates that model identity, labels, and canary inputs
  cannot be retrieved through task metadata or tool fixtures.

## Phase 5 — Restricted retrospective shadow suite

**Goal:** test external validity without clinical intervention.

This phase is optional and requires institutional data/privacy/IRB determination,
formal access controls, and a documented model-provider policy. It is not a
condition for publishing an open v1.

### Rules

- Use properly approved, de-identified historical artifacts only.
- Scan DICOM headers and pixel/overlay/burned-in text; record the de-ID method.
- Keep data in an isolated restricted tenant; no public artifact copies.
- Use offline/local models by default. Hosted APIs require explicit approval,
  contractual review, and configuration evidence.
- Run in retrospective silent mode: no one relies on output for a care decision.
- Analyze by site, modality, vendor, patient/context subgroup where valid, task
  difficulty, and source freshness. Do not claim generalizability from one site.

### Exit gate

- Security review and access audit pass.
- No restricted examples are included in public releases or telemetry exports.
- The evaluation report separates observed retrospective performance from any
  prospective clinical utility claim.

## Phase 6 — Public release and continuous operation

**Goal:** publish a benchmark that remains meaningful after models train on it.

### Release package

- benchmark card: scope, intended/non-intended use, data statement, task taxonomy,
  grading, known gaps, versions, and limitations;
- public development set plus reference harness;
- sealed-test access and submission policy;
- signed task and harness release artifacts;
- model report template and leaderboard inclusion policy;
- failure taxonomy, safety scorecard, and per-domain results—not a single ranking;
- reproduction package for selected results; and
- issue reporting, correction, deprecation, and incident processes.

### Continuous work

- rotate sealed canaries and refresh holdouts on a published cadence;
- monitor for contamination/leakage and task gaming;
- rerun a sentinel suite after harness, provider, judge, or tool-environment
  changes;
- retain comparable historical releases; never silently overwrite scores;
- publish errata and task retirements with reason codes; and
- conduct an annual governance, privacy, and clinical-scope review.

## Delivery timeline and resourcing

These are planning ranges, not promises; the key variable is SME review capacity.

| Milestone | Typical elapsed range | Critical contributors |
| --- | --- | --- |
| Charter + kernel proof | 2–4 weeks | benchmark lead, platform engineer, 2 SMEs |
| Sandboxed tools + 30–60 dev tasks | 4–8 additional weeks | platform/systems engineer, domain authors |
| Comparison platform + review UI | 4–8 additional weeks | AI engineer, full-stack engineer, evaluator |
| 120–200-item private pilot | 8–16 additional weeks | 4–8 domain reviewers, adjudicator, data steward |
| Restricted shadow suite | variable; approval-dependent | privacy/IRB, security, local IT, domain leads |

The leanest credible early team is 2 technical FTE-equivalents plus meaningful
protected/compensated SME time. A public benchmark that lacks task adjudication,
separate hidden labels, and proper reporting is cheaper, but it will not support
the rigor claim the project is aiming for.

## Operational readiness checklist

Before calling the platform “v1-ready,” verify all of the following:

- [ ] Reference solutions pass every released task in the final release image.
- [ ] Runtime task projection cannot reveal gold labels, task-author identity, or
      restricted provenance.
- [ ] A model cannot access host files, credentials, internet, or a live clinical
      endpoint from a normal task sandbox.
- [ ] Every model result has exact task, harness, model, settings, tool, grader,
      and artifact identity.
- [ ] Results distinguish execution failure, invalid output, correctness failure,
      safety failure, and unresolved adjudication.
- [ ] LLM judges are calibrated against blinded human review for the scores they
      influence.
- [ ] Reported metrics have uncertainty intervals and per-slice denominators.
- [ ] Public/gated/restricted data are separate in storage, credentials, and
      release workflow.
- [ ] Backup restore, compromised-token response, and task-leakage response have
      been rehearsed.
- [ ] Governance group signs the benchmark card and release decision.

The architecture and task taxonomy are detailed in
[ARCHITECTURE.md](ARCHITECTURE.md) and [TASK_CATALOG.md](TASK_CATALOG.md).
