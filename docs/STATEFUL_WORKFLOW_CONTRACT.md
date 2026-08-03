# Stateful workflow promotion contract

**Status:** receipt schema and validator implemented; task/run/submission integration pending; no currently published score satisfies this gate
**Scope:** read-only or synthetic research sandboxes; never a live clinical system

## Current evidence boundary

The published OpenKBP v0.6 lane contains real-data **workflow views**, not
stateful agent executions. Each task presents a bounded input and accepts one
structured response. The current harness does not yet prove that a model
changed a sandbox from a known initial state into a correct final state.

Accordingly, current rows may support claims about bounded interpretation,
artifact construction, deterministic grading, and safe escalation under the
declared one-response contract. They may not be described as end-to-end agent
workflow completion, autonomous planning, or clinical system operation.

This distinction follows the broader lesson from agent and software
benchmarks: a plausible final answer is not equivalent to a verified
environment state. [AgentBench](https://arxiv.org/abs/2308.03688) evaluates
agents in interactive environments; [SWE-bench Verified](https://openai.com/index/introducing-swe-bench-verified/)
adds professional task review; and the [SWE-bench Pro audit](https://openai.com/index/separating-signal-from-noise-coding-evaluations/)
shows why executable tests still need item-level validity review.

## Version boundary

Stateful work will use new contract versions rather than silently widening
`medeval.task.v1` or `medeval.run.v2`.

| Contract | Required addition | Purpose |
| --- | --- | --- |
| `medeval.task.v2` | `execution_kind` and authored `workflow_contract` | Distinguish one-response tasks from stateful sandbox work |
| `medeval.runtime-task.v2` | runtime-safe workflow policy, without gold or grader data | Give the agent only the state and actions it is allowed to use |
| `medeval.run.v3` | `execution_kind`, `initial_state_hash`, `workflow_contract_hash` | Bind a run before execution starts |
| `medphysbench.workflow-receipt.v1` | trajectory and final-state evidence | Prove what happened and what the grader inspected |
| `medphysbench.common-harness-submission.v2` | paired result and workflow-receipt inventory | Prevent receipt-free stateful submissions |
| `medphysbench.review-evidence.v2` | workflow-promotion review fields | Keep anti-gaming and expert-review evidence visible |

Historical v1/v2 one-response tasks and results remain valid under their
original contract. They are never retroactively relabeled as stateful.

## Authored workflow contract

A stateful task must declare all of the following before a runner can start:

- an immutable initial-state manifest and digest;
- read-only input mounts and explicit writable roots;
- a typed tool allowlist and resource budget;
- required final artifacts and their schemas;
- termination conditions and a maximum step count;
- full trajectory retention for scored attempts;
- final-state grading as a required pass gate;
- at least one task-specific exploit or plausible near-miss test.

The candidate sees the runtime-safe subset. Gold state, hidden expected values,
grader code, exploit fixtures, and alternative outputs remain outside the
sandbox.

## Per-attempt workflow receipt

Every scored stateful attempt must produce a sidecar receipt bound to the exact
result artifact. At minimum it records:

```json
{
  "schema_version": "medphysbench.workflow-receipt.v1",
  "run_id": "run_20260803_0001",
  "task_id": "tg263-rename-case-01",
  "attempt_index": 0,
  "initial_state_hash": "1111111111111111111111111111111111111111111111111111111111111111",
  "workflow_contract_hash": "2222222222222222222222222222222222222222222222222222222222222222",
  "tools_observed": [
    {"tool_name": "planner.inspect", "tool_kind": "structured_io", "call_count": 2},
    {"tool_name": "planner.write_objectives", "tool_kind": "transform", "call_count": 1}
  ],
  "trajectory_summary": {
    "step_count": 7,
    "assistant_turns": 3,
    "tool_call_count": 4,
    "terminal_state": "completed"
  },
  "trajectory_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
  "final_state_tree_sha256": "4444444444444444444444444444444444444444444444444444444444444444",
  "output_artifacts": [
    {"path": "metrics.json", "sha256": "5555555555555555555555555555555555555555555555555555555555555555", "bytes": 1024}
  ],
  "grader_inputs_complete": true
}
```

The public projection may publish hashes, counts, and reduced verdicts. It must
not expose hidden grader inputs, private trajectories, credentials, PHI, or
reward-hacking details.

## Hard rank-eligibility gates

A stateful attempt is invalid and unrankable if any of these checks fail:

1. The initial-state or workflow-contract hash differs from the frozen run
   manifest.
2. The receipt is missing, duplicated, or not cryptographically bound to the
   result.
3. An observed tool or writable path is outside the authored allowlist.
4. A required final artifact is missing or its hash differs from the receipt.
5. The required final-state grader did not inspect the recorded final state.
6. The trajectory is incomplete, exceeds the step budget, or contains a
   forbidden action.
7. Repository validation cannot demonstrate a passing reference execution and
   a failing exploit/near-miss execution.

An output-only grader can supplement these checks, but it can never be the sole
pass condition for a stateful task.

## Release promotion gate

A release containing stateful tasks cannot use a comparison maturity label
until all of the following are machine-checkable and complete:

- every stateful attempt has a valid workflow receipt;
- final-state graders and authored exploit tests pass;
- protected passing traces receive the declared review treatment;
- two independent qualified domain reviewers approve each high-risk family;
- data-rights/PHI review is documented;
- a human baseline or an explicit no-human-comparison claim is published;
- a protected family-level holdout is operating;
- at least one independent replication is published or explicitly shown as
  missing in the release evidence index.

The first implementation target is a synthetic or publication-cleared,
read-only RT planning sandbox following [PLANNING_SANDBOX.md](PLANNING_SANDBOX.md).
Nothing in this contract permits connection to a clinical TPS, treatment
management system, record-and-verify system, or delivery machine.
