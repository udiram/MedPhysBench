# MedPhysBench: Reproducible Evaluation of Medical-Physics AI Systems

**Public development release:** `public-dev-2026-07-31`  
**Benchmark version:** `0.2.0`  
**Status:** Research benchmark; not clinical validation  

## Abstract

Medical-physics work combines quantitative reasoning, evidence review, artifact production,
software and data-system interaction, quality assurance, and the ability to stop when required
information or authority is absent. Most published medical-model evaluations test static question
answering. MedPhysBench instead evaluates whether an AI system can complete a versioned task
correctly, satisfy a machine-checkable output contract, preserve safety boundaries, and produce a
reproducible run record.

The first public development release contains 16 synthetic and source-grounded tasks spanning core
physics, radiation therapy, brachytherapy, imaging, nuclear medicine, radiation safety,
informatics, quality assurance, and research interpretation. Every task has an authored view and a
sealed runtime view; gold answers, graders, and sensitive provenance never cross the candidate
boundary. The reference harness records model identity, prompt and tool hashes, sampling
parameters, latency, raw provider output, grader results, and safety failures. Results are reported
as task success, safe success, structured-output validity, escalation accuracy, `any_pass`,
`all_pass`, domain results, and Wilson 95% confidence intervals.

This release is a complete public-development evaluation loop and publication package. It is not
evidence of autonomous clinical competence. Headline generalization claims require the planned
expert-vetted, contamination-controlled sealed evaluation lane.

## 1. Motivation

Medical physics is not one exam. A useful evaluation must distinguish at least four questions:

1. Did the system produce the correct outcome?
2. Did it produce the required artifact or final environment state?
3. Did it recognize missing information, policy boundaries, and mandatory escalation?
4. Can the result be reproduced from a frozen run contract?

The benchmark therefore avoids a single prose-quality judge and does not treat a fluent answer as
success. It also keeps base-model/common-harness comparisons separate from native agent-system
comparisons.

MedAgentBench is the closest medical agent-evaluation analogue, with FHIR-grounded tasks in a
medical-record environment, but it does not cover the breadth of medical-physics work [1,2].
Published radiation-oncology physics evaluations provide valuable knowledge-testing evidence but
remain primarily static question-answering studies [3]. MedPhysBench targets the missing
tool-, artifact-, and escalation-aware layer.

## 2. Benchmark contract

Each task pack declares:

- stable task and schema versions;
- domain, track, access class, and risk tier;
- instructions and structured inputs;
- runtime-visible context artifacts;
- allowed tool interfaces and budgets;
- a strict JSON output schema;
- deterministic graders;
- escalation expectations and prohibited actions;
- provenance, licensing, and PHI review status;
- contamination tags and stop conditions.

`TaskSpec.runtime_task()` is the only representation a candidate may receive. The projection
deliberately excludes the grading block, provenance, author identity, and reference output. Tests
assert this separation and assert that CLI validation cannot print grading material.

## 3. Public development release

The `public-dev-2026-07-31` release contains 16 tasks. It intentionally mixes calculation,
evidence-grounding, checklist, informatics, and abstention boundaries.

| Domain | Representative task families |
| --- | --- |
| Core physics | inverse-square scaling and units |
| Radiation therapy | output deviation, EQD2, plan-release boundary |
| Brachytherapy | radionuclide decay |
| Imaging | CT pixel spacing, trend escalation, protocol checklist gaps |
| Nuclear medicine | decay-corrected activity and effective half-life |
| Radiation safety | barrier transmission and boundary-aware interpretation |
| Informatics | DICOM identifier-tag handling |
| Quality assurance | missing baseline and missing detector calibration |
| Research and leadership | source-packet claims and confidence-interval restraint |

The open set is designed for harness development, replication, adapter testing, and transparent
baseline comparisons. Because task content and graders are public, it must not be used alone for
strong generalization claims.

## 4. Execution

The current reference harness supports Ollama-compatible local and cloud models. It:

1. constructs a frozen system prompt and runtime task payload;
2. requests a JSON object matching the task schema;
3. records provider/model revision and sampling parameters;
4. preserves raw response, reasoning field when the provider exposes it, token counts, and latency;
5. converts malformed or absent structured output into an explicit parser failure;
6. runs deterministic outcome, artifact, and safety graders;
7. writes one immutable JSON record per task attempt;
8. aggregates model results into a leaderboard artifact.

Provider failures are not converted into answers and do not disappear from denominators. The
campaign runner can continue after an error, while `--fail-fast` is available for adapter
qualification.

## 5. Grading

The public grader library currently supports:

- JSON Schema validation;
- numeric tolerance;
- exact scalar match;
- unordered exact-list match;
- required source or concept strings;
- mandatory escalation.

Task success requires every declared grader to pass. Safety is reported independently: a
non-safety mistake does not become a safety failure, and a critical unsafe action cannot be hidden
by averaging other grades.

Future artifact tasks use the same pattern to grade final files or sandbox state. Human or
model-based adjudication, when needed, remains a separate lane with blinded review and
inter-rater reporting.

## 6. Metrics and uncertainty

The public leaderboard reports:

- **task success rate**: fraction of attempts passing all graders;
- **safe success rate**: fraction passing all graders without a critical safety failure;
- **safety-gate rate**: fraction without a critical safety failure;
- **valid-output rate**: fraction satisfying the declared JSON Schema;
- **appropriate-escalation rate**: correct behavior on tasks requiring escalation;
- **critical unsafe-action rate**;
- **`any_pass`**: fraction of tasks with at least one successful attempt;
- **`all_pass`**: fraction of tasks for which every attempt succeeds;
- **domain safe success**;
- **Wilson 95% confidence interval** over binary attempt success.

Ranks are descriptive. Overlapping intervals and small public task counts make close rank
differences unsuitable for superiority claims. Larger sealed suites should use hierarchical
bootstrap intervals and publish rank uncertainty.

## 7. Reproducibility artifacts

Each public score is backed by:

- the versioned release manifest;
- task YAML and schema versions;
- frozen system/user prompt construction;
- provider and model revision;
- temperature, seed, and token budget;
- prompt and tool-schema hashes;
- sandbox/tool-environment identifiers;
- raw provider response and parse events;
- deterministic grader outputs;
- task-level duration and error state;
- generated leaderboard JSON.

The repository CI runs contract tests, task-release validation, lint, and the deterministic
reference demo. Live model scores are never regenerated in CI without an explicit campaign.

## 8. Governance and validation

Public task contributions follow:

`Propose → dual domain-expert review → reference run → leakage review → public or sealed release`

Acceptance requires solvability, an explicit gold contract, reproducible execution, licensing and
privacy review, and a named owner. Sealed evaluation tasks additionally require access control,
audit logging, and a rule preventing candidate outputs from influencing label disclosure before
the run closes.

The safety positioning follows IAEA, FDA, and WHO guidance emphasizing intended use, human
oversight, clear limits, quality assurance, and fallback behavior [7–10].

## 9. Limitations

The public release has deliberate limits:

- 16 tasks are enough to test the evaluation loop but not enough to represent medical physics.
- Most inputs are synthetic; no patient data or proprietary clinical content is included.
- The development set is public and therefore contamination-prone.
- Current published scores use one attempt per task unless a manifest states otherwise.
- Tool-state and file-artifact tracks are implemented in the architecture but require additional
  expert-authored release tasks before they can support headline results.
- Model availability through a local Ollama installation is an access snapshot, not an exhaustive
  survey of frontier systems.
- The benchmark has not undergone external peer review or medical-device validation.

These limits are reported as part of the result, not deferred to fine print.

## 10. Release plan

The next research-grade release gates are:

1. recruit independent medical-physics reviewers and publish reviewer criteria;
2. expand to at least 100 vetted tasks with prespecified domain/risk quotas;
3. add resettable tool-state and artifact tasks in container images pinned by digest;
4. establish a private holdout and rotating fresh set;
5. run contamination and solvability audits;
6. repeat models across multiple seeds to estimate consistency;
7. add blinded human adjudication only for tasks that cannot be graded deterministically;
8. publish a benchmark card, data statement, and external validation report.

## References

1. Stanford ML Group. *MedAgentBench*. https://stanfordmlgroup.github.io/projects/medagentbench/
2. Kim Y, et al. *MedAgentBench: A Realistic Virtual EHR Environment to Benchmark Medical LLM Agents*. arXiv:2501.14654. https://arxiv.org/abs/2501.14654
3. Holmes J, et al. *Evaluation of large language models in radiation oncology physics*. Frontiers in Oncology. 2025. https://www.frontiersin.org/journals/oncology/articles/10.3389/fonc.2025.1557064/full
4. OpenAI. *Introducing SWE-bench Verified*. https://openai.com/index/introducing-swe-bench-verified/
5. Anthropic. *Demystifying evals for AI agents*. https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
6. Stanford CRFM. *HELM*. https://github.com/stanford-crfm/helm
7. International Atomic Energy Agency. *Artificial Intelligence for Accelerating Nuclear Applications, Science and Technology*. https://www-pub.iaea.org/MTCD/publications/PDF/p15925-PUB2135_web.pdf
8. U.S. Food and Drug Administration. *Transparency for Machine Learning-Enabled Medical Devices: Guiding Principles*. https://www.fda.gov/medical-devices/software-medical-device-samd/transparency-machine-learning-enabled-medical-devices-guiding-principles
9. World Health Organization. *Ethics and governance of artificial intelligence for health*. https://www.who.int/publications/i/item/9789240029200
10. World Health Organization. *Ethics and governance of artificial intelligence for health: guidance on large multi-modal models*. https://www.who.int/publications/i/item/9789240084759
