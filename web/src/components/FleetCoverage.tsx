import { ArrowRight, Check, ChevronDown, CircleDashed, Search } from "lucide-react";
import { useDeferredValue, useMemo, useState } from "react";
import {
  filterFleetModels,
  fleetNextGateLabel,
  fleetRouteLabel,
  hasAttestedQualification,
  type FleetRouteFilter,
  type FleetSourceFilter,
  type FleetStageFilter,
} from "../lib/fleetReadiness";
import { REPO_URL } from "../content";
import type { FleetStatus, FleetStatusModel } from "../types";

type Props = {
  data: FleetStatus | null;
};

const FUNNEL_STAGES = [
  ["planned_base_models", "Frozen panel", "Predeclared unique base IDs"],
  ["access_qualified_base_models", "Published evidence", "Any route-backed or native public evidence; not a common-harness gate"],
  ["evaluated_base_models", "Common-harness evaluated", "Complete current-contract matrix on a common adapter"],
  ["ranked_base_models", "Rankable", "At least two systems share one exact frozen comparison contract"],
  ["workflow_view_evaluated_base_models", "OpenKBP workflow-view", "Complete one-response OpenKBP view matrix; not stateful"],
] as const;

export function FleetCoverage({ data }: Props) {
  const [source, setSource] = useState<FleetSourceFilter>("all");
  const [stage, setStage] = useState<FleetStageFilter>("all");
  const [route, setRoute] = useState<FleetRouteFilter>("all");
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const routeOptions = useMemo(
    () => [...new Set((data?.models ?? []).flatMap((model) => model.planned_routes))].sort((left, right) => left.localeCompare(right)),
    [data],
  );

  const rows = useMemo(() => {
    if (!data) return [];
    return filterFleetModels(data.models, { source, stage, route, query: deferredQuery });
  }, [data, deferredQuery, route, source, stage]);

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
  const completionGate = data.completion_gate;

  return (
    <section className="fleet-section" id="fleet">
      <div className="section-heading fleet-heading">
        <div>
          <p className="eyebrow">Fleet integrity</p>
          <h2>{target} planned. {data.summary.access_qualified_base_models} with published evidence. {data.summary.evaluated_base_models} attested common-harness evaluated.</h2>
        </div>
        <p>
          The panel counts unique base model IDs—not effort settings, providers, aliases, or partial attempts. Published evidence is
          intentionally broader than qualification: only complete, attested common-harness matrices advance to evaluated or ranked.
          Native and recorded evaluations remain fully visible in the model index without inflating the comparable gate.
        </p>
      </div>

      <ol className="fleet-funnel" aria-label="Model fleet qualification funnel">
        {FUNNEL_STAGES.map(([key, label, description], index) => {
          const value = data.summary[key];
          const priorValue = key === "workflow_view_evaluated_base_models"
            ? data.summary.evaluated_base_models
            : index === 0
              ? target
              : data.summary[FUNNEL_STAGES[index - 1][0]];
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

      {completionGate ? (
        <section className="fleet-completion-gate" aria-label="50-model completion claim gate">
          <div className="fleet-completion-score">
            <span>Publication claim gate</span>
            <strong>{completionGate.satisfied_base_model_count}<small> / {completionGate.required_base_model_count}</small></strong>
            <p>
              {completionGate.satisfied
                ? "Every frozen evidence and composition requirement is satisfied."
                : `${completionGate.remaining_base_model_count} frozen base models still need complete, attested common-harness evidence.`}
            </p>
          </div>
          <div className="fleet-completion-progress" aria-hidden="true">
            <i style={{ width: `${(completionGate.satisfied_base_model_count / completionGate.required_base_model_count) * 100}%` }} />
          </div>
          <dl className="fleet-completion-composition">
            <CompletionFacet label="Open weights" facet={completionGate.composition.open_base_models} />
            <CompletionFacet label="Closed models" facet={completionGate.composition.closed_base_models} />
            <CompletionFacet label="Vision-capable" facet={completionGate.composition.vision_capable_base_models} />
            <CompletionFacet label="Stewards" facet={completionGate.composition.steward_count} />
            <div>
              <dt>Size tiers</dt>
              <dd>{completionGate.composition.size_tiers.observed.join(" · ") || "none"}</dd>
              <small>{completionGate.composition.size_tiers.satisfied ? "requirement met" : `missing ${completionGate.composition.size_tiers.remaining.join(" · ")}`}</small>
            </div>
          </dl>
        </section>
      ) : null}

      <div className="fleet-coverage-line" aria-label="Frozen fleet composition">
        <span><strong>Planned panel</strong></span>
        <span><strong>{data.summary.open_planned_models}</strong> open-weight</span>
        <span><strong>{data.summary.closed_planned_models}</strong> closed</span>
        <span><strong>{data.summary.vision_planned_models}</strong> vision-capable</span>
        <span><strong>{data.summary.steward_count}</strong> stewards</span>
        <span><strong>{data.summary.published_system_configurations}</strong> published configurations</span>
        <span><strong>{data.summary.published_release_rows}</strong> release rows</span>
        <span><strong>{data.summary.declared_route_count}</strong> executable routes declared</span>
        <span><strong>{data.summary.route_set_count}</strong> frozen route sets</span>
      </div>

      <div className="fleet-coverage-line" aria-label="Actually evaluated fleet composition">
        <span><strong>Evaluated slice</strong></span>
        <span><strong>{data.summary.evaluated_open_base_models}</strong> open-weight</span>
        <span><strong>{data.summary.evaluated_closed_base_models}</strong> closed</span>
        <span><strong>{data.summary.evaluated_image_route_base_models}</strong> image-capable routes evaluated</span>
        <span><strong>{data.summary.evaluated_steward_count}</strong> stewards</span>
        <span><strong>{data.summary.evaluated_size_tiers.join(" · ") || "none"}</strong> size tiers represented</span>
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
              <span>Openness</span>
              <span className="select-wrap">
                <select value={source} onChange={(event) => setSource(event.target.value as FleetSourceFilter)}>
                  <option value="all">All systems</option>
                  <option value="open">Open weights</option>
                  <option value="closed">Closed models</option>
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
            <label className="field">
              <span>Qualification</span>
              <span className="select-wrap">
                <select value={stage} onChange={(event) => setStage(event.target.value as FleetStageFilter)}>
                  <option value="all">Every stage</option>
                  <option value="workflow_view">OpenKBP workflow-view evaluated</option>
                  <option value="ranked">Rankable</option>
                  <option value="evaluated">Published evaluation</option>
                  <option value="access">Published access/evidence</option>
                  <option value="needs_evidence">Needs OpenKBP view evidence</option>
                  <option value="planned">No access evidence</option>
                </select>
                <ChevronDown aria-hidden="true" />
              </span>
            </label>
            <label className="field">
              <span>Planned route</span>
              <span className="select-wrap">
                <select value={route} onChange={(event) => setRoute(event.target.value as FleetRouteFilter)}>
                  <option value="all">Any route</option>
                  {routeOptions.map((value) => (
                    <option key={value} value={value}>
                      {fleetRouteLabel(value)}
                    </option>
                  ))}
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

function CompletionFacet({ label, facet }: { label: string; facet: { required: number; observed: number; satisfied: boolean; remaining: number } }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{facet.observed} / {facet.required}</dd>
      <small>{facet.satisfied ? "requirement met" : `${facet.remaining} remaining`}</small>
    </div>
  );
}

function FleetModelCard({ model }: { model: FleetStatusModel }) {
  const attested = hasAttestedQualification(model);
  const status = model.workflow_view_ranked
    ? "OpenKBP view ranked"
    : model.ranked
      ? "Rankable"
      : model.evaluated
        ? "Published"
        : model.access_qualified
          ? attested
            ? model.qualification_stage?.toUpperCase() ?? "Attested"
            : "Published evidence"
          : "Planned";
  const statusClass = model.workflow_view_ranked || model.ranked
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
        <span>{sizeTierLabel(model.size_tier)}</span>
        <span>{model.steward}</span>
        {model.system_configuration_count > 0 ? <span>{model.system_configuration_count} config{model.system_configuration_count === 1 ? "" : "s"}</span> : null}
        <span>{model.planned_routes.map(fleetRouteLabel).join(" · ")}</span>
      </footer>
      <details className="fleet-card-details">
        <summary>
          <span>
            <small>Next gate</small>
            <strong>{fleetNextGateLabel(model.next_gate)}</strong>
          </span>
          <ChevronDown aria-hidden="true" />
        </summary>
        <div className="fleet-card-readiness">
          <p>{model.readiness_note}</p>
          {model.access_evidence.length > 0 ? (
            <ul aria-label={`Access evidence for ${model.display_name}`}>
              {model.access_evidence.map((evidence) => (
                <li key={`${evidence.provider ?? "unknown"}:${evidence.model}:${evidence.date}`}>
                  <div>
                    <strong>{evidence.provider ?? "Undeclared provider"} · {evidence.model}</strong>
                    <span>
                      {evidence.qualification_evidence
                        ? `${evidence.qualification_stage?.toUpperCase() ?? "Attested"} attested`
                        : "Published evidence"} · {evidence.date}
                    </span>
                  </div>
                  <p>{evidence.note}</p>
                  {evidence.qualification_evidence ? (
                    <a
                      href={`${REPO_URL}/blob/main/${evidence.qualification_evidence.manifest_path}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Inspect attested submission · {evidence.qualification_evidence.submission_id}
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="fleet-no-evidence"><ArrowRight aria-hidden="true" /> Start with an exact Q0 route probe; do not infer availability from the planned provider list.</p>
          )}
        </div>
      </details>
    </article>
  );
}

function sizeTierLabel(value: FleetStatusModel["size_tier"]) {
  if (value === "frontier") return "Frontier";
  if (value === "undisclosed") return "Undisclosed";
  return `${value.charAt(0).toUpperCase()}${value.slice(1)} tier`;
}
