import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const features = resolve(root, "src/features");

function files(path) {
  return readdirSync(path).flatMap((name) => {
    const item = resolve(path, name);
    return statSync(item).isDirectory() ? files(item) : /\.tsx?$/.test(item) ? [item] : [];
  });
}

test("plan control and both girder planning paths expose public feature entrypoints", () => {
  for (const name of ["planControl", "girderPlanning", "girderPlanSimulation"]) {
    assert.equal(existsSync(resolve(features, name, "index.ts")), true, `${name} requires index.ts`);
  }
});

test("new girder plan simulation remains independent from specialty planning and publication", () => {
  const simulationSource = files(resolve(features, "girderPlanSimulation"))
    .map((path) => readFileSync(path, "utf8"))
    .join("\n");
  const specialtySource = files(resolve(features, "girderPlanning"))
    .map((path) => readFileSync(path, "utf8"))
    .join("\n");
  assert.doesNotMatch(simulationSource, /features\/girderPlanning|GirderPlanningConfig|solveIntegratedSchedule|createBaselinePlan|PlanControl/);
  assert.doesNotMatch(specialtySource, /girderPlanSimulation|GirderPlanSimulation/);
});

test("features do not import sibling feature internals", () => {
  for (const path of files(features)) {
    const source = readFileSync(path, "utf8");
    assert.doesNotMatch(source, /from\s+["'](?:\.\.\/)+(?:[^"']*\/)?features\/(?![^/"']+["'])/);
  }
});
