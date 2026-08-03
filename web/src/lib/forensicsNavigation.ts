import { modelRunKey } from "./modelRunKey";
import { setUrlParams } from "./urlState";
import type { ModelResult } from "../types";

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
