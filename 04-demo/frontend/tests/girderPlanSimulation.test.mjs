import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const feature = resolve(root, "src/features/girderPlanSimulation");
const read = (name) => readFileSync(resolve(feature, name), "utf8");

test("girder plan simulation exposes one independent page and all result views", () => {
  for (const name of [
    "index.ts",
    "GirderPlanSimulationPanel.tsx",
    "LineGraphView.tsx",
    "YardPlanEditor.tsx",
    "RouteSequenceEditor.tsx",
    "SimulationResultPanel.tsx",
    "adapter.ts",
    "styles.css",
  ]) assert.equal(existsSync(resolve(feature, name)), true, `${name} must exist`);

  const panel = read("GirderPlanSimulationPanel.tsx");
  assert.match(panel, /架梁计划推演/);
  assert.match(panel, /已确认项目主数据版本/);
  assert.match(panel, /保存新版本/);
  assert.match(panel, /校验方案/);
  assert.match(panel, /生成架梁计划/);
  assert.match(panel, /不写入现有架梁专项与综合排程/);
});

test("yard capacities distinguish beam type production inventory and erection capacity", () => {
  const source = read("YardPlanEditor.tsx");
  assert.match(source, /分梁型产能与期初库存/);
  assert.match(source, /daily_capacity_pieces/);
  assert.match(source, /initial_inventory_pieces/);
  assert.match(source, /max_inventory_pieces/);
  assert.match(source, /daily_erection_capacity_pieces/);
  assert.match(source, /每个梁场首期只配置一条架梁线/);
});

test("route editor only maintains bridge target order and confirms ambiguous paths", () => {
  const source = read("RouteSequenceEditor.tsx");
  assert.match(source, /只排列待架桥梁幅别/);
  assert.match(source, /上移/);
  assert.match(source, /下移/);
  assert.match(source, /confirmed_paths/);
  assert.match(source, /user_selected_path/);
  assert.doesNotMatch(source, /自动优化顺序|推荐替代顺序/);
});

test("object diagnostics can focus yards routes and line graph nodes", () => {
  const combined = ["adapter.ts", "LineGraphView.tsx", "YardPlanEditor.tsx", "RouteSequenceEditor.tsx"]
    .map(read)
    .join("\n");
  assert.match(combined, /data-entity-id/);
  assert.match(combined, /scrollIntoView/);
  assert.match(combined, /subject_id/);
});

test("result view shows schedule inventory delivery controls and independent confirmation", () => {
  const source = read("SimulationResultPanel.tsx");
  assert.match(source, /梁场甘特与桥梁日期/);
  assert.match(source, /工点最晚交付控制/);
  assert.match(source, /分梁型库存序列/);
  assert.match(source, /材料不足/);
  assert.match(source, /确认独立策划成果/);
  assert.match(source, /非工程技术可行结论、非综合排程收敛结果、非正式执行基线/);
});

test("frontend contract and API cover the independent lifecycle", () => {
  const contract = readFileSync(resolve(root, "src/contracts/girderPlanSimulation.ts"), "utf8");
  const api = readFileSync(resolve(root, "src/api/girderPlanSimulationApi.ts"), "utf8");
  for (const state of ["draft", "ready", "calculated", "confirmed", "stale", "blocked"]) assert.match(contract, new RegExp(`"${state}"`));
  for (const field of ["beam_type_id", "daily_capacity_pieces", "daily_erection_capacity_pieces", "latest_delivery_date", "result_fingerprint"]) assert.match(contract, new RegExp(field));
  for (const operation of ["line-graphs", "scenarios", "validate", "runs", "confirm"]) assert.match(api, new RegExp(operation));
});
