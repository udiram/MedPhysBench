import { Check, ChevronDown, CircleDashed, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import type { FleetStatus, FleetStatusModel } from "../types";

type Props = {
  data: FleetStatus | null;
};

type SourceFilter = "all" | "open" | "closed";
type StageFilter = "all" | "ranked" | "evaluated" | "access" | "planned";

const FUNNEL_STAGES = [
  ["planned_base_models", "Frozen panel", "Predeclared unique base IDs"],
  ["access_qualified_base_models", "Access qualified", "Live Q0 or later evidence"],
  ["evaluated_base_models", "Published", "At least one complete release matrix"],
  ["ranked_base_models", "Rankable", "Complete common-harness evidence"],
] as const;

export function FleetCoverage({ data }: Props) {
  const [source, setSource] = useState<SourceFilter>("all");
  const [stage, setStage] = useState<StageFilter>("all");
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  const rows = useMemo(() => {
    if (!data) return [];
    const normalized = deferredQuery.trim().toLowerCase();
    return data.models.filter((model) => {
      const matchesSource = source === "all" || model.openness === source;
      const matchesStage =
        stage === "all" ||
        (stage === "ranked" && model.ranked) ||
        (stage === "evaluated" && model.evaluated) ||
        (stage === "access" && model.access_qualified) ||
        (stage === "planned" && !model.access_qualified);
      const matchesQuery =
        !normalized ||
        model.display_name.toLowerCase().includes(normalized) ||
        model.base_model_id.toLowerCase().includes(normalized) ||
        model.steward.toLowerCase().includes(normalized) ||
        model.family.toLowerCase().includes(normalized);
      return matchesSource && matchesStage && matchesQuery;
    });
  }, [data, deferredQuery, source, stage]);

  if (!data) {
    return (
      <section className="fleet-section" id="fleet" aria-busy="true">
        <div className="section-heading">
          <h2>50-model qualification fleet</h2>
          <p>The frozen fleet projection is loading.</p>
        </div>
      </section>
    );
  }

  const target = data.summary.planned_base_models;

  return (
    <section className="fleet-section" id="fleet">
      <div className="section-heading fleet-heading">
        <div>
          <p className="eyebrow">Fleet integrity</p>
          <h2>{target} planned. {data.summary.evaluated_base_models} actually evaluated.</h2>
        </div>
        <p>
          The panel counts unique base model IDs—not effort settings, providers, aliases, or partial attempts. A model advances only
          when the evidence for that stage exists.
        </p>
      </div>

      <ol className="fleet-funnel" aria-label="Model fleet qualification funnel">
        {FUNNEL_STAGES.map(([key, label, description], index) => {
          const value = data.summary[key];
          const priorValue = index === 0 ? target : data.summary[FUNNEL_STAGES[index - 1][0]];
          return (
            <li key={key}>
              <div className="fleet-stage-topline">
                <span>0{index + 1}</span>
                <strong>{value}</strong>
                <small>/ {target}</small>
              </div>
              <h3>{label}</h3>
              <p>{description}</p>
              <div className="fleet-stage-track" aria-hidden="true">
                <i style={{ width: `${target === 0 ? 0 : (value / target) * 100}%` }} />
              </div>
              {index > 0 ? <small>{priorValue - value} stopped before this gate</small> : <small>Panel frozen before score review</small>}
            </li>
          );
        })}
      </ol>

      <div className="fleet-coverage-line" aria-label="Frozen fleet composition">
        <span><strong>{data.summary.open_planned_models}</strong> open-weight</span>
        <span><strong>{data.summary.closed_planned_models}</strong> closed</span>
        <span><strong>{data.summary.vision_planned_models}</strong> vision-capable</span>
        <span><strong>{data.summary.steward_count}</strong> stewards</span>
        <span><strong>{data.summary.published_system_configurations}</strong> published configurations</span>
        <span><strong>{data.summary.published_release_rows}</strong> release rows</span>
      </div>

      <details className="fleet-registry">
        <summary>
          <span>
            <strong>Inspect the frozen 50-model panel</strong>
            <small>See which exact base IDs are planned, accessible, published, and rankable.</small>
          </span>
          <ChevronDown aria-hidden="true" />
        </summary>
        <div className="fleet-registry-body">
          <div className="fleet-controls">
            <label className="field search-field">
              <span>Search fleet</span>
              <span className="search-wrap">
                <Search aria-hidden="true" />
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Model, steward, or base ID" />
              </span>
            </label>
            <label className="field">
              <span>Model source</span>
              <span className="select-wrap">
                <select value={source} onChange={(event) => setSource(event.target.value as SourceFilter)}>
                  <option value="all">Open + closed</option>
                  <option value="open">Open weights</option>
                  <option value="closed">Closed weights</option>
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
            <label className="field">
              <span>Qualification</span>
              <span className="select-wrap">
                <select value={stage} onChange={(event) => setStage(event.target.value as StageFilter)}>
                  <option value="all">Every stage</option>
                  <option value="ranked">Rankable</option>
                  <option value="evaluated">Published evaluation</option>
                  <option value="access">Access qualified</option>
                  <option value="planned">Planned only</option>
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
            <div className="fleet-result-count" role="status">
              <strong>{rows.length}</strong>
              <span>base models shown</span>
            </div>
          </div>

          <div className="fleet-model-grid">
            {rows.map((model) => <FleetModelCard key={model.base_model_id} model={model} />)}
          </div>
          {rows.length === 0 ? <p className="table-state">No planned base models match these filters.</p> : null}
        </div>
      </details>
    </section>
  );
}

function FleetModelCard({ model }: { model: FleetStatusModel }) {
  const status = model.ranked
    ? "Rankable"
    : model.evaluated
      ? "Published"
      : model.access_qualified
        ? model.qualification_stage?.toUpperCase() ?? "Access"
        : "Planned";
  const statusClass = model.ranked
    ? "ranked"
    : model.evaluated
      ? "evaluated"
      : model.access_qualified
        ? "access"
        : "planned";

  return (
    <article className={`fleet-model-card ${statusClass}`}>
      <header>
        <span className="fleet-state-icon" aria-hidden="true">
          {model.evaluated ? <Check /> : <CircleDashed />}
        </span>
        <span>
          <strong>{model.display_name}</strong>
          <small>{model.base_model_id}</small>
        </span>
        <em>{status}</em>
      </header>
      <footer>
        <span>{model.openness === "open" ? "Open weights" : "Closed"}</span>
        <span>{model.modalities.includes("image") ? "Vision" : "Text"}</span>
        <span>{model.steward}</span>
        {model.system_configuration_count > 0 ? <span>{model.system_configuration_count} config{model.system_configuration_count === 1 ? "" : "s"}</span> : null}
      </footer>
    </article>
  );
}
