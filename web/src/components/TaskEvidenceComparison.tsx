import { formatDuration, formatPercent, formatTokens, normalizeModelDisplayName, providerLabel, shortHash } from "../lib/format";
import { taskAttemptKey } from "../lib/forensicsNavigation";
import { publicTaskInputFor } from "../lib/publicTaskInputs";
import { publishedTaskEvidence, summarizeEvidenceValue, verifiedTaskEvidence } from "../lib/taskEvidenceComparison";
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
  comparisonKey: string;
  entries: readonly T[];
  onComparisonChange: (key: string) => void;
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
  comparisonKey,
  entries,
  onComparisonChange,
  publicOutputs,
  releaseEvidence,
  releaseId,
  resultsScope,
  selected,
  selectedTask,
}: Props<T>) {
  if (!selected || !selectedTask) return null;

  const input = publicTaskInputFor(catalog, releaseId, selectedTask);
  const verified = verifiedTaskEvidence(entries, selected, selectedTask);
  const comparisons = publishedTaskEvidence(entries, selected, selectedTask);
  const best = verified[0] ?? null;
  const comparison = comparisons.find((entry) => entry.comparison.entry.key === comparisonKey) ?? best ?? comparisons[0] ?? null;
  const human = releaseEvidence?.evidence.human_baseline ?? null;
  const selectedName = normalizeModelDisplayName(selected.row.model_name);

  return (
    <section className="task-evidence-comparison" id="exact-task-comparison" aria-labelledby="task-evidence-title">
      <header className="task-evidence-heading">
        <div>
          <h3 id="task-evidence-title">Exact task comparison</h3>
          <p>
            Read the shared input once, then compare the exact scored outputs. The comparison model defaults to the
            verified task leader, but any eligible released peer can be selected.
          </p>
        </div>
        <div className="task-evidence-integrity" aria-label="Comparison integrity contract">
          <strong>{resultsScope === "official" ? "Official view" : "Published evidence view"}</strong>
          <span>Task leader: complete official rows only</span>
          <span>Exact runtime hash required</span>
        </div>
      </header>
      {comparisons.length ? (
        <div className="task-peer-control">
          <label htmlFor="task-peer-select">Compare {selectedName} with</label>
          <select
            id="task-peer-select"
            value={comparison?.comparison.entry.key ?? ""}
            onChange={(event) => onComparisonChange(event.target.value)}
          >
            {comparisons.map((entry) => (
              <option key={entry.comparison.entry.key} value={entry.comparison.entry.key}>
                {normalizeModelDisplayName(entry.comparison.entry.row.model_name)}
                {entry.comparison.entry.key === best?.comparison.entry.key ? " · task leader" : ""}
                {entry.comparison.entry.row.ranking_eligible ? "" : " · descriptive"}
              </option>
            ))}
          </select>
          <span>{best ? `${normalizeModelDisplayName(best.comparison.entry.row.model_name)} leads the official rows · ${best.comparison.outcomes.safe_success}/${best.comparison.attempts.length} safe successes.` : ""}</span>
        </div>
      ) : null}
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

          {comparison ? (
            <OutputEvidenceCard
              aggregate={`${comparison.comparison.outcomes.safe_success}/${comparison.comparison.attempts.length} safe successes · ${formatPercent(comparison.comparison.safeSuccessRate)}`}
              cardTone="leader"
              comparisonNote={comparisonModelNote(
                comparison.comparisonKind,
                comparison.attemptMatch,
                comparison.comparison.entry.key === best?.comparison.entry.key,
                comparison.comparison.entry.row.ranking_eligible,
              )}
              inspectHref={forensicsHref(releaseId, comparison.comparison.entry.key, comparison.attempt)}
              label={comparison.comparison.entry.key === best?.comparison.entry.key ? "Best verified model" : "Comparison model"}
              modelName={comparison.comparison.entry.row.model_name}
              provider={comparison.comparison.entry.row.provider}
              publicOutputs={publicOutputs}
              task={comparison.attempt}
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
        <span>Exact scored output</span>
        {publicOutputs && task.output ? <pre>{renderJson(task.output)}</pre> : <p>Output is not public for this release.</p>}
        {publicOutputs ? (
          <details className="exact-output-detail">
            <summary>Readable field summary</summary>
            <OutputFields output={task.output} />
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

function comparisonModelNote(
  comparisonKind: "selected_run" | "controlled_peer" | "descriptive_cross_contract",
  attemptMatch: "exact_attempt" | "same_runtime_input",
  taskLeader: boolean,
  rankingEligible: boolean,
) {
  const attempt = attemptMatch === "exact_attempt"
    ? "Exact attempt index, seed, and runtime input match."
    : "Same sealed runtime input; representative attempt from a different sampling contract.";
  if (comparisonKind === "selected_run") return `${taskLeader ? "The selected run is also the verified task leader." : "This is the selected run shown in both columns."} ${attempt}`;
  if (comparisonKind === "controlled_peer") return `${taskLeader ? "Verified task leader" : "User-selected published peer"} from the same harness contract. ${attempt}`;
  return `${taskLeader ? "Verified task leader" : rankingEligible ? "User-selected verified peer" : "User-selected descriptive peer"} from a different execution contract. ${attempt}`;
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
  return `/explore?${params.toString()}#exact-task-comparison`;
}
