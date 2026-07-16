import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const api = readFileSync(new URL("../src/api/projectMasterApi.ts", import.meta.url), "utf8");
const client = readFileSync(new URL("../src/api/client.ts", import.meta.url), "utf8");

test("project master client covers template import polling versions queries and export", () => {
  for (const path of [
    "/api/project-master/template",
    "/project-master/imports",
    "/project-master/versions/current",
    "/workpoints",
    "/export",
    "/girder-workpoints",
  ]) assert.match(api, new RegExp(path.replaceAll("/", "\\/")));
  assert.match(api, /new FormData\(\)/);
  assert.match(api, /waitForProjectMasterImport/);
  assert.match(api, /apiGetBlob/);
  assert.match(client, /detail\.code/);
});
