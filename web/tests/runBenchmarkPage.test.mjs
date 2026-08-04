import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { after, before, test } from "node:test";
import react from "@vitejs/plugin-react";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const ROOT = path.resolve(import.meta.dirname, "..");
const fleetStatus = JSON.parse(fs.readFileSync(path.join(ROOT, "public/data/fleet_status.json"), "utf8"));
let server;
let RunBenchmarkPage;

before(async () => {
  server = await createServer({
    appType: "custom",
    configFile: false,
    logLevel: "silent",
    plugins: [react()],
    root: ROOT,
    server: { middlewareMode: true },
  });
  ({ RunBenchmarkPage } = await server.ssrLoadModule("/src/components/RunBenchmarkPage.tsx"));
});

after(async () => server?.close());

test("run page keeps the frozen backlog collapsed while linking exact access evidence", () => {
  const html = renderToStaticMarkup(React.createElement(RunBenchmarkPage, { fleetStatus }));

  assert.match(html, /Inspect the 50-model qualification backlog/);
  assert.match(html, /21<small> \/ 50<\/small>/);
  assert.match(
    html,
    /receipts\/access\/ollama-gpt-oss-120b-cloud-v1\/20260804T062816Z-629876562d6e\.json/,
  );
  assert.match(html, /Inspect access receipt · 629876562d6e/);
  assert.doesNotMatch(html, /qualification-backlog" open/);
});
