# MedPhysBench Results

## Public development release

Release `public-dev-2026-07-31` was scored on Friday, July 31, 2026 against 16 public synthetic
medical-physics tasks. The published table below includes the 11 locally reachable Ollama models
that completed scored attempts. Retired or blocked cloud handles are documented separately in
[`web/public/data/access_status.json`](../web/public/data/access_status.json).

The headline metric is `safe_success_rate`: the fraction of attempts that both solved the task
and cleared the critical safety gate.

| Rank | Model | Safe success | Task success | Critical unsafe rate | Valid output |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | `qwen3:14b` | 50.0% | 50.0% | 6.25% | 100.0% |
| 2 | `deepseek-r1:1.5b` | 43.75% | 43.75% | 6.25% | 100.0% |
| 3 | `qwen2.5:7b-instruct` | 43.75% | 43.75% | 6.25% | 100.0% |
| 4 | `qwen3:8b` | 43.75% | 43.75% | 6.25% | 100.0% |
| 5 | `qwen3.5:4b` | 37.5% | 37.5% | 0.0% | 100.0% |
| 6 | `llama3.1:8b` | 31.25% | 31.25% | 6.25% | 100.0% |
| 7 | `llama3.2:3b` | 25.0% | 25.0% | 12.5% | 100.0% |
| 8 | `gemma3:4b` | 12.5% | 12.5% | 6.25% | 100.0% |
| 9 | `qwen3:1.7b` | 12.5% | 12.5% | 18.75% | 100.0% |
| 10 | `qwen2.5vl:3b` | 0.0% | 0.0% | 6.25% | 100.0% |
| 11 | `qwen3-vl:8b` | 0.0% | 0.0% | 100.0% | 0.0% |

## Reading the first leaderboard

- The strongest scored model in this release was `qwen3:14b`, but even it solved only half of
  the suite safely.
- `deepseek-r1:1.5b`, `qwen2.5:7b-instruct`, and `qwen3:8b` formed a tight second tier at
  `43.75%` safe success.
- The biggest separation was not output validity. Most text models produced schema-valid JSON
  nearly all the time. The losses came from exact numeric mistakes, set-matching mistakes,
  and escalation-boundary failures.
- Tier 3 escalation remained brittle. `public.rt.plan-release-boundary-001` produced the clearest
  unsafe failures across multiple models.
- The two vision-capable models performed poorly in text-only mode. `qwen3-vl:8b` was especially
  misaligned for this harness and failed every task unsafely.

## Top-model failure profile

The highest-ranked model, `qwen3:14b`, still failed 8 of 16 tasks. Its misses were concentrated in:

- synthetic brachytherapy decay arithmetic
- synthetic FDG decay correction arithmetic
- barrier transmission arithmetic
- DICOM direct-identifier set selection
- refusal/escalation with missing QA baseline context
- confidence-interval interpretation without overclaiming
- synthetic EQD2 arithmetic
- the patient-specific plan release boundary task, which was the only unsafe miss in its run

## Access status on July 31, 2026

These handles were checked live on Friday, July 31, 2026 and were not included in the ranked table:

- `qwen3.5:397b-cloud`: blocked by Ollama Cloud weekly usage limit (`HTTP 429`)
- `kimi-k2.5:cloud`: Ollama reported this model retired on **July 31, 2026**
- `kimi-k2-thinking:cloud`: Ollama reported this model retired on **June 16, 2026**
- `minimax-m2.1:cloud`: Ollama reported this model retired on **July 15, 2026**

## Important boundary

These results come from a public synthetic development suite. They are useful for harness
verification, early model comparison, and task-design iteration. They are not a substitute for
sealed test sets, blinded SME adjudication, institutional shadow evaluation, or any claim of
clinical readiness.
