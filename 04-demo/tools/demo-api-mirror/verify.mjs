import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const toolDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(toolDir, "..", "..", "..");
const apiSource = readFileSync(join(toolDir, "api.mts"), "utf8");
const girderOpenApi = readFileSync(join(repoRoot, "03-requirements", "specs", "051-girder-plan-simulation", "contracts", "girder-plan-simulation.openapi.yaml"), "utf8");
const girderSegmentOpenApi = readFileSync(join(repoRoot, "03-requirements", "specs", "058-girder-continuous-bridge-segments", "contracts", "girder-continuous-bridge-segments.openapi.yaml"), "utf8");
const girderBackendContract = readFileSync(join(repoRoot, "04-demo", "backend", "app", "contracts", "girder_plan_simulation.py"), "utf8");
const girderFrontendContract = readFileSync(join(repoRoot, "04-demo", "frontend", "src", "contracts", "girderPlanSimulation.ts"), "utf8");
const netlifyConfig = readFileSync(join(repoRoot, "netlify.toml"), "utf8");
if (/^\s*functions\s*=|\[functions\]/m.test(netlifyConfig)) {
  throw new Error("netlify.toml unexpectedly configures Functions; demo mirror must remain undeployed.");
}
if (!/resource_pools:\s*\[\]/.test(apiSource) || !/function currentProjectResourcePools/.test(apiSource)) {
  throw new Error("demo mirror must expose an empty project default and filter cached project resources");
}
if (!/scope_mode \?\? "PROJECT_SHARED"\) === "PROJECT_SHARED"/.test(apiSource)) {
  throw new Error("demo mirror must retain the explicit shared-resource matching branch");
}
for (const operation of [
  "line-graphs",
  "girder-plan-simulation/scenarios",
  "scenarios\\/([^/]+)\\/validate",
  "girder-plan-simulation/runs",
  "runs\\/([^/]+)\\/confirm",
]) {
  if (!apiSource.includes(operation)) throw new Error(`demo mirror misses girder plan operation: ${operation}`);
}
if (!/girderPlanScenarioCache/.test(apiSource) || !/girderPlanRunCache/.test(apiSource)) {
  throw new Error("girder plan mirror must keep independent ephemeral scenario and run state");
}
for (const sharedField of [
  "beam_type_id",
  "daily_capacity_pieces",
  "daily_erection_capacity_pieces",
  "latest_delivery_date",
  "input_fingerprint",
  "result_fingerprint",
]) {
  for (const [label, source] of [["OpenAPI", girderOpenApi], ["backend", girderBackendContract], ["frontend", girderFrontendContract], ["mirror", apiSource]]) {
    if (!source.includes(sharedField)) throw new Error(`${label} girder plan contract misses ${sharedField}`);
  }
}
for (const state of ["draft", "ready", "calculated", "confirmed", "stale", "blocked"]) {
  if (!girderBackendContract.includes(`"${state}"`) || !girderFrontendContract.includes(`"${state}"`) || !apiSource.includes(`"${state}"`)) {
    throw new Error(`girder plan lifecycle state is not synchronized: ${state}`);
  }
}
for (const [label, source] of [["v3 OpenAPI", girderSegmentOpenApi], ["backend", girderBackendContract], ["frontend", girderFrontendContract], ["mirror", apiSource]]) {
  if (!source.includes("bridge_segment_kind") || !source.includes("girder-plan-line-graph/v3")) {
    throw new Error(`${label} misses synchronized v3 bridge segment contract`);
  }
}
if (!/opening_inventory_pieces: opening, produced_pieces: produced, erected_pieces: erected, closing_inventory_pieces: inventory/.test(apiSource)) {
  throw new Error("girder plan mirror must expose the daily inventory conservation ledger");
}

const tsc = join(repoRoot, "node_modules", "typescript", "bin", "tsc");
const result = spawnSync(process.execPath, [tsc, "-p", join(toolDir, "tsconfig.json")], {
  cwd: repoRoot,
  encoding: "utf8",
});
if (result.stdout) process.stdout.write(result.stdout);
if (result.stderr) process.stderr.write(result.stderr);
if (result.status !== 0) process.exit(result.status ?? 1);

console.log("demo API mirror: typecheck OK; deployment wiring absent");
