import type { Config, Context } from "@netlify/functions";
import readXlsxFile from "read-excel-file/node";

declare const Netlify: { env: { get(name: string): string | undefined } } | undefined;

type ComponentType =
  | "pile"
  | "cap"
  | "spread_foundation"
  | "ground_tie_beam"
  | "middle_tie_beam"
  | "pier_body"
  | "cap_beam"
  | "abutment_body"
  | "precast_beam"
  | "beam_erection"
  | "cast_in_place_continuous_beam"
  | "cast_in_place_box_beam"
  | "steel_box_beam"
  | "bridge_deck_system";

type ComponentModel = {
  id: string;
  name: string;
  component_type: ComponentType;
  quantity: number;
  quantity_label: string;
  method_id?: string | null;
  productivity_option_id?: string | null;
  enabled: boolean;
  properties: Record<string, unknown>;
};

type ProcessTemplate = {
  id: string;
  component_type: ComponentType;
  process_name: string;
  method_id?: string | null;
  duration_method: string;
  quantity_source: string;
  productivity_value: number;
  productivity_unit: string;
  standard_section_height_m?: number | null;
  resource_type: string;
  productivity_options?: ProductivityOption[];
  applicability: Record<string, unknown>;
  is_default: boolean;
};

type ProductivityOption = {
  id: string;
  name: string;
  duration_method: string;
  quantity_source: string;
  productivity_value: number;
  productivity_unit: string;
  standard_section_height_m?: number | null;
  is_default: boolean;
};

type TaskOverride = {
  method_id?: string | null;
  productivity_option_id?: string | null;
};

type RelationshipType = "FS" | "SS" | "FF" | "SF";

type LogicRule = {
  id: string;
  scope: "same_structure" | "structure_sequence";
  structure_type?: "pier" | "abutment" | "upper_structure" | "continuous_beam" | null;
  to_component: ComponentType;
  predecessor_candidates: ComponentType[];
  predecessor_strategy: "all" | "first_available";
  relationship: RelationshipType;
  lag_days: number;
  severity?: "error" | "warning";
  note: string;
};

type UpperStructureLogicRule = {
  id: string;
  relationship: RelationshipType;
  lag_days: number;
  severity?: "error" | "warning";
  note?: string;
};

type WorkSectionSide = "left" | "right" | "none";

type UpperStructureModel = {
  id: string;
  name: string;
  structure_type: string;
  side: WorkSectionSide;
  span_index: number;
  support_range: string;
  span_length_m: number;
  beam_count_per_span?: number | null;
  span_group_expression: string;
  properties: Record<string, unknown>;
};

type ResourcePool = {
  id: string;
  type: string;
  label: string;
  resource_mode?: "LIMITED" | "UNLIMITED";
  quantity: number | null;
  max_quantity?: number | null;
  calendar_id: string;
  enabled: boolean;
  compatible_process_ids: string[];
};

type MilestoneConstraint = {
  id: string;
  name: string;
  level: "contract" | "control" | "internal";
  mode: "hard" | "soft";
  scope_type: "project" | "bridge" | "work_section" | "structure" | "component";
  scope_id?: string | null;
  target_event: "start" | "finish";
  target_date: string;
  penalty_per_day: number;
};

type ScenarioInput = {
  scenario_id: string;
  scenario_name: string;
  project: {
    project_id: string;
    project_name: string;
    start_date: string;
    bridges: Array<{
      id: string;
      name: string;
      order: number;
      workpoint_type: "bridge";
      import_source: Record<string, unknown>;
      work_sections: Array<{
        id: string;
        name: string;
        order: number;
        side: WorkSectionSide;
        structures: Array<{
          id: string;
          name: string;
          structure_type: "pier" | "abutment" | "upper_structure" | "continuous_beam";
          order: number;
          support_no?: string | null;
          support_index?: number | null;
          components: ComponentModel[];
        }>;
        upper_structures: UpperStructureModel[];
      }>;
    }>;
  };
  process_library: ProcessTemplate[];
  logic_rules: LogicRule[];
  upper_structure_logic_rules?: UpperStructureLogicRule[];
  task_overrides?: Record<string, TaskOverride>;
  resource_calendars: Array<{
    id: string;
    name: string;
    working_weekdays: number[];
    blackout_dates: string[];
  }>;
  resource_pools: ResourcePool[];
  milestones: MilestoneConstraint[];
  time_limit_seconds: number;
};

type BridgeModel = ScenarioInput["project"]["bridges"][number];
type WorkSectionModel = BridgeModel["work_sections"][number];
type StructureModel = WorkSectionModel["structures"][number];

type Task = {
  id: string;
  name: string;
  bridge_id?: string | null;
  work_section_id?: string | null;
  component_id?: string | null;
  sequence_order: number;
  structure_id: string;
  structure_name: string;
  structure_type: string;
  component_type: ComponentType;
  process_name: string;
  productivity_rule_id: string;
  quantity: number;
  quantity_label: string;
  duration_days: number;
  compatible_resource_types: string[];
};

type PrecedenceLink = {
  id: string;
  predecessor_id: string;
  successor_id: string;
  relationship: RelationshipType;
  lag_days: number;
  source_rule_id: string;
  severity?: "error" | "warning";
};

type Resource = {
  id: string;
  name: string;
  type: string;
  pool_id: string;
  pool_label: string;
  enabled: boolean;
  calendar_id: string;
};

type ScheduledTask = Task & {
  start_offset: number;
  end_offset: number;
  start_date: string;
  finish_date: string;
  assigned_resource_id?: string | null;
  assigned_resource_name?: string | null;
  assigned_resource_type?: string | null;
  predecessor_ids: string[];
};

type GeneratedScheduleInput = {
  schedule_input: {
    project_name: string;
    start_date: string;
    tasks: Task[];
    precedence_links: PrecedenceLink[];
    resources: Resource[];
    milestones: MilestoneConstraint[];
    time_limit_seconds: number;
  };
  validation: Array<{ level: "info" | "warning" | "error"; message: string; subject_id?: string | null }>;
  source_summary: Record<string, unknown>;
};

const CONTINUOUS_BEAM_STRUCTURE_CODE = "castInPlaceContinuousBoxGirder";
const CAST_IN_PLACE_BOX_BEAM_STRUCTURE_CODE = "castInPlaceBoxGirder";
const SIMPLE_BEAM_STRUCTURE_CODE = "precastTGirder";
const CONTINUOUS_BEAM_DEFAULT_STANDARD_SEGMENT_CYCLES = 18;
const DEFAULT_RESOURCE_MAX_QUANTITIES: Record<string, number> = {
  rotary_drill: 5,
  circulation_drill: 5,
  impact_drill: 5,
  manual_pile_team: 10,
  cap_team: 5,
  pier_body_team: 5,
  cap_beam_team: 5,
};
const KEY_RESOURCE_COMPONENT_TYPES = new Set<ComponentType>(["pile", "cap", "pier_body", "cap_beam", "cast_in_place_continuous_beam"]);
const DEFAULT_RESOURCE_TYPE_BY_COMPONENT: Partial<Record<ComponentType, string>> = {
  cap: "cap_team",
  pier_body: "pier_body_team",
  cap_beam: "cap_beam_team",
  cast_in_place_continuous_beam: "cast_in_place_continuous_beam_team",
};
const PILE_RESOURCE_TYPE_BY_PROCESS: Record<string, string> = {
  pile_rotary_regular: "rotary_drill",
  pile_circulation: "circulation_drill",
  pile_impact: "impact_drill",
  pile_manual: "manual_pile_team",
};
const PILE_RESOURCE_TYPE_BY_METHOD: Record<string, string> = {
  rotary_drill: "rotary_drill",
  circulation_drill: "circulation_drill",
  impact_drill: "impact_drill",
  manual_pile: "manual_pile_team",
  manual_excavation: "manual_pile_team",
};
const UPPER_STRUCTURE_LOGIC_RULE_IDS = [
  "cast_in_place_box_beam_after_lower_structure",
  "continuous_beam_zero_block_after_main_pier_lower_structure",
  "continuous_beam_side_straight_after_edge_lower_structure",
  "continuous_beam_t_chain",
  "continuous_beam_side_closure",
  "continuous_beam_middle_closure",
  "continuous_beam_edge_before_middle_closure",
  "continuous_beam_middle_closure_sequence",
] as const;

type ProcessIntent = {
  component_type?: ComponentType | null;
  process_method_id?: string | null;
  process_name?: string | null;
  sides?: string[];
  support_nos?: string[];
  component_names?: string[];
  pile_nos?: string[];
  target_role?: string | null;
  action?: string;
};

type ProcessIntentPayload = {
  intents: ProcessIntent[];
  warnings: string[];
};

type WorkbookSheet = {
  sheet: string;
  data: unknown[][];
};

export default async function handler(req: Request, context: Context) {
  try {
    const endpoint = context.params.endpoint;
    if (endpoint === "health" && req.method === "GET") {
      return json({ status: "ok" });
    }
    if ((endpoint === "demo-scenario" || endpoint === "process-library") && req.method === "GET") {
      const scenario = createDefaultScenario();
      return json(endpoint === "process-library" ? scenario.process_library : scenario);
    }
    if (endpoint === "process-library" && req.method === "PUT") {
      const body = await req.json();
      return json(body.process_library ?? []);
    }
    if (endpoint === "import-local-bridge-params" && req.method === "POST") {
      const scenario = await req.json();
      return json(importResult(scenario, [], [{
        id: "local-demo-import",
        message: "Netlify Functions 本地演示导入使用当前默认场景；请选择 Excel 文件可触发真实解析。",
      }]));
    }
    if (endpoint === "import-bridge-params" && req.method === "POST") {
      return await importUploadedBridgeParams(req);
    }
    if (endpoint === "generate-schedule-input" && req.method === "POST") {
      return json(generateScheduleInput(await req.json()));
    }
    if (endpoint === "solve-scenario" && req.method === "POST") {
      return json(solveScenario(await req.json(), false));
    }
    if (endpoint === "solve-min-resources" && req.method === "POST") {
      const body = await req.json();
      return json(solveScenario(body.scenario, true));
    }
    if (endpoint === "compare-scenarios" && req.method === "POST") {
      return json(compareScenarios(await req.json()));
    }
    if (endpoint === "apply-process-natural-language" && req.method === "POST") {
      const body = await req.json();
      return json(await applyProcessNaturalLanguage(body.scenario, String(body.prompt ?? "")));
    }
    return json({ detail: `Unknown API endpoint: /api/${endpoint}` }, 404);
  } catch (error) {
    return json({ detail: error instanceof Error ? error.message : String(error) }, 500);
  }
}

export const config: Config = {
  path: "/api/:endpoint",
};

function json(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

function createDefaultScenario(): ScenarioInput {
  const processLibrary = createProcessLibrary();
  const structures = [
    createAbutment("A0", "0号台", 0, 2, 30, "rotary_drill"),
    ...[1, 2, 3].map((index) => createPier(index, 36, "rotary_drill")),
    ...[4, 5].map((index) => createPier(index, 50, "rotary_drill")),
    ...[6, 7].map((index) => createPier(index, 50, "manual_pile")),
    ...[8, 9, 10, 11, 12].map((index) => createPier(index, 50, "rotary_drill")),
    createAbutment("A13", "13号台", 999, 2, 30, "rotary_drill"),
  ];
  return {
    scenario_id: "default-lower-structure",
    scenario_name: "默认下部结构模拟方案",
    project: {
      project_id: "demo-project",
      project_name: "桥梁下部结构场景化 CP-SAT 自动排程 Demo",
      start_date: "2026-06-01",
      bridges: [{
        id: "B1",
        name: "青洛河1号大桥",
        order: 1,
        workpoint_type: "bridge",
        import_source: {},
        work_sections: [{
          id: "WS-LOWER",
          name: "下部结构一工区",
          order: 1,
          side: "none",
          structures,
          upper_structures: [],
        }],
      }],
    },
    process_library: processLibrary,
    logic_rules: [
      rule("cap_after_piles", null, "cap", ["pile"], "all", 3, "承台在同一墩台全部桩基完成后施工。"),
      rule("pier_body_after_cap", "pier", "pier_body", ["ground_tie_beam", "cap", "pile"], "first_available", 5, "墩柱优先以承台前置。"),
      rule("cap_beam_after_pier_body", "pier", "cap_beam", ["pier_body", "middle_tie_beam"], "all", 3, "盖梁以墩柱、中系梁为前置。"),
      rule("abutment_body_after_cap", "abutment", "abutment_body", ["cap", "pile", "spread_foundation"], "first_available", 5, "桥台台身优先以承台为前置。"),
    ],
    upper_structure_logic_rules: defaultUpperStructureLogicRules(),
    resource_calendars: [{ id: "continuous", name: "连续自然日", working_weekdays: [0, 1, 2, 3, 4, 5, 6], blackout_dates: [] }],
    resource_pools: [
      pool("pool-rotary-drill", "rotary_drill", "旋挖钻", 3, 5),
      pool("pool-circulation-drill", "circulation_drill", "回旋钻", 1, 5),
      pool("pool-impact-drill", "impact_drill", "冲击钻", 1, 5),
      pool("pool-manual-pile", "manual_pile_team", "人工挖孔班组", 1, 10),
      pool("pool-cap", "cap_team", "承台模板", 1, 5),
      pool("pool-pier-body", "pier_body_team", "墩柱模板", 1, 5),
      pool("pool-cap-beam", "cap_beam_team", "盖梁模板", 1, 5),
      pool("pool-cast-in-place-continuous-beam", "cast_in_place_continuous_beam_team", "连续梁班组", 1, 1),
    ],
    milestones: [
      milestone("M-contract-finish", "合同下部结构及上部现浇梁完工", "contract", "hard", "bridge", "B1", "2028-12-31", 10),
      milestone("M-control-ws-lower", "下部结构及上部现浇梁强控节点", "control", "hard", "bridge", "B1", "2028-12-15", 10),
      milestone("M-internal-cap", "承台内部目标", "internal", "soft", "component", "cap", "2027-05-25", 20),
    ],
    time_limit_seconds: 10,
  };
}

function createAbutment(id: string, name: string, order: number, pileCount: number, pileLength: number, methodId: string) {
  const components = pileComponents(id, name, pileCount, pileLength, methodId);
  components.push(component(`${id}-CAP`, `${name}-承台`, "cap", 1, "1个"));
  components.push(component(`${id}-BODY`, `${name}-桥台`, "abutment_body", 1, "5m", null, { height_m: 5 }));
  return { id, name, structure_type: "abutment" as const, order, support_no: null, support_index: null, components };
}

function createPier(index: number, pileLength: number, methodId: string) {
  const id = `P${String(index).padStart(2, "0")}`;
  const name = `${index}号墩`;
  const height = 7 + (index % 4) * 1.5;
  const components = pileComponents(id, name, 2, pileLength, methodId);
  components.push(component(`${id}-CAP`, `${name}-承台`, "cap", 1, "1个"));
  components.push(component(`${id}-BODY`, `${name}-墩柱`, "pier_body", height, `${height}m`, null, { height_m: height }));
  components.push(component(`${id}-BEAM`, `${name}-盖梁`, "cap_beam", 1, "1个"));
  return { id, name, structure_type: "pier" as const, order: index, support_no: null, support_index: null, components };
}

function pileComponents(structureId: string, structureName: string, count: number, length: number, methodId: string) {
  return Array.from({ length: count }, (_, index) => {
    const pileNo = index + 1;
    return component(
      `${structureId}-PILE-${String(pileNo).padStart(2, "0")}`,
      `${structureName}-${pileNo}#桩基`,
      "pile",
      length,
      `直径1.5m，桩长${length}m`,
      methodId,
      { pile_no: pileNo, diameter_m: 1.5, length_m: length },
    );
  });
}

function component(
  id: string,
  name: string,
  componentType: ComponentType,
  quantity: number,
  quantityLabel: string,
  methodId: string | null = null,
  properties: Record<string, unknown> = {},
): ComponentModel {
  return {
    id,
    name,
    component_type: componentType,
    quantity,
    quantity_label: quantityLabel,
    method_id: methodId,
    productivity_option_id: null,
    enabled: true,
    properties,
  };
}

function createProcessLibrary(): ProcessTemplate[] {
  return [
    process("pile_rotary_regular", "pile", "旋挖钻", "rotary_drill", "days_per_unit", "count", 3, "天/根", "rotary_drill", true),
    process("pile_circulation", "pile", "回旋钻", "circulation_drill", "days_per_unit", "count", 2, "天/根", "circulation_drill", false),
    process("pile_impact", "pile", "冲击钻", "impact_drill", "days_per_unit", "count", 2, "天/根", "impact_drill", false),
    process("pile_manual", "pile", "人工挖孔", "manual_pile", "days_per_unit", "pile_length_m", 1, "天/m", "manual_pile_team", false),
    process("ground_tie_beam_standard", "ground_tie_beam", "桩系梁施工", null, "fixed_days", "count", 3, "天/个", "tie_beam_team", true),
    process("cap_standard", "cap", "承台施工", null, "fixed_days", "count", 30, "天/个", "cap_team", true),
    process("spread_foundation_standard", "spread_foundation", "扩大基础施工", null, "fixed_days", "count", 8, "天/个", "spread_foundation_team", true),
    process("pier_body_climbing_form", "pier_body", "爬模施工", "climbing_form", "days_per_unit", "pier_height_m", 7, "天/节", "pier_body_team", true, 4.5),
    process("pier_body_standard", "pier_body", "整体式浇筑", "integral_casting", "fixed_days", "count", 20, "天/个", "pier_body_team", false),
    process("pier_body_sliding_form", "pier_body", "滑模施工", "sliding_form", "days_per_unit", "pier_height_m", 6, "天/节", "pier_body_team", false, 4.5),
    process("pier_body_turnover_form", "pier_body", "翻模施工", "turnover_form", "days_per_unit", "pier_height_m", 12, "天/节", "pier_body_team", false, 4.5),
    process("middle_tie_beam_standard", "middle_tie_beam", "中系梁施工", null, "fixed_days", "count", 4, "天/个", "tie_beam_team", true),
    process("cap_beam_standard", "cap_beam", "盖梁施工", null, "fixed_days", "count", 10, "天/个", "cap_beam_team", true),
    process("abutment_body_standard", "abutment_body", "桥台施工", null, "fixed_days", "count", 15, "天/个", "abutment_team", true),
    process("precast_beam_standard", "precast_beam", "制梁", null, "fixed_days", "count", 35, "天/片", "precast_beam_team", true),
    process("beam_erection_standard", "beam_erection", "架梁", null, "fixed_days", "count", 2, "天/片", "beam_erection_team", true),
    process("cast_in_place_continuous_zero_block", "cast_in_place_continuous_beam", "0号块", "zero_block", "fixed_days", "count", 120, "天/块", "cast_in_place_continuous_beam_team", true),
    process("cast_in_place_continuous_standard_segment", "cast_in_place_continuous_beam", "标准块", "standard_segment", "days_per_unit", "count", 10, "天/块", "cast_in_place_continuous_beam_team", false),
    process("cast_in_place_continuous_closure_segment", "cast_in_place_continuous_beam", "合拢段", "closure_segment", "fixed_days", "count", 30, "天/块", "cast_in_place_continuous_beam_team", false),
    process("cast_in_place_continuous_straight_segment", "cast_in_place_continuous_beam", "直线段", "straight_segment", "fixed_days", "count", 35, "天/块", "cast_in_place_continuous_beam_team", false),
    process("cast_in_place_box_beam_standard", "cast_in_place_box_beam", "现浇箱梁", null, "fixed_days", "count", 45, "天/联", "cast_in_place_box_beam_team", true),
    process("steel_box_beam_standard", "steel_box_beam", "钢箱梁", null, "fixed_days", "count", 30, "天/片", "steel_box_beam_team", true),
    process("bridge_deck_system_standard", "bridge_deck_system", "桥面系", null, "units_per_day", "deck_length_m", 30, "米/天", "bridge_deck_system_team", true),
  ];
}

function process(
  id: string,
  componentType: ComponentType,
  processName: string,
  methodId: string | null,
  durationMethod: string,
  quantitySource: string,
  productivityValue: number,
  productivityUnit: string,
  resourceType: string,
  isDefault: boolean,
  standardSectionHeight: number | null = null,
): ProcessTemplate {
  const option = {
    id: `${id}-default`,
    name: "默认工效",
    duration_method: durationMethod,
    quantity_source: quantitySource,
    productivity_value: productivityValue,
    productivity_unit: productivityUnit,
    standard_section_height_m: standardSectionHeight,
    is_default: true,
  };
  return {
    id,
    component_type: componentType,
    process_name: processName,
    method_id: methodId,
    duration_method: durationMethod,
    quantity_source: quantitySource,
    productivity_value: productivityValue,
    productivity_unit: productivityUnit,
    standard_section_height_m: standardSectionHeight,
    resource_type: resourceType,
    productivity_options: [option],
    applicability: {},
    is_default: isDefault,
  };
}

function rule(
  id: string,
  structureType: "pier" | "abutment" | null,
  toComponent: ComponentType,
  predecessors: ComponentType[],
  strategy: "all" | "first_available",
  lagDays: number,
  note: string,
): LogicRule {
  return {
    id,
    scope: "same_structure",
    structure_type: structureType,
    to_component: toComponent,
    predecessor_candidates: predecessors,
    predecessor_strategy: strategy,
    relationship: "FS",
    lag_days: lagDays,
    severity: "error",
    note,
  };
}

function defaultUpperStructureLogicRules(): UpperStructureLogicRule[] {
  return [
    {
      id: "cast_in_place_box_beam_after_lower_structure",
      relationship: "FS",
      lag_days: 0,
      severity: "error",
      note: "现浇箱梁在对应跨组墩台下部结构完成后开始。",
    },
    {
      id: "continuous_beam_zero_block_after_main_pier_lower_structure",
      relationship: "FS",
      lag_days: 0,
      severity: "error",
      note: "连续梁0号块在对应主墩下部结构完成后开始。",
    },
    {
      id: "continuous_beam_side_straight_after_edge_lower_structure",
      relationship: "FS",
      lag_days: 0,
      severity: "error",
      note: "连续梁边跨连续段在对应边跨墩台下部结构完成后开始。",
    },
    {
      id: "continuous_beam_t_chain",
      relationship: "FS",
      lag_days: 0,
      severity: "error",
      note: "连续梁T构内0号块和标准段按顺序施工。",
    },
    {
      id: "continuous_beam_side_closure",
      relationship: "FS",
      lag_days: 0,
      severity: "error",
      note: "连续梁边跨合龙段在边跨连续段和相邻T构完成后开始。",
    },
    {
      id: "continuous_beam_middle_closure",
      relationship: "FS",
      lag_days: 0,
      severity: "error",
      note: "连续梁中跨合龙段在相邻两个T构完成后开始。",
    },
    {
      id: "continuous_beam_edge_before_middle_closure",
      relationship: "FS",
      lag_days: 0,
      severity: "error",
      note: "连续梁默认边跨合龙先于中跨合龙。",
    },
    {
      id: "continuous_beam_middle_closure_sequence",
      relationship: "FS",
      lag_days: 0,
      severity: "error",
      note: "连续梁中跨合龙按配置顺序推进。",
    },
  ];
}

function upperStructureLogicRulesById(rules: UpperStructureLogicRule[] = []) {
  const merged = new Map<string, UpperStructureLogicRule>();
  for (const rule of defaultUpperStructureLogicRules()) {
    merged.set(rule.id, rule);
  }
  for (const rule of rules) {
    merged.set(rule.id, {
      ...rule,
      relationship: rule.relationship ?? "FS",
      lag_days: rule.lag_days ?? 0,
      severity: rule.severity ?? "error",
    });
  }
  return merged;
}

function upperStructureLogicRule(
  rules: Map<string, UpperStructureLogicRule> | undefined,
  ruleId: string,
): UpperStructureLogicRule {
  return rules?.get(ruleId) ?? {
    id: ruleId,
    relationship: "FS",
    lag_days: 0,
    severity: "error",
  };
}

function pool(id: string, type: string, label: string, quantity: number, maxQuantity: number): ResourcePool {
  return {
    id,
    type,
    label,
    resource_mode: "LIMITED",
    quantity,
    max_quantity: maxQuantity,
    calendar_id: "continuous",
    enabled: true,
    compatible_process_ids: [],
  };
}

function milestone(
  id: string,
  name: string,
  level: "contract" | "control" | "internal",
  mode: "hard" | "soft",
  scopeType: MilestoneConstraint["scope_type"],
  scopeId: string,
  targetDate: string,
  penaltyPerDay: number,
): MilestoneConstraint {
  return {
    id,
    name,
    level,
    mode,
    scope_type: scopeType,
    scope_id: scopeId,
    target_event: "finish",
    target_date: targetDate,
    penalty_per_day: penaltyPerDay,
  };
}

function importResult(
  scenario: ScenarioInput,
  qualityChecks: Array<Record<string, unknown>> = [],
  warnings: Array<Record<string, unknown>> = [],
  canonicalBridge: Record<string, unknown> = {},
) {
  const componentCount = scenario.project.bridges.flatMap((bridge) =>
    bridge.work_sections.flatMap((section) => section.structures.flatMap((structure) => structure.components)),
  ).length;
  return {
    scenario,
    canonical_bridge: canonicalBridge,
    summary: {
      bridgeName: scenario.project.bridges[0]?.name ?? scenario.project.project_name,
      carriagewayCount: 1,
      supportCount: scenario.project.bridges[0]?.work_sections[0]?.structures.length ?? 0,
      componentCount,
      lowerComponentCount: componentCount,
      upperComponentCount: 0,
      spanExpression: "演示数据",
    },
    quality_checks: qualityChecks,
    warnings,
  };
}

async function importUploadedBridgeParams(req: Request) {
  const form = await req.formData();
  const uploaded = form.get("file");
  const scenarioText = String(form.get("scenario") ?? "");
  const targetBridge = String(form.get("target_bridge") ?? form.get("targetBridge") ?? "").trim();
  if (!uploaded || typeof uploaded === "string" || typeof uploaded.arrayBuffer !== "function") {
    return json({ detail: "multipart 字段 file 不能为空，请选择 .xlsx/.xlsm 文件。" }, 400);
  }
  if (!scenarioText) {
    return json({ detail: "multipart 字段 scenario 不能为空。" }, 400);
  }

  const scenario = JSON.parse(scenarioText) as ScenarioInput;
  const fileName = uploaded.name || "uploaded.xlsx";
  if (!/\.(xlsx|xlsm)$/i.test(fileName)) {
    return json({ detail: "暂只支持 .xlsx/.xlsm Excel 文件。" }, 415);
  }

  const workbookSheets = await readXlsxFile(Buffer.from(await uploaded.arrayBuffer())) as WorkbookSheet[];
  const sheetNames = workbookSheets.map((sheet) => sheet.sheet);
  const parsed = parseWorkbook(workbookSheets, fileName, targetBridge);
  if (!parsed.structures.length) {
    return json(importResult(scenario, [], [{
      id: "excel-structure-not-found",
      message: "已读取 Excel，但未识别到包含墩台号、桩长、墩高等桥梁参数的行，当前方案未被覆盖。",
      details: { fileName, sheetNames },
    }], parsed.canonical));
  }

  const nextScenario = structuredClone(scenario);
  const bridgeName = targetBridge || parsed.bridgeName || stripExtension(fileName);
  nextScenario.project.project_name = scenario.project.project_name || bridgeName;
  nextScenario.project.bridges = [{
    id: "B1",
    name: bridgeName,
    order: 1,
    workpoint_type: "bridge",
    import_source: {
      fileName,
      parsedAt: new Date().toISOString(),
      source: "netlify-functions-xlsx",
    },
    work_sections: [{
      id: "WS-IMPORT",
      name: "Excel导入工区",
      order: 1,
      side: "none",
      structures: parsed.structures,
      upper_structures: [],
    }],
  }];
  applyResourceMaxQuantityDefaults(nextScenario);

  return json(importResult(nextScenario, [{
    id: "excel-import-ok",
    level: "info",
    message: `已从 ${fileName} 识别 ${parsed.structures.length} 个墩台结构。`,
  }], parsed.warnings, {
    schemaVersion: "netlify-functions-bridge-import/v1",
    source: { fileName, targetBridge, sheetNames },
    bridge: { name: bridgeName },
    structures: parsed.structures,
    sheets: parsed.sheetSummaries,
  }));
}

function parseWorkbook(workbookSheets: WorkbookSheet[], fileName: string, targetBridge: string) {
  const structuresById = new Map<string, ScenarioInput["project"]["bridges"][number]["work_sections"][number]["structures"][number]>();
  const warnings: Array<Record<string, unknown>> = [];
  const sheetSummaries: Array<Record<string, unknown>> = [];
  let detectedBridgeName = targetBridge || "";

  for (const sheet of workbookSheets) {
    const sheetName = sheet.sheet;
    const rows = sheet.data;
    const headerIndex = findHeaderIndex(rows);
    const headers = rows[headerIndex]?.map((cell) => normalizeText(String(cell))) ?? [];
    let parsedRows = 0;

    for (let rowIndex = headerIndex + 1; rowIndex < rows.length; rowIndex += 1) {
      const row = rows[rowIndex] ?? [];
      const joined = normalizeText(row.map((cell) => String(cell ?? "")).join(" "));
      if (!joined) continue;
      const rowMap = mapRow(headers, row);
      const support = extractSupport(rowMap, joined);
      if (!support) {
        const bridge = extractBridgeName(rowMap, joined);
        if (bridge && !detectedBridgeName) detectedBridgeName = bridge;
        continue;
      }
      const pileLength = extractNumber(rowMap, joined, ["桩长", "桩基长", "桩长m", "pilelength"]);
      const pileDiameter = extractNumber(rowMap, joined, ["桩径", "直径", "桩基直径", "diameter"]) ?? 1.5;
      const pileCount = Math.max(0, Math.round(extractNumber(rowMap, joined, ["桩数", "根数", "桩基根数", "数量"]) ?? (pileLength ? 2 : 0)));
      const bodyHeight = extractNumber(rowMap, joined, ["墩高", "柱高", "台高", "高度", "height"]) ?? (support.type === "pier" ? 8 : 5);
      const hasCap = includesAny(rowMap, joined, ["承台"]) || Boolean(pileLength);
      const hasCapBeam = support.type === "pier" && !includesAny(rowMap, joined, ["无盖梁", "不设盖梁"]);
      const components = [
        ...pileComponents(support.id, support.name, pileCount, pileLength ?? 30, "rotary_drill").map((item) => ({
          ...item,
          properties: { ...item.properties, diameter_m: pileDiameter, source_trace: { sheet: sheetName, row: rowIndex + 1 } },
        })),
      ];
      if (hasCap) {
        components.push(component(`${support.id}-CAP`, `${support.name}-承台`, "cap", 1, "1个", null, { source_trace: { sheet: sheetName, row: rowIndex + 1 } }));
      }
      components.push(component(
        `${support.id}-BODY`,
        `${support.name}-${support.type === "pier" ? "墩柱" : "桥台"}`,
        support.type === "pier" ? "pier_body" : "abutment_body",
        support.type === "pier" ? bodyHeight : 1,
        support.type === "pier" ? `${bodyHeight}m` : `${bodyHeight}m`,
        null,
        { height_m: bodyHeight, source_trace: { sheet: sheetName, row: rowIndex + 1 } },
      ));
      if (hasCapBeam) {
        components.push(component(`${support.id}-BEAM`, `${support.name}-盖梁`, "cap_beam", 1, "1个", null, { source_trace: { sheet: sheetName, row: rowIndex + 1 } }));
      }

      structuresById.set(support.id, {
        id: support.id,
        name: support.name,
        structure_type: support.type,
        order: support.order,
        support_no: support.name,
        support_index: support.order,
        components,
      });
      parsedRows += 1;
    }
    if (parsedRows > 0) {
      sheetSummaries.push({ name: sheetName, parsedRows, headerRow: headerIndex + 1 });
    }
  }

  const structures = Array.from(structuresById.values()).sort((left, right) => left.order - right.order);
  if (!structures.length) {
    warnings.push({
      id: "no-structure-row",
      message: "未找到可识别的墩台参数行。请确认表格包含“墩台号/墩号/台号”和“桩长/墩高”等列。",
    });
  }

  return {
    bridgeName: detectedBridgeName || stripExtension(fileName),
    structures,
    warnings,
    sheetSummaries,
    canonical: {
      schemaVersion: "netlify-functions-workbook-facts/v1",
      source: { fileName, targetBridge },
      sheetSummaries,
    },
  };
}

function findHeaderIndex(rows: unknown[][]) {
  const limit = Math.min(rows.length, 30);
  let bestIndex = 0;
  let bestScore = -1;
  for (let index = 0; index < limit; index += 1) {
    const text = normalizeText((rows[index] ?? []).join(" "));
    const score = ["墩", "台", "桩长", "桩径", "墩高", "柱高", "承台", "盖梁", "编号", "数量"]
      .reduce((sum, keyword) => sum + (text.includes(keyword) ? 1 : 0), 0);
    if (score > bestScore) {
      bestIndex = index;
      bestScore = score;
    }
  }
  return bestIndex;
}

function mapRow(headers: string[], row: unknown[]) {
  const map = new Map<string, string>();
  row.forEach((cell, index) => {
    const header = headers[index] || `column_${index + 1}`;
    const value = normalizeText(String(cell ?? ""));
    if (value) map.set(header, value);
  });
  return map;
}

function extractSupport(rowMap: Map<string, string>, joined: string) {
  const explicit = valueForHeaders(rowMap, ["墩台号", "墩号", "台号", "墩台", "支座", "编号", "孔跨"]);
  const text = explicit || joined;
  const match = text.match(/(?:^|[^\d])(\d{1,3})\s*(?:#|号)?\s*(墩|台)/) ?? text.match(/\b([AP])\s*0*(\d{1,3})\b/i);
  if (!match) return null;
  const isAlpha = /^[AP]$/i.test(match[1]);
  const order = Number(isAlpha ? match[2] : match[1]);
  const type = (isAlpha ? match[1].toUpperCase() === "P" : match[2] === "墩") ? "pier" : "abutment";
  const id = type === "pier" ? `P${String(order).padStart(2, "0")}` : `A${order}`;
  const name = `${order}号${type === "pier" ? "墩" : "台"}`;
  return { id, name, type: type as "pier" | "abutment", order: type === "pier" ? order : (order === 0 ? 0 : 900 + order) };
}

function extractBridgeName(rowMap: Map<string, string>, joined: string) {
  const explicit = valueForHeaders(rowMap, ["桥名", "桥梁名称", "工程名称"]);
  if (explicit) return explicit;
  const match = joined.match(/([\u4e00-\u9fa5A-Za-z0-9]+(?:大桥|特大桥|中桥|桥))/);
  return match?.[1] ?? "";
}

function extractNumber(rowMap: Map<string, string>, joined: string, labels: string[]) {
  const headerValue = valueForHeaders(rowMap, labels);
  const fromHeader = numberFromText(headerValue);
  if (fromHeader !== null) return fromHeader;
  for (const label of labels) {
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = joined.match(new RegExp(`${escaped}[^\\d.-]{0,12}(-?\\d+(?:\\.\\d+)?)`, "i"));
    if (match) return Number(match[1]);
  }
  return null;
}

function valueForHeaders(rowMap: Map<string, string>, labels: string[]) {
  for (const [header, value] of rowMap.entries()) {
    const normalizedHeader = normalizeText(header).toLowerCase();
    if (labels.some((label) => normalizedHeader.includes(normalizeText(label).toLowerCase()))) {
      return value;
    }
  }
  return "";
}

function numberFromText(text: string) {
  const match = text.match(/-?\d+(?:\.\d+)?/);
  return match ? Number(match[0]) : null;
}

function includesAny(rowMap: Map<string, string>, joined: string, keywords: string[]) {
  const text = `${joined} ${Array.from(rowMap.keys()).join(" ")}`;
  return keywords.some((keyword) => text.includes(keyword));
}

function stripExtension(fileName: string) {
  return fileName.replace(/\.[^.]+$/, "");
}

function applyResourceMaxQuantityDefaults(scenario: ScenarioInput) {
  const continuousTCount = continuousBeamTStructureCount(scenario);
  scenario.resource_pools = scenario.resource_pools.map((item) => ({
    ...item,
    max_quantity: (item.resource_mode ?? "LIMITED") === "UNLIMITED"
      ? item.max_quantity ?? item.quantity ?? null
      : Math.max(
        item.quantity ?? 0,
        item.type === "cast_in_place_continuous_beam_team"
          ? continuousTCount
          : DEFAULT_RESOURCE_MAX_QUANTITIES[item.type] ?? item.max_quantity ?? item.quantity ?? 0,
      ),
  }));
}

function continuousBeamTStructureCount(scenario: ScenarioInput) {
  let count = 0;
  for (const bridge of scenario.project.bridges) {
    for (const section of bridge.work_sections) {
      for (const group of continuousBeamGroups(section.upper_structures ?? [])) {
        const spanIndices = [...new Set(group.map((upper) => upper.span_index))].sort((a, b) => a - b);
        count += continuousMainSupports(group, spanIndices).length;
      }
    }
  }
  return count;
}

function applyRequiredResourceTypes(
  tasks: Task[],
  resourcePools: ResourcePool[],
  validation: GeneratedScheduleInput["validation"],
): Task[] {
  const poolsByType = new Map(resourcePools.map((poolModel) => [poolModel.type, poolModel]));
  const warningKeys = new Set<string>();
  return tasks.map((task) => ({
    ...task,
    compatible_resource_types: requiredResourceTypesForTask(task, poolsByType, validation, warningKeys),
  }));
}

function requiredResourceTypesForTask(
  task: Task,
  poolsByType: Map<string, ResourcePool>,
  validation: GeneratedScheduleInput["validation"],
  warningKeys: Set<string>,
): string[] {
  const resourceType = defaultResourceTypeForTask(task);
  if (!resourceType) return [];
  const poolModel = poolsByType.get(resourceType);
  if (isLimitedPoolAvailable(poolModel)) return [resourceType];
  if (KEY_RESOURCE_COMPONENT_TYPES.has(task.component_type)) {
    appendUnboundedResourceWarning(resourceType, poolModel, validation, warningKeys);
    return [];
  }
  if (poolModel && (poolModel.resource_mode ?? "LIMITED") === "LIMITED") {
    appendUnboundedResourceWarning(resourceType, poolModel, validation, warningKeys);
  }
  return [];
}

function defaultResourceTypeForTask(task: Task): string | null {
  const fallback = task.compatible_resource_types[0] ?? null;
  const processId = task.productivity_rule_id.split(":")[0];
  const methodId = methodIdFromProcessId(processId);
  if (task.component_type === "pile") {
    return PILE_RESOURCE_TYPE_BY_PROCESS[processId] ?? (methodId ? PILE_RESOURCE_TYPE_BY_METHOD[methodId] : null) ?? fallback;
  }
  return DEFAULT_RESOURCE_TYPE_BY_COMPONENT[task.component_type] ?? fallback;
}

function methodIdFromProcessId(processId: string): string | null {
  return Object.keys(PILE_RESOURCE_TYPE_BY_METHOD).find((methodId) => processId.includes(methodId)) ?? null;
}

function isLimitedPoolAvailable(poolModel: ResourcePool | undefined): boolean {
  return Boolean(
    poolModel
      && poolModel.enabled
      && (poolModel.resource_mode ?? "LIMITED") === "LIMITED"
      && (poolModel.quantity ?? 0) > 0,
  );
}

function appendUnboundedResourceWarning(
  resourceType: string,
  poolModel: ResourcePool | undefined,
  validation: GeneratedScheduleInput["validation"],
  warningKeys: Set<string>,
) {
  const reason = resourceUnboundedReason(poolModel);
  const key = `${resourceType}:${reason}`;
  if (warningKeys.has(key)) return;
  warningKeys.add(key);
  validation.push({
    level: "warning",
    subject_id: poolModel?.id ?? resourceType,
    message: `资源“${poolModel?.label ?? resourceType}”${reason}，相关工作项按资源默认充足处理，不产生资源等待。`,
  });
}

function resourceUnboundedReason(poolModel: ResourcePool | undefined): string {
  if (!poolModel) return "未配置";
  if (!poolModel.enabled) return "未启用";
  if ((poolModel.resource_mode ?? "LIMITED") === "UNLIMITED") return "设置为默认充足";
  if ((poolModel.quantity ?? 0) <= 0) return "限制数量为 0";
  return "不可用";
}

function generateScheduleInput(scenario: ScenarioInput, useMaxResources = false): GeneratedScheduleInput {
  const built = buildTasks(scenario);
  const resourceWarnings: GeneratedScheduleInput["validation"] = [];
  const tasks = applyRequiredResourceTypes(built.tasks, scenario.resource_pools, resourceWarnings);
  const precedenceLinks = [
    ...buildPrecedenceLinks(tasks, scenario.logic_rules),
    ...built.generatedLinks,
  ];
  const resources = expandResources(scenario.resource_pools, useMaxResources);
  return {
    schedule_input: {
      project_name: scenario.project.project_name,
      start_date: scenario.project.start_date,
      tasks,
      precedence_links: precedenceLinks,
      resources,
      milestones: scenario.milestones,
      time_limit_seconds: scenario.time_limit_seconds,
    },
    validation: [
      ...resourceWarnings,
      ...(resources.length ? [] : [{ level: "info" as const, message: "未生成受限命名资源，当前场景将按资源默认充足排程。" }]),
      {
        level: "info",
        message: `Netlify Functions 已生成 ${tasks.length} 个工作项、${precedenceLinks.length} 条工艺逻辑关系、${resources.length} 个受限命名资源。`,
      },
    ],
    source_summary: {
      bridge_count: scenario.project.bridges.length,
      process_count: scenario.process_library.length,
      resource_pool_count: scenario.resource_pools.length,
      milestone_count: scenario.milestones.length,
      continuous_beam_task_count: tasks.filter((task) => task.structure_type === "continuous_beam").length,
    },
  };
}

function buildTasks(scenario: ScenarioInput): { tasks: Task[]; generatedLinks: PrecedenceLink[] } {
  const tasks: Task[] = [];
  const generatedLinks: PrecedenceLink[] = [];
  const upperLogicRules = upperStructureLogicRulesById(scenario.upper_structure_logic_rules);
  const taskOverrides = scenario.task_overrides ?? {};
  for (const bridge of [...scenario.project.bridges].sort((a, b) => a.order - b.order)) {
    for (const section of [...bridge.work_sections].sort((a, b) => a.order - b.order)) {
      const sectionLowerStart = tasks.length;
      for (const structure of [...section.structures].sort((a, b) => a.order - b.order)) {
        structure.components.forEach((item, index) => {
          if (!item.enabled) return;
          const selected = selectProcess(item, scenario.process_library);
          if (!selected) return;
          const effectiveProcess = effectiveProcessForComponent(selected, item);
          const quantity = quantityForProcess(item, effectiveProcess.quantity_source);
          tasks.push({
            id: item.id,
            name: item.name,
            bridge_id: bridge.id,
            work_section_id: section.id,
            component_id: item.id,
            sequence_order: structure.order * 100 + index,
            structure_id: structure.id,
            structure_name: structure.name,
            structure_type: structure.structure_type,
            component_type: item.component_type,
            process_name: effectiveProcess.process_name,
            productivity_rule_id: effectiveProcess.id,
            quantity,
            quantity_label: item.quantity_label,
            duration_days: calculateDuration(quantity, effectiveProcess),
            compatible_resource_types: [effectiveProcess.resource_type],
          });
        });
      }
      const sectionLowerTasks = tasks.slice(sectionLowerStart);
      const upper = buildUpperStructureTasks(
        bridge.id,
        section,
        scenario.process_library,
        sectionLowerTasks,
        generatedLinks.length + 1,
        upperLogicRules,
        taskOverrides,
      );
      tasks.push(...upper.tasks);
      generatedLinks.push(...upper.links);
    }
  }
  return { tasks, generatedLinks };
}

function buildUpperStructureTasks(
  bridgeId: string,
  section: WorkSectionModel,
  processLibrary: ProcessTemplate[],
  lowerTasks: Task[],
  linkStart: number,
  upperLogicRules: Map<string, UpperStructureLogicRule>,
  taskOverrides: Record<string, TaskOverride>,
): { tasks: Task[]; links: PrecedenceLink[] } {
  const supportCompletions = lowerCompletionTasksBySupport(section, lowerTasks);
  const tasks: Task[] = [];
  const links: PrecedenceLink[] = [];

  // 本期简支梁只保留为结构参数，不生成架梁排程任务。

  const box = buildCastInPlaceBoxBeamTasks(
    bridgeId,
    section,
    processLibrary,
    supportCompletions,
    linkStart + links.length,
    upperLogicRules,
    taskOverrides,
  );
  tasks.push(...box.tasks);
  links.push(...box.links);

  const continuous = buildContinuousBeamTasks(
    bridgeId,
    section,
    processLibrary,
    supportCompletions,
    linkStart + links.length,
    upperLogicRules,
    taskOverrides,
  );
  tasks.push(...continuous.tasks);
  links.push(...continuous.links);

  return { tasks, links };
}

function buildSimpleBeamErectionTasks(
  bridgeId: string,
  section: WorkSectionModel,
  processLibrary: ProcessTemplate[],
  supportCompletions: Map<string, Task[]>,
): { tasks: Task[]; links: PrecedenceLink[] } {
  const tasks: Task[] = [];
  const links: PrecedenceLink[] = [];
  const sideCode = sideCodeFor(section.side);
  const sideLabel = sideLabelFor(section.side);

  for (const upper of [...(section.upper_structures ?? [])].sort((a, b) => a.span_index - b.span_index)) {
    if (!isSimpleBeamUpper(upper)) continue;
    const task = appendUpperTask(tasks, {
      componentId: `${upper.id}-ERECTION`,
      name: `${sideLabel}第${upper.span_index}跨简支梁架梁`,
      componentType: "beam_erection",
      quantity: Number(upper.beam_count_per_span ?? 1) || 1,
      quantityLabel: upper.beam_count_per_span ? `${upper.beam_count_per_span}片` : "1跨",
      bridgeId,
      workSectionId: section.id,
      sequenceOrder: 90000 + upper.span_index,
      structureId: `${bridgeId}-${sideCode}-SPAN-${String(upper.span_index).padStart(2, "0")}-ERECTION`,
      structureName: `${sideLabel}第${upper.span_index}跨简支梁架梁`,
      processLibrary,
      properties: {
        upper_structure_id: upper.id,
        support_range: upper.support_range,
        span_index: upper.span_index,
      },
    });
    links.push(...buildLowerToUpperLinks({
      successor: task,
      supportRefs: supportRefsFromUpper(upper),
      supportCompletions,
      sourceRuleId: "simple_beam_after_lower_structure",
      linkPrefix: `LUB-${bridgeId}-${section.id}-S${String(upper.span_index).padStart(2, "0")}`,
    }));
  }

  return { tasks, links };
}

function buildCastInPlaceBoxBeamTasks(
  bridgeId: string,
  section: WorkSectionModel,
  processLibrary: ProcessTemplate[],
  supportCompletions: Map<string, Task[]>,
  linkStart: number,
  upperLogicRules: Map<string, UpperStructureLogicRule>,
  taskOverrides: Record<string, TaskOverride>,
): { tasks: Task[]; links: PrecedenceLink[] } {
  const tasks: Task[] = [];
  const links: PrecedenceLink[] = [];
  const sideCode = sideCodeFor(section.side);
  const sideLabel = sideLabelFor(section.side);
  let linkNo = linkStart;

  for (const uppers of castInPlaceBoxBeamGroups(section.upper_structures ?? [])) {
    const groupIndex = upperGroupIndex(uppers[0]);
    const spanIndices = uppers.map((upper) => upper.span_index);
    const task = appendUpperTask(tasks, {
      componentId: `${bridgeId}-${sideCode}-BOX-G${String(groupIndex).padStart(2, "0")}-CAST`,
      name: `${sideLabel}第${groupIndex}联现浇箱梁`,
      componentType: "cast_in_place_box_beam",
      quantity: 1,
      quantityLabel: "1联",
      bridgeId,
      workSectionId: section.id,
      sequenceOrder: 95000 + groupIndex,
      structureId: `${bridgeId}-${sideCode}-BOX-G${String(groupIndex).padStart(2, "0")}`,
      structureName: `${sideLabel}第${groupIndex}联现浇箱梁`,
      processLibrary,
      taskOverrides,
      properties: {
        upper_structure_ids: uppers.map((upper) => upper.id),
        span_start_index: Math.min(...spanIndices),
        span_end_index: Math.max(...spanIndices),
      },
    });
    const nextLinks = buildLowerToUpperLinks({
      successor: task,
      supportRefs: supportRefsForUpperGroup(uppers),
      supportCompletions,
      sourceRuleId: "cast_in_place_box_beam_after_lower_structure",
      linkPrefix: `LUB-${bridgeId}-${section.id}-BOX-G${String(groupIndex).padStart(2, "0")}`,
      startIndex: linkNo,
      upperLogicRules,
    });
    links.push(...nextLinks);
    linkNo += nextLinks.length;
  }

  return { tasks, links };
}

function appendUpperTask(
  tasks: Task[],
  input: {
    componentId: string;
    name: string;
    componentType: ComponentType;
    quantity: number;
    quantityLabel: string;
    bridgeId: string;
    workSectionId: string;
    sequenceOrder: number;
    structureId: string;
    structureName: string;
    processLibrary: ProcessTemplate[];
    taskOverrides?: Record<string, TaskOverride>;
    properties?: Record<string, unknown>;
    methodId?: string | null;
    structureType?: string;
  },
) {
  const component = applyTaskOverride({
    id: input.componentId,
    name: input.name,
    component_type: input.componentType,
    quantity: input.quantity,
    quantity_label: input.quantityLabel,
    method_id: input.methodId ?? null,
    productivity_option_id: null,
    enabled: true,
    properties: input.properties ?? {},
  }, input.taskOverrides);
  const selected = selectProcess(component, input.processLibrary);
  if (!selected) return null;
  const effectiveProcess = effectiveProcessForComponent(selected, component);
  const quantity = quantityForProcess(component, effectiveProcess.quantity_source);
  const task: Task = {
    id: component.id,
    name: component.name,
    bridge_id: input.bridgeId,
    work_section_id: input.workSectionId,
    component_id: component.id,
    sequence_order: input.sequenceOrder,
    structure_id: input.structureId,
    structure_name: input.structureName,
    structure_type: input.structureType ?? "upper_structure",
    component_type: component.component_type,
    process_name: effectiveProcess.process_name,
    productivity_rule_id: effectiveProcess.id,
    quantity,
    quantity_label: component.quantity_label,
    duration_days: calculateDuration(quantity, effectiveProcess),
    compatible_resource_types: [effectiveProcess.resource_type],
  };
  tasks.push(task);
  return task;
}

function buildLowerToUpperLinks(input: {
  successor: Task | null;
  supportRefs: string[];
  supportCompletions: Map<string, Task[]>;
  sourceRuleId: string;
  linkPrefix: string;
  startIndex?: number;
  upperLogicRules?: Map<string, UpperStructureLogicRule>;
}) {
  if (!input.successor) return [];
  const links: PrecedenceLink[] = [];
  const seenRefs = new Set<string>();
  let linkNo = input.startIndex ?? 1;
  const rule = upperStructureLogicRule(input.upperLogicRules, input.sourceRuleId);

  for (const supportRef of input.supportRefs) {
    const normalizedRef = normalizeSupportLabel(supportRef);
    if (!normalizedRef || seenRefs.has(normalizedRef)) continue;
    seenRefs.add(normalizedRef);
    const predecessors = input.supportCompletions.get(normalizedRef) ?? [];
    for (const predecessor of predecessors) {
      links.push({
        id: `${input.linkPrefix}-${String(linkNo).padStart(4, "0")}`,
        predecessor_id: predecessor.id,
        successor_id: input.successor.id,
        relationship: rule.relationship,
        lag_days: rule.lag_days,
        source_rule_id: input.sourceRuleId,
        severity: rule.severity ?? "error",
      });
      linkNo += 1;
    }
  }
  return links;
}

function lowerCompletionTasksBySupport(section: WorkSectionModel, lowerTasks: Task[]) {
  const tasksByStructure = groupBy(lowerTasks, (task) => task.structure_id);
  const result = new Map<string, Task[]>();

  for (const structure of section.structures) {
    const completionTasks = selectLowerCompletionTasks(structure, tasksByStructure.get(structure.id) ?? []);
    if (!completionTasks.length) continue;
    for (const key of supportKeysForStructure(structure)) {
      result.set(key, completionTasks);
    }
  }
  return result;
}

function selectLowerCompletionTasks(structure: StructureModel, tasks: Task[]) {
  const priorities: Record<string, ComponentType[]> = {
    pier: ["cap_beam", "middle_tie_beam", "pier_body", "cap", "ground_tie_beam", "spread_foundation", "pile"],
    abutment: ["abutment_body", "cap", "spread_foundation", "pile"],
  };
  for (const componentType of priorities[structure.structure_type] ?? []) {
    const matches = tasks.filter((task) => task.component_type === componentType);
    if (matches.length) return matches;
  }
  return tasks;
}

function supportKeysForStructure(structure: StructureModel) {
  const keys = new Set<string>();
  for (const value of [structure.support_no, structure.name]) {
    const normalized = normalizeSupportLabel(value);
    if (normalized) keys.add(normalized);
  }
  if (structure.support_index !== undefined && structure.support_index !== null) {
    const label = structure.structure_type === "pier" ? "墩" : "台";
    keys.add(`${structure.support_index}#${label}`);
  }
  return keys;
}

function supportRefsFromUpper(upper: UpperStructureModel) {
  const refs = parseSupportRefs(upper.support_range);
  if (refs.length) return refs;
  const leftIndex = upper.span_index - 1;
  return [supportLabelFromIndex(leftIndex, true), `${upper.span_index}#墩`];
}

function supportRefsForUpperGroup(uppers: UpperStructureModel[]) {
  const refs = uppers
    .sort((a, b) => a.span_index - b.span_index)
    .flatMap((upper) => supportRefsFromUpper(upper));
  return dedupeSupportRefs(refs);
}

function edgeSupportRefs(uppers: UpperStructureModel[], edge: "left" | "right") {
  const ordered = [...uppers].sort((a, b) => a.span_index - b.span_index);
  if (!ordered.length) return [];
  const edgeUpper = edge === "left" ? ordered[0] : ordered[ordered.length - 1];
  const refs = parseSupportRefs(edgeUpper.support_range);
  if (refs.length) return [edge === "left" ? refs[0] : refs[refs.length - 1]];
  if (edge === "left") return [supportLabelFromIndex(edgeUpper.span_index - 1, true)];
  return [`${edgeUpper.span_index}#墩`];
}

function parseSupportRefs(supportRange: string) {
  const refs: string[] = [];
  for (const match of supportRange.matchAll(/(\d+)\s*(?:#|号)?\s*(墩|台)/g)) {
    refs.push(`${Number(match[1])}#${match[2]}`);
  }
  return dedupeSupportRefs(refs);
}

function dedupeSupportRefs(refs: string[]) {
  const deduped: string[] = [];
  const seen = new Set<string>();
  for (const ref of refs) {
    const normalized = normalizeSupportLabel(ref);
    if (normalized && !seen.has(normalized)) {
      deduped.push(normalized);
      seen.add(normalized);
    }
  }
  return deduped;
}

function normalizeSupportLabel(value: unknown) {
  if (value === undefined || value === null) return null;
  const text = String(value).trim().replace(/\s+/g, "").replace(/号/g, "#");
  const match = text.match(/(\d+)\s*#?\s*(墩|台)/);
  return match ? `${Number(match[1])}#${match[2]}` : text || null;
}

function supportLabelFromIndex(index: number, isLeftEdge = false) {
  if (index === 0 && isLeftEdge) return "0#台";
  return `${index}#墩`;
}

function castInPlaceBoxBeamGroups(upperStructures: UpperStructureModel[]) {
  const groups = new Map<number, UpperStructureModel[]>();
  for (const upper of upperStructures) {
    if (!isCastInPlaceBoxBeamUpper(upper)) continue;
    const groupIndex = upperGroupIndex(upper);
    groups.set(groupIndex, [...(groups.get(groupIndex) ?? []), upper]);
  }
  return [...groups.values()]
    .map((items) => items.sort((a, b) => a.span_index - b.span_index))
    .sort((a, b) => Math.min(...a.map((item) => item.span_index)) - Math.min(...b.map((item) => item.span_index)));
}

function isSimpleBeamUpper(upper: UpperStructureModel) {
  if (upper.properties.structure_code === SIMPLE_BEAM_STRUCTURE_CODE) return true;
  if (isContinuousBeamUpper(upper) || isCastInPlaceBoxBeamUpper(upper)) return false;
  return upper.structure_type.includes("简支") || upper.structure_type.includes("T梁");
}

function isCastInPlaceBoxBeamUpper(upper: UpperStructureModel) {
  if (upper.properties.structure_code === CAST_IN_PLACE_BOX_BEAM_STRUCTURE_CODE) return true;
  return upper.structure_type.includes("现浇")
    && upper.structure_type.includes("箱梁")
    && !isContinuousBeamUpper(upper);
}

function upperGroupIndex(upper: UpperStructureModel) {
  const value = Number(upper.properties.group_index ?? upper.span_index);
  return Number.isFinite(value) ? Math.trunc(value) : upper.span_index;
}

function buildContinuousBeamTasks(
  bridgeId: string,
  section: WorkSectionModel,
  processLibrary: ProcessTemplate[],
  supportCompletions: Map<string, Task[]>,
  linkStart: number,
  upperLogicRules: Map<string, UpperStructureLogicRule>,
  taskOverrides: Record<string, TaskOverride>,
): { tasks: Task[]; links: PrecedenceLink[] } {
  const tasks: Task[] = [];
  const links: PrecedenceLink[] = [];
  let linkNo = linkStart;

  const addLink = (predecessor: Task | null, successor: Task | null, sourceRuleId: string) => {
    if (!predecessor || !successor) return;
    const rule = upperStructureLogicRule(upperLogicRules, sourceRuleId);
    links.push({
      id: `LCB-${bridgeId}-${section.id}-${String(linkNo).padStart(4, "0")}`,
      predecessor_id: predecessor.id,
      successor_id: successor.id,
      relationship: rule.relationship,
      lag_days: rule.lag_days,
      source_rule_id: sourceRuleId,
      severity: rule.severity ?? "error",
    });
    linkNo += 1;
  };

  for (const uppers of continuousBeamGroups(section.upper_structures ?? [])) {
    const groupIndex = continuousGroupIndex(uppers[0]);
    const spanIndices = [...new Set(uppers.map((upper) => upper.span_index))].sort((a, b) => a - b);
    const mainSupports = continuousMainSupports(uppers, spanIndices);
    if (!mainSupports.length) continue;

    const standardCycles = continuousIntSetting(
      uppers,
      ["standard_segment_cycles", "standard_block_cycles", "standard_blocks_per_side"],
      CONTINUOUS_BEAM_DEFAULT_STANDARD_SEGMENT_CYCLES,
      0,
    );
    const sideCode = sideCodeFor(section.side);
    const sideLabel = sideLabelFor(section.side);
    const prefix = `${bridgeId}-${sideCode}-CB-G${String(groupIndex).padStart(2, "0")}`;
    const groupLabel = sideLabel ? `${sideLabel}连续梁` : "连续梁";
    const baseOrder = 100000 + groupIndex * 10000;
    const tCompletionTasks: Array<Task | null> = [];

    mainSupports.forEach((supportIndex, supportOffset) => {
      const tIndex = supportOffset + 1;
      const structureId = `${prefix}-T${String(tIndex).padStart(2, "0")}-P${String(supportIndex).padStart(2, "0")}`;
      const structureName = `${groupLabel}${supportIndex}#墩T构`;
      let previous = appendContinuousTask(tasks, {
        componentId: `${structureId}-ZERO`,
        name: `${structureName}-0号块`,
        methodId: "zero_block",
        quantityLabel: "1块",
        bridgeId,
        workSectionId: section.id,
        sequenceOrder: baseOrder + tIndex * 1000,
        structureId,
        structureName,
        processLibrary,
        taskOverrides,
      });
      const zeroBlockLinks = buildLowerToUpperLinks({
        successor: previous,
        supportRefs: [`${supportIndex}#墩`],
        supportCompletions,
        sourceRuleId: "continuous_beam_zero_block_after_main_pier_lower_structure",
        linkPrefix: `LUB-${bridgeId}-${section.id}-CB-G${String(groupIndex).padStart(2, "0")}-T${String(tIndex).padStart(2, "0")}`,
        startIndex: linkNo,
        upperLogicRules,
      });
      links.push(...zeroBlockLinks);
      linkNo += zeroBlockLinks.length;
      if (standardCycles > 0) {
        const current = appendContinuousTask(tasks, {
          componentId: `${structureId}-STD`,
          name: `${structureName}-标准段${standardCycles}块`,
          methodId: "standard_segment",
          quantity: standardCycles,
          quantityLabel: `${standardCycles}块`,
          bridgeId,
          workSectionId: section.id,
          sequenceOrder: baseOrder + tIndex * 1000 + 1,
          structureId,
          structureName,
          processLibrary,
          taskOverrides,
        });
        addLink(previous, current, "continuous_beam_t_chain");
        if (current) previous = current;
      }
      tCompletionTasks.push(previous);
    });

    const leftEdgeStructureName = `${groupLabel}${mainSupports[0]}#墩T构`;
    const rightEdgeStructureName = `${groupLabel}${mainSupports[mainSupports.length - 1]}#墩T构`;

    const leftStraight = appendContinuousTask(tasks, {
      componentId: `${prefix}-LEFT-STRAIGHT`,
      name: `${leftEdgeStructureName}-边跨连续段`,
      methodId: "straight_segment",
      quantityLabel: "1段",
      bridgeId,
      workSectionId: section.id,
      sequenceOrder: baseOrder + 9000,
      structureId: `${prefix}-LEFT-P${String(mainSupports[0]).padStart(2, "0")}`,
      structureName: leftEdgeStructureName,
      processLibrary,
      taskOverrides,
    });
    const leftClosure = appendContinuousTask(tasks, {
      componentId: `${prefix}-LEFT-CLOSURE`,
      name: `${leftEdgeStructureName}-边跨合龙段`,
      methodId: "closure_segment",
      quantityLabel: "1段",
      bridgeId,
      workSectionId: section.id,
      sequenceOrder: baseOrder + 9100,
      structureId: `${prefix}-LEFT-P${String(mainSupports[0]).padStart(2, "0")}`,
      structureName: leftEdgeStructureName,
      processLibrary,
      taskOverrides,
    });
    const rightStraight = appendContinuousTask(tasks, {
      componentId: `${prefix}-RIGHT-STRAIGHT`,
      name: `${rightEdgeStructureName}-边跨连续段`,
      methodId: "straight_segment",
      quantityLabel: "1段",
      bridgeId,
      workSectionId: section.id,
      sequenceOrder: baseOrder + 9200,
      structureId: `${prefix}-RIGHT-P${String(mainSupports[mainSupports.length - 1]).padStart(2, "0")}`,
      structureName: rightEdgeStructureName,
      processLibrary,
      taskOverrides,
    });
    const rightClosure = appendContinuousTask(tasks, {
      componentId: `${prefix}-RIGHT-CLOSURE`,
      name: `${rightEdgeStructureName}-边跨合龙段`,
      methodId: "closure_segment",
      quantityLabel: "1段",
      bridgeId,
      workSectionId: section.id,
      sequenceOrder: baseOrder + 9300,
      structureId: `${prefix}-RIGHT-P${String(mainSupports[mainSupports.length - 1]).padStart(2, "0")}`,
      structureName: rightEdgeStructureName,
      processLibrary,
      taskOverrides,
    });
    addLink(leftStraight, leftClosure, "continuous_beam_side_closure");
    const leftStraightLinks = buildLowerToUpperLinks({
      successor: leftStraight,
      supportRefs: edgeSupportRefs(uppers, "left"),
      supportCompletions,
      sourceRuleId: "continuous_beam_side_straight_after_edge_lower_structure",
      linkPrefix: `LUB-${bridgeId}-${section.id}-CB-G${String(groupIndex).padStart(2, "0")}-LEFT`,
      startIndex: linkNo,
      upperLogicRules,
    });
    links.push(...leftStraightLinks);
    linkNo += leftStraightLinks.length;
    addLink(tCompletionTasks[0], leftClosure, "continuous_beam_side_closure");
    addLink(rightStraight, rightClosure, "continuous_beam_side_closure");
    const rightStraightLinks = buildLowerToUpperLinks({
      successor: rightStraight,
      supportRefs: edgeSupportRefs(uppers, "right"),
      supportCompletions,
      sourceRuleId: "continuous_beam_side_straight_after_edge_lower_structure",
      linkPrefix: `LUB-${bridgeId}-${section.id}-CB-G${String(groupIndex).padStart(2, "0")}-RIGHT`,
      startIndex: linkNo,
      upperLogicRules,
    });
    links.push(...rightStraightLinks);
    linkNo += rightStraightLinks.length;
    addLink(tCompletionTasks[tCompletionTasks.length - 1], rightClosure, "continuous_beam_side_closure");

    const midClosures: Array<Task | null> = [];
    for (let index = 0; index < mainSupports.length - 1; index += 1) {
      const closureIndex = index + 1;
      const leftSupport = mainSupports[index];
      const rightSupport = mainSupports[index + 1];
      const midClosure = appendContinuousTask(tasks, {
        componentId: `${prefix}-MID-${String(closureIndex).padStart(2, "0")}-CLOSURE`,
        name: `${groupLabel}${leftSupport}#墩-${rightSupport}#墩-中跨合龙${closureIndex}`,
        methodId: "closure_segment",
        quantityLabel: "1段",
        bridgeId,
        workSectionId: section.id,
        sequenceOrder: baseOrder + 9400 + closureIndex,
        structureId: `${prefix}-MID-${String(closureIndex).padStart(2, "0")}-P${String(leftSupport).padStart(2, "0")}-P${String(rightSupport).padStart(2, "0")}`,
        structureName: `${groupLabel}${leftSupport}#墩-${rightSupport}#墩中跨`,
        processLibrary,
        taskOverrides,
      });
      addLink(tCompletionTasks[index], midClosure, "continuous_beam_middle_closure");
      addLink(tCompletionTasks[index + 1], midClosure, "continuous_beam_middle_closure");
      addLink(leftClosure, midClosure, "continuous_beam_edge_before_middle_closure");
      addLink(rightClosure, midClosure, "continuous_beam_edge_before_middle_closure");
      midClosures.push(midClosure);
    }

    const levels = middleClosureLevels(uppers, midClosures.length);
    levels.slice(1).forEach((currentLevel, levelIndex) => {
      const previousLevel = levels[levelIndex];
      for (const predecessorIndex of previousLevel) {
        for (const successorIndex of currentLevel) {
          addLink(
            midClosures[predecessorIndex - 1],
            midClosures[successorIndex - 1],
            "continuous_beam_middle_closure_sequence",
          );
        }
      }
    });
  }

  return { tasks, links };
}

function appendContinuousTask(
  tasks: Task[],
  input: {
    componentId: string;
    name: string;
    methodId: string;
    quantity?: number;
    quantityLabel: string;
    bridgeId: string;
    workSectionId: string;
    sequenceOrder: number;
    structureId: string;
    structureName: string;
    processLibrary: ProcessTemplate[];
    taskOverrides?: Record<string, TaskOverride>;
  },
) {
  const component = applyTaskOverride({
    id: input.componentId,
    name: input.name,
    component_type: "cast_in_place_continuous_beam",
    quantity: input.quantity ?? 1,
    quantity_label: input.quantityLabel,
    method_id: input.methodId,
    productivity_option_id: null,
    enabled: true,
    properties: {},
  }, input.taskOverrides);
  const selected = selectProcess(component, input.processLibrary);
  if (!selected) return null;
  const effectiveProcess = effectiveProcessForComponent(selected, component);
  const quantity = quantityForProcess(component, effectiveProcess.quantity_source);
  const task: Task = {
    id: component.id,
    name: component.name,
    bridge_id: input.bridgeId,
    work_section_id: input.workSectionId,
    component_id: component.id,
    sequence_order: input.sequenceOrder,
    structure_id: input.structureId,
    structure_name: input.structureName,
    structure_type: "continuous_beam",
    component_type: component.component_type,
    process_name: effectiveProcess.process_name,
    productivity_rule_id: effectiveProcess.id,
    quantity,
    quantity_label: component.quantity_label,
    duration_days: calculateDuration(quantity, effectiveProcess),
    compatible_resource_types: [effectiveProcess.resource_type],
  };
  tasks.push(task);
  return task;
}

function continuousBeamGroups(upperStructures: UpperStructureModel[]) {
  const groups = new Map<number, UpperStructureModel[]>();
  for (const upper of upperStructures) {
    if (!isContinuousBeamUpper(upper)) continue;
    const groupIndex = continuousGroupIndex(upper);
    groups.set(groupIndex, [...(groups.get(groupIndex) ?? []), upper]);
  }
  return [...groups.values()]
    .map((items) => items.sort((a, b) => a.span_index - b.span_index))
    .sort((a, b) => Math.min(...a.map((item) => item.span_index)) - Math.min(...b.map((item) => item.span_index)));
}

function isContinuousBeamUpper(upper: UpperStructureModel) {
  return upper.properties.structure_code === CONTINUOUS_BEAM_STRUCTURE_CODE
    || upper.structure_type.includes("连续")
    || upper.structure_type.includes("刚构");
}

function continuousGroupIndex(upper: UpperStructureModel) {
  return Number(upper.properties.group_index ?? upper.span_index);
}

function continuousMainSupports(uppers: UpperStructureModel[], spanIndices: number[]) {
  const configured = continuousListSetting(uppers, ["main_support_indices", "main_pier_indices"]);
  if (configured.length) return [...new Set(configured)].sort((a, b) => a - b);
  if (spanIndices.length < 2) return [];
  const result: number[] = [];
  for (let support = Math.min(...spanIndices); support < Math.max(...spanIndices); support += 1) {
    result.push(support);
  }
  return result;
}

function middleClosureLevels(uppers: UpperStructureModel[], middleCount: number) {
  if (middleCount <= 1) return Array.from({ length: middleCount }, (_, index) => [index + 1]);
  const configured = continuousNestedListSetting(uppers, ["middle_closure_sequence", "mid_span_closure_sequence"]);
  if (configured.length) return validMiddleClosureLevels(configured, middleCount);
  const strategy = String(continuousSetting(uppers, ["middle_closure_order", "mid_span_closure_order", "closure_order"]) ?? "side_to_center");
  if (strategy === "left_to_right" || strategy === "one_side_to_other") {
    return Array.from({ length: middleCount }, (_, index) => [index + 1]);
  }
  if (strategy === "right_to_left") {
    return Array.from({ length: middleCount }, (_, index) => [middleCount - index]);
  }
  const levels: number[][] = [];
  let left = 1;
  let right = middleCount;
  while (left <= right) {
    levels.push(left === right ? [left] : [left, right]);
    left += 1;
    right -= 1;
  }
  return levels;
}

function validMiddleClosureLevels(levels: number[][], middleCount: number) {
  const seen = new Set<number>();
  const valid = levels
    .map((level) => level.filter((index) => index >= 1 && index <= middleCount && !seen.has(index) && (seen.add(index) || true)))
    .filter((level) => level.length);
  for (let index = 1; index <= middleCount; index += 1) {
    if (!seen.has(index)) valid.push([index]);
  }
  return valid;
}

function continuousIntSetting(uppers: UpperStructureModel[], keys: string[], defaultValue: number, minimum: number) {
  const value = Number(continuousSetting(uppers, keys));
  return Number.isFinite(value) ? Math.max(minimum, Math.trunc(value)) : defaultValue;
}

function continuousListSetting(uppers: UpperStructureModel[], keys: string[]) {
  const value = continuousSetting(uppers, keys);
  if (!Array.isArray(value)) return [];
  return value.map((item) => Number(item)).filter((item) => Number.isFinite(item));
}

function continuousNestedListSetting(uppers: UpperStructureModel[], keys: string[]) {
  const value = continuousSetting(uppers, keys);
  if (!Array.isArray(value)) return [];
  if (value.every((item) => !Array.isArray(item))) {
    return continuousListSettingFromValue(value).map((item) => [item]);
  }
  return value
    .filter((item): item is unknown[] => Array.isArray(item))
    .map((item) => continuousListSettingFromValue(item))
    .filter((item) => item.length);
}

function continuousListSettingFromValue(value: unknown[]) {
  return value.map((item) => Number(item)).filter((item) => Number.isFinite(item));
}

function continuousSetting(uppers: UpperStructureModel[], keys: string[]) {
  for (const upper of uppers) {
    const nested = upper.properties.continuous_beam;
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      const record = nested as Record<string, unknown>;
      for (const key of keys) {
        if (record[key] !== undefined && record[key] !== null) return record[key];
      }
    }
    for (const key of keys) {
      if (upper.properties[key] !== undefined && upper.properties[key] !== null) return upper.properties[key];
    }
  }
  return null;
}

function sideCodeFor(side: WorkSectionSide) {
  return ({ left: "L", right: "R", none: "N" } as const)[side] ?? "N";
}

function sideLabelFor(side: WorkSectionSide) {
  return ({ left: "左幅", right: "右幅", none: "" } as const)[side] ?? "";
}

function applyTaskOverride(component: ComponentModel, taskOverrides?: Record<string, TaskOverride>): ComponentModel {
  const override = taskOverrides?.[component.id];
  if (!override) return component;
  return {
    ...component,
    method_id: override.method_id ?? component.method_id,
    productivity_option_id: override.productivity_option_id ?? component.productivity_option_id,
  };
}

function selectProcess(componentModel: ComponentModel, processLibrary: ProcessTemplate[]) {
  const options = processLibrary.filter((item) => item.component_type === componentModel.component_type);
  if (componentModel.method_id) {
    return options.find((item) => item.id === componentModel.method_id || item.method_id === componentModel.method_id) ?? null;
  }
  return options.find((item) => item.is_default) ?? options[0] ?? null;
}

function effectiveProcessForComponent(processTemplate: ProcessTemplate, componentModel: ComponentModel): ProcessTemplate {
  const selectedOption = selectedProductivityOption(componentModel, processTemplate);
  const processWithOption = selectedOption
    ? {
      ...processTemplate,
      id: `${processTemplate.id}:${selectedOption.id}`,
      duration_method: selectedOption.duration_method,
      quantity_source: selectedOption.quantity_source,
      productivity_value: selectedOption.productivity_value,
      productivity_unit: selectedOption.productivity_unit,
      standard_section_height_m: selectedOption.standard_section_height_m ?? processTemplate.standard_section_height_m,
    }
    : processTemplate;
  if (componentModel.component_type === "cast_in_place_continuous_beam" && componentModel.method_id === "standard_segment") {
    return {
      ...processWithOption,
      duration_method: "days_per_unit",
      quantity_source: "count",
    };
  }
  return processWithOption;
}

function selectedProductivityOption(componentModel: ComponentModel, processTemplate: ProcessTemplate): ProductivityOption | null {
  const options = processTemplate.productivity_options ?? [];
  if (!options.length) return null;
  if (componentModel.productivity_option_id) {
    const selected = options.find((option) => option.id === componentModel.productivity_option_id);
    if (selected) return selected;
  }
  return options.find((option) => option.is_default) ?? options[0] ?? null;
}

function quantityForProcess(componentModel: ComponentModel, quantitySource: string) {
  if (quantitySource === "count") {
    if (componentModel.component_type === "cast_in_place_continuous_beam" && componentModel.method_id === "standard_segment") {
      return componentModel.quantity;
    }
    return 1;
  }
  if (quantitySource === "pile_length_m") return Number(componentModel.properties.length_m ?? componentModel.quantity);
  if (quantitySource === "pier_height_m") return Number(componentModel.properties.height_m ?? componentModel.quantity);
  if (quantitySource === "deck_length_m") {
    return Number(componentModel.properties.length_m ?? componentModel.properties.total_length_m ?? componentModel.quantity);
  }
  return componentModel.quantity;
}

function calculateDuration(quantity: number, processTemplate: ProcessTemplate) {
  if (
    processTemplate.component_type === "cast_in_place_continuous_beam"
    && processTemplate.id.startsWith("cast_in_place_continuous_standard_segment")
  ) {
    return Math.max(1, Math.ceil(quantity * processTemplate.productivity_value));
  }
  if (
    processTemplate.component_type === "pier_body"
    && processTemplate.quantity_source === "pier_height_m"
    && processTemplate.productivity_unit === "天/节"
    && processTemplate.standard_section_height_m
  ) {
    const sectionCount = Math.max(1, Math.ceil(quantity / processTemplate.standard_section_height_m));
    return Math.max(1, Math.ceil(sectionCount * processTemplate.productivity_value));
  }
  if (processTemplate.duration_method === "units_per_day") {
    return Math.max(1, Math.ceil(quantity / processTemplate.productivity_value));
  }
  if (processTemplate.duration_method === "days_per_unit") {
    return Math.max(1, Math.ceil(quantity * processTemplate.productivity_value));
  }
  return Math.max(1, Math.ceil(processTemplate.productivity_value));
}

function buildPrecedenceLinks(tasks: Task[], logicRules: LogicRule[]) {
  const links: PrecedenceLink[] = [];
  let counter = 1;
  const byStructure = groupBy(tasks, (task) => task.structure_id);
  for (const structureTasks of byStructure.values()) {
    const structureType = structureTasks[0]?.structure_type;
    for (const logicRule of logicRules) {
      if (logicRule.scope !== "same_structure") continue;
      if (logicRule.structure_type && logicRule.structure_type !== structureType) continue;
      const successors = structureTasks.filter((task) => task.component_type === logicRule.to_component);
      if (!successors.length) continue;
      const predecessors = selectPredecessors(structureTasks, logicRule);
      for (const successor of successors) {
        for (const predecessor of predecessors) {
          if (predecessor.id === successor.id) continue;
          links.push({
            id: `L${String(counter).padStart(4, "0")}`,
            predecessor_id: predecessor.id,
            successor_id: successor.id,
            relationship: logicRule.relationship,
            lag_days: logicRule.lag_days,
            source_rule_id: logicRule.id,
            severity: logicRule.severity,
          });
          counter += 1;
        }
      }
    }
  }
  return links;
}

function selectPredecessors(tasks: Task[], logicRule: LogicRule) {
  if (logicRule.predecessor_strategy === "all") {
    return tasks.filter((task) => logicRule.predecessor_candidates.includes(task.component_type));
  }
  for (const componentType of logicRule.predecessor_candidates) {
    const matches = tasks.filter((task) => task.component_type === componentType);
    if (matches.length) return matches;
  }
  return [];
}

function expandResources(pools: ResourcePool[], useMaxResources: boolean): Resource[] {
  return pools.flatMap((poolModel) => {
    if (!poolModel.enabled || (poolModel.resource_mode ?? "LIMITED") === "UNLIMITED") return [];
    const count = useMaxResources ? (poolModel.max_quantity ?? poolModel.quantity ?? 0) : (poolModel.quantity ?? 0);
    return Array.from({ length: count }, (_, index) => ({
      id: `${poolModel.type}_${index + 1}`,
      name: `${poolModel.label}${index + 1}`,
      type: poolModel.type,
      pool_id: poolModel.id,
      pool_label: poolModel.label,
      enabled: true,
      calendar_id: poolModel.calendar_id,
    }));
  });
}

function solveScenario(scenario: ScenarioInput, useMaxResources: boolean) {
  const generated = generateScheduleInput(scenario, useMaxResources);
  const result = schedule(generated);
  const diagnostics = [
    ...generated.validation,
    { level: "info", message: "Netlify Functions 演示排程已完成。完整 CP-SAT 求解仍建议部署 FastAPI/OR-Tools 后端。" },
  ];
  return {
    scenario_id: scenario.scenario_id,
    scenario_name: scenario.scenario_name,
    generated,
    result,
    milestone_results: result.milestone_results,
    diagnostics,
    metrics: {
      task_count: generated.schedule_input.tasks.length,
      logic_link_count: generated.schedule_input.precedence_links.length,
      resource_count: generated.schedule_input.resources.length,
      resource_types: Array.from(new Set(generated.schedule_input.resources.map((resource) => resource.type))).sort(),
      total_days: result.objective_days,
      soft_late_count: result.milestone_results.filter((item) => item.mode === "soft" && item.lateness_days > 0).length,
      soft_penalty: result.milestone_results.reduce((sum, item) => sum + item.penalty, 0),
      hard_milestones_met: result.milestone_results.filter((item) => item.mode === "hard" && item.status === "met").length,
      hard_milestone_count: result.milestone_results.filter((item) => item.mode === "hard").length,
    },
  };
}

function earliestStartFromPrecedenceLink(link: PrecedenceLink, predecessor: ScheduledTask, successor: Task) {
  if (link.relationship === "SS") {
    return predecessor.start_offset + link.lag_days;
  }
  if (link.relationship === "FF") {
    return predecessor.end_offset + link.lag_days - successor.duration_days;
  }
  if (link.relationship === "SF") {
    return predecessor.start_offset + link.lag_days - successor.duration_days;
  }
  return predecessor.end_offset + link.lag_days;
}

function schedule(generated: GeneratedScheduleInput) {
  const input = generated.schedule_input;
  const predecessorLinks = groupBy(input.precedence_links, (link) => link.successor_id);
  const taskById = new Map(input.tasks.map((task) => [task.id, task]));
  const resourcesByType = groupBy(input.resources, (resource) => resource.type);
  const resourceAvailable = new Map(input.resources.map((resource) => [resource.id, 0]));
  const scheduledById = new Map<string, ScheduledTask>();
  const remaining = [...input.tasks].sort((a, b) => a.sequence_order - b.sequence_order || a.id.localeCompare(b.id));
  let guard = 0;

  while (remaining.length && guard < input.tasks.length * input.tasks.length) {
    guard += 1;
    const index = remaining.findIndex((task) =>
      (predecessorLinks.get(task.id) ?? []).every((link) => scheduledById.has(link.predecessor_id) || !taskById.has(link.predecessor_id)),
    );
    const task = remaining.splice(index >= 0 ? index : 0, 1)[0];
    const links = predecessorLinks.get(task.id) ?? [];
    const readyAt = Math.max(0, ...links.map((link) => {
      const predecessor = scheduledById.get(link.predecessor_id);
      if (!predecessor) return 0;
      return earliestStartFromPrecedenceLink(link, predecessor, task);
    }));
    const candidates = task.compatible_resource_types.flatMap((type) => resourcesByType.get(type) ?? []);
    const assigned = candidates.reduce<Resource | null>((best, current) => {
      if (!best) return current;
      return (resourceAvailable.get(current.id) ?? 0) < (resourceAvailable.get(best.id) ?? 0) ? current : best;
    }, null);
    const resourceReady = assigned ? resourceAvailable.get(assigned.id) ?? 0 : 0;
    const start = Math.max(readyAt, resourceReady);
    const end = start + task.duration_days;
    if (assigned) resourceAvailable.set(assigned.id, end);
    scheduledById.set(task.id, {
      ...task,
      start_offset: start,
      end_offset: end,
      start_date: addDays(input.start_date, start),
      finish_date: addDays(input.start_date, end),
      assigned_resource_id: assigned?.id ?? null,
      assigned_resource_name: assigned?.name ?? null,
      assigned_resource_type: assigned?.type ?? null,
      predecessor_ids: links.map((link) => link.predecessor_id).filter((id) => scheduledById.has(id)),
    });
  }

  const tasks = Array.from(scheduledById.values()).sort((a, b) => a.start_offset - b.start_offset || a.id.localeCompare(b.id));
  const makespan = tasks.reduce((max, task) => Math.max(max, task.end_offset), 0);
  return {
    status: "FEASIBLE",
    objective_days: makespan,
    plan_start_date: input.start_date,
    plan_finish_date: addDays(input.start_date, makespan),
    tasks,
    resource_allocations: tasks
      .filter((task) => task.assigned_resource_id)
      .map((task) => ({
        resource_id: task.assigned_resource_id,
        resource_name: task.assigned_resource_name,
        resource_type: task.assigned_resource_type,
        task_id: task.id,
        task_name: task.name,
        start_offset: task.start_offset,
        end_offset: task.end_offset,
        start_date: task.start_date,
        finish_date: task.finish_date,
      })),
    milestone_results: milestoneResults(input.milestones, tasks, input.start_date),
    validation: [],
    stats: {
      solve_mode: "netlify_functions_demo_scheduler",
      continuity_metrics: {
        continuity_score: 100,
        same_structure_craft_split_count: 0,
        jump_pier_count: 0,
        max_jump_distance: 0,
        side_switch_count: 0,
        cross_side_jump_count: 0,
        direction_reversal_count: 0,
        same_structure_craft_split_details: [],
        jump_transition_details: [],
        resource_paths: [],
      },
    },
    objective_breakdown: {
      solve_mode: "netlify_functions_demo_scheduler",
    },
  };
}

function milestoneResults(milestones: MilestoneConstraint[], tasks: ScheduledTask[], startDate: string) {
  return milestones.map((item) => {
    const scopedTasks = tasksForMilestone(item, tasks);
    if (!scopedTasks.length) {
      return { ...item, actual_date: null, actual_offset: null, lateness_days: 0, penalty: 0, status: "not_evaluated" };
    }
    const actualOffset = item.target_event === "start"
      ? Math.min(...scopedTasks.map((task) => task.start_offset))
      : Math.max(...scopedTasks.map((task) => task.end_offset));
    const targetOffset = daysBetween(startDate, item.target_date);
    const lateness = Math.max(0, actualOffset - targetOffset);
    return {
      ...item,
      actual_date: addDays(startDate, actualOffset),
      actual_offset: actualOffset,
      lateness_days: lateness,
      penalty: item.mode === "soft" ? lateness * item.penalty_per_day : 0,
      status: lateness > 0 ? "late" : "met",
    };
  });
}

function isLowerOrCastInPlaceBeamTask(task: Task) {
  return ["pier", "abutment"].includes(task.structure_type)
    || task.component_type === "cast_in_place_continuous_beam"
    || task.component_type === "cast_in_place_box_beam";
}

function tasksForMilestone(milestoneModel: MilestoneConstraint, tasks: ScheduledTask[]) {
  if (milestoneModel.scope_type === "component" && milestoneModel.scope_id) {
    return tasks.filter((task) => task.component_type === milestoneModel.scope_id || task.component_id === milestoneModel.scope_id);
  }
  if (milestoneModel.scope_type === "structure" && milestoneModel.scope_id) {
    return tasks.filter((task) => task.structure_id === milestoneModel.scope_id);
  }
  if (milestoneModel.scope_type === "work_section" && milestoneModel.scope_id) {
    return tasks.filter((task) => task.work_section_id === milestoneModel.scope_id && isLowerOrCastInPlaceBeamTask(task));
  }
  if (milestoneModel.scope_type === "bridge" && milestoneModel.scope_id) {
    return tasks.filter((task) => task.bridge_id === milestoneModel.scope_id && isLowerOrCastInPlaceBeamTask(task));
  }
  return tasks.filter(isLowerOrCastInPlaceBeamTask);
}

async function applyProcessNaturalLanguage(scenario: ScenarioInput, prompt: string) {
  const nextScenario = structuredClone(scenario);
  const intentPayload = await understandProcessPrompt(nextScenario, prompt);
  const changes: Array<Record<string, unknown>> = [];
  const warnings = [...intentPayload.warnings];

  for (const intent of intentPayload.intents) {
    const selected = resolveProcess(nextScenario, intent);
    if (!selected) {
      warnings.push(`未能匹配工艺：${intent.process_name || intent.process_method_id || "未指定工艺"}。`);
      continue;
    }
    const targets = matchIntentComponents(nextScenario, intent);
    if (!targets.length) {
      warnings.push(`未找到可应用构件：${intentTargetLabel(intent)}。`);
      continue;
    }
    for (const item of targets) {
      item.method_id = selected.method_id || selected.id;
      item.productivity_option_id = null;
    }
    changes.push({
      action: intent.action || "AI 操作助手工艺设置",
      process_id: selected.method_id || selected.id,
      process_name: selected.process_name,
      matched_count: targets.length,
      targets: targets.slice(0, 20).map((item) => item.name),
      message: `${intent.action || "AI 操作助手工艺设置"}：已将 ${targets.length} 个构件设置为“${selected.process_name}”。`,
    });
  }

  if (!changes.length && !warnings.length) {
    warnings.push("暂未识别到可应用的工艺设置，请说明构件范围和工艺名称。");
  }
  applyResourceMaxQuantityDefaults(nextScenario);
  return { scenario: nextScenario, changes, warnings };
}

async function understandProcessPrompt(scenario: ScenarioInput, prompt: string): Promise<ProcessIntentPayload> {
  const llmPayload = await understandProcessPromptWithModel(scenario, prompt);
  if (llmPayload.intents.length) return llmPayload;
  const fallback = understandProcessPromptLocally(prompt);
  return {
    intents: fallback.intents,
    warnings: [...llmPayload.warnings, ...fallback.warnings],
  };
}

async function understandProcessPromptWithModel(scenario: ScenarioInput, prompt: string): Promise<ProcessIntentPayload> {
  const endpoint = modelEndpoint();
  if (!endpoint) {
    return { intents: [], warnings: ["未配置 Netlify AI Gateway 或 OpenAI-compatible 端点，已使用本地规则解析。"] };
  }

  const payload = {
    model: envValue("PROCESS_NL_LLM_MODEL") || "gpt-4o-mini",
    messages: [
      { role: "system", content: processIntentInstruction() },
      {
        role: "user",
        content: JSON.stringify({
          user_prompt: prompt,
          process_library: processLibraryCatalog(scenario),
          component_catalog: componentCatalog(scenario),
          output_schema: processIntentOutputSchema(),
        }),
      },
    ],
    temperature: Number(envValue("PROCESS_NL_LLM_TEMPERATURE") ?? 0),
    response_format: { type: "json_object" },
  };
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const apiKey = envValue("PROCESS_NL_LLM_API_KEY") || envValue("OPENAI_API_KEY");
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`;

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      return { intents: [], warnings: [`大模型调用失败(${response.status})，已使用本地规则解析。`] };
    }
    const raw = await response.json();
    return normalizeIntentPayload(extractIntentPayload(raw));
  } catch (error) {
    return { intents: [], warnings: [`大模型调用异常，已使用本地规则解析：${error instanceof Error ? error.message : String(error)}`] };
  }
}

function modelEndpoint() {
  const explicit = envValue("PROCESS_NL_LLM_ENDPOINT");
  if (explicit) return explicit;
  const base = envValue("OPENAI_BASE_URL");
  if (!base) return "";
  const trimmed = base.replace(/\/$/, "");
  return trimmed.endsWith("/chat/completions") ? trimmed : `${trimmed}/chat/completions`;
}

function envValue(name: string) {
  return typeof Netlify !== "undefined" ? Netlify?.env.get(name) : undefined;
}

function processIntentInstruction() {
  return [
    "你是桥梁施工排程系统的工艺设置语义解析器。",
    "把用户自然语言解析为 JSON，不要输出 Markdown，不要解释。",
    "只允许返回 {\"intents\": [...], \"warnings\": [...]}。",
    "intent 字段包括 component_type、process_method_id、process_name、sides、support_nos、component_names、pile_nos、target_role、action。",
    "component_type 只能从构件和工艺库中选择，例如 pile、pier_body、cap、cap_beam、ground_tie_beam、middle_tie_beam。",
    "process_method_id 优先使用工艺库 method_id，例如 rotary_drill、impact_drill、manual_pile、climbing_form。",
    "用户说连续梁主墩或主墩爬模时，可以设置 target_role 为 continuous_girder_main_pier。",
    "无法确认时放入 warnings，不要编造不存在的构件。",
  ].join("");
}

function processLibraryCatalog(scenario: ScenarioInput) {
  return scenario.process_library.map((item) => ({
    component_type: item.component_type,
    method_id: item.method_id || item.id,
    process_name: item.process_name,
  }));
}

function componentCatalog(scenario: ScenarioInput) {
  return scenario.project.bridges.flatMap((bridge) =>
    bridge.work_sections.flatMap((section) =>
      section.structures.flatMap((structure) =>
        structure.components.map((item) => ({
          bridge: bridge.name,
          section: section.name,
          side: section.side,
          support_no: structure.support_no || structure.name,
          component_type: item.component_type,
          component_name: item.name,
          current_method_id: item.method_id,
        })),
      ),
    ),
  );
}

function processIntentOutputSchema() {
  return {
    intents: [{
      component_type: "pile",
      process_method_id: "manual_pile",
      process_name: "人工挖孔",
      sides: [],
      support_nos: ["3号墩", "4号墩"],
      component_names: [],
      pile_nos: [],
      target_role: null,
      action: "指定墩桩基工艺",
    }],
    warnings: [],
  };
}

function extractIntentPayload(raw: unknown): unknown {
  if (isRecord(raw) && Array.isArray(raw.intents)) return raw;
  if (isRecord(raw) && Array.isArray(raw.choices) && raw.choices.length) {
    const first = raw.choices[0];
    const content = isRecord(first) && isRecord(first.message) ? first.message.content : "";
    if (typeof content === "string") return JSON.parse(stripJsonFence(content));
  }
  if (isRecord(raw) && typeof raw.output_text === "string") return JSON.parse(stripJsonFence(raw.output_text));
  if (isRecord(raw) && typeof raw.content === "string") return JSON.parse(stripJsonFence(raw.content));
  return raw;
}

function normalizeIntentPayload(raw: unknown): ProcessIntentPayload {
  if (!isRecord(raw)) return { intents: [], warnings: ["大模型返回不是 JSON 对象，已使用本地规则解析。"] };
  const intents = Array.isArray(raw.intents)
    ? raw.intents.filter(isRecord).map((item) => ({
      component_type: isComponentType(item.component_type) ? item.component_type : null,
      process_method_id: stringOrNull(item.process_method_id),
      process_name: stringOrNull(item.process_name),
      sides: stringArray(item.sides),
      support_nos: stringArray(item.support_nos),
      component_names: stringArray(item.component_names),
      pile_nos: stringArray(item.pile_nos),
      target_role: stringOrNull(item.target_role),
      action: stringOrNull(item.action) ?? "AI 操作助手工艺设置",
    }))
    : [];
  return {
    intents,
    warnings: stringArray(raw.warnings),
  };
}

function understandProcessPromptLocally(prompt: string): ProcessIntentPayload {
  const text = normalizeText(prompt);
  const intents: ProcessIntent[] = [];
  const pileProcess = pileProcessFromText(text);
  if (text.includes("桩基") && pileProcess) {
    intents.push({
      component_type: "pile",
      process_method_id: pileProcess.methodId,
      process_name: pileProcess.name,
      support_nos: extractSupportNos(text),
      component_names: extractPileComponentNames(text),
      pile_nos: extractPileNos(text),
      action: "指定桩基工艺",
    });
  }
  if (text.includes("爬模")) {
    intents.push({
      component_type: "pier_body",
      process_method_id: "climbing_form",
      process_name: "爬模施工",
      target_role: text.includes("连续梁") || text.includes("主墩") ? "continuous_girder_main_pier" : null,
      support_nos: extractSupportNos(text),
      action: "指定墩柱爬模工艺",
    });
  }
  return { intents, warnings: [] };
}

function pileProcessFromText(text: string) {
  if (text.includes("人工挖孔") || text.includes("挖孔桩")) return { methodId: "manual_pile", name: "人工挖孔" };
  if (text.includes("回旋钻")) return { methodId: "circulation_drill", name: "回旋钻" };
  if (text.includes("冲击钻") || text.includes("冲孔")) return { methodId: "impact_drill", name: "冲击钻成孔" };
  if (text.includes("旋挖")) return { methodId: "rotary_drill", name: "旋挖钻成孔" };
  return null;
}

function resolveProcess(scenario: ScenarioInput, intent: ProcessIntent) {
  const methodId = intent.process_method_id || methodFromProcessName(intent.process_name ?? "");
  if (intent.component_type === "pile" && methodId) {
    const found = scenario.process_library.find((item) => item.component_type === "pile" && (item.method_id === methodId || item.id === methodId));
    if (found) return found;
  }
  if (intent.component_type === "pier_body" && (methodId === "climbing_form" || (intent.process_name ?? "").includes("爬模"))) {
    return ensureProcess(scenario, "pier_body", "climbing_form", "爬模施工", "pier_body_team", "days_per_unit", "pier_height_m", 7, "天/节", 4.5);
  }
  return scenario.process_library.find((item) => {
    if (intent.component_type && item.component_type !== intent.component_type) return false;
    if (methodId && (item.method_id === methodId || item.id === methodId)) return true;
    return Boolean(intent.process_name && (item.process_name.includes(intent.process_name) || intent.process_name.includes(item.process_name)));
  }) ?? null;
}

function methodFromProcessName(name: string) {
  const text = normalizeText(name);
  return pileProcessFromText(text)?.methodId ?? (text.includes("爬模") ? "climbing_form" : null);
}

function ensureProcess(
  scenario: ScenarioInput,
  componentType: ComponentType,
  methodId: string,
  processName: string,
  resourceType: string,
  durationMethod: string,
  quantitySource: string,
  productivityValue: number,
  productivityUnit: string,
  standardSectionHeight: number | null = null,
) {
  const existing = scenario.process_library.find((item) => item.component_type === componentType && (item.method_id === methodId || item.id === methodId));
  if (existing) return existing;
  const created = process(
    `${componentType}_${methodId}`,
    componentType,
    processName,
    methodId,
    durationMethod,
    quantitySource,
    productivityValue,
    productivityUnit,
    resourceType,
    false,
    standardSectionHeight,
  );
  scenario.process_library.push(created);
  if (!scenario.resource_pools.some((item) => item.type === resourceType)) {
    scenario.resource_pools.push(pool(`pool-${resourceType.replaceAll("_", "-")}`, resourceType, processName, 1, 1));
  }
  return created;
}

function matchIntentComponents(scenario: ScenarioInput, intent: ProcessIntent) {
  const componentNames = new Set((intent.component_names ?? []).map(normalizeText));
  const supportNos = new Set((intent.support_nos ?? []).map(normalizeSupportNo).filter(Boolean));
  const pileNos = new Set((intent.pile_nos ?? []).map((item) => item.replace(/\D/g, "")).filter(Boolean));
  let matches = scenario.project.bridges.flatMap((bridge) =>
    bridge.work_sections.flatMap((section) =>
      section.structures.flatMap((structure) =>
        structure.components
          .filter((item) => !intent.component_type || item.component_type === intent.component_type)
          .filter((item) => !supportNos.size || supportNos.has(normalizeSupportNo(structure.support_no || structure.name)))
          .filter((item) => !componentNames.size || componentNames.has(normalizeText(item.name)))
          .filter((item) => !pileNos.size || pileNos.has(componentPileNo(item)))
          .map((item) => item),
      ),
    ),
  );
  if (!matches.length && intent.target_role === "continuous_girder_main_pier" && intent.component_type === "pier_body") {
    matches = scenario.project.bridges.flatMap((bridge) =>
      bridge.work_sections.flatMap((section) =>
        section.structures
          .filter((structure) => structure.structure_type === "pier")
          .slice(0, 4)
          .flatMap((structure) => structure.components.filter((item) => item.component_type === "pier_body")),
      ),
    );
  }
  return matches;
}

function intentTargetLabel(intent: ProcessIntent) {
  return [
    ...(intent.support_nos ?? []),
    ...(intent.component_names ?? []),
    intent.component_type ?? "",
  ].filter(Boolean).join(" / ") || "未指定范围";
}

function extractSupportNos(text: string) {
  return Array.from(text.matchAll(/(\d{1,3})\s*#?\s*(墩|台)/g)).map((match) => `${Number(match[1])}号${match[2]}`);
}

function extractPileNos(text: string) {
  return Array.from(text.matchAll(/(\d{1,3})\s*#?\s*桩基/g)).map((match) => String(Number(match[1])));
}

function extractPileComponentNames(text: string) {
  return Array.from(text.matchAll(/(\d{1,3})\s*#?\s*(墩|台)[-—~至到\s]*(\d{1,3})\s*#?\s*桩基/g))
    .map((match) => `${Number(match[1])}号${match[2]}-${Number(match[3])}#桩基`);
}

function normalizeSupportNo(value: string) {
  const text = normalizeText(value);
  const match = text.match(/(\d{1,3})\s*(?:#|号)?\s*(墩|台)/);
  return match ? `${Number(match[1])}号${match[2]}` : text;
}

function componentPileNo(item: ComponentModel) {
  const match = normalizeText(item.name).match(/-(\d{1,3})#桩基$/);
  return match ? String(Number(match[1])) : "";
}

function compareScenarios(body: { results?: Array<ReturnType<typeof solveScenario>> }) {
  const summaries = (body.results ?? []).map((item) => {
    const penalty = item.milestone_results.reduce((sum, milestoneModel) => sum + milestoneModel.penalty, 0);
    const score = (item.result.objective_days ?? 0) + penalty;
    return {
      scenario_id: item.scenario_id,
      scenario_name: item.scenario_name,
      status: item.result.status,
      total_days: item.result.objective_days,
      plan_finish_date: item.result.plan_finish_date,
      soft_late_count: item.milestone_results.filter((milestoneModel) => milestoneModel.mode === "soft" && milestoneModel.lateness_days > 0).length,
      hard_missed_count: item.milestone_results.filter((milestoneModel) => milestoneModel.mode === "hard" && milestoneModel.lateness_days > 0).length,
      soft_penalty: penalty,
      score,
      resource_count: item.generated.schedule_input.resources.length,
    };
  });
  const best = summaries.reduce<typeof summaries[number] | null>((current, item) => {
    if (!current) return item;
    return item.score < current.score ? item : current;
  }, null);
  return {
    summaries,
    best_scenario_id: best?.scenario_id ?? null,
    notes: best ? ["推荐方案按总工期加软里程碑罚分综合选择。"] : [],
  };
}

function groupBy<T>(items: T[], keyFn: (item: T) => string) {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const key = keyFn(item);
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  return groups;
}

function normalizeText(value: string) {
  return value
    .normalize("NFKC")
    .replace(/\s+/g, "")
    .replace(/[，、；;]+/g, "，")
    .trim();
}

function stripJsonFence(value: string) {
  let text = value.trim();
  if (text.startsWith("```")) {
    text = text.replace(/^```(?:json)?/i, "").replace(/```$/i, "").trim();
  }
  return text;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isComponentType(value: unknown): value is ComponentType {
  return [
    "pile",
    "cap",
    "spread_foundation",
    "ground_tie_beam",
    "middle_tie_beam",
    "pier_body",
    "cap_beam",
    "abutment_body",
    "precast_beam",
    "beam_erection",
    "cast_in_place_continuous_beam",
    "cast_in_place_box_beam",
    "steel_box_beam",
    "bridge_deck_system",
  ].includes(String(value));
}

function stringOrNull(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string").map((item) => item.trim()).filter(Boolean) : [];
}

function addDays(value: string, days: number) {
  const date = new Date(`${value}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function daysBetween(start: string, end: string) {
  const startDate = new Date(`${start}T00:00:00Z`).getTime();
  const endDate = new Date(`${end}T00:00:00Z`).getTime();
  return Math.round((endDate - startDate) / 86400000);
}
