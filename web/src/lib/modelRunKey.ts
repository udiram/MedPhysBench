import type { ModelResult } from "../types";

type ModelRunIdentity = Pick<
  ModelResult,
  "provider" | "model_name" | "model_revision" | "harness_revision" | "comparison_group" | "execution_surface" | "run_profile"
>;

type ReleasedModelRunIdentity = ModelRunIdentity & {
  release_id?: string | null;
  release_key?: string | null;
};

type ComparableModelRun = ReleasedModelRunIdentity & Pick<ModelResult, "ranking_eligible" | "safe_success_rate">;

export function modelRunKey(row: ModelRunIdentity) {
  const harness = row.harness_revision ?? row.run_profile?.harness_revision ?? row.execution_surface ?? "surface";
  const configuration =
    row.run_profile?.run_configuration_hash ??
    row.comparison_group ??
    row.model_revision ??
    row.execution_surface ??
    "default";
  return `${row.provider}::${row.model_name}::${harness}::${configuration}`;
}

export function releasedModelRunKey(row: ReleasedModelRunIdentity) {
  return `${row.release_key ?? row.release_id ?? "release"}::${modelRunKey(row)}`;
}

export function modelRunUrlSelection(row: Pick<ReleasedModelRunIdentity, "release_key"> & ModelRunIdentity) {
  return {
    runKey: modelRunKey(row),
    runRelease: row.release_key,
  };
}

export function compareModelRuns(left: ComparableModelRun, right: ComparableModelRun) {
  const isCommon = (row: ComparableModelRun) =>
    row.execution_surface === "common_harness" || row.run_profile?.is_common_harness === true;
  return (
    Number(right.ranking_eligible) - Number(left.ranking_eligible) ||
    Number(isCommon(right)) - Number(isCommon(left)) ||
    (right.harness_revision ?? "").localeCompare(left.harness_revision ?? "") ||
    right.safe_success_rate - left.safe_success_rate ||
    (left.release_id ?? "").localeCompare(right.release_id ?? "") ||
    modelRunKey(left).localeCompare(modelRunKey(right))
  );
}
