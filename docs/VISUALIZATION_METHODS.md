# Benchmark visualization methods

MedPhysBench treats plots as part of the evaluation contract, not as decorative
leaderboard graphics. Every plotted value is available in the release JSON and
every chart has a table or text fallback.

## Design references

The public site borrows four established benchmark conventions:

- [SWE-bench Verified](https://www.swebench.com/verified.html) separates benchmark
  versions and standardizes the harness for apples-to-apples model comparison.
  MedPhysBench therefore computes official ranks within identical provider/harness
  groups and keeps those ranks separate from a
  descriptive cross-surface outcome order.
- [MLPerf Inference](https://mlcommons.org/benchmarks/inference-datacenter/) reports
  performance subject to accuracy constraints and uses Pareto views rather than a
  single throughput number. MedPhysBench pairs safe success with token and wall-time
  cost and draws each frontier only within one official harness group.
- [METR's time-horizon work](https://metr.org/time-horizons/) makes uncertainty and
  fitted reliability visible rather than presenting a point estimate as exact.
  MedPhysBench leads with a direct-labeled interval plot and reports Wilson and
  family-cluster intervals where available.
- [Artificial Analysis](https://artificialanalysis.ai/leaderboards/models/) compares
  model quality with speed and price. MedPhysBench currently publishes provider-
  reported tokens and common-harness wall time; cost remains absent until a frozen,
  auditable pricing snapshot exists.

## Views and semantics

### Cross-release model index and evidence drilldown

The first results surface is a discovery index, not an ordinal leaderboard. It
joins every public model/release row to a versioned source-availability catalog,
then allows filtering by model name, provider, release, execution surface, and
open-weight versus closed-weight status. Provider and weight availability are
separate fields: a Groq-hosted Llama or gpt-oss run is still an open-weight model
served by a hosted provider.

GPT-5.6, Groq, and Ollama rows use the same table, release card, metrics, and
task-evidence component. Execution surface and official comparison-group rank
are row metadata rather than reasons to move a model into a separate visual
section. The index's `Best verified` value is recomputed only from a complete
task projection with explicit pass labels; a legacy release aggregate remains
visible inside its release card but cannot become that summary value. Even the
verified summary is navigation metadata, not a cross-release rank.

Each release card exposes outcome filters for safe passes, safe failures, unsafe
attempts, and legacy outcomes whose pass label cannot be reproduced. Search can
match task IDs, domains, failed lanes, and deterministic grader IDs. The public
drilldown contains provenance hashes and failure-contract identifiers, but not
raw model responses, hidden expected values, provider reasoning, or grader golds.
This follows HELM's prompt-level transparency principle while preserving the
sealed-task boundary required by MedPhysBench.

Explorer state is URL-backed. The selected release, source/provider filters,
execution surface, expanded model row, selected release card, and task-evidence
filters survive refresh and can be shared as a direct link for audit or review.

### Outcome interval plot

The primary plot is a horizontal dot-and-whisker view. The point is safe task
success and the whisker is its Wilson 95% interval. Models are direct-labeled.
Circles denote officially ranked harness-group rows; diamonds denote complete native-surface
rows. Native rows can receive a descriptive `outcome_rank`, but never an official
`rank` unless they satisfy the common-harness contract.

The point-estimate order is deliberately not a significance claim. Readers should
not infer an effort or model difference when intervals overlap, particularly in the
two-family OpenKBP pilot.

### Efficiency frontiers

Token and time views place safe task success on the vertical axis and resource use
on the horizontal axis. Higher and farther left is better. A frontier is drawn only
within each official harness group because native imports do not expose comparable
usage or inference-time telemetry. Provider token counts remain tokenizer-specific,
and no line connects Groq-hosted measurements to local Ollama measurements.

### Reliability profile

The reliability view shows safe success, all-attempt agreement, valid-output rate,
and safety-gate rate together. This prevents a high average from hiding unstable
repeated attempts or output-contract failures. Agreement is repeatability under the
declared settings, not evidence that seeded samples are statistically independent.

## Missingness and failure policy

- Missing token or latency telemetry is displayed as unavailable, never as zero.
- Unsupported required modalities are completed zero-score capability failures.
- Provider output-contract failures are completed zero-score model failures.
- Transient rate limits are retried with bounded, traced backoff and are not scored
  as model failures.
- Exhausted provider or transport failures remain visible error attempts and make a
  campaign ineligible for official ranking.
- Incomplete, duplicate, hash-drifted, or regrade-inconsistent rows are omitted from
  the descriptive outcome order.

These rules prevent a model from improving its apparent position by declining hard
tasks, omitting telemetry, or producing a run matrix that cannot be regraded.
