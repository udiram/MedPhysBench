import { ChevronDown, ExternalLink } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { REPO_URL } from "../content";
import { buildSpotlightSelection } from "../lib/evidenceSpotlight";
import { formatDuration, formatPercent, formatTokens, normalizeModelDisplayName, providerLabel, shortHash } from "../lib/format";
import { taskAttemptKey } from "../lib/forensicsNavigation";
import { taskReviewFor, taskReviewLabel } from "../lib/taskReview";
import type { Leaderboard, ModelTaskResult, ReleaseEvidence, ReviewEvidence } from "../types";

type Props = {
  data: Leaderboard | null;
  releaseEvidence: ReleaseEvidence | null;
  reviewEvidence: ReviewEvidence | null;
};

export function EvidenceSpotlight({ data, releaseEvidence, reviewEvidence }: Props) {
  const [modelKey, setModelKey] = useState("");
  const [taskId, setTaskId] = useState("");
  const selection = useMemo(
    () => buildSpotlightSelection(data, modelKey, taskId),
    [data, modelKey, taskId],
  );

  useEffect(() => {
    if (selection.selected && selection.selected.key !== modelKey) {
      setModelKey(selection.selected.key);
    }
  }, [modelKey, selection.selected]);

  useEffect(() => {
    const nextTaskId = selection.selectedAttempt?.task.task_id ?? "";
    if (nextTaskId && nextTaskId !== taskId) setTaskId(nextTaskId);
  }, [selection.selectedAttempt, taskId]);

  const selectedTask = selection.selectedAttempt?.task ?? null;
  const human = releaseEvidence?.evidence.human_baseline ?? null;
  const review = taskReviewFor(reviewEvidence, selectedTask?.task_id);
  const publicOutputs = data?.release.public_attempt_detail === "sanitized_output";

  return (
    <section className="spotlight-section" aria-labelledby="spotlight-title">
      <div className="spotlight-heading">
        <div>
          <h2 id="spotlight-title">One task, three points of reference</h2>
          <p>
            Pick a published model and inspect one exact attempt beside the strongest verified peer run under the same
            frozen harness. Human evidence stays blank until qualified participants complete the matched study.
          </p>
        </div>
        <a className="text-link" href="/explore">
          Explore every attempt <span aria-hidden="true">→</span>
        </a>
      </div>

      <div className="spotlight-controls" aria-label="Featured comparison controls">
        <label className="field">
          <span>Model run</span>
          <span className="select-wrap">
            <select
              aria-label="Select a verified model run"
              value={selection.selected?.key ?? ""}
              onChange={(event) => {
                setModelKey(event.target.value);
                setTaskId("");
              }}
            >
              {selection.runs.map((run) => (
                <option key={run.key} value={run.key}>
                  {runOptionLabel(run.row)}
                </option>
              ))}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
        <label className="field spotlight-task-field">
          <span>Task</span>
          <span className="select-wrap">
            <select
              aria-label="Select a benchmark task"
              value={selectedTask?.task_id ?? ""}
              onChange={(event) => setTaskId(event.target.value)}
            >
              {selection.taskIds.map((id) => (
                <option key={id} value={id}>
                  {taskTitle(selection.selected?.row.tasks ?? [], id)}
                </option>
              ))}
            </select>
            <ChevronDown aria-hidden="true" />
          </span>
        </label>
      </div>

      {!selection.selected || !selectedTask ? (
        <div className="spotlight-empty" role="status">
          Loading verified attempt evidence…
        </div>
      ) : (
        <>
          <header className="task-brief">
            <div>
              <p>{selection.taskTitle}</p>
              <span>{selectedTask.task_id}</span>
            </div>
            <div className="task-validation">
              <strong>{taskReviewLabel(review)}</strong>
              <span>{review ? "Automated reference feasibility recorded" : "Review ledger did not match this task"}</span>
            </div>
          </header>

          <div className="evidence-ledger">
            <AttemptColumn
              label="Selected model"
              modelName={selection.selected.row.model_name}
              provider={selection.selected.row.provider}
              task={selectedTask}
              publicOutput={publicOutputs}
              releaseId={data?.release.release_id ?? null}
              runKey={selection.selected.key}
            />
            {selection.bestPeer && selection.bestPeerAttempt ? (
              <AttemptColumn
                label="Best controlled peer"
                modelName={selection.bestPeer.row.model_name}
                provider={selection.bestPeer.row.provider}
                task={selection.bestPeerAttempt.task}
                publicOutput={publicOutputs}
                releaseId={data?.release.release_id ?? null}
                runKey={selection.bestPeer.key}
                aggregate={`${formatPercent(selection.bestPeerSafeSuccessRate)} across matched attempts`}
              />
            ) : (
              <section className="ledger-column ledger-unavailable" aria-label="Best controlled peer unavailable">
                <p className="ledger-label">Best controlled peer</p>
                <h3>No valid peer for this run</h3>
                <p>
                  This model has no other verified run with the same comparison group, harness revision, and exact
                  attempt contract. A cross-contract rank is not inferred.
                </p>
                {selection.bestPeerSafeSuccessRate != null ? (
                  <p>Aggregate peer evidence exists, but an exact paired attempt could not be matched.</p>
                ) : null}
              </section>
            )}
            <section className="ledger-column human-column" aria-label="Best verified human result">
              <p className="ledger-label">Best verified human</p>
              <h3>Coming soon</h3>
              <p>
                {human
                  ? `${human.status === "recruiting" ? "Recruiting" : human.status.replaceAll("_", " ")} · ${human.completed}/${human.target ?? "—"} release-matched participants`
                  : "Human-baseline evidence is unavailable."}
              </p>
              <p>
                No reviewed task-level human response is published. Aggregate participation alone is not enough;
                reference solutions prove feasibility and are never substituted for human performance.
              </p>
              <a className="text-link" href="/humans">
                Human benchmark and eligibility <span aria-hidden="true">→</span>
              </a>
            </section>
          </div>
        </>
      )}
    </section>
  );
}

type AttemptColumnProps = {
  aggregate?: string;
  label: string;
  modelName: string;
  provider: string;
  publicOutput: boolean;
  releaseId: string | null;
  runKey: string;
  task: ModelTaskResult;
};

function AttemptColumn({ aggregate, label, modelName, provider, publicOutput, releaseId, runKey, task }: AttemptColumnProps) {
  const passed = task.outcome_category === "safe_success";
  const requiredGraders = task.grader_results?.filter((grader) => grader.required_for_pass) ?? [];
  const decisiveGrader = requiredGraders.find((grader) => !grader.passed) ?? null;
  const inspectHref = forensicsHref(releaseId, runKey, task);

  return (
    <section className="ledger-column" aria-label={`${label}: ${normalizeModelDisplayName(modelName)}`}>
      <p className="ledger-label">{label}</p>
      <h3>{normalizeModelDisplayName(modelName)}</h3>
      <p className="ledger-provider">{providerLabel(provider)} · attempt {(task.attempt_index ?? 0) + 1}</p>
      <div className="ledger-outcome">
        <strong className={passed ? "outcome-good" : task.safe === false ? "outcome-bad" : "outcome-warn"}>
          {outcomeLabel(task)}
        </strong>
        <span>{task.score == null ? "Score unavailable" : `${Math.round(task.score * 100)}% attempt score`}</span>
      </div>
      {aggregate ? <p className="ledger-aggregate">{aggregate}</p> : null}
      {publicOutput ? <OutputFields output={task.output} /> : <p>Structured output is not public for this release.</p>}
      <div className="grader-verdict">
        <strong>{decisiveGrader ? humanizeGrader(decisiveGrader.grader_id) : "All required checks passed"}</strong>
        <p>
          {decisiveGrader?.rationale
            ?? (requiredGraders.length ? `${requiredGraders.length}/${requiredGraders.length} required deterministic checks passed.` : "No deterministic grader rationale is published.")}
        </p>
      </div>
      <dl className="attempt-telemetry">
        <div>
          <dt>Time</dt>
          <dd>{task.capability_failure && task.duration_seconds === 0 ? "No model call" : formatDuration(task.duration_seconds)}</dd>
        </div>
        <div>
          <dt>Tokens</dt>
          <dd>{task.token_usage?.available ? formatTokens(task.token_usage.total_tokens) : "Unavailable"}</dd>
        </div>
      </dl>
      <a className="text-link" href={inspectHref}>
        Inspect exact attempt <span aria-hidden="true">→</span>
      </a>
    </section>
  );
}

function OutputFields({ output }: { output: Record<string, unknown> | undefined }) {
  if (!output || !Object.keys(output).length) return <p>No structured output was recorded.</p>;
  return (
    <dl className="output-fields">
      {Object.entries(output).slice(0, 6).map(([key, value]) => (
        <div key={key}>
          <dt>{key.replaceAll("_", " ")}</dt>
          <dd>{displayValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function displayValue(value: unknown) {
  if (Array.isArray(value)) return value.length ? value.map((item) => Array.isArray(item) ? item.join(", ") : String(item)).join(" · ") : "None";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value == null) return "Unavailable";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function outcomeLabel(task: ModelTaskResult) {
  if (task.capability_failure) return "Capability unavailable";
  if (task.outcome_category === "safe_success") return "Safe success";
  if (task.outcome_category === "safe_failure") return "Safe failure";
  if (task.outcome_category === "unsafe") return "Unsafe";
  return "Inconclusive";
}

function humanizeGrader(value: string | undefined) {
  if (!value) return "Required check failed";
  return `Failed: ${value.split(".").at(-1)?.replaceAll("_", " ") ?? value}`;
}

function taskTitle(tasks: readonly ModelTaskResult[], taskId: string) {
  return tasks.find((task) => task.task_id === taskId)?.title ?? taskId;
}

function runOptionLabel(row: import("../types").ModelResult) {
  const evidence = row.ranking_eligible ? "official" : "descriptive";
  const configuration = row.run_profile?.run_configuration_hash ?? row.comparison_group ?? row.model_revision;
  return `${normalizeModelDisplayName(row.model_name)} · ${providerLabel(row.provider)} · ${evidence} · ${shortHash(configuration)}`;
}

function forensicsHref(releaseId: string | null, runKey: string, task: ModelTaskResult) {
  const params = new URLSearchParams();
  if (releaseId === "public-core-v0.4") params.set("release", "core");
  else if (releaseId === "public-imaging-pilot-v0.4") params.set("release", "imaging");
  else if (releaseId === "public-tg263-pilot-v0.5") params.set("release", "tg263");
  params.set("fx_model", runKey);
  params.set("fx_task", taskAttemptKey(task));
  return `/explore?${params.toString()}#forensics`;
}

export function EvidenceSpotlightSources() {
  return (
    <p className="spotlight-source-note">
      Evidence comes from immutable public result artifacts. The OpenKBP reference dose is a standardized synthetic
      clinical-quality plan; this is an offline research fixture, not a clinical case review. {" "}
      <a href={`${REPO_URL}/blob/main/docs/DATA_STATEMENT.md`} target="_blank" rel="noreferrer">
        Data statement <ExternalLink aria-hidden="true" />
      </a>
    </p>
  );
}
