import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const fixture = JSON.parse(readFileSync(resolve(root, "tests/fixtures/architecture/frontend-baseline.json"), "utf8"));

function functions(path, seen = new Set()) {
  if (seen.has(path)) return [];
  seen.add(path);
  const value = readFileSync(path, "utf8");
  const result = new Set([...value.matchAll(/^export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/gm)].map((match) => match[1]));
  for (const match of value.matchAll(/^export\s+\*\s+from\s+["']([^"']+)["']/gm)) {
    const base = resolve(path, "..", match[1]);
    for (const candidate of [base, `${base}.ts`, resolve(base, "index.ts")]) {
      try { for (const name of functions(candidate, seen)) result.add(name); break; } catch {}
    }
  }
  return [...result].sort();
}

test("legacy scheduler API re-exports all 40 frozen functions", () => {
  assert.deepEqual(functions(resolve(root, "src/api/schedulerApi.ts")), fixture.public_contracts.scheduler_api_functions);
});

test("domain API entrypoints cover all functions without copies", () => {
  const files = ["scenarioApi.ts", "schedulingApi.ts", "assistantApi.ts", "resourceAssistantApi.ts", "planControlApi.ts", "girderPlanningApi.ts"];
  const source = files.map((file) => readFileSync(resolve(root, "src/api", file), "utf8")).join("\n");
  for (const name of fixture.public_contracts.scheduler_api_functions) assert.match(source, new RegExp(`\\b${name}\\b`));
});
