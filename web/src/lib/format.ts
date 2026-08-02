export function formatPercent(value: number | null | undefined) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

export function domainLabel(value: string) {
  return value
    .replace(/_physics$/, "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function artifactDirectory(modelName: string) {
  return modelName.replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_+|_+$/g, "");
}

export function formatDuration(seconds: number | null | undefined) {
  if (seconds == null || !Number.isFinite(seconds)) return "Unavailable";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${(seconds / 60).toFixed(1)}m`;
}

export function formatTokens(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "Unavailable";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 }).format(value);
}

export function shortHash(value: string | undefined) {
  if (!value) return "—";
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

export function providerLabel(provider: string): string {
  if (provider === "codex-native") return "OpenAI (GPT)";
  if (provider === "groq") return "Groq";
  if (provider === "ollama") return "Ollama";
  return provider;
}
