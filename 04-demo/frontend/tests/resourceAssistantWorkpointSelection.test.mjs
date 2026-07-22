import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";


const root = resolve(import.meta.dirname, "..");
const panel = readFileSync(resolve(root, "src/features/resourceAssistant/ResourceAssistantPanel.tsx"), "utf8");
const workspace = readFileSync(resolve(root, "src/app/Workspace.tsx"), "utf8");
const card = readFileSync(resolve(root, "src/features/resourceAssistant/ResourcePlanCard.tsx"), "utf8");
const domain = readFileSync(resolve(root, "src/domain/resourceAssistant.ts"), "utf8");
const contracts = readFileSync(resolve(root, "src/contracts/scheduler.ts"), "utf8");


test("AI comparison requires an explicit stable workpoint before generation", () => {
  assert.match(contracts, /target_workpoint_id: string;/);
  assert.match(panel, /<option value="">请选择工点<\/option>/);
  assert.match(panel, /disabled=\{!targetWorkpoint \|\| generating/);
  assert.match(panel, /target_workpoint_id: requestedWorkpointId/);
  assert.match(workspace, /workpoints=\{currentResourceWorkpoints\}/);
  assert.match(panel, /workpointOptionLabel\(workpoint\.workpoint_id, workpoint\.workpoint_name/);
  assert.match(panel, /workpoints\.filter\([\s\S]*?schedule_support === "bridge_supported"/);
  assert.doesNotMatch(panel, /scenario\?\.project\.bridges/);
});


test("AI comparison makes the single-workpoint resource boundary visible", () => {
  assert.match(panel, /AI 仅调整“\$\{targetWorkpoint\.workpoint_name\}”的本地资源；求解和指标仍为全项目口径/);
  assert.match(card, /资源推进工点：\{plan\.target_workpoint_name\}/);
  assert.match(card, /以下指标为全项目排程结果/);
  assert.match(domain, /editableResourcePoolsForWorkpoint/);
  assert.match(domain, /scope_mode \?\? "PROJECT_SHARED"\) !== "WORKPOINT_EXCLUSIVE"/);
});


test("workpoint changes invalidate the whole comparison session and isolate late responses", () => {
  assert.match(panel, /scopeRequestRef\.current \+= 1/);
  assert.match(panel, /setPlanResults\(\[\]\)/);
  assert.match(panel, /setComparison\(null\)/);
  assert.match(panel, /setRecommendation\(null\)/);
  assert.match(panel, /setDetailPlanId\(null\)/);
  assert.match(panel, /setLlmContextDownload\(null\)/);
  assert.match(panel, /scopeId !== scopeRequestRef\.current/);
});
