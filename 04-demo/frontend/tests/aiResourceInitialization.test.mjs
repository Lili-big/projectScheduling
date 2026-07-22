import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = resolve(import.meta.dirname, "..");
const resourcesTab = readFileSync(resolve(root, "src/features/resources/ResourcesTab.tsx"), "utf8");
const workspace = readFileSync(resolve(root, "src/app/Workspace.tsx"), "utf8");
const api = readFileSync(resolve(root, "src/api/_schedulerApi.ts"), "utf8");

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

function localPool(patch = {}) {
  return {
    id: "workpoint-WP-A-rotary_drill",
    type: "rotary_drill",
    label: "旋挖钻机",
    resource_mode: "LIMITED",
    scope_mode: "WORKPOINT_EXCLUSIVE",
    workpoint_id: "WP-A",
    quantity: 2,
    max_quantity: 3,
    authorized_workpoint_ids: null,
    workpoint_overrides: [],
    calendar_id: "continuous",
    enabled: true,
    compatible_process_ids: ["pile-rotary"],
    ...patch,
  };
}

test("resource header exposes one gated AI initialization action beside the existing save action", () => {
  assert.match(resourcesTab, /aria-label="AI快速配置工装"/);
  assert.match(resourcesTab, /className="resource-title-actions"/);
  assert.ok(resourcesTab.indexOf('aria-label="AI快速配置工装"') < resourcesTab.indexOf("aria-label={saveLabel}"));
  assert.match(resourcesTab, /aiRequestInFlightRef\.current/);
  assert.match(resourcesTab, /aiInitializationState\.status === "loading"/);
  assert.match(resourcesTab, /workpointState\.versionId !== \(scenario\.project_data_version_id \?\? ""\)/);
  assert.match(resourcesTab, /initializeAiWorkpointResources\(\{ scenario \}\)/);
  assert.doesNotMatch(resourcesTab, /initializeAiWorkpointResources\([\s\S]*?api.?key/i);
});

test("API client sends only the current scenario to the local initializer endpoint", () => {
  assert.match(api, /initializeAiWorkpointResources\([\s\S]*?request:\s*AiWorkpointResourceInitializationRequest/);
  assert.match(api, /initialize-workpoint-resources/);
  assert.doesNotMatch(api.match(/export function initializeAiWorkpointResources[\s\S]*?\n\}/)?.[0] ?? "", /api.?key|authorization/i);
});

test("AI additions merge once while every existing resource object remains untouched", async () => {
  const { mergeAiWorkpointResourcePools } = await loadResources();
  const existing = localPool({
    id: "existing-a",
    type: "cap_team",
    label: "人工确认承台班组",
    quantity: 7,
    max_quantity: 9,
    enabled: false,
    incremental_unit_cost: 123,
    custom_user_field: "keep-byte-for-byte",
  });
  const addition = localPool();
  const before = structuredClone(existing);
  const merged = mergeAiWorkpointResourcePools([existing], [addition]);

  assert.equal(merged.length, 2);
  assert.equal(merged[0], existing);
  assert.deepEqual(merged[0], before);
  assert.equal(merged[1].workpoint_id, "WP-A");
  assert.equal(merged[1].type, "rotary_drill");
});

test("ID or workpoint-resource conflicts reject the entire AI batch without mutation", async () => {
  const { mergeAiWorkpointResourcePools } = await loadResources();
  const existing = localPool({ id: "existing-a", type: "cap_team" });
  const additions = [
    localPool({ id: "new-a", type: "rotary_drill" }),
    localPool({ id: "new-b", type: "cap_team" }),
  ];
  const before = structuredClone(existing);

  assert.throws(
    () => mergeAiWorkpointResourcePools([existing], additions),
    /冲突/,
  );
  assert.deepEqual(existing, before);
});

test("late responses require matching project version and resource semantic fingerprint", () => {
  assert.match(resourcesTab, /response\.project_data_version_id !== versionId/);
  assert.match(resourcesTab, /resourcePoolsSemanticFingerprint\(latestScenario\.resource_pools\) !== requestResourceFingerprint/);
  assert.match(workspace, /response\.project_data_version_id !== requestVersionId/);
  assert.match(workspace, /mergeAiWorkpointResourcePools/);
  assert.match(workspace, /setResourcesDirty\(true\)/);
});

test("successful AI initialization remains unsaved and uses the existing per-workpoint editor", () => {
  assert.match(resourcesTab, /配置已填入当前页面，尚未保存，请逐工点确认后点击“保存”/);
  assert.match(resourcesTab, /resource-workpoint-nav/);
  assert.doesNotMatch(resourcesTab, /全量预览|AI推荐保存|保存AI推荐/);
  const initializeFunction = resourcesTab.match(/async function initializeAllWorkpointResources\(\)[\s\S]*?\n  \}/)?.[0] ?? "";
  assert.doesNotMatch(initializeFunction, /onSaveLocalConfig/);
});
