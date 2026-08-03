# Benchmark methods review

Status: adopted design review, 2026-08-01

MedPhysBench is already unusually strict for an early domain benchmark: task and runtime views are separated, releases and run identities are immutable, scored artifacts are deterministically regraded, rank eligibility is explicit, and native execution surfaces are not silently merged with common-harness rankings. The limiting factor is now evidence maturity, not basic harness construction.

Release loading now also enforces a declared task-family concentration ceiling (50% by
default), and the public forensic view projects only explicitly scoped defect records onto
individual tasks. These controls reduce correlated-case score inflation and make known QA
limitations inspectable at the same level as model evidence; neither substitutes for a
larger, independently reviewed family set.

This review compares the current system with contemporary benchmark practice and records what MedPhysBench will adopt next. It does not convert a public development release into clinical or human-comparison evidence.

## Lessons from leading benchmarks

| Benchmark practice | Why it matters | MedPhysBench action |
| --- | --- | --- |
| Datapoint-level audits in [the 2026 SWE-Bench Pro review](https://openai.com/index/separating-signal-from-noise-coding-evaluations/) | Longer, more realistic tasks can still be broken by underspecified prompts, overly strict tests, low-coverage tests, or misleading instructions; the audit estimated roughly 30% of the public set was broken. | Run automated attempt/failure-trace triage, independent investigator passes, and blinded domain-expert review; treat both false rejection and false acceptance as release-blocking defects. |
| Human feasibility review in [SWE-bench Verified](https://openai.com/index/introducing-swe-bench-verified/) | Executable tests can still be unfair, underspecified, or reject valid solutions. | Require two independent qualified physicist reviews for D3/D4 and real-workflow families before promotion. |
| Continuing defect audits in [SWE-bench](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/) | A released benchmark can later prove broken or contaminated. | Maintain a public defect and invalidation ledger; never silently rewrite a released score. |
| Fresh and delayed-release questions in [LiveBench](https://livebench.ai/) and [SWE-bench-Live](https://github.com/microsoft/swe-bench-live) | Static public tests invite memorization and optimization against labels. | Operate rotating canaries plus semi-private and private family-level holdouts. Public tasks remain development/regression data. |
| Private test material in [GAIA](https://arxiv.org/abs/2311.12983), [Humanity's Last Exam](https://agi.safe.ai/), and [FrontierMath](https://epoch.ai/frontiermath) | Protected answers and tasks extend the useful life of difficult evaluations. | Publish aggregate holdout results and contract metadata without task text, golds, or grader internals. |
| Real executable environments in [OSWorld](https://osworld-v1.xlang.ai/) and [Terminal-Bench](https://www.tbench.ai/) | State-graded workflows measure completion, not merely plausible prose. | Promote read-only DICOM, planning, QA, and analysis sandboxes with deterministic final-state graders. |
| Trajectory review and reward-hacking policy in [Terminal-Bench](https://www.tbench.ai/news/leaderboard-integrity-update) | Passing a test through leakage or a loophole is not the intended capability. | Require trajectories for protected passing trials, mutation tests, negative controls, and a documented exploit-review decision. |
| Continuous validation and versioned repairs in [Terminal-Bench 2.1](https://www.tbench.ai/news/terminal-bench-2-1) | Expert-reviewed tasks can still reveal defects after launch, and repairs can materially change model results. | Run validation continuously, publish a new immutable release for task repairs, and retain the prior score plus defect disposition. |
| Human task-time evidence in [METR/RE-Bench](https://metr.org/blog/2024-11-22-evaluating-r-d-capabilities-of-llms/) | Difficulty labels are stronger when tied to expert work rather than author intuition. | Publish anonymized physicist time, success, confidence, and adjudication evidence under the preregistered protocol. |
| Scenario and metric transparency in [HELM](https://crfm.stanford.edu/helm/index.html) | A single aggregate hides capability and risk variation. | Publish task-family, domain, safety, reliability, integrity, and efficiency slices beside the primary metric. |
| Closed/open divisions and audited system descriptions in [MLPerf](https://docs.mlcommons.org/inference/submission/) | Performance is only comparable under declared system and rule constraints. | Treat common-harness and native-system results as separate divisions; preserve exact model, provider, adapter, effort, hardware, and pricing snapshots. |
| Confidence intervals in [Chatbot Arena](https://www.lmsys.org/blog/2023-12-07-leaderboard/) | Point-estimate ranks imply distinctions that sampling evidence may not support. | Display intervals beside every score and avoid ordinal claims when intervals and family-adjusted evidence do not distinguish rows. |
| Repeated evaluation and uncertainty in [Artificial Analysis](https://artificialanalysis.ai/methodology/intelligence-benchmarking) | A polished aggregate is not trustworthy if trial count, confidence interval, or benchmark-version change is hidden. | Publish repeat count and score intervals; version any grader, weighting, or task-set change; keep score, time, tokens, and eventual cost as separate evidence views. |
| Anti-saturation targeting in [LiveBench](https://livebench.ai/livebench.pdf) | A suite that lets frontier models cluster near 100% stops distinguishing systems and invites test-specific optimization. | Review task families when the strongest validated systems leave the intended difficulty band; add fresh families and retire saturated public-development items rather than silently moving thresholds. |
| Calibration reporting and private holdout in [Humanity's Last Exam](https://lastexam.ai/) | Accuracy alone omits whether a model knows when it is likely wrong, while a fully public static set invites overfitting. | Add confidence/Brier-style reporting only after confidence collection is standardized, and operate a physically separate family-level shadow holdout before any frontier claim. |
| Leakage and test-poisoning reports in [SWE-bench](https://github.com/SWE-bench/SWE-bench/issues/465) and [its poisoned-test discussion](https://github.com/SWE-bench/SWE-bench/issues/538) | A system can appear to pass through future-state leakage or by weakening the evaluator rather than completing the intended task. | Add leak/poison canaries, make grader/test assets read-only, hash the sandbox state before and after execution, and require trajectory review for protected passes. |
| Claim, system, budget, elicitation, and validity disclosures in [the trustworthy third-party evaluation playbook](https://openai.com/index/trustworthy-third-party-evaluations-foundations/) | A model name and score omit the harness, tools, turns, tokens, retries, time, and checks needed to interpret a result. | Treat the exact tested configuration and resource budget as part of the result; publish validity checks for contamination, reward hacking, refusals, evaluation awareness, and harness sensitivity. |
| Real clinical-task taxonomies in [MedHELM](https://medhelm.org/) and interactive medical environments in [MedAgentBench](https://stanfordmlgroup.github.io/projects/medagentbench/) | Exam-style knowledge is not a substitute for work products and tool-mediated workflows. | Keep knowledge tasks as one lane; shift growth toward read-only artifacts, tools, multimodal evidence, and safe escalation. |

## Critical gap assessment

### P0 — protected evaluation is not operating

All currently shipped releases are public. Public task text, labels, and grader contracts are appropriate for development and reproducibility, but not for a durable frontier claim. The next comparison release must be split by `family_id`, held outside the public repository, and evaluated through an audited service or controlled lab process. Canary families should detect task extraction and label leakage.

### P0 — expert and human evidence is preregistered, not complete

The OpenKBP release is correctly labeled provisional. It remains unsuitable for human-level, clinical-validation, or broad workflow claims until independent domain review, rights review, and the human baseline are complete. A small preregistered pilot may precede the full target, but incomplete evidence must remain visible.

### P1 — public core reliability is single-shot

The frozen public core is useful for regression, but a single attempt per task cannot support strong stochastic comparisons. A comparison-grade subset should use at least five declared attempts per model/task. Report `pass@1`, `pass@k`, and `pass^k`; for safety-sensitive work, consistency and all-attempt success matter as much as best-of-k.

### P1 — too many tasks are contract-completion questions

Static JSON answers are valuable when the target really is calculation or bounded interpretation. They should not dominate an agent benchmark. The next task wave should prioritize stateful but read-only workflows: plan-objective construction, dose/statistics extraction, structure normalization, QA trend investigation, DICOM integrity repair in a sandbox, secondary-check packets, and reproducible analysis notebooks.

### P1 — generic grader mutations are gated; authored adversarial cases remain incomplete

A reference solution passing proves feasibility, not grader completeness. Repository validation now
removes every required output field and applies a targeted failing mutation to every declared grader,
then verifies that the affected grader and overall task reject the result. The current public tree
executes 688 such deterministic probes. This catches permissive schema/grader wiring and protects the
mechanical release path, but it is not a substitute for task-specific authored near-misses,
unsafe-but-plausible outputs, alternate valid solutions, or leakage checks. Those richer cases remain
a promotion requirement for protected comparison releases.

### P1 — the frozen OpenKBP v0.6 limitations field is presence-graded, not meaning-graded

All ten v0.6 tasks require a non-empty `limitations` string, but their deterministic graders do not
check whether it contains the task-specific boundary stated in the authored reference. A fluent but
irrelevant sentence can therefore satisfy that field. This does not change the already frozen v0.6
outcome labels, and the released task or grader hashes must not be rewritten in place. The defect is
disclosed on the provisional release; v0.7 and later tasks that require a limitations field must add
an explicit deterministic semantic contract, authored negative cases, or a documented reason why the
field is reported but not score-bearing.

## Evidence-maturity levels

| Level | Required evidence | Permitted public language |
| --- | --- | --- |
| Public development | Public tasks, deterministic feasibility, immutable release | Development/regression evidence only |
| Public pilot | Repeated trials, declared families, complete attempt matrix | Provisional within-group comparison |
| Domain reviewed | Two independent qualified reviews per high-risk family; defects resolved | Expert-reviewed task set |
| Human baselined | Preregistered expert attempts, adjudication, uncertainty | Model-versus-sampled-human comparison for the declared task set |
| Protected comparison | Family-level holdout, canaries, audited execution, repeated trials | Contamination-resistant comparison for that frozen release |
| External replication | Independent operator and environment reproduce the result | Replicated benchmark result |

No level authorizes patient-specific use, clinical release, or autonomous treatment decisions.

## Promotion gates for the next comparison release

1. Holdout families are physically absent from public task, result, and website bundles.
2. Every task passes the repository-wide deterministic mutation gate and has authored near-miss,
   unsafe-plausible, alternate-valid-when-applicable, and leakage-review evidence.
3. D3/D4 and real-workflow tasks have two independent qualified reviewers.
4. Every submitted row has a complete declared attempt matrix and exact system description.
5. At least five attempts per task are collected for stochastic headline comparisons.
6. Family-aware uncertainty is reported when multiple views share a patient, case, machine, or source packet.
7. Passing protected trajectories undergo reward-hacking review.
8. A defect ledger, invalidation policy, and immutable regrade process are live before publication.
9. Human results are published only after the preregistered protocol and adjudication gates complete.
10. Claim language is checked against the evidence-maturity level and the research-only boundary.

## What should happen next

The highest-value sequence is:

1. operate a protected qualification lane;
2. finish independent review and a human-baseline pilot;
3. extend the machine-required mutation gate with authored, task-specific adversarial cases;
4. add stateful RT workflow tasks and broader independent families;
5. freeze pricing snapshots and publish cost per attempt and per safe success;
6. seek external replication.

Adding more public questions before these steps improves breadth but not benchmark defensibility.
