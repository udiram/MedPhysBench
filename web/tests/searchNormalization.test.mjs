import assert from "node:assert/strict";
import test from "node:test";
import { matchesSearchText, normalizeSearchText } from "../src/lib/searchNormalization.ts";

test("model search treats punctuation and spacing as presentation details", () => {
  assert.equal(normalizeSearchText("GPT‑5.6 Sol"), "gpt 5 6 sol");
  assert.equal(matchesSearchText("GPT-5.6 Sol", "gpt 5.6"), true);
  assert.equal(matchesSearchText("GPT-5.6 Sol", "gpt5.6"), true);
  assert.equal(matchesSearchText("GPT-5.6 Sol", "GPT‑5.6"), true);
  assert.equal(matchesSearchText("GPT-5.6 Sol", "gpt 5.5"), false);
});

test("provider and model identifiers remain searchable across separators", () => {
  assert.equal(matchesSearchText("deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B", "deepseek r1"), true);
  assert.equal(matchesSearchText("meta-llama/llama-4-scout-17b-16e-instruct", "llama 4 scout"), true);
  assert.equal(matchesSearchText("Groq", "groq"), true);
});

test("blank normalized queries do not filter candidates", () => {
  assert.equal(matchesSearchText("any model", "---"), true);
});
