import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const workspace = readFileSync(new URL("../src/features/projectMasterData/ProjectMasterDataWorkspace.tsx", import.meta.url), "utf8");
const preview = readFileSync(new URL("../src/features/projectMasterData/ImportPreview.tsx", import.meta.url), "utf8");
const navigation = readFileSync(new URL("../src/features/layout/WorkspaceNavigation.tsx", import.meta.url), "utf8");
const parameterAssistant = readFileSync(new URL("../src/features/assistant/parameter/ParameterAssistantPanel.tsx", import.meta.url), "utf8");
const girder = readFileSync(new URL("../src/features/girderPlanning/GirderPlanningPanel.tsx", import.meta.url), "utf8");

test("project master workspace exposes complete snapshot workflow and hierarchy", () => {
  assert.match(workspace, /尚未建立项目主数据/);
  assert.match(workspace, /下载 Excel 模板/);
  assert.match(workspace, /ImportPreview/);
  assert.match(workspace, /VersionHistory/);
  assert.match(workspace, /WorkPointList/);
  assert.match(workspace, /WorkPointDetail/);
  assert.match(preview, /已知悉告警/);
  assert.match(preview, /确认并设为当前版本/);
});

test("navigation separates project master from AI parameter assistant and removes old imports", () => {
  assert.match(navigation, /projectFiles.+项目主数据/);
  assert.match(navigation, /parameterAssistant.+AI 参数助手/);
  assert.doesNotMatch(parameterAssistant, /导入桥梁结构参数/);
  assert.doesNotMatch(girder, /导入架梁工点/);
  assert.match(girder, /workpoint_id \+ side/);
});
