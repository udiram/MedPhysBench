import assert from "node:assert/strict";
import test from "node:test";

import { resolveRunBaseModelId } from "../src/lib/modelIdentity.ts";

const catalog = new Map([
  [
    "codex-native::gpt-5.6-sol [effort=high]",
    {
      provider: "codex-native",
      model_name: "gpt-5.6-sol [effort=high]",
      base_model_id: "gpt-5.6-sol",
    },
  ],
  [
    "groq::llama-3.1-8b-instant",
    {
      provider: "groq",
      model_name: "llama-3.1-8b-instant",
      base_model_id: "meta-llama/Llama-3.1-8B-Instruct",
    },
  ],
  [
    "ollama::llama3.1:8b",
    {
      provider: "ollama",
      model_name: "llama3.1:8b",
      base_model_id: "meta-llama/Llama-3.1-8B-Instruct",
    },
  ],
  [
    "ollama::qwen3-vl:8b",
    {
      provider: "ollama",
      model_name: "qwen3-vl:8b",
      base_model_id: "Qwen/Qwen3-VL-8B-Instruct",
    },
  ],
  [
    "ollama::qwen3-vl:8b-instruct",
    {
      provider: "ollama",
      model_name: "qwen3-vl:8b-instruct",
      base_model_id: "Qwen/Qwen3-VL-8B-Instruct",
    },
  ],
]);

test("catalog identity groups GPT effort variants under the frozen base model", () => {
  const key = resolveRunBaseModelId(
    {
      provider: "codex-native",
      model_name: "gpt-5.6-sol [effort=high]",
      model_revision: "gpt-5.6-sol@2026-08-02",
    },
    catalog,
  );

  assert.equal(key, "gpt-5.6-sol");
});

test("catalog identity keeps Groq routes on the same public base-model axis", () => {
  const key = resolveRunBaseModelId(
    {
      provider: "groq",
      model_name: "llama-3.1-8b-instant",
      model_revision: "llama-3.1-8b-instant@2026-08-01",
    },
    catalog,
  );

  assert.equal(key, "meta-llama/Llama-3.1-8B-Instruct");
});

test("catalog identity groups local and Groq Llama 3.1 routes without merging run evidence", () => {
  const localKey = resolveRunBaseModelId(
    {
      provider: "ollama",
      model_name: "llama3.1:8b",
      model_revision: "sha256:46e0c10c039e",
    },
    catalog,
  );
  const hostedKey = resolveRunBaseModelId(
    {
      provider: "groq",
      model_name: "llama-3.1-8b-instant",
      model_revision: "llama-3.1-8b-instant@2026-08-01",
    },
    catalog,
  );

  assert.equal(localKey, hostedKey);
  assert.equal(localKey, "meta-llama/Llama-3.1-8B-Instruct");
});

test("catalog identity groups Qwen3-VL historical and Instruct artifacts without relabeling runs", () => {
  const historical = resolveRunBaseModelId(
    { provider: "ollama", model_name: "qwen3-vl:8b", model_revision: "qwen3-vl:8b" },
    catalog,
  );
  const instruct = resolveRunBaseModelId(
    {
      provider: "ollama",
      model_name: "qwen3-vl:8b-instruct",
      model_revision: "sha256:0533d74300e4",
    },
    catalog,
  );

  assert.equal(historical, instruct);
  assert.equal(instruct, "Qwen/Qwen3-VL-8B-Instruct");
});

test("uncatalogued runs use revision identity before the configuration fallback", () => {
  assert.equal(
    resolveRunBaseModelId(
      { provider: "provider", model_name: "alias", model_revision: "org/base@immutable-revision" },
      catalog,
    ),
    "org/base",
  );
  assert.equal(
    resolveRunBaseModelId(
      { provider: "provider", model_name: "alias", model_revision: "immutable-revision" },
      catalog,
    ),
    "run::provider::alias",
  );
});
