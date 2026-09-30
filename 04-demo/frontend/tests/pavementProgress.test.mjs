import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import ts from "typescript";
const require = createRequire(import.meta.url);
function load(path, imports={}) {
  const module={exports:{}};
  const js=ts.transpileModule(readFileSync(new URL(path,import.meta.url),"utf8"), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  new Function("require","module","exports",js)(name=>imports[name]??require(name),module,module.exports);
  return module.exports;
}
const pavement=load("../src/domain/pavement.ts");
const p=load("../src/domain/pavementProgress.ts",{"./pavement":pavement});
const row={component_id:"c",structure_id:"s",workpoint_id:"w",section_name:"第一段",component_name:"水稳",side:"left",design_length_m:1790,width_m:null,thickness_m:null,status:"active"};
const view=()=>({project_id:"p",master_version_id:"v",revision:0,rows:[row],historical_rows:[],entries:[]});
const key=(day,cid="c")=>p.progressCellKey(cid,day);
const entries=[{component_id:"c",progress_date:"2026-09-01",completed_length_m:300},{component_id:"c",progress_date:"2026-09-02",completed_length_m:450},{component_id:"c",progress_date:"2026-10-01",completed_length_m:100}];

test("all dates contribute; replacement, clearing, explicit zero and decimal sums",()=>{
  let v={...view(),entries};
  assert.equal(p.progressTotals(v,{})["c"].remaining,940);
  assert.equal(p.progressTotals(v,{[key("2026-09-01")]:"320"})["c"].remaining,920);
  assert.equal(p.progressTotals(v,{[key("2026-09-01")]:"320",[key("2026-09-02")]:""})["c"].remaining,1370);
  assert.deepEqual(p.progressChanges(v,{[key("2026-09-01")]:"300",[key("2026-09-02")]:"",[key("2026-10-02")]:"0"}),[
    {component_id:"c",progress_date:"2026-09-02",completed_length_m:null},{component_id:"c",progress_date:"2026-10-02",completed_length_m:0}]);
  const totals=p.progressTotals(view(),{[key("2026-09-01")]:"0.1",[key("2026-09-02")]:"0.2"});
  assert.equal(totals.c.completed,.3);
});
test("overrun is preserved; invalid values are rejected but blank is neutral",()=>{
  const total=p.progressTotals(view(),{[key("2026-09-01")]:"1800"}).c;
  assert.equal(total.remaining,-10);assert.equal(total.overrun,10);
  for(const s of ["-1","NaN","Infinity","0.0001","1e5","9007199254741"]) assert.ok(p.parseDailyLength(s).error,s);
  assert.equal(p.parseDailyLength("").value,null);
  assert.equal(p.parseDailyLength("0").value,0);
  assert.equal(p.parseDailyLength("1.2000").value,1.2);
  const missing={...view(),rows:[{...row,design_length_m:null}]};
  assert.equal(p.progressTotals(missing,{[key("2026-09-01")]:"42"}).c.remaining,null);
});
test("months handle leap years, local current month and year changes",()=>{
  assert.equal(p.progressMonthDays("2024-02").length,29);
  assert.equal(p.progressMonthDays("2026-02").length,28);
  assert.equal(p.progressMonthDays("2026-09")[0],"2026-09-01");
  assert.equal(p.shiftProgressMonth("2026-12",1),"2027-01");
  assert.deepEqual(p.progressMonthDays("2026-13"),[]);
});
test("reuse task grouping without generated result; disabled and auxiliary rows",()=>{
  const scenario={project:{bridges:[{id:"w",work_sections:[{id:"s",name:"第一段",structures:[{id:"s",components:[
    {id:"c",name:"水稳",enabled:true,component_type:"cement_stabilized_base",quantity:999,properties:{unit:"t",layer_order:1}},
    {id:"off",name:"停用",enabled:false,component_type:"granular_base",properties:{layer_order:2}}
  ]}]}]}]},process_library:[],pavement_settings:{...pavement.emptyPavementSettings(),ancillary_steps:[{id:"x",name:"历史辅助",before_component_id:"c",duration_days:1,order:1}]}};
  const before=JSON.stringify(scenario);
  const groups=p.progressGroups(scenario,view());
  assert.deepEqual(groups.map(g=>g.id),pavement.pavementTaskGroups(scenario,null).map(g=>g.id));
  assert.equal(groups[0].rows.length,2);assert.equal(groups[0].rows[0].master,null);
  assert.equal(groups[0].rows[1].master.design_length_m,1790);
  assert.equal(JSON.stringify(scenario),before);
});
test("conflict review retains drafts until explicitly chosen; invalid IDs cannot be kept",()=>{
  const drafts={[key("2026-09-01")]:"150",[key("2026-09-01","removed")]:"10"};
  const v={...view(),entries:[entries[0]],revision:2};
  const review=p.progressReview(v,drafts);
  assert.equal(review.length,2);assert.equal(review[0].saved,300);assert.equal(review[0].local,"150");
  assert.equal(review[0].editable,true);assert.equal(review[1].editable,false);
  assert.equal(Object.keys(drafts).length,2);
});
test("latest request gate blocks stale and cancelled responses",()=>{
  const gate=p.progressRequestGate();const a=gate.next(),b=gate.next();
  assert.equal(a(),false);assert.equal(b(),true);gate.cancel();assert.equal(b(),false);
});

test("navigation is pavement-only and mirror explicitly rejects both methods",async()=>{
  const {createElement}=require("react"),{renderToStaticMarkup}=require("react-dom/server");
  const navigation=load("../src/features/layout/WorkspaceNavigation.tsx");
  const props={activeTab:"projectFiles",openTabs:[],onOpen:()=>{},collapsed:false,onToggleCollapsed:()=>{}};
  assert.match(renderToStaticMarkup(createElement(navigation.SideNavigation,{...props,engineeringDomain:"pavement"})),/实际进度统计/);
  assert.doesNotMatch(renderToStaticMarkup(createElement(navigation.SideNavigation,{...props,engineeringDomain:"bridge"})),/实际进度统计/);
  const mirror=readFileSync(new URL("../../tools/demo-api-mirror/api.mts",import.meta.url),"utf8");
  const guard=mirror.slice(mirror.indexOf("  const containsPavement ="),mirror.indexOf("  try {",mirror.indexOf("  const containsPavement =")));
  const fn=new Function("req",ts.transpileModule(`return (async()=>{${guard}\nreturn null;})();`,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText);
  for(const method of ["GET","PUT"]){
    const response=await fn(new Request("http://localhost/api/projects/p/pavement-progress",{method}));
    assert.equal(response.status,422);assert.equal((await response.json()).detail.code,"PAVEMENT_FEATURE_NOT_SUPPORTED");
  }
});
test("read failures remain explicit errors rather than empty progress",()=>{
  assert.match(p.progressError(new Error('{"detail":{"code":"PAVEMENT_PROGRESS_STORAGE_ERROR","message":"读取失败"}}')),/读取失败.*PAVEMENT_PROGRESS_STORAGE_ERROR/);
  assert.match(p.progressError(new Error('{"detail":[{"msg":"invalid date"}]}')),/invalid date/);
});
