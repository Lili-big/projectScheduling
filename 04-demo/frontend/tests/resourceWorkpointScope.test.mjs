import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = resolve(import.meta.dirname, "..");

function toDataUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

async function loadResources() {
  const transpile = (path) => ts.transpileModule(readFileSync(path, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
    fileName: path,
  }).outputText;
  const constantsUrl = toDataUrl(transpile(resolve(root, "src/domain/constants.ts")));
  const source = transpile(resolve(root, "src/domain/resources.ts"))
    .replaceAll('from "./constants"', `from "${constantsUrl}"`);
  return import(toDataUrl(source));
}

function pool(patch = {}) {
  return {
    id: "pool-1",
    type: "resource-type",
    label: "资源一",
    resource_mode: "LIMITED",
    quantity: 2,
    max_quantity: 4,
    calendar_id: "continuous",
    enabled: true,
    compatible_process_ids: [],
    ...patch,
  };
}

test("legacy pools migrate generically to project shared while null and empty authorization stay distinct", async () => {
  const { normalizeResourcePoolForWorkspace } = await loadResources();

  const migrated = normalizeResourcePoolForWorkspace(pool());
  assert.equal(migrated.scope_mode, "PROJECT_SHARED");
  assert.equal(migrated.authorized_workpoint_ids, null);
  assert.deepEqual(migrated.workpoint_overrides, []);
  assert.equal(migrated.quantity, 2);
  assert.equal(normalizeResourcePoolForWorkspace(pool({ authorized_workpoint_ids: null })).authorized_workpoint_ids, null);
  assert.deepEqual(normalizeResourcePoolForWorkspace(pool({ authorized_workpoint_ids: [] })).authorized_workpoint_ids, []);
});

test("exclusive workpoints inherit global values, accept partial overrides and restore inheritance", async () => {
  const {
    effectiveWorkpointResource,
    restoreWorkpointResourceInheritance,
    setWorkpointResourceOverride,
  } = await loadResources();
  const exclusive = pool({
    scope_mode: "WORKPOINT_EXCLUSIVE",
    authorized_workpoint_ids: ["WP-B", "WP-A", "WP-A"],
  });

  assert.deepEqual(effectiveWorkpointResource(exclusive, "WP-B"), {
    workpointId: "WP-B",
    enabled: true,
    quantity: 2,
    maxQuantity: 4,
    inheritanceSource: "inherited",
  });

  const overridden = setWorkpointResourceOverride(exclusive, "WP-B", { quantity: 3 });
  assert.deepEqual(overridden.authorized_workpoint_ids, ["WP-A", "WP-B"]);
  assert.deepEqual(overridden.workpoint_overrides, [{ workpoint_id: "WP-B", quantity: 3 }]);
  assert.deepEqual(effectiveWorkpointResource(overridden, "WP-B"), {
    workpointId: "WP-B",
    enabled: true,
    quantity: 3,
    maxQuantity: 4,
    inheritanceSource: "overridden",
  });

  const restored = restoreWorkpointResourceInheritance(overridden, "WP-B");
  assert.deepEqual(restored.workpoint_overrides, []);
  assert.equal(effectiveWorkpointResource(restored, "WP-B").inheritanceSource, "inherited");
});

test("scope normalization and fingerprint use stable sets without resource-name or id-format rules", async () => {
  const {
    normalizeResourcePoolForWorkspace,
    resourcePoolsSemanticFingerprint,
    resourcePoolScopeIssues,
  } = await loadResources();
  const left = pool({
    id: "arbitrary",
    scope_mode: "WORKPOINT_EXCLUSIVE",
    authorized_workpoint_ids: ["z", "a", "z"],
    workpoint_overrides: [
      { workpoint_id: "z", quantity: 3, max_quantity: null },
      { workpoint_id: "a", enabled: null, quantity: null, max_quantity: null },
    ],
  });
  const right = pool({
    id: "arbitrary",
    scope_mode: "WORKPOINT_EXCLUSIVE",
    authorized_workpoint_ids: ["a", "z"],
    workpoint_overrides: [{ workpoint_id: "z", max_quantity: null, quantity: 3 }],
  });

  assert.deepEqual(normalizeResourcePoolForWorkspace(left).authorized_workpoint_ids, ["a", "z"]);
  assert.equal(resourcePoolsSemanticFingerprint([left]), resourcePoolsSemanticFingerprint([right]));
  assert.deepEqual(resourcePoolScopeIssues(left, ["a", "z"]), []);
  assert.deepEqual(resourcePoolScopeIssues(right, ["a"]), ["配置包含当前项目主数据版本之外的工点"]);
});

test("scenario normalization preserves explicit unlimited mode and standardizes scoped pools", async () => {
  const { normalizeScenarioResourcePools } = await loadResources();
  const scenario = {
    marker: "scenario",
    resource_pools: [pool({ resource_mode: "UNLIMITED", quantity: null, max_quantity: null })],
  };
  const normalized = normalizeScenarioResourcePools(scenario);

  assert.equal(normalized.resource_pools[0].resource_mode, "UNLIMITED");
  assert.equal(normalized.resource_pools[0].scope_mode, "PROJECT_SHARED");
  assert.equal(normalized.resource_pools[0].authorized_workpoint_ids, null);
});
