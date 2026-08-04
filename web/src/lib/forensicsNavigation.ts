import { modelRunKey } from "./modelRunKey.ts";
import { setUrlParams } from "./urlState.ts";
import { normalizeModelDisplayName, providerLabel } from "./format.ts";
import type { ModelResult, ModelTaskResult } from "../types";

type ForensicsLabelRun = {
  provider: string;
  model_name: string;
  comparison_group?: string | null;
  harness_revision?: string | null;
  execution_surface?: string | null;
};

export function runForensicsAccessibleLabel(
  row: ForensicsLabelRun,
  options: { action?: string; releaseTitle?: string } = {},
) {
  const comparisonIdentity = row.comparison_group?.split("::").at(-1);
  const immutableContext = comparisonIdentity?.replace(/^config=/, "configuration ")
    ?? row.harness_revision
    ?? row.execution_surface
    ?? "published run";
  const releaseContext = options.releaseTitle ? ` in ${options.releaseTitle}` : "";
  return `${options.action ?? "Open attempt forensics"} for ${normalizeModelDisplayName(row.model_name)} on ${providerLabel(row.provider)}${releaseContext} — ${immutableContext}`;
}

export function taskAttemptKey(task: ModelTaskResult) {
  if (task.attempt_id) return task.attempt_id;
  return [
    task.task_id,
    task.attempt_index ?? "noattempt",
    task.seed ?? "noseed",
    task.run_id ?? "norun",
    task.runtime_task_hash ?? task.prompt_hash ?? "nohash",
  ].join("::");
}

export function exactPeerAttempt(
  tasks: readonly ModelTaskResult[],
  reference: ModelTaskResult,
): ModelTaskResult | null {
  const matches = tasks.filter((task) =>
    task.task_id === reference.task_id
    && task.attempt_index === reference.attempt_index
    && task.seed === reference.seed
    && task.runtime_task_hash === reference.runtime_task_hash
  );
  return matches.length === 1 ? matches[0] : null;
}

export function publicArtifactHref(path: string | null | undefined) {
  if (!path || !/^results\/releases\/[A-Za-z0-9._/-]+\.json$/.test(path)) return null;
  if (path.split("/").includes("..")) return null;
  const encodedPath = path.split("/").map(encodeURIComponent).join("/");
  return `https://github.com/udiram/MedPhysBench/blob/main/${encodedPath}`;
}

export function navigateToRunForensics(row: ModelResult) {
  setUrlParams(
    {
      fx_provider: row.provider,
      fx_model: modelRunKey(row),
      fx_domain: null,
      fx_outcome: null,
      fx_task: null,
    },
    { history: "push" },
  );
  if (typeof window === "undefined") return;
  window.dispatchEvent(new PopStateEvent("popstate"));
  if (window.location.hash !== "#forensics") {
    window.location.hash = "forensics";
  } else {
    document.getElementById("forensics")?.scrollIntoView();
  }
}

export function navigateToTaskForensics(row: ModelResult, task: ModelTaskResult) {
  setUrlParams(taskForensicsSelection(row, task), { history: "push" });
  if (typeof window === "undefined") return;
  window.dispatchEvent(new PopStateEvent("popstate"));
  if (window.location.hash !== "#forensics") {
    window.location.hash = "forensics";
  } else {
    document.getElementById("forensics")?.scrollIntoView();
  }
}

export function taskForensicsSelection(row: ModelResult, task: ModelTaskResult) {
  return {
    fx_provider: row.provider,
    fx_model: modelRunKey(row),
    fx_domain: null,
    fx_outcome: null,
    fx_task: taskAttemptKey(task),
  };
}
