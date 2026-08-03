import assert from "node:assert/strict";
import test from "node:test";

import { DATA_ASSET_REVISION, versionedDataUrl } from "../src/lib/dataAssets.ts";

test("public data URLs are pinned to an immutable release revision", () => {
  assert.match(DATA_ASSET_REVISION, /^[0-9a-f]{7,40}$/);
  assert.equal(
    versionedDataUrl("/data/fleet_status.json"),
    `/data/fleet_status.json?release=${DATA_ASSET_REVISION}`,
  );
  assert.equal(
    versionedDataUrl("/data/results.json?view=all"),
    `/data/results.json?view=all&release=${DATA_ASSET_REVISION}`,
  );
});
