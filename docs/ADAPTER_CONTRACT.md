# Model adapter contract

An adapter is responsible for one bounded transformation: a sealed `RuntimeTask` becomes one
candidate output plus trace and provider metadata. It must not read `TaskSpec.grading`, provenance,
reference outputs, private files, or previous candidate outputs.

## Required behavior

1. Declare provider, model name and revision, harness name and revision.
2. Preserve the frozen system prompt and user-prompt construction for a common-harness run.
3. Apply the declared seed, temperature, token budget, timeout, and tool policy when supported.
4. Return exactly one JSON object matching the task schema. Do not repair or extract JSON from prose.
5. Record latency, usage, provider completion reason, and non-sensitive error evidence.
6. Turn provider failures into explicit error artifacts; never synthesize a fallback answer.
7. Keep native-agent evaluations in a separate track when the provider cannot honor the common harness.

## Qualification tests

- exact-object and duplicate-key parsing;
- timeout, authentication, unavailable-model, and malformed-response behavior;
- seed and parameter propagation;
- model/revision identity stability;
- no access to authored grading fields;
- error artifacts remain present in the expected attempt matrix;
- public sanitization removes reasoning/private provider fields without removing score evidence.

An adapter is not publication-ready until the qualification suite passes and one complete reference
release summarizes as rank-eligible.
