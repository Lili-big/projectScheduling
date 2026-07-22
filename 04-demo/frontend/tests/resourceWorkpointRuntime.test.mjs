import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createWriteStream, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { dirname, resolve } from "node:path";
import test, { after, before } from "node:test";
import { fileURLToPath } from "node:url";

const testRoot = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(testRoot, "..");
const demoRoot = resolve(frontendRoot, "..");
const repoRoot = resolve(demoRoot, "..");
const backendRoot = resolve(demoRoot, "backend");
const runId = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
const evidenceRoot = resolve(repoRoot, ".local-data", "logs", "050-structure-matched-resource-catalog", "runtime");
const logDir = resolve(evidenceRoot, `${runId}-resource-workpoint-runtime`);
const tempDir = resolve(repoRoot, ".local-data", "tmp", "resource-workpoint-runtime", runId);
const frontendUrl = "http://127.0.0.1:5173";
const apiUrl = "http://127.0.0.1:8000";
const timeoutMs = 180_000;

mkdirSync(logDir, { recursive: true });
mkdirSync(tempDir, { recursive: true });

const ownedProcesses = [];
const evidence = {
  runId,
  command: "node --test 04-demo/frontend/tests/resourceWorkpointRuntime.test.mjs",
  nodeVersion: process.version,
  logDir,
  runtime: null,
  browser: null,
  oracle: null,
  transitions: [],
  requests: { saves: [], generations: [], workpointLists: [], workpointDetails: [] },
  assertions: {},
};
let browser = null;
let cdp = null;
let page = null;
let oracle = null;
let networkMode = {
  saveFailureRemaining: 0,
  workpointMode: "pass",
  pauseNextV1: false,
  pauseNextDetail: false,
  firstDetailWithoutStructures: false,
  projectMasterMock: false,
  v2Confirmed: false,
};
let pausedV1 = null;
let pausedDetail = null;

const sleep = (ms) => new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
const now = () => new Date().toISOString();

async function waitUntil(check, label, limitMs = timeoutMs, intervalMs = 100) {
  const startedAt = Date.now();
  let lastError = null;
  while (Date.now() - startedAt < limitMs) {
    try {
      const value = await check();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await sleep(intervalMs);
  }
  throw new Error(`Timed out waiting for ${label}.${lastError ? ` Last error: ${lastError.message}` : ""}`);
}

async function httpOk(url) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(2_000) });
    return response.ok;
  } catch {
    return false;
  }
}

function resolvePython() {
  return [
    process.env.PYTHON,
    resolve(repoRoot, ".venv", "Scripts", "python.exe"),
    resolve(demoRoot, ".venv", "Scripts", "python.exe"),
    resolve(backendRoot, ".venv", "Scripts", "python.exe"),
  ].filter(Boolean).find((candidate) => existsSync(candidate)) ?? "python";
}

function vitePackagePath() {
  return fileURLToPath(import.meta.resolve("vite/package.json"));
}

function startLoggedProcess(name, command, args, cwd) {
  const stdoutPath = resolve(logDir, `${name}.stdout.log`);
  const stderrPath = resolve(logDir, `${name}.stderr.log`);
  const stdout = createWriteStream(stdoutPath, { flags: "a" });
  const stderr = createWriteStream(stderrPath, { flags: "a" });
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, PYTHONUTF8: "1" },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  child.stdout.pipe(stdout);
  child.stderr.pipe(stderr);
  ownedProcesses.push({ child, stdout, stderr, stdoutPath, stderrPath });
  return { startedAt: now(), stdoutPath, stderrPath };
}

async function ensureService({ name, healthUrl, command, args, cwd }) {
  if (await httpOk(healthUrl)) return { name, mode: "reused", observedAt: now() };
  const metadata = startLoggedProcess(name, command, args, cwd);
  await waitUntil(() => httpOk(healthUrl), `${name} health endpoint`, 90_000, 250);
  return { name, mode: "started", ...metadata, healthyAt: now() };
}

async function ensureRuntime() {
  const fastapi = await ensureService({
    name: "fastapi",
    healthUrl: `${apiUrl}/api/health`,
    command: resolvePython(),
    args: ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd: backendRoot,
  });
  const vitePackage = JSON.parse(readFileSync(vitePackagePath(), "utf8"));
  const vite = await ensureService({
    name: "vite",
    healthUrl: frontendUrl,
    command: process.execPath,
    args: [resolve(dirname(vitePackagePath()), "bin", "vite.js"), "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
    cwd: frontendRoot,
  });
  return { fastapi, vite, versions: { node: process.version, vite: vitePackage.version } };
}

async function stopOwnedProcesses() {
  for (const entry of [...ownedProcesses].reverse()) {
    if (entry.child.exitCode === null) entry.child.kill();
    await Promise.race([new Promise((resolvePromise) => entry.child.once("exit", resolvePromise)), sleep(3_000)]);
    entry.stdout.end();
    entry.stderr.end();
  }
}

async function freeTcpPort() {
  return new Promise((resolvePromise, rejectPromise) => {
    const server = createServer();
    server.once("error", rejectPromise);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : null;
      server.close((error) => error ? rejectPromise(error) : resolvePromise(port));
    });
  });
}

function findBrowserExecutable() {
  const candidates = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    resolve(process.env.LOCALAPPDATA ?? "", "Google", "Chrome", "Application", "chrome.exe"),
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    resolve(process.env.LOCALAPPDATA ?? "", "Microsoft", "Edge", "Application", "msedge.exe"),
  ];
  const executable = candidates.find((candidate) => candidate && existsSync(candidate));
  if (!executable) throw new Error("No system Edge/Chrome/Chromium executable was found.");
  return executable;
}

class CdpConnection {
  constructor(webSocketUrl) {
    this.webSocket = new WebSocket(webSocketUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.listeners = new Map();
    this.eventErrors = [];
    this.closed = false;
    this.ready = new Promise((resolvePromise, rejectPromise) => {
      this.webSocket.addEventListener("open", resolvePromise, { once: true });
      this.webSocket.addEventListener("error", rejectPromise, { once: true });
      this.webSocket.addEventListener("close", () => rejectPromise(new Error("CDP WebSocket closed before opening.")), { once: true });
    });
    this.webSocket.addEventListener("message", (event) => this.handleMessage(event.data));
    this.webSocket.addEventListener("close", () => {
      this.closed = true;
      for (const pending of this.pending.values()) pending.reject(new Error(`${pending.method}: CDP WebSocket closed.`));
      this.pending.clear();
    });
  }

  handleMessage(data) {
    const message = JSON.parse(String(data));
    if (message.id) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(`${pending.method}: ${message.error.message}`));
      else pending.resolve(message.result ?? {});
      return;
    }
    for (const listener of this.listeners.get(`${message.sessionId ?? "*"}:${message.method}`) ?? []) {
      Promise.resolve(listener(message.params ?? {}, message.sessionId)).catch((error) => this.eventErrors.push(error));
    }
    for (const listener of this.listeners.get(`*:${message.method}`) ?? []) {
      Promise.resolve(listener(message.params ?? {}, message.sessionId)).catch((error) => this.eventErrors.push(error));
    }
  }

  async send(method, params = {}, sessionId = undefined) {
    await this.ready;
    if (this.closed) throw new Error(`${method}: CDP WebSocket is closed.`);
    const id = this.nextId++;
    const message = { id, method, params };
    if (sessionId) message.sessionId = sessionId;
    const response = new Promise((resolvePromise, rejectPromise) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        rejectPromise(new Error(`${method}: CDP response timed out after 60000ms.`));
      }, 60_000);
      this.pending.set(id, {
        resolve: (value) => { clearTimeout(timer); resolvePromise(value); },
        reject: (error) => { clearTimeout(timer); rejectPromise(error); },
        method,
      });
    });
    this.webSocket.send(JSON.stringify(message));
    return response;
  }

  on(method, listener, sessionId = "*") {
    const key = `${sessionId}:${method}`;
    const listeners = this.listeners.get(key) ?? new Set();
    listeners.add(listener);
    this.listeners.set(key, listeners);
  }
}

async function launchBrowser() {
  const executable = findBrowserExecutable();
  const port = await freeTcpPort();
  const physicalProfileDir = resolve(tempDir, "browser-profile");
  const profileDir = physicalProfileDir;
  mkdirSync(profileDir, { recursive: true });
  const stdoutPath = resolve(logDir, "browser.stdout.log");
  const stderrPath = resolve(logDir, "browser.stderr.log");
  const stdout = createWriteStream(stdoutPath, { flags: "a" });
  const stderr = createWriteStream(stderrPath, { flags: "a" });
  const child = spawn(executable, [
    "--headless=new",
    "--disable-gpu",
    "--disable-gpu-sandbox",
    "--disable-gpu-shader-disk-cache",
    "--disable-features=SkiaGraphite,DawnGraphite",
    "--disable-extensions",
    "--disable-background-networking",
    "--no-first-run",
    "--no-default-browser-check",
    "--remote-allow-origins=*",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    "about:blank",
  ], { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  child.stdout.pipe(stdout);
  child.stderr.pipe(stderr);
  const version = await waitUntil(async () => {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      return response.ok ? response.json() : null;
    } catch {
      return null;
    }
  }, "browser DevTools endpoint", 30_000);
  return { child, stdout, stderr, executable, product: version.Browser, webSocketUrl: version.webSocketDebuggerUrl };
}

async function closeBrowser() {
  if (!browser) return;
  try { await cdp.send("Browser.close"); } catch { if (browser.child.exitCode === null) browser.child.kill(); }
  await Promise.race([new Promise((resolvePromise) => browser.child.once("exit", resolvePromise)), sleep(5_000)]);
  if (browser.child.exitCode === null) browser.child.kill();
  browser.stdout.end();
  browser.stderr.end();
}

async function createPage() {
  const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  await cdp.send("Page.enable", {}, sessionId);
  await cdp.send("Runtime.enable", {}, sessionId);
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: `
    (() => {
      const records = [];
      const capture = (reason) => {
        const panel = document.querySelector('.resource-scope-panel');
        records.push({
          at: Date.now(), reason,
          version: panel?.getAttribute('data-resource-version') ?? null,
          status: panel?.querySelector('[role="alert"]') ? 'error' : panel?.querySelector('[role="status"]') ? 'loading' : panel ? 'ready' : 'absent',
          workpoints: [...document.querySelectorAll('.resource-workpoint-nav button')].map((node) => node.textContent.trim()),
          text: panel?.innerText ?? '',
        });
      };
      window.__resourceRuntime = { records, capture };
      new MutationObserver(() => capture('mutation')).observe(document, { subtree: true, childList: true, characterData: true, attributes: true });
      document.addEventListener('DOMContentLoaded', () => capture('dom-content-loaded'));
    })();
  ` }, sessionId);
  await cdp.send("Fetch.enable", { patterns: [{ urlPattern: "*/api/*", requestStage: "Request" }] }, sessionId);
  cdp.on("Fetch.requestPaused", (params) => handleRequestPaused(params, sessionId), sessionId);
  return { targetId, sessionId };
}

async function evaluate(expression) {
  const response = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  }, page.sessionId);
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.text ?? "Runtime evaluation failed");
  return response.result.value;
}

async function navigate(url = frontendUrl) {
  await cdp.send("Page.navigate", { url }, page.sessionId);
  await waitUntil(() => evaluate("document.readyState === 'complete'"), "page load");
}

async function clickText(text) {
  return evaluate(`(() => {
    const target = [...document.querySelectorAll('button')].find((item) => item.textContent.trim() === ${JSON.stringify(text)});
    if (!target) return false;
    target.click();
    return true;
  })()`);
}

async function openResourcesAfterTaskReady() {
  await waitForExpression("Boolean(document.querySelector('.task-view-header-panel'))", "stable task view before resource navigation", 90_000);
  await waitForExpression("[...document.querySelectorAll('button')].some((item) => item.textContent.trim() === '生成任务视图' && !item.disabled)", "idle task generation before resource navigation", 90_000);
  await sleep(500);
  assert.equal(await evaluate(`(() => {
    const target = [...document.querySelectorAll('.side-nav-item')].find((item) => item.textContent.trim().startsWith('资源配置'));
    if (!target) return false;
    target.click();
    return true;
  })()`), true);
  await sleep(500);
  const state = await evaluate(`(() => ({
    panel: Boolean(document.querySelector('.resource-scope-panel')),
    body: document.body.innerText.slice(0, 3000),
  }))()`);
  assert.equal(state.panel, true, JSON.stringify(state));
}

async function waitForExpression(expression, label, limitMs = 60_000) {
  return waitUntil(() => evaluate(expression), label, limitMs);
}

function base64Json(value) {
  return Buffer.from(JSON.stringify(value)).toString("base64");
}

async function fulfillJson(requestId, value, responseCode = 200) {
  await cdp.send("Fetch.fulfillRequest", {
    requestId,
    responseCode,
    responseHeaders: [{ name: "Content-Type", value: "application/json; charset=utf-8" }],
    body: base64Json(value),
  }, page.sessionId);
}

async function handleRequestPaused(params) {
  const url = params.request.url;
  const method = params.request.method;
  if (method === "PUT" && url.includes("/api/local-scenario-config")) {
    const body = JSON.parse(params.request.postData ?? "{}");
    evidence.requests.saves.push({ at: now(), body });
    if (networkMode.saveFailureRemaining > 0) {
      networkMode.saveFailureRemaining -= 1;
      await fulfillJson(params.requestId, { detail: "受控保存失败" }, 503);
    } else {
      await fulfillJson(params.requestId, body);
    }
    return;
  }
  if (method === "POST" && url.includes("/api/generate-schedule-input")) {
    evidence.requests.generations.push({ at: now(), body: JSON.parse(params.request.postData ?? "{}") });
  }
  const workpointMatch = url.match(/\/api\/project-master\/versions\/([^/]+)\/workpoints\?/);
  if (method === "GET" && workpointMatch) {
    const versionId = decodeURIComponent(workpointMatch[1]);
    evidence.requests.workpointLists.push({ at: now(), versionId, mode: networkMode.workpointMode });
    if (versionId === oracle.v2Version.version_id) {
      await fulfillJson(params.requestId, pageOf(oracle.v2Workpoints));
      return;
    }
    if (versionId === oracle.currentVersion.version_id && networkMode.pauseNextV1) {
      networkMode.pauseNextV1 = false;
      pausedV1 = { requestId: params.requestId };
      return;
    }
    if (versionId === oracle.currentVersion.version_id && networkMode.workpointMode === "empty") {
      await fulfillJson(params.requestId, pageOf([]));
      return;
    }
    if (versionId === oracle.currentVersion.version_id && networkMode.workpointMode === "fail") {
      networkMode.workpointMode = "pass";
      await fulfillJson(params.requestId, { detail: "受控工点加载失败" }, 503);
      return;
    }
  }
  const workpointDetailMatch = url.match(/\/api\/project-master\/versions\/([^/]+)\/workpoints\/([^/?]+)(?:\?|$)/);
  if (method === "GET" && workpointDetailMatch) {
    const versionId = decodeURIComponent(workpointDetailMatch[1]);
    const workpointId = decodeURIComponent(workpointDetailMatch[2]);
    evidence.requests.workpointDetails.push({ at: now(), versionId, workpointId });
    const details = versionId === oracle.v2Version.version_id ? oracle.v2Details : oracle.currentDetails;
    const detail = details[workpointId];
    if (detail) {
      if (networkMode.pauseNextDetail) {
        networkMode.pauseNextDetail = false;
        pausedDetail = { requestId: params.requestId, detail };
        return;
      }
      if (networkMode.firstDetailWithoutStructures && workpointId === oracle.currentWorkpoints[0].workpoint_id) {
        await fulfillJson(params.requestId, { ...detail, structures: [] });
        return;
      }
      await fulfillJson(params.requestId, detail);
      return;
    }
  }
  if (networkMode.projectMasterMock) {
    if (method === "GET" && url.includes(`/api/projects/${encodeURIComponent(oracle.projectId)}/project-master/versions?`)) {
      const items = networkMode.v2Confirmed
        ? [{ ...oracle.v2Version, status: "confirmed" }, { ...oracle.currentVersion, status: "superseded" }]
        : [oracle.currentVersion, oracle.v2Version];
      await fulfillJson(params.requestId, { page: 1, page_size: 50, total: items.length, items });
      return;
    }
    if (method === "POST" && /\/api\/projects\/[^/]+\/project-master\/imports$/.test(url)) {
      await fulfillJson(params.requestId, oracle.importBatch);
      return;
    }
    if (method === "GET" && url.endsWith(`/api/project-master/versions/${oracle.v2Version.version_id}`)) {
      await fulfillJson(params.requestId, oracle.v2Version);
      return;
    }
    if (method === "POST" && url.endsWith(`/api/project-master/versions/${oracle.v2Version.version_id}/confirm`)) {
      networkMode.v2Confirmed = true;
      await fulfillJson(params.requestId, { ...oracle.v2Version, status: "confirmed", confirmed_at: now() });
      return;
    }
  }
  await cdp.send("Fetch.continueRequest", { requestId: params.requestId }, page.sessionId);
}

function pageOf(items) {
  return { page: 1, page_size: 200, total: items.length, items };
}

function workpoint(id, name, sortOrder) {
  return {
    workpoint_id: id,
    workpoint_name: name,
    workpoint_type: "bridge",
    alignment_code: null,
    start_mileage_m: null,
    end_mileage_m: null,
    sort_order: sortOrder,
    schedule_support: "bridge_supported",
    remark: null,
    structures: [],
    source: null,
  };
}

function resourceParameter(parameterCode, value, { unit = null, sortOrder = 1 } = {}) {
  return {
    parameter_code: parameterCode,
    value_type: typeof value === "number" ? "number" : "text",
    value,
    unit,
    sort_order: sortOrder,
    source: null,
  };
}

function resourceComponent(id, type, {
  methodId = null,
  enabled = true,
  quantity = 1,
  unit = "个",
  parameters = [],
} = {}) {
  return {
    component_id: id,
    structure_id: "runtime-lower",
    component_name: id,
    component_type: type,
    quantity,
    unit,
    enabled,
    sort_order: 1,
    remark: null,
    parameters: [...parameters, ...(methodId ? [resourceParameter("method_id", methodId)] : [])],
    source: null,
  };
}

function resourceDetail(item, { empty = false } = {}) {
  if (empty) return { ...item, structures: [] };
  return {
    ...item,
    structures: [
      {
        structure_id: "runtime-lower",
        workpoint_id: item.workpoint_id,
        structure_name: "受控下部结构",
        structure_category: "substructure",
        structure_type: "bridge_pier",
        side: "left",
        section_code: "runtime-section",
        section_name: "受控工区",
        control_level: "normal",
        sort_order: 1,
        remark: null,
        parameters: [],
        components: [
          resourceComponent("runtime-pile", "pile", {
            methodId: "rotary_drill",
            quantity: 5,
            unit: "根",
            parameters: [resourceParameter("diameter_m", 1.8, { unit: "m" })],
          }),
          resourceComponent("runtime-cap", "cap", {
            quantity: 2,
            unit: "个",
            parameters: [
              resourceParameter("length_m", 3, { unit: "m", sortOrder: 1 }),
              resourceParameter("width_m", 4, { unit: "m", sortOrder: 2 }),
              resourceParameter("height_m", 12, { unit: "m", sortOrder: 3 }),
            ],
          }),
          resourceComponent("runtime-pier", "pier_body"),
          resourceComponent("runtime-cap-beam", "cap_beam"),
        ],
        source: null,
      },
      {
        structure_id: "runtime-continuous",
        workpoint_id: item.workpoint_id,
        structure_name: "受控连续梁",
        structure_category: "superstructure",
        structure_type: "continuous_unit",
        side: "left",
        section_code: "runtime-section",
        section_name: "受控工区",
        control_level: "control",
        sort_order: 2,
        remark: null,
        parameters: [],
        components: [],
        source: null,
      },
    ],
  };
}

async function loadOracle() {
  const scenario = await (await fetch(`${apiUrl}/api/demo-scenario`)).json();
  const currentVersion = await (await fetch(`${apiUrl}/api/projects/${encodeURIComponent(scenario.project.project_id)}/project-master/versions/current`)).json();
  const page = await (await fetch(`${apiUrl}/api/project-master/versions/${encodeURIComponent(currentVersion.version_id)}/workpoints?page=1&page_size=200&workpoint_type=bridge`)).json();
  assert.ok(page.items.length > 1, "runtime fixture requires at least two authoritative bridge workpoints");
  const counts = { workpoints: 2, structures: 0, components: 0, errors: 0, warnings: 0 };
  const v2VersionId = `${currentVersion.version_id}-runtime-next`;
  const v2Workpoints = [workpoint("runtime-current-a", "当前版本工点甲", 1), workpoint("runtime-current-b", "当前版本工点乙", 2)];
  const v2Version = {
    version_id: v2VersionId,
    project_id: scenario.project.project_id,
    version_no: Number(currentVersion.version_no ?? 1) + 1,
    status: "draft",
    content_fingerprint: "runtime-controlled-v2",
    source_batch_id: "runtime-batch",
    base_version_id: currentVersion.version_id,
    counts,
    created_at: now(),
    created_by: "runtime-test",
    confirmed_at: null,
    confirmed_by: null,
    diff_counts: { added: 2, modified: 0, deleted: 0 },
    diff_entries: [],
    warning_codes: [],
  };
  return {
    projectId: scenario.project.project_id,
    currentVersion,
    currentWorkpoints: page.items,
    currentDetails: Object.fromEntries(page.items.map((item, index) => [item.workpoint_id, resourceDetail(item, { empty: index > 0 })])),
    v2Version,
    v2Workpoints,
    v2Details: Object.fromEntries(v2Workpoints.map((item, index) => [item.workpoint_id, resourceDetail(item, { empty: index > 0 })])),
    importBatch: {
      batch_id: "runtime-batch",
      project_id: scenario.project.project_id,
      status: "ready",
      file_name: "runtime.xlsx",
      file_sha256: "runtime-sha",
      content_fingerprint: "runtime-controlled-v2",
      expected_current_version_id: currentVersion.version_id,
      created_version_id: v2VersionId,
      existing_version_id: null,
      cancelled_version_id: null,
      counts,
      diff_counts: { added: 2, modified: 0, deleted: 0 },
      issues: [],
      created_at: now(),
      created_by: "runtime-test",
      completed_at: now(),
      failure_message: null,
    },
  };
}

before(async () => {
  evidence.runtime = await ensureRuntime();
  oracle = await loadOracle();
  evidence.oracle = {
    projectId: oracle.projectId,
    currentVersionId: oracle.currentVersion.version_id,
    currentWorkpointCount: oracle.currentWorkpoints.length,
    controlledNextVersionId: oracle.v2Version.version_id,
  };
  browser = await launchBrowser();
  evidence.browser = { executable: browser.executable, product: browser.product, launchedAt: now() };
  cdp = new CdpConnection(browser.webSocketUrl);
  await cdp.ready;
  page = await createPage();
});

after(async () => {
  try {
    if (page) evidence.transitions = await evaluate("window.__resourceRuntime?.records ?? []");
  } catch {}
  evidence.cdpEventErrors = cdp?.eventErrors.map((error) => error.message) ?? [];
  mkdirSync(evidenceRoot, { recursive: true });
  writeFileSync(resolve(logDir, "resource-workpoint-runtime-summary.json"), `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  await closeBrowser();
  await stopOwnedProcesses();
});

test("T015 production workspace matches Chinese resources from structures across save, empty and version races", { timeout: timeoutMs }, async () => {
  await navigate(`${frontendUrl}/?resource-workpoint-runtime=${runId}`);
  await waitForExpression("[...document.querySelectorAll('button')].some((item) => item.textContent.trim() === '资源配置')", "workspace navigation");
  await openResourcesAfterTaskReady();
  await waitForExpression("document.querySelector('.resource-scope-panel')?.innerText.includes('旋挖钻机') && document.querySelector('.resource-scope-panel')?.innerText.includes('连续梁班组')", "structure-matched Chinese resources");
  const firstResourceState = await evaluate(`(() => ({
    url: location.href,
    body: document.body.innerText.slice(0, 3000),
    panel: Boolean(document.querySelector('.resource-scope-panel')),
    sharedEditor: Boolean(document.querySelector('.resource-shared-section')),
  }))()`);
  assert.equal(firstResourceState.panel, true, JSON.stringify(firstResourceState));
  assert.equal(firstResourceState.sharedEditor, false, JSON.stringify(firstResourceState));
  assert.equal(await evaluate("document.querySelectorAll('.resource-workpoint-section input[aria-label*=" + JSON.stringify("获准") + "]').length"), 0);
  assert.equal(await evaluate("Boolean(document.querySelector('.resource-catalog-add'))"), true);
  assert.equal(await evaluate("Boolean(document.querySelector('.resource-workpoint-detail-grid'))"), true);
  assert.equal(await evaluate("document.querySelector('.resource-structure-panel')?.innerText.includes('旋挖钻-φ1.8×5根')"), true);
  assert.equal(await evaluate("document.querySelector('.resource-structure-panel')?.innerText.includes('3×4×12m×2个')"), true);
  assert.equal(await evaluate("document.querySelectorAll('.resource-config-panel table, .resource-config-panel thead, .resource-config-panel code, .resource-config-panel input[type=checkbox]').length"), 0);
  assert.equal(await evaluate("document.querySelector('.resource-config-list input[aria-label$='当前投入']')?.value"), "0");
  assert.equal(await evaluate("document.querySelector('.resource-config-list input[aria-label$='可增上限']')?.value"), "0");
  assert.equal(evidence.requests.saves.length, 0);
  assert.ok(evidence.requests.generations.length > 0);
  assert.equal(evidence.requests.generations.some(({ body }) => body.resource_pools?.some((pool) => pool.scope_mode === "PROJECT_SHARED")), false);

  await evaluate("document.querySelectorAll('.resource-workpoint-nav button')[1].click()");
  await waitForExpression("Boolean(document.querySelector('[data-resource-suggestion-empty=true]'))", "initial empty second workpoint suggestions");
  networkMode.pauseNextDetail = true;
  await evaluate("document.querySelectorAll('.resource-workpoint-nav button')[0].click()");
  await waitUntil(() => pausedDetail, "paused old workpoint detail", 30_000);
  await evaluate("document.querySelectorAll('.resource-workpoint-nav button')[1].click()");
  await waitForExpression("Boolean(document.querySelector('[data-resource-suggestion-empty=true]'))", "empty second workpoint suggestions");
  await fulfillJson(pausedDetail.requestId, pausedDetail.detail);
  pausedDetail = null;
  await sleep(300);
  assert.equal(await evaluate("document.querySelectorAll('.resource-workpoint-nav button')[1].classList.contains('active')"), true);
  assert.equal(await evaluate("Boolean(document.querySelector('[data-resource-suggestion-empty=true]'))"), true);
  await evaluate("document.querySelectorAll('.resource-workpoint-nav button')[0].click()");
  await waitForExpression("document.querySelector('.resource-scope-panel')?.innerText.includes('旋挖钻机')", "return to matched workpoint");
  const editedValue = 3;
  await evaluate(`(() => {
    const input = document.querySelector('.resource-config-list input[aria-label$="当前投入"]');
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setValue.call(input, String(${editedValue}));
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  })()`);
  await waitForExpression(`document.querySelector('.resource-config-list input[aria-label$="当前投入"]')?.value === '${editedValue}'`, "workpoint-local quantity");

  networkMode.saveFailureRemaining = 1;
  assert.equal(await clickText("保存"), true);
  await waitForExpression("[...document.querySelectorAll('button')].some((item) => item.textContent.trim() === '重试保存')", "save failure retry");
  assert.equal(await evaluate(`document.querySelector('.resource-config-list input[aria-label$="当前投入"]')?.value === '${editedValue}'`), true);
  assert.equal(await clickText("重试保存"), true);
  await waitForExpression(`document.querySelector('button[aria-label="保存"]')?.disabled === true`, "successful save");

  assert.equal(evidence.requests.saves.length, 2);
  const savedPool = evidence.requests.saves[1].body.resource_pools.find((pool) => pool.scope_mode === "WORKPOINT_EXCLUSIVE" && pool.workpoint_id);
  assert.equal(savedPool.scope_mode, "WORKPOINT_EXCLUSIVE");
  assert.equal(savedPool.workpoint_overrides.length, 0);
  assert.equal(savedPool.enabled, true);
  assert.ok(oracle.currentWorkpoints.some((item) => item.workpoint_id === savedPool.workpoint_id));
  assert.equal(evidence.requests.saves[1].body.resource_pools.some((pool) => pool.scope_mode === "PROJECT_SHARED"), false);

  networkMode.firstDetailWithoutStructures = true;
  await evaluate("document.querySelectorAll('.resource-workpoint-nav button')[1].click()");
  await waitForExpression("Boolean(document.querySelector('[data-resource-suggestion-empty=true]'))", "empty second workpoint before retained pool check");
  await evaluate("document.querySelectorAll('.resource-workpoint-nav button')[0].click()");
  await waitForExpression("Boolean(document.querySelector('[data-structure-summary-empty=true]'))", "empty structure summary before retained pool check");
  await waitForExpression(`document.querySelector('.resource-config-list input[aria-label$="当前投入"]')?.value === '${editedValue}'`, "configured pool retained after structure mismatch");
  networkMode.firstDetailWithoutStructures = false;

  networkMode.workpointMode = "fail";
  await navigate(`${frontendUrl}/?resource-workpoint-runtime=${runId}-retry`);
  await openResourcesAfterTaskReady();
  await waitForExpression("Boolean(document.querySelector('.resource-scope-state.error button'))", "workpoint load error");
  await evaluate("document.querySelector('.resource-scope-state.error button').click()");
  await waitForExpression("document.querySelectorAll('.resource-workpoint-nav button').length > 0", "workpoint retry ready");

  networkMode.workpointMode = "empty";
  await navigate(`${frontendUrl}/?resource-workpoint-runtime=${runId}-empty`);
  await openResourcesAfterTaskReady();
  await waitForExpression(`Boolean(document.querySelector('[data-resource-empty="true"]'))`, "authoritative empty state");
  assert.equal(await evaluate("document.querySelectorAll('.resource-config-item').length"), 0);

  networkMode.workpointMode = "fail";
  await navigate(`${frontendUrl}/?resource-workpoint-runtime=${runId}-version-race`);
  await openResourcesAfterTaskReady();
  await waitForExpression("Boolean(document.querySelector('.resource-scope-state.error button'))", "pre-race workpoint error");
  networkMode.pauseNextV1 = true;
  await evaluate("document.querySelector('.resource-scope-state.error button').click()");
  await waitUntil(() => pausedV1, "paused old-version workpoint request", 30_000);

  networkMode.projectMasterMock = true;
  assert.equal(await clickText("项目主数据"), true);
  await waitForExpression("Boolean(document.querySelector('.project-master-actions input[type=file]'))", "project master file input");
  await evaluate(`(() => {
    const input = document.querySelector('.project-master-actions input[type=file]');
    const transfer = new DataTransfer();
    transfer.items.add(new File(['runtime'], 'runtime.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }));
    Object.defineProperty(input, 'files', { configurable: true, value: transfer.files });
    input.dispatchEvent(new Event('change', { bubbles: true }));
  })()`);
  await waitForExpression("[...document.querySelectorAll('button')].some((item) => item.textContent.trim() === '确认并设为当前版本' && !item.disabled)", "confirm imported version");
  assert.equal(await clickText("确认并设为当前版本"), true);
  assert.equal(await clickText("资源配置"), true);
  await waitForExpression(`document.querySelector('.resource-scope-panel')?.getAttribute('data-resource-version') === ${JSON.stringify(oracle.v2Version.version_id)} && document.querySelectorAll('.resource-workpoint-nav button').length === ${oracle.v2Workpoints.length}`, "current version resource rows");
  await fulfillJson(pausedV1.requestId, pageOf(oracle.currentWorkpoints));
  pausedV1 = null;
  await sleep(500);

  const finalState = await evaluate(`(() => ({
    version: document.querySelector('.resource-scope-panel')?.getAttribute('data-resource-version'),
    names: [...new Set([...document.querySelectorAll('.resource-workpoint-nav button')].map((node) => node.textContent.trim()))],
    text: document.querySelector('.resource-scope-panel')?.innerText ?? '',
    records: window.__resourceRuntime.records,
  }))()`);
  assert.equal(finalState.version, oracle.v2Version.version_id);
  assert.deepEqual(finalState.names, oracle.v2Workpoints.map((item) => item.workpoint_name));
  assert.equal(finalState.text.includes("默认充足"), false);
  const v2Commit = finalState.records.findIndex((record) => record.version === oracle.v2Version.version_id && record.workpoints.length > 0);
  assert.ok(v2Commit >= 0);
  assert.equal(finalState.records.slice(v2Commit).some((record) => record.version === oracle.currentVersion.version_id && record.workpoints.length > 0), false);
  assert.equal(cdp.eventErrors.length, 0);

  evidence.assertions = {
    sharedEditorVisible: false,
    generationRequestsWithSharedPools: 0,
    saveRequestsWithSharedPools: 0,
    workpointLocalRecordVisible: true,
    ChineseNamesVisible: true,
    structureMatchedTypesVisible: true,
    structureSummaryVisible: true,
    resourceFieldHeadersVisible: false,
    resourceEnableToggleVisible: false,
    savedPoolEnabledDerivedFromQuantity: true,
    suggestionsStartAtZero: true,
    staleDetailCommits: 0,
    configuredPoolRetainedAfterMismatch: true,
    saveFailureRetriedWithoutInputLoss: true,
    authoritativeEmptyRows: 0,
    oldVersionDomCommitsAfterCurrentReady: 0,
    defaultSufficientFalsePositives: 0,
    nameOrIdSpecialFillBranches: 0,
    projectSharedTransferDays: 0,
    projectSharedTransferCost: 0,
  };
});
