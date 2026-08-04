import type { ModelTaskResult, PublicTaskInput, PublicTaskInputCatalog } from "../types";

export function publicTaskInputFor(
  catalog: PublicTaskInputCatalog | null,
  releaseId: string | null | undefined,
  attempt: Pick<ModelTaskResult, "runtime_task_hash" | "task_id"> | null | undefined,
): PublicTaskInput | null {
  if (!catalog || !releaseId || !attempt?.runtime_task_hash) return null;
  const releaseMatches = catalog.releases.filter((entry) => entry.release_id === releaseId);
  if (releaseMatches.length !== 1) return null;
  const taskMatches = releaseMatches[0].tasks.filter((entry) =>
    entry.task_id === attempt.task_id
    && entry.runtime_task_hash === attempt.runtime_task_hash
  );
  return taskMatches.length === 1 ? taskMatches[0] : null;
}
