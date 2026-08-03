import assert from "node:assert/strict";
import test from "node:test";

import { formatBytes } from "../src/lib/format.ts";

test("formatBytes reports binary artifact sizes without implying decimal units", () => {
  assert.equal(formatBytes(0), "0 B");
  assert.equal(formatBytes(1024), "1.00 KiB");
  assert.equal(formatBytes(7703795680), "7.17 GiB");
  assert.equal(formatBytes(undefined), "Unavailable");
});
