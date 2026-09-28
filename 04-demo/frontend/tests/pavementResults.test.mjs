import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

const root = resolve(import.meta.dirname, "..");

function toDataUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

function transpile(path) {
  return ts.transpileModule(readFileSync(path, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
    fileName: path,
  }).outputText;
}

async function loadPresenter() {
  const constantsUrl = toDataUrl(transpile(resolve(root, "src/domain/constants.ts")));
  const labelsUrl = toDataUrl(transpile(resolve(root, "src/domain/labels.ts")));
  const resourcesUrl = toDataUrl(
    transpile(resolve(root, "src/domain/resources.ts"))
      .replaceAll('from "./constants"', `from "${constantsUrl}"`),
  );
  const source = transpile(resolve(root, "src/features/scheduleResults/presenter.ts"))
    .replace('from "../../domain/labels"', `from "${labelsUrl}"`)
    .replace('from "../../domain/resources"', `from "${resourcesUrl}"`);
  return import(toDataUrl(source));
}

const { pavementResultPresentation, buildResourceScopeResult } = await loadPresenter();
const hybridMeta = { method:"greedy_cpsat", initial_strategy:"earliest_start", valid_candidate_count:3,
  initial_days:16, final_days:13, improvement_days:3, selected_source:"cp_sat", optimizer_status:"OPTIMAL",
  optimizer_not_run_reason:null, outcome:"improved", initial_plan_seconds:.1, model_build_seconds:.2, cp_sat_seconds:.3, total_seconds:.6 };

test("progress keeps ticking without new solutions and releases its timer on terminal or unmount",()=>{
  const path=resolve(root,"src/features/scheduleResults/PavementSolveProgress.tsx");
  const compiled=ts.transpileModule(readFileSync(path,"utf8"),{fileName:path,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  let clock=1000,state,dependencies,cleanup,tick=null,cleared=0;
  const hooks={
    useState(initial){ if(state===undefined) state=typeof initial==="function"?initial():initial; return [state,value=>{state=value;}]; },
    useEffect(effect,next){ if(!dependencies || next.some((d,i)=>d!==dependencies[i])) {cleanup?.();dependencies=next;cleanup=effect();} },
  };
  const require=createRequire(import.meta.url), module={exports:{}};
  new Function("require","module","exports","performance","window",compiled)(name=>name==="react"?hooks:require(name),module,module.exports,
    {now:()=>clock},{setInterval(fn){tick=fn;return 1;},clearInterval(){tick=null;cleared++;}});
  const render=(status="running",startedAt=1000)=>renderToStaticMarkup(module.exports.PavementSolveProgress({status,hasPlan:true,improvementCount:0,progress:{startedAt,timeBudgetSeconds:15}}));
  assert.match(render(),/已等待 0.0 秒/);
  clock=6000;tick();assert.match(render(),/已等待 5.0 秒/);
  clock=11000;tick();assert.match(render(),/已等待 10.0 秒/);
  assert.match(render(),/已改善 0 次/); // Same plan, a full five seconds of activity.
  assert.equal(render("complete"),"");assert.equal(tick,null);assert.equal(cleared,1);
  render("running",11000);assert.equal(typeof tick,"function");
  assert.equal(render("interrupted",11000),"");assert.equal(tick,null);
  render("running",11000);cleanup?.();assert.equal(tick,null);assert.equal(cleared,3);
});
test("hybrid presentation keeps fallback feasible, source and improvement separate", () => {
  const base={status:"FEASIBLE",pavement_summary:{construction_finish_date:"2026-10-05"}};
  const view=meta=>pavementResultPresentation({...base,pavement_optimization:{...hybridMeta,...meta}});
  assert.match(view({}).optimizationText,/AI 推演排程方案 · 初步 16 天 → 推演后 13 天 · 缩短 3 天/);
  assert.doesNotMatch(view({}).optimizationText,/CP-SAT/);
  const fallback=view({outcome:"initial_retained",optimizer_status:"UNKNOWN",selected_source:"greedy",final_days:16,improvement_days:0});
  assert.equal(fallback.hasPlan,true); assert.match(fallback.status,/可行/);
  assert.match(fallback.optimizationNotice,/限时内未获得更好方案，采用初步计划/);
  assert.match(view({outcome:"initial_retained",optimizer_status:null,optimizer_not_run_reason:"budget_exhausted"}).optimizationNotice,/预算/);
  assert.match(view({outcome:"initial_retained",selected_source:"greedy"}).optimizationNotice,/最优/);
  const cold=view({outcome:"cp_sat_only",initial_days:null,initial_strategy:null,improvement_days:null});
  assert.doesNotMatch(cold.optimizationText,/初步 0|缩短 0/);
  assert.match(cold.optimizationText,/推演后 13 天/);
  assert.equal(pavementResultPresentation(base).optimizationText,null);
  const failed=pavementResultPresentation({...base,status:"MODEL_INVALID",pavement_optimization:{...hybridMeta,outcome:"inconsistent",final_days:null}});
  assert.equal(failed.optimizationText,null); assert.equal(failed.constructionFinish,"—");
  assert.match(failed.optimizationNotice,/不一致/);
});

test("live and interrupted plans never claim final or optimal", () => {
  const result={status:"FEASIBLE",pavement_summary:{construction_finish_date:"2026-10-05"},pavement_optimization:hybridMeta};
  const live=pavementResultPresentation(result,"running");
  assert.match(live.optimizationText,/当前最好 13 天/);
  assert.doesNotMatch(live.optimizationText,/最终/);
  assert.match(live.optimizationNotice,/AI 正在推演/);
  assert.match(pavementResultPresentation(result,"interrupted").optimizationNotice,/未完成/);
  assert.match(pavementResultPresentation(result,"complete").optimizationNotice,/尚未证明最优/);
});
test("partial results label the included scope, all pending has its own empty state and historical results stay untouched", () => {
  const scope = {total_section_count:25,included_section_count:21,included_layer_count:84,blocked_sections:[{structure_id:"s",section_name:"段",reason:"征地",component_ids:["c"]}]};
  const current = pavementResultPresentation({status:"FEASIBLE", stats:{pavement_handover:scope}});
  assert.equal(current.handoverScope, scope);
  assert.equal(current.finishLabel, "本次纳入范围施工完成日期");
  assert.equal(pavementResultPresentation({status:"MODEL_INVALID",validation:[{code:"PAVEMENT_NO_SCHEDULABLE_SECTION"}]}).noSchedulableSection, true);
  assert.equal(pavementResultPresentation({status:"OPTIMAL"}).handoverScope, undefined);
});
test("two processes allocated to one shared instance still display one named fleet", () => {
  const pool = {id:"shared",label:"碎石/水稳共享机组",quantity:1,compatible_process_ids:["gravel","water"]};
  const resource = {id:"shared::instance::1",pool_id:"shared",name:"碎石/水稳共享机组1",scope_mode:"PROJECT_SHARED",eligible_workpoint_ids:["road"],compatible_process_ids:pool.compatible_process_ids};
  const generated = {schedule_input:{resources:[resource],tasks:[{id:"g",bridge_id:"road",component_type:"granular_base"},{id:"w",bridge_id:"road",component_type:"cement_stabilized_base"}]}};
  const result = {resource_allocations:[{resource_id:resource.id,task_id:"g"},{resource_id:resource.id,task_id:"w"}],stats:{}};
  const display = buildResourceScopeResult({generated,result,resourcePools:[pool],workpoints:[{workpoint_id:"road",workpoint_name:"路面"}]});
  assert.equal(display.rows.length,1);
  assert.equal(display.rows[0].currentQuantity,1);
  assert.equal(display.rows[0].resourceLabel,pool.label);
});
test("pavement dates keep zero-wait boundary and feasible status distinct", () => {
  const result = {status:"FEASIBLE",pavement_summary:{input_kind:"demo",construction_finish_date:"2026-01-01",ready_date:"2026-01-02",ready_offset:1}};
  const display = pavementResultPresentation(result);
  assert.equal(display.constructionFinish,"2026-01-01");
  assert.equal(display.readyDate,"2026-01-02");
  assert.equal(display.elapsedDays,1);
  assert.match(display.source,/演示/);
  assert.match(display.status,/可行/);
  assert.doesNotMatch(display.status,/^最优$/);
  assert.equal(display.legacy,true);
});

test("construction result uses work finish without misreading readiness boundary", () => {
  const display=pavementResultPresentation({status:"OPTIMAL",objective_breakdown:{objective:"earliest_construction_finish"},pavement_summary:{construction_finish_date:"2026-01-07",construction_finish_offset:7,ready_offset:7,ready_date:"2026-01-08",readiness:[]}});
  assert.equal(display.legacy,false);
  assert.equal(display.constructionFinish,"2026-01-07");
  assert.equal(display.elapsedDays,7);
});

test("date ranges group the current plan across sections and years without adding wait days", () => {
  const task=(id,process,start,finish)=>({id,component_type:process,start_date:start,finish_date:finish,
    pavement_context:{task_kind:"construction",process_type:process}});
  const result={status:"FEASIBLE",plan_start_date:"2026-12-01",pavement_summary:{ready_date:"2027-01-20"},tasks:[
    task("a2","asphalt_course","2027-01-05","2027-01-08"),
    task("w1","cement_stabilized_base","2026-12-25","2026-12-28"),
    task("g1","granular_base","2026-12-20","2026-12-22"),
    task("a1","asphalt_course","2027-01-01","2027-01-02"),
    {...task("w2","cement_stabilized_base","2026-12-28","2027-01-01"),pavement_context:undefined},
    {...task("prep","asphalt_course","2026-12-30","2026-12-31"),pavement_context:{task_kind:"preparation",process_type:"asphalt_course"}},
  ]};
  const before=JSON.stringify(result);
  const ranges=pavementResultPresentation(result).dateRanges;
  assert.deepEqual(ranges.map(({key,startDate,finishDate})=>({key,startDate,finishDate})),[
    {key:"overall",startDate:"2026-12-20",finishDate:"2027-01-08"},
    {key:"lower",startDate:"2026-12-20",finishDate:"2027-01-01"},
    {key:"upper",startDate:"2027-01-01",finishDate:"2027-01-08"},
  ]);
  const improved={...result,tasks:result.tasks.map(t=>t.id==="a2"?{...t,finish_date:"2027-01-06"}:t)};
  assert.equal(pavementResultPresentation(improved,"running").dateRanges[0].finishDate,"2027-01-06");
  assert.equal(JSON.stringify(result),before);
});

test("date ranges leave omitted layers empty and hide stale dates on failed plans", () => {
  const result={status:"OPTIMAL",pavement_summary:{},tasks:[
    {component_type:"granular_base",start_date:"2026-12-20",finish_date:"2026-12-20"},
  ]};
  const upper=pavementResultPresentation(result).dateRanges[2];
  assert.equal(upper.taskCount,0); assert.equal(upper.startDate,null); assert.equal(upper.finishDate,null);
  assert.equal(pavementResultPresentation({...result,tasks:[]}).dateRanges[0].startDate,null);
  for (const status of ["UNKNOWN","INFEASIBLE","MODEL_INVALID"]) {
    assert.deepEqual(pavementResultPresentation({...result,status}).dateRanges,[]);
  }
});

test("pending dates use the result snapshot and disappear on failed or historical results", () => {
  const scope={total_section_count:2,included_section_count:2,included_layer_count:2,blocked_sections:[],pending_policy:"strict_last",pending_sections:[{structure_id:"B",section_name:"段B",reason:"征地",component_ids:["B-1"]}]};
  const result={status:"FEASIBLE",stats:{pavement_handover:scope},objective_breakdown:{objective:"earliest_construction_finish"},pavement_summary:{construction_finish_date:"2026-09-27",pending_section_dates:[{structure_id:"B",required_handover_date:"2026-09-26",estimated_finish_date:"2026-09-27"}]}};
  const current=pavementResultPresentation(result);
  assert.equal(current.pendingSections[0].required_handover_date,"2026-09-26");
  assert.equal(current.pendingSections[0].estimated_finish_date,"2026-09-27");
  assert.equal(current.pendingSections[0].reason,"征地");
  assert.match(current.finishLabel,/含待移交假设/);
  const fleet=pavementResultPresentation({...result,stats:{pavement_handover:{...scope,pending_policy:"per_fleet_last"}}});
  assert.deepEqual(fleet.pendingSections,current.pendingSections);
  assert.match(fleet.handoverNotice,/各机组完成自身正常段任务后/);
  assert.match(current.handoverNotice,/历史方案.*正常段全部完成后/);
  for(const status of ["UNKNOWN","INFEASIBLE","MODEL_INVALID"]) {
    const failed=pavementResultPresentation({...result,status});
    assert.equal(failed.hasPlan,false);
    assert.equal(failed.pendingSections[0].required_handover_date,null);
    assert.equal(failed.pendingSections[0].estimated_finish_date,null);
    assert.equal(failed.constructionFinish,"—");
  }
  assert.deepEqual(pavementResultPresentation({...result,stats:{}}).pendingSections,[]);
});

test("result table renders conditional dates and never leaks them into failed results", () => {
  const path=resolve(root,"src/features/scheduleResults/ScheduleResultsWorkspace.tsx");
  const require=createRequire(import.meta.url);
  function loadComponent(path) {
    const compiled=ts.transpileModule(readFileSync(path,"utf8"),{fileName:path,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
    const module={exports:{}};
    new Function("require","module","exports",compiled)(name=>name==="./presenter" ? {pavementResultPresentation} : name.startsWith("./") ? loadComponent(resolve(root,"src/features/scheduleResults",name+(name==="./pavementViewModel" ? ".ts" : ".tsx"))) : require(name),module,module.exports);
    return module.exports;
  }
  const module={exports:loadComponent(path)};
  const result={status:"FEASIBLE",tasks:[],plan_start_date:"2026-09-23",objective_breakdown:{objective:"earliest_construction_finish"},stats:{pavement_handover:{total_section_count:2,included_section_count:2,included_layer_count:2,blocked_sections:[],pending_policy:"strict_last",pending_sections:[{structure_id:"B",section_name:"段B",reason:"征地",component_ids:["B-1"]}]}},pavement_summary:{construction_finish_date:"2026-09-27",construction_finish_offset:5,resource_assumptions:[],wait_intervals:[],transfers:[],pending_section_dates:[{structure_id:"B",required_handover_date:"2026-09-26",estimated_finish_date:"2026-09-27"}]}};
  const before=JSON.stringify(result);
  const render=value=>renderToStaticMarkup(createElement(module.exports.PavementScheduleResults,{result:value}));
  const html=render(result);
  assert.match(html,/aria-label="排程起止日期"/);
  assert.match(html,/整体排程/); assert.match(html,/下面层（碎石＋水稳）/); assert.match(html,/上面层（沥青）/);
  assert.match(html,/暂无排程日期/); assert.match(html,/未纳入本次排程/);
  assert.match(html,/本方案最晚需移交日/); assert.match(html,/预计施工完成日期/);
  assert.match(html,/<td>2026-09-26<\/td><td>2026-09-27<\/td>/);
  assert.match(html,/实际移交仍待确认/);
  assert.match(html,/历史方案按正常段全部完成后/);
  const fleetHtml=render({...result,stats:{pavement_handover:{...result.stats.pavement_handover,pending_policy:"per_fleet_last"}}});
  assert.match(fleetHtml,/各机组完成自身正常段任务后，再施工待移交段/);
  assert.doesNotMatch(fleetHtml,/正常段全部完成后/);
  assert.match(fleetHtml,/<td>2026-09-26<\/td><td>2026-09-27<\/td>/);
  assert.match(html,/纳入 2 段/);
  const failed=render({...result,status:"UNKNOWN"});
  assert.match(failed,/征地/); assert.match(failed,/尚未计算/);
  assert.doesNotMatch(failed,/2026-09-26|2026-09-27/);
  assert.doesNotMatch(failed,/aria-label="排程起止日期"/);
  assert.equal(JSON.stringify(result),before);
  const hybridHtml=render({...result,pavement_optimization:hybridMeta});
  assert.match(hybridHtml,/AI 推演排程方案 · 初步 16 天 → 推演后 13 天 · 缩短 3 天/);
  assert.match(hybridHtml,/计算耗时/); assert.match(hybridHtml,/2026-09-26/);
  const fallbackHtml=render({...result,pavement_optimization:{...hybridMeta,outcome:"initial_retained",optimizer_status:"UNKNOWN",selected_source:"greedy",final_days:16,improvement_days:0}});
  assert.match(fallbackHtml,/限时内未获得更好方案，采用初步计划/);
  assert.doesNotMatch(fallbackHtml,/未获得可展示的可行计划/);
  const tasks=[0,1].map(i=>({id:`t${i}`,structure_id:`s${i}`,structure_name:`段${i}`,bridge_id:"road",sequence_order:1,
    component_id:`c${i}`,process_name:"碎石",name:`段${i} · 碎石`,component_type:"granular_base",duration_days:2,
    start_offset:i*3,end_offset:i*3+2,start_date:"2026-01-01",finish_date:"2026-01-02",assigned_resource_id:"crew",assigned_resource_name:"共享机组",
    properties:{start_chainage:i?"AK0+000":"K1+000",end_chainage:i?"K2+000":"K2+000"},pavement_context:{position_id:`s${i}:left`,source_component_id:`c${i}`}}));
  const generated={schedule_input:{tasks,resources:[],precedence_links:[{id:"l",predecessor_id:"t0",successor_id:"t1",relationship:"FS",lag_days:1}]}};
  const diagram=renderToStaticMarkup(createElement(module.exports.PavementScheduleResults,{result:{...result,tasks},generated}));
  assert.match(diagram,/<dt>开始日期<\/dt><dd><time dateTime="2026-01-01">2026-01-01<\/time>/);
  assert.match(diagram,/<dt>完成日期<\/dt><dd><time dateTime="2026-01-02">2026-01-02<\/time>/);
  assert.equal((diagram.match(/aria-level="1"/g)||[]).length,2);
  assert.equal((diagram.match(/aria-level="2"/g)||[]).length,2);
  assert.equal((diagram.match(/data-task-bar=/g)||[]).length,2);
  assert.match(diagram,/data-link-id="l"/);
  assert.match(diagram,/无法按统一里程定位/);
  assert.match(diagram,/上一步/); assert.match(diagram,/工艺等待（不占主机组）/);
  assert.match(diagram,/机组作业与空闲/); assert.match(diagram,/定位最长空闲/);
  assert.equal((diagram.match(/data-resource-row=/g)||[]).length,1);
  assert.ok(diagram.indexOf('aria-label="施工计划表格与横道图"') < diagram.indexOf('aria-label="机组作业与空闲"'));
  assert.ok(diagram.indexOf('aria-label="机组作业与空闲"') < diagram.indexOf('aria-label="机组里程轴与施工顺序"'));
  assert.doesNotMatch(failed,/data-resource-row=/);
  assert.match(diagram,/双幅施工顺序示意图/); assert.match(diagram,/仅看当前前后箭线/);
  assert.doesNotMatch(diagram,/pv-flow-date|data-flow-task=|时间间距|作业区间表示/);
  assert.match(diagram,/等宽施工段/); assert.match(diagram,/施工顺序图节点间距/);
  assert.equal((diagram.match(/data-flow-side=/g)||[]).length,2);
  assert.match(diagram,/本机组该幅无作业/); assert.match(diagram,/定位机组到访/);
  const flowTasks=[0,1,2,3].map(i=>({...tasks[0],id:`v${i}`,structure_id:`section${i%3}`,structure_name:`段${i%3}`,start_offset:i*3,end_offset:i*3+2,
    pavement_context:{position_id:`section${i%3}:${i===2?"right":"left"}`},properties:{start_chainage:`K${i===3?1:i+1}+000`,end_chainage:`K${i===3?1:i+1}+500`}}));
  const flowHtml=renderToStaticMarkup(createElement(module.exports.PavementScheduleResults,{result:{...result,tasks:flowTasks},generated:{schedule_input:{tasks:flowTasks,resources:[],precedence_links:[]}}}));
  assert.equal((flowHtml.match(/data-flow-edge=/g)||[]).length,3);
  assert.equal((flowHtml.match(/data-flow-kind="cross-side"/g)||[]).length,2);
  assert.equal((flowHtml.match(/data-flow-visit=/g)||[]).length,4);
  assert.equal((flowHtml.match(/data-flow-section=/g)||[]).length,3);
  assert.equal((flowHtml.match(/class="pv-flow-process"/g)||[]).length,4);
  assert.match(flowHtml,/起点/); assert.match(flowHtml,/终点/);
  assert.match(flowHtml,/role="button" tabindex="0" aria-label="流转/);
  assert.equal((flowHtml.match(/marker-mid=/g)||[]).length,3); // Direction stays visible away from dense endpoint labels.
  const denseTasks=Array.from({length:100},(_,i)=>({...flowTasks[i%4],id:`dense${i}`,structure_id:`s${i%4}`,start_offset:i*3,end_offset:i*3+2,assigned_resource_id:i<80?"crew":"crew2",assigned_resource_name:i<80?"机组1":"机组2",pavement_context:{position_id:`s${i%4}:${i%2?"right":"left"}`}}));
  const denseHtml=renderToStaticMarkup(createElement(module.exports.PavementScheduleResults,{result:{...result,tasks:denseTasks},generated:{schedule_input:{tasks:denseTasks,resources:[],precedence_links:[]}}}));
  assert.equal((denseHtml.match(/data-flow-visit=/g)||[]).length,80);
  assert.equal((denseHtml.match(/data-flow-edge=/g)||[]).length,79);
  assert.match(denseHtml,/<option value="crew2">机组2<\/option>/);
  assert.doesNotMatch(failed,/data-flow-visit=/);
  const progressModule=loadComponent(resolve(root,"src/features/scheduleResults/PavementSolveProgress.tsx"));
  assert.match(progressModule.pavementProgressText(true,5,15),/持续优化/);
  assert.match(progressModule.pavementProgressText(true,16,15),/等待计算结果收尾/);
  const progressHtml=status=>renderToStaticMarkup(createElement(progressModule.PavementSolveProgress,{status,hasPlan:true,progress:{startedAt:0,timeBudgetSeconds:15},improvementCount:0}));
  assert.match(progressHtml("running"),/已等待/);
  assert.equal(progressHtml("complete"),""); assert.equal(progressHtml("interrupted"),"");
});


test("idle presentation reports conditional idle optimum and retains the construction finish meaning",()=>{
  const result={status:"OPTIMAL",objective_days:10,pavement_summary:{construction_finish_offset:10,construction_finish_date:"2026-01-10"},
    objective_breakdown:{objective:"min_idle_with_makespan_cap"},pavement_optimization:hybridMeta,
    pavement_idle_optimization:{makespan_cap_days:10,baseline_idle_days:4,final_idle_days:0,improvement_idle_days:4,
      baseline_transfer_days:1,final_transfer_days:2,proved_optimal:true,outcome:"improved"}};
  const done=pavementResultPresentation(result,"complete");
  assert.equal(done.legacy,false);assert.match(done.optimizationText,/窝工 4 → 0 机组·天/);
  assert.match(done.optimizationNotice,/10 天.*窝工已最小/);assert.doesNotMatch(done.optimizationNotice,/工期已证明最优/);
  assert.match(pavementResultPresentation(result,"running").optimizationNotice,/减少.*窝工/);
  assert.match(pavementResultPresentation(result,"interrupted").optimizationNotice,/未完成/);
  result.pavement_idle_optimization.proved_optimal=false;
  assert.match(pavementResultPresentation(result,"complete").optimizationNotice,/尚未证明/);
});
