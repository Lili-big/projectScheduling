import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const toolDir = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(toolDir, "..", "..");
const netlifyConfig = readFileSync(join(repoRoot, "netlify.toml"), "utf8");
if (/^\s*functions\s*=|\[functions\]/m.test(netlifyConfig)) {
  throw new Error("netlify.toml unexpectedly configures Functions; demo mirror must remain undeployed.");
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
