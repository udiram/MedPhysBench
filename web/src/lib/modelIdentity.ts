import type { ModelCatalogEntry, ModelResult } from "../types";

type ModelIdentity = Pick<ModelResult, "provider" | "model_name" | "model_revision">;

export function resolveRunBaseModelId(
  row: ModelIdentity,
  catalogByProviderModel: ReadonlyMap<string, ModelCatalogEntry>,
) {
  const catalogEntry = catalogByProviderModel.get(`${row.provider}::${row.model_name}`);
  if (catalogEntry?.base_model_id) {
    return catalogEntry.base_model_id;
  }

  if (typeof row.model_revision === "string" && row.model_revision.includes("@")) {
    return row.model_revision.split("@", 1)[0];
  }

  return `run::${row.provider}::${row.model_name}`;
}
