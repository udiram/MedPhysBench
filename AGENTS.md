# MedPhys-AgentBench contributor rules

## Non-negotiable scope

- This repository is a research and evaluation platform, not a clinical decision-support system.
- Do not add patient-identifiable data, clinical credentials, vendor screenshots, confidential manuals, or hidden test labels to the repository.
- Never wire a task to a live treatment-planning, treatment-delivery, imaging, or clinical-record system.
- New high-risk task ideas must first be expressed as a read-only, synthetic, or shadow-evaluation scenario.

## Benchmark integrity

- Preserve immutable task, grader, prompt, tool, and model manifests for every scored run.
- Keep development, validation, hidden test, restricted shadow, and canary data physically separated.
- Do not use evaluation labels, historical ground truth, or task metadata as runtime agent context unless explicitly declared by the track.
- Add a reference solution and automated feasibility test for every new task.
- Use deterministic graders wherever a valid deterministic check exists; document why an LLM or human grader is required.

## Engineering practices

- Keep task contracts backward compatible or publish a new schema version.
- Do not make task success depend on a particular hidden chain of thought or exact tool sequence.
- Use isolated sandboxes with explicit tool allowlists and bounded resources.
- Treat a model-provider alias as mutable: persist the provider, exact model identifier, request date, settings, and response metadata.
