import assert from "node:assert/strict";
import test from "node:test";

import { formatBytes, normalizeModelDisplayName } from "../src/lib/format.ts";

test("formatBytes reports binary artifact sizes without implying decimal units", () => {
  assert.equal(formatBytes(0), "0 B");
  assert.equal(formatBytes(1024), "1.00 KiB");
  assert.equal(formatBytes(7703795680), "7.17 GiB");
  assert.equal(formatBytes(undefined), "Unavailable");
});

test("GPT-5.6 system names remain distinct but share professional display casing", () => {
  assert.equal(normalizeModelDisplayName("gpt-5.6-sol [effort=high]"), "GPT-5.6 [effort=high]");
  assert.equal(normalizeModelDisplayName("gpt-5.6-terra [effort=high]"), "GPT-5.6 Terra [effort=high]");
});
