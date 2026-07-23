import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = resolve(import.meta.dirname, "..");

async function loadProductionModule() {
  const path = resolve(root, "src/features/taskView/projectMasterDisplayState.ts");
  const output = ts.transpileModule(readFileSync(path, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
    fileName: path,
  }).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(output).toString("base64")}`);
}

function deferred() {
  let resolvePromise;
  let rejectPromise;
  const promise = new Promise((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });
  return { promise, resolve: resolvePromise, reject: rejectPromise };
}

function workpoint(id, name = id) {
  return { workpoint_id: id, workpoint_name: name, sort_order: 1, work_sections: [] };
}

function response(versionId, workpoints) {
  return { project_data_version_id: versionId, workpoints };
}

test("display identity is versioned, trims, sorts and deduplicates workpoint ids", async () => {
  const { createProjectMasterDisplayIdentity } = await loadProductionModule();
  assert.deepEqual(
    createProjectMasterDisplayIdentity("pmv-2", ["WP-2", " ", "WP-1", "WP-2"]),
    {
      projectDataVersionId: "pmv-2",
      workpointIds: ["WP-1", "WP-2"],
      requestKey: JSON.stringify(["pmv-2", ["WP-1", "WP-2"]]),
    },
  );
});

test("one batch loader call stays loading then commits the complete response atomically", async () => {
  const { createProjectMasterDisplayCoordinator } = await loadProductionModule();
  const request = deferred();
  const calls = [];
  const coordinator = createProjectMasterDisplayCoordinator((versionId, workpointIds) => {
    calls.push({ versionId, workpointIds });
    return request.promise;
  });
  const states = [];
  coordinator.subscribe((state) => states.push(state));

  const loading = coordinator.setIdentity("pmv-1", ["WP-2", "WP-1", "WP-1"]);
  assert.equal(coordinator.getState().status, "loading");
  assert.deepEqual(calls, [{ versionId: "pmv-1", workpointIds: ["WP-1", "WP-2"] }]);
  request.resolve(response("pmv-1", [workpoint("WP-1", "一号桥"), workpoint("WP-2", "二号桥")]));
  await loading;

  assert.equal(coordinator.getState().status, "ready");
  assert.deepEqual(coordinator.getState().workpoints.map((item) => item.workpoint_id), ["WP-1", "WP-2"]);
  assert.deepEqual(states.map((state) => state.status), ["loading", "ready"]);
});

test("an empty identity becomes ready without a network request", async () => {
  const { createProjectMasterDisplayCoordinator } = await loadProductionModule();
  let requestCount = 0;
  const coordinator = createProjectMasterDisplayCoordinator(async () => {
    requestCount += 1;
    return response("pmv-1", []);
  });
  await coordinator.setIdentity("pmv-1", []);
  assert.equal(requestCount, 0);
  assert.equal(coordinator.getState().status, "ready");
  assert.deepEqual(coordinator.getState().workpoints, []);
});

test("a failed batch produces error and retry uses one new generation", async () => {
  const { createProjectMasterDisplayCoordinator } = await loadProductionModule();
  const attempts = [];
  const coordinator = createProjectMasterDisplayCoordinator(() => {
    const request = deferred();
    attempts.push(request);
    return request.promise;
  });

  const first = coordinator.setIdentity("pmv-1", ["WP-1", "WP-2"]);
  const firstGeneration = coordinator.getState().generation;
  assert.equal(attempts.length, 1, "one request identity must create exactly one batch request");
  attempts[0].reject(new Error("network"));
  await first;
  assert.equal(coordinator.getState().status, "error");
  assert.equal("workpoints" in coordinator.getState(), false);

  const retry = coordinator.retry();
  assert.equal(coordinator.getState().status, "loading");
  assert.ok(coordinator.getState().generation > firstGeneration);
  attempts[1].resolve(response("pmv-1", [workpoint("WP-1"), workpoint("WP-2")]));
  await retry;
  assert.equal(coordinator.getState().status, "ready");
  assert.equal(attempts.length, 2);
});

test("invalid version or workpoint sets never commit partial or extra mappings", async () => {
  const { createProjectMasterDisplayCoordinator } = await loadProductionModule();
  for (const invalid of [
    response("pmv-old", [workpoint("WP-1"), workpoint("WP-2")]),
    response("pmv-1", [workpoint("WP-1")]),
    response("pmv-1", [workpoint("WP-1"), workpoint("WP-2"), workpoint("WP-3")]),
    response("pmv-1", [workpoint("WP-1"), workpoint("WP-1")]),
  ]) {
    const coordinator = createProjectMasterDisplayCoordinator(async () => invalid);
    await coordinator.setIdentity("pmv-1", ["WP-1", "WP-2"]);
    assert.equal(coordinator.getState().status, "error");
    assert.equal("workpoints" in coordinator.getState(), false);
  }
});

test("a fast identity switch ignores a late batch response from the old identity", async () => {
  const { createProjectMasterDisplayCoordinator } = await loadProductionModule();
  const requests = new Map();
  const coordinator = createProjectMasterDisplayCoordinator((versionId, workpointIds) => {
    const request = deferred();
    requests.set(`${versionId}:${workpointIds.join(",")}`, request);
    return request.promise;
  });

  const oldLoad = coordinator.setIdentity("pmv-old", ["WP-1"]);
  const currentLoad = coordinator.setIdentity("pmv-current", ["WP-2"]);
  requests.get("pmv-current:WP-2").resolve(response("pmv-current", [workpoint("WP-2", "当前桥梁")]));
  await currentLoad;
  requests.get("pmv-old:WP-1").resolve(response("pmv-old", [workpoint("WP-1", "旧桥梁")]));
  await oldLoad;

  assert.equal(coordinator.getState().identity.projectDataVersionId, "pmv-current");
  assert.deepEqual(coordinator.getState().workpoints.map((item) => item.workpoint_name), ["当前桥梁"]);
});

test("a complete ready mapping is reused only for the same request identity", async () => {
  const { createProjectMasterDisplayCoordinator } = await loadProductionModule();
  let requestCount = 0;
  const coordinator = createProjectMasterDisplayCoordinator(async (versionId, ids) => {
    requestCount += 1;
    return response(versionId, ids.map((id) => workpoint(id)));
  });

  await coordinator.setIdentity("pmv-1", ["WP-1"]);
  await coordinator.setIdentity("pmv-2", ["WP-1"]);
  await coordinator.setIdentity("pmv-1", ["WP-1"]);
  assert.equal(requestCount, 2);
  assert.equal(coordinator.getState().identity.projectDataVersionId, "pmv-1");
  assert.equal(coordinator.getState().status, "ready");
});
