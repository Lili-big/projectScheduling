import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

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

test("daily progress API sends project-scoped versioned cell changes", async () => {
  const calls=[];
  const fake={project_id:"road",master_version_id:"v",revision:1,rows:[],historical_rows:[],entries:[]};
  const module={exports:{}};
  new Function("require","module","exports",ts.transpileModule(api,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(
    name=>name==="./client"?{apiGet:async(...args)=>{calls.push(["GET",...args]);return fake;},apiPut:async(...args)=>{calls.push(["PUT",...args]);return fake;}}:{},module,module.exports);
  assert.equal(await module.exports.getPavementProgress("road / 1"),fake);
  const body={expected_master_version_id:"v",expected_revision:0,cells:[{component_id:"c",progress_date:"2026-09-01",completed_length_m:null}]};
  assert.equal(await module.exports.savePavementProgress("road / 1",body),fake);
  assert.deepEqual(calls,[["GET","/api/projects/road%20%2F%201/pavement-progress"],["PUT","/api/projects/road%20%2F%201/pavement-progress",body]]);
});
