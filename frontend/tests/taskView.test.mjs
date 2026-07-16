import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const presenter = readFileSync(resolve(root, "src/features/taskView/presenter.ts"), "utf8");
const entrypoint = readFileSync(resolve(root, "src/features/taskView/index.ts"), "utf8");
const workspace = readFileSync(resolve(root, "src/features/taskView/TaskViewWorkspace.tsx"), "utf8");

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
