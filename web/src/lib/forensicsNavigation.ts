import { modelRunKey } from "./modelRunKey.ts";
import { setUrlParams } from "./urlState.ts";
import type { ModelResult, ModelTaskResult } from "../types";

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
