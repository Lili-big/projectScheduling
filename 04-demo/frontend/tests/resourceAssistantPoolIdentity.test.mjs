import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = resolve(import.meta.dirname, "..");

function toDataUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

async function loadDomain() {
  const path = resolve(root, "src/domain/resourceAssistant.ts");
  const rawSource = readFileSync(path, "utf8").replace(
    /import \{ resourceTypeLabel \} from "\.\/resources";/,
    "const resourceTypeLabel = (value) => value;",
  );
  const source = ts.transpileModule(rawSource, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
    fileName: path,
  }).outputText;
  return import(toDataUrl(source));
}

function plan() {
  return {
    scenario_id: "plan-1",
    target_workpoint_id: "WP-A",
    target_workpoint_name: "工点 A",
    generation_source: "fallback",
    changed_from_standard: false,
    solve_status: "ready_to_solve",
    resource_pools: [
      { id: "shared-a", type: "team-x", label: "一区共享", scope_mode: "PROJECT_SHARED", quantity: 1, max_quantity: 3, enabled: true },
      { id: "shared-b", type: "team-x", label: "二区共享", scope_mode: "PROJECT_SHARED", quantity: 2, max_quantity: 4, enabled: true },
      { id: "local-a", type: "team-x", label: "工点班组", scope_mode: "WORKPOINT_EXCLUSIVE", workpoint_id: "WP-A", quantity: 1, max_quantity: 2, enabled: true },
    ],
  };
}

test("quantity edits update only the selected pool id", async () => {
  const { normalizePlanResourcePoolQuantity } = await loadDomain();
  const updated = normalizePlanResourcePoolQuantity(plan(), "shared-b", 4);
  assert.deepEqual(updated.resource_pools.map((pool) => [pool.id, pool.quantity]), [
    ["shared-a", 1],
    ["shared-b", 4],
    ["local-a", 1],
  ]);
  assert.equal(updated.solve_status, "stale");
});

test("assistant UI only exposes scoped updates for the selected local workpoint", () => {
  const panel = readFileSync(resolve(root, "src/features/resourceAssistant/ResourceAssistantPanel.tsx"), "utf8");
  const card = readFileSync(resolve(root, "src/features/resourceAssistant/ResourcePlanCard.tsx"), "utf8");
  assert.match(panel, /resource_updates:\s*\{\}/);
  assert.match(panel, /scoped_resource_updates:\s*\[\{ resource_pool_id: resourcePoolId, workpoint_id: workpointId, quantity \}\]/);
  assert.match(panel, /workpointId !== plan\.target_workpoint_id/);
  assert.match(card, /editableResourcePoolsForWorkpoint\(plan\)/);
  assert.doesNotMatch(card, /项目共享总量/);
});
