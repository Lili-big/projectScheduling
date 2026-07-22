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
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
    fileName: path,
  }).outputText;
}

async function loadWorkflows() {
  const scenarioPath = resolve(root, "src/app/workflows/scenarioWorkflow.ts");
  const scenarioSource = transpile(scenarioPath);
  const scenarioUrl = toDataUrl(scenarioSource);
  const solveSource = transpile(resolve(root, "src/app/workflows/solveWorkflow.ts"))
    .replace('from "./scenarioWorkflow"', `from "${scenarioUrl}"`);
  return {
    scenario: await import(scenarioUrl),
    solve: await import(toDataUrl(solveSource)),
  };
}

const scenario = {
  scenario_id: "S",
  scenario_name: "scope",
  project: { project_id: "P", project_name: "P", start_date: "2026-01-01", bridges: [] },
  process_library: [],
  logic_rules: [],
  resource_pools: [],
  milestones: [],
  time_limit_seconds: 3,
};

test("solve fingerprint changes with workpoint scope and remains stable for all scope", async () => {
  const { scenario: workflow } = await loadWorkflows();
  const allA = workflow.scenarioFingerprintForSolve(scenario);
  const allB = workflow.scenarioFingerprintForSolve(scenario, null);
  const workpointA = workflow.scenarioFingerprintForSolve(scenario, "WP-A");
  const workpointB = workflow.scenarioFingerprintForSolve(scenario, "WP-B");

  assert.equal(allA, allB);
  assert.notEqual(allA, workpointA);
  assert.notEqual(workpointA, workpointB);
});

test("solve workflow forwards one scope to request and result fingerprint", async () => {
  const { solve: workflow } = await loadWorkflows();
  let receivedWorkpoint = null;
  const result = await workflow.solveScenarioWorkflow(
    scenario,
    (value) => value,
    async (_value, workpointId) => {
      receivedWorkpoint = workpointId;
      return { generated: { solve_scope: { mode: "WORKPOINT", workpoint_id: workpointId, workpoint_name: "A" } } };
    },
    "WP-A",
  );

  assert.equal(receivedWorkpoint, "WP-A");
  assert.match(result.fingerprint, /WP-A/);
});

test("workspace exposes scope selection, invalidation and single-result save guard", () => {
  const workspace = readFileSync(resolve(root, "src/app/Workspace.tsx"), "utf8");
  assert.match(workspace, /selectedSolveWorkpointId/);
  assert.match(workspace, /onSolveWorkpointChange/);
  assert.match(workspace, /clearSolveScopeOutputs/);
  assert.match(workspace, /solveRequestRef\.current \+= 1/);
  assert.match(workspace, /requestId !== solveRequestRef\.current/);
  assert.match(workspace, /单工点结果仅用于试算，不能保存为全项目方案/);
  assert.match(workspace, /disabled=\{Boolean\(busy\) \|\| resourceWorkpointState\.status !== "ready"\}/);
});

test("frontend API and Netlify mirror share optional query scope", () => {
  const api = readFileSync(resolve(root, "src/api/_schedulerApi.ts"), "utf8");
  const mirror = readFileSync(resolve(root, "../tools/demo-api-mirror/api.mts"), "utf8");
  assert.match(api, /workpoint_id=/);
  assert.match(api, /encodeURIComponent\(normalized\)/);
  assert.match(mirror, /searchParams\.get\("workpoint_id"\)/);
  assert.match(mirror, /SOLVE_SCOPE_WORKPOINT_INVALID/);
  assert.match(mirror, /solve_scope: solveScope/);
});
