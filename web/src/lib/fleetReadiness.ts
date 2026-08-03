import type { FleetStatusModel } from "../types";

export type FleetSourceFilter = "all" | "open" | "closed";
export type FleetStageFilter =
  | "all"
  | "workflow"
  | "ranked"
  | "evaluated"
  | "access"
  | "needs_evidence"
  | "planned";
export type FleetRouteFilter = "all" | FleetStatusModel["planned_routes"][number];

type FleetFilters = {
  source: FleetSourceFilter;
  stage: FleetStageFilter;
  route: FleetRouteFilter;
  query: string;
};

export function filterFleetModels(models: FleetStatusModel[], filters: FleetFilters) {
  const query = filters.query.trim().toLowerCase();
  return models.filter((model) => {
    const matchesSource = filters.source === "all" || model.openness === filters.source;
    const matchesStage =
      filters.stage === "all" ||
      (filters.stage === "workflow" && model.workflow_qualified) ||
      (filters.stage === "ranked" && model.ranked) ||
      (filters.stage === "evaluated" && model.evaluated) ||
      (filters.stage === "access" && model.access_qualified) ||
      (filters.stage === "needs_evidence" && !model.workflow_qualified) ||
      (filters.stage === "planned" && !model.access_qualified);
    const matchesRoute = filters.route === "all" || model.planned_routes.includes(filters.route);
    const searchText = [
      model.display_name,
      model.base_model_id,
      model.steward,
      model.family,
      model.readiness_note,
      fleetNextGateLabel(model.next_gate),
      ...model.planned_routes.map(fleetRouteLabel),
      ...model.access_evidence.flatMap((evidence) => [
        evidence.provider ?? "",
        evidence.model,
        evidence.surface,
        evidence.note,
        evidence.qualification_evidence?.submission_id ?? "",
        evidence.qualification_evidence?.manifest_path ?? "",
      ]),
    ]
      .join(" ")
      .toLowerCase();
    return matchesSource && matchesStage && matchesRoute && (!query || searchText.includes(query));
  });
}

export function fleetNextGateLabel(value: FleetStatusModel["next_gate"]) {
  if (value === "q0_access") return "Q0 · verify exact access";
  if (value === "q2_common_harness") return "Q2 · common-harness matrix";
  if (value === "q2_workflow") return "Q2 · workflow matrix";
  return "Q3 · reviewed comparison";
}

export function fleetRouteLabel(value: FleetStatusModel["planned_routes"][number]) {
  if (value === "self_hosted") return "Self-hosted";
  if (value === "openai") return "OpenAI API";
  if (value === "codex_native") return "Codex native";
  if (value === "aws_bedrock") return "AWS Bedrock";
  if (value === "xai") return "xAI";
  return value.charAt(0).toUpperCase() + value.slice(1);
}
