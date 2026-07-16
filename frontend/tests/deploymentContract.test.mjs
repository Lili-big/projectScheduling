import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "../..");

test("Vite development proxy and production API base remain explicit", () => {
  const vite = readFileSync(resolve(root, "frontend/vite.config.ts"), "utf8");
  const client = readFileSync(resolve(root, "frontend/src/api/client.ts"), "utf8");
  assert.match(vite, /"\/api": "http:\/\/127\.0\.0\.1:8000"/);
  assert.match(client, /VITE_API_BASE_URL/);
});

test("Netlify remains a Node 22 static frontend deployment with SPA fallback", () => {
  const config = readFileSync(resolve(root, "netlify.toml"), "utf8");
  assert.match(config, /publish = "frontend\/dist"/);
  assert.match(config, /NODE_VERSION = "22"/);
  assert.match(config, /from = "\/\*"[\s\S]*to = "\/index\.html"[\s\S]*status = 200/);
  assert.doesNotMatch(config, /functions\s*=/);
});
