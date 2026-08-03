import assert from "node:assert/strict";
import test from "node:test";

import { providerIdsForSlice, resolveProviderSelection } from "../src/lib/modelSlice.ts";

test("provider slices do not leak routes hidden by the active filter", () => {
  assert.deepEqual(
    providerIdsForSlice(["groq", "ollama"], ["groq"], "groq"),
    ["groq"],
  );
});

test("the unfiltered model registry retains every catalogued and observed route", () => {
  assert.deepEqual(
    providerIdsForSlice(["ollama", "groq"], ["groq", "custom"], "all"),
    ["custom", "groq", "ollama"],
  );
});

test("provider deep links accept stable IDs and human-facing labels case-insensitively", () => {
  const providers = ["codex-native", "groq", "ollama"];
  const label = (provider) => provider === "codex-native" ? "Codex native" : provider[0].toUpperCase() + provider.slice(1);

  assert.equal(resolveProviderSelection("groq", providers, label), "groq");
  assert.equal(resolveProviderSelection("Groq", providers, label), "groq");
  assert.equal(resolveProviderSelection("CODEX NATIVE", providers, label), "codex-native");
  assert.equal(resolveProviderSelection(null, providers, label), "all");
});
