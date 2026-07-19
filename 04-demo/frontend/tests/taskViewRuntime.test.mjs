import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import {
  createWriteStream,
  existsSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { createServer } from "node:net";
import { basename, dirname, resolve } from "node:path";
import test, { after, before } from "node:test";
import { fileURLToPath } from "node:url";

const testRoot = dirname(fileURLToPath(import.meta.url));
const frontendRoot = resolve(testRoot, "..");
const demoRoot = resolve(frontendRoot, "..");
const repoRoot = resolve(demoRoot, "..");
const backendRoot = resolve(demoRoot, "backend");
const runId = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
const logDir = resolve(repoRoot, ".local-data", "logs", `${runId}-task-view-runtime`);
const tempDir = resolve(repoRoot, ".local-data", "tmp", "task-view-runtime", runId);
const frontendUrl = process.env.TASK_VIEW_RUNTIME_FRONTEND_URL ?? "http://127.0.0.1:5173";
const apiUrl = process.env.TASK_VIEW_RUNTIME_API_URL ?? "http://127.0.0.1:8000";
const timeoutMs = Number(process.env.TASK_VIEW_RUNTIME_TIMEOUT_MS ?? 180_000);

mkdirSync(logDir, { recursive: true });
mkdirSync(tempDir, { recursive: true });

const ownedProcesses = [];
const evidence = {
  runId,
  command: "npm run test:task-view-runtime",
  nodeVersion: process.version,
  logDir,
  tempDir,
  runtime: null,
  browser: null,
  oracle: null,
  scenarios: {},
};

let browserProcess = null;
let cdp = null;
let fullPage = null;
let oracle = null;

function now() {
  return new Date().toISOString();
}

function sleep(ms) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

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
  const suffix = lastError ? ` Last error: ${lastError.message}` : "";
  throw new Error(`Timed out waiting for ${label}.${suffix}`);
}

async function httpOk(url, timeout = 2_000) {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(timeout) });
    return response.ok;
  } catch {
    return false;
  }
}

function processMetadataForPort(port) {
  if (process.platform !== "win32") return null;
  try {
    const netstat = spawnSync("netstat.exe", ["-ano", "-p", "tcp"], { encoding: "utf8" });
    const listener = netstat.stdout
      .split(/\r?\n/)
      .map((line) => line.trim())
      .find((line) => line.includes(`:${port} `) && /\sLISTENING\s/i.test(line));
    if (!listener) return null;
    const pid = Number(listener.split(/\s+/).at(-1));
    if (!Number.isInteger(pid)) return null;
    const command = [
      `$p=Get-Process -Id ${pid} -ErrorAction Stop;`,
      `[pscustomobject]@{pid=$p.Id;process=$p.ProcessName;startTime=$p.StartTime.ToString('o')} | ConvertTo-Json -Compress`,
    ].join(" ");
    const result = spawnSync("powershell.exe", ["-NoProfile", "-Command", command], { encoding: "utf8" });
    return result.status === 0 ? JSON.parse(result.stdout.trim()) : { pid };
  } catch {
    return null;
  }
}

function runtimeVersions() {
  const vitePackage = JSON.parse(readFileSync(vitePackagePath(), "utf8"));
  const python = resolvePython();
  const pythonResult = spawnSync(
    python,
    ["-c", "import fastapi,sys,uvicorn;print(sys.version.split()[0]+' fastapi='+fastapi.__version__+' uvicorn='+uvicorn.__version__)"],
    { cwd: backendRoot, encoding: "utf8" },
  );
  return {
    node: process.version,
    vite: vitePackage.version,
    pythonFastApiUvicorn: pythonResult.status === 0 ? pythonResult.stdout.trim() : "unavailable",
  };
}

function vitePackagePath() {
  return fileURLToPath(import.meta.resolve("vite/package.json"));
}

function resolvePython() {
  const candidates = [
    process.env.PYTHON,
    resolve(repoRoot, ".venv", "Scripts", "python.exe"),
    resolve(demoRoot, ".venv", "Scripts", "python.exe"),
    resolve(backendRoot, ".venv", "Scripts", "python.exe"),
  ].filter(Boolean);
  return candidates.find((candidate) => existsSync(candidate)) ?? "python";
}

function startLoggedProcess(name, command, args, cwd) {
  const stdoutPath = resolve(logDir, `${name}.stdout.log`);
  const stderrPath = resolve(logDir, `${name}.stderr.log`);
  const stdout = createWriteStream(stdoutPath, { flags: "a" });
  const stderr = createWriteStream(stderrPath, { flags: "a" });
  const startedAt = now();
  const child = spawn(command, args, {
    cwd,
    env: { ...process.env, PYTHONUTF8: "1" },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  child.stdout.pipe(stdout);
  child.stderr.pipe(stderr);
  const entry = { name, child, stdout, stderr, stdoutPath, stderrPath, startedAt };
  ownedProcesses.push(entry);
  return entry;
}

async function ensureRuntimeService({ name, healthUrl, command, args, cwd, port }) {
  const observedAt = now();
  if (await httpOk(healthUrl)) {
    return {
      name,
      mode: "reused",
      observedAt,
      listener: processMetadataForPort(port),
    };
  }

  const processEntry = startLoggedProcess(name, command, args, cwd);
  await waitUntil(() => httpOk(healthUrl), `${name} health endpoint`, 90_000, 250);
  return {
    name,
    mode: "started",
    startedAt: processEntry.startedAt,
    healthyAt: now(),
    listener: processMetadataForPort(port),
    stdoutPath: processEntry.stdoutPath,
    stderrPath: processEntry.stderrPath,
  };
}

async function ensureRuntime() {
  const backend = await ensureRuntimeService({
    name: "fastapi",
    healthUrl: `${apiUrl}/api/health`,
    command: resolvePython(),
    args: ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd: backendRoot,
    port: 8000,
  });
  const viteEntry = resolve(dirname(vitePackagePath()), "bin", "vite.js");
  const vite = await ensureRuntimeService({
    name: "vite",
    healthUrl: `${frontendUrl}/`,
    command: process.execPath,
    args: [viteEntry, "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
    cwd: frontendRoot,
    port: 5173,
  });
  return { versions: runtimeVersions(), fastapi: backend, vite };
}

async function stopOwnedProcesses() {
  for (const entry of [...ownedProcesses].reverse()) {
    if (entry.child.exitCode === null) entry.child.kill();
    await Promise.race([
      new Promise((resolvePromise) => entry.child.once("exit", resolvePromise)),
      sleep(3_000),
    ]);
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
  const candidates = process.platform === "win32"
    ? [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        resolve(process.env.LOCALAPPDATA ?? "", "Google", "Chrome", "Application", "chrome.exe"),
        resolve(process.env.LOCALAPPDATA ?? "", "Microsoft", "Edge", "Application", "msedge.exe"),
      ]
    : ["/usr/bin/microsoft-edge", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"];
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
    this.ready = new Promise((resolvePromise, rejectPromise) => {
      this.webSocket.addEventListener("open", resolvePromise, { once: true });
      this.webSocket.addEventListener("error", rejectPromise, { once: true });
    });
    this.webSocket.addEventListener("message", (event) => this.handleMessage(event.data));
    this.webSocket.addEventListener("close", () => {
      for (const { reject } of this.pending.values()) reject(new Error("CDP connection closed."));
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
    if (!message.method) return;
    const keys = [`${message.sessionId ?? "*"}:${message.method}`, `*:${message.method}`];
    for (const key of keys) {
      for (const listener of this.listeners.get(key) ?? []) {
        Promise.resolve(listener(message.params ?? {}, message.sessionId)).catch((error) => {
          this.eventErrors.push(error);
        });
      }
    }
  }

  async send(method, params = {}, sessionId = undefined) {
    await this.ready;
    const id = this.nextId++;
    const message = { id, method, params };
    if (sessionId) message.sessionId = sessionId;
    const response = new Promise((resolvePromise, rejectPromise) => {
      this.pending.set(id, { resolve: resolvePromise, reject: rejectPromise, method });
    });
    this.webSocket.send(JSON.stringify(message));
    return response;
  }

  on(method, listener, sessionId = "*") {
    const key = `${sessionId}:${method}`;
    const listeners = this.listeners.get(key) ?? new Set();
    listeners.add(listener);
    this.listeners.set(key, listeners);
    return () => listeners.delete(listener);
  }
}

async function launchBrowser() {
  const executable = findBrowserExecutable();
  const port = await freeTcpPort();
  const physicalProfileDir = resolve(tempDir, "browser-profile");
  let profileDir = physicalProfileDir;
  let mappedDrive = null;
  if (process.platform === "win32") {
    const drive = ["Z:", "Y:", "X:", "W:", "V:"].find((candidate) => !existsSync(`${candidate}\\`));
    if (drive) {
      const mapped = spawnSync("subst.exe", [drive, tempDir], { encoding: "utf8" });
      if (mapped.status === 0) {
        mappedDrive = drive;
        profileDir = `${drive}\\browser-profile`;
      }
    }
  }
  mkdirSync(profileDir, { recursive: true });
  const stdoutPath = resolve(logDir, "browser.stdout.log");
  const stderrPath = resolve(logDir, "browser.stderr.log");
  const stdout = createWriteStream(stdoutPath, { flags: "a" });
  const stderr = createWriteStream(stderrPath, { flags: "a" });
  const launchedAt = now();
  const child = spawn(executable, [
    "--headless=new",
    "--disable-gpu",
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

  let version;
  try {
    version = await waitUntil(async () => {
      try {
        const response = await fetch(`http://127.0.0.1:${port}/json/version`);
        return response.ok ? await response.json() : null;
      } catch {
        return null;
      }
    }, "browser DevTools endpoint", 30_000, 100);
  } catch (error) {
    if (child.exitCode === null) child.kill();
    stdout.end();
    stderr.end();
    if (mappedDrive) spawnSync("subst.exe", [mappedDrive, "/D"]);
    throw error;
  }

  return {
    child,
    executable,
    launchedAt,
    profileDir,
    physicalProfileDir,
    mappedDrive,
    stdout,
    stderr,
    stdoutPath,
    stderrPath,
    product: version.Browser,
    protocolVersion: version["Protocol-Version"],
    webSocketUrl: version.webSocketDebuggerUrl,
  };
}

async function closeBrowser() {
  if (!browserProcess) return;
  try {
    if (cdp) await cdp.send("Browser.close");
  } catch {
    if (browserProcess.child.exitCode === null) browserProcess.child.kill();
  }
  await Promise.race([
    new Promise((resolvePromise) => browserProcess.child.once("exit", resolvePromise)),
    sleep(5_000),
  ]);
  if (browserProcess.child.exitCode === null) browserProcess.child.kill();
  browserProcess.stdout.end();
  browserProcess.stderr.end();
  const safeTempRoot = resolve(repoRoot, ".local-data", "tmp", "task-view-runtime").toLowerCase();
  if (browserProcess.physicalProfileDir.toLowerCase().startsWith(`${safeTempRoot.toLowerCase()}\\`)) {
    try {
      rmSync(browserProcess.physicalProfileDir, { recursive: true, force: true });
    } catch {
      // A browser helper may release its final handle slightly after Browser.close.
    }
  }
  if (browserProcess.mappedDrive) spawnSync("subst.exe", [browserProcess.mappedDrive, "/D"]);
}

function observerScript(rawTokenGroups) {
  return `(() => {
    const rawTokenGroups = ${JSON.stringify(rawTokenGroups)};
    const records = [];
    let sequence = 0;
    let lastSignature = null;
    const text = (node) => (node?.textContent ?? "").replace(/\\s+/g, " ").trim();
    const unique = (values) => Array.from(new Set(values.filter(Boolean)));
    const segments = (values) => unique(values.flatMap((value) => value.split(/\\s+\\/\\s+/).map((part) => part.trim())));
    const collect = (reason, mutationCount = 0) => {
      const rows = Array.from(document.querySelectorAll(".task-view-table tbody tr"));
      const parentTitles = unique(Array.from(document.querySelectorAll(".task-view-parent-title strong"), text));
      const bridgeSectionCells = unique(rows.map((row) => text(row.children[1])));
      const sideCells = unique(rows.map((row) => text(row.children[2])));
      const taskNames = unique(rows.map((row) => text(row.children[5])));
      const alert = document.querySelector('.task-view-empty[role="alert"]');
      const loading = document.querySelector('.task-view-empty[role="status"]');
      const state = alert ? "error" : loading ? "loading" : rows.length > 0 ? "ready" : document.querySelector(".task-view-empty") ? "empty" : "absent";
      const relevantSegments = segments([...parentTitles, ...bridgeSectionCells, ...sideCells, ...taskNames]);
      const hits = Object.fromEntries(Object.entries(rawTokenGroups).map(([group, tokens]) => [
        group,
        relevantSegments.filter((value) => tokens.includes(value)),
      ]));
      const identityVersion = document.querySelector("[data-runtime-version]")?.getAttribute("data-runtime-version") ?? null;
      const signature = JSON.stringify({ state, rows: rows.length, parentTitles, bridgeSectionCells, sideCells, taskNames, hits, identityVersion });
      if (signature === lastSignature) return;
      lastSignature = signature;
      records.push({
        sequence: ++sequence,
        at: performance.now(),
        reason,
        mutationCount,
        state,
        rowCount: rows.length,
        parentTitles,
        bridgeSectionCells,
        sideCells,
        taskNames,
        hits,
        identityVersion,
      });
    };
    const start = () => {
      const observer = new MutationObserver((mutations) => collect("mutation", mutations.length));
      observer.observe(document, { subtree: true, childList: true, characterData: true });
      collect("observer-start");
      window.__taskViewRuntime = {
        records,
        capture: () => collect("manual"),
        reset: () => { records.length = 0; sequence = 0; lastSignature = null; },
      };
    };
    if (document.documentElement) start();
    else document.addEventListener("DOMContentLoaded", start, { once: true });
  })();`;
}

async function createPage(rawTokenGroups) {
  const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
  await Promise.all([
    cdp.send("Page.enable", {}, sessionId),
    cdp.send("Runtime.enable", {}, sessionId),
    cdp.send("Network.enable", {}, sessionId),
  ]);
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: observerScript(rawTokenGroups) }, sessionId);
  return { targetId, sessionId };
}

async function evaluate(page, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  }, page.sessionId);
  if (result.exceptionDetails) {
    const description = result.exceptionDetails.exception?.description ?? result.exceptionDetails.text;
    throw new Error(`Browser evaluation failed: ${description}`);
  }
  return result.result.value;
}

async function waitForPage(page, expression, label, limitMs = timeoutMs) {
  return waitUntil(() => evaluate(page, expression), label, limitMs, 100);
}

async function navigate(page, url) {
  await cdp.send("Page.navigate", { url }, page.sessionId);
  await waitForPage(page, "document.readyState === 'complete'", `page load for ${url}`, 30_000);
}

async function hardReload(page) {
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true }, page.sessionId);
  await cdp.send("Network.clearBrowserCache", {}, page.sessionId);
  await cdp.send("Page.reload", { ignoreCache: true }, page.sessionId);
  await waitForPage(page, "document.readyState === 'complete'", "hard reload", 30_000);
}

async function json(url, init = undefined) {
  let lastError = null;
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      const response = await fetch(url, { ...init, signal: AbortSignal.timeout(timeoutMs) });
      if (!response.ok) throw new Error(`${response.status} ${url}: ${await response.text()}`);
      return await response.json();
    } catch (error) {
      lastError = error;
      if (attempt < 3) await sleep(150 * attempt);
    }
  }
  throw new Error(`Failed to read ${url} after 3 attempts: ${lastError?.message ?? "unknown error"}`);
}

async function loadOracle() {
  const scenario = await json(`${apiUrl}/api/demo-scenario`);
  const current = await json(
    `${apiUrl}/api/projects/${encodeURIComponent(scenario.project.project_id)}/project-master/versions/current`,
  );
  const versionedScenario = { ...scenario, project_data_version_id: current.version_id };
  const [currentDetail, versionPage] = await Promise.all([
    json(`${apiUrl}/api/project-master/versions/${encodeURIComponent(current.version_id)}`),
    json(`${apiUrl}/api/projects/${encodeURIComponent(scenario.project.project_id)}/project-master/versions?page=1&page_size=50`),
  ]);
  const generated = await json(`${apiUrl}/api/generate-schedule-input`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(versionedScenario),
  });
  const tasks = generated.schedule_input.tasks;
  const workpointIds = [...new Set(tasks.map((task) => task.bridge_id).filter(Boolean))].sort();
  const workpoints = [];
  for (const workpointId of workpointIds) {
    workpoints.push(await json(
      `${apiUrl}/api/project-master/versions/${encodeURIComponent(current.version_id)}/workpoints/${encodeURIComponent(workpointId)}`,
    ));
  }
  const structures = workpoints.flatMap((workpoint) => workpoint.structures);
  return {
    versionId: current.version_id,
    scenario: versionedScenario,
    currentVersion: current,
    currentVersionDetail: currentDetail,
    versionPage,
    generated,
    workpoints,
    taskCount: tasks.length,
    taskNames: [...new Set(tasks.map((task) => task.name).filter(Boolean))],
    workpointNames: [...new Set(workpoints.map((workpoint) => workpoint.workpoint_name).filter(Boolean))],
    sectionNames: [...new Set(structures.map((structure) => structure.section_name).filter(Boolean))],
    rawTokenGroups: {
      bridgeId: workpointIds,
      workSectionId: [...new Set(tasks.map((task) => task.work_section_id).filter(Boolean))],
      sectionCode: [...new Set(structures.map((structure) => structure.section_code).filter(Boolean))],
      placeholder: ["-"],
    },
  };
}

function flattenedHits(records) {
  const totals = {};
  for (const record of records) {
    for (const [group, hits] of Object.entries(record.hits)) {
      totals[group] = (totals[group] ?? 0) + hits.length;
    }
  }
  return totals;
}

function taskNameCommitCount(records) {
  let previous = "";
  let count = 0;
  for (const record of records) {
    const signature = JSON.stringify(record.taskNames);
    if (record.taskNames.length > 0 && signature !== previous) count += 1;
    previous = signature;
  }
  return count;
}

function transitionSummary(records) {
  return records.map((record) => ({
    sequence: record.sequence,
    state: record.state,
    rowCount: record.rowCount,
    taskNameCount: record.taskNames.length,
    identityVersion: record.identityVersion,
    hits: Object.fromEntries(Object.entries(record.hits).map(([key, values]) => [key, values.length])),
  }));
}

function assertZeroHits(records) {
  const hits = flattenedHits(records);
  for (const [group, count] of Object.entries(hits)) assert.equal(count, 0, `${group} visible hit count`);
  return hits;
}

async function currentTaskRows(page) {
  return evaluate(page, `Array.from(document.querySelectorAll('.task-view-table tbody tr')).map((row) => ({
    bridgeSection: (row.children[1]?.textContent ?? '').replace(/\\s+/g, ' ').trim(),
    side: (row.children[2]?.textContent ?? '').replace(/\\s+/g, ' ').trim(),
    taskName: (row.children[5]?.textContent ?? '').replace(/\\s+/g, ' ').trim(),
  }))`);
}

function assertAuthoritativeRows(rows) {
  assert.equal(rows.length, oracle.taskCount, "the ready DOM must contain every generated task exactly once");
  const workpointNames = new Set(oracle.workpointNames);
  const sectionNames = new Set(oracle.sectionNames);
  const taskNames = new Set(oracle.taskNames);
  const invalid = rows.filter((row) => {
    const [workpointName, sectionName] = row.bridgeSection.split(/\s+\/\s+/);
    return !workpointNames.has(workpointName)
      || !sectionNames.has(sectionName)
      || !row.side
      || row.side === "-"
      || !taskNames.has(row.taskName);
  });
  assert.deepEqual(invalid.slice(0, 5), [], "every ready row must use authoritative names");
}

function projectMasterDetailFromUrl(url) {
  const match = new URL(url).pathname.match(/^\/api\/project-master\/versions\/([^/]+)\/workpoints\/([^/]+)$/);
  if (!match) return null;
  return {
    versionId: decodeURIComponent(match[1]),
    workpointId: decodeURIComponent(match[2]),
  };
}

function generatedVariant(generated, versionId, workpointIds) {
  const selectedWorkpointIds = new Set(workpointIds);
  const tasks = generated.schedule_input.tasks.filter((task) => selectedWorkpointIds.has(task.bridge_id));
  const taskIds = new Set(tasks.map((task) => task.id));
  return {
    ...generated,
    schedule_input: {
      ...generated.schedule_input,
      tasks,
      precedence_links: generated.schedule_input.precedence_links.filter((link) => (
        taskIds.has(link.predecessor_id) && taskIds.has(link.successor_id)
      )),
    },
    source_summary: {
      ...generated.source_summary,
      bridge_count: selectedWorkpointIds.size,
      project_data_version_id: versionId,
    },
  };
}

function variantOracle(generated, workpoints) {
  const workpointIds = [...new Set(generated.schedule_input.tasks.map((task) => task.bridge_id).filter(Boolean))].sort();
  const allowedIds = new Set(workpointIds);
  const selectedWorkpoints = workpoints.filter((workpoint) => allowedIds.has(workpoint.workpoint_id));
  return {
    versionId: generated.source_summary.project_data_version_id,
    workpointIds,
    taskCount: generated.schedule_input.tasks.length,
    taskNames: generated.schedule_input.tasks.map((task) => task.name).sort(),
    uniqueTaskNames: [...new Set(generated.schedule_input.tasks.map((task) => task.name))].sort(),
    workpointNames: selectedWorkpoints.map((workpoint) => workpoint.workpoint_name),
    sectionNames: [...new Set(selectedWorkpoints.flatMap((workpoint) => (
      workpoint.structures.map((structure) => structure.section_name).filter(Boolean)
    )))],
  };
}

function assertRowsMatchVariant(rows, expected) {
  assert.equal(rows.length, expected.taskCount, "the production DOM must contain the controlled current task set exactly once");
  assert.deepEqual(rows.map((row) => row.taskName).sort(), expected.taskNames, "task names must come from the controlled generate response");
  const workpointNames = new Set(expected.workpointNames);
  const sectionNames = new Set(expected.sectionNames);
  const invalid = rows.filter((row) => {
    const [workpointName, sectionName] = row.bridgeSection.split(/\s+\/\s+/);
    return !workpointNames.has(workpointName)
      || !sectionNames.has(sectionName)
      || !row.side
      || row.side === "-";
  });
  assert.deepEqual(invalid.slice(0, 5), [], "each current row must use authoritative project-master names");
}

async function fulfillJson(page, requestId, payload, responseCode = 200) {
  await cdp.send("Fetch.fulfillRequest", {
    requestId,
    responseCode,
    responseHeaders: [{ name: "content-type", value: "application/json; charset=utf-8" }],
    body: Buffer.from(JSON.stringify(payload), "utf8").toString("base64"),
  }, page.sessionId);
}

function trackPageNetwork(page) {
  const pending = new Map();
  const failed = [];
  const recentResponses = [];
  const removeRequest = cdp.on("Network.requestWillBeSent", (params) => {
    pending.set(params.requestId, {
      requestId: params.requestId,
      method: params.request.method,
      url: params.request.url,
      type: params.type,
      startedAt: params.wallTime ? new Date(params.wallTime * 1_000).toISOString() : now(),
      responseStatus: null,
    });
  }, page.sessionId);
  const removeResponse = cdp.on("Network.responseReceived", (params) => {
    const request = pending.get(params.requestId);
    if (request) request.responseStatus = params.response.status;
  }, page.sessionId);
  const removeFinished = cdp.on("Network.loadingFinished", (params) => {
    const request = pending.get(params.requestId);
    if (!request) return;
    recentResponses.push({ ...request, encodedDataLength: params.encodedDataLength });
    if (recentResponses.length > 30) recentResponses.shift();
    pending.delete(params.requestId);
  }, page.sessionId);
  const removeFailed = cdp.on("Network.loadingFailed", (params) => {
    const request = pending.get(params.requestId);
    failed.push({
      ...(request ?? { requestId: params.requestId }),
      errorText: params.errorText,
      canceled: params.canceled ?? false,
      blockedReason: params.blockedReason ?? null,
    });
    if (failed.length > 30) failed.shift();
    pending.delete(params.requestId);
  }, page.sessionId);
  return {
    snapshot: () => ({
      pending: [...pending.values()],
      failed: [...failed],
      recentResponses: [...recentResponses],
    }),
    dispose: () => {
      removeRequest();
      removeResponse();
      removeFinished();
      removeFailed();
    },
  };
}

async function probeService(url, port) {
  const startedAt = now();
  const startedMs = Date.now();
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(2_000) });
    return {
      url,
      ok: response.ok,
      status: response.status,
      elapsedMs: Date.now() - startedMs,
      startedAt,
      listener: processMetadataForPort(port),
    };
  } catch (error) {
    return {
      url,
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      elapsedMs: Date.now() - startedMs,
      startedAt,
      listener: processMetadataForPort(port),
    };
  }
}

async function collectT036Failure(page, tracker, phase, error) {
  let pageState;
  try {
    pageState = await evaluate(page, `(() => {
      const records = window.__taskViewRuntime?.records ?? [];
      return {
        url: location.href,
        readyState: document.readyState,
        taskRowCount: document.querySelectorAll('.task-view-table tbody tr').length,
        loadingVisible: Boolean(document.querySelector('.task-view-empty[role="status"]')),
        errorVisible: Boolean(document.querySelector('.task-view-empty[role="alert"]')),
        lastMutation: records.at(-1) ?? null,
        visibleTextSample: (document.body?.innerText ?? '').replace(/\s+/g, ' ').slice(0, 800),
      };
    })()`);
  } catch (pageError) {
    pageState = { evaluationError: pageError instanceof Error ? pageError.message : String(pageError) };
  }
  const [vite, fastapi] = await Promise.all([
    probeService(`${frontendUrl}/`, 5173),
    probeService(`${apiUrl}/api/health`, 8000),
  ]);
  return {
    status: "failed",
    failedAt: now(),
    phase,
    error: error instanceof Error ? error.message : String(error),
    pageState,
    network: tracker.snapshot(),
    services: { vite, fastapi },
    overlapPrevention: "warm ready barrier before measured hard reload",
  };
}

function findWorkbookFixture() {
  const root = resolve(
    repoRoot,
    "01-customer-validation",
    "workpackages",
    "lugu-validation-material",
    "project-master",
    "results",
  );
  const pending = [root];
  while (pending.length > 0) {
    const directory = pending.shift();
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) pending.push(path);
      else if (entry.isFile() && entry.name.toLowerCase().endsWith(".xlsx")) return path;
    }
  }
  throw new Error(`No project-master workbook fixture found under ${root}`);
}

before(async () => {
  evidence.runtime = await ensureRuntime();
  oracle = await loadOracle();
  evidence.oracle = {
    versionId: oracle.versionId,
    taskCount: oracle.taskCount,
    workpointCount: oracle.rawTokenGroups.bridgeId.length,
    rawTokenCounts: Object.fromEntries(Object.entries(oracle.rawTokenGroups).map(([key, values]) => [key, values.length])),
  };
  browserProcess = await launchBrowser();
  evidence.browser = {
    executable: browserProcess.executable,
    product: browserProcess.product,
    protocolVersion: browserProcess.protocolVersion,
    launchedAt: browserProcess.launchedAt,
    stdoutPath: browserProcess.stdoutPath,
    stderrPath: browserProcess.stderrPath,
  };
  cdp = new CdpConnection(browserProcess.webSocketUrl);
  await Promise.race([
    cdp.ready,
    sleep(10_000).then(() => { throw new Error("Timed out connecting to the browser CDP WebSocket."); }),
  ]);
});

after(async () => {
  evidence.cdpEventErrors = cdp?.eventErrors.map((error) => error.message) ?? [];
  writeFileSync(resolve(logDir, "task-view-runtime-summary.json"), `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  await closeBrowser();
  await stopOwnedProcesses();
});

test("T036 hard reload commits only an atomic authoritative task-name DOM", { timeout: timeoutMs }, async (t) => {
  fullPage = await createPage(oracle.rawTokenGroups);
  const tracker = trackPageNetwork(fullPage);
  const deadline = Date.now() + Math.max(30_000, timeoutMs - 10_000);
  const remaining = () => Math.max(1_000, deadline - Date.now());
  let phase = "initial-navigation";
  try {
    await navigate(fullPage, `${frontendUrl}/?task-view-runtime=${runId}`);
    phase = "warm-ready-barrier";
    await waitForPage(
      fullPage,
      `document.querySelectorAll('.task-view-table tbody tr').length === ${oracle.taskCount}`,
      "warm authoritative task view before measured reload",
      remaining(),
    );
    const warmReadyAt = now();
    phase = "measured-hard-reload";
    const hardReloadAt = now();
    await hardReload(fullPage);
    phase = "measured-ready";
    await waitForPage(
      fullPage,
      `document.querySelectorAll('.task-view-table tbody tr').length === ${oracle.taskCount}`,
      "complete authoritative task view",
      remaining(),
    );
    const readyAt = now();
    await evaluate(fullPage, "window.__taskViewRuntime.capture()");

    const records = await evaluate(fullPage, "window.__taskViewRuntime.records");
    const rows = await currentTaskRows(fullPage);
    const loadingIndex = records.findIndex((record) => record.state === "loading");
    const readyIndex = records.findIndex((record) => record.rowCount > 0);
    assert.ok(loadingIndex >= 0, "generic loading state must be observed");
    assert.ok(readyIndex > loadingIndex, "authoritative rows must commit only after loading");
    assert.equal(records.some((record) => record.state === "error"), false);
    assert.equal(taskNameCommitCount(records), 1, "task names must commit atomically once");
    assertAuthoritativeRows(rows);
    const zeroHits = assertZeroHits(records);

    const summary = {
      warmReadyAt,
      hardReloadAt,
      readyAt,
      overlapPrevention: "warm ready barrier before measured hard reload",
      transitions: transitionSummary(records),
      taskNameCommits: taskNameCommitCount(records),
      readyRowCount: rows.length,
      zeroHits,
      networkAtReady: tracker.snapshot(),
    };
    evidence.scenarios.T036 = summary;
    t.diagnostic(JSON.stringify(summary));
  } catch (error) {
    const failure = await collectT036Failure(fullPage, tracker, phase, error);
    evidence.scenarios.T036 = failure;
    t.diagnostic(JSON.stringify(failure));
    throw error;
  } finally {
    tracker.dispose();
  }
});

test("T037 one failed workpoint request shows generic error, then real retry commits atomically", { timeout: timeoutMs }, async (t) => {
  assert.ok(fullPage, "T036 must establish the full application page first");
  let failNextWorkpointRequest = true;
  let failedRequestUrl = null;
  let pausedRequestCount = 0;
  const removeListener = cdp.on("Fetch.requestPaused", async (params) => {
    pausedRequestCount += 1;
    if (failNextWorkpointRequest && !failedRequestUrl) {
      failedRequestUrl = params.request.url;
      await cdp.send("Fetch.failRequest", { requestId: params.requestId, errorReason: "Failed" }, fullPage.sessionId);
      return;
    }
    await cdp.send("Fetch.continueRequest", { requestId: params.requestId }, fullPage.sessionId);
  }, fullPage.sessionId);

  await cdp.send("Fetch.enable", {
    patterns: [{ urlPattern: "*/api/project-master/versions/*/workpoints/*", requestStage: "Request" }],
  }, fullPage.sessionId);
  await hardReload(fullPage);
  await waitForPage(fullPage, "Boolean(document.querySelector('.task-view-empty[role=\"alert\"]'))", "generic project-master error");
  await evaluate(fullPage, "window.__taskViewRuntime.capture()");
  const beforeRetry = await evaluate(fullPage, "window.__taskViewRuntime.records");
  assert.ok(failedRequestUrl, "one real workpoint request must be failed by the browser");
  assert.ok(beforeRetry.some((record) => record.state === "loading"));
  assert.equal(beforeRetry.at(-1).state, "error");
  assert.equal(beforeRetry.some((record) => record.rowCount > 0), false, "error path must never commit partial rows");
  assertZeroHits(beforeRetry);

  failNextWorkpointRequest = false;
  await cdp.send("Fetch.disable", {}, fullPage.sessionId);
  removeListener();
  const clicked = await evaluate(fullPage, `(() => {
    const button = document.querySelector('.task-view-empty[role="alert"] button');
    if (!button) return false;
    button.click();
    return true;
  })()`);
  assert.equal(clicked, true, "the page's actual retry button must be clicked");
  await waitForPage(
    fullPage,
    `document.querySelectorAll('.task-view-table tbody tr').length === ${oracle.taskCount}`,
    "complete authoritative task view after retry",
  );
  await evaluate(fullPage, "window.__taskViewRuntime.capture()");

  const records = await evaluate(fullPage, "window.__taskViewRuntime.records");
  const rows = await currentTaskRows(fullPage);
  assertAuthoritativeRows(rows);
  assert.equal(taskNameCommitCount(records), 1, "retry must commit task names atomically once");
  const zeroHits = assertZeroHits(records);
  assert.deepEqual(cdp.eventErrors.map((error) => error.message), []);

  const summary = {
    failedRequestUrl,
    pausedRequestCount,
    beforeRetryTransitions: transitionSummary(beforeRetry),
    fullTransitions: transitionSummary(records),
    partialRowCommitsBeforeRetry: beforeRetry.filter((record) => record.rowCount > 0).length,
    taskNameCommits: taskNameCommitCount(records),
    readyRowCount: rows.length,
    zeroHits,
  };
  evidence.scenarios.T037 = summary;
  t.diagnostic(JSON.stringify(summary));
});

test("T038 same-version production identity switch ignores late workpoint responses", { timeout: timeoutMs }, async (t) => {
  const progress = { status: "running", stage: "closing-prior-production-page", updatedAt: now() };
  evidence.scenarios.T038 = progress;
  const markStage = (stage) => {
    progress.stage = stage;
    progress.updatedAt = now();
  };
  if (fullPage) {
    await cdp.send("Target.closeTarget", { targetId: fullPage.targetId });
    fullPage = null;
  }
  markStage("initial-production-ready");
  const page = await createPage(oracle.rawTokenGroups);
  progress.pageTargetId = page.targetId;
  await navigate(page, `${frontendUrl}/?task-view-runtime=${runId}&scenario=T038`);
  await waitForPage(
    page,
    `document.querySelectorAll('.task-view-table tbody tr').length === ${oracle.taskCount}`,
    "isolated production task view for T038",
  );

  const allWorkpointIds = oracle.rawTokenGroups.bridgeId;
  assert.ok(allWorkpointIds.length >= 6, "the runtime fixture must expose three disjoint identity sets");
  const variantA = generatedVariant(oracle.generated, oracle.versionId, allWorkpointIds.slice(0, 2));
  const variantC = generatedVariant(oracle.generated, oracle.versionId, allWorkpointIds.slice(2, 4));
  const variantB = generatedVariant(oracle.generated, oracle.versionId, allWorkpointIds.slice(-2));
  const expectedA = variantOracle(variantA, oracle.workpoints);
  const expectedC = variantOracle(variantC, oracle.workpoints);
  const expectedB = variantOracle(variantB, oracle.workpoints);
  progress.normalizedIdentitySets = {
    sameVersionA: expectedA.workpointIds,
    sameVersionB: expectedB.workpointIds,
    crossVersionOld: expectedC.workpointIds,
  };
  assert.deepEqual(expectedA.workpointIds.filter((id) => expectedB.workpointIds.includes(id)), [], "controlled identities must be disjoint");
  assert.deepEqual(expectedC.workpointIds.filter((id) => [...expectedA.workpointIds, ...expectedB.workpointIds].includes(id)), [], "the cross-version old identity must bypass the production ready cache");

  const generateRequests = [];
  const detailRequests = [];
  const paused = new Map();
  let phase = "capture-generates";
  const workbookPath = findWorkbookFixture();
  const workpointById = new Map(oracle.workpoints.map((workpoint) => [workpoint.workpoint_id, workpoint]));
  const cross = {
    newVersionId: `runtime-version-${runId}`,
    batchId: `runtime-batch-${runId}`,
    imported: false,
    confirmed: false,
    importRequests: [],
    confirmRequests: [],
  };
  const versionFields = {
    version_id: cross.newVersionId,
    project_id: oracle.currentVersionDetail.project_id,
    version_no: oracle.currentVersionDetail.version_no + 1,
    content_fingerprint: `runtime-fingerprint-${runId}`,
    source_batch_id: cross.batchId,
    base_version_id: oracle.versionId,
    counts: oracle.currentVersionDetail.counts,
    created_at: now(),
    created_by: "runtime-gate",
  };
  const draftVersion = {
    ...versionFields,
    status: "draft",
    confirmed_at: null,
    confirmed_by: null,
    diff_counts: { added: 0, modified: 0, deleted: 0 },
    diff_entries: [],
    warning_codes: [],
  };
  const confirmedVersion = {
    ...draftVersion,
    status: "confirmed",
    confirmed_at: now(),
    confirmed_by: "runtime-gate",
  };
  const importBatch = {
    batch_id: cross.batchId,
    project_id: oracle.currentVersionDetail.project_id,
    status: "ready",
    file_name: basename(workbookPath),
    file_sha256: `runtime-sha-${runId}`,
    content_fingerprint: versionFields.content_fingerprint,
    expected_current_version_id: oracle.versionId,
    created_version_id: cross.newVersionId,
    existing_version_id: null,
    cancelled_version_id: null,
    counts: oracle.currentVersionDetail.counts,
    diff_counts: draftVersion.diff_counts,
    issues: [],
    created_at: now(),
    created_by: "runtime-gate",
    completed_at: now(),
    failure_message: null,
  };

  function controlledVersionPage() {
    const oldItems = oracle.versionPage.items
      .filter((item) => item.version_id !== cross.newVersionId)
      .map((item) => item.version_id === oracle.versionId
        ? { ...item, status: cross.confirmed ? "superseded" : "confirmed" }
        : item);
    const nextVersion = cross.confirmed ? confirmedVersion : draftVersion;
    return {
      page: oracle.versionPage.page,
      page_size: oracle.versionPage.page_size,
      total: oldItems.length + 1,
      items: [nextVersion, ...oldItems],
    };
  }

  async function continuePaused(params) {
    if (!paused.has(params.requestId)) return;
    await cdp.send("Fetch.continueRequest", { requestId: params.requestId }, page.sessionId);
    paused.delete(params.requestId);
  }

  async function fulfillPaused(params, payload) {
    if (!paused.has(params.requestId)) return;
    await fulfillJson(page, params.requestId, payload);
    paused.delete(params.requestId);
  }

  const removeListener = cdp.on("Fetch.requestPaused", async (params) => {
    paused.set(params.requestId, params);
    const requestUrl = new URL(params.request.url);
    if (params.request.method === "POST" && requestUrl.pathname === "/api/generate-schedule-input") {
      generateRequests.push(params);
      progress.generateRequestCount = generateRequests.length;
      progress.lastRequestUrl = params.request.url;
      return;
    }

    const detail = projectMasterDetailFromUrl(params.request.url);
    if (detail) {
      detailRequests.push({ ...detail, url: params.request.url, requestId: params.requestId, phase });
      progress.detailRequestCount = detailRequests.length;
      progress.lastRequestUrl = params.request.url;
      if (phase === "identity-a" && expectedA.workpointIds.includes(detail.workpointId)) return;
      if (phase === "identity-b" && expectedB.workpointIds.includes(detail.workpointId)) {
        await continuePaused(params);
        return;
      }
      if (phase === "cross-version-old" && expectedC.workpointIds.includes(detail.workpointId)) return;
      if (phase === "cross-version-current" && detail.versionId === cross.newVersionId && expectedB.workpointIds.includes(detail.workpointId)) {
        await fulfillPaused(params, workpointById.get(detail.workpointId));
        return;
      }
    }

    const projectVersionsPath = `/api/projects/${encodeURIComponent(oracle.currentVersionDetail.project_id)}/project-master/versions`;
    const importPath = `/api/projects/${encodeURIComponent(oracle.currentVersionDetail.project_id)}/project-master/imports`;
    const newVersionPath = `/api/project-master/versions/${encodeURIComponent(cross.newVersionId)}`;
    if (params.request.method === "POST" && requestUrl.pathname === importPath) {
      cross.imported = true;
      cross.importRequests.push(params.request.url);
      await fulfillPaused(params, importBatch);
      return;
    }
    if (params.request.method === "GET" && requestUrl.pathname === newVersionPath) {
      await fulfillPaused(params, draftVersion);
      return;
    }
    if (params.request.method === "POST" && requestUrl.pathname === `${newVersionPath}/confirm`) {
      cross.confirmed = true;
      cross.confirmRequests.push(params.request.url);
      await fulfillPaused(params, confirmedVersion);
      return;
    }
    if (params.request.method === "GET" && requestUrl.pathname === projectVersionsPath && cross.imported) {
      await fulfillPaused(params, controlledVersionPage());
      return;
    }
    if (params.request.method === "GET" && requestUrl.pathname === `${newVersionPath}/workpoints`) {
      await fulfillPaused(params, {
        page: 1,
        page_size: oracle.workpoints.length,
        total: oracle.workpoints.length,
        items: oracle.workpoints,
      });
      return;
    }
    await continuePaused(params);
  }, page.sessionId);

  await cdp.send("Fetch.enable", {
    patterns: [
      { urlPattern: "*/api/generate-schedule-input", requestStage: "Request" },
      { urlPattern: "*/api/projects/*/project-master/imports", requestStage: "Request" },
      { urlPattern: "*/api/projects/*/project-master/versions*", requestStage: "Request" },
      { urlPattern: "*/api/project-master/versions/*", requestStage: "Request" },
    ],
  }, page.sessionId);

  try {
    await evaluate(page, "window.__taskViewRuntime.reset(); window.__taskViewRuntime.capture()");
    const clicks = await evaluate(page, `(() => {
      const button = document.querySelector('.task-view-title-actions button.secondary');
      if (!button || button.disabled) return null;
      let captured = 0;
      button.addEventListener('click', () => { captured += 1; }, { capture: true });
      button.click();
      button.click();
      window.__taskViewRuntimeClickCount = () => captured;
      return { firstDisabled: button.disabled, connected: button.isConnected };
    })()`);
    assert.ok(clicks?.connected, "the actual production refresh button must receive the clicks");
    markStage("two-generate-requests");
    await waitUntil(() => generateRequests.length === 2, "two real generate requests from the synchronous clicks");
    assert.equal(await evaluate(page, "window.__taskViewRuntimeClickCount()"), 2, "both synchronous clicks must reach the production button");

    const postedVersions = generateRequests.map((request) => JSON.parse(request.request.postData).project_data_version_id);
    assert.deepEqual(postedVersions, [oracle.versionId, oracle.versionId], "both real POST bodies must carry the current version");

    phase = "identity-a";
    await fulfillPaused(generateRequests[0], variantA);
    markStage("identity-a-details");
    await waitUntil(
      () => detailRequests.filter((request) => request.phase === "identity-a").length === expectedA.workpointIds.length,
      "identity A project-master detail requests",
    );
    const requestsA = detailRequests.filter((request) => request.phase === "identity-a");
    assert.deepEqual(requestsA.map((request) => request.workpointId).sort(), expectedA.workpointIds, "identity A URLs are the independent workpoint oracle");
    await continuePaused(paused.get(requestsA[0].requestId));
    await sleep(250);
    assert.equal(
      await evaluate(page, "document.querySelectorAll('.task-view-table tbody tr').length"),
      0,
      "one completed A detail must never expose partial task rows",
    );

    phase = "identity-b";
    await fulfillPaused(generateRequests[1], variantB);
    markStage("identity-b-details");
    await waitUntil(
      () => detailRequests.filter((request) => request.phase === "identity-b").length === expectedB.workpointIds.length,
      "identity B project-master detail requests",
    );
    const requestsB = detailRequests.filter((request) => request.phase === "identity-b");
    assert.deepEqual(requestsB.map((request) => request.workpointId).sort(), expectedB.workpointIds, "identity B URLs are the independent workpoint oracle");
    markStage("identity-b-ready-dom");
    await waitForPage(
      page,
      `document.querySelectorAll('.task-view-table tbody tr').length === ${expectedB.taskCount}`,
      "identity B authoritative production DOM",
    );

    const heldA = requestsA.slice(1).map((request) => paused.get(request.requestId)).filter(Boolean);
    for (const request of heldA) await continuePaused(request);
    await sleep(750);
    await evaluate(page, "window.__taskViewRuntime.capture()");

    const rows = await currentTaskRows(page);
    const records = await evaluate(page, "window.__taskViewRuntime.records");
    assertRowsMatchVariant(rows, expectedB);
    const loadingIndex = records.findIndex((record) => record.state === "loading");
    assert.ok(loadingIndex >= 0, "the production loading gate must be visible between identities");
    const switchRecords = records.slice(loadingIndex);
    const readyRecords = switchRecords.filter((record) => record.state === "ready");
    const validReadyRecords = readyRecords.filter((record) => (
      record.rowCount === expectedB.taskCount
      && JSON.stringify([...record.taskNames].sort()) === JSON.stringify(expectedB.uniqueTaskNames)
      && record.bridgeSectionCells.every((value) => expectedB.workpointNames.some((name) => value.startsWith(`${name} / `)))
    ));
    assert.equal(validReadyRecords.length, readyRecords.length, "every ready mutation must match identity B");
    assert.equal(taskNameCommitCount(switchRecords), 1, "only identity B may commit task names after the identity switch begins");
    const zeroHits = assertZeroHits(records);
    const urlVersionConsistency = detailRequests.every((request) => request.versionId === oracle.versionId);
    assert.equal(urlVersionConsistency, true, "every workpoint URL must match the controlled source-summary version");

    const crossVersionGenerated = generatedVariant(oracle.generated, cross.newVersionId, expectedB.workpointIds);
    const crossVersionExpected = variantOracle(crossVersionGenerated, oracle.workpoints);
    await evaluate(page, "window.__taskViewRuntime.reset(); window.__taskViewRuntime.capture()");
    phase = "cross-version-old";
    const oldRefreshClicked = await evaluate(page, `(() => {
      const button = document.querySelector('.task-view-title-actions button.secondary');
      if (!button || button.disabled) return false;
      button.click();
      return true;
    })()`);
    assert.equal(oldRefreshClicked, true, "the old-version request must start from the production refresh button");
    markStage("cross-old-generate-request");
    await waitUntil(() => generateRequests.length === 3, "old-version generate request before unmount");
    const oldVersionPost = JSON.parse(generateRequests[2].request.postData).project_data_version_id;
    assert.equal(oldVersionPost, oracle.versionId, "the in-flight old request must originate from the old scenario version");
    await fulfillPaused(generateRequests[2], variantC);
    markStage("cross-old-loading-dom");
    await waitForPage(
      page,
      "Boolean(document.querySelector('.task-view-empty[role=\"status\"]')) && document.querySelectorAll('.task-view-table tbody tr').length === 0",
      "cross-version old identity loading gate",
      30_000,
    );
    markStage("cross-old-detail-requests");
    await waitUntil(
      () => detailRequests.filter((request) => request.phase === "cross-version-old").length === expectedC.workpointIds.length,
      "old-version workpoint requests before production unmount",
      30_000,
    );
    const oldVersionDetails = detailRequests.filter((request) => request.phase === "cross-version-old");
    assert.deepEqual(oldVersionDetails.map((request) => request.workpointId).sort(), expectedC.workpointIds);
    assert.equal(await evaluate(page, "document.querySelectorAll('.task-view-table tbody tr').length"), 0);

    phase = "project-master-confirmation";
    const projectMasterOpened = await evaluate(page, `(() => {
      const button = Array.from(document.querySelectorAll('.side-nav-item'))
        .find((item) => item.querySelector('svg.lucide-database'));
      if (!button) return false;
      button.click();
      return true;
    })()`);
    assert.equal(projectMasterOpened, true, "the real project-master navigation item must be clicked");
    markStage("project-master-workspace");
    await waitForPage(page, "Boolean(document.querySelector('.project-master-workspace'))", "production project-master workspace");
    const taskTabUnmounted = await evaluate(page, "!document.querySelector('.task-view-title-actions') && !document.querySelector('.task-view-table')");
    assert.equal(taskTabUnmounted, true, "TaskViewTab must unmount on the production project-master route");

    await cdp.send("DOM.enable", {}, page.sessionId);
    const { root } = await cdp.send("DOM.getDocument", { depth: -1, pierce: true }, page.sessionId);
    const { nodeId: fileInputNodeId } = await cdp.send("DOM.querySelector", {
      nodeId: root.nodeId,
      selector: '.project-master-actions input[type="file"]',
    }, page.sessionId);
    assert.ok(fileInputNodeId, "the production project-master file input must exist");
    await cdp.send("DOM.setFileInputFiles", { nodeId: fileInputNodeId, files: [workbookPath] }, page.sessionId);
    markStage("project-master-import-request");
    await waitUntil(() => cross.importRequests.length === 1, "real project-master import request");
    markStage("project-master-confirm-button");
    await waitForPage(
      page,
      "Boolean(document.querySelector('.project-master-import-preview button.primary:not(:disabled)'))",
      "enabled production version-confirm button",
    );
    const confirmedThroughUi = await evaluate(page, `(() => {
      const button = document.querySelector('.project-master-import-preview button.primary:not(:disabled)');
      if (!button) return false;
      button.click();
      return true;
    })()`);
    assert.equal(confirmedThroughUi, true, "the real version-confirm button must be clicked");
    markStage("project-master-confirm-request");
    await waitUntil(() => cross.confirmRequests.length === 1 && cross.confirmed, "real project-master confirmation request");

    phase = "cross-version-current";
    const taskTabOpened = await evaluate(page, `(() => {
      const button = Array.from(document.querySelectorAll('.side-nav-item'))
        .find((item) => item.querySelector('svg.lucide-clipboard-list'));
      if (!button) return false;
      button.click();
      return true;
    })()`);
    assert.equal(taskTabOpened, true, "the real task-view navigation item must be clicked after confirmation");
    markStage("cross-current-generate-request");
    await waitUntil(() => generateRequests.length === 4, "current-version generate request after production remount");
    const currentVersionPost = JSON.parse(generateRequests[3].request.postData).project_data_version_id;
    assert.equal(currentVersionPost, cross.newVersionId, "the remounted production task view must generate from the confirmed version");
    await fulfillPaused(generateRequests[3], crossVersionGenerated);
    markStage("cross-current-detail-requests");
    await waitUntil(
      () => detailRequests.filter((request) => request.phase === "cross-version-current").length === crossVersionExpected.workpointIds.length,
      "current-version workpoint requests after production remount",
    );
    const currentVersionDetails = detailRequests.filter((request) => request.phase === "cross-version-current");
    assert.deepEqual(currentVersionDetails.map((request) => request.workpointId).sort(), crossVersionExpected.workpointIds);
    assert.equal(currentVersionDetails.every((request) => request.versionId === cross.newVersionId), true);
    markStage("cross-current-ready-dom");
    await waitForPage(
      page,
      `document.querySelectorAll('.task-view-table tbody tr').length === ${crossVersionExpected.taskCount}`,
      "current-version authoritative DOM after production remount",
    );

    for (const request of oldVersionDetails.map((item) => paused.get(item.requestId)).filter(Boolean)) {
      await continuePaused(request);
    }
    await sleep(750);
    await evaluate(page, "window.__taskViewRuntime.capture()");
    const crossRows = await currentTaskRows(page);
    const crossRecords = await evaluate(page, "window.__taskViewRuntime.records");
    assertRowsMatchVariant(crossRows, crossVersionExpected);
    const crossLoadingIndex = crossRecords.findIndex((record) => record.state === "loading");
    assert.ok(crossLoadingIndex >= 0);
    const crossSwitchRecords = crossRecords.slice(crossLoadingIndex);
    const crossReadyRecords = crossSwitchRecords.filter((record) => record.state === "ready");
    const validCrossReadyRecords = crossReadyRecords.filter((record) => (
      record.rowCount === crossVersionExpected.taskCount
      && JSON.stringify([...record.taskNames].sort()) === JSON.stringify(crossVersionExpected.uniqueTaskNames)
      && record.bridgeSectionCells.every((value) => crossVersionExpected.workpointNames.some((name) => value.startsWith(`${name} / `)))
    ));
    assert.equal(validCrossReadyRecords.length, crossReadyRecords.length, "late old-version responses must not mutate the remounted current DOM");
    assert.equal(taskNameCommitCount(crossSwitchRecords), 1, "the remounted task view must commit only the current version");
    const crossZeroHits = assertZeroHits(crossRecords);
    const crossVersionSummary = {
      productionPath: "ProjectMasterDataWorkspace confirm -> App scenario version -> TaskViewTab unmount/remount",
      workbookFixture: workbookPath,
      importRequestUrl: cross.importRequests[0],
      confirmRequestUrl: cross.confirmRequests[0],
      taskTabUnmounted,
      generatePosts: [oldVersionPost, currentVersionPost],
      controlledResponses: {
        old: { sourceVersion: expectedC.versionId, workpointIds: expectedC.workpointIds },
        current: { sourceVersion: crossVersionExpected.versionId, workpointIds: crossVersionExpected.workpointIds },
      },
      oldDetailUrls: oldVersionDetails.map((request) => request.url),
      currentDetailUrls: currentVersionDetails.map((request) => request.url),
      partialMappingCommits: crossSwitchRecords.filter((record) => record.rowCount > 0 && record.rowCount !== crossVersionExpected.taskCount).length,
      lateIdentityOverwrites: crossReadyRecords.length - validCrossReadyRecords.length,
      readyIdentityConsistency: crossReadyRecords.length === 0 ? 0 : validCrossReadyRecords.length / crossReadyRecords.length,
      transitions: transitionSummary(crossRecords),
      readyRowCount: crossRows.length,
      zeroHits: crossZeroHits,
    };

    const summary = {
      productionPath: "Workspace.generateOnly -> generated -> TaskViewTab identity/effect/maps/rows",
      pageIsolation: "fresh production target after T037",
      capturedClicks: 2,
      generateRequestIds: generateRequests.map((request) => request.networkId ?? request.requestId),
      postedVersions,
      controlledResponses: {
        identityA: { sourceVersion: expectedA.versionId, workpointIds: expectedA.workpointIds, taskCount: expectedA.taskCount },
        identityB: { sourceVersion: expectedB.versionId, workpointIds: expectedB.workpointIds, taskCount: expectedB.taskCount },
      },
      detailRequestUrls: detailRequests.map((request) => request.url),
      baselineReadyRowCount: records[0]?.rowCount ?? 0,
      partialMappingCommits: switchRecords.filter((record) => record.rowCount > 0 && record.rowCount !== expectedB.taskCount).length,
      lateIdentityOverwrites: readyRecords.length - validReadyRecords.length,
      readyIdentityConsistency: readyRecords.length === 0 ? 0 : validReadyRecords.length / readyRecords.length,
      transitions: transitionSummary(records),
      readyRowCount: rows.length,
      zeroHits,
      crossVersion: crossVersionSummary,
    };
    evidence.scenarios.T038 = summary;
    t.diagnostic(JSON.stringify(summary));
  } catch (error) {
    let pageState = null;
    try {
      pageState = await evaluate(page, `(() => {
        const records = window.__taskViewRuntime?.records ?? [];
        return {
          url: location.href,
          rowCount: document.querySelectorAll('.task-view-table tbody tr').length,
          loadingVisible: Boolean(document.querySelector('.task-view-empty[role="status"]')),
          errorVisible: Boolean(document.querySelector('.task-view-empty[role="alert"]')),
          lastMutation: records.at(-1) ?? null,
        };
      })()`);
    } catch (pageError) {
      pageState = { evaluationError: pageError instanceof Error ? pageError.message : String(pageError) };
    }
    Object.assign(progress, {
      status: "failed",
      error: error instanceof Error ? error.message : String(error),
      phase,
      generateRequestCount: generateRequests.length,
      detailRequestCount: detailRequests.length,
      detailRequests: detailRequests.map((request) => ({ phase: request.phase, versionId: request.versionId, workpointId: request.workpointId, url: request.url })),
      pausedRequestUrls: [...paused.values()].map((request) => request.request.url),
      pageState,
    });
    t.diagnostic(JSON.stringify(progress));
    throw error;
  } finally {
    for (const request of paused.values()) {
      try { await cdp.send("Fetch.continueRequest", { requestId: request.requestId }, page.sessionId); }
      catch { /* Fetch.disable below releases anything already invalidated. */ }
    }
    await cdp.send("Fetch.disable", {}, page.sessionId);
    removeListener();
  }
});
