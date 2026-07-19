import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const controller = readFileSync(resolve(root, "src/app/useWorkspaceController.ts"), "utf8");
const scenario = readFileSync(resolve(root, "src/app/workflows/scenarioWorkflow.ts"), "utf8");
const solve = readFileSync(resolve(root, "src/app/workflows/solveWorkflow.ts"), "utf8");
const workspace = readFileSync(resolve(root, "src/app/Workspace.tsx"), "utf8");

test("workspace controller coordinates busy, errors and fingerprint invalidation", () => {
  assert.match(controller, /useState<BusyState>/);
  assert.match(controller, /setError/);
  assert.match(controller, /previousScenarioFingerprintRef/);
  assert.match(controller, /onScenarioInvalidated/);
});

test("scenario and solve workflows expose stable orchestration seams", () => {
  assert.match(scenario, /export async function loadScenarioWorkflow/);
  assert.match(scenario, /export async function generateScheduleWorkflow/);
  assert.match(scenario, /export function scenarioFingerprintForSolve/);
  assert.match(solve, /export async function solveScenarioWorkflow/);
  assert.match(solve, /fallbackTargetDaysForScenario/);
});

test("resource mutations use pool identity and retain scenario invalidation", () => {
  assert.match(workspace, /function upsertResourcePool\(poolId: string/);
  assert.match(workspace, /function addResourcePool\(pool: ResourcePool/);
  assert.match(workspace, /function removeResourcePool\(poolId: string/);
  assert.doesNotMatch(workspace, /function updateResourcePool\(index: number/);
  assert.match(controller, /invalidationHandlerRef\.current\(\)/);
});
