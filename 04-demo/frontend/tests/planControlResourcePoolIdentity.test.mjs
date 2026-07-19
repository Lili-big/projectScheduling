import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const panel = readFileSync(resolve(root, "src/features/planControl/PlanControlPanel.tsx"), "utf8");

test("plan-control resource increments are keyed by pool id instead of resource type", () => {
  assert.match(panel, /\[pool\.id, resourceIncrementLimit\]/);
  assert.doesNotMatch(panel, /\[resourceType, resourceIncrementLimit\]/);
});

test("adjustment cards expose the concrete target pool labels", () => {
  assert.match(panel, /调整资源池/);
  assert.match(panel, /adjustmentResourcePoolLabels/);
});
