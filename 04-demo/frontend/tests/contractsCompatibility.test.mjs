import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const fixture = JSON.parse(readFileSync(resolve(root, "tests/fixtures/architecture/frontend-baseline.json"), "utf8"));

function names(path, seen = new Set()) {
  if (seen.has(path)) return [];
  seen.add(path);
  const value = readFileSync(path, "utf8");
  const result = new Set([...value.matchAll(/^export\s+(?:type|interface|enum|class|const|function)\s+([A-Za-z_$][\w$]*)/gm)].map((match) => match[1]));
  for (const match of value.matchAll(/^export\s+\*\s+from\s+["']([^"']+)["']/gm)) {
    const base = resolve(path, "..", match[1]);
    for (const candidate of [`${base}.ts`, resolve(base, "index.ts")]) {
      try { for (const name of names(candidate, seen)) result.add(name); break; } catch {}
    }
  }
  return [...result].sort();
}

test("legacy scheduler types re-export all frozen contract names", () => {
  assert.deepEqual(names(resolve(root, "src/types/scheduler.ts")), fixture.public_contracts.scheduler_type_exports);
});

test("domain contract entrypoints exist and reference the canonical module", () => {
  for (const file of ["core.ts", "project.ts", "scheduling.ts", "assistants.ts", "planControl.ts", "girder.ts"]) {
    assert.match(readFileSync(resolve(root, "src/contracts", file), "utf8"), /from\s+["']\.\/scheduler["']/);
  }
});
