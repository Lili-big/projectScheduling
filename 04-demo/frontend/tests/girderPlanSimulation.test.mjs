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
  assert.match(panel, /Promise\.allSettled/);
  assert.match(panel, /后端服务尚未加载架梁计划推演接口/);
});

test("yard capacities distinguish beam type production inventory and erection capacity", () => {
  const source = read("YardPlanEditor.tsx");
  assert.match(source, /分梁型产能与期初库存/);
  assert.match(source, /daily_capacity_pieces/);
  assert.match(source, /initial_inventory_pieces/);
  assert.match(source, /max_inventory_pieces/);
  assert.match(source, /daily_erection_capacity_pieces/);
  assert.match(source, /每个梁场首期只配置一条架梁线/);
  for (const label of ["制梁能力（片/天）", "期初库存（片）", "最大库存（片，可空）"]) assert.match(source, new RegExp(label));
});

test("line graph renders two fixed carriageways on one spatial grid", () => {
  const source = read("LineGraphView.tsx");
  const styles = read("styles.css");
  assert.match(source, /label: "左幅", prefix: "ZK"/);
  assert.match(source, /label: "右幅", prefix: "K"/);
  assert.match(source, /spatial_group_id/);
  assert.match(source, /display_order/);
  assert.match(source, /alignment_code/);
  assert.match(source, /girder-sim-node-slot/);
  assert.doesNotMatch(source, /该幅暂无工点/);
  assert.match(styles, /grid-template-columns/);
  assert.match(styles, /overflow-x:\s*auto/);
});

test("line graph keeps ZK and K on the main tracks and moves interchange prefixes into compact branches", () => {
  const source = read("LineGraphView.tsx");
  const styles = read("styles.css");
  assert.match(source, /isMainlineNode/);
  assert.match(source, /branchRoutes/);
  assert.match(source, /girder-sim-branch-layer/);
  assert.match(source, /girder-sim-branch-route/);
  assert.match(source, /girder-sim-branch-connector/);
  assert.match(source, /normalizedPrefix\(node\)/);
  assert.match(source, /title=\{node\.name\}/);
  assert.doesNotMatch(source, /该幅暂无工点|girder-sim-slot-empty/);
  assert.match(styles, /\.girder-sim-branch-layer/);
  assert.match(styles, /\.girder-sim-branch-route/);
  assert.match(styles, /\.girder-sim-branch-connector/);
  assert.match(styles, /text-overflow:\s*ellipsis/);
});

test("line graph uses two horizontal route segments with typed workpoint and yard legends", () => {
  const source = read("LineGraphView.tsx");
  const panel = read("GirderPlanSimulationPanel.tsx");
  const styles = read("styles.css");
  for (const label of ["路基", "桥梁", "隧道", "互通/连接", "梁场"]) assert.match(source, new RegExp(label));
  assert.match(source, /girder-sim-legend-line/);
  assert.match(source, /girder-sim-track-marker/);
  assert.match(source, /type === "roadbed" \|\| type === "bridge" \|\| type === "tunnel"/);
  assert.doesNotMatch(source, /import \{[^}]*\bRoute\b[^}]*\} from "lucide-react"/);
  assert.match(source, /girder-sim-yard-marker/);
  assert.match(panel, /yards=\{draft\.beamYards\}/);
  assert.match(styles, /girder-sim-node-slot::before/);
  assert.match(styles, /height:\s*4px/);
});

test("line graph uses the right K mileage axis, compressed roadbeds, emphasized structures and mileage-positioned yards", () => {
  const source = read("LineGraphView.tsx");
  const editor = read("YardPlanEditor.tsx");
  const styles = read("styles.css");
  assert.match(source, /右幅 K 里程主轴/);
  assert.match(source, /minmax\(26px/);
  assert.match(source, /axisTickLabel/);
  assert.match(source, /normalizedPrefix\(node\) === "K"/);
  assert.match(source, /visualGroupWidth/);
  assert.match(source, /roadbed: \{ base: 40, factor: 0\.5/);
  assert.match(source, /girder-sim-track-span/);
  assert.match(source, /yardOffsetPercent/);
  assert.match(source, /formatMileageRange/);
  assert.match(editor, /梁场中心里程（m）/);
  assert.match(editor, /centerMileage/);
  assert.match(styles, /girder-sim-mileage-axis-track/);
  assert.match(styles, /girder-sim-track-span\.bridge/);
  assert.match(styles, /girder-sim-track-span\.bridge\.approach_small/);
  assert.match(styles, /girder-sim-track-span\.bridge\.continuous/);
  assert.match(styles, /girder-sim-track-span\.bridge\.approach_large/);
  assert.match(styles, /girder-sim-track-span\.tunnel/);
  assert.match(styles, /girder-sim-track-span\.roadbed \{ height: 4px; background: #7994b5; box-shadow: none/);
});

test("dense workpoint names use two visible lanes and bridge tunnel markers are line-only", () => {
  const source = read("LineGraphView.tsx");
  const styles = read("styles.css");
  assert.match(source, /girder-sim-node-label/);
  assert.match(source, /labelLane/);
  assert.match(source, /nodePositionPercent/);
  assert.match(source, /isLineOnlyNode/);
  assert.match(source, /bridge_segment_kind/);
  assert.match(source, /workpointDisplayName/);
  assert.match(source, /deployedYards\.length \* 28 \+ 10/);
  assert.match(source, /<span>\{workpointDisplayName\(node\)\}<\/span>/);
  assert.match(source, /title=\{node\.name\}/);
  assert.doesNotMatch(source, /<small><b>\{node\.alignment_code/);
  assert.match(styles, /girder-sim-node-label\.lane-0/);
  assert.match(styles, /girder-sim-node-label\.lane-1/);
  assert.match(styles, /overflow:\s*visible/);
  assert.match(styles, /white-space:\s*nowrap/);
  assert.match(styles, /background:\s*transparent\s*!important/);
  assert.match(styles, /box-shadow:\s*none/);
  assert.match(styles, /max-width:\s*calc\(100% - 6px\)\s*!important/);
  assert.match(styles, /text-overflow:\s*ellipsis/);
  assert.doesNotMatch(styles, /girder-sim-node-label\.selected\s*\{[^}]*outline/);
  assert.doesNotMatch(styles, /girder-sim-node-label\.late\s*\{[^}]*background/);
  assert.match(styles, /grid-template-rows:\s*32px 24px auto minmax\(4px, auto\)/);
  assert.doesNotMatch(source, /girder-sim-node-title/);
});

test("continuous bridge blocks are independently selectable while continuous structures remain passage-only", () => {
  const source = read("LineGraphView.tsx");
  const routeEditor = read("RouteSequenceEditor.tsx");
  const adapter = read("adapter.ts");
  const styles = read("styles.css");
  assert.match(source, /selectedNodeId/);
  assert.match(source, /aria-pressed=\{selectedNodeId === node\.node_id\}/);
  assert.match(source, /segmentRoleLabel/);
  assert.match(source, /连续结构（仅通行）/);
  assert.match(source, /运梁通道/);
  assert.match(source, /data-segment-kind/);
  assert.match(adapter, /filter\(\(node\) => node\.requires_erection\)/);
  assert.match(routeEditor, /连续结构段仅作为运梁通道自动补齐/);
  assert.match(styles, /girder-sim-track-span\.selected/);
  assert.match(styles, /girder-sim-node-label\.lane-2/);
  assert.match(styles, /girder-sim-track-span\.bridge\.approach_small::after/);
  assert.match(styles, /girder-sim-track-span\.bridge\.continuous::after/);
  assert.match(styles, /girder-sim-track-span\.bridge\.approach_large::after/);
});

test("line graph does not expose scheme-level manual connection selection", () => {
  const source = read("LineGraphView.tsx");
  const panel = read("GirderPlanSimulationPanel.tsx");
  const adapter = read("adapter.ts");
  const styles = read("styles.css");
  for (const removed of ["onConfirmConnection", "connectionNodes", "toggleConnectionNode", "人工连接确认", "确认连接"]) {
    assert.doesNotMatch(source, new RegExp(removed));
  }
  assert.doesNotMatch(panel, /confirmConnection|connectionOverrides|方案级人工连接/);
  assert.match(panel, /connection_overrides:\s*\[\]/);
  assert.doesNotMatch(adapter, /connectionOverrides/);
  assert.doesNotMatch(styles, /girder-sim-connection/);
});

test("yard deployment writes a stable dual-carriageway node and preserves legacy fallback", () => {
  const editor = read("YardPlanEditor.tsx");
  const adapter = read("adapter.ts");
  assert.match(editor, /deployment_node_id/);
  assert.match(editor, /原部署节点已失效，请重新选择/);
  assert.match(editor, /左幅|右幅/);
  assert.match(adapter, /yard\.deployment_node_id/);
  assert.match(adapter, /candidates\.length === 1/);
});

test("route editor only maintains bridge target order and confirms ambiguous paths", () => {
  const source = read("RouteSequenceEditor.tsx");
  assert.match(source, /只排列待架引桥段/);
  assert.match(source, /连续结构段仅作为运梁通道自动补齐，不计入架梁任务/);
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
  for (const field of ["projection_version", "bridge_segment_kind", "spatial_group_id", "placement_source", "deployment_node_id", "beam_type_id", "daily_capacity_pieces", "daily_erection_capacity_pieces", "latest_delivery_date", "result_fingerprint"]) assert.match(contract, new RegExp(field));
  for (const operation of ["line-graphs", "scenarios", "validate", "runs", "confirm"]) assert.match(api, new RegExp(operation));
});
