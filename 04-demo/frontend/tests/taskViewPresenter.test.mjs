import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = resolve(import.meta.dirname, "..");

function toDataUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

function transpile(path) {
  return ts.transpileModule(readFileSync(path, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: path,
  }).outputText;
}

async function loadDomainModules() {
  const constantsUrl = toDataUrl(transpile(resolve(root, "src/domain/constants.ts")));
  const labels = await import(toDataUrl(transpile(resolve(root, "src/domain/labels.ts"))));
  const resourcesSource = transpile(resolve(root, "src/domain/resources.ts"))
    .replaceAll('from "./constants"', `from "${constantsUrl}"`);
  const resources = await import(toDataUrl(resourcesSource));
  return { labels, resources };
}

async function loadPresenter() {
  const labelsUrl = toDataUrl(transpile(resolve(root, "src/domain/labels.ts")));
  const presenterSource = transpile(resolve(root, "src/features/taskView/presenter.ts"))
    .replace('from "../../domain/labels"', `from "${labelsUrl}"`);
  return import(toDataUrl(presenterSource));
}

test("task view uses shared component labels and generic unlimited-resource presentation", async () => {
  const { labels, resources } = await loadDomainModules();
  const task = {
    component_type: "abutment_body",
    compatible_resource_types: [],
  };

  assert.equal(labels.componentLabels[task.component_type], "桥台");
  assert.equal(resources.taskResourceTypesLabel(task, []), "默认充足");
});

test("task view consumes backend process and duration fields without business-value branches", () => {
  const app = readFileSync(resolve(root, "src/app/Workspace.tsx"), "utf8");

  assert.match(app, /row\.task\.process_name/);
  assert.match(app, /row\.task\.duration_days/);
  assert.match(app, /尚未生成求解前任务图/);
  assert.match(app, /当前筛选条件下没有任务/);
  assert.doesNotMatch(app, /component_type\s*===\s*["']abutment_body["']/);
  assert.doesNotMatch(app, /duration_days\s*===\s*(?:10|15)/);
});

test("project-master presenter uses authoritative names and generic unavailable text", async () => {
  const { buildProjectMasterTaskViewMaps, taskViewNameUnavailable } = await loadPresenter();
  const maps = buildProjectMasterTaskViewMaps([
    {
      workpoint_id: "WP-1",
      workpoint_name: "权威桥梁",
      sort_order: 1,
      structures: [
        { section_code: "SEC-1", section_name: "权威工区", side: "left", sort_order: 2 },
        { section_code: "SEC-2", section_name: "", side: "none", sort_order: 3 },
      ],
    },
    {
      workpoint_id: "WP-2",
      workpoint_name: "",
      sort_order: 2,
      structures: [],
    },
  ]);

  assert.equal(maps.bridges.get("WP-1").name, "权威桥梁");
  assert.equal(maps.bridges.get("WP-2").name, taskViewNameUnavailable);
  assert.deepEqual(maps.sections.get("SEC-1:left"), {
    name: "权威工区",
    order: 2,
    sideLabel: "左幅",
  });
  assert.deepEqual(maps.sections.get("SEC-2:none"), {
    name: taskViewNameUnavailable,
    order: 3,
    sideLabel: "无幅别",
  });
});
