import { formatDuration, formatPercent, formatTokens, normalizeModelDisplayName, providerLabel, shortHash } from "../lib/format";
import { taskAttemptKey } from "../lib/forensicsNavigation";
import { publicTaskInputFor } from "../lib/publicTaskInputs";
import { bestVerifiedTaskEvidence, summarizeEvidenceValue } from "../lib/taskEvidenceComparison";
import type { TaskComparisonEntry } from "../lib/taskComparison";
import type { ResultsScope } from "../lib/resultsScope";
import type {
  ModelTaskResult,
  PublicTaskInputCatalog,
  ReleaseEvidence,
} from "../types";

type Props<T extends TaskComparisonEntry> = {
  catalog: PublicTaskInputCatalog | null;
  catalogLoaded: boolean;
  entries: readonly T[];
  publicOutputs: boolean;
  releaseEvidence: ReleaseEvidence | null;
  releaseId: string;
  resultsScope: ResultsScope;
  selected: T | null;
  selectedTask: ModelTaskResult | null;
};

export function TaskEvidenceComparison<T extends TaskComparisonEntry>({
  catalog,
  catalogLoaded,
  entries,
  publicOutputs,
  releaseEvidence,
  releaseId,
  resultsScope,
  selected,
  selectedTask,
}: Props<T>) {
  if (!selected || !selectedTask) return null;

  const input = publicTaskInputFor(catalog, releaseId, selectedTask);
  const best = bestVerifiedTaskEvidence(entries, selected, selectedTask);
  const human = releaseEvidence?.evidence.human_baseline ?? null;
  const selectedName = normalizeModelDisplayName(selected.row.model_name);

  return (
    <section className="task-evidence-comparison" aria-labelledby="task-evidence-title">
      <header className="task-evidence-heading">
        <div>
          <h3 id="task-evidence-title">Compare the exact response</h3>
          <p>
            The shared input is the released runtime object seen by every compared system. The response columns show
            the selected attempt, the best verified model on this exact task input, and matched human evidence.
          </p>
        </div>
        <div className="task-evidence-integrity" aria-label="Comparison integrity contract">
          <strong>{resultsScope === "official" ? "Official view" : "Published evidence view"}</strong>
          <span>Task leader: complete official rows only</span>
          <span>Exact runtime hash required</span>
        </div>
      </header>
      <p className="sr-only" aria-live="polite">
        Showing {selectedName}, task {selectedTask.title}, attempt {(selectedTask.attempt_index ?? 0) + 1}.
      </p>

      <div className="task-comparison-stage">
        <section className="shared-task-input" aria-label="Exact task input shown to every compared respondent">
          <header>
            <span>Exact shared input</span>
            <h4>{selectedTask.title}</h4>
            <p>{selectedTask.task_id}</p>
            <dl>
              <div><dt>Runtime</dt><dd>{shortHash(selectedTask.runtime_task_hash)}</dd></div>
              <div><dt>Attempt</dt><dd>{(selectedTask.attempt_index ?? 0) + 1}</dd></div>
            </dl>
          </header>
          {!catalogLoaded ? (
            <p className="task-input-state" role="status">Loading the exact runtime-visible task input…</p>
          ) : input ? (
            <div className="task-input-body">
              <div className="task-instructions">
                <span>Instructions</span>
                <p>{input.runtime_task.instructions}</p>
              </div>
              <EvidenceJson label="Input data" value={input.runtime_task.input_payload} />
              <dl className="task-input-contract">
                <div><dt>Risk tier</dt><dd>{input.runtime_task.risk_tier.replaceAll("_", " ")}</dd></div>
                <div><dt>Context artifacts</dt><dd>{input.runtime_task.context_artifacts.length}</dd></div>
                <div><dt>Allowed tools</dt><dd>{input.runtime_task.allowed_tools.length}</dd></div>
              </dl>
              <details className="runtime-input-detail">
                <summary>Expected response shape</summary>
                <pre>{renderJson(input.runtime_task.expected_output_schema)}</pre>
              </details>
              <details className="runtime-input-detail complete-runtime-input">
                <summary>Complete released input</summary>
                <p>
                  Includes context artifacts, tool permissions, safety constraints, and stop conditions. Authoring-only
                  gold and grader data are excluded.
                </p>
                <pre>{renderJson(input.runtime_task)}</pre>
              </details>
            </div>
          ) : (
            <p className="task-input-state bad" role="alert">
              Exact input unavailable: the release, task ID, and runtime hash did not resolve to one sealed public task.
            </p>
          )}
        </section>

        <div className="task-output-columns" role="group" aria-label="Side-by-side task response comparison">
          <OutputEvidenceCard
            aggregate={null}
            cardTone="selected"
            comparisonNote="The exact model attempt selected above."
            label="Selected model"
            modelName={selected.row.model_name}
            provider={selected.row.provider}
            publicOutputs={publicOutputs}
            task={selectedTask}
          />

          {best ? (
            <OutputEvidenceCard
              aggregate={`${best.comparison.outcomes.safe_success}/${best.comparison.attempts.length} safe successes · ${formatPercent(best.comparison.safeSuccessRate)}`}
              cardTone="leader"
              comparisonNote={bestModelNote(best.comparisonKind, best.attemptMatch)}
              inspectHref={forensicsHref(releaseId, best.comparison.entry.key, best.attempt)}
              label="Best verified model"
              modelName={best.comparison.entry.row.model_name}
              provider={best.comparison.entry.row.provider}
              publicOutputs={publicOutputs}
              task={best.attempt}
            />
          ) : (
            <section className="task-output-card unavailable" aria-label="Best verified model unavailable">
              <span className="task-output-label">Best verified model</span>
              <h4>No eligible task leader</h4>
              <p className="task-empty-explanation">
                No complete, officially ranked run resolved to this exact task ID and runtime hash. A nearby or
                cross-contract result is not substituted.
              </p>
            </section>
          )}

          <section className="task-output-card human-placeholder" aria-label="Best verified human response">
            <span className="task-output-label">Best verified human</span>
            <h4>Coming soon</h4>
            <p className="task-output-provider">Same released task · reviewed participants only</p>
            <div className="human-output-placeholder" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <p>
              No verified task-level human response is published for this release. Reference answers are feasibility
              evidence, not human performance, and are never substituted here.
            </p>
            <dl className="human-task-status">
              <div><dt>Study status</dt><dd>{human?.status.replaceAll("_", " ") ?? "unavailable"}</dd></div>
              <div><dt>Participants</dt><dd>{human ? `${human.completed}/${human.target ?? "—"}` : "—"}</dd></div>
            </dl>
            <a className="task-output-link" href="/humans">Human benchmark protocol <span aria-hidden="true">→</span></a>
          </section>
        </div>
      </div>
    </section>
  );
}

type OutputCardProps = {
  aggregate: string | null;
  cardTone: "selected" | "leader";
  comparisonNote: string;
  inspectHref?: string;
  label: string;
  modelName: string;
  provider: string;
  publicOutputs: boolean;
  task: ModelTaskResult;
};

function OutputEvidenceCard({
  aggregate,
  cardTone,
  comparisonNote,
  inspectHref,
  label,
  modelName,
  provider,
  publicOutputs,
  task,
}: OutputCardProps) {
  const failedRequired = task.grader_results?.find((grader) => grader.required_for_pass && !grader.passed) ?? null;
  const successful = task.outcome_category === "safe_success";
  return (
    <section className={`task-output-card ${cardTone}`} aria-label={`${label}: ${normalizeModelDisplayName(modelName)}`}>
      <span className="task-output-label">{label}</span>
      <h4>{normalizeModelDisplayName(modelName)}</h4>
      <p className="task-output-provider">
        {providerLabel(provider)} · attempt {(task.attempt_index ?? 0) + 1}
      </p>
      <div className="task-output-outcome">
        <strong className={successful ? "outcome-good" : task.safe === false ? "outcome-bad" : "outcome-warn"}>
          {outcomeLabel(task)}
        </strong>
        <span>{task.score == null ? "Score unavailable" : formatPercent(task.score)}</span>
      </div>
      {aggregate ? <p className="task-output-aggregate">{aggregate}</p> : null}
      <p className="task-comparison-note">{comparisonNote}</p>
      <div className="task-output-json">
        <span>Model output</span>
        {publicOutputs ? <OutputFields output={task.output} /> : <p>Output is not public for this release.</p>}
        {publicOutputs && task.output ? (
          <details className="exact-output-detail">
            <summary>View exact structured output</summary>
            <pre>{renderJson(task.output)}</pre>
          </details>
        ) : null}
      </div>
      <div className="task-grader-summary">
        <span>{failedRequired ? "Decisive failed check" : "Required checks"}</span>
        <strong>{failedRequired?.grader_id ?? "All published required checks passed"}</strong>
        <p>{failedRequired?.rationale ?? "No required deterministic failure is published for this attempt."}</p>
      </div>
      <dl className="task-output-telemetry">
        <div><dt>Time</dt><dd>{formatDuration(task.duration_seconds)}</dd></div>
        <div><dt>Tokens</dt><dd>{task.token_usage?.available ? formatTokens(task.token_usage.total_tokens) : "Unavailable"}</dd></div>
      </dl>
      {inspectHref ? <a className="task-output-link" href={inspectHref}>Open this exact attempt <span aria-hidden="true">→</span></a> : null}
    </section>
  );
}

function OutputFields({ output }: { output: Record<string, unknown> | undefined }) {
  if (!output || !Object.keys(output).length) return <p>No structured output was recorded.</p>;
  return (
    <dl className="task-output-fields">
      {Object.entries(output).map(([key, value]) => (
        <div key={key}>
          <dt>{key.replaceAll("_", " ")}</dt>
          <dd>{summarizeEvidenceValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function EvidenceJson({ label, value }: { label: string; value: Record<string, unknown> }) {
  return (
    <div className="task-input-json">
      <span>{label}</span>
      <pre>{renderJson(value)}</pre>
    </div>
  );
}

function bestModelNote(
  comparisonKind: "selected_is_leader" | "controlled_peer" | "descriptive_cross_contract",
  attemptMatch: "exact_attempt" | "same_runtime_input",
) {
  const attempt = attemptMatch === "exact_attempt"
    ? "Exact attempt index, seed, and runtime input match."
    : "Same sealed runtime input; representative attempt from a different sampling contract.";
  if (comparisonKind === "selected_is_leader") return `The selected run is also the verified task leader. ${attempt}`;
  if (comparisonKind === "controlled_peer") return `Official same-harness task leader. ${attempt}`;
  return `Official task leader from a different execution contract; the comparison is descriptive. ${attempt}`;
}

function outcomeLabel(task: ModelTaskResult) {
  if (task.capability_failure) return "Capability unavailable";
  if (task.outcome_category === "safe_success") return "Safe success";
  if (task.outcome_category === "safe_failure") return "Safe failure";
  if (task.outcome_category === "unsafe") return "Unsafe";
  return "Inconclusive";
}

function renderJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

function forensicsHref(releaseId: string, runKey: string, task: ModelTaskResult) {
  const params = new URLSearchParams();
  if (releaseId === "public-core-v0.4") params.set("release", "core");
  else if (releaseId === "public-imaging-pilot-v0.4") params.set("release", "imaging");
  else if (releaseId === "public-tg263-pilot-v0.5") params.set("release", "tg263");
  params.set("fx_model", runKey);
  params.set("fx_task", taskAttemptKey(task));
  return `/explore?${params.toString()}#forensics`;
}
