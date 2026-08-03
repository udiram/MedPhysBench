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

When a provider returns an HTTP response that explicitly rejects generated structured output, the
attempt is a completed model/output-contract failure rather than a transport retry. Persist only a
redacted receipt: provider/model identity, status and error code, response-body SHA-256, measured
wall time, and a provider request ID when supplied. Never retain the rejected generation in public
artifacts and never invent token usage that the provider did not return. A complete matrix with
missing usage telemetry remains inspectable but cannot pass the current common-harness publication
gate. A trustworthy provider-reported total token count satisfies that gate; prompt and completion
splits remain unavailable unless the provider reports them, and the benchmark never estimates either
split from a total.

Recorded native surfaces must use `recorded-batch.v2` for new public evidence. The capture binds the
exact sealed batch, model revision, effort, attempt, output digest, fresh-context timestamps, and
declared transport-only tools. The recorded adapter writes the capture ID into every result trace and
raw-response receipt, declares `live_provider_request=false`, and leaves latency and token usage
unavailable. A valid capture improves provenance; it does not satisfy common-harness qualification.

## Qualification tests

- exact-object and duplicate-key parsing;
- timeout, authentication, unavailable-model, and malformed-response behavior;
- seed and parameter propagation;
- model/revision identity stability;
- no access to authored grading fields;
- error artifacts remain present in the expected attempt matrix;
- public sanitization removes reasoning/private provider fields without removing score evidence.
- output-contract rejections preserve a body digest and timing receipt without the rejected text.

An adapter is not publication-ready until the qualification suite passes and one complete reference
release summarizes as rank-eligible.
