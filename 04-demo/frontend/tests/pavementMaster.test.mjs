import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { createRequire } from "node:module";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = (path) => readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8");
test("pavement master keeps empty state, source and normalized quantities visible", () => {
  assert.match(source("features/projectMasterData/ProjectMasterDataWorkspace.tsx"), /尚未建立项目主数据/);
  assert.match(source("features/projectMasterData/ProjectMasterDataWorkspace.tsx"), /downloadProjectMasterTemplate\(engineeringDomain\)/);
  assert.match(source("features/projectMasterData/WorkPointDetail.tsx"), /确认净施工长度/);
  assert.match(source("features/projectMasterData/WorkPointDetail.tsx"), /厚度（统一m）/);
  assert.match(source("features/projectMasterData/WorkPointDetail.tsx"), /支持路面排程/);
  assert.match(source("domain/projectMaster.ts"), /issue\.sheet_name/);
  assert.match(source("domain/projectMaster.ts"), /issue\.row_no/);
});

const require = createRequire(import.meta.url);
function loadSource(path) {
  const compiled = ts.transpileModule(source(path), {
    fileName: path,
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} };
  new Function("require", "module", "exports", compiled)((name) => {
    if (name === "../../api/projectMasterApi") return {};
    if (name === "../../domain/projectMaster") return loadSource("domain/projectMaster.ts");
    if (name === "../../domain/pavement") return loadSource("domain/pavement.ts");
    if (name === "./PavementSectionLayers") return loadSource("features/projectMasterData/PavementSectionLayers.tsx");
    if (name === "./PavementSectionHandover") return loadSource("features/projectMasterData/PavementSectionHandover.tsx");
    return require(name);
  }, module, module.exports);
  return module.exports;
}
const { PavementMasterTable } = loadSource("features/projectMasterData/PavementMasterTable.tsx");
const parameters = values => Object.entries(values).map(([parameter_code, value]) => ({ parameter_code, value }));
const section = (sort_order, values, extra = {}) => ({
  structure_id: `S${sort_order}`, sort_order, section_name: "左幅", structure_name: `第${sort_order}段`,
  side: "left", parameters: parameters(values), components: [], ...extra,
});
const workpoint = structures => ({ workpoint_id: "road", workpoint_name: "路面工程", sort_order: 1, structures });
const render = structures => renderToStaticMarkup(createElement(PavementMasterTable, { workpoints: [workpoint(structures)] }));
function tableRows(html, name = "施工段明细") {
  const body = html.split(`aria-label="${name}"`)[1].split("<tbody>")[1].split("</tbody>")[0];
  return [...body.matchAll(/<tr[^>]*>(.*?)<\/tr>/g)].map(row =>
    [...row[1].matchAll(/<(?:td|th)[^>]*>(.*?)<\/(?:td|th)>/g)].map(cell => cell[1].replace(/<[^>]+>/g, "")));
}

test("segment table has inline units and only segment attributes, preserving source lengths and chainage", () => {
  const rows = [
    section(9, { start_chainage: "K675+120", end_chainage: "CK0+000", construction_length_m: 4949, width_m: 14, water_stable_thickness_m: 0.76, water_stable_density_t_m3: 2.38, roadbed_available_date: "2026-07-10" }, {
      remark: "原表工程量：125325（疑似质量，单位待确认）。原表工期：50 天（对应工序未明确）。",
    }),
    section(3, { start_chainage: "K669+937", end_chainage: "K672+560", construction_length_m: 1614, width_m: 9.2, water_stable_thickness_m: 0.76, water_stable_density_t_m3: 2.38, roadbed_available_date: "2026-10-16" }, {
      remark: "原表工程量：26,859（疑似质量）。原表工期：6天。",
    }),
  ];
  const html = render(rows);
  assert.deepEqual(tableRows(html), [
    ["1", "左幅", "K669+937–K672+560", "1,614", "9.2", "2026-10-16"],
    ["2", "左幅", "K675+120–CK0+000", "4,949", "14", "2026-07-10"],
  ]);
  assert.match(html, /6,563/);
  assert.match(html, /施工长度（m）/);
  assert.match(html, /宽度（m）/);
  assert.doesNotMatch(html, /水稳厚度|水稳密度|水稳工程量|<small>/);
  assert.doesNotMatch(html.replace(/title="[^"]*"/g, ""), /原表工程量|原表工期|排程依据|待确认|参考数据|查看原始说明|结构层待补充/);
  assert.equal(rows[0].sort_order, 9, "display sorting must not mutate source data");
});

test("pavement table never invents missing values from remarks or chainage arithmetic", () => {
  const html = render([section(1, { start_chainage: "K1+000", end_chainage: "K2+000", construction_length_m: "" }, {
    remark: "征地问题未解决，时间暂定",
  })]);
  assert.deepEqual(tableRows(html)[0], ["1", "左幅", "K1+000–K2+000", "—", "—", "移交待定：尚未明确移交条件"]);
  assert.deepEqual(tableRows(render([section(1, {})]))[0].slice(-3), ["—", "—", "移交待定：尚未明确移交条件"]);
  assert.equal(tableRows(render([section(1, {}, { remark: "已完成" })]))[0].at(-1), "移交待定：尚未明确移交条件");
  assert.match(html, /已填写长度/);
  assert.match(render([]), /当前版本暂无路面施工段/);
});

test("handover editor and summary reflect explicit statuses with no invented date", () => {
  const rows = [section(1, {roadbed_handover_status:"handed_over"}), section(2, {roadbed_handover_status:"pending",roadbed_handover_note:"征地未解决"})];
  const html = render(rows);
  assert.match(html, /已移交（按计划开始日）/);
  assert.match(html, /移交待定：征地未解决/);
  const editor = renderToStaticMarkup(createElement(PavementMasterTable, {workpoints:[workpoint(rows)],readOnly:false,onExpand:()=>{},onSaveHandover:async()=>{}}));
  assert.match(editor, /路床移交状态/);
  assert.match(editor, /保存移交条件/);
  assert.doesNotMatch(editor, /aria-label="路床移交日期"/);
});

test("failed handover save retains the draft; non-dated transition clears the effective date", async () => {
  const state = [];
  let cursor = 0;
  const module = {exports:{}};
  const compiled = ts.transpileModule(source("features/projectMasterData/PavementSectionHandover.tsx"), {
    compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,jsx:ts.JsxEmit.ReactJSX},
  }).outputText;
  new Function("require","module","exports",compiled)(name => {
    if(name === "react") return {useEffect(effect) { effect(); },useState(initial) {const i=cursor++; if(!(i in state)) state[i]=initial; return [state[i],value=>{state[i]=typeof value==='function'?value(state[i]):value;}];}};
    if(name === "../../domain/pavement") return loadSource("domain/pavement.ts");
    return require(name);
  },module,module.exports);
  let submitted;
  let reportedDirty = false;
  const props = {section:section(1,{roadbed_available_date:"2026-10-25"}),readOnly:false,onDirtyChange:(_key,dirty)=>{reportedDirty=dirty;},onSave:async(id,values)=>{submitted={id,values}; throw new Error("主数据已更新，请重新加载当前版本后再编辑。");}};
  const renderEditor=()=>{cursor=0;return module.exports.PavementSectionHandover(props);};
  const nodes=root=>!root||typeof root!=='object'?[]:[root,...[root.props?.children].flat(Infinity).flatMap(nodes)];
  const find=(root,key,value)=>nodes(root).find(n=>n.props?.[key]===value);
  let tree=renderEditor();
  find(tree,'aria-label','路床移交状态').props.onChange({target:{value:'pending'}});
  tree=renderEditor();
  assert.equal(find(tree,'aria-label','路床移交日期'),undefined);
  find(tree,'aria-label','路床移交说明').props.onChange({target:{value:'征地未解决'}});
  tree=renderEditor();
  nodes(tree).find(n=>n.type==='button').props.onClick();
  await new Promise(resolve=>setImmediate(resolve));
  tree=renderEditor();
  assert.equal(submitted.values.available_date,null);
  assert.equal(submitted.values.status,'pending');
  assert.equal(find(tree,'aria-label','路床移交说明').props.value,'征地未解决');
  assert.match(find(tree,'role','alert').props.children,/主数据已更新/);
  assert.equal(nodes(tree).find(n=>n.type==='button').props.disabled,false);
  assert.equal(reportedDirty,true);
});

test("layer table derives tonnes from layer attributes and retains missing density and disabled state", () => {
  const html = render([section(1, { construction_length_m: 100, width_m: 9.2 }, { components: [
    { component_id: "water", component_name: "水稳下基层", component_type: "cement_stabilized_base", quantity: 100, unit: "m", sort_order: 2, enabled: false, parameters: parameters({ thickness_m: 0.2, density_t_m3: 2.38 }) },
    { component_id: "gravel", component_name: "碎石垫层", component_type: "granular_base", quantity: 160, unit: "m3", sort_order: 1, enabled: true, parameters: parameters({ thickness_m: 0.16 }) },
  ] })]);
  assert.deepEqual(tableRows(html, "结构层明细"), [
    ["第1段", "1", "碎石垫层", "碎石", "0.16", "—", "—", "启用", ""],
    ["第1段", "2", "水稳下基层", "水稳", "0.2", "2.38", "438", "停用", ""],
  ]);
  assert.doesNotMatch(html, /结构层待补充/);
});

test("layers render under their own section with editable empty thickness and a local save action", () => {
  const entry = section(1, { construction_length_m: 2490 }, { components: [
    { component_id: "water", component_name: "水稳下基层", component_type: "cement_stabilized_base", quantity: 2490, unit: "m", sort_order: 1, enabled: true, parameters: [] },
  ] });
  const html = renderToStaticMarkup(createElement(PavementMasterTable, { workpoints: [workpoint([entry])], readOnly: false, onExpand: () => {}, onSaveLayers: async () => {} }));
  assert.match(html, /pavement-section-detail-row/);
  assert.match(html, /第1段 · 结构层/);
  assert.match(html, /aria-label="第1层厚度"[^>]*placeholder="待填写"[^>]*value=""/);
  assert.match(html, /aria-label="第1层密度"[^>]*placeholder="待填写"[^>]*value=""/);
  assert.match(html, /工程量（t）/);
  assert.doesNotMatch(html, /2,490 m/);
  assert.match(html, /保存本段/);
  assert.doesNotMatch(html, /单段结构层模板|预览应用结果/);
  const historical = renderToStaticMarkup(createElement(PavementMasterTable, { workpoints: [workpoint([entry])], readOnly: true, onExpand: () => {} }));
  assert.match(historical, /历史版本，只读/);
  assert.doesNotMatch(historical, /保存本段|添加结构层/);
});

test("nested editor uses its parent section width and layer thickness, rounding only displayed tonnes", () => {
  for (const [id, length, width, expected] of [[1, 2490, 9.2, "10,904"], [9, 4949, 14, "32,980"]]) {
    const entry = section(id, { construction_length_m: length, width_m: width }, { components: [
      { component_id: "water", component_name: "水稳下基层", component_type: "cement_stabilized_base", quantity: length, unit: "m", sort_order: 1, enabled: true, parameters: parameters({ thickness_m: .2, density_t_m3: 2.38 }) },
      { component_id: "asphalt", component_name: "沥青面层", component_type: "asphalt_course", quantity: length, unit: "m", sort_order: 2, enabled: false, parameters: [] },
    ] });
    const html = renderToStaticMarkup(createElement(PavementMasterTable, { workpoints: [workpoint([entry])], readOnly: false, onExpand: () => {} }));
    assert.ok(html.includes(`>${expected}</td>`));
    assert.match(html, /aria-label="第1层密度"[^>]*value="2.38"/);
    assert.doesNotMatch(html.match(/<input[^>]*aria-label="第2层启用"[^>]*>/)[0], /checked/);
  }
});
