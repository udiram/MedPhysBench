# MedPhysBench: Reproducible Evaluation of Medical-Physics AI Systems

**Public development releases:** `public-core-v0.5`, `public-tg263-pilot-v0.5`, `public-imaging-pilot-v0.4`, and `public-real-workflows-pilot-v0.6`

**Benchmark version:** `0.6.0`

**Status:** Research benchmark; not clinical validation

## Abstract

Medical-physics work combines quantitative reasoning, evidence review, artifact production,
software and data-system interaction, quality assurance, and the ability to stop when required
information or authority is absent. Most published medical-model evaluations test static question
answering. MedPhysBench instead evaluates whether an AI system can complete a versioned task
correctly, satisfy a machine-checkable output contract, preserve safety boundaries, and produce a
reproducible run record.

Version 0.6 contains an 82-task public-core hardening candidate, including an independently
authored 18-task TG-263-aligned structure-naming lane, plus five separately reported, hash-pinned real
MRI, CT, and PET tasks and a ten-task OpenKBP radiation-therapy pilot derived from two patient
families. The OpenKBP lane spans structure/dose grid segmentation, published-criteria plan review,
data-integrity audit, and TG-263 naming. The core spans radiation therapy, brachytherapy, imaging, nuclear medicine,
radiation safety, informatics, quality assurance, and research methods. Every task has an authored view and a
sealed runtime view; gold answers, graders, and sensitive provenance never cross the candidate
boundary. The reference harness records model identity, prompt and tool hashes, sampling
parameters, latency, provider-response digests, grader results, and safety failures. Results are reported
as task success, safe success, structured-output validity, escalation accuracy, `any_pass`,
`all_pass`, domain results, and Wilson 95% confidence intervals.

Version 0.6 retains deterministic regrading and adds reference-feasibility reconstruction,
hash-verified multimodal assets, bounding-box IoU and grid-mask Dice graders, and sealed-batch
import checks. It also binds each attempt to the grader hash and scoring revision and reports
family-cluster uncertainty for correlated patient-linked tasks. A model is rankable only when its
task/attempt matrix is complete, deterministically regraded, internally consistent, and backed by
per-call execution traces, provider/runtime receipts, usage telemetry, and duration telemetry.
Native conversation-surface pilots are published separately and cannot receive a common-harness rank.
Difficulty governance adds family-level splits, rotating holdouts, paired counterfactuals,
multi-seed consistency, saturation triggers, and a 20-phase radiation-therapy competency map.

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

The frozen scored snapshot, `public-core-v0.4`, contains 64 tasks. The `public-core-v0.5`
candidate contains 82 tasks after adding 18 ambiguity-heavy structure-naming cases. It mixes calculation, evidence-grounding,
checklist, informatics, and abstention boundaries. The `public-imaging-pilot-v0.4` release contains
five licensed retrospective-image tasks and is never merged into the core rank. The
`public-real-workflows-pilot-v0.6` release adds ten tasks from two pinned OpenKBP
cases and is likewise reported separately. Its five views per case share a `family_id`.

| Domain | Representative task families |
| --- | --- |
| Core physics | attenuation, inverse square, uncertainty, units |
| Radiation therapy | dosimetry calculations, QA rules, release boundaries |
| Brachytherapy | decay, dwell-time scaling, release boundaries |
| Imaging | sampling, CT/MR/US calculations, trend escalation |
| Nuclear medicine | activity, SUV, SPECT/PET QA, missing-input boundaries |
| Radiation safety | time, distance, correction, decay, spill boundaries |
| Informatics | DICOM, checksums, timestamps, run integrity |
| Quality assurance | metrics, tolerances, interruption and calibration boundaries |
| Research and statistics | uncertainty, multiplicity, diagnostic metrics, claim restraint |

The open set is designed for harness development, replication, adapter testing, and transparent
baseline comparisons. Because task content and graders are public, it must not be used alone for
strong generalization claims.

## 4. Execution

The reference harness supports Ollama-compatible models and native image payloads. It also imports
a sealed, task-ID-keyed recorded batch for explicitly unranked native-surface pilots. It:

1. constructs a frozen system prompt and runtime task payload;
2. requests a JSON object matching the task schema;
3. records provider/model revision and sampling parameters;
4. preserves raw response and reasoning only in the private execution record, then publishes
   response digests, token counts, and latency after sanitization;
5. converts malformed or absent structured output into an explicit parser failure;
6. runs deterministic outcome, artifact, and safety graders;
7. writes one immutable JSON record per task attempt;
8. aggregates model results into a leaderboard artifact and ranks only complete,
   internally consistent runs.

The structured-output parser accepts exactly one JSON object. It rejects Markdown fences,
surrounding prose, trailing candidates, duplicate keys, non-object roots, and non-finite numeric
constants. This prevents adapter repair behavior from becoming an undocumented source of score.

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
- bounding-box intersection over union;
- coarse-grid mask Dice;
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
- **family-cluster bootstrap interval** when patient/task family identifiers are available;
- **median and total token use**, when the provider reports it;
- **median common-harness wall time**, with unavailable native telemetry shown as missing;
- **score-efficiency Pareto frontier**, reported only within one release and comparable harness.
- **official harness-group rank**, computed only when at least two systems share identical provider,
  harness revision, adapter-settings hash, sampling/token contract, and seed policy;
- **descriptive cross-surface outcome order**, available to complete native rows but never labeled API-equivalent.

Ranks are descriptive. Overlapping intervals and small public task counts make close rank
differences unsuitable for superiority claims. Larger sealed suites should use hierarchical
bootstrap intervals and publish rank uncertainty.

### 6.1 Public baseline snapshot

Five local models completed the 64-task core through the common Ollama harness. Their historical scores ranged
from 25.00% to 73.44%; `qwen3:14b` led with 73.44% safe
success with a 98.44% safety-gate rate. Those v1 artifacts predate the current grader-hash and
scoring-revision contract, so their point estimates remain visible but no longer receive current-contract
official ranks. Six GPT-5.6 effort configurations completed the same sealed
runtime batch on a native Codex conversation surface; three scored 100% and three scored 98.44%, all
with 100% safety-gate rate. Those GPT rows are deliberately unranked because the surface was not the
common adapter and did not provide equivalent isolation or sampling controls. Three local vision
models also completed the separate imaging pilot. Ten local models and five Groq-hosted
models then completed three attempts on every OpenKBP v0.6 task. `qwen3.5:4b` led the four-system
Ollama v1 group
at 50.0% safe success; `llama-3.3-70b-versatile` and `openai/gpt-oss-20b` tied at 60.0% in the Groq
group. GPT-5.6 low, high, and ultra completed three native-surface attempts per OpenKBP task and
scored 66.67%, 76.67%, and 73.33%, respectively. Their descriptive outcome order is high, ultra,
then low, but their Wilson intervals overlap. Those native rows have no official harness-group rank
because they lack the common adapter and comparable token/time telemetry.
DeepSeek R1 Distill Qwen 1.5B, Phi-4 Mini, and five additional digest-pinned local models completed the
same v2 matrix. Qwen 3 14B and 8B each reached 40.0% safe success, Qwen 2.5 7B Instruct
reached 30.0%, Phi-4 Mini reached 10.0%, and Qwen 3 1.7B, DeepSeek R1 1.5B, and
Llama 3.2 3B reached 0.0%.
Every text-only model retained twelve explicit unsupported-image outcomes in the denominator.
The seven-system exact-configuration group now receives a within-group rank; it is not merged with
the older Ollama, Groq, or native GPT-5.6 groups.
Full evidence is published in
[`RESULTS.md`](RESULTS.md) and the release directories.

To probe saturation, GPT-5.6 high and ultra were also evaluated on the 18-task TG-263 pilot.
They achieved 27.78% and 22.22% safe success respectively while preserving 100% of safety and
required-escalation gates. These are unranked native-surface results, but they show that a perfect
score on the earlier public core does not transfer to stricter naming and ambiguity contracts.

## 7. Reproducibility artifacts

Each public score is backed by:

- the versioned release manifest;
- task YAML and schema versions;
- frozen system/user prompt construction;
- system-prompt, task-prompt, tool-schema, and runtime-task hashes;
- provider and model revision;
- temperature, seed, and token budget;
- sandbox/tool-environment identifiers;
- sanitized provider-response digests and parse events;
- deterministic grader outputs;
- task-level duration and error state;
- generated leaderboard JSON.

During publication, the summarizer verifies the expected `(task_id, attempt_index)` set, rejects
duplicates, unknown tasks, unresolved transport-error attempts, and mixed execution configurations, enforces
task/model/harness identity consistency, checks prompt/tool/runtime/system hashes, and recomputes
deterministic grades from output. Any disagreement between stored and recomputed pass/safety fields
makes the row unrankable and remains visible in the integrity report. Common-harness calls must also
carry a model-response trace, non-empty provider/runtime receipt, usage counts, and positive duration;
an explicit unsupported-modality preflight trace is the only no-call exception.

Contributed bundles additionally use `common-harness-submission.v1`, which binds the frozen release
hash, source commits, base-model mapping, environment, attestations, and every result or transport
ledger file by byte length and SHA-256. CI rejects omitted, inserted, reordered, or modified artifacts.
This is auditable provenance rather than cryptographic proof of honest third-party execution; stronger
claims require managed runners or independently signed provider receipts.

Unsupported required modalities and provider JSON-generation failures are completed zero-score
model attempts rather than transport errors. This prevents systems from escaping the denominator by
declining difficult inputs while keeping infrastructure failures distinct from model behavior.

The repository CI runs contract tests, task-release validation, repository-wide schema checks over
all authored tasks, sealed runtime projections, run manifests, and public results, lint, public
reasoning-redaction checks, and the deterministic reference demo. Live model scores are never
regenerated in CI without an explicit campaign.

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

- 97 public tasks still do not represent the breadth or prevalence of medical-physics work.
- Most core inputs are synthetic. The imaging pilot contains reduced, de-identified public research
  images under MSD, TCIA, and AutoPET/ENHANCE.PET terms.
- The development set is public and therefore contamination-prone.
- Current published scores use one attempt per task unless a manifest states otherwise.
- The v1 `prompt_hash` remains the legacy instruction hash for comparability; separate system-prompt
  and full-runtime-task hashes bind the complete candidate-visible contract.
- Tool-state and file-artifact tracks are implemented in the architecture but require additional
  expert-authored release tasks before they can support headline results.
- Model availability through a local Ollama installation is an access snapshot, not an exhaustive
  survey of frontier systems.
- The PET classification pilot contains one released negative source label and cannot estimate
  diagnostic performance, subgroup performance, or clinical utility.
- The benchmark has not undergone external peer review or medical-device validation.
- The OpenKBP v0.6 lane has only two patient families, pending independent domain/publication-rights
  review, and no measured human baseline. Its ten task views are not ten independent cases.

These limits are reported as part of the result, not deferred to fine print.

## 10. Release plan

The next research-grade release gates are:

1. recruit independent medical-physics reviewers and publish reviewer criteria;
2. expand beyond 100 independently reviewed tasks with prespecified domain/risk quotas;
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
11. Antonelli M, et al. *The Medical Segmentation Decathlon*. Nature Communications. 2022. https://www.nature.com/articles/s41467-022-30695-9
12. Armato SG III, et al. *The Lung Image Database Consortium and Image Database Resource Initiative*. Medical Physics. 2011. https://doi.org/10.1118/1.3528204
13. ENHANCE.PET initiative. *ENHANCE.PET 1.6k*. https://registry.opendata.aws/enhance-pet-1-6k/
