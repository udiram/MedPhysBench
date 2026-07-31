import { startTransition, useEffect, useState } from "react";
import type { Leaderboard } from "../types";

export function useLeaderboard(url: string) {
  const [data, setData] = useState<Leaderboard | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(false);
    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`Leaderboard request failed: ${response.status}`);
        return response.json() as Promise<Leaderboard>;
      })
      .then((payload) => {
        startTransition(() => {
          setData(payload);
          setLoadError(false);
        });
      })
      .catch((error: unknown) => {
        const errorName =
          typeof error === "object" && error !== null && "name" in error
            ? String(error.name)
            : "";
        if (errorName !== "AbortError") setLoadError(true);
      });
    return () => controller.abort();
  }, [url]);

  return { data, loadError };
}
