#!/usr/bin/env node

import { existsSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";

const frontendRoot = resolve(import.meta.dirname, "..");
const dist = resolve(frontendRoot, "dist");
const assets = resolve(dist, "assets");
const threshold = 1.05;
const baseline = { js: 470.62 * 1000, css: 86.82 * 1000 };

if (!existsSync(resolve(dist, "index.html")) || !existsSync(assets)) {
  throw new Error("frontend/dist is incomplete; run npm run build first");
}

function largest(extension) {
  const files = readdirSync(assets)
    .filter((name) => name.endsWith(extension))
    .map((name) => ({ name, bytes: statSync(resolve(assets, name)).size }))
    .sort((left, right) => right.bytes - left.bytes);
  if (!files.length) throw new Error(`no ${extension} output found`);
  return files[0];
}

const js = largest(".js");
const css = largest(".css");
for (const [kind, output] of Object.entries({ js, css })) {
  const limit = baseline[kind] * threshold;
  if (output.bytes > limit) {
    throw new Error(`${kind} budget exceeded: ${output.name} ${output.bytes} > ${Math.floor(limit)} bytes`);
  }
}

console.log(`build budget: OK js=${(js.bytes / 1000).toFixed(2)}kB css=${(css.bytes / 1000).toFixed(2)}kB threshold=5%`);
