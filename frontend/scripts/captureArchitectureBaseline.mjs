#!/usr/bin/env node

import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";

const repoRoot = resolve(import.meta.dirname, "../..");
const frontendRoot = join(repoRoot, "frontend");
const defaultOutput = join(frontendRoot, "tests/fixtures/architecture/frontend-baseline.json");

function text(path) {
  return readFileSync(path, "utf8");
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function exportedNames(source) {
  const names = new Set();
  for (const match of source.matchAll(/^export\s+(?:async\s+)?(?:declare\s+)?(?:type|interface|enum|class|const|let|function)\s+([A-Za-z_$][\w$]*)/gm)) {
    names.add(match[1]);
  }
  for (const match of source.matchAll(/^export\s*\{([^}]+)\}/gms)) {
    for (const item of match[1].split(",")) {
      const name = item.trim().split(/\s+as\s+/).at(-1)?.trim();
      if (name) names.add(name);
    }
  }
  return [...names].sort();
}

function resolveTsModule(fromPath, specifier) {
  const base = resolve(dirname(fromPath), specifier);
  for (const candidate of [base, `${base}.ts`, `${base}.tsx`, join(base, "index.ts"), join(base, "index.tsx")]) {
    if (existsSync(candidate) && statSync(candidate).isFile()) return candidate;
  }
  return null;
}

function exportedNamesFromFile(path, seen = new Set()) {
  if (seen.has(path)) return [];
  seen.add(path);
  const value = text(path);
  const names = new Set(exportedNames(value));
  for (const match of value.matchAll(/^export\s+\*\s+from\s+["']([^"']+)["']/gm)) {
    const target = resolveTsModule(path, match[1]);
    if (target) for (const name of exportedNamesFromFile(target, seen)) names.add(name);
  }
  return [...names].sort();
}

function apiFunctionsFromFile(path, seen = new Set()) {
  if (seen.has(path)) return [];
  seen.add(path);
  const value = text(path);
  const names = new Set(apiFunctions(value));
  for (const match of value.matchAll(/^export\s+\*\s+from\s+["']([^"']+)["']/gm)) {
    const target = resolveTsModule(path, match[1]);
    if (target) for (const name of apiFunctionsFromFile(target, seen)) names.add(name);
  }
  return [...names].sort();
}

function apiFunctions(source) {
  return [...source.matchAll(/^export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/gm)]
    .map((match) => match[1])
    .sort();
}

function lineCount(path) {
  return text(path).split(/\r?\n/).length;
}

function directorySize(path) {
  if (!existsSync(path)) return 0;
  return readdirSync(path, { withFileTypes: true }).reduce((total, entry) => {
    const current = join(path, entry.name);
    return total + (entry.isDirectory() ? directorySize(current) : statSync(current).size);
  }, 0);
}

function lockManifest(path) {
  if (!existsSync(path)) return null;
  const raw = text(path);
  const lock = JSON.parse(raw);
  const packages = Object.entries(lock.packages ?? {})
    .filter(([name]) => name)
    .map(([name, value]) => ({ path: name.replaceAll("\\", "/"), version: value.version ?? null }))
    .sort((a, b) => a.path.localeCompare(b.path));
  return { path: relative(repoRoot, path).replaceAll("\\", "/"), sha256: sha256(raw), packages };
}

const schedulerTypesPath = join(frontendRoot, "src/types/scheduler.ts");
const schedulerApiPath = join(frontendRoot, "src/api/schedulerApi.ts");
const appPath = join(frontendRoot, "src/app/App.tsx");
const stylesPath = join(frontendRoot, "src/styles.css");
const typeSource = text(schedulerTypesPath);
const apiSource = text(schedulerApiPath);

const baseline = {
  format_version: 1,
  public_contracts: {
    scheduler_type_exports: exportedNamesFromFile(schedulerTypesPath),
    scheduler_api_functions: apiFunctionsFromFile(schedulerApiPath),
    scheduler_api_function_count: apiFunctionsFromFile(schedulerApiPath).length,
    root_app_default_export: /export\s+default\s+App\s*;?|export\s*\{\s*default\s*\}\s*from/.test(text(join(frontendRoot, "src/App.tsx"))),
  },
  module_lines: {
    "frontend/src/app/App.tsx": lineCount(appPath),
    "frontend/src/types/scheduler.ts": lineCount(schedulerTypesPath),
    "frontend/src/api/schedulerApi.ts": lineCount(schedulerApiPath),
    "frontend/src/styles.css": lineCount(stylesPath),
  },
  build: {
    output_path: "frontend/dist",
    total_bytes: directorySize(join(frontendRoot, "dist")),
  },
  npm_locks: [
    lockManifest(join(repoRoot, "package-lock.json")),
    lockManifest(join(frontendRoot, "package-lock.json")),
    lockManifest(join(repoRoot, "tools/ai-ppt-system/package-lock.json")),
  ].filter(Boolean),
};

const args = process.argv.slice(2);
const checkIndex = args.indexOf("--check");
if (checkIndex >= 0) {
  const fixture = resolve(repoRoot, args[checkIndex + 1]);
  const expected = JSON.parse(text(fixture));
  const comparable = ({ public_contracts, npm_locks }) => ({ public_contracts, npm_locks });
  if (JSON.stringify(comparable(baseline)) !== JSON.stringify(comparable(expected))) {
    console.error(`architecture baseline mismatch: ${relative(repoRoot, fixture)}`);
    process.exit(1);
  }
  console.log(`architecture baseline matches ${relative(repoRoot, fixture)}`);
  process.exit(0);
}

const outputIndex = args.indexOf("--output");
const output = outputIndex >= 0 ? resolve(repoRoot, args[outputIndex + 1]) : defaultOutput;
mkdirSync(dirname(output), { recursive: true });
writeFileSync(output, `${JSON.stringify(baseline, null, 2)}\n`, "utf8");
console.log(`wrote ${relative(repoRoot, output)} (${baseline.public_contracts.scheduler_api_function_count} API functions)`);
