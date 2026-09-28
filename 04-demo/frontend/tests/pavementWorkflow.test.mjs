import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const load = async path => import(`data:text/javascript;base64,${Buffer.from(ts.transpileModule(readFileSync(new URL(path, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText).toString("base64")}`);
const pavement = await load("../src/domain/pavement.ts");
const workflow = await load("../src/app/workflows/scenarioWorkflow.ts");

test("roadbed statuses distinguish handed over, pending and legacy dates without guessing remarks", () => {
  assert.equal(pavement.pavementHandover({roadbed_available_date:"2026-10-25"}).status, "dated");
  assert.equal(pavement.pavementHandover({roadbed_handover_status:"handed_over"}).label, "已移交（按计划开始日）");
  assert.equal(pavement.pavementHandover({}).status, "pending");
  assert.equal(pavement.pavementHandover({roadbed_handover_status:"pending", roadbed_handover_note:"征地未解决"}).note, "征地未解决");
  assert.equal(pavement.pavementHandover({roadbed_handover_status:"dated"}).invalid, true);
  assert.equal(pavement.pavementHandover({roadbed_handover_status:"pending",roadbed_available_date:"2026-10-25"}).invalid, true);
});

test("shared fleet capabilities keep a single capacity and invalidate all edited fields", () => {
  const draft = pavement.newPavementFleet("shared");
  assert.equal(draft.quantity, 0);
  assert.equal(draft.transfer_days, null);
  const selected = pavement.togglePavementFleetProcess(pavement.togglePavementFleetProcess(draft, "gravel", true), "water", true);
  const pool = {...selected, quantity:1, max_quantity:1, transfer_days:1};
  const scenario = {engineering_domain:"pavement", resource_pools:[pool], process_library:[{id:"gravel"},{id:"water"}]};
  assert.deepEqual(draft.compatible_process_ids, []);
  assert.equal(pool.quantity, 1);
  assert.deepEqual(pavement.pavementFleetErrors(scenario), []);
  assert.ok(pavement.pavementFleetErrors({...scenario,resource_pools:[{...pool,compatible_process_ids:[]}]}).length);
  assert.ok(pavement.pavementFleetErrors({...scenario,resource_pools:[{...pool,compatible_process_ids:["bad"]}]}).length);
  assert.deepEqual(pavement.pavementFleetErrors({...scenario,resource_pools:[draft]}), []);
  const fingerprint = workflow.scenarioFingerprintForSolve(scenario);
  for (const patch of [{label:"改名"},{quantity:2},{transfer_days:2},{enabled:false},{authorized_workpoint_ids:[]},{compatible_process_ids:["water"]}]) {
    assert.notEqual(workflow.scenarioFingerprintForSolve({...scenario,resource_pools:[{...pool,...patch}]}), fingerprint);
  }
  assert.deepEqual(pavement.togglePavementFleetProcess(pool,"gravel",false).compatible_process_ids,["water"]);
});

test("material tonnes use actual layer dimensions and reject missing or invalid values", () => {
  const quantity = pavement.pavementLayerQuantityT;
  assert.ok(Math.abs(quantity(2490, 9.2, .2, 2.38) - 10904.208) < 1e-8);
  assert.ok(Math.abs(quantity(4949, 14, .2, 2.38) - 32980.136) < 1e-8);
  assert.equal(quantity("100", "10", ".25", "2"), 500);
  assert.equal(quantity(0, 10, .25, 2), 0);
  for (const invalid of [null, undefined, "", " ", false, -1, Infinity, NaN]) {
    assert.equal(quantity(invalid, 10, .25, 2), null);
    assert.equal(quantity(100, invalid, .25, 2), null);
    assert.equal(quantity(100, 10, invalid, 2), null);
    assert.equal(quantity(100, 10, .25, invalid), null);
  }
  assert.equal(quantity(100, 0, .25, 2), null);
  assert.equal(quantity(100, 10, 0, 2), null);
  assert.equal(quantity(100, 10, .25, 0), null);
});

test("durations use per-fleet productivity and reject invalid/mismatched inputs", () => {
  assert.deepEqual([760,410,680].map(n => pavement.pavementDuration(n,"m",700,"m/天")), [2,1,1]);
  assert.equal(pavement.pavementDuration(760,"m",0,"m/天"), null);
  assert.equal(pavement.pavementDuration(760,"m3",700,"m/天"), null);
});
test("all road conditions, fleets and versions invalidate generated results", () => {
  const base = { engineering_domain: "pavement", pavement_settings: pavement.emptyPavementSettings(), resource_pools: [], project_data_version_id: "v1" };
  const old = workflow.scenarioFingerprintForSolve(base);
  for (const patch of [
    { project_data_version_id: "v2" }, { task_overrides: { a: { productivity_option_id: "other" } } },
    { resource_pools: [{ quantity: 2, transfer_days: 1 }] },
    { pavement_settings: { ...base.pavement_settings, layer_conditions: [{component_id:"a",wait_days:7,basis_note:"确认"}] } },
    { pavement_settings: { ...base.pavement_settings, dependency_rules: [{predecessor_key:"a",successor_key:"b",relationship:"SS",lag_days:2}] } },
  ]) assert.notEqual(workflow.scenarioFingerprintForSolve({...base,...patch}), old);
});

function relationScenario() {
  return { pavement_settings: { ...pavement.emptyPavementSettings(), layer_conditions: [
    { component_id: "A-1", wait_days: 7 }, { component_id: "B-1", wait_days: 7 },
  ] }, project: { bridges: [{ work_sections: ["A", "B"].map(id => ({ id, name: id, structures: [{ id, components: [
    { id: `${id}-1`, name: "水稳", component_type: "cement_stabilized_base", enabled: true, properties: { layer_order: 1 } },
    { id: `${id}-2`, name: "沥青", component_type: "asphalt_course", enabled: true, properties: { layer_order: 2 } },
  ] }] })) }] } };
}

test("dependency rows resolve project and section rules and restore inheritance", () => {
  const scenario = relationScenario();
  const rule = { predecessor_key: "layer:cement_stabilized_base:1", successor_key: "layer:asphalt_course:1", relationship: "FS", lag_days: 7 };
  scenario.pavement_settings = pavement.setPavementDependencyRule(scenario.pavement_settings, rule);
  const local = { ...rule, structure_id: "B", relationship: "SS", lag_days: 2 };
  scenario.pavement_settings = pavement.setPavementDependencyRule(scenario.pavement_settings, local);
  const values = () => pavement.pavementDependencyRows(scenario).map(r => [r.structure_id, r.relationship, r.lag_days, r.source]);
  assert.deepEqual(values(), [["A", "FS", 7, "project"], ["B", "SS", 2, "section"]]);
  scenario.pavement_settings = pavement.setPavementDependencyRule(scenario.pavement_settings, local, true);
  assert.deepEqual(values(), [["A", "FS", 7, "project"], ["B", "FS", 7, "project"]]);
  scenario.pavement_settings = pavement.setPavementDependencyRule(scenario.pavement_settings, { ...rule, lag_days: null });
  assert.ok(pavement.pavementDependencyRows(scenario).every(r => r.lag_days === null));
  assert.equal(scenario.pavement_settings.dependency_rules.length, 1);
  assert.equal(scenario.pavement_settings.layer_conditions[0].wait_days, 7);
});

test("dependency node keys include disabled layer positions and zero-day preparation ordinals", () => {
  const scenario = relationScenario();
  const components = scenario.project.bridges[0].work_sections[0].structures[0].components;
  components.unshift({ id: "disabled", name: "原下层", component_type: "cement_stabilized_base", enabled: false, properties: { layer_order: 0 } });
  scenario.pavement_settings.ancillary_steps = [
    { id: "zero", before_component_id: "A-2", kind: "seal", name: "零天条件", order: 1, duration_days: 0, wait_after_days: 1 },
    { id: "seal", before_component_id: "A-2", kind: "seal", name: "封层", order: 2, duration_days: 1, wait_after_days: 2 },
  ];
  const rows = pavement.pavementDependencyRows(scenario).filter(r => r.structure_id === "A");
  assert.deepEqual(rows.map(r => [r.predecessor_key, r.successor_key, r.lag_days]), [
    ["layer:cement_stabilized_base:2", "layer:asphalt_course:1/prep:seal:2", 8],
    ["layer:asphalt_course:1/prep:seal:2", "layer:asphalt_course:1", 2],
  ]);
});

test("disabled asphalt retains its editable predecessor without entering the active task chain", () => {
  const scenario = relationScenario();
  for (const section of scenario.project.bridges[0].work_sections) {
    section.structures[0].components[1].enabled = false;
  }
  const rule = { predecessor_key: "layer:cement_stabilized_base:1", successor_key: "layer:asphalt_course:1", relationship: "FS", lag_days: 7 };
  scenario.pavement_settings = pavement.setPavementDependencyRule(scenario.pavement_settings, rule);
  const before = JSON.stringify(scenario);
  assert.deepEqual(pavement.pavementDependencyRows(scenario), []);
  assert.deepEqual(pavement.pavementDependencyRows(scenario, true).map(row =>
    [row.predecessor_name, row.successor_name, row.relationship, row.lag_days, row.source]),
    [["水稳", "沥青", "FS", 7, "project"], ["水稳", "沥青", "FS", 7, "project"]]);
  assert.equal(JSON.stringify(scenario), before);
  scenario.pavement_settings = pavement.setPavementDependencyRule(scenario.pavement_settings, { ...rule, structure_id: "B", lag_days: 10 });
  assert.deepEqual(pavement.pavementDependencyRows(scenario, true).map(row => row.lag_days), [7, 10]);
  assert.deepEqual(pavement.pavementDependencyRows(scenario), []);
  assert.ok(pavement.pavementLayers(scenario).every(layer => layer.component.component_type !== "asphalt_course"));
});

test("bulk waits only fill missing conditions of the selected process", () => {
  const settings = { ...pavement.emptyPavementSettings(), layer_conditions: [{ component_id: "w1", wait_days: 9, accepted_available_date: "2026-12-01", basis_note: "已确认" }], ancillary_steps: [{ id: "prime" }] };
  const scenario = { pavement_settings: settings, project: { bridges: [{ work_sections: [{ structures: [{ components: [
    { id: "w1", component_type: "cement_stabilized_base", enabled: true },
    { id: "w2", component_type: "cement_stabilized_base", enabled: true },
    { id: "w3", component_type: "cement_stabilized_base", enabled: false },
    { id: "a1", component_type: "asphalt_course", enabled: true },
  ] }] }] }] } };
  const result = pavement.fillMissingPavementConditions(scenario, "cement_stabilized_base", 7);
  assert.equal(result.layer_conditions.length, 2);
  assert.deepEqual(result.layer_conditions[0], settings.layer_conditions[0]);
  assert.equal(result.layer_conditions[1].component_id, "w2");
  assert.equal(result.layer_conditions[1].wait_days, 7);
  assert.deepEqual(result.ancillary_steps, settings.ancillary_steps);
  assert.equal(settings.layer_conditions.length, 1);
  assert.throws(() => pavement.fillMissingPavementConditions(scenario, "asphalt_course", -1));
  assert.throws(() => pavement.fillMissingPavementConditions(scenario, "asphalt_course", 1.5));
  assert.equal(pavement.fillMissingPavementConditions(scenario, "asphalt_course", 0).layer_conditions[1].wait_days, 0);
});
