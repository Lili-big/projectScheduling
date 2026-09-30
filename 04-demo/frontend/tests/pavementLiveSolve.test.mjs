import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = resolve(import.meta.dirname, "..");
const url = text => `data:text/javascript;base64,${Buffer.from(text).toString("base64")}`;
const compile = path => ts.transpileModule(readFileSync(resolve(root,path),"utf8"), {
  compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022},fileName:path,
}).outputText;
const scenarioUrl = url(compile("src/app/workflows/scenarioWorkflow.ts"));
const workflow = await import(url(compile("src/app/workflows/solveWorkflow.ts").replace('from "./scenarioWorkflow"',`from "${scenarioUrl}"`)));
const client = await import(url(compile("src/api/client.ts").replaceAll("import.meta.env", "({})")));
const handover={pending_policy:"per_fleet_last",pending_sections:[{structure_id:"B",reason:"待移交"}]};
const solved = days => ({result:{status:"FEASIBLE",objective_days:days,stats:{pavement_handover:handover}},generated:{schedule_input:{pavement_handover_scope:handover}},diagnostics:[]});
const event = (type, sequence, days=16) => ({type,sequence,elapsed_seconds:sequence,
  ...(type==="started" ? {time_budget_seconds:15} : {solved:solved(days)}),
  ...(type==="solution" ? {solution_kind:sequence===2?"initial":"improvement"} : {})});

test("UTF8, split lines and multiple events remain intact",async()=>{
  const encoded=new TextEncoder().encode('{"中文":"方案"}\n\n{"n":2}\n{"n":3}');
  const values=[];
  const stream=new ReadableStream({start(c){for(const byte of encoded)c.enqueue(Uint8Array.of(byte));c.close();}});
  await client.readNdjsonStream(stream,value=>values.push(value));
  assert.deepEqual(values,[{中文:"方案"},{n:2},{n:3}]);
});

test("initial, improvements, complete publish best and EOF without terminal interrupts",async()=>{
  for(const complete of [true,false]){
    const transport=async(s,scope,publish)=>{
      publish(event("started",1));publish(event("solution",2));publish(event("solution",3,13));
      if(complete)publish(event("complete",4,13));
    };
    const states=[];
    await workflow.createPavementSolveController(transport).request({},null,state=>states.push(state));
    assert.equal(states.at(-1).status,complete?"complete":"interrupted");
    assert.equal(states.at(-1).solved.result.objective_days,13);
    assert.equal(states[0].timeBudgetSeconds,null);
    assert.equal(states[1].timeBudgetSeconds,15);
    assert.equal(states.at(-1).timeBudgetSeconds,15);
    assert.equal(states.find(s=>s.solved?.result.objective_days===16).status,"running");
    for(const state of states.filter(s=>s.solved)) {
      assert.deepEqual(state.solved.result.stats.pavement_handover,handover);
      assert.deepEqual(state.solved.generated.schedule_input.pavement_handover_scope,handover);
    }
  }
});

test("bad order, repeated terminal or worse result is not accepted as completion",async()=>{
  for(const tail of [[event("solution",2,13)],[event("complete",3,17)],
      [event("complete",3),event("complete",4)]]){
    const states=[];
    await workflow.createPavementSolveController(async(s,scope,publish)=>{
      publish(event("started",1));publish(event("solution",2));tail.forEach(publish);
    }).request({},null,state=>states.push(state));
    assert.equal(states.at(-1).status,"interrupted");
    assert.equal(states.at(-1).solved.result.objective_days,16);
  }
});

test("replacement and cancellation abort and suppress old events including finally",async()=>{
  const requests=[];
  const controller=workflow.createPavementSolveController((s,scope,publish,signal)=>new Promise(resolve=>requests.push({publish,signal,resolve})));
  const old=[],next=[];
  const first=controller.request({id:1},null,s=>old.push(s));
  const second=controller.request({id:2},"scope",s=>next.push(s));
  assert.equal(requests[0].signal.aborted,true);
  requests[0].publish(event("started",1)); requests[0].publish(event("solution",2));requests[0].resolve();
  requests[1].publish(event("started",1));requests[1].publish(event("solution",2,13));
  controller.cancel(); requests[1].publish(event("complete",3,13));requests[1].resolve();
  await Promise.all([first,second]);
  assert.equal(old.length,1);
  assert.equal(old[0].timeBudgetSeconds,null);
  assert.equal(next.at(-1).timeBudgetSeconds,15);
  assert.equal(next.at(-1).status,"running");
  assert.equal(requests[1].signal.aborted,true);
});

test("server error preserves received plan, model error cannot hide as successful plan",async()=>{
  for(const tail of [{type:"error",sequence:3,elapsed_seconds:3,code:"FAILED",message:"失败"},
    {type:"complete",sequence:3,elapsed_seconds:3,solved:{...solved(0),result:{status:"MODEL_INVALID"},diagnostics:[{level:"error",message:"不一致"}]}}]){
    const states=[];
    await workflow.createPavementSolveController(async(s,scope,publish)=>{
      publish(event("started",1));publish(event("solution",2));publish(tail);
    }).request({},null,s=>states.push(s));
    assert.equal(states.at(-1).status,"interrupted");
    assert.equal(states.at(-1).solved.result.objective_days,16);
    assert.ok(states.at(-1).error);
  }
});


const idlePlan=(idle,days=10)=>({result:{status:"FEASIBLE",objective_days:days,tasks:[{id:"a",start_offset:0,end_offset:1,assigned_resource_id:"r"}],
  objective_breakdown:{objective:"min_idle_with_makespan_cap"},pavement_summary:{input_fingerprint:"input",construction_finish_offset:days},
  pavement_idle_optimization:{goal:"min_idle_with_makespan_cap",metric:"fleet_internal_idle_v1",baseline_input_fingerprint:"input",
    makespan_cap_days:10,baseline_idle_days:4,final_idle_days:idle,improvement_idle_days:4-idle,
    baseline_transfer_days:1,final_transfer_days:1,proved_optimal:false,outcome:idle<4?"improved":"baseline_retained"}},diagnostics:[]});
const idleEvent=(type,sequence,idle,days=10)=>({...event(type,sequence),solved:idlePlan(idle,days)});
test("idle mode retains baseline and accepts same duration or duration within the original cap",async()=>{
  const baseline=idlePlan(4),states=[];
  const controller=workflow.createPavementSolveController(()=>assert.fail("ordinary solve"),async(s,scope,base,publish)=>{
    assert.equal(base,baseline);publish(event("started",1));publish(idleEvent("solution",2,4));
    publish(idleEvent("solution",3,3,9));publish(idleEvent("solution",4,1,10));publish(idleEvent("complete",5,1));
  });
  await controller.request({},null,s=>states.push(s),baseline);
  assert.equal(states[0].solved,baseline);
  assert.equal(states.at(-1).status,"complete");
  assert.equal(states.at(-1).solved.result.pavement_idle_optimization.final_idle_days,1);
});
test("idle rejects cap breaches, duplicate/worse idle, changing baseline or missing metadata",async()=>{
  for(const mutate of [e=>e.solved.result.objective_days=11,e=>e.solved.result.pavement_idle_optimization.final_idle_days=4,
    e=>e.solved.result.pavement_idle_optimization.makespan_cap_days=11,
    e=>e.solved.result.pavement_idle_optimization.baseline_idle_days=5,
    e=>e.solved.result.pavement_idle_optimization.baseline_input_fingerprint="other",
    e=>delete e.solved.result.pavement_idle_optimization]){
    const states=[];
    await workflow.createPavementSolveController(()=>{},async(s,scope,base,publish)=>{
      publish(event("started",1));publish(idleEvent("solution",2,4));const bad=idleEvent("solution",3,2);mutate(bad);publish(bad);
    }).request({},null,s=>states.push(s),idlePlan(4));
    assert.equal(states.at(-1).status,"interrupted");
    assert.equal(states.at(-1).solved.result.pavement_idle_optimization.final_idle_days,4);
  }
});
test("idle keeps baseline on preflight failure and cancellation suppresses late results",async()=>{
  const baseline=idlePlan(4),states=[];
  await workflow.createPavementSolveController(()=>{},async()=>{throw Error("基准过期");}).request({},null,s=>states.push(s),baseline);
  assert.equal(states.at(-1).solved,baseline);assert.equal(states.at(-1).status,"interrupted");
  let send,finish,signal;
  const controller=workflow.createPavementSolveController(()=>{},(s,scope,base,publish,abort)=>new Promise(resolve=>{send=publish;finish=resolve;signal=abort;}));
  const updates=[],pending=controller.request({},null,s=>updates.push(s),baseline);
  controller.cancel();send(event("started",1));send(idleEvent("solution",2,4));finish();await pending;
  assert.ok(signal.aborted);assert.equal(updates.length,1);assert.equal(updates[0].solved,baseline);
});
test("idle entry needs matching current feasible input and is disabled during any operation",()=>{
  const baseline=idlePlan(4);baseline.generated={schedule_input:{pavement_handover_scope:{pending_policy:"per_fleet_last"}}};
  assert.ok(workflow.canOptimizePavementIdle(baseline,true,false));
  assert.equal(workflow.canOptimizePavementIdle(baseline,false,false),false);
  assert.equal(workflow.canOptimizePavementIdle(baseline,true,true),false);
  assert.equal(workflow.canOptimizePavementIdle(null,true,false),false);
});

test("budget draft accepts finite positive seconds including above 15 and rejects empty or invalid input",()=>{
  for (const value of ["", " ", "0", "-1", "Infinity", "NaN", "bad"]) assert.equal(workflow.parsePavementSolveBudget(value),null);
  for (const value of ["15", "30", "60", "0.5"]) assert.equal(workflow.parsePavementSolveBudget(value),Number(value));
});

test("per-run budgets create request snapshots and retain the idle baseline identity",async()=>{
  const scenario={time_limit_seconds:15,resource_pools:[{quantity:2}]};
  const baseline=idlePlan(4);
  baseline.generated={schedule_input:{time_limit_seconds:30,pavement_handover_scope:handover}};
  const before=JSON.stringify({scenario,baseline});
  for (const budget of [15,30,60]) {
    const normal=[], idle=[];
    const controller=workflow.createPavementSolveController(async(s,scope,publish)=>{
      assert.notEqual(s,scenario);assert.equal(s.time_limit_seconds,budget);
      assert.deepEqual(s.resource_pools,scenario.resource_pools);
      publish({...event("started",1),time_budget_seconds:budget});publish(event("complete",2));
    },async(s,scope,base,publish,signal,seconds)=>{
      assert.equal(base,baseline);assert.equal(s.time_limit_seconds,30);assert.equal(seconds,budget);
      assert.deepEqual(s.resource_pools,scenario.resource_pools);
      publish({...event("started",1),time_budget_seconds:seconds});
      publish(idleEvent("solution",2,4));publish(idleEvent("complete",3,2));
    });
    await controller.request(scenario,null,s=>normal.push(s),undefined,budget);
    await controller.request(scenario,null,s=>idle.push(s),baseline,budget);
    assert.equal(normal.at(-1).status,"complete");assert.equal(normal.at(-1).timeBudgetSeconds,budget);
    assert.equal(idle.at(-1).status,"complete");assert.equal(idle.at(-1).timeBudgetSeconds,budget);
    assert.equal(idle[0].solved,baseline);
  }
  assert.equal(JSON.stringify({scenario,baseline}),before);
});

test("invalid explicit budget does not dispatch and a mismatching server budget preserves baseline",async()=>{
  const controller=workflow.createPavementSolveController(()=>assert.fail("invalid request dispatched"));
  for (const value of [0,-1,Infinity,NaN]) await assert.rejects(controller.request({},null,()=>{},undefined,value),/秒数/);
  const baseline=idlePlan(4),states=[];
  baseline.generated={schedule_input:{time_limit_seconds:15}};
  await workflow.createPavementSolveController(()=>{},async(s,scope,base,publish)=>publish(event("started",1)))
    .request({time_limit_seconds:15},null,s=>states.push(s),baseline,60);
  assert.equal(states.at(-1).status,"interrupted");assert.equal(states.at(-1).solved,baseline);
});

test("API idle budget controls request payload and connection wait, with legacy fallback",async()=>{
  const stubUrl=url(`export const calls=[]; export const apiPostStream=(...args)=>{calls.push(args);return Promise.resolve()};
    export const apiGet=()=>{}; export const apiPost=()=>{}; export const apiPostFormData=()=>{}; export const apiPut=()=>{};`);
  const stub=await import(stubUrl);
  const api=await import(url(compile("src/api/_schedulerApi.ts").replace('from "./client"',`from "${stubUrl}"`)));
  const scenario={time_limit_seconds:15},baseline=idlePlan(4);
  for(const budget of [undefined,30,60]) {
    await api.optimizePavementIdleStream(scenario,null,baseline,()=>{},new AbortController().signal,budget);
    const [path,payload,,,wait]=stub.calls.at(-1);
    assert.equal(path,"/api/solve-scenario/idle/stream");
    assert.equal(payload.scenario,scenario);assert.equal(payload.baseline,baseline);
    assert.equal(payload.time_budget_seconds,budget);
    assert.equal(wait,((budget ?? 15)+30)*1000);
  }
  await api.solvePavementScenarioStream({...scenario,time_limit_seconds:60},null,()=>{},new AbortController().signal);
  assert.equal(stub.calls.at(-1)[4],90000);
});
