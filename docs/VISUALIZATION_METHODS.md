# Benchmark visualization methods

MedPhysBench treats plots as part of the evaluation contract, not as decorative
leaderboard graphics. Every plotted value is available in the release JSON and
every chart has a table or text fallback.

## Design references

The public site borrows established benchmark conventions while keeping MedPhysBench's
comparability boundary explicit:

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
- [HELM](https://crfm-helm.readthedocs.io/en/v0.5.15/) combines a unified provider-facing
  leaderboard with prompt/response inspection. MedPhysBench likewise keeps providers on one
  evidence surface and makes the individual task/attempt record the unit of audit.
- [LiveBench](https://github.com/livebench/livebench) publishes task/category breakdowns,
  refreshed releases, and confidence intervals while targeting questions that avoid immediate
  frontier saturation. MedPhysBench uses the same motivation for versioned releases, protected
  holdouts, direct interval display, and retirement review.

## Views and semantics

### Frozen fleet qualification funnel

The fleet view uses one constant denominator: the 50 unique base model IDs frozen before
additional score inspection. It separately reports access-qualified, evaluated, and rankable
counts. Effort settings, provider routes, and aliases remain visible system configurations but do
not inflate fleet breadth. The underlying `fleet_status.json` is deterministically rebuilt from the
frozen fleet manifest, model catalog, access ledger, and all public release projections.

Each exact planned base ID is inspectable with open-weight/closed, steward, modality, and
qualification filters. A local probe that stops at 18/30 attempts can advance access evidence but
cannot produce a published score, evaluated count, or rank. This follows the same missingness-first
principle used by HELM and the completion gates used by execution benchmarks: coverage is itself a
reported result.

### Cross-release model index and evidence drilldown

The first results surface is a discovery index, not an ordinal leaderboard. It defaults to the
currently selected release; an explicit all-release mode exists for evidence discovery and never
creates a cross-release rank. It
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
raw provider responses, hidden expected values, provider reasoning, or grader
golds. A release must explicitly declare `public_attempt_detail:
sanitized_output` before the reporter can expose task answers, and that policy is
rejected for any non-public access class. Eligible public-development releases
include only schema-declared answer fields, per-attempt score, wall time, token
counts, reduced deterministic grader verdicts without gold-bearing evidence, and
a redacted provider/runtime receipt. Comparison-profile releases cannot opt in,
even when their task contracts are public. Aggregate-only is the default. Exact model,
harness, and run-configuration revisions are shown beside the attempt evidence.
When a cataloged route publishes artifact-build provenance, the same run contract also labels the
build class, quantization, immutable source revision, and source record. Community quantizations are
therefore visible as system attributes rather than being styled or counted as separate base models.
This follows HELM's prompt-level
transparency principle while preserving the sealed-task boundary required by
MedPhysBench.

Expanding a base model opens a cross-run workbench on the same presentation surface for every
provider and model family. It keeps each exact release, harness, revision, configuration hash, and
execution surface separate; summarizes safe passes, safe failures, unsafe outcomes, capability
unavailability, and missing legacy labels; then projects failures by domain, scoring lane,
deterministic grader, and task family. Compact visible identifiers retain their exact values as
accessible metadata. This lets a reader move from a headline score to the repeated family-level
failure pattern without treating two different harness contracts as interchangeable.

Explorer state is URL-backed. The selected release, source/provider filters,
execution surface, expanded model row, selected release card, forensic run set,
domain, outcome, and selected task survive refresh and can be shared as a direct
link for audit or review.

Results scope is global rather than component-local. The default `All published evidence` state
keeps GPT-5.6, Groq, Ollama, and all other published rows available across score, efficiency,
capability, and forensics views. `Official comparison only` applies the same restriction to every
view and persists as `results_scope=official`; controls that would broaden one component while the
global scope is official are disabled. The unified default is a discovery and diagnostic surface,
not a cross-contract ordinal leaderboard.

Selecting any attempt also opens a task-first comparison table across every run set
surviving the active openness and provider filters. It reports attempts, safe-success
rate, outcome mix, top failed grader, and execution-surface label, then switches directly
into that model's matched evidence. The table is descriptive across surfaces and never
creates an official cross-surface rank. Provider choices remain discoverable when the
selected release has zero matching rows, producing an explicit empty state instead of a
silent filter reset. Plot controls repeat the frozen-panel denominator (`evaluated/50`)
so visible configuration counts cannot be mistaken for unique evaluated base-model breadth.

The attempt-forensics surface also includes a horizontally scrollable model-by-task fingerprint
matrix. Columns are exact task views ordered by observed difficulty, rows are exact run sets, and
each cell exposes the safe-pass fraction plus unsafe, unavailable, safe-failure, or inconclusive
counts. Selecting a cell opens its highest-severity attempt. The matrix labels every execution
surface and explicitly warns that correlated task views are not independent patients or cases; it is
a diagnostic heatmap table, never a cross-harness rank.

### Unified outcome interval plot

The default plot is a horizontal dot-and-whisker view showing a bounded, high-signal slice of the
rows surviving the same release/source/provider/surface filters. An explicit show-all control
restores every surviving row, and the adjacent evidence table retains the complete filtered data
behind its own progressive-disclosure control. This reduces label collision without changing the
release JSON, deleting low-scoring rows, or silently sampling the evidence. A URL-backed comparison-
contract filter can restrict the view to an identical provider, harness revision, adapter-settings
hash, sampling contract, and seed policy; cross-contract views remain descriptive. The point is
safe task success and the whisker is
the release's primary 95% interval: family-cluster where declared, otherwise Wilson. Models are
direct-labeled. Filled circles denote officially ranked common-harness rows, hollow circles denote
visible but unranked common-harness rows, and diamonds denote complete native-surface rows. GPT-5.6,
Groq, and Ollama therefore share one score axis. Shape and row annotations communicate execution
comparability; provider or model family never creates a separate visual leaderboard. Native rows
can receive a descriptive `outcome_rank`, but never an official `rank` unless they satisfy the
common-harness contract.

The point-estimate order is deliberately not a significance claim. Readers should
not infer an effort or model difference when intervals overlap, particularly in the
two-family OpenKBP pilot.

Exact ties on safe success, task success, and safety-gate rate share a competition
rank (`1, 1, 3`). Names determine display order only. Overlapping intervals do not
automatically create a tie because that would require a declared inferential procedure.

### Efficiency frontiers

Token and time views place safe task success on the vertical axis and resource use
on the horizontal axis. Higher and farther left is better. A frontier is drawn only
within each official harness group because native imports do not expose comparable
usage or inference-time telemetry. Provider token counts remain tokenizer-specific,
and no line connects Groq-hosted measurements to local Ollama measurements.
The evidence table exposes median input, output, and total tokens separately and allows sorting by
total tokens or median wall time. Missing telemetry stays explicit and sorts after observed values;
it is never coerced to zero. TTFT and post-first-token throughput remain absent until every compared
surface supplies those timestamp semantics under a frozen contract. This follows Artificial
Analysis's separation of TTFT, output speed, and end-to-end response time rather than deriving them
from one aggregate duration field.

The default score chart shows at most 14 directly labeled rows and the dense evidence table shows
at most 16. Both state the number displayed and provide an explicit show-all action. These are
presentation limits only: filtered rows remain addressable, downloadable, and available through the
public JSON contract.

MedPhysBench does not publish a single composite capability/efficiency index. A weighted index would
hide value judgments about medical-physics domain importance, safety, latency, cost, and missing
telemetry unless its weights, version policy, and sensitivity analysis were frozen first. The site
instead keeps score, reliability, time, and tokens as linked but separable views.

### Reliability profile

The reliability view shows safe success, all-attempt agreement, valid-output rate,
and safety-gate rate together. This prevents a high average from hiding unstable
repeated attempts or output-contract failures. Agreement is repeatability under the
declared settings, not evidence that seeded samples are statistically independent.

## Missingness and failure policy

- Missing token or latency telemetry is displayed as unavailable, never as zero.
- Unsupported required modalities are completed zero-score capability failures and
  appear as `capability unavailable`, not `unsafe`, because no model action occurred.
  They remain in the overall task-success denominator but are excluded from the
  provider-call safety and telemetry denominators; both denominator counts are
  published beside the rates.
- Provider output-contract failures are completed zero-score model failures.
- Transient rate limits are retried with bounded, traced backoff and are not scored
  as model failures.
- Exhausted provider or transport failures remain visible error attempts and make a
  campaign ineligible for official ranking.
- Incomplete, duplicate, hash-drifted, or regrade-inconsistent rows are omitted from
  the descriptive outcome order.

These rules prevent a model from improving its apparent position by declining hard
tasks, omitting telemetry, or producing a run matrix that cannot be regraded.
