export function getUrlParam(key: string): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get(key);
}

export function setUrlParams(
  updates: Record<string, string | null | undefined>,
  options: { history?: "replace" | "push" } = {},
) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  for (const [key, value] of Object.entries(updates)) {
    if (value == null || value === "") url.searchParams.delete(key);
    else url.searchParams.set(key, value);
  }
  const next = `${url.pathname}${url.search}${url.hash}`;
  const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  if (next !== current) {
    if (options.history === "push") window.history.pushState(null, "", next);
    else window.history.replaceState(null, "", next);
  }
}

export function readEnumParam<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  const value = getUrlParam(key);
  return value && allowed.includes(value as T) ? (value as T) : fallback;
}
