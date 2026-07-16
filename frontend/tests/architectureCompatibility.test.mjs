import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";


const frontendRoot = resolve(import.meta.dirname, "..");
const fixture = JSON.parse(readFileSync(resolve(frontendRoot, "tests/fixtures/architecture/frontend-baseline.json"), "utf8"));

function source(path) {
  return readFileSync(resolve(frontendRoot, path), "utf8");
}

function exportsOf(value) {
  const names = new Set();
  for (const match of value.matchAll(/^export\s+(?:async\s+)?(?:declare\s+)?(?:type|interface|enum|class|const|let|function)\s+([A-Za-z_$][\w$]*)/gm)) names.add(match[1]);
  for (const match of value.matchAll(/^export\s*\{([^}]+)\}/gms)) {
    for (const item of match[1].split(",")) {
      const name = item.trim().split(/\s+as\s+/).at(-1)?.trim();
      if (name) names.add(name);
    }
  }
  return [...names].sort();
}

function resolveModule(fromPath, specifier) {
  const base = resolve(fromPath, "..", specifier);
  for (const candidate of [base, `${base}.ts`, `${base}.tsx`, resolve(base, "index.ts"), resolve(base, "index.tsx")]) {
    try {
      readFileSync(candidate, "utf8");
      return candidate;
    } catch {}
  }
  return null;
}

function exportsFromFile(path, seen = new Set()) {
  if (seen.has(path)) return [];
  seen.add(path);
  const value = readFileSync(path, "utf8");
  const names = new Set(exportsOf(value));
  for (const match of value.matchAll(/^export\s+\*\s+from\s+["']([^"']+)["']/gm)) {
    const target = resolveModule(path, match[1]);
    if (target) for (const name of exportsFromFile(target, seen)) names.add(name);
  }
  return [...names].sort();
}

function apiFunctionsFromFile(path, seen = new Set()) {
  if (seen.has(path)) return [];
  seen.add(path);
  const value = readFileSync(path, "utf8");
  const names = new Set([...value.matchAll(/^export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/gm)].map((match) => match[1]));
  for (const match of value.matchAll(/^export\s+\*\s+from\s+["']([^"']+)["']/gm)) {
    const target = resolveModule(path, match[1]);
    if (target) for (const name of apiFunctionsFromFile(target, seen)) names.add(name);
  }
  return [...names].sort();
}

test("legacy scheduler types preserve all public exports", () => {
  assert.deepEqual(exportsFromFile(resolve(frontendRoot, "src/types/scheduler.ts")), fixture.public_contracts.scheduler_type_exports);
});

test("legacy scheduler API preserves all 40 public functions", () => {
  const names = apiFunctionsFromFile(resolve(frontendRoot, "src/api/schedulerApi.ts"));
  assert.equal(names.length, 40);
  assert.deepEqual(names, fixture.public_contracts.scheduler_api_functions);
});

test("root App default export and scenario invalidation remain wired", () => {
  assert.match(source("src/App.tsx"), /export\s+default\s+App\s*;?|export\s*\{\s*default\s*\}\s*from/);
  const app = source("src/app/Workspace.tsx");
  assert.match(app, /setGenerated\(null\)/);
  assert.match(app, /setSolveResult\(null\)/);
  assert.match(app, /setComparison\(null\)/);
  assert.match(app, /setIntegratedSnapshot/);
  assert.match(app, /scenarioFingerprintForSolve/);
});
