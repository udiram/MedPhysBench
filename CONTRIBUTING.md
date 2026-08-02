# Contributing to MedPhysBench

MedPhysBench welcomes code, documentation, adapter, and task contributions. Task contributions have
a higher evidence bar because they affect scientific claims.

## Development

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
uv run medphys-bench validate-release releases/public_dev_2026_07_31.yaml

cd web
npm install
npm run build
npm audit --omit=dev
```

## Task proposal requirements

A proposal must include:

- domain, track, intended competency, and risk tier;
- why the task represents authentic medical-physics work;
- data/source provenance and redistribution rights;
- a runtime-visible task view with no gold leakage;
- strict output or final-state acceptance criteria;
- a reference result that passes every grader;
- expected escalation behavior and prohibited actions;
- PHI/privacy review;
- contamination and ambiguity analysis;
- a long-term owner.

Before inclusion in a scored release, a task requires two independent domain-expert reviews,
reference execution, grader mutation testing, and leakage review.

## Result submission requirements

Do not submit a hand-authored leaderboard row. Submit the complete, unfiltered common-harness
artifact directory plus a v1 submission manifest. The manifest binds every file by SHA-256 and
byte length, the canonical artifact-tree hash, frozen release contract, exact base-model mapping,
model revision, source commits, execution window, environment, budget, and explicit attestations.

Build a manifest only after the 30-attempt matrix is complete and deterministic regrading succeeds:

```bash
uv run python scripts/common_harness_submission.py build \
  --release-file releases/public_real_workflows_pilot_v0_6.yaml \
  --results-directory results/releases/public-real-workflows-pilot-v0.6/MODEL_DIRECTORY \
  --submission-id UNIQUE_SUBMISSION_ID \
  --submission-kind external_reproduction \
  --submitter-name "YOUR NAME" \
  --affiliation "YOUR AFFILIATION" \
  --hardware-summary "CPU, RAM, GPU, and execution limits" \
  --funding provider_free_tier \
  --runtime-version provider=EXACT_VERSION \
  --output submissions/UNIQUE_SUBMISSION_ID.json \
  --attest

uv run python scripts/common_harness_submission.py validate \
  submissions/UNIQUE_SUBMISSION_ID.json
```

The validator rejects missing or extra artifacts, byte or hash changes, path traversal, false or
missing attestations, unknown commits, release-contract drift, model-catalog mismatches, incomplete
attempt sets, deterministic regrade drift, missing execution traces, missing provider receipts,
and missing per-call token or duration telemetry. Explicit unsupported-modality preflight outcomes
remain valid scored capability failures and do not pretend a provider call occurred. A manifest
makes a submission auditable; it is not a cryptographic proof that a third party did not fabricate
all files. Frontier claims still require a managed runner or independently signed provider receipts.

## Pull requests

Keep changes scoped. Include the exact validation commands and results. Never commit credentials,
PHI, restricted task labels, or model-provider response data whose terms prohibit redistribution.

By contributing, you agree that code contributions are licensed under MIT and public task content
under the license declared in each task pack.
