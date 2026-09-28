import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import ts from "typescript";

const root = resolve(import.meta.dirname, "..");

function toDataUrl(source) {
  return `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
}

async function loadResources() {
  const transpile = (path) => ts.transpileModule(readFileSync(path, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
    fileName: path,
  }).outputText;
  const constantsUrl = toDataUrl(transpile(resolve(root, "src/domain/constants.ts")));
  const source = transpile(resolve(root, "src/domain/resources.ts"))
    .replaceAll('from "./constants"', `from "${constantsUrl}"`);
  return import(toDataUrl(source));
}

function pool(patch = {}) {
  return {
    id: "pool-1",
    type: "resource-type",
    label: "资源一",
    resource_mode: "LIMITED",
    quantity: 2,
    max_quantity: 4,
    calendar_id: "continuous",
    enabled: true,
    compatible_process_ids: [],
    ...patch,
  };
}

function process(id, componentType, resourceType, { methodId = null, isDefault = true, processName = id } = {}) {
  return {
    id,
    process_name: processName,
    component_type: componentType,
    method_id: methodId,
    resource_type: resourceType,
    is_default: isDefault,
  };
}

function parameter(parameterCode, value, { valueType = typeof value === "number" ? "number" : "text", unit = null, sortOrder = 1 } = {}) {
  return { parameter_code: parameterCode, value_type: valueType, value, unit, sort_order: sortOrder };
}

function component(componentId, componentType, {
  enabled = true,
  methodId = null,
  quantity = 1,
  unit = "个",
  parameters = [],
} = {}) {
  return {
    component_id: componentId,
    structure_id: "structure-lower",
    component_name: componentId,
    component_type: componentType,
    quantity,
    unit,
    enabled,
    sort_order: 1,
    parameters: [...parameters, ...(methodId ? [parameter("method_id", methodId)] : [])],
  };
}

function structure(structureId, structureType, components = [], parameters = []) {
  return {
    structure_id: structureId,
    workpoint_id: "WP-A",
    structure_name: structureId,
    structure_category: structureType.endsWith("unit") ? "superstructure" : "substructure",
    structure_type: structureType,
    side: "left",
    sort_order: 1,
    parameters,
    components,
  };
}

function workpoint(structures) {
  return {
    workpoint_id: "WP-A",
    workpoint_name: "测试工点",
    workpoint_type: "bridge",
    sort_order: 1,
    schedule_support: "bridge_supported",
    structures,
  };
}

const processLibrary = [
  process("pile_rotary_regular", "pile", "rotary_drill", { methodId: "rotary_drill", processName: "旋挖钻" }),
  process("pile_circulation", "pile", "circulation_drill", { methodId: "circulation_drill", isDefault: false, processName: "回旋钻" }),
  process("pile_impact", "pile", "impact_drill", { methodId: "impact_drill", isDefault: false, processName: "冲击钻" }),
  process("pile_manual", "pile", "manual_pile_team", { methodId: "manual_pile", isDefault: false, processName: "人工挖孔" }),
  process("cap_standard", "cap", "cap_team", { processName: "承台施工" }),
  process("middle_tie_standard", "middle_tie_beam", "tie_beam_team", { processName: "柱系梁施工" }),
  process("pier_body_standard", "pier_body", "pier_body_team", { processName: "墩身施工" }),
  process("pier_body_climbing_form", "pier_body", "pier_body_team", { methodId: "climbing_form", isDefault: false, processName: "爬模施工" }),
  process("ground_tie_standard", "ground_tie_beam", "tie_beam_team", { processName: "桩系梁施工" }),
  process("cap_beam_standard", "cap_beam", "cap_beam_team", { processName: "盖梁施工" }),
  process("continuous_default", "cast_in_place_continuous_beam", "cast_in_place_continuous_beam_team", { processName: "连续梁施工" }),
];

test("legacy pools migrate generically to project shared while null and empty authorization stay distinct", async () => {
  const { normalizeResourcePoolForWorkspace } = await loadResources();

  const migrated = normalizeResourcePoolForWorkspace(pool());
  assert.equal(migrated.scope_mode, "PROJECT_SHARED");
  assert.equal(migrated.authorized_workpoint_ids, null);
  assert.deepEqual(migrated.workpoint_overrides, []);
  assert.equal(migrated.quantity, 2);
  assert.equal(normalizeResourcePoolForWorkspace(pool({ authorized_workpoint_ids: null })).authorized_workpoint_ids, null);
  assert.deepEqual(normalizeResourcePoolForWorkspace(pool({ authorized_workpoint_ids: [] })).authorized_workpoint_ids, []);
});

test("exclusive workpoints inherit global values, accept partial overrides and restore inheritance", async () => {
  const {
    effectiveWorkpointResource,
    restoreWorkpointResourceInheritance,
    setWorkpointResourceOverride,
  } = await loadResources();
  const exclusive = pool({
    scope_mode: "WORKPOINT_EXCLUSIVE",
    authorized_workpoint_ids: ["WP-B", "WP-A", "WP-A"],
  });

  assert.deepEqual(effectiveWorkpointResource(exclusive, "WP-B"), {
    workpointId: "WP-B",
    enabled: true,
    quantity: 2,
    maxQuantity: 4,
    inheritanceSource: "inherited",
  });

  const overridden = setWorkpointResourceOverride(exclusive, "WP-B", { quantity: 3 });
  assert.deepEqual(overridden.authorized_workpoint_ids, ["WP-A", "WP-B"]);
  assert.deepEqual(overridden.workpoint_overrides, [{ workpoint_id: "WP-B", quantity: 3 }]);
  assert.deepEqual(effectiveWorkpointResource(overridden, "WP-B"), {
    workpointId: "WP-B",
    enabled: true,
    quantity: 3,
    maxQuantity: 4,
    inheritanceSource: "overridden",
  });

  const restored = restoreWorkpointResourceInheritance(overridden, "WP-B");
  assert.deepEqual(restored.workpoint_overrides, []);
  assert.equal(effectiveWorkpointResource(restored, "WP-B").inheritanceSource, "inherited");
});

test("scope normalization and fingerprint use stable sets without resource-name or id-format rules", async () => {
  const {
    normalizeResourcePoolForWorkspace,
    resourcePoolsSemanticFingerprint,
    resourcePoolScopeIssues,
  } = await loadResources();
  const left = pool({
    id: "arbitrary",
    scope_mode: "WORKPOINT_EXCLUSIVE",
    authorized_workpoint_ids: ["z", "a", "z"],
    workpoint_overrides: [
      { workpoint_id: "z", quantity: 3, max_quantity: null },
      { workpoint_id: "a", enabled: null, quantity: null, max_quantity: null },
    ],
  });
  const right = pool({
    id: "arbitrary",
    scope_mode: "WORKPOINT_EXCLUSIVE",
    authorized_workpoint_ids: ["a", "z"],
    workpoint_overrides: [{ workpoint_id: "z", max_quantity: null, quantity: 3 }],
  });

  assert.deepEqual(normalizeResourcePoolForWorkspace(left).authorized_workpoint_ids, ["a", "z"]);
  assert.equal(resourcePoolsSemanticFingerprint([left]), resourcePoolsSemanticFingerprint([right]));
  assert.deepEqual(resourcePoolScopeIssues(left, ["a", "z"]), []);
  assert.deepEqual(resourcePoolScopeIssues(right, ["a"]), ["配置包含当前项目主数据版本之外的工点"]);
});

test("scenario normalization removes project shared pools without mutating the source", async () => {
  const { normalizeScenarioResourcePools } = await loadResources();
  const shared = pool({ id: "shared", resource_mode: "UNLIMITED", quantity: null, max_quantity: null });
  const local = pool({ id: "local", scope_mode: "WORKPOINT_EXCLUSIVE", workpoint_id: "WP-A" });
  const scenario = {
    marker: "scenario",
    resource_pools: [shared, local],
  };
  const normalized = normalizeScenarioResourcePools(scenario);

  assert.deepEqual(normalized.resource_pools.map((item) => item.id), ["local"]);
  assert.equal(normalized.resource_pools[0].scope_mode, "WORKPOINT_EXCLUSIVE");
  assert.equal(normalized.resource_pools[0].workpoint_id, "WP-A");
  assert.deepEqual(scenario.resource_pools, [shared, local]);
});

test("workpoint-local pools upsert by workpoint and type while deriving enabled from quantity", async () => {
  const {
    localResourcePoolsForWorkpoint,
    upsertWorkpointLocalResource,
  } = await loadResources();
  const initial = [pool({ id: "shared-x", type: "team-x", scope_mode: "PROJECT_SHARED" })];
  const added = upsertWorkpointLocalResource(initial, "WP-A", {
    id: "local-a-x",
    type: "team-x",
    label: "A 点班组",
    quantity: 0,
    max_quantity: 3,
    enabled: true,
  });
  const updated = upsertWorkpointLocalResource(added, "WP-A", {
    id: "ignored-new-id",
    type: "team-x",
    label: "A 点班组",
    quantity: 2,
    max_quantity: 4,
    enabled: true,
  });

  assert.equal(updated.length, 2);
  assert.deepEqual(localResourcePoolsForWorkpoint(updated, "WP-A").map((item) => ({
    id: item.id,
    workpoint_id: item.workpoint_id,
    quantity: item.quantity,
    max_quantity: item.max_quantity,
    enabled: item.enabled,
    authorized_workpoint_ids: item.authorized_workpoint_ids,
    workpoint_overrides: item.workpoint_overrides,
  })), [{
    id: "local-a-x",
    workpoint_id: "WP-A",
    quantity: 2,
    max_quantity: 4,
    enabled: true,
    authorized_workpoint_ids: null,
    workpoint_overrides: [],
  }]);
});

test("catalog projection is deterministic and same-type shared pools remain independent", async () => {
  const {
    resourceCatalogProjection,
    sharedResourcePools,
  } = await loadResources();
  const shared = [
    pool({ id: "pool-b", type: "team-x", label: "二区班组", scope_mode: "PROJECT_SHARED", authorized_workpoint_ids: ["WP-B"] }),
    pool({ id: "pool-a", type: "team-x", label: "一区班组", scope_mode: "PROJECT_SHARED", authorized_workpoint_ids: ["WP-A"] }),
  ];
  const processes = [
    { id: "process-b", name: "工艺乙", component_type: "pier_body", resource_type: "team-y" },
    { id: "process-a", name: "工艺甲", component_type: "cap", resource_type: "team-x" },
  ];

  assert.deepEqual(sharedResourcePools(shared).map((item) => item.id), ["pool-a", "pool-b"]);
  assert.deepEqual(resourceCatalogProjection(processes, shared).map((item) => item.type), ["cap_team", "pier_body_team", "team-x"]);
});

test("canonical workpoint resources derive enabled from quantity while project-shared compatibility stays unchanged", async () => {
  const { normalizeResourcePoolForWorkspace } = await loadResources();

  const zeroLocal = normalizeResourcePoolForWorkspace(pool({
    id: "local-zero",
    scope_mode: "WORKPOINT_EXCLUSIVE",
    workpoint_id: "WP-A",
    quantity: 0,
    max_quantity: 3,
    enabled: true,
  }));
  const positiveLocal = normalizeResourcePoolForWorkspace(pool({
    id: "local-positive",
    scope_mode: "WORKPOINT_EXCLUSIVE",
    workpoint_id: "WP-A",
    quantity: 2.9,
    max_quantity: 1,
    enabled: false,
  }));
  const shared = normalizeResourcePoolForWorkspace(pool({
    id: "shared-disabled",
    scope_mode: "PROJECT_SHARED",
    quantity: 2,
    enabled: false,
  }));

  assert.equal(zeroLocal.enabled, false);
  assert.equal(zeroLocal.max_quantity, 3);
  assert.equal(positiveLocal.quantity, 2);
  assert.equal(positiveLocal.max_quantity, 2);
  assert.equal(positiveLocal.enabled, true);
  assert.equal(shared.enabled, false);
});

test("precast beam production is excluded from workpoint suggestions and the supplemental catalog", async () => {
  const { resourceCatalogProjection, workpointResourceTypeProjection } = await loadResources();
  const processes = [
    ...processLibrary,
    process("precast_beam_standard", "precast_beam", "precast_beam_team"),
    process("beam_erection_standard", "beam_erection", "beam_erection_team"),
  ];
  const catalogTypes = resourceCatalogProjection(processes, [
    pool({ id: "legacy-precast", type: "precast_beam_team", label: "预制梁班组" }),
  ]).map((item) => item.type);
  const suggestionTypes = workpointResourceTypeProjection(
    workpoint([
      structure("simple-span", "simple_span", [component("precast", "precast_beam")]),
      structure("structure-lower", "bridge_pier", [
        component("pile", "pile", { methodId: "rotary_drill" }),
        component("cap", "cap"),
      ]),
    ]),
    processes,
  );

  assert.equal(catalogTypes.includes("precast_beam_team"), false);
  assert.equal(suggestionTypes.includes("precast_beam_team"), false);
  assert.equal(catalogTypes.includes("beam_erection_team"), true);
  assert.equal(catalogTypes.includes("rotary_drill"), true);
  assert.equal(suggestionTypes.includes("rotary_drill"), true);
  assert.equal(suggestionTypes.includes("cap_team"), true);
});

test("workpoint projection selects the actual pile method and defaults only when no method is explicit", async () => {
  const { workpointResourceTypeProjection } = await loadResources();
  const methods = [
    ["rotary_drill", "rotary_drill"],
    ["circulation_drill", "circulation_drill"],
    ["impact_drill", "impact_drill"],
    ["manual_pile", "manual_pile_team"],
  ];

  for (const [methodId, expectedType] of methods) {
    const actual = workpointResourceTypeProjection(
      workpoint([structure("structure-lower", "bridge_pier", [component(`pile-${methodId}`, "pile", { methodId })])]),
      processLibrary,
    );
    assert.deepEqual(actual, [expectedType]);
  }

  assert.deepEqual(
    workpointResourceTypeProjection(
      workpoint([structure("structure-lower", "bridge_pier", [component("pile-default", "pile")])]),
      processLibrary,
    ),
    ["rotary_drill"],
  );
  assert.deepEqual(
    workpointResourceTypeProjection(
      workpoint([structure("structure-lower", "bridge_pier", [component("pile-invalid", "pile", { methodId: "unknown" })])]),
      processLibrary,
    ),
    [],
  );
});

test("workpoint projection maps continuous and ordinary structures, filters disabled components and stays deterministic", async () => {
  const { workpointResourceTypeProjection } = await loadResources();
  const input = workpoint([
    structure("continuous", "continuous_unit"),
    structure("structure-lower", "bridge_pier", [
      component("cap-a", "cap"),
      component("cap-b", "cap"),
      component("pier", "pier_body"),
      component("cap-beam", "cap_beam"),
      component("disabled-pile", "pile", { enabled: false, methodId: "impact_drill" }),
      component("unknown", "unknown_component"),
    ]),
  ]);
  const expected = ["cap_beam_team", "cap_team", "cast_in_place_continuous_beam_team", "pier_body_team"];

  assert.deepEqual(workpointResourceTypeProjection(input, processLibrary), expected);
  assert.deepEqual(workpointResourceTypeProjection({ ...input, structures: [...input.structures].reverse() }, [...processLibrary].reverse()), expected);
  assert.deepEqual(workpointResourceTypeProjection(workpoint([]), processLibrary), []);
});

test("workpoint structure summaries group six lower-structure types by parameters process and unit", async () => {
  const { workpointStructureSummaryProjection } = await loadResources();
  const diameter = parameter("diameter_m", 1.8, { unit: "m" });
  const capDimensions = [
    parameter("length_m", 3, { unit: "m", sortOrder: 1 }),
    parameter("width_m", 4, { unit: "m", sortOrder: 2 }),
    parameter("height_m", 12, { unit: "m", sortOrder: 3 }),
  ];
  const structures = [
    structure("pier-a", "bridge_pier", [
      component("pile-a", "pile", { methodId: "rotary_drill", quantity: 3, unit: "根", parameters: [diameter] }),
      component("cap-a", "cap", { unit: "个", parameters: capDimensions }),
      component("middle", "middle_tie_beam", { unit: "道", parameters: [parameter("length_m", 8, { unit: "m" })] }),
      component("pier", "pier_body", { unit: "个", parameters: [parameter("height_m", 12, { unit: "m" })] }),
      component("ground", "ground_tie_beam", { unit: "道", parameters: [parameter("length_m", 10, { unit: "m" })] }),
      component("cap-beam", "cap_beam", { unit: "个", parameters: [parameter("length_m", 15, { unit: "m" })] }),
      component("disabled", "pile", { enabled: false, methodId: "impact_drill", quantity: 99, unit: "根", parameters: [diameter] }),
      component("zero", "cap", { quantity: 0, unit: "个", parameters: capDimensions }),
      component("other", "precast_beam", { quantity: 8, unit: "片" }),
    ]),
    structure("pier-b", "bridge_pier", [
      component("pile-b", "pile", { methodId: "rotary_drill", quantity: 2, unit: "根", parameters: [diameter] }),
      component("pile-impact", "pile", { methodId: "impact_drill", quantity: 2, unit: "根", parameters: [diameter] }),
      component("cap-b", "cap", { unit: "个", parameters: [...capDimensions].reverse() }),
    ]),
  ];

  const actual = workpointStructureSummaryProjection(workpoint(structures), processLibrary);

  assert.deepEqual(actual.map((group) => group.label), ["桩基", "承台", "柱系梁", "墩身", "桩系梁", "盖梁"]);
  assert.deepEqual(actual.map((group) => group.sortOrder), [1, 2, 3, 4, 5, 6]);
  assert.equal(actual[0].items.length, 2);
  assert.equal(actual[0].items.find((item) => item.processLabel === "旋挖钻")?.quantity, 5);
  assert.equal(actual[0].items.find((item) => item.processLabel === "旋挖钻")?.displayText, "旋挖钻-φ1.8m×5根");
  assert.match(actual[1].items[0].displayText, /3×4×12m×2个$/);
  assert.deepEqual(
    workpointStructureSummaryProjection(workpoint([...structures].reverse()), [...processLibrary].reverse()),
    actual,
  );
});

test("pile summaries aggregate by process diameter and unit while ignoring pile length", async () => {
  const { workpointStructureSummaryProjection } = await loadResources();
  const pileParameters = (diameter, length, unit = "m") => [
    parameter("diameter_m", diameter, { unit }),
    parameter("length_m", length, { unit: "m", sortOrder: 2 }),
    parameter("form", "摩擦桩", { sortOrder: 3 }),
  ];
  const input = workpoint([
    structure("pile-summary", "bridge_pier", [
      component("pile-25", "pile", { methodId: "rotary_drill", quantity: 8, unit: "根", parameters: pileParameters(1.5, 25) }),
      component("pile-30", "pile", { methodId: "rotary_drill", quantity: 7, unit: "根", parameters: pileParameters(1.5, 30) }),
      component("pile-35", "pile", { methodId: "rotary_drill", quantity: 5, unit: "根", parameters: pileParameters(1.5, 35) }),
      component("pile-diameter", "pile", { methodId: "rotary_drill", quantity: 4, unit: "根", parameters: pileParameters(1.8, 25) }),
      component("pile-process", "pile", { methodId: "impact_drill", quantity: 3, unit: "根", parameters: pileParameters(1.5, 25) }),
      component("pile-unit", "pile", { methodId: "rotary_drill", quantity: 2, unit: "根", parameters: pileParameters("150", 25, "cm") }),
      component("pile-disabled", "pile", { enabled: false, methodId: "rotary_drill", quantity: 99, unit: "根", parameters: pileParameters(1.5, 40) }),
      component("pile-zero", "pile", { methodId: "rotary_drill", quantity: 0, unit: "根", parameters: pileParameters(1.5, 45) }),
      component("pile-missing", "pile", { methodId: "rotary_drill", quantity: 2, unit: "根", parameters: [parameter("length_m", 18, { unit: "m" })] }),
    ]),
  ]);

  const pileItems = workpointStructureSummaryProjection(input, processLibrary)[0].items;
  assert.equal(pileItems.find((item) => item.displayText === "旋挖钻-φ1.5m×20根")?.quantity, 20);
  assert.ok(pileItems.some((item) => item.displayText === "旋挖钻-φ1.8m×4根"));
  assert.ok(pileItems.some((item) => item.displayText === "冲击钻-φ1.5m×3根"));
  assert.ok(pileItems.some((item) => item.displayText === "旋挖钻-φ150cm×2根"));
  assert.ok(pileItems.some((item) => item.displayText === "旋挖钻-桩径未提供×2根"));
  assert.ok(pileItems.every((item) => !/25m|30m|35m|40m|45m|摩擦桩/.test(item.displayText)));
  assert.deepEqual(
    workpointStructureSummaryProjection({ ...input, structures: [...input.structures].reverse() }, [...processLibrary].reverse()),
    workpointStructureSummaryProjection(input, processLibrary),
  );
});

test("cap and pier summaries preserve metric dimensions and aggregate piers by section only", async () => {
  const { workpointStructureSummaryProjection } = await loadResources();
  const circular = (height, form) => [
    parameter("diameter_m", 1.5),
    parameter("height_m", height),
    parameter("form", form),
  ];
  const rectangular = (dimensions, height, form) => [
    parameter("dimensions_m", dimensions),
    parameter("height_m", height),
    parameter("form", form),
  ];
  const input = workpoint([
    structure("cap-and-pier", "bridge_pier", [
      component("cap-a", "cap", { quantity: 1, unit: "个", parameters: [parameter("form", "16.5*16.5*6.0")] }),
      component("cap-b", "cap", { quantity: 2, unit: "个", parameters: [parameter("form", "16.5×16.5×6.0")] }),
      component("cap-c", "cap", { quantity: 3, unit: "个", parameters: [parameter("form", "16.5 x 16.5 X 6.0")] }),
      component("pier-circular-inner", "pier_body", { methodId: "climbing_form", quantity: 4, unit: "根", parameters: circular(12.5, "内柱") }),
      component("pier-circular-outer", "pier_body", { methodId: "climbing_form", quantity: 6, unit: "根", parameters: circular(28.75, "外柱") }),
      component("pier-rectangle-left", "pier_body", { methodId: "climbing_form", quantity: 2, unit: "根", parameters: rectangular("2.0*1.5", 18, "左柱") }),
      component("pier-rectangle-right", "pier_body", { methodId: "climbing_form", quantity: 3, unit: "根", parameters: rectangular("2.0 × 1.5", 26, "右柱") }),
      component("pier-rectangle-different", "pier_body", { methodId: "climbing_form", quantity: 1, unit: "根", parameters: rectangular("2.0*1.8", 26, "右柱") }),
      component("pier-variable", "pier_body", { methodId: "climbing_form", quantity: 2, unit: "根", parameters: rectangular("8.0*6.0/4.0", 80, "独墩") }),
      component("pier-variable-first-axis", "pier_body", { methodId: "climbing_form", quantity: 2, unit: "根", parameters: rectangular("9.2/7.0*10.6", 80, "独墩") }),
      component("pier-missing", "pier_body", { methodId: "climbing_form", quantity: 2, unit: "根", parameters: [parameter("height_m", 15), parameter("form", "内柱")] }),
      component("pier-conflict", "pier_body", { methodId: "climbing_form", quantity: 1, unit: "根", parameters: [parameter("diameter_m", 1.8), parameter("dimensions_m", "2.0*1.5")] }),
    ]),
  ]);

  const actual = workpointStructureSummaryProjection(input, processLibrary);
  const capItems = actual.find((group) => group.componentType === "cap").items;
  const pierItems = actual.find((group) => group.componentType === "pier_body").items;
  assert.deepEqual(capItems.map((item) => item.displayText), ["承台施工-16.5×16.5×6.0m×6个"]);
  assert.ok(pierItems.some((item) => item.displayText === "爬模施工-φ1.5m×10根"));
  assert.ok(pierItems.some((item) => item.displayText === "爬模施工-2.0×1.5m×5根"));
  assert.ok(pierItems.some((item) => item.displayText === "爬模施工-2.0×1.8m×1根"));
  assert.ok(pierItems.some((item) => item.displayText === "爬模施工-8.0×6.0/4.0m×2根"));
  assert.ok(pierItems.some((item) => item.displayText === "爬模施工-9.2/7.0×10.6m×2根"));
  assert.ok(pierItems.some((item) => item.displayText === "爬模施工-截面尺寸未提供×2根"));
  assert.ok(pierItems.some((item) => item.displayText === "爬模施工-截面尺寸冲突×1根"));
  assert.ok(pierItems.every((item) => !/12\.5|28\.75|18m|26m|80m|内柱|外柱|左柱|右柱|独墩|m²/.test(item.displayText)));
});

test("workpoint structure summaries keep different units and unknown or missing process information diagnosable", async () => {
  const { workpointStructureSummaryProjection } = await loadResources();
  const input = workpoint([
    structure("unknown-method", "bridge_pier", [
      component("unknown", "pile", { methodId: "unregistered-method", quantity: 2, unit: "根" }),
      component("missing-a", "cap", { quantity: 1, unit: "个", parameters: [parameter("form", "矩形")] }),
      component("missing-b", "cap", { quantity: 3, unit: "座", parameters: [parameter("form", "矩形")] }),
    ]),
  ]);
  const processesWithoutCapDefault = processLibrary.filter((item) => item.component_type !== "cap");
  const actual = workpointStructureSummaryProjection(input, processesWithoutCapDefault);

  assert.match(actual[0].items[0].displayText, /工艺未识别/);
  assert.equal(actual[1].items.length, 2);
  assert.ok(actual[1].items.every((item) => item.processLabel === "工艺未指定"));
  assert.deepEqual(actual[1].items.map((item) => item.unit), ["个", "座"]);
  assert.deepEqual(workpointStructureSummaryProjection(workpoint([]), processLibrary), []);
});

test("resource names prefer configured Chinese labels, cover built-ins and keep unknown types diagnosable", async () => {
  const { resourceTypeLabel } = await loadResources();
  const builtIns = {
    rotary_drill: "旋挖钻机",
    circulation_drill: "回旋钻机",
    impact_drill: "冲击钻机",
    manual_pile_team: "人工挖孔班组",
    cap_team: "承台模板",
    spread_foundation_team: "扩大基础班组",
    tie_beam_team: "系梁班组",
    pier_body_team: "墩柱模板",
    cap_beam_team: "盖梁模板",
    abutment_team: "桥台班组",
    precast_beam_team: "预制梁班组",
    beam_erection_team: "架梁班组",
    cast_in_place_continuous_beam_team: "连续梁班组",
    cast_in_place_box_beam_team: "现浇箱梁班组",
    steel_box_beam_team: "钢箱梁班组",
    bridge_deck_system_team: "桥面系班组",
  };
  for (const [type, expected] of Object.entries(builtIns)) {
    const label = resourceTypeLabel(type, []);
    assert.equal(label, expected);
    assert.match(label, /[\u3400-\u9fff]/u);
  }

  assert.equal(resourceTypeLabel("rotary_drill", [pool({ type: "rotary_drill", label: "一号桥旋挖设备" })]), "一号桥旋挖设备");
  assert.equal(resourceTypeLabel("rotary_drill", [pool({ type: "rotary_drill", label: "rotary_drill" })]), "旋挖钻机");
  assert.equal(resourceTypeLabel("custom-crane", [pool({ type: "custom-crane", label: "自定义吊车" })]), "自定义吊车");
  assert.equal(resourceTypeLabel("custom-crane", [pool({ type: "custom-crane", label: "custom-crane" })]), "未命名资源");
});

test("fingerprint distinguishes workpoint identity but ignores pool ordering", async () => {
  const { resourcePoolsSemanticFingerprint } = await loadResources();
  const localA = pool({ id: "local-a", scope_mode: "WORKPOINT_EXCLUSIVE", workpoint_id: "WP-A" });
  const localB = pool({ id: "local-b", scope_mode: "WORKPOINT_EXCLUSIVE", workpoint_id: "WP-B" });
  assert.equal(
    resourcePoolsSemanticFingerprint([localA, localB]),
    resourcePoolsSemanticFingerprint([localB, localA]),
  );
  assert.notEqual(
    resourcePoolsSemanticFingerprint([localA]),
    resourcePoolsSemanticFingerprint([{ ...localA, workpoint_id: "WP-C" }]),
  );
});

test("bridge resource page keeps the workpoint-local editor and omits shared-pool configuration", () => {
  const fullSource = readFileSync(resolve(root, "src/features/resources/ResourcesTab.tsx"), "utf8");
  // The explicitly separate pavement editor supports shared fleets; bridge behavior stays frozen.
  const source = fullSource.replace(/export function PavementResources[\s\S]*?(?=type AiInitializationState)/, "");
  const styles = readFileSync(resolve(root, "src/features/resources/styles.css"), "utf8");
  assert.match(source, /工点资源配置/);
  assert.match(source, /scope_mode:\s*"WORKPOINT_EXCLUSIVE"/);
  assert.match(source, /workpoint_id:\s*selectedWorkpoint\.workpoint_id/);
  assert.match(source, /getProjectMasterWorkpoint/);
  assert.match(source, /detailRequestId/);
  assert.match(source, /正在加载当前工点结构/);
  assert.match(source, /当前工点结构加载失败/);
  assert.match(source, /当前工点没有匹配到待配置资源/);
  assert.match(source, /当前工点没有可汇总的下部结构信息/);
  assert.match(source, /workpointStructureSummaryProjection/);
  assert.match(source, /className="resource-workpoint-detail-grid"/);
  assert.ok(source.indexOf('<h4 id="resource-structure-heading">结构物信息') < source.indexOf('<h4 id="resource-config-heading">资源配置'));
  assert.match(source, /className="resource-config-list"/);
  assert.doesNotMatch(source, /<code>\{item\.type\}<\/code>/);
  assert.doesNotMatch(source, /<table|<thead|resource-status-toggle|type="checkbox"/);
  assert.match(source, /const maxQuantity = pool \? resourcePoolUsableLimit\(pool\) : 0/);
  assert.match(source, /结构可能使用，尚未配置/);
  assert.match(source, /aria-label=\{`\$\{selectedWorkpoint\.workpoint_name\} \$\{label\} 当前投入`\}/);
  assert.match(source, /aria-label=\{`\$\{selectedWorkpoint\.workpoint_name\} \$\{label\} 可增上限`\}/);
  assert.match(source, /onRemoveResourcePool/);
  assert.match(source, /onApplyAiWorkpointResources/);
  assert.match(source, /addLocalResource\(item, \{ quantity: nextQuantity, max_quantity:/);
  assert.match(source, /onClick=\{\(\) => onRemoveResourcePool\(pool\.id\)\}/);
  assert.match(source, /onClick=\{onSaveLocalConfig\}/);
  assert.doesNotMatch(source, /AI[\s\S]{0,80}onSaveLocalConfig/);
  assert.match(styles, /\.resource-workpoint-detail-grid\s*\{[^}]*grid-template-columns:/s);
  assert.match(styles, /@media \(max-width: 900px\)[\s\S]*\.resource-workpoint-detail-grid\s*\{[^}]*grid-template-columns:\s*1fr/s);
  assert.doesNotMatch(styles, /\.resource-workpoint-table\s*\{[^}]*min-width:\s*900px/s);
  assert.doesNotMatch(source, /generated\?\.schedule_input\.tasks|taskLikelyTypes|applicableProcessIds\.length > 0/);
  assert.doesNotMatch(source, /范围共享资源池|新增共享池|删除共享池|全部工点（动态）/);
  assert.doesNotMatch(source, /该资源适用于哪些工点|获准工点/);
});
