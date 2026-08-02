import assert from "node:assert/strict";
import test from "node:test";

import { getUrlParam, readEnumParam, setUrlParams } from "../src/lib/urlState.ts";

function browserHarness(initialUrl) {
  let current = new URL(initialUrl);
  const calls = [];
  globalThis.window = {
    get location() {
      return current;
    },
    history: {
      pushState(_state, _unused, next) {
        calls.push(["push", next]);
        current = new URL(next, current);
      },
      replaceState(_state, _unused, next) {
        calls.push(["replace", next]);
        current = new URL(next, current);
      },
    },
  };
  return { calls, current: () => current };
}

test.afterEach(() => {
  delete globalThis.window;
});

test("system canonicalization replaces the current URL without erasing unrelated state", () => {
  const harness = browserHarness("https://example.test/bench?release=real&fx_source=open#forensics");

  setUrlParams({ fx_model: "ollama::qwen", fx_source: null });

  assert.deepEqual(harness.calls, [["replace", "/bench?release=real&fx_model=ollama%3A%3Aqwen#forensics"]]);
  assert.equal(getUrlParam("release"), "real");
  assert.equal(getUrlParam("fx_source"), null);
});

test("meaningful filter changes push a navigable history entry", () => {
  const harness = browserHarness("https://example.test/bench?fx_source=open#forensics");

  setUrlParams({ fx_source: "closed", fx_provider: "codex-native" }, { history: "push" });

  assert.deepEqual(harness.calls, [["push", "/bench?fx_source=closed&fx_provider=codex-native#forensics"]]);
  assert.equal(harness.current().searchParams.get("fx_source"), "closed");
});

test("enum readers reject malformed deep-link values", () => {
  browserHarness("https://example.test/?fx_outcome=%3Cscript%3E");

  assert.equal(readEnumParam("fx_outcome", ["all", "safe_success", "unsafe"], "all"), "all");
});
