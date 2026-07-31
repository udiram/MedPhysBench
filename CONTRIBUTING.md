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

## Pull requests

Keep changes scoped. Include the exact validation commands and results. Never commit credentials,
PHI, restricted task labels, or model-provider response data whose terms prohibit redistribution.

By contributing, you agree that code contributions are licensed under MIT and public task content
under the license declared in each task pack.
