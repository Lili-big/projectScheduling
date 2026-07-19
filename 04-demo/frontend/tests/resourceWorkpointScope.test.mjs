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

test("workpoint-local pools upsert by workpoint and type while preserving zero quantity", async () => {
  const {
    localResourcePoolsForWorkpoint,
    upsertWorkpointLocalResource,
  } = await loadResources();
  const initial = [pool({ id: "shared-x", type: "team-x", scope_mode: "PROJECT_SHARED" })];
  const added = upsertWorkpointLocalResource(initial, "WP-A", {
    id: "local-a-x",
    type: "team-x",
    label: "A 点班组",
    quantity: 0,
    max_quantity: 3,
    enabled: true,
  });
  const updated = upsertWorkpointLocalResource(added, "WP-A", {
    id: "ignored-new-id",
    type: "team-x",
    label: "A 点班组",
    quantity: 2,
    max_quantity: 4,
    enabled: false,
  });

  assert.equal(updated.length, 2);
  assert.deepEqual(localResourcePoolsForWorkpoint(updated, "WP-A").map((item) => ({
    id: item.id,
    workpoint_id: item.workpoint_id,
    quantity: item.quantity,
    max_quantity: item.max_quantity,
    enabled: item.enabled,
    authorized_workpoint_ids: item.authorized_workpoint_ids,
    workpoint_overrides: item.workpoint_overrides,
  })), [{
    id: "local-a-x",
    workpoint_id: "WP-A",
    quantity: 2,
    max_quantity: 4,
    enabled: false,
    authorized_workpoint_ids: null,
    workpoint_overrides: [],
  }]);
});

test("catalog projection is deterministic and same-type shared pools remain independent", async () => {
  const {
    resourceCatalogProjection,
    sharedResourcePools,
  } = await loadResources();
  const shared = [
    pool({ id: "pool-b", type: "team-x", label: "二区班组", scope_mode: "PROJECT_SHARED", authorized_workpoint_ids: ["WP-B"] }),
    pool({ id: "pool-a", type: "team-x", label: "一区班组", scope_mode: "PROJECT_SHARED", authorized_workpoint_ids: ["WP-A"] }),
  ];
  const processes = [
    { id: "process-b", name: "工艺乙", component_type: "pier_body", resource_type: "team-y" },
    { id: "process-a", name: "工艺甲", component_type: "cap", resource_type: "team-x" },
  ];

  assert.deepEqual(sharedResourcePools(shared).map((item) => item.id), ["pool-a", "pool-b"]);
  assert.deepEqual(resourceCatalogProjection(processes, shared).map((item) => item.type), ["cap_team", "pier_body_team", "team-x"]);
});

test("fingerprint distinguishes workpoint identity but ignores pool ordering", async () => {
  const { resourcePoolsSemanticFingerprint } = await loadResources();
  const localA = pool({ id: "local-a", scope_mode: "WORKPOINT_EXCLUSIVE", workpoint_id: "WP-A" });
  const localB = pool({ id: "local-b", scope_mode: "WORKPOINT_EXCLUSIVE", workpoint_id: "WP-B" });
  assert.equal(
    resourcePoolsSemanticFingerprint([localA, localB]),
    resourcePoolsSemanticFingerprint([localB, localA]),
  );
  assert.notEqual(
    resourcePoolsSemanticFingerprint([localA]),
    resourcePoolsSemanticFingerprint([{ ...localA, workpoint_id: "WP-C" }]),
  );
});

test("resource page separates workpoint-local rows from the shared-pool range editor", () => {
  const source = readFileSync(resolve(root, "src/features/resources/ResourcesTab.tsx"), "utf8");
  assert.match(source, /工点资源与共享池/);
  assert.match(source, /scope_mode:\s*"WORKPOINT_EXCLUSIVE"/);
  assert.match(source, /workpoint_id:\s*selectedWorkpoint\.workpoint_id/);
  assert.match(source, /task\.bridge_id === selectedWorkpoint\?\.workpoint_id/);
  assert.match(source, /范围共享资源池/);
  assert.match(source, /同类型可建立多个独立池/);
  assert.doesNotMatch(source, /该资源适用于哪些工点|获准工点/);
});
