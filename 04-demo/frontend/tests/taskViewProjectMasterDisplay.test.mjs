import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = resolve(import.meta.dirname, "..");

async function loadProductionModule() {
  const path = resolve(root, "src/features/taskView/projectMasterDisplayState.ts");
  const output = ts.transpileModule(readFileSync(path, "utf8"), {
    compilerOptions: {
      module: ts.ModuleKind.ESNext,
      target: ts.ScriptTarget.ES2022,
    },
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
  return {
    workpoint_id: id,
    workpoint_name: name,
    workpoint_type: "bridge",
    sort_order: 1,
    schedule_support: "bridge_supported",
    structures: [],
  };
}

test("display identity is versioned, sorted and unique", async () => {
  const { createProjectMasterDisplayIdentity } = await loadProductionModule();
  assert.deepEqual(
    createProjectMasterDisplayIdentity("pmv-2", ["WP-2", "WP-1", "WP-2"]),
    {
      projectDataVersionId: "pmv-2",
      workpointIds: ["WP-1", "WP-2"],
      requestKey: JSON.stringify(["pmv-2", ["WP-1", "WP-2"]]),
    },
  );
});

test("mapping stays loading until all workpoints succeed and commits ready atomically", async () => {
  const { createProjectMasterDisplayCoordinator } = await loadProductionModule();
  const requests = new Map([
    ["WP-1", deferred()],
    ["WP-2", deferred()],
  ]);
  const coordinator = createProjectMasterDisplayCoordinator((_, id) => requests.get(id).promise);
  const states = [];
  coordinator.subscribe((state) => states.push(state));

  const loading = coordinator.setIdentity("pmv-1", ["WP-2", "WP-1", "WP-1"]);
  assert.equal(coordinator.getState().status, "loading");
  requests.get("WP-1").resolve(workpoint("WP-1", "一号桥"));
  await Promise.resolve();
  assert.equal(coordinator.getState().status, "loading");
  assert.equal("workpoints" in coordinator.getState(), false);

  requests.get("WP-2").resolve(workpoint("WP-2", "二号桥"));
  await loading;
  assert.equal(coordinator.getState().status, "ready");
  assert.deepEqual(coordinator.getState().workpoints.map((item) => item.workpoint_id), ["WP-1", "WP-2"]);
  assert.deepEqual(states.map((state) => state.status), ["loading", "ready"]);
});

test("any failed request produces an error without partial mappings and retry uses a new generation", async () => {
  const { createProjectMasterDisplayCoordinator } = await loadProductionModule();
  const attempts = [];
  const coordinator = createProjectMasterDisplayCoordinator((_, id) => {
    const request = deferred();
    attempts.push({ id, request });
    return request.promise;
  });

  const first = coordinator.setIdentity("pmv-1", ["WP-1", "WP-2"]);
  const firstGeneration = coordinator.getState().generation;
  attempts[0].request.resolve(workpoint(attempts[0].id));
  attempts[1].request.reject(new Error("network"));
  await first;

  assert.equal(coordinator.getState().status, "error");
  assert.equal("workpoints" in coordinator.getState(), false);

  const retry = coordinator.retry();
  assert.equal(coordinator.getState().status, "loading");
  assert.ok(coordinator.getState().generation > firstGeneration);
  attempts[2].request.resolve(workpoint(attempts[2].id));
  attempts[3].request.resolve(workpoint(attempts[3].id));
  await retry;
  assert.equal(coordinator.getState().status, "ready");
});

test("a fast identity switch ignores a late response from the old version", async () => {
  const { createProjectMasterDisplayCoordinator } = await loadProductionModule();
  const requests = new Map();
  const coordinator = createProjectMasterDisplayCoordinator((versionId, id) => {
    const request = deferred();
    requests.set(`${versionId}:${id}`, request);
    return request.promise;
  });

  const oldLoad = coordinator.setIdentity("pmv-old", ["WP-1"]);
  const currentLoad = coordinator.setIdentity("pmv-current", ["WP-2"]);
  requests.get("pmv-current:WP-2").resolve(workpoint("WP-2", "当前桥梁"));
  await currentLoad;
  assert.equal(coordinator.getState().identity.projectDataVersionId, "pmv-current");

  requests.get("pmv-old:WP-1").resolve(workpoint("WP-1", "旧桥梁"));
  await oldLoad;
  assert.equal(coordinator.getState().identity.projectDataVersionId, "pmv-current");
  assert.deepEqual(coordinator.getState().workpoints.map((item) => item.workpoint_name), ["当前桥梁"]);
});

test("a complete ready mapping is reused only for the same request identity", async () => {
  const { createProjectMasterDisplayCoordinator } = await loadProductionModule();
  let requestCount = 0;
  const coordinator = createProjectMasterDisplayCoordinator(async (_, id) => {
    requestCount += 1;
    return workpoint(id);
  });

  await coordinator.setIdentity("pmv-1", ["WP-1"]);
  await coordinator.setIdentity("pmv-2", ["WP-1"]);
  await coordinator.setIdentity("pmv-1", ["WP-1"]);

  assert.equal(requestCount, 2);
  assert.equal(coordinator.getState().identity.projectDataVersionId, "pmv-1");
  assert.equal(coordinator.getState().status, "ready");
});
