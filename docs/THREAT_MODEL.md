# Benchmark integrity threat model

## Protected claims and assets

The system protects four things: sealed grading material, the exact candidate-visible contract,
the one-to-one mapping between attempts and expected tasks, and the evidence chain supporting a
published score. Clinical systems and patient care are explicitly outside this benchmark runtime.

## Adversaries

- A candidate system trying to infer or access gold labels.
- A submitter selecting, deleting, duplicating, or editing attempts to inflate a score.
- A provider response exploiting permissive parsing or numeric edge cases.
- An accidental release process mixing model revisions, harnesses, tasks, or stale artifacts.
- A benchmark author unintentionally leaking labels through runtime fields or fixtures.

## Controls

| Attack | Control | Residual risk |
| --- | --- | --- |
| Read grading/provenance in the sandbox | Explicit `RuntimeTask` projection and leakage tests | Prompt/context may still contain an authoring mistake |
| Hide failed tasks | Expected task/attempt matrix; incomplete rows are unranked | Release manifest itself may be under-scoped |
| Duplicate successful attempts | Unique `(task_id, attempt_index)` and run-ID checks | Collusion outside the published artifact chain |
| Edit `passed`, `safe`, or grades | Summary-time deterministic regrading from output | Compromised grader code or task labels |
| Exploit parser repair | Exact-object JSON decoder; reject fences, trailing text, duplicate keys, NaN/Infinity | Provider APIs may transform content before receipt |
| Mix model/harness revisions | Manifest consistency checks | Providers may serve mutable weights behind one name |
| Mix sampling or sandbox configurations | Run-set configuration consistency checks | Some provider-side settings may be undisclosed |
| Change prompts or tools | Prompt/tool/runtime/system hashes | Legacy artifacts have fewer hash fields |
| Rank a complete matrix of provider failures | Completed-attempt eligibility rule; error rows remain unranked | Availability remains a time-specific observation |
| Average away an unsafe act | Critical safety gate and separate unsafe-action rate | Incorrectly authored severity remains possible |
| Publish hidden reasoning | Public artifact sanitizer and CI check | New provider fields require sanitizer maintenance |
| Ship malformed evidence | Repository-wide schema validation for tasks, runtime projections, manifests, and results | JSON Schema cannot prove semantic correctness |
| Leak evaluator host paths | Public summaries emit repository-relative task paths; regression test rejects absolutes | Free-form provider errors still require review |

## Required response

An integrity failure makes a model row unrankable; it is not converted into a low-confidence rank.
A task-label or leakage defect requires withdrawing the affected release or publishing a new
release ID. Historical artifacts remain available with a clear correction notice.
