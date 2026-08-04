import { formatDuration, formatPercent, formatTokens, normalizeModelDisplayName, providerLabel, shortHash } from "../lib/format";
import { publicTaskInputFor } from "../lib/publicTaskInputs";
import { bestPublishedTaskEvidence } from "../lib/taskEvidenceComparison";
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
  const best = bestPublishedTaskEvidence(entries, selected, selectedTask);
  const human = releaseEvidence?.evidence.human_baseline ?? null;

  return (
    <section className="task-evidence-comparison" aria-labelledby="task-evidence-title">
      <header className="task-evidence-heading">
        <div>
          <h3 id="task-evidence-title">Input and outputs for this task</h3>
          <p>
            One sealed task input, the selected model response, the strongest published task result, and the matched
            human evidence state. The best-model column is task-specific—not simply the overall leaderboard leader.
          </p>
        </div>
        <span>{resultsScope === "official" ? "Official comparison scope" : "All published evidence scope"}</span>
      </header>

      <section className="shared-task-input" aria-label="Exact task input shown to evaluated models">
        <header>
          <div>
            <span>Shared sealed input</span>
            <h4>{selectedTask.title}</h4>
            <p>{selectedTask.task_id}</p>
          </div>
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
            <EvidenceJson label="Input payload" value={input.runtime_task.input_payload} />
            <EvidenceJson label="Expected response shape" value={input.runtime_task.expected_output_schema} />
            <dl className="task-input-contract">
              <div><dt>Risk tier</dt><dd>{input.runtime_task.risk_tier.replaceAll("_", " ")}</dd></div>
              <div><dt>Context artifacts</dt><dd>{input.runtime_task.context_artifacts.length}</dd></div>
              <div><dt>Allowed tools</dt><dd>{input.runtime_task.allowed_tools.length}</dd></div>
            </dl>
            <details className="complete-runtime-input">
              <summary>View complete sealed runtime input</summary>
              <p>
                This is the full task object delivered to the evaluated system, including context artifacts, tool
                permissions, safety constraints, and stop conditions. Authoring-only gold and grader data are excluded.
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

      <div className="task-output-columns" role="group" aria-label="Side-by-side task output comparison">
        <OutputEvidenceCard
          aggregate={null}
          comparisonNote="The exact attempt selected in the explorer."
          label="Selected model"
          modelName={selected.row.model_name}
          provider={selected.row.provider}
          publicOutputs={publicOutputs}
          task={selectedTask}
        />

        {best ? (
          <OutputEvidenceCard
            aggregate={`${best.comparison.outcomes.safe_success}/${best.comparison.attempts.length} safe successes · ${formatPercent(best.comparison.safeSuccessRate)}`}
            comparisonNote={bestModelNote(best.comparisonKind, best.attemptMatch)}
            label="Best published model on this task"
            modelName={best.comparison.entry.row.model_name}
            provider={best.comparison.entry.row.provider}
            publicOutputs={publicOutputs}
            task={best.attempt}
          />
        ) : (
          <section className="task-output-card unavailable" aria-label="Best published model unavailable">
            <span className="task-output-label">Best published model on this task</span>
            <h4>No eligible task leader</h4>
            <p>No complete published run resolved to this exact sealed runtime input.</p>
          </section>
        )}

        <section className="task-output-card human-placeholder" aria-label="Best verified human response">
          <span className="task-output-label">Best verified human</span>
          <h4>Coming soon</h4>
          <p>No verified task-level human response is published for this release.</p>
          <dl className="human-task-status">
            <div><dt>Study status</dt><dd>{human?.status.replaceAll("_", " ") ?? "unavailable"}</dd></div>
            <div><dt>Participants</dt><dd>{human ? `${human.completed}/${human.target ?? "—"}` : "—"}</dd></div>
          </dl>
          <p>
            Reference answers are feasibility evidence, not human performance. This column remains empty until matched
            participant evidence is reviewed and released.
          </p>
          <a href="/humans">Human benchmark protocol <span aria-hidden="true">→</span></a>
        </section>
      </div>
    </section>
  );
}

type OutputCardProps = {
  aggregate: string | null;
  comparisonNote: string;
  label: string;
  modelName: string;
  provider: string;
  publicOutputs: boolean;
  task: ModelTaskResult;
};

function OutputEvidenceCard({
  aggregate,
  comparisonNote,
  label,
  modelName,
  provider,
  publicOutputs,
  task,
}: OutputCardProps) {
  const failedRequired = task.grader_results?.find((grader) => grader.required_for_pass && !grader.passed) ?? null;
  const successful = task.outcome_category === "safe_success";
  return (
    <section className="task-output-card" aria-label={`${label}: ${normalizeModelDisplayName(modelName)}`}>
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
        <span>Structured output</span>
        {publicOutputs ? <pre>{renderJson(task.output)}</pre> : <p>Output is not public for this release.</p>}
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
    </section>
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
  if (comparisonKind === "selected_is_leader") return `The selected run is also the task leader. ${attempt}`;
  if (comparisonKind === "controlled_peer") return `Controlled same-harness task leader. ${attempt}`;
  return `Descriptive cross-contract task leader; no official cross-contract rank is inferred. ${attempt}`;
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
