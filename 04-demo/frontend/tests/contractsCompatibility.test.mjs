import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const fixture = JSON.parse(readFileSync(resolve(root, "tests/fixtures/architecture/frontend-baseline.json"), "utf8"));
const schedulerContract = readFileSync(resolve(root, "src/contracts/scheduler.ts"), "utf8");
const displayState = readFileSync(resolve(root, "src/features/taskView/projectMasterDisplayState.ts"), "utf8");
const resourceScopeOpenApi = readFileSync(
  resolve(root, "..", "..", "03-requirements/specs/048-workpoint-first-resource-allocation/contracts/workpoint-resource-allocation.openapi.yaml"),
  "utf8",
);
const aiResourceInitializationOpenApi = readFileSync(
  resolve(root, "..", "..", "03-requirements/specs/059-ai-batch-resource-initialization/contracts/ai-workpoint-resource-initialization.openapi.yaml"),
  "utf8",
);

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
  const resourceScopeAdditions = [
    "AiResourceQuantityRecommendation",
    "AiWorkpointResourceInitializationRequest",
    "AiWorkpointResourceInitializationResponse",
    "AiWorkpointResourceInitializationSummary",
    "AiWorkpointResourceRecommendation",
    "ResourcePoolQuantityResult",
    "ResourceScopeMode",
    "ScopedResourceQuantityUpdate",
    "WorkpointResourceOverride",
  ];
  assert.deepEqual(
    names(resolve(root, "src/types/scheduler.ts")),
    [...new Set([...fixture.public_contracts.scheduler_type_exports, ...resourceScopeAdditions])].sort(),
  );
});

test("domain contract entrypoints exist and reference the canonical module", () => {
  for (const file of ["core.ts", "project.ts", "scheduling.ts", "assistants.ts", "planControl.ts", "girder.ts"]) {
    assert.match(readFileSync(resolve(root, "src/contracts", file), "utf8"), /from\s+["']\.\/scheduler["']/);
  }
});

test("task-view contracts keep both component types and open generated-source metadata", () => {
  assert.match(schedulerContract, /\|\s*"cap_beam"/);
  assert.match(schedulerContract, /\|\s*"abutment_body"/);
  assert.match(schedulerContract, /source_summary:\s*Record<string, unknown>/);
  assert.match(displayState, /ProjectMasterDisplayState/);
  assert.match(displayState, /status:\s*"loading"/);
  assert.match(displayState, /status:\s*"ready"/);
  assert.match(displayState, /status:\s*"error"/);
});

test("resource-scope types align with the incremental contract and keep legacy inputs", () => {
  assert.match(resourceScopeOpenApi, /ResourceScopeMode:/);
  assert.match(resourceScopeOpenApi, /enum:\s*\[PROJECT_SHARED, WORKPOINT_EXCLUSIVE\]/);
  assert.match(schedulerContract, /export type ResourceScopeMode = "PROJECT_SHARED" \| "WORKPOINT_EXCLUSIVE"/);
  assert.match(schedulerContract, /export type WorkpointResourceOverride = \{/);
  assert.match(schedulerContract, /scope_mode\?: ResourceScopeMode/);
  assert.match(schedulerContract, /workpoint_id\?: string \| null/);
  assert.match(schedulerContract, /authorized_workpoint_ids\?: string\[\] \| null/);
  assert.match(schedulerContract, /workpoint_overrides\?: WorkpointResourceOverride\[\]/);
  assert.match(schedulerContract, /eligible_workpoint_ids:\s*string\[\]/);
  assert.match(schedulerContract, /exclusive_workpoint_id\?:\s*string \| null/);
  assert.match(schedulerContract, /export type ScopedResourceQuantityUpdate = \{/);
  assert.match(schedulerContract, /export type ResourcePoolQuantityResult = \{/);
  assert.match(schedulerContract, /resource_pool_id:\s*string/);
  assert.match(schedulerContract, /current_quantity:\s*number/);
  assert.match(schedulerContract, /recommended_quantity:\s*number/);
  assert.match(schedulerContract, /resource_updates:\s*Record<string, number>/);
  assert.match(schedulerContract, /scoped_resource_updates\?:\s*ScopedResourceQuantityUpdate\[\]/);
  assert.doesNotMatch(schedulerContract, /\bmin_quantity\b/);
});

test("AI resource comparison requires a target workpoint while old plans stay readable", () => {
  assert.match(
    schedulerContract,
    /export type ResourceAssistantInitialRequest = \{[\s\S]*?target_workpoint_id:\s*string;/,
  );
  assert.match(
    schedulerContract,
    /export type ResourceAssistantPlan = \{[\s\S]*?target_workpoint_id\?:\s*string \| null;/,
  );
  assert.match(
    schedulerContract,
    /export type ResourceAssistantPlan = \{[\s\S]*?target_workpoint_name\?:\s*string \| null;/,
  );
});

test("AI workpoint resource initialization types match the 059 scenario-only contract", () => {
  assert.match(aiResourceInitializationOpenApi, /initialize-workpoint-resources:/);
  assert.match(aiResourceInitializationOpenApi, /AiWorkpointResourceInitializationRequest:[\s\S]*?required:\s*\[scenario\]/);
  assert.match(schedulerContract, /export type AiWorkpointResourceInitializationRequest = \{\s*scenario:\s*ScenarioInput;\s*\}/);
  assert.match(schedulerContract, /export type AiWorkpointResourceInitializationResponse = \{[\s\S]*?resource_pools_to_add:\s*ResourcePool\[\]/);
  assert.match(schedulerContract, /export type AiWorkpointResourceInitializationSummary = \{[\s\S]*?added_resource_count:\s*number/);
  const requestType = schedulerContract.match(/export type AiWorkpointResourceInitializationRequest = \{[\s\S]*?\n\};/)?.[0] ?? "";
  assert.doesNotMatch(requestType, /api.?key|endpoint|authorization/i);
});
