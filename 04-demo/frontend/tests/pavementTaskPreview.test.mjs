import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
const load = async path => import(`data:text/javascript;base64,${Buffer.from(ts.transpileModule(readFileSync(new URL(path, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText).toString("base64")}`);
const pavement = await load("../src/domain/pavement.ts");
const workflow = await load("../src/app/workflows/scenarioWorkflow.ts");
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };

test("preview latest input wins, caches ALL scope, cancels on leave and retries explicitly", async () => {
  const pending = [];
  const controller = workflow.createPavementPreviewController((scenario, scope) => {
    assert.equal(scope, null); const d=deferred(); pending.push(d); return d.promise;
  });
  const updates=[]; const emit=s=>updates.push(s);
  const a={project_data_version_id:"a"}, b={project_data_version_id:"b"};
  const pa=controller.request(a,emit), pb=controller.request(b,emit);
  pending[1].resolve({tag:"b"}); await pb;
  pending[0].resolve({tag:"a"}); await pa;
  assert.equal(updates.at(-1).generation.tag,"b");
  await controller.request(b,emit); assert.equal(pending.length,2);
  const fail=controller.request(a,emit); pending[2].reject(new Error("offline")); await fail;
  assert.equal(updates.at(-1).status,"error");
  await controller.request(a,emit); assert.equal(pending.length,3);
  const retry=controller.request(a,emit,true); pending[3].resolve({tag:"retry"}); await retry;
  const leave=controller.request(b,emit,true); controller.invalidate(); const n=updates.length;
  pending[4].resolve({tag:"leave"}); await leave; assert.equal(updates.length,n);
});

function fixture() {
  const components=[1,2,3].map(i=>({id:`A-${i}`,name:`层${i}`,component_type:"cement_stabilized_base",enabled:true,quantity:1790,properties:{unit:"m",layer_order:i}}));
  const scenario={task_overrides:{},process_library:[{id:"p",component_type:"cement_stabilized_base",is_default:true,productivity_options:[{id:"o",is_default:true,name:"方案"}]}],pavement_settings:{...pavement.emptyPavementSettings(),layer_conditions:[{component_id:"A-1",wait_days:7}]},project:{bridges:[{id:"w",work_sections:[{id:"A",name:"段A",structures:[{id:"A",components}]}]}]}};
  const tasks=components.map(c=>({id:`pavement:${c.id}`,component_id:c.id,structure_id:"A",name:c.name,quantity:1790,quantity_label:"1790m",duration_days:3,productivity_rule_id:"o",properties:{unit:"m",productivity_value:800,productivity_unit:"m/天"},pavement_context:{task_kind:"construction",process_id:"p"}}));
  const generated={schedule_input:{tasks,precedence_links:[{predecessor_id:tasks[0].id,successor_id:tasks[1].id,relationship:"FS",lag_days:7,source_rule_id:"pavement_layer_condition"},{predecessor_id:tasks[1].id,successor_id:tasks[2].id,relationship:"FS",lag_days:0,source_rule_id:"pavement_layer_condition"}]},validation:[]};
  return {scenario,generated};
}

test("handover scope removes blocked rows without changing layer or productivity configuration", () => {
  const {scenario, generated} = fixture();
  const before = JSON.stringify(scenario);
  generated.schedule_input.pavement_handover_scope = {total_section_count:1,included_section_count:0,included_layer_count:0,blocked_sections:[{structure_id:"A",section_name:"段A",reason:"征地未解决",component_ids:["A-1","A-2","A-3"]}]};
  generated.schedule_input.tasks=[];
  assert.deepEqual(pavement.pavementTaskGroups(scenario, generated), []);
  assert.equal(JSON.stringify(scenario), before);
  delete generated.schedule_input.pavement_handover_scope;
  assert.equal(pavement.pavementTaskGroups(scenario, generated)[0].rows.length, 3);
});

for (const policy of ["strict_last", "per_fleet_last"]) test(`pending ${policy} keeps decomposition and accurate rule`, () => {
  const {scenario, generated} = fixture();
  generated.schedule_input.pavement_handover_scope = {total_section_count:1,included_section_count:1,included_layer_count:3,blocked_sections:[],pending_policy:policy,pending_sections:[{structure_id:"A",section_name:"段A",reason:"征地未解决",component_ids:["A-1","A-2","A-3"]}]};
  const before = JSON.stringify(scenario);
  const group = pavement.pavementTaskGroups(scenario, generated)[0];
  assert.equal(group.rows.length, 3);
  assert.equal(group.pendingHandover.reason, "征地未解决");
  assert.equal(group.rows[1].relations[0].lag_days, 7);
  assert.equal(JSON.stringify(scenario), before);
  const require=createRequire(import.meta.url), module={exports:{}};
  const compiled=ts.transpileModule(readFileSync(new URL("../src/features/taskView/TaskViewWorkspace.tsx",import.meta.url),"utf8"),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  new Function("require","module","exports",compiled)(name=>name==="../../domain/pavement"?pavement:require(name),module,module.exports);
  const html=renderToStaticMarkup(createElement(module.exports.PavementTaskView,{scenario,generated,status:"ready"}));
  assert.match(html,/其中 1 段待移交，附条件排程/);
  assert.match(html,policy==="per_fleet_last"?/各机组完成自身正常段任务后/:/历史任务按其他施工段全部工序完成后/);
});
test("projection uses generated values, preserves unknown edges and missing layers", () => {
  const {scenario,generated}=fixture();
  let rows=pavement.pavementTaskGroups(scenario,generated)[0].rows;
  assert.equal(rows.length,3); assert.equal(rows[0].task.duration_days,3);
  assert.equal(rows[1].relations[0].lag_days,7);
  assert.equal(rows[2].relations[0].lag_days,null);
  generated.schedule_input.tasks.splice(1,1);
  generated.schedule_input.precedence_links=[{predecessor_id:"pavement:A-1",successor_id:"pavement:A-3",relationship:"FS",lag_days:7,source_rule_id:"pavement_layer_condition"}];
  rows=pavement.pavementTaskGroups(scenario,generated)[0].rows;
  assert.equal(rows.length,3); assert.equal(rows[1].task,null);
  assert.equal(rows[2].relations[0].predecessor_name,"层2");
  assert.equal(rows[2].relations[0].status,"pending");
});
test("projection keeps chosen method and invalid selection instead of defaulting silently", () => {
  const {scenario,generated}=fixture();
  scenario.process_library.push({id:"second",method_id:"custom",component_type:"cement_stabilized_base",productivity_options:[{id:"fast",name:"快"}]});
  scenario.task_overrides["A-1"]={method_id:"custom",productivity_option_id:"gone"};
  generated.schedule_input.tasks.shift();
  const row=pavement.pavementTaskGroups(scenario,generated)[0].rows[0];
  assert.equal(row.process.id,"second"); assert.equal(row.selectedOptionId,"gone");
});

test("positive preparation and fixed links stay visible; zero-day steps stay conditions", () => {
  const {scenario,generated}=fixture();
  scenario.pavement_settings.ancillary_steps=[{id:"zero",kind:"seal",before_component_id:"A-2",name:"零天封层",order:0,duration_days:0,wait_after_days:1},{id:"prep",kind:"seal",before_component_id:"A-2",name:"封层",order:1,duration_days:2,wait_after_days:0}];
  generated.schedule_input.tasks.push({id:"pavement-prep:prep",component_id:"A-2",name:"封层",duration_days:2,pavement_context:{task_kind:"preparation"}});
  scenario.pavement_settings.fixed_sequences=[{process_type:"cement_stabilized_base",component_ids:["missing","A-1"]}];
  const rows=pavement.pavementTaskGroups(scenario,generated)[0].rows;
  assert.deepEqual(rows.map(r=>r.name),["层1","封层","层2","层3"]);
  assert.equal(rows[1].task.duration_days,2);
  assert.equal(rows[1].relations[0].lag_days,8);
  assert.equal(rows[0].relations[0].status,"invalid");
  generated.validation=[{level:"error",code:"PAVEMENT_LOGIC_CYCLE",message:"cycle"}];
  assert.ok(pavement.pavementTaskGroups(scenario,generated)[0].rows[2].relations.every(r=>r.status==="invalid"));
});
