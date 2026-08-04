import { useEffect, useMemo, useState } from "react";
import { domainLabel, formatPercent, providerLabel } from "../lib/format";
import { modelRunKey } from "../lib/modelRunKey";
import { taskAttemptKey } from "../lib/forensicsNavigation";
import { scoreEvidenceAvailable } from "../lib/resultEvidence";
import type { ItemDiagnosticsArtifact, Leaderboard, PublicTaskInputCatalog, ReleaseView } from "../types";

type Props = {
  catalog: PublicTaskInputCatalog | null;
  catalogLoaded: boolean;
  data: Leaderboard | null;
  diagnostics?: ItemDiagnosticsArtifact | null;
  releaseView: ReleaseView;
};

export function EvalCatalogPage({ catalog, catalogLoaded, data, diagnostics, releaseView }: Props) {
  const [query, setQuery] = useState("");
  const [selectedTaskId, setSelectedTaskId] = useState("");
  const releaseTasks = useMemo(
    () => catalog?.releases.find((release) => release.release_id === data?.release.release_id)?.tasks ?? [],
    [catalog, data?.release.release_id],
  );
  const filteredTasks = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return releaseTasks;
    return releaseTasks.filter(({ runtime_task: task }) =>
      task.title.toLowerCase().includes(normalized)
      || task.task_id.toLowerCase().includes(normalized)
      || domainLabel(task.domain).toLowerCase().includes(normalized)
      || task.instructions.toLowerCase().includes(normalized)
    );
  }, [query, releaseTasks]);
  const selected = filteredTasks.find((task) => task.task_id === selectedTaskId) ?? filteredTasks[0] ?? null;
  const observed = useMemo(() => {
    if (!selected || !data) return null;
    const attempts = [...data.models, ...(data.unranked_models ?? [])]
      .filter((row) => scoreEvidenceAvailable(row))
      .flatMap((row) => row.tasks.filter((task) =>
        task.task_id === selected.task_id && task.runtime_task_hash === selected.runtime_task_hash
      ));
    const safeSuccesses = attempts.filter((task) => task.outcome_category === "safe_success").length;
    return {
      attempts: attempts.length,
      safeSuccesses,
      unsafe: attempts.filter((task) => task.outcome_category === "unsafe").length,
      unavailable: attempts.filter((task) => task.outcome_category === "unavailable" || task.capability_failure).length,
    };
  }, [data, selected]);
  const domainCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const task of releaseTasks) counts.set(task.runtime_task.domain, (counts.get(task.runtime_task.domain) ?? 0) + 1);
    return [...counts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
  }, [releaseTasks]);

  useEffect(() => setSelectedTaskId(""), [data?.release.release_id]);

  if (!catalogLoaded || !data) {
    return <section className="eval-catalog" aria-label="Evaluation catalog"><p role="status">Loading released evaluation contracts…</p></section>;
  }

  return (
    <section className="eval-catalog" aria-labelledby="eval-catalog-title">
      <header className="eval-catalog-summary">
        <div>
          <h2 id="eval-catalog-title">{data.release.title}</h2>
          <p>{data.release.description}</p>
        </div>
        <dl>
          <div><dt>Tasks</dt><dd>{releaseTasks.length}</dd></div>
          <div><dt>Domains</dt><dd>{domainCounts.length}</dd></div>
          <div><dt>Released runs</dt><dd>{data.models.length + (data.unranked_models?.length ?? 0)}</dd></div>
        </dl>
      </header>

      {diagnostics?.release_id === data.release.release_id ? (
        <BenchmarkPowerPanel diagnostics={diagnostics} />
      ) : null}

      <div className="eval-domain-map" aria-label="Task coverage by domain">
        {domainCounts.map(([domain, count]) => (
          <div key={domain}>
            <span>{domainLabel(domain)}</span>
            <i style={{ flexGrow: count }} />
            <strong>{count}</strong>
          </div>
        ))}
      </div>

      <div className="eval-browser">
        <aside className="eval-task-index">
          <label>
            <span>Find an eval</span>
            <input value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder="Task, domain, or instruction" />
          </label>
          <div role="list" aria-label="Released evaluation tasks">
            {filteredTasks.map((task) => (
              <button
                key={`${task.task_id}:${task.runtime_task_hash}`}
                type="button"
                aria-pressed={selected?.task_id === task.task_id}
                onClick={() => setSelectedTaskId(task.task_id)}
              >
                <strong>{task.runtime_task.title}</strong>
                <span>{domainLabel(task.runtime_task.domain)}</span>
              </button>
            ))}
          </div>
        </aside>

        {selected ? (
          <article className="eval-task-reader">
            <header>
              <div>
                <span>{domainLabel(selected.runtime_task.domain)}</span>
                <h3>{selected.runtime_task.title}</h3>
                <p>{selected.task_id}</p>
              </div>
              <a href={exploreHref(data, selected.task_id, selected.runtime_task_hash, releaseView)}>
                See model answers <span aria-hidden="true">→</span>
              </a>
            </header>

            <div className="eval-contract-graphic" aria-label="Evaluation contract anatomy">
              <div><span>1</span><strong>Sealed task</strong><p>Instructions and released input only</p></div>
              <div><span>2</span><strong>Model response</strong><p>Bounded schema and tool contract</p></div>
              <div><span>3</span><strong>Outcome</strong><p>Deterministic checks and safety gates</p></div>
            </div>

            <dl className="eval-observed-outcomes" aria-label="Observed outcomes on this exact released input">
              <div><dt>Evaluated attempts</dt><dd>{observed?.attempts ?? 0}</dd></div>
              <div><dt>Observed safe success</dt><dd>{observed?.attempts ? `${observed.safeSuccesses}/${observed.attempts}` : "No evidence yet"}</dd></div>
              <div><dt>Unsafe</dt><dd>{observed?.unsafe ?? 0}</dd></div>
              <div><dt>Capability unavailable</dt><dd>{observed?.unavailable ?? 0}</dd></div>
            </dl>

            <section className="eval-reader-section">
              <h4>What the model sees</h4>
              <p>{selected.runtime_task.instructions}</p>
              <pre>{JSON.stringify(selected.runtime_task.input_payload, null, 2)}</pre>
            </section>

            <details className="eval-reader-detail">
              <summary>Open the full released contract</summary>
              <dl>
                <div><dt>Risk</dt><dd>{selected.runtime_task.risk_tier.replaceAll("_", " ")}</dd></div>
                <div><dt>Tools</dt><dd>{selected.runtime_task.allowed_tools.length}</dd></div>
                <div><dt>Artifacts</dt><dd>{selected.runtime_task.context_artifacts.length}</dd></div>
              </dl>
              <pre>{JSON.stringify(selected.runtime_task, null, 2)}</pre>
            </details>
          </article>
        ) : (
          <div className="eval-reader-empty" role="status">No released task matches this search.</div>
        )}
      </div>
    </section>
  );
}

function BenchmarkPowerPanel({ diagnostics }: { diagnostics: ItemDiagnosticsArtifact }) {
  const groups = diagnostics.item_diagnostics.groups;
  const floorSignal = groups.some((group) =>
    group.summary.watch_signals.some((signal) => signal.code === "near_zero_family_entropy_above_half")
  );
  const totalModels = groups.reduce((sum, group) => sum + group.model_count, 0);
  const totalAttempts = groups.reduce((sum, group) => sum + group.attempt_count, 0);

  return (
    <section className="benchmark-power" aria-labelledby="benchmark-power-title">
      <header>
        <div>
          <span>Benchmark power</span>
          <h3 id="benchmark-power-title">
            {floorSignal ? "The public response matrix shows floor effects." : "The public response matrix remains informative."}
          </h3>
          <p>
            This diagnostic asks whether tasks separate systems inside one exact harness contract. It does not mix
            providers, call a public set contamination-resistant, or convert small-panel estimates into official ranks.
          </p>
        </div>
        <dl>
          <div><dt>Eligible systems</dt><dd>{totalModels}</dd></div>
          <div><dt>Scored attempts</dt><dd>{totalAttempts}</dd></div>
          <div><dt>Exact groups</dt><dd>{groups.length}</dd></div>
        </dl>
      </header>

      <div className="benchmark-power-groups">
        {groups.map((group) => {
          const provider = group.comparison_group.split("::", 1)[0];
          const taskRates = group.tasks.map((task) => task.safe_success_rate).sort((left, right) => left - right);
          const minimum = taskRates[0] ?? 0;
          const maximum = taskRates.at(-1) ?? 0;
          const median = group.summary.median_task_safe_success_rate ?? 0;
          return (
            <article key={group.comparison_group}>
              <header>
                <span>{providerLabel(provider)}</span>
                <strong>{group.model_count} systems · {group.attempt_count} attempts</strong>
              </header>
              <div className="benchmark-power-spectrum" aria-label={`${providerLabel(provider)} task safe-success range`}>
                <i style={{ left: `${minimum * 100}%`, width: `${Math.max(1, (maximum - minimum) * 100)}%` }} />
                <b style={{ left: `${median * 100}%` }} />
              </div>
              <dl>
                <div><dt>Best system</dt><dd>{formatPercent(group.summary.best_system_safe_success_rate)}</dd></div>
                <div><dt>Median task</dt><dd>{formatPercent(group.summary.median_task_safe_success_rate)}</dd></div>
                <div>
                  <dt>Discrimination</dt>
                  <dd>{group.summary.median_task_discrimination == null ? "Not estimable" : group.summary.median_task_discrimination.toFixed(2)}</dd>
                </div>
                <div><dt>Estimable tasks</dt><dd>{group.summary.discrimination_task_count}/{group.task_count}</dd></div>
              </dl>
              <p>
                {group.summary.panel_solved_family_count}/{group.family_count} families were solved by at least 80% of
                systems. {group.summary.near_zero_entropy_family_count}/{group.family_count} had near-zero family-solved entropy.
              </p>
            </article>
          );
        })}
      </div>

      <details>
        <summary>How to read this diagnostic</summary>
        <p>
          A floor signal means most systems fail the family-level threshold in the same way; a ceiling signal would mean
          most solve it. Both reduce separation. Task discrimination is reported only with at least three systems and
          non-zero variance. These are public-development diagnostics, not protected-holdout saturation decisions.
        </p>
        <a href="/data/public-real-workflows-pilot-v0.6-diagnostics.json">Download the hash-bound diagnostic JSON</a>
      </details>
    </section>
  );
}

function exploreHref(data: Leaderboard, taskId: string, runtimeHash: string, releaseView: ReleaseView) {
  const rows = [...data.models, ...(data.unranked_models ?? [])]
    .filter((row) =>
      scoreEvidenceAvailable(row)
      && row.completed_count === row.expected_attempt_count
      && row.error_count === 0
      && row.integrity.missing_attempt_keys === 0
    )
    .sort((left, right) =>
      (left.outcome_rank ?? Number.POSITIVE_INFINITY) - (right.outcome_rank ?? Number.POSITIVE_INFINITY)
      || left.model_name.localeCompare(right.model_name)
    );
  for (const row of rows) {
    const attempt = row.tasks.find((task) => task.task_id === taskId && task.runtime_task_hash === runtimeHash);
    if (!attempt) continue;
    const params = new URLSearchParams();
    if (releaseView !== "real") params.set("release", releaseView);
    params.set("fx_model", modelRunKey(row));
    params.set("fx_task", taskAttemptKey(attempt));
    return `/explore?${params.toString()}#exact-task-comparison`;
  }
  const params = new URLSearchParams();
  if (releaseView !== "real") params.set("release", releaseView);
  params.set("fx_task_query", taskId);
  return `/explore?${params.toString()}#forensics`;
}
