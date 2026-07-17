import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const features = resolve(root, "src/features");

function files(path) {
  return readdirSync(path).flatMap((name) => {
    const item = resolve(path, name);
    return statSync(item).isDirectory() ? files(item) : /\.tsx?$/.test(item) ? [item] : [];
  });
}

test("plan control and girder planning expose public feature entrypoints", () => {
  for (const name of ["planControl", "girderPlanning"]) {
    assert.equal(existsSync(resolve(features, name, "index.ts")), true, `${name} requires index.ts`);
  }
});

test("features do not import sibling feature internals", () => {
  for (const path of files(features)) {
    const source = readFileSync(path, "utf8");
    assert.doesNotMatch(source, /from\s+["'](?:\.\.\/)+(?:[^"']*\/)?features\/(?![^/"']+["'])/);
  }
});
