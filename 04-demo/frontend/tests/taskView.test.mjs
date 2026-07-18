import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const presenter = readFileSync(resolve(root, "src/features/taskView/presenter.ts"), "utf8");
const entrypoint = readFileSync(resolve(root, "src/features/taskView/index.ts"), "utf8");
const workspace = readFileSync(resolve(root, "src/features/taskView/TaskViewWorkspace.tsx"), "utf8");
const app = readFileSync(resolve(root, "src/app/Workspace.tsx"), "utf8");
const displayState = readFileSync(resolve(root, "src/features/taskView/projectMasterDisplayState.ts"), "utf8");

test("task view owns filtering and structure grouping presenters", () => {
  assert.match(presenter, /export function filterTaskViewRows/);
  assert.match(presenter, /structureText/);
  assert.match(presenter, /processText/);
  assert.match(presenter, /export function groupTaskRowsByStructure/);
});

test("task view exposes a public feature entrypoint", () => {
  assert.match(entrypoint, /export \* from "\.\/presenter"/);
  assert.match(entrypoint, /TaskViewWorkspace/);
  assert.match(workspace, /task-view-grid/);
});

test("task view enriches project-master workpoint names and side labels", () => {
  assert.match(presenter, /export function buildProjectMasterTaskViewMaps/);
  assert.match(presenter, /workpoint\.workpoint_name/);
  assert.match(presenter, /structure\.section_name/);
  assert.match(presenter, /sideLabels\[side\]/);
  assert.match(app, /getProjectMasterWorkpoint/);
  assert.match(app, /scenario\.project_data_version_id/);
  assert.match(app, /buildProjectMasterTaskViewMaps/);
});

test("project-master display state owns generic loading, ready, error and retry behavior", () => {
  assert.match(displayState, /createProjectMasterDisplayIdentity/);
  assert.match(displayState, /createProjectMasterDisplayCoordinator/);
  assert.match(displayState, /"loading"/);
  assert.match(displayState, /"ready"/);
  assert.match(displayState, /"error"/);
  assert.match(displayState, /retry/);
  assert.match(workspace, /displayStatus/);
  assert.match(workspace, /onRetry/);
});

test("task view never exposes raw project-master ids or placeholders as visible names", () => {
  assert.doesNotMatch(app, /bridge\?\.name\s*\?\?\s*task\.bridge_id/);
  assert.doesNotMatch(app, /section\?\.name\s*\?\?\s*task\.work_section_id/);
  assert.doesNotMatch(app, /getProjectMasterWorkpoint\([^)]*\)\.catch\(\(\)\s*=>\s*null\)/s);
  assert.doesNotMatch(presenter, /name:\s*structure\.section_name\s*\|\|\s*structure\.section_code/);
  assert.doesNotMatch(presenter, /sideLabel:\s*side\s*===\s*"none"\s*\?\s*"-"/);
});
