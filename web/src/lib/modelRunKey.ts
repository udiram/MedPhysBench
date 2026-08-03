import type { ModelResult } from "../types";

export function modelRunKey(row: ModelResult) {
  const harness = row.harness_revision ?? row.run_profile?.harness_revision ?? row.execution_surface ?? "surface";
  const configuration =
    row.run_profile?.run_configuration_hash ??
    row.comparison_group ??
    row.model_revision ??
    row.execution_surface ??
    "default";
  return `${row.provider}::${row.model_name}::${harness}::${configuration}`;
}
