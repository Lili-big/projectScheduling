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

test("resource assistant API exposes the 059 local scenario-only initializer", () => {
  const source = readFileSync(resolve(root, "src/api/resourceAssistantApi.ts"), "utf8");
  const implementation = readFileSync(resolve(root, "src/api/_schedulerApi.ts"), "utf8");
  assert.match(source, /initializeAiWorkpointResources/);
  assert.match(implementation, /initialize-workpoint-resources/);
  const initializer = implementation.match(/export function initializeAiWorkpointResources[\s\S]*?\n\}/)?.[0] ?? "";
  assert.match(initializer, /AiWorkpointResourceInitializationRequest/);
  assert.doesNotMatch(initializer, /api.?key|authorization/i);
});

test("scheduling API keeps bodies compatible while adding optional workpoint query", () => {
  const api = readFileSync(resolve(root, "src/api/_schedulerApi.ts"), "utf8");
  assert.match(api, /function schedulingPath\(path: string, workpointId\?: string \| null\)/);
  assert.match(api, /\?workpoint_id=\$\{encodeURIComponent\(normalized\)\}/);
  assert.match(api, /schedulingPath\("\/api\/generate-schedule-input", workpointId\)/);
  assert.match(api, /schedulingPath\("\/api\/solve-scenario", workpointId\)/);
  assert.match(api, /schedulingPath\("\/api\/solve-min-resources", workpointId\)/);
  assert.match(api, /schedulingPath\("\/api\/solve-resource-cost", workpointId\)/);
});

test("demo API mirror exposes the v2 dual-carriageway girder contract", () => {
  const mirror = readFileSync(resolve(root, "..", "tools", "demo-api-mirror", "api.mts"), "utf8");
  assert.match(mirror, /girder-plan-line-graph\/v2/);
  assert.match(mirror, /R0:left/);
  assert.match(mirror, /R0:right/);
  assert.match(mirror, /spatial_group_id/);
  assert.match(mirror, /placement_source/);
  assert.match(mirror, /yard\.deployment_node_id/);
  assert.doesNotMatch(mirror, /R0:unknown|T1:unknown/);
});

test("demo API mirror keeps unified fixed and minimum-resource metadata honest", () => {
  const mirror = readFileSync(resolve(root, "..", "tools", "demo-api-mirror", "api.mts"), "utf8");
  assert.match(mirror, /function solveMinimumResourcesScenario/);
  assert.match(mirror, /unified_fixed_resource_single_stage/);
  assert.match(mirror, /global_minimum_resource_search_unavailable/);
  assert.match(mirror, /function solveMinimumResourcesScenario[\s\S]*target_status:\s*"unconfirmed"/);
  assert.match(mirror, /solved\.result\.status = "UNKNOWN"/);
  assert.match(mirror, /candidate_verified:\s*false/);
  assert.match(mirror, /retry_attempted:\s*false/);
  assert.match(mirror, /alternative_results:\s*\[\]/);
  assert.doesNotMatch(mirror, /recommended_resources_verified/);
});
