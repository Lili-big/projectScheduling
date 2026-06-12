import {
  AlertCircle,
  Bot,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Database,
  Flag,
  GitCompare,
  Layers3,
  Loader2,
  Play,
  Save,
  Server,
  Sparkles,
  Upload,
  Workflow,
  X,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

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
type RelationshipType = "FS" | "SS" | "FF" | "SF";
type WorkPointType = "road" | "bridge" | "tunnel";
type WorkSectionSide = "left" | "right" | "none";
type TabKey = "project" | "process" | "logic" | "resources" | "milestones" | "tasks" | "results";
type GanttMode = "by_structure" | "by_process";
type TaskViewMode = "by_structure" | "by_process";

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

type StructureModel = {
  id: string;
  name: string;
  structure_type: "pier" | "abutment";
  order: number;
  support_no?: string | null;
  support_index?: number | null;
  components: ComponentModel[];
};

type WorkSection = {
  id: string;
  name: string;
  order: number;
  side: WorkSectionSide;
  structures: StructureModel[];
  upper_structures: UpperStructureModel[];
};

type ProjectBridge = {
  id: string;
  name: string;
  order: number;
  workpoint_type: WorkPointType;
  import_source: Record<string, unknown>;
  work_sections: WorkSection[];
};

type ProjectModel = {
  project_id: string;
  project_name: string;
  start_date: string;
  bridges: ProjectBridge[];
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

type ProcessTemplate = {
  id: string;
  component_type: ComponentType;
  process_name: string;
  method_id?: string | null;
  duration_method: string;
  quantity_source: string;
  productivity_value: number;
  productivity_unit: string;
  resource_type: string;
  productivity_options?: ProductivityOption[];
  applicability: Record<string, unknown>;
  is_default: boolean;
};

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

type ResourceCalendar = {
  id: string;
  name: string;
  working_weekdays: number[];
  blackout_dates: string[];
};

type ResourcePool = {
  id: string;
  type: string;
  label: string;
  quantity: number;
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
  project: ProjectModel;
  process_library: ProcessTemplate[];
  logic_rules: LogicRule[];
  upper_structure_logic_rules?: UpperStructureLogicRule[];
  resource_calendars: ResourceCalendar[];
  resource_pools: ResourcePool[];
  milestones: MilestoneConstraint[];
  time_limit_seconds: number;
};

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
  enabled: boolean;
  calendar_id: string;
};

type ResourceAllocation = {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  task_id: string;
  task_name: string;
  start_offset: number;
  end_offset: number;
  start_date: string;
  finish_date: string;
};

type MilestoneResult = MilestoneConstraint & {
  actual_date?: string | null;
  actual_offset?: number | null;
  lateness_days: number;
  penalty: number;
  status: "met" | "late" | "not_evaluated";
};

type ValidationMessage = {
  level: "info" | "warning" | "error";
  message: string;
  subject_id?: string | null;
};

type ScheduleInput = {
  project_name: string;
  start_date: string;
  tasks: Task[];
  precedence_links: PrecedenceLink[];
  resources: Resource[];
  milestones: MilestoneConstraint[];
  time_limit_seconds: number;
};

type GeneratedScheduleInput = {
  schedule_input: ScheduleInput;
  validation: ValidationMessage[];
  source_summary: Record<string, unknown>;
};

type ScheduleResult = {
  status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN" | "MODEL_INVALID";
  objective_days: number | null;
  plan_start_date: string;
  plan_finish_date?: string | null;
  tasks: ScheduledTask[];
  resource_allocations: ResourceAllocation[];
  milestone_results: MilestoneResult[];
  validation: ValidationMessage[];
  stats: Record<string, unknown>;
  objective_breakdown: Record<string, unknown>;
};

type ScenarioSolveResult = {
  scenario_id: string;
  scenario_name: string;
  generated: GeneratedScheduleInput;
  result: ScheduleResult;
  milestone_results: MilestoneResult[];
  diagnostics: ValidationMessage[];
  metrics: Record<string, unknown>;
};

type CompareResponse = {
  summaries: Array<Record<string, unknown>>;
  best_scenario_id?: string | null;
  notes: string[];
};

type ImportBridgeParamsResponse = {
  scenario: ScenarioInput;
  canonical_bridge: Record<string, unknown>;
  summary: Record<string, unknown>;
  quality_checks: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
};

type ProcessNlChange = {
  action: string;
  process_id?: string | null;
  process_name?: string | null;
  matched_count: number;
  targets: string[];
  message: string;
};

type ProcessNlResponse = {
  scenario: ScenarioInput;
  changes: ProcessNlChange[];
  warnings: string[];
};

type ContinuitySplitDetail = {
  structure_id: string;
  structure_name: string;
  component_label: string;
  process_name: string;
  resource_count: number;
  resource_names: string[];
};

type ContinuityJumpDetail = {
  resource_id: string;
  resource_name: string;
  from_location: string;
  to_location: string;
  jump_distance: number | null;
  is_jump_pier: boolean;
  is_side_switch: boolean;
  is_cross_side_jump: boolean;
  is_direction_reversal: boolean;
};

type ResourcePathStep = {
  task_id: string;
  task_name: string;
  location: string;
  component_type: ComponentType;
  component_label: string;
  start_date: string;
  finish_date: string;
};

type ResourcePath = {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  task_count: number;
  start_date?: string | null;
  finish_date?: string | null;
  jump_pier_count: number;
  side_switch_count: number;
  cross_side_jump_count: number;
  path: ResourcePathStep[];
};

type ContinuityMetrics = {
  continuity_score: number;
  same_structure_craft_split_count: number;
  jump_pier_count: number;
  max_jump_distance: number;
  side_switch_count: number;
  cross_side_jump_count: number;
  direction_reversal_count: number;
  same_structure_craft_split_details: ContinuitySplitDetail[];
  jump_transition_details: ContinuityJumpDetail[];
  resource_paths: ResourcePath[];
};

type StructureRow = ReturnType<typeof buildStructureRows>[number];

type StructureFilters = {
  workpointLabel: string;
  bridgeAndSection: string;
  structureLevel: string;
  sideLabel: string;
  location: string;
  name: string;
  typeLabel: string;
  dimension: string;
  processLabel: string;
  productivityLabel: string;
};

type TaskViewFilters = {
  structureText: string;
  processText: string;
};

type TaskViewRow = {
  task: Task;
  bridgeName: string;
  bridgeOrder: number;
  sectionName: string;
  sectionOrder: number;
  sideLabel: string;
  structureLabel: string;
  parentStructureId: string;
  parentStructureLabel: string;
  predecessorLinks: PrecedenceLink[];
  searchText: string;
};

type TaskViewGroup = {
  id: string;
  title: string;
  subtitle: string;
  rows: TaskViewRow[];
};

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";
const PREDECESSOR_HOVER_DELAY_MS = 450;
const PREDECESSOR_HOVER_CLOSE_DELAY_MS = 140;

const componentLabels: Record<ComponentType, string> = {
  pile: "桩基",
  cap: "承台",
  spread_foundation: "扩大基础",
  ground_tie_beam: "地系梁",
  middle_tie_beam: "中系梁",
  pier_body: "墩身",
  cap_beam: "盖梁",
  abutment_body: "桥台",
  precast_beam: "制梁",
  beam_erection: "架梁",
  cast_in_place_continuous_beam: "现浇连续梁",
  cast_in_place_box_beam: "现浇箱梁",
  steel_box_beam: "钢箱梁",
  bridge_deck_system: "桥面系",
};

type UpperStructureLogicDefinition = {
  id: string;
  name: string;
  upperTarget: string;
  lowerPredecessor: string;
  generation: string;
  note: string;
};

const upperStructureLogicDefinitions: UpperStructureLogicDefinition[] = [
  {
    id: "cast_in_place_box_beam_after_lower_structure",
    name: "现浇箱梁前置",
    upperTarget: "现浇箱梁现场任务",
    lowerPredecessor: "跨组覆盖范围内墩台完成任务",
    generation: "按现浇箱梁跨组生成任务，跨组涉及支座均作为前置。",
    note: "现浇箱梁在对应跨组墩台下部结构完成后开始。",
  },
  {
    id: "continuous_beam_zero_block_after_main_pier_lower_structure",
    name: "连续梁0号块前置",
    upperTarget: "主墩T构0号块",
    lowerPredecessor: "对应主墩完成任务",
    generation: "每个主墩T构生成1个0号块任务，对应主墩完成后开始。",
    note: "连续梁0号块在对应主墩下部结构完成后开始。",
  },
  {
    id: "continuous_beam_side_straight_after_edge_lower_structure",
    name: "连续梁边跨连续段前置",
    upperTarget: "边跨连续段",
    lowerPredecessor: "对应边跨墩台完成任务",
    generation: "每联连续梁左右边跨各生成1个连续段任务，边跨墩台完成后开始。",
    note: "连续梁边跨连续段在对应边跨墩台下部结构完成后开始。",
  },
  {
    id: "continuous_beam_t_chain",
    name: "连续梁T构顺序",
    upperTarget: "同一主墩T构标准段",
    lowerPredecessor: "同一T构0号块或上一段",
    generation: "每个T构内0号块、标准段按顺序生成前后置关系。",
    note: "连续梁T构内0号块和标准段按顺序施工。",
  },
  {
    id: "continuous_beam_side_closure",
    name: "连续梁边跨合龙",
    upperTarget: "边跨合龙段",
    lowerPredecessor: "边跨连续段和相邻T构",
    generation: "左右边跨合龙段分别以前置边跨连续段和相邻T构完成为前置。",
    note: "连续梁边跨合龙段在边跨连续段和相邻T构完成后开始。",
  },
  {
    id: "continuous_beam_middle_closure",
    name: "连续梁中跨合龙",
    upperTarget: "中跨合龙段",
    lowerPredecessor: "相邻两个T构",
    generation: "每个中跨合龙段以左右相邻T构完成为前置。",
    note: "连续梁中跨合龙段在相邻两个T构完成后开始。",
  },
  {
    id: "continuous_beam_edge_before_middle_closure",
    name: "边跨先于中跨合龙",
    upperTarget: "中跨合龙段",
    lowerPredecessor: "左右边跨合龙段",
    generation: "默认所有中跨合龙段等待边跨合龙段完成后开始。",
    note: "连续梁默认边跨合龙先于中跨合龙。",
  },
  {
    id: "continuous_beam_middle_closure_sequence",
    name: "中跨合龙顺序",
    upperTarget: "后序中跨合龙段",
    lowerPredecessor: "前序中跨合龙段",
    generation: "按连续梁配置的中跨合龙顺序生成前后置关系。",
    note: "连续梁中跨合龙按配置顺序推进。",
  },
];

function defaultUpperStructureLogicRules(): UpperStructureLogicRule[] {
  return upperStructureLogicDefinitions.map((definition) => ({
    id: definition.id,
    relationship: "FS",
    lag_days: 0,
    severity: "error",
    note: definition.note,
  }));
}

function mergeUpperStructureLogicRules(rules: UpperStructureLogicRule[] = []): UpperStructureLogicRule[] {
  const byId = new Map(defaultUpperStructureLogicRules().map((rule) => [rule.id, rule]));
  for (const rule of rules) {
    byId.set(rule.id, {
      ...rule,
      relationship: rule.relationship ?? "FS",
      lag_days: rule.lag_days ?? 0,
      severity: rule.severity ?? "error",
    });
  }
  return upperStructureLogicDefinitions.map((definition) => byId.get(definition.id) ?? {
    id: definition.id,
    relationship: "FS",
    lag_days: 0,
    severity: "error",
    note: definition.note,
  });
}

const upperStructureCodes = {
  simpleBeam: "precastTGirder",
  castInPlaceBoxBeam: "castInPlaceBoxGirder",
  continuousBeam: "castInPlaceContinuousBoxGirder",
} as const;

type UpperLowerLogicConstraint = {
  id: string;
  name: string;
  upperTarget: string;
  lowerPredecessor: string;
  generation: string;
  relationship: RelationshipType;
  lagDays: number;
  matchedText: string;
  note: string;
};

const durationMethodLabels: Record<string, string> = {
  units_per_day: "按日完成量计算",
  days_per_unit: "按单位耗时计算",
  fixed_days: "固定工期",
};

const quantitySourceLabels: Record<string, string> = {
  pile_length_m: "桩长",
  pier_height_m: "墩高",
  deck_length_m: "桥面长度",
  count: "构件数量",
};

const pileProductivityUnitOptions = [
  { unit: "m/天", duration_method: "units_per_day", quantity_source: "pile_length_m" },
  { unit: "根/天", duration_method: "units_per_day", quantity_source: "count" },
  { unit: "天/根", duration_method: "days_per_unit", quantity_source: "count" },
  { unit: "天/m", duration_method: "days_per_unit", quantity_source: "pile_length_m" },
];

const segmentedPierMethodIds = new Set(["climbing_form", "sliding_form", "turnover_form"]);

const segmentedPierProductivityUnitOptions = [
  { unit: "天/节", duration_method: "days_per_unit", quantity_source: "pier_height_m" },
  { unit: "m/天", duration_method: "units_per_day", quantity_source: "pier_height_m" },
];

function defaultStandardSectionHeightForUnit(unit: string): number | undefined {
  return unit === "天/节" ? 4.5 : undefined;
}

function supportsSegmentedPierUnits(process: ProcessTemplate): boolean {
  return (
    process.component_type === "pier_body"
    && (
      Boolean(process.method_id && segmentedPierMethodIds.has(process.method_id))
      || ["爬模", "滑模", "翻模"].some((keyword) => process.process_name.includes(keyword))
    )
  );
}

function sectionHeightForOption(option: ProductivityOption): number | undefined {
  const value = option.standard_section_height_m;
  return typeof value === "number" && value > 0 ? value : defaultStandardSectionHeightForUnit(option.productivity_unit);
}

function normalizeProductivityOptionForProcess(process: ProcessTemplate, option: ProductivityOption): ProductivityOption {
  if (!supportsSegmentedPierUnits(process)) {
    return option;
  }
  const unitRule = segmentedPierProductivityUnitOptions.find((item) => item.unit === option.productivity_unit);
  if (!unitRule) {
    return option;
  }
  return {
    ...option,
    duration_method: unitRule.duration_method,
    quantity_source: unitRule.quantity_source,
    standard_section_height_m: unitRule.unit === "天/节" ? sectionHeightForOption(option) : undefined,
  };
}

function isSectionBasedPierProductivity(option: ProductivityOption): boolean {
  return option.productivity_unit === "天/节";
}

const componentColors: Record<ComponentType, string> = {
  pile: "#2563eb",
  cap: "#0f766e",
  spread_foundation: "#0d9488",
  ground_tie_beam: "#64748b",
  middle_tie_beam: "#0891b2",
  pier_body: "#b45309",
  cap_beam: "#7c3aed",
  abutment_body: "#be123c",
  precast_beam: "#155e75",
  beam_erection: "#9333ea",
  cast_in_place_continuous_beam: "#0369a1",
  cast_in_place_box_beam: "#16a34a",
  steel_box_beam: "#475569",
  bridge_deck_system: "#c2410c",
};

const componentOrder: ComponentType[] = [
  "pile",
  "cap",
  "spread_foundation",
  "ground_tie_beam",
  "pier_body",
  "middle_tie_beam",
  "cap_beam",
  "abutment_body",
  "precast_beam",
  "beam_erection",
  "cast_in_place_continuous_beam",
  "cast_in_place_box_beam",
  "steel_box_beam",
  "bridge_deck_system",
];

function componentSortIndex(componentType: ComponentType): number {
  const index = componentOrder.indexOf(componentType);
  return index >= 0 ? index : componentOrder.length;
}

const workpointLabels: Record<WorkPointType, string> = {
  road: "路",
  bridge: "桥",
  tunnel: "隧",
};

const sideLabels: Record<WorkSectionSide, string> = {
  left: "左幅",
  right: "右幅",
  none: "无幅别",
};

const scheduleStatusLabels: Record<ScheduleResult["status"], string> = {
  OPTIMAL: "最优",
  FEASIBLE: "可行",
  INFEASIBLE: "不可行",
  UNKNOWN: "未知",
  MODEL_INVALID: "模型无效",
};

const milestoneStatusLabels: Record<MilestoneResult["status"], string> = {
  met: "已满足",
  late: "已迟延",
  not_evaluated: "未评估",
};

const diagnosticLevelLabels: Record<ValidationMessage["level"], string> = {
  info: "正常",
  warning: "提醒",
  error: "严重偏差",
};

type MetricTone = "ok" | "warn" | "danger" | "neutral";

type PlanStatusDisplay = {
  label: string;
  tone: MetricTone;
  hint?: string;
  diagnostic?: ValidationMessage;
};

function derivePlanStatus(result: ScheduleResult | null): PlanStatusDisplay {
  if (!result) {
    return { label: "未求解", tone: "neutral" };
  }

  const isSolved = result.status === "OPTIMAL" || result.status === "FEASIBLE";
  if (!isSolved) {
    return {
      label: scheduleStatusLabels[result.status],
      tone: result.status === "UNKNOWN" ? "warn" : "danger",
    };
  }

  const solveMode = typeof result.objective_breakdown.solve_mode === "string"
    ? result.objective_breakdown.solve_mode
    : result.stats.solve_mode;
  const isShortestDurationMode = !solveMode || solveMode === "shortest_duration_fixed_resources";

  if (!isShortestDurationMode) {
    return { label: scheduleStatusLabels[result.status], tone: "ok" };
  }

  const lateMilestones = result.milestone_results.filter((milestone) => milestone.lateness_days > 0);
  const hardLateCount = lateMilestones.filter((milestone) => milestone.mode === "hard").length;
  const softLateCount = lateMilestones.filter((milestone) => milestone.mode === "soft").length;

  if (hardLateCount > 0) {
    return {
      label: "不可行",
      tone: "danger",
      hint: "硬里程碑未满足",
      diagnostic: {
        level: "error",
        message: `工期不满足硬里程碑要求：${hardLateCount} 个强制里程碑节点未满足。`,
        subject_id: "plan-status-hard-milestone",
      },
    };
  }

  if (softLateCount > 0) {
    return {
      label: "可行",
      tone: "warn",
      hint: "弱节点不满足",
      diagnostic: {
        level: "warning",
        message: `弱节点不满足：${softLateCount} 个提醒里程碑节点未满足。`,
        subject_id: "plan-status-soft-milestone",
      },
    };
  }

  return { label: "可行", tone: "ok", hint: "里程碑均满足" };
}

const tabs: Array<{ key: TabKey; label: string; icon: ReactNode }> = [
  { key: "project", label: "项目参数", icon: <Layers3 size={15} /> },
  { key: "process", label: "工艺工效库", icon: <Database size={15} /> },
  { key: "logic", label: "工艺逻辑", icon: <Workflow size={15} /> },
  { key: "resources", label: "资源配置", icon: <Server size={15} /> },
  { key: "milestones", label: "里程碑", icon: <Flag size={15} /> },
  { key: "tasks", label: "任务视图", icon: <ClipboardList size={15} /> },
  { key: "results", label: "模拟结果", icon: <CheckCircle2 size={15} /> },
];

function SideNavigation({
  activeTab,
  openTabs,
  onOpen,
}: {
  activeTab: TabKey | null;
  openTabs: TabKey[];
  onOpen: (tabKey: TabKey) => void;
}) {
  return (
    <aside className="side-nav">
      <div className="side-nav-section">
        <div className="side-nav-heading">功能导航</div>
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`side-nav-item ${activeTab === tab.key ? "active" : ""}`}
            type="button"
            onClick={() => onOpen(tab.key)}
          >
            <span className="side-nav-icon">{tab.icon}</span>
            <span>{tab.label}</span>
            {openTabs.includes(tab.key) && <span className="side-nav-dot" />}
          </button>
        ))}
      </div>
    </aside>
  );
}

function WorkspaceTabStrip({
  openTabs,
  activeTab,
  onSelect,
  onClose,
}: {
  openTabs: TabKey[];
  activeTab: TabKey | null;
  onSelect: (tabKey: TabKey) => void;
  onClose: (tabKey: TabKey) => void;
}) {
  return (
    <div className="workspace-tabs" role="tablist" aria-label="已打开模块">
      {openTabs.map((tabKey) => {
        const tab = tabs.find((item) => item.key === tabKey);
        if (!tab) return null;

        return (
          <div className={`workspace-tab ${activeTab === tabKey ? "active" : ""}`} key={tab.key}>
            <button className="workspace-tab-main" type="button" onClick={() => onSelect(tab.key)}>
              {tab.icon}
              <span>{tab.label}</span>
            </button>
            <button
              className="workspace-tab-close"
              type="button"
              aria-label={`关闭${tab.label}`}
              onClick={() => onClose(tab.key)}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default function App() {
  const [scenario, setScenario] = useState<ScenarioInput | null>(null);
  const [generated, setGenerated] = useState<GeneratedScheduleInput | null>(null);
  const [generatedScenarioFingerprint, setGeneratedScenarioFingerprint] = useState<string | null>(null);
  const [solveResult, setSolveResult] = useState<ScenarioSolveResult | null>(null);
  const [solveResultScenarioFingerprint, setSolveResultScenarioFingerprint] = useState<string | null>(null);
  const [openTabs, setOpenTabs] = useState<TabKey[]>(["project"]);
  const [activeTab, setActiveTab] = useState<TabKey | null>("project");
  const [ganttMode, setGanttMode] = useState<GanttMode>("by_structure");
  const [savedResults, setSavedResults] = useState<ScenarioSolveResult[]>([]);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [busy, setBusy] = useState<"loading" | "generating" | "solving" | "minResources" | "comparing" | "importing" | "nl" | "savingProcessLibrary" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastImport, setLastImport] = useState<ImportBridgeParamsResponse | null>(null);
  const [processLibraryDirty, setProcessLibraryDirty] = useState(false);

  useEffect(() => {
    void loadScenario();
  }, []);

  const flatStructures = useMemo(() => (scenario ? flattenStructures(scenario.project) : []), [scenario]);
  const scenarioFingerprint = useMemo(() => (scenario ? scenarioFingerprintForSolve(scenario) : null), [scenario]);
  const currentGenerated = scenarioFingerprint !== null && generatedScenarioFingerprint === scenarioFingerprint ? generated : null;
  const currentSolveResult = scenarioFingerprint !== null && solveResultScenarioFingerprint === scenarioFingerprint ? solveResult : null;
  const previousScenarioFingerprintRef = useRef<string | null>(null);

  useEffect(() => {
    if (previousScenarioFingerprintRef.current === null) {
      previousScenarioFingerprintRef.current = scenarioFingerprint;
      return;
    }
    if (previousScenarioFingerprintRef.current === scenarioFingerprint) return;
    previousScenarioFingerprintRef.current = scenarioFingerprint;
    setGenerated(null);
    setGeneratedScenarioFingerprint(null);
    setSolveResult(null);
    setSolveResultScenarioFingerprint(null);
    setComparison(null);
  }, [scenarioFingerprint]);

  async function loadScenario() {
    setBusy("loading");
    setError(null);
    try {
      const demo = await apiGet<ScenarioInput>("/api/demo-scenario");
      const imported = await apiPost<ImportBridgeParamsResponse>("/api/import-local-bridge-params", demo);
      setScenario(imported.scenario);
      setGenerated(null);
      setGeneratedScenarioFingerprint(null);
      setSolveResult(null);
      setSolveResultScenarioFingerprint(null);
      setComparison(null);
      setLastImport(imported);
      setActiveTab("project");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function generateOnly() {
    if (!scenario) return;
    const requestScenario = scenario;
    const requestFingerprint = scenarioFingerprintForSolve(requestScenario);
    setBusy("generating");
    setError(null);
    try {
      const nextGenerated = await apiPost<GeneratedScheduleInput>("/api/generate-schedule-input", requestScenario);
      setGenerated(nextGenerated);
      setGeneratedScenarioFingerprint(requestFingerprint);
      openModule("tasks");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function solveCurrent() {
    if (!scenario) return;
    const requestScenario = scenario;
    const requestFingerprint = scenarioFingerprintForSolve(requestScenario);
    setBusy("solving");
    setError(null);
    try {
      await solveWith(requestScenario, requestFingerprint);
      openModule("results");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function solveMinResources() {
    if (!scenario) return;
    const requestScenario = scenario;
    const requestFingerprint = scenarioFingerprintForSolve(requestScenario);
    const hasHardMilestone = scenario.milestones.some((milestone) => milestone.mode === "hard");
    const matchingSolveResult = solveResultScenarioFingerprint === requestFingerprint ? solveResult : null;
    const fallbackTargetDays = matchingSolveResult?.result.objective_days ?? null;
    if (!hasHardMilestone && !fallbackTargetDays) {
      setError("请先运行“固定资源条件下，推算最短工期”，或设置至少一个可匹配的强制里程碑目标。");
      return;
    }
    setBusy("minResources");
    setError(null);
    try {
      const solved = await apiPost<ScenarioSolveResult>("/api/solve-min-resources", {
        scenario: requestScenario,
        fallback_target_days: fallbackTargetDays,
      });
      setGenerated(solved.generated);
      setGeneratedScenarioFingerprint(requestFingerprint);
      setSolveResult(solved);
      setSolveResultScenarioFingerprint(requestFingerprint);
      openModule("results");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function solveWith(nextScenario: ScenarioInput, fingerprint = scenarioFingerprintForSolve(nextScenario)) {
    const solved = await apiPost<ScenarioSolveResult>("/api/solve-scenario", nextScenario);
    setGenerated(solved.generated);
    setGeneratedScenarioFingerprint(fingerprint);
    setSolveResult(solved);
    setSolveResultScenarioFingerprint(fingerprint);
  }

  async function compareSavedResults(nextResults = savedResults) {
    if (!nextResults.length) return;
    setBusy("comparing");
    setError(null);
    try {
      const nextComparison = await apiPost<CompareResponse>("/api/compare-scenarios", { results: nextResults });
      setComparison(nextComparison);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function importBridgeParams(file: File, targetBridge: string) {
    if (!scenario) return;
    setBusy("importing");
    setError(null);
    try {
      const payload = new FormData();
      payload.append("file", file);
      payload.append("scenario", JSON.stringify(scenario));
      if (targetBridge.trim()) {
        payload.append("target_bridge", targetBridge.trim());
      }
      const imported = await apiPostFormData<ImportBridgeParamsResponse>("/api/import-bridge-params", payload);
      setScenario(imported.scenario);
      setGenerated(null);
      setGeneratedScenarioFingerprint(null);
      setSolveResult(null);
      setSolveResultScenarioFingerprint(null);
      setComparison(null);
      setLastImport(imported);
      setActiveTab("project");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function applyProcessNaturalLanguage(prompt: string): Promise<ProcessNlResponse | null> {
    if (!scenario) return null;
    setBusy("nl");
    setError(null);
    try {
      const result = await apiPost<ProcessNlResponse>("/api/apply-process-natural-language", { scenario, prompt });
      setScenario(result.scenario);
      if (hasProcessLibraryChanged(scenario.process_library, result.scenario.process_library)) {
        setProcessLibraryDirty(true);
      }
      setGenerated(null);
      setGeneratedScenarioFingerprint(null);
      setSolveResult(null);
      setSolveResultScenarioFingerprint(null);
      setComparison(null);
      return result;
    } catch (err) {
      setError(errorText(err));
      return null;
    } finally {
      setBusy(null);
    }
  }

  function saveCurrentResult() {
    if (!currentSolveResult) return;
    const nextResult = {
      ...currentSolveResult,
      scenario_id: `${currentSolveResult.scenario_id}-${savedResults.length + 1}`,
      scenario_name: `${currentSolveResult.scenario_name} #${savedResults.length + 1}`,
    };
    const nextResults = [...savedResults, nextResult];
    setSavedResults(nextResults);
    void compareSavedResults(nextResults);
  }

  function patchScenario(patch: Partial<ScenarioInput>) {
    setScenario((current) => (current ? { ...current, ...patch } : current));
  }

  function openModule(tabKey: TabKey) {
    setOpenTabs((current) => (current.includes(tabKey) ? current : [...current, tabKey]));
    setActiveTab(tabKey);
  }

  function closeModule(tabKey: TabKey) {
    setOpenTabs((current) => {
      const nextTabs = current.filter((key) => key !== tabKey);
      if (activeTab === tabKey) {
        const closedIndex = current.indexOf(tabKey);
        const nextIndex = Math.min(closedIndex, nextTabs.length - 1);
        setActiveTab(nextTabs[nextIndex] ?? null);
      } else if (activeTab && !nextTabs.includes(activeTab)) {
        setActiveTab(nextTabs[0] ?? null);
      }
      return nextTabs;
    });
  }

  function patchProject(patch: Partial<ProjectModel>) {
    setScenario((current) =>
      current ? { ...current, project: { ...current.project, ...patch } } : current,
    );
  }

  function updateProcess(index: number, patch: Partial<ProcessTemplate>) {
    setProcessLibraryDirty(true);
    setScenario((current) =>
      current
        ? {
            ...current,
            process_library: current.process_library.map((process, processIndex) =>
              processIndex === index ? { ...process, ...patch } : process,
            ),
          }
        : current,
    );
  }

  async function saveCurrentProcessLibrary() {
    if (!scenario) return;
    setBusy("savingProcessLibrary");
    setError(null);
    try {
      const processLibrary = await apiPut<ProcessTemplate[]>("/api/process-library", {
        process_library: scenario.process_library,
      });
      setScenario((current) => (current ? { ...current, process_library: processLibrary } : current));
      setProcessLibraryDirty(false);
      setGenerated(null);
      setGeneratedScenarioFingerprint(null);
      setSolveResult(null);
      setSolveResultScenarioFingerprint(null);
      setComparison(null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  function updateLogic(index: number, patch: Partial<LogicRule>) {
    setScenario((current) =>
      current
        ? {
            ...current,
            logic_rules: current.logic_rules.map((rule, ruleIndex) =>
              ruleIndex === index ? { ...rule, ...patch } : rule,
            ),
          }
        : current,
    );
  }

  function updateUpperStructureLogic(ruleId: string, patch: Partial<UpperStructureLogicRule>) {
    setScenario((current) =>
      current
        ? {
            ...current,
            upper_structure_logic_rules: mergeUpperStructureLogicRules(current.upper_structure_logic_rules).map((rule) =>
              rule.id === ruleId ? { ...rule, ...patch } : rule,
            ),
          }
        : current,
    );
  }

  function updateResourcePool(index: number, patch: Partial<ResourcePool>) {
    setScenario((current) =>
      current
        ? {
            ...current,
            resource_pools: current.resource_pools.map((pool, poolIndex) =>
              poolIndex === index ? { ...pool, ...patch } : pool,
            ),
          }
        : current,
    );
  }

  function updateMilestone(index: number, patch: Partial<MilestoneConstraint>) {
    setScenario((current) =>
      current
        ? {
            ...current,
            milestones: current.milestones.map((milestone, milestoneIndex) =>
              milestoneIndex === index ? { ...milestone, ...patch } : milestone,
            ),
          }
        : current,
    );
  }

  function updateComponent(componentId: string, patch: Partial<ComponentModel>) {
    setScenario((current) => {
      if (!current) return current;
      return {
        ...current,
        project: {
          ...current.project,
          bridges: current.project.bridges.map((bridge) => ({
            ...bridge,
            work_sections: bridge.work_sections.map((section) => ({
              ...section,
              structures: section.structures.map((structure) => ({
                ...structure,
                components: structure.components.map((component) =>
                  component.id === componentId ? { ...component, ...patch } : component,
                ),
              })),
            })),
          })),
        },
      };
    });
  }

  function renderModule(tabKey: TabKey) {
    if (!scenario && tabKey !== "results") {
      return <div className="empty">正在加载场景...</div>;
    }

    switch (tabKey) {
      case "project":
        return scenario ? (
          <ProjectTab
            scenario={scenario}
            flatStructures={flatStructures}
            onUpdateComponent={updateComponent}
            onImportBridgeParams={importBridgeParams}
            onApplyProcessNaturalLanguage={applyProcessNaturalLanguage}
            importing={busy === "importing"}
            applyingProcessText={busy === "nl"}
          />
        ) : null;
      case "process":
        return scenario ? (
          <ProcessTab
            scenario={scenario}
            onUpdateProcess={updateProcess}
            onSaveProcessLibrary={saveCurrentProcessLibrary}
            savingProcessLibrary={busy === "savingProcessLibrary"}
            processLibraryDirty={processLibraryDirty}
          />
        ) : null;
      case "logic":
        return scenario ? (
          <LogicTab
            scenario={scenario}
            onUpdateLogic={updateLogic}
            onUpdateUpperStructureLogic={updateUpperStructureLogic}
          />
        ) : null;
      case "resources":
        return scenario ? <ResourcesTab scenario={scenario} onUpdateResourcePool={updateResourcePool} /> : null;
      case "milestones":
        return scenario ? <MilestonesTab scenario={scenario} onUpdateMilestone={updateMilestone} /> : null;
      case "tasks":
        return scenario ? (
          <TaskViewTab
            scenario={scenario}
            generated={currentGenerated}
            solveResult={currentSolveResult}
            onGenerateTaskView={generateOnly}
            busy={busy}
          />
        ) : null;
      case "results":
        return (
          <ResultsTab
            scenario={scenario}
            generated={currentGenerated}
            solveResult={currentSolveResult}
            onPatchScenario={patchScenario}
            onPatchProject={patchProject}
            onSolveCurrent={solveCurrent}
            onSolveMinResources={solveMinResources}
            busy={busy}
            ganttMode={ganttMode}
            onGanttModeChange={setGanttMode}
            onSaveCurrent={saveCurrentResult}
            savedResults={savedResults}
            comparison={comparison}
            onCompare={() => void compareSavedResults()}
            comparing={busy === "comparing"}
          />
        );
    }
  }

  return (
    <div className="app-shell">
      <div className="app-body">
        <SideNavigation activeTab={activeTab} openTabs={openTabs} onOpen={openModule} />

        <main className="workspace">
          <WorkspaceTabStrip
            openTabs={openTabs}
            activeTab={activeTab}
            onSelect={setActiveTab}
            onClose={closeModule}
          />
        {error && (
          <section className="notice error">
            <AlertCircle size={18} />
            <span>{error}</span>
          </section>
        )}

        <div className="workspace-content">
        {scenario && activeTab === "project" && (
          <ProjectTab
            scenario={scenario}
            flatStructures={flatStructures}
            onUpdateComponent={updateComponent}
            onImportBridgeParams={importBridgeParams}
            onApplyProcessNaturalLanguage={applyProcessNaturalLanguage}
            importing={busy === "importing"}
            applyingProcessText={busy === "nl"}
          />
        )}
        {scenario && activeTab === "process" && (
          <ProcessTab
            scenario={scenario}
            onUpdateProcess={updateProcess}
            onSaveProcessLibrary={saveCurrentProcessLibrary}
            savingProcessLibrary={busy === "savingProcessLibrary"}
            processLibraryDirty={processLibraryDirty}
          />
        )}
        {scenario && activeTab === "logic" && (
          <LogicTab
            scenario={scenario}
            onUpdateLogic={updateLogic}
            onUpdateUpperStructureLogic={updateUpperStructureLogic}
          />
        )}
        {scenario && activeTab === "resources" && (
          <ResourcesTab scenario={scenario} onUpdateResourcePool={updateResourcePool} />
        )}
        {scenario && activeTab === "milestones" && (
          <MilestonesTab scenario={scenario} onUpdateMilestone={updateMilestone} />
        )}
        {scenario && activeTab === "tasks" && (
          <TaskViewTab
            scenario={scenario}
            generated={currentGenerated}
            solveResult={currentSolveResult}
            onGenerateTaskView={generateOnly}
            busy={busy}
          />
        )}
        {activeTab === "results" && (
          <ResultsTab
            scenario={scenario}
            generated={currentGenerated}
            solveResult={currentSolveResult}
            onPatchScenario={patchScenario}
            onPatchProject={patchProject}
            onSolveCurrent={solveCurrent}
            onSolveMinResources={solveMinResources}
            busy={busy}
            ganttMode={ganttMode}
            onGanttModeChange={setGanttMode}
            onSaveCurrent={saveCurrentResult}
            savedResults={savedResults}
            comparison={comparison}
            onCompare={() => void compareSavedResults()}
            comparing={busy === "comparing"}
          />
        )}
        </div>
      </main>
    </div>
    </div>
  );
}

function ProjectTab({
  scenario,
  flatStructures,
  onUpdateComponent,
  onImportBridgeParams,
  onApplyProcessNaturalLanguage,
  importing,
  applyingProcessText,
}: {
  scenario: ScenarioInput;
  flatStructures: ReturnType<typeof flattenStructures>;
  onUpdateComponent: (componentId: string, patch: Partial<ComponentModel>) => void;
  onImportBridgeParams: (file: File, targetBridge: string) => void;
  onApplyProcessNaturalLanguage: (prompt: string) => Promise<ProcessNlResponse | null>;
  importing: boolean;
  applyingProcessText: boolean;
}) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [processPrompt, setProcessPrompt] = useState("");
  const [processNlResult, setProcessNlResult] = useState<ProcessNlResponse | null>(null);
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [structureFilters, setStructureFilters] = useState<StructureFilters>({
    workpointLabel: "",
    bridgeAndSection: "",
    structureLevel: "",
    sideLabel: "",
    location: "",
    name: "",
    typeLabel: "",
    dimension: "",
    processLabel: "",
    productivityLabel: "",
  });
  const structureRows = buildStructureRows(scenario.project, scenario.process_library);
  const filteredStructureRows = filterStructureRows(structureRows, structureFilters);

  async function submitProcessPrompt() {
    if (!processPrompt.trim() || applyingProcessText) return;
    const result = await onApplyProcessNaturalLanguage(processPrompt);
    if (result) setProcessNlResult(result);
  }

  function useAssistantExample(prompt: string) {
    setProcessPrompt(prompt);
    setAssistantOpen(true);
  }

  return (
    <div className="tab-grid project-tab-grid">
      <section className="panel full project-structure-panel">
        <PanelTitle
          title="结构构件清单"
          subtitle={`${filteredStructureRows.length} / ${structureRows.length} 项，结构尺寸和桩基工艺会进入任务生成层`}
          action={
            <div className="structure-import-action">
              <input
                type="file"
                accept=".xlsx,.xlsm"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
              <button
                className="secondary"
                type="button"
                disabled={!selectedFile || importing}
                onClick={() => selectedFile && onImportBridgeParams(selectedFile, "")}
              >
                {importing ? <Loader2 className="spin" size={16} /> : <Upload size={16} />}
                导入 Excel
              </button>
            </div>
          }
        />
        <div className="table-wrap tall project-structure-table">
          <table>
            <thead>
              <tr>
                <th>工点</th>
                <th>桥梁 / 工区</th>
                <th>结构层级</th>
                <th>幅别</th>
                <th>位置</th>
                <th>构件</th>
                <th>类型</th>
                <th>结构尺寸</th>
                <th>工艺</th>
                <th>工效</th>
              </tr>
              <tr className="filter-row">
                <th>
                  <input value={structureFilters.workpointLabel} onChange={(event) => setStructureFilters((current) => ({ ...current, workpointLabel: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.bridgeAndSection} onChange={(event) => setStructureFilters((current) => ({ ...current, bridgeAndSection: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <select value={structureFilters.structureLevel} onChange={(event) => setStructureFilters((current) => ({ ...current, structureLevel: event.target.value }))}>
                    <option value="">全部</option>
                    <option value="下部结构">下部结构</option>
                    <option value="上部结构">上部结构</option>
                  </select>
                </th>
                <th>
                  <select value={structureFilters.sideLabel} onChange={(event) => setStructureFilters((current) => ({ ...current, sideLabel: event.target.value }))}>
                    <option value="">全部</option>
                    <option value="左幅">左幅</option>
                    <option value="右幅">右幅</option>
                    <option value="无幅别">无幅别</option>
                  </select>
                </th>
                <th>
                  <input value={structureFilters.location} onChange={(event) => setStructureFilters((current) => ({ ...current, location: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.name} onChange={(event) => setStructureFilters((current) => ({ ...current, name: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.typeLabel} onChange={(event) => setStructureFilters((current) => ({ ...current, typeLabel: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.dimension} onChange={(event) => setStructureFilters((current) => ({ ...current, dimension: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.processLabel} onChange={(event) => setStructureFilters((current) => ({ ...current, processLabel: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.productivityLabel} onChange={(event) => setStructureFilters((current) => ({ ...current, productivityLabel: event.target.value }))} placeholder="筛选" />
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredStructureRows.map((row) => {
                const processOptions = row.component ? processOptionsForComponent(row.component, scenario.process_library) : [];
                const selectedProcess = row.component ? selectedProcessForComponent(row.component, scenario.process_library) : null;
                const productivityOptions = selectedProcess ? processProductivityOptions(selectedProcess) : [];
                const selectedProductivity = row.component && selectedProcess ? selectedProductivityOption(row.component, selectedProcess) : null;
                const showProcessSelect = processOptions.length > 1 || (processOptions.length > 0 && !selectedProcess);
                const showProductivitySelect = Boolean(selectedProcess && selectedProductivity && productivityOptions.length > 1);

                return (
                  <tr key={row.id}>
                    <td><span className="tag">{row.workpointLabel}</span></td>
                    <td>{row.bridgeAndSection}</td>
                    <td><span className="tag">{row.structureLevel}</span></td>
                    <td>{row.sideLabel}</td>
                    <td>{row.location}</td>
                    <td>{row.name}</td>
                    <td><span className="tag">{row.typeLabel}</span></td>
                    <td className="note-cell">{row.dimension}</td>
                    <td>
                      {row.component && processOptions.length > 0 ? (
                        showProcessSelect ? (
                          <select
                            value={selectedProcess?.id ?? ""}
                            onChange={(event) => {
                              const nextProcess = processOptions.find((process) => process.id === event.target.value);
                              if (!nextProcess) return;
                              const nextDefault = defaultProductivityOption(nextProcess);
                              onUpdateComponent(row.component!.id, {
                                method_id: nextProcess.method_id ?? nextProcess.id,
                                productivity_option_id: nextDefault?.id ?? null,
                              });
                            }}
                          >
                            {!selectedProcess && <option value="">请选择工艺</option>}
                            {processOptions.map((process) => (
                              <option key={process.id} value={process.id}>{process.process_name}</option>
                            ))}
                          </select>
                        ) : (
                          <code>-</code>
                        )
                      ) : (
                        <code>-</code>
                      )}
                    </td>
                    <td>
                      {selectedProcess && selectedProductivity ? (
                        showProductivitySelect ? (
                          <select
                            value={selectedProductivity.id}
                            onChange={(event) => onUpdateComponent(row.component!.id, { productivity_option_id: event.target.value })}
                          >
                            {productivityOptions.map((option) => (
                              <option key={option.id} value={option.id}>{productivityOptionLabel(option)}</option>
                            ))}
                          </select>
                        ) : (
                          <span className="text-pill">{productivityOptionLabel(selectedProductivity)}</span>
                        )
                      ) : (
                        <code>{row.productivityLabel}</code>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      {assistantOpen ? (
        <aside className="nl-process-panel" aria-label="AI 操作助手">
          <div className="nl-process-title">
            <div className="nl-process-heading">
              <span className="assistant-mark"><Bot size={16} /></span>
              <div>
                <strong>AI 操作助手</strong>
                <span>自然语言快捷设置</span>
              </div>
            </div>
            <button className="icon-button" type="button" aria-label="收起 AI 操作助手" onClick={() => setAssistantOpen(false)}>
              <X size={16} />
            </button>
          </div>
          <textarea
            value={processPrompt}
            onChange={(event) => setProcessPrompt(event.target.value)}
            placeholder="例如：左幅的3#墩和4#墩的桩基工艺设置成人工挖孔。"
          />
          <div className="assistant-examples" aria-label="快捷示例">
            <button type="button" onClick={() => useAssistantExample("桩基默认采用旋挖钻施工，其中1#墩-1桩基、1#墩-2桩基采用人工挖孔桩。")}>
              默认旋挖
            </button>
            <button type="button" onClick={() => useAssistantExample("渠溪河大桥连续梁主墩使用爬模施工。")}>
              主墩爬模
            </button>
            <button type="button" onClick={() => useAssistantExample("左幅的3#墩和4#墩的桩基工艺设置成人工挖孔。")}>
              指定墩位
            </button>
          </div>
          <button className="primary assistant-submit" disabled={!processPrompt.trim() || applyingProcessText} onClick={submitProcessPrompt}>
            {applyingProcessText ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
            让助手执行
          </button>
          {processNlResult && (
            <div className="nl-process-result">
              {processNlResult.changes.map((change, index) => (
                <span key={`${change.action}-${index}`}>{change.message}</span>
              ))}
              {processNlResult.warnings.map((warning, index) => (
                <span className="warn" key={`${warning}-${index}`}>{warning}</span>
              ))}
            </div>
          )}
        </aside>
      ) : (
        <button className="assistant-launcher" type="button" aria-label="打开 AI 操作助手" onClick={() => setAssistantOpen(true)}>
          <Bot size={18} />
          <span>AI 助手</span>
        </button>
      )}
    </div>
  );
}

function ProcessTab({
  scenario,
  onUpdateProcess,
  onSaveProcessLibrary,
  savingProcessLibrary,
  processLibraryDirty,
}: {
  scenario: ScenarioInput;
  onUpdateProcess: (index: number, patch: Partial<ProcessTemplate>) => void;
  onSaveProcessLibrary: () => void;
  savingProcessLibrary: boolean;
  processLibraryDirty: boolean;
}) {
  const resourcePoolByType = new Map(scenario.resource_pools.map((pool) => [pool.type, pool]));

  function productivityOptions(process: ProcessTemplate): ProductivityOption[] {
    return process.productivity_options?.length
      ? process.productivity_options
      : [
          {
            id: `${process.id}-default`,
            name: "默认工效",
            duration_method: process.duration_method,
            quantity_source: process.quantity_source,
            productivity_value: process.productivity_value,
            productivity_unit: process.productivity_unit,
            standard_section_height_m: defaultStandardSectionHeightForUnit(process.productivity_unit),
            is_default: true,
          },
        ];
  }

  function patchProductivityOption(processIndex: number, optionId: string, patch: Partial<ProductivityOption>) {
    const process = scenario.process_library[processIndex];
    const nextOptions = productivityOptions(process).map((option) => {
      if (option.id !== optionId) return option;
      const nextOption = { ...option, ...patch };
      if (patch.productivity_unit && process.component_type === "pile") {
        const unitRule = pileProductivityUnitOptions.find((item) => item.unit === patch.productivity_unit);
        if (unitRule) {
          nextOption.duration_method = unitRule.duration_method;
          nextOption.quantity_source = unitRule.quantity_source;
        }
      }
      if (patch.productivity_unit && supportsSegmentedPierUnits(process)) {
        const unitRule = segmentedPierProductivityUnitOptions.find((item) => item.unit === patch.productivity_unit);
        if (unitRule) {
          nextOption.duration_method = unitRule.duration_method;
          nextOption.quantity_source = unitRule.quantity_source;
          nextOption.standard_section_height_m = unitRule.unit === "天/节"
            ? sectionHeightForOption(nextOption)
            : undefined;
        }
      }
      return nextOption;
    });
    updateProcessWithOptions(processIndex, nextOptions);
  }

  function addProductivityOption(processIndex: number) {
    const process = scenario.process_library[processIndex];
    const options = productivityOptions(process);
    const defaultOption = options.find((option) => option.is_default) ?? options[0];
    updateProcessWithOptions(processIndex, [
      ...options,
      {
        ...defaultOption,
        id: `${process.id}-option-${Date.now()}`,
        name: `工效分组${options.length + 1}`,
        is_default: false,
      },
    ]);
  }

  function removeProductivityOption(processIndex: number, optionId: string) {
    const options = productivityOptions(scenario.process_library[processIndex]);
    if (options.length <= 1) return;
    const removed = options.find((option) => option.id === optionId);
    let nextOptions = options.filter((option) => option.id !== optionId);
    if (removed?.is_default) {
      nextOptions = nextOptions.map((option, index) => ({ ...option, is_default: index === 0 }));
    }
    updateProcessWithOptions(processIndex, nextOptions);
  }

  function setDefaultProductivityOption(processIndex: number, optionId: string) {
    updateProcessWithOptions(
      processIndex,
      productivityOptions(scenario.process_library[processIndex]).map((option) => ({ ...option, is_default: option.id === optionId })),
    );
  }

  function updateProcessWithOptions(processIndex: number, options: ProductivityOption[]) {
    const process = scenario.process_library[processIndex];
    const normalizedByUnit = options.map((option) => normalizeProductivityOptionForProcess(process, option));
    const defaultOption = normalizedByUnit.find((option) => option.is_default) ?? normalizedByUnit[0];
    const normalizedOptions = normalizedByUnit.map((option) => ({ ...option, is_default: option.id === defaultOption.id }));
    onUpdateProcess(processIndex, {
      productivity_options: normalizedOptions,
      duration_method: defaultOption.duration_method,
      quantity_source: defaultOption.quantity_source,
      productivity_value: defaultOption.productivity_value,
      productivity_unit: defaultOption.productivity_unit,
    });
  }

  const sortedProcessEntries = scenario.process_library
    .map((process, processIndex) => ({ process, processIndex }))
    .sort((left, right) => (
      componentSortIndex(left.process.component_type) - componentSortIndex(right.process.component_type)
      || left.processIndex - right.processIndex
    ));

  return (
    <section className="panel full process-library-panel">
      <PanelTitle
        title="施工工艺及工效库"
        subtitle="工艺模板按构件类型、适用工艺和默认资源类型维护"
        action={
          <button
            className="secondary"
            type="button"
            onClick={onSaveProcessLibrary}
            disabled={savingProcessLibrary || !processLibraryDirty}
            title="演示环境使用显式保存；实际工程应改为页面实时保存。"
            aria-label="保存工艺工效库"
          >
            {savingProcessLibrary ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
            保存
          </button>
        }
      />
      <div className="table-wrap process-library-table">
        <table>
          <thead>
            <tr>
              <th>构件</th>
              <th>工艺名称</th>
              <th>工期算法</th>
              <th>工程量来源</th>
              <th>工效分组</th>
              <th>默认资源</th>
            </tr>
          </thead>
          <tbody>
            {sortedProcessEntries.map(({ process, processIndex }) => {
              const currentPool = resourcePoolByType.get(process.resource_type);
              const options = productivityOptions(process);
              return (
                <tr key={process.id}>
                  <td><span className="tag">{componentLabels[process.component_type]}</span></td>
                  <td>
                    <span className="process-name-text">{process.process_name}</span>
                  </td>
                  <td><span className="text-pill">{durationMethodLabels[process.duration_method] ?? process.duration_method}</span></td>
                  <td><span className="text-pill">{quantitySourceLabels[process.quantity_source] ?? process.quantity_source}</span></td>
                  <td>
                    <div className="productivity-groups">
                      {options.map((option, optionIndex) => {
                        const isSegmentedPierProcess = supportsSegmentedPierUnits(process);
                        const showSectionHeight = isSectionBasedPierProductivity(option);
                        const isLastOption = optionIndex === options.length - 1;
                        return (
                          <div className={`productivity-group ${option.is_default ? "default" : ""}`} key={option.id}>
                            <input
                              className="productivity-name-input"
                              value={option.name}
                              onChange={(event) => patchProductivityOption(processIndex, option.id, { name: event.target.value })}
                            />
                            <input
                              type="number"
                              min={0.1}
                              step={0.1}
                              value={option.productivity_value}
                              onChange={(event) => patchProductivityOption(processIndex, option.id, { productivity_value: Number(event.target.value) })}
                              aria-label="工效值"
                            />
                            {process.component_type === "pile" ? (
                              <select
                                className="productivity-unit-control"
                                value={option.productivity_unit}
                                onChange={(event) => patchProductivityOption(processIndex, option.id, { productivity_unit: event.target.value })}
                              >
                                {pileProductivityUnitOptions.map((item) => (
                                  <option value={item.unit} key={item.unit}>{item.unit}</option>
                                ))}
                              </select>
                            ) : isSegmentedPierProcess ? (
                              <select
                                className="productivity-unit-control"
                                value={option.productivity_unit}
                                onChange={(event) => patchProductivityOption(processIndex, option.id, { productivity_unit: event.target.value })}
                              >
                                {segmentedPierProductivityUnitOptions.map((item) => (
                                  <option value={item.unit} key={item.unit}>{item.unit}</option>
                                ))}
                              </select>
                            ) : (
                              <span className="text-pill productivity-unit-control">{option.productivity_unit}</span>
                            )}
                            <span className="section-height-field">
                              {showSectionHeight ? (
                                <>
                                  <input
                                    type="number"
                                    min={0.1}
                                    step={0.1}
                                    value={sectionHeightForOption(option)}
                                    onChange={(event) => patchProductivityOption(processIndex, option.id, { standard_section_height_m: Number(event.target.value) })}
                                    aria-label="标准节高"
                                  />
                                  <span className="unit">m/节</span>
                                </>
                              ) : (
                                <span className="section-height-placeholder">-</span>
                              )}
                            </span>
                            <span className="text-pill productivity-source-pill">{quantitySourceLabels[option.quantity_source] ?? option.quantity_source}</span>
                            {option.is_default ? (
                              <span className="default-badge">默认分组</span>
                            ) : (
                              <button
                              className="mini-button set-default"
                              type="button"
                              onClick={() => setDefaultProductivityOption(processIndex, option.id)}
                            >
                                设为默认
                              </button>
                            )}
                            <button
                              className="mini-button"
                              type="button"
                              disabled={options.length <= 1}
                              onClick={() => removeProductivityOption(processIndex, option.id)}
                            >
                              删除
                            </button>
                            {isLastOption ? (
                              <button className="mini-button add" type="button" onClick={() => addProductivityOption(processIndex)}>
                                新增
                              </button>
                            ) : (
                              <span className="productivity-add-spacer" />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </td>
                  <td>
                    <select
                      value={process.resource_type}
                      onChange={(event) => onUpdateProcess(processIndex, { resource_type: event.target.value })}
                    >
                      {!currentPool && <option value={process.resource_type}>{process.resource_type}</option>}
                      {scenario.resource_pools.map((pool) => (
                        <option value={pool.type} key={pool.id}>{pool.label}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LogicTab({
  scenario,
  onUpdateLogic,
  onUpdateUpperStructureLogic,
}: {
  scenario: ScenarioInput;
  onUpdateLogic: (index: number, patch: Partial<LogicRule>) => void;
  onUpdateUpperStructureLogic: (ruleId: string, patch: Partial<UpperStructureLogicRule>) => void;
}) {
  const upperLowerConstraints = buildUpperLowerLogicConstraints(scenario);

  const relationshipSelect = (
    value: RelationshipType,
    onChange: (value: RelationshipType) => void,
  ) => (
    <select className="logic-relation-select" value={value} onChange={(event) => onChange(event.target.value as RelationshipType)}>
      <option value="FS">FS</option>
      <option value="SS">SS</option>
      <option value="FF">FF</option>
      <option value="SF">SF</option>
    </select>
  );
  const lagInput = (value: number, onChange: (value: number) => void) => (
    <div className="logic-lag-control">
      <input
        type="number"
        min={0}
        value={value}
        onChange={(event) => onChange(Math.max(0, Number(event.target.value) || 0))}
      />
      <span className="unit">自然日</span>
    </div>
  );

  return (
    <section className="panel full logic-panel">
      <PanelTitle title="工艺逻辑约束" subtitle="下部结构规则与桥梁上部结构派生约束使用同一套关系和间隔配置" />
      <div className="logic-content unified">
        <div className="logic-section-title">
          <div>
            <h3>规则配置</h3>
            <span>{scenario.logic_rules.length} 条下部规则 / {upperLowerConstraints.length} 条桥梁上部规则</span>
          </div>
          <span className="text-pill">关系与间隔进入排程求解</span>
        </div>
        <div className="table-wrap logic-unified">
          <table className="logic-unified-table">
            <thead>
              <tr>
                <th>规则</th>
                <th>当前 / 后续</th>
                <th>前置来源</th>
                <th>策略 / 生成</th>
                <th>关系</th>
                <th>间隔</th>
                <th>当前匹配</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              {scenario.logic_rules.map((rule, index) => (
                <tr key={rule.id}>
                  <td>
                    <div className="logic-rule-heading">
                      <span className="logic-source-badge lower">下部结构</span>
                      <div className="rule-name">{logicRuleDisplayName(rule)}</div>
                    </div>
                    <code className="muted-code">{rule.id}</code>
                  </td>
                  <td>{componentLabels[rule.to_component]}</td>
                  <td>{rule.predecessor_candidates.map((item) => componentLabels[item]).join(" / ")}</td>
                  <td>
                    <select
                      value={rule.predecessor_strategy}
                      onChange={(event) => onUpdateLogic(index, { predecessor_strategy: event.target.value as LogicRule["predecessor_strategy"] })}
                    >
                      <option value="first_available">优先回退</option>
                      <option value="all">全部满足</option>
                    </select>
                  </td>
                  <td>{relationshipSelect(rule.relationship, (relationship) => onUpdateLogic(index, { relationship }))}</td>
                  <td>{lagInput(rule.lag_days, (lag_days) => onUpdateLogic(index, { lag_days }))}</td>
                  <td><span className="logic-match muted">默认规则</span></td>
                  <td className="note-cell">{rule.note}</td>
                </tr>
              ))}
              {upperLowerConstraints.map((constraint) => (
                <tr key={constraint.id}>
                  <td>
                    <div className="logic-rule-heading">
                      <span className="logic-source-badge upper">桥梁上部</span>
                      <div className="rule-name">{constraint.name}</div>
                    </div>
                    <code className="muted-code">{constraint.id}</code>
                  </td>
                  <td>{constraint.upperTarget}</td>
                  <td>{constraint.lowerPredecessor}</td>
                  <td className="note-cell">{constraint.generation}</td>
                  <td>
                    {relationshipSelect(
                      constraint.relationship,
                      (relationship) => onUpdateUpperStructureLogic(constraint.id, { relationship }),
                    )}
                  </td>
                  <td>
                    {lagInput(
                      constraint.lagDays,
                      (lag_days) => onUpdateUpperStructureLogic(constraint.id, { lag_days }),
                    )}
                  </td>
                  <td><span className="logic-match">{constraint.matchedText}</span></td>
                  <td className="note-cell">{constraint.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function logicRuleDisplayName(rule: LogicRule): string {
  if (rule.note) {
    return rule.note.replace(/。$/, "");
  }
  const predecessors = rule.predecessor_candidates.map((item) => componentLabels[item]).join("、");
  return `${componentLabels[rule.to_component]}在${predecessors}之后施工`;
}

function ResourcesTab({
  scenario,
  onUpdateResourcePool,
}: {
  scenario: ScenarioInput;
  onUpdateResourcePool: (index: number, patch: Partial<ResourcePool>) => void;
}) {
  return (
    <section className="panel full">
      <PanelTitle title="资源配置约束" subtitle="资源池按数量自动展开为命名资源，求解器自动从候选资源中选择" />
      <div className="resource-grid">
        {scenario.resource_pools.map((pool, index) => (
          <div className="resource-card" key={pool.id}>
            <div>
              <strong>{pool.label}</strong>
              <code>{pool.type}</code>
            </div>
            <label>
              默认数量
              <input
                type="number"
                min={0}
                value={pool.quantity}
                onChange={(event) => {
                  const quantity = Number(event.target.value);
                  onUpdateResourcePool(index, { quantity, max_quantity: Math.max(pool.max_quantity ?? pool.quantity, quantity) });
                }}
              />
            </label>
            <label>
              最大数量
              <input
                type="number"
                min={pool.quantity}
                value={pool.max_quantity ?? pool.quantity}
                onChange={(event) => onUpdateResourcePool(index, { max_quantity: Math.max(Number(event.target.value), pool.quantity) })}
              />
            </label>
            <label>
              日历
              <select value={pool.calendar_id} onChange={(event) => onUpdateResourcePool(index, { calendar_id: event.target.value })}>
                {scenario.resource_calendars.map((calendar) => (
                  <option value={calendar.id} key={calendar.id}>{calendar.name}</option>
                ))}
              </select>
            </label>
            <label className="check-row">
              <input
                type="checkbox"
                checked={pool.enabled}
                onChange={(event) => onUpdateResourcePool(index, { enabled: event.target.checked })}
              />
              启用
            </label>
          </div>
        ))}
      </div>
    </section>
  );
}

function MilestonesTab({
  scenario,
  onUpdateMilestone,
}: {
  scenario: ScenarioInput;
  onUpdateMilestone: (index: number, patch: Partial<MilestoneConstraint>) => void;
}) {
  return (
    <section className="panel full">
      <PanelTitle title="关键里程碑节点约束" subtitle="固定资源最短工期允许突破目标并给出偏差；固定工期最少资源会把强制目标作为不可突破工期" />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>节点</th>
              <th>等级</th>
              <th>约束</th>
              <th>范围</th>
              <th>事件</th>
              <th>目标日期</th>
              <th>罚分/天</th>
            </tr>
          </thead>
          <tbody>
            {scenario.milestones.map((milestone, index) => (
              <tr key={milestone.id}>
                <td>
                  <input
                    className="wide-input"
                    value={milestone.name}
                    onChange={(event) => onUpdateMilestone(index, { name: event.target.value })}
                  />
                </td>
                <td>
                  <select value={milestone.level} onChange={(event) => onUpdateMilestone(index, { level: event.target.value as MilestoneConstraint["level"] })}>
                    <option value="contract">合同</option>
                    <option value="control">强控</option>
                    <option value="internal">内部</option>
                  </select>
                </td>
                <td>
                  <select value={milestone.mode} onChange={(event) => onUpdateMilestone(index, { mode: event.target.value as MilestoneConstraint["mode"] })}>
                    <option value="hard">强制目标</option>
                    <option value="soft">提醒目标</option>
                  </select>
                </td>
                <td>{scopeLabel(milestone, scenario)}</td>
                <td>
                  <select
                    value={milestone.target_event}
                    onChange={(event) => onUpdateMilestone(index, { target_event: event.target.value as MilestoneConstraint["target_event"] })}
                  >
                    <option value="finish">完成</option>
                    <option value="start">开始</option>
                  </select>
                </td>
                <td>
                  <input
                    type="date"
                    value={milestone.target_date}
                    onChange={(event) => onUpdateMilestone(index, { target_date: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min={0}
                    value={milestone.penalty_per_day}
                    disabled={milestone.mode === "hard"}
                    onChange={(event) => onUpdateMilestone(index, { penalty_per_day: Number(event.target.value) })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TaskViewTab({
  scenario,
  generated,
  solveResult,
  onGenerateTaskView,
  busy,
}: {
  scenario: ScenarioInput;
  generated: GeneratedScheduleInput | null;
  solveResult: ScenarioSolveResult | null;
  onGenerateTaskView: () => void;
  busy: "loading" | "generating" | "solving" | "minResources" | "comparing" | "importing" | "nl" | "savingProcessLibrary" | null;
}) {
  const [groupMode, setGroupMode] = useState<TaskViewMode>("by_structure");
  const [filters, setFilters] = useState<TaskViewFilters>({
    structureText: "",
    processText: "",
  });
  const [openPredecessorTaskId, setOpenPredecessorTaskId] = useState<string | null>(null);
  const [predecessorAnchorRect, setPredecessorAnchorRect] = useState<DOMRect | null>(null);
  const predecessorHoverOpenTimerRef = useRef<number | null>(null);
  const predecessorHoverCloseTimerRef = useRef<number | null>(null);
  const generatedForDetails = solveResult?.generated ?? generated;
  const workSectionDisplayById = useMemo(
    () => buildWorkSectionDisplayById(scenario.project),
    [scenario.project],
  );
  const linksBySuccessor = useMemo(
    () => buildPredecessorLinksBySuccessor(generatedForDetails),
    [generatedForDetails],
  );
  const taskById = useMemo(
    () => new Map((generatedForDetails?.schedule_input.tasks ?? []).map((task) => [task.id, task])),
    [generatedForDetails],
  );
  const logicRuleById = useMemo(
    () => new Map(scenario.logic_rules.map((rule) => [rule.id, rule])),
    [scenario.logic_rules],
  );
  const rows = useMemo(
    () => buildTaskViewRows(generatedForDetails, scenario, linksBySuccessor, workSectionDisplayById),
    [generatedForDetails, linksBySuccessor, scenario, workSectionDisplayById],
  );
  const filteredRows = useMemo(() => filterTaskViewRows(rows, filters), [filters, rows]);
  const groups = useMemo(() => buildTaskViewGroups(filteredRows, groupMode), [filteredRows, groupMode]);
  const generating = busy === "generating";

  useEffect(() => () => {
    clearPredecessorHoverTimers(predecessorHoverOpenTimerRef, predecessorHoverCloseTimerRef);
  }, []);

  function closePredecessorPopover() {
    setOpenPredecessorTaskId(null);
    setPredecessorAnchorRect(null);
  }

  function showPredecessorPopover(taskId: string, anchor: HTMLElement) {
    clearPredecessorHoverTimers(predecessorHoverOpenTimerRef, predecessorHoverCloseTimerRef);
    predecessorHoverOpenTimerRef.current = window.setTimeout(() => {
      setPredecessorAnchorRect(anchor.getBoundingClientRect());
      setOpenPredecessorTaskId(taskId);
    }, PREDECESSOR_HOVER_DELAY_MS);
  }

  function schedulePredecessorPopoverClose() {
    clearPredecessorHoverTimer(predecessorHoverOpenTimerRef);
    clearPredecessorHoverTimer(predecessorHoverCloseTimerRef);
    predecessorHoverCloseTimerRef.current = window.setTimeout(closePredecessorPopover, PREDECESSOR_HOVER_CLOSE_DELAY_MS);
  }

  function keepPredecessorPopoverOpen() {
    clearPredecessorHoverTimer(predecessorHoverCloseTimerRef);
  }

  function predecessorDetails(row: TaskViewRow): PredecessorDetail[] {
    return row.predecessorLinks.map((link) => {
      const predecessor = taskById.get(link.predecessor_id);
      return {
        predecessorId: link.predecessor_id,
        predecessor,
        predecessorSideLabel: predecessor ? workSectionLabelForTask(predecessor, workSectionDisplayById) : "-",
        link,
        rule: logicRuleById.get(link.source_rule_id),
      };
    });
  }

  return (
    <div className="task-view-grid">
      <section className="panel full task-view-header-panel">
        <PanelTitle
          title="任务视图"
          subtitle="调用 OR-Tools CP-SAT 前核验结构物识别、工期计算和工艺逻辑关系"
          action={
            <div className="task-view-title-actions">
              {generatedForDetails && (
                <div className="segmented">
                  <button className={groupMode === "by_structure" ? "active" : ""} type="button" onClick={() => setGroupMode("by_structure")}>
                    按墩号
                  </button>
                  <button className={groupMode === "by_process" ? "active" : ""} type="button" onClick={() => setGroupMode("by_process")}>
                    按工艺
                  </button>
                </div>
              )}
              <button className="secondary" type="button" onClick={onGenerateTaskView} disabled={generating || !scenario}>
              {generating ? <Loader2 className="spin" size={16} /> : <ClipboardList size={16} />}
              {generatedForDetails ? "刷新任务视图" : "生成任务视图"}
              </button>
            </div>
          }
        />
        {!generatedForDetails && (
          <div className="task-view-empty">
            <ClipboardList size={34} />
            <strong>尚未生成求解前任务图</strong>
            <span>生成后可按墩号或工艺核验任务、工期和前置关系；此操作不会调用 CP-SAT。</span>
          </div>
        )}
        {generatedForDetails && (
          <div className="task-view-filters">
            <label>
              结构物
              <input
                value={filters.structureText}
                onChange={(event) => setFilters((current) => ({ ...current, structureText: event.target.value }))}
                placeholder="桥梁、工区、幅别、墩号、任务"
              />
            </label>
            <label>
              工艺 / 构件
              <input
                value={filters.processText}
                onChange={(event) => setFilters((current) => ({ ...current, processText: event.target.value }))}
                placeholder="工艺名称或构件类型"
              />
            </label>
          </div>
        )}
      </section>

      {generatedForDetails && (
        <>
          <section className="panel full task-view-panel">
            <PanelTitle
              title="任务清单"
              subtitle={groupMode === "by_structure" ? "按墩号从小到大展示，组内按工序顺序排列" : "按工艺聚合，组内仍按墩号从小到大排列"}
            />
            <div className="task-view-groups">
              {groups.length > 0 ? (
                groups.map((group) => (
                  <div className="task-view-group" key={group.id}>
                    <div className="task-view-group-title">
                      <strong>{group.title}</strong>
                      <span>{taskViewGroupSubtitle(group.rows, groupMode, scenario)}</span>
                    </div>
                    <div className="table-wrap task-view-table-wrap">
                      <table className="task-view-table">
                        <thead>
                          <tr>
                            <th>桥梁 / 工区</th>
                            <th>幅别</th>
                            <th>墩号 / 结构物</th>
                            <th>构件</th>
                            <th>任务名称</th>
                            <th>工艺</th>
                            <th>工程量</th>
                            <th>工期</th>
                            <th>工期计算</th>
                            <th>候选资源</th>
                            <th>前置</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.rows.map((row) => {
                            const isOpen = openPredecessorTaskId === row.task.id;
                            return (
                              <tr key={`${group.id}-${row.task.id}`}>
                                <td>{row.bridgeName} / {row.sectionName}</td>
                                <td><span className="side-tag">{row.sideLabel}</span></td>
                                <td>{row.structureLabel}</td>
                                <td><span className="tag">{componentLabels[row.task.component_type]}</span></td>
                                <td>{row.task.name}</td>
                                <td>{row.task.process_name}</td>
                                <td>{row.task.quantity_label || displayValue(row.task.quantity)}</td>
                                <td>{effectiveTaskDurationDays(row.task, scenario)} 天</td>
                                <td className="duration-expression" title={durationExpression(row.task, scenario)}>
                                  {durationExpression(row.task, scenario)}
                                </td>
                                <td>{row.task.compatible_resource_types.join(" / ")}</td>
                                <td className="predecessor-cell">
                                  {row.predecessorLinks.length > 0 ? (
                                    <button
                                      className="predecessor-count has-items"
                                      type="button"
                                      onMouseEnter={(event) => showPredecessorPopover(row.task.id, event.currentTarget)}
                                      onMouseLeave={schedulePredecessorPopoverClose}
                                      onFocus={(event) => showPredecessorPopover(row.task.id, event.currentTarget)}
                                      onBlur={schedulePredecessorPopoverClose}
                                      aria-expanded={isOpen}
                                    >
                                      {row.predecessorLinks.length}
                                    </button>
                                  ) : (
                                    <span className="predecessor-zero">0</span>
                                  )}
                                  {isOpen && (
                                    <PredecessorPopover
                                      task={row.task}
                                      details={predecessorDetails(row)}
                                      anchorRect={predecessorAnchorRect}
                                      onMouseEnter={keepPredecessorPopoverOpen}
                                      onMouseLeave={schedulePredecessorPopoverClose}
                                    />
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))
              ) : (
                <div className="empty">当前筛选条件下没有任务</div>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function ResultsTab({
  scenario,
  generated,
  solveResult,
  onPatchScenario,
  onPatchProject,
  onSolveCurrent,
  onSolveMinResources,
  busy,
  ganttMode,
  onGanttModeChange,
  onSaveCurrent,
  savedResults,
  comparison,
  onCompare,
  comparing,
}: {
  scenario: ScenarioInput | null;
  generated: GeneratedScheduleInput | null;
  solveResult: ScenarioSolveResult | null;
  onPatchScenario: (patch: Partial<ScenarioInput>) => void;
  onPatchProject: (patch: Partial<ProjectModel>) => void;
  onSolveCurrent: () => void;
  onSolveMinResources: () => void;
  busy: "loading" | "generating" | "solving" | "minResources" | "comparing" | "importing" | "nl" | "savingProcessLibrary" | null;
  ganttMode: GanttMode;
  onGanttModeChange: (mode: GanttMode) => void;
  onSaveCurrent: () => void;
  savedResults: ScenarioSolveResult[];
  comparison: CompareResponse | null;
  onCompare: () => void;
  comparing: boolean;
}) {
  const [openPredecessorTaskId, setOpenPredecessorTaskId] = useState<string | null>(null);
  const [predecessorAnchorRect, setPredecessorAnchorRect] = useState<DOMRect | null>(null);
  const predecessorHoverOpenTimerRef = useRef<number | null>(null);
  const predecessorHoverCloseTimerRef = useRef<number | null>(null);
  const result = solveResult?.result ?? null;
  const planStatus = useMemo(() => derivePlanStatus(result), [result]);
  const summary = useMemo(() => buildSummary(scenario, generated, solveResult), [scenario, generated, solveResult]);
  const generatedForDetails = solveResult?.generated ?? generated;
  const recommendedResourceCounts = recommendedResourceCountsFromResult(result);
  const continuityMetrics = continuityMetricsFromResult(result);
  const workSectionDisplayById = useMemo(
    () => buildWorkSectionDisplayById(scenario?.project ?? null),
    [scenario?.project],
  );
  const diagnostics = useMemo(() => {
    const messages = solveResult?.diagnostics ?? generated?.validation ?? [];
    if (!planStatus.diagnostic) return messages;
    const alreadyIncluded = messages.some((message) => message.subject_id === planStatus.diagnostic?.subject_id);
    return alreadyIncluded ? messages : [planStatus.diagnostic, ...messages];
  }, [generated, planStatus.diagnostic, solveResult]);
  const scheduledTaskById = useMemo(
    () => new Map((result?.tasks ?? []).map((task) => [task.id, task])),
    [result],
  );
  const linksBySuccessor = useMemo(() => {
    const links = new Map<string, PrecedenceLink[]>();
    for (const link of generatedForDetails?.schedule_input.precedence_links ?? []) {
      const current = links.get(link.successor_id) ?? [];
      current.push(link);
      links.set(link.successor_id, current);
    }
    return links;
  }, [generatedForDetails]);
  const logicRuleById = useMemo(
    () => new Map((scenario?.logic_rules ?? []).map((rule) => [rule.id, rule])),
    [scenario],
  );

  useEffect(() => () => {
    clearPredecessorHoverTimers(predecessorHoverOpenTimerRef, predecessorHoverCloseTimerRef);
  }, []);

  function closePredecessorPopover() {
    setOpenPredecessorTaskId(null);
    setPredecessorAnchorRect(null);
  }

  function showPredecessorPopover(taskId: string, anchor: HTMLElement) {
    clearPredecessorHoverTimers(predecessorHoverOpenTimerRef, predecessorHoverCloseTimerRef);
    predecessorHoverOpenTimerRef.current = window.setTimeout(() => {
      setPredecessorAnchorRect(anchor.getBoundingClientRect());
      setOpenPredecessorTaskId(taskId);
    }, PREDECESSOR_HOVER_DELAY_MS);
  }

  function schedulePredecessorPopoverClose() {
    clearPredecessorHoverTimer(predecessorHoverOpenTimerRef);
    clearPredecessorHoverTimer(predecessorHoverCloseTimerRef);
    predecessorHoverCloseTimerRef.current = window.setTimeout(closePredecessorPopover, PREDECESSOR_HOVER_CLOSE_DELAY_MS);
  }

  function keepPredecessorPopoverOpen() {
    clearPredecessorHoverTimer(predecessorHoverCloseTimerRef);
  }

  function predecessorDetails(task: ScheduledTask): PredecessorDetail[] {
    const links = linksBySuccessor.get(task.id) ?? [];
    return task.predecessor_ids.map((predecessorId) => {
      const predecessor = scheduledTaskById.get(predecessorId);
      const link = links.find((item) => item.predecessor_id === predecessorId);
      const rule = link ? logicRuleById.get(link.source_rule_id) : undefined;
      return {
        predecessorId,
        predecessor,
        predecessorSideLabel: predecessor ? workSectionLabelForTask(predecessor, workSectionDisplayById) : "-",
        link,
        rule,
      };
    });
  }

  return (
    <div className="results-grid">
      {scenario && (
        <section className="panel full simulation-params-panel">
          <PanelTitle
            title="模拟参数"
            subtitle="方案、计划起点和求解配置"
            action={
              <div className="actions inline">
                <button className="primary" onClick={onSolveCurrent} disabled={Boolean(busy) || !scenario}>
                  {busy === "solving" || busy === "loading" ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
                  固定资源条件下，推算最短工期
                </button>
                <button className="secondary" onClick={onSolveMinResources} disabled={Boolean(busy) || !scenario}>
                  {busy === "minResources" ? <Loader2 className="spin" size={16} /> : <Server size={16} />}
                  固定工期条件下，推算最少资源
                </button>
              </div>
            }
          />
          <div className="form-grid">
            <label>
              方案名称
              <input value={scenario.scenario_name} onChange={(event) => onPatchScenario({ scenario_name: event.target.value })} />
            </label>
            <label>
              项目名称
              <input value={scenario.project.project_name} onChange={(event) => onPatchProject({ project_name: event.target.value })} />
            </label>
            <label>
              计划开始
              <input type="date" value={scenario.project.start_date} onChange={(event) => onPatchProject({ start_date: event.target.value })} />
            </label>
            <label>
              求解时限(秒)
              <input
                type="number"
                min={1}
                value={scenario.time_limit_seconds}
                onChange={(event) => onPatchScenario({ time_limit_seconds: Number(event.target.value) })}
              />
            </label>
          </div>
        </section>
      )}

      <section className="summary-band">
        <Metric label="计划状态" value={planStatus.label} tone={planStatus.tone} hint={planStatus.hint} icon={<Server size={18} />} />
        <Metric label="总工期" value={summary.days} tone="neutral" icon={<CalendarDays size={18} />} />
        <Metric label="工作项" value={summary.tasks} tone="neutral" icon={<CheckCircle2 size={18} />} />
        <Metric label="资源 / 里程碑" value={summary.resourcesAndMilestones} tone="neutral" icon={<Flag size={18} />} />
      </section>

      <section className="panel full">
        <div className="panel-title">
          <div>
            <h2>约束诊断</h2>
            <span>生成层、求解层和里程碑检查的摘要</span>
          </div>
          <div className="actions inline">
            <button className="secondary" onClick={onSaveCurrent} disabled={!solveResult}>
              <Save size={15} />
              保存方案
            </button>
            <button className="secondary" onClick={onCompare} disabled={!savedResults.length || comparing}>
              {comparing ? <Loader2 className="spin" size={15} /> : <GitCompare size={15} />}
              对比
            </button>
          </div>
        </div>
        <div className="diagnostics">
          {diagnostics.slice(0, 12).map((message, index) => (
            <div className={`diagnostic ${message.level}`} key={`${message.subject_id ?? "message"}-${index}`}>
              <strong>{diagnosticLevelLabels[message.level]}</strong>
              <span>{message.message}</span>
            </div>
          ))}
          {!solveResult && !generated && <div className="empty">等待生成或求解</div>}
        </div>
      </section>

      {recommendedResourceCounts.length > 0 && (
        <section className="panel full">
          <PanelTitle title="推荐资源数量" subtitle="固定工期条件下推算的最少并行资源" />
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>资源</th>
                  <th>推荐数量</th>
                  <th>最大数量</th>
                </tr>
              </thead>
              <tbody>
                {recommendedResourceCounts.map((item) => (
                  <tr key={item.resource_pool_id}>
                    <td>{item.label}</td>
                    <td>{item.recommended_quantity}</td>
                    <td>{item.max_quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="panel full">
        <PanelTitle title="里程碑结果" subtitle="软节点允许超期，迟延天数会进入加权目标" />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>节点</th>
                <th>约束</th>
                <th>目标</th>
                <th>实际</th>
                <th>迟延</th>
                <th>罚分</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {result?.milestone_results.map((milestone) => (
                <tr key={milestone.id}>
                  <td>{milestone.name}</td>
                  <td>{milestone.mode === "hard" ? "强制目标" : "提醒目标"}</td>
                  <td>{milestone.target_date}</td>
                  <td>{milestone.actual_date ?? "-"}</td>
                  <td>{milestone.lateness_days} 天</td>
                  <td>{milestone.penalty}</td>
                  <td><span className={`status-pill ${milestoneStatusClass(milestone)}`}>{milestoneStatusLabels[milestone.status]}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel full">
        <PanelTitle
          title="计划表"
          subtitle={result?.plan_finish_date ? `${result.plan_start_date} 至 ${result.plan_finish_date}` : "等待求解"}
        />
        <div className="table-wrap plan">
          <table>
            <thead>
              <tr>
                <th>工作项</th>
                <th>幅别</th>
                <th>构件</th>
                <th>计划表达式</th>
                <th>工期</th>
                <th>计划开始</th>
                <th>计划完成</th>
                <th>资源</th>
                <th>前置数</th>
              </tr>
            </thead>
            <tbody>
              {result?.tasks.map((task) => {
                const isOpen = openPredecessorTaskId === task.id;
                return (
                  <tr key={task.id}>
                    <td>{task.name}</td>
                    <td><span className="side-tag">{workSectionLabelForTask(task, workSectionDisplayById)}</span></td>
                    <td><span className="tag">{componentLabels[task.component_type]}</span></td>
                    <td className="duration-expression" title={durationExpression(task, scenario)}>
                      {durationExpression(task, scenario)}
                    </td>
                    <td>{effectiveTaskDurationDays(task, scenario)} 天</td>
                    <td>{task.start_date}</td>
                    <td>{task.finish_date}</td>
                    <td>{task.assigned_resource_name ?? "-"}</td>
                    <td className="predecessor-cell">
                      {task.predecessor_ids.length > 0 ? (
                        <button
                          className="predecessor-count has-items"
                          type="button"
                          onMouseEnter={(event) => showPredecessorPopover(task.id, event.currentTarget)}
                          onMouseLeave={schedulePredecessorPopoverClose}
                          onFocus={(event) => showPredecessorPopover(task.id, event.currentTarget)}
                          onBlur={schedulePredecessorPopoverClose}
                          aria-expanded={isOpen}
                        >
                          {task.predecessor_ids.length}
                        </button>
                      ) : (
                        <span className="predecessor-zero">0</span>
                      )}
                      {isOpen && (
                        <PredecessorPopover
                          task={task}
                          details={predecessorDetails(task)}
                          anchorRect={predecessorAnchorRect}
                          onMouseEnter={keepPredecessorPopoverOpen}
                          onMouseLeave={schedulePredecessorPopoverClose}
                        />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel full">
        <div className="panel-title">
          <div>
            <h2>甘特图</h2>
            <span>{ganttMode === "by_structure" ? "按墩台聚类，墩号从小到大" : "按工艺聚类，子级按计划先后展示"}</span>
          </div>
          <div className="segmented">
            <button className={ganttMode === "by_structure" ? "active" : ""} onClick={() => onGanttModeChange("by_structure")}>
              按墩台
            </button>
            <button className={ganttMode === "by_process" ? "active" : ""} onClick={() => onGanttModeChange("by_process")}>
              按工艺
            </button>
          </div>
        </div>
        <Gantt
          tasks={result?.tasks ?? []}
          makespan={Math.max(result?.objective_days ?? 1, 1)}
          mode={ganttMode}
          workSectionDisplayById={workSectionDisplayById}
        />
      </section>

      <section className="panel full">
        <PanelTitle title="资源泳道" subtitle="横轴按计划时间展示每条资源的占用连续性" />
        <ResourceLanes
          allocations={result?.resource_allocations ?? []}
          makespan={Math.max(result?.objective_days ?? 1, 1)}
        />
      </section>

      <section className="panel full">
        <PanelTitle title="资源路径图" subtitle="按施工先后展示资源经过的左/右幅-墩号序列" />
        <ResourcePathChart resourcePaths={continuityMetrics?.resource_paths ?? []} />
      </section>

      <section className="panel full">
        <PanelTitle title="方案对比" subtitle={`${savedResults.length} 个已保存方案`} />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>方案</th>
                <th>状态</th>
                <th>总工期</th>
                <th>软节点迟延数</th>
                <th>软罚分</th>
                <th>综合分</th>
              </tr>
            </thead>
            <tbody>
              {comparison?.summaries.map((item) => (
                <tr key={String(item.scenario_id)}>
                  <td>{String(item.scenario_name)}</td>
                  <td>{formatScheduleStatus(item.status)}</td>
                  <td>{String(item.total_days ?? "-")}</td>
                  <td>{String(item.soft_late_count ?? 0)}</td>
                  <td>{String(item.soft_penalty ?? 0)}</td>
                  <td>{String(item.score ?? "-")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

type PredecessorDetail = {
  predecessorId: string;
  predecessor?: Task;
  predecessorSideLabel?: string;
  link?: PrecedenceLink;
  rule?: LogicRule;
};

function PredecessorPopover({
  task,
  details,
  anchorRect,
  onMouseEnter,
  onMouseLeave,
}: {
  task: Task;
  details: PredecessorDetail[];
  anchorRect: DOMRect | null;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}) {
  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      className="predecessor-popover"
      style={predecessorPopoverStyle(anchorRect)}
      onPointerDown={(event) => event.stopPropagation()}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {details.length ? (
        <div className="predecessor-list">
          {details.map((detail) => (
            <div className="predecessor-item" key={`${task.id}-${detail.predecessorId}-${detail.link?.id ?? "missing"}`}>
              <div className="predecessor-item-title">
                {detail.predecessorSideLabel && detail.predecessorSideLabel !== "-" && (
                  <span className="side-tag mini">{detail.predecessorSideLabel}</span>
                )}
                <strong>{detail.predecessor?.name ?? detail.predecessorId}</strong>
                {detail.link && <span className="predecessor-relation-token">{formatPrecedenceToken(detail.link)}</span>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="predecessor-empty">这个工作项可以直接作为起始工作安排。</div>
      )}
    </div>,
    document.body,
  );
}

function clearPredecessorHoverTimer(timerRef: { current: number | null }) {
  if (timerRef.current === null) return;
  window.clearTimeout(timerRef.current);
  timerRef.current = null;
}

function clearPredecessorHoverTimers(
  openTimerRef: { current: number | null },
  closeTimerRef: { current: number | null },
) {
  clearPredecessorHoverTimer(openTimerRef);
  clearPredecessorHoverTimer(closeTimerRef);
}

function predecessorPopoverStyle(anchorRect: DOMRect | null): CSSProperties {
  if (typeof window === "undefined") return {};
  const margin = 12;
  const width = Math.min(360, Math.max(280, window.innerWidth - margin * 2));
  const maxHeight = Math.min(360, Math.max(180, window.innerHeight - margin * 2));
  const fallbackTop = Math.min(96, Math.max(margin, window.innerHeight - maxHeight - margin));

  if (!anchorRect) {
    return {
      top: fallbackTop,
      left: Math.max(margin, window.innerWidth - width - 24),
      width,
      maxHeight,
    };
  }

  const preferredLeft = anchorRect.right - width;
  const left = Math.min(
    Math.max(margin, preferredLeft),
    Math.max(margin, window.innerWidth - width - margin),
  );
  const belowTop = anchorRect.bottom + 8;
  const shouldOpenAbove = belowTop + Math.min(maxHeight, 240) > window.innerHeight - margin
    && anchorRect.top > window.innerHeight / 2;
  const top = shouldOpenAbove
    ? Math.max(margin, anchorRect.top - maxHeight - 8)
    : Math.min(belowTop, Math.max(margin, window.innerHeight - 140));

  return { top, left, width, maxHeight };
}

function formatPrecedenceToken(link?: PrecedenceLink): string {
  if (!link) return "-";
  return `${link.relationship}+${link.lag_days}`;
}

function Metric({
  label,
  value,
  tone,
  hint,
  icon,
}: {
  label: string;
  value: string;
  tone: MetricTone;
  hint?: string;
  icon: ReactNode;
}) {
  return (
    <div className={`metric ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {hint && <small>{hint}</small>}
      </div>
    </div>
  );
}

function PanelTitle({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return (
    <div className="panel-title">
      <div>
        <h2>{title}</h2>
        <span>{subtitle}</span>
      </div>
      {action && <div className="panel-title-action">{action}</div>}
    </div>
  );
}

function Gantt({
  tasks,
  makespan,
  mode,
  workSectionDisplayById,
}: {
  tasks: ScheduledTask[];
  makespan: number;
  mode: GanttMode;
  workSectionDisplayById: Map<string, WorkSectionDisplay>;
}) {
  if (!tasks.length) return <div className="empty">暂无排程结果</div>;
  const groups = buildGanttGroups(tasks, mode, workSectionDisplayById);
  return (
    <div className="gantt">
      {groups.map((group) => (
        <div className="gantt-group" key={group.id}>
          <div className="gantt-group-title">
            <strong>{group.title}</strong>
            <span>{group.startDate} 至 {group.finishDate}</span>
          </div>
          {group.tasks.map((task) => {
            const sideLabel = workSectionLabelForTask(task, workSectionDisplayById);
            return (
              <div className="gantt-row" key={task.id}>
                <div className="gantt-label">
                  {sideLabel !== "-" && <span className="side-tag mini">{sideLabel}</span>}
                  <span className="gantt-task-name">{task.name}</span>
                </div>
                <div className="gantt-track">
                  <div
                    className="gantt-bar"
                    style={{
                      left: `${(task.start_offset / makespan) * 100}%`,
                      width: `${Math.max(((task.end_offset - task.start_offset) / makespan) * 100, 1.2)}%`,
                      backgroundColor: componentColors[task.component_type],
                    }}
                    title={ganttTaskHoverTitle(task, sideLabel)}
                  >
                    <span>{task.duration_days}d</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function ResourceLanes({
  allocations,
  makespan,
}: {
  allocations: ResourceAllocation[];
  makespan: number;
}) {
  if (!allocations.length) return <div className="empty">暂无资源分配</div>;
  const groups = groupBy(allocations, (item) => item.resource_id);
  return (
    <div className="lanes">
      {Object.entries(groups).map(([, items]) => (
        <div className="lane-row" key={items[0].resource_id}>
          <div className="lane-label">
            <strong>{items[0].resource_name}</strong>
            <code>{items[0].resource_type}</code>
          </div>
          <div className="lane-track">
            {items.map((allocation) => (
              <div
                className="lane-bar"
                key={allocation.task_id}
                style={{
                  left: `${(allocation.start_offset / makespan) * 100}%`,
                  width: `${Math.max(((allocation.end_offset - allocation.start_offset) / makespan) * 100, 1.2)}%`,
                }}
                title={allocationHoverTitle(allocation)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function ResourcePathChart({ resourcePaths }: { resourcePaths: ResourcePath[] }) {
  const visiblePaths = resourcePaths.filter((path) => path.path.length > 0);
  if (!visiblePaths.length) return <div className="empty">暂无资源路径</div>;
  return (
    <div className="resource-path-chart">
      {visiblePaths.map((path) => {
        const labels = compactPathLabels(path.path.map((step) => shortLocationLabel(step.location)));
        return (
          <div className="resource-path-row" key={path.resource_id}>
            <div className="resource-path-label">
              <strong>{path.resource_name}</strong>
            </div>
            <div className="resource-path-sequence" title={resourcePathHoverTitle(path, labels)}>
              {labels.map((label, index) => (
                <span className="resource-path-step" key={`${path.resource_id}-${label}-${index}`}>
                  {label}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ganttTaskHoverTitle(task: ScheduledTask, sideLabel = "-"): string {
  return [
    `工作项：${task.name}`,
    `幅别：${sideLabel}`,
    `构件：${componentLabels[task.component_type]}`,
    `计划：${task.start_date} 至 ${task.finish_date}`,
    `工期：${task.duration_days} 天`,
    `分配资源：${task.assigned_resource_name ?? "-"}`,
    `资源序列：${task.assigned_resource_id ?? "-"}`,
    `资源类型：${task.assigned_resource_type ?? "-"}`,
  ].join("\n");
}

function allocationHoverTitle(allocation: ResourceAllocation): string {
  return [
    `工作项：${allocation.task_name}`,
    `计划：${allocation.start_date} 至 ${allocation.finish_date}`,
    `分配资源：${allocation.resource_name}`,
    `资源序列：${allocation.resource_id}`,
    `资源类型：${allocation.resource_type}`,
  ].join("\n");
}

function resourcePathHoverTitle(path: ResourcePath, labels: string[]): string {
  return [
    `资源：${path.resource_name}`,
    `资源类型：${path.resource_type}`,
    `施工路径：${labels.join("-")}`,
    `任务数：${path.task_count}`,
  ].join("\n");
}

function compactPathLabels(labels: string[]): string[] {
  const compacted: string[] = [];
  for (const label of labels) {
    if (!label || compacted[compacted.length - 1] === label) continue;
    compacted.push(label);
  }
  return compacted;
}

function shortLocationLabel(location: string): string {
  const sidePrefix = location.includes("左幅") ? "左" : location.includes("右幅") ? "右" : "";
  const numberMatch = location.match(/(\d+)\s*号[墩台]?/);
  if (sidePrefix && numberMatch) return `${sidePrefix}${numberMatch[1]}`;
  if (numberMatch) return numberMatch[1];
  return location.replace(/幅/g, "").replace(/号墩/g, "").replace(/号台/g, "").replace(/\s+/g, "");
}

type WorkSectionDisplay = {
  label: string;
  shortLabel: string;
};

function buildWorkSectionDisplayById(project: ProjectModel | null): Map<string, WorkSectionDisplay> {
  const result = new Map<string, WorkSectionDisplay>();
  if (!project) return result;
  for (const bridge of project.bridges) {
    for (const section of bridge.work_sections) {
      const hasSide = section.side && section.side !== "none";
      const label = hasSide ? sideLabels[section.side] : section.name || "-";
      const shortLabel = section.side === "left" ? "左" : section.side === "right" ? "右" : label;
      result.set(section.id, { label, shortLabel });
    }
  }
  return result;
}

function workSectionLabelForTask(task: Task, workSectionDisplayById: Map<string, WorkSectionDisplay>): string {
  if (!task.work_section_id) return "-";
  return workSectionDisplayById.get(task.work_section_id)?.label ?? "-";
}

function titleWithWorkSectionLabel(title: string, task: Task, workSectionDisplayById: Map<string, WorkSectionDisplay>): string {
  const sideLabel = workSectionLabelForTask(task, workSectionDisplayById);
  if (sideLabel === "-" || title.includes(sideLabel)) return title;
  return `${sideLabel} ${title}`;
}

function buildGanttGroups(
  tasks: ScheduledTask[],
  mode: GanttMode,
  workSectionDisplayById: Map<string, WorkSectionDisplay>,
) {
  if (mode === "by_process") {
    return componentOrder
      .map((component) => {
        const children = tasks
          .filter((task) => task.component_type === component)
          .sort((a, b) => a.start_offset - b.start_offset || compareStructureIds(a.structure_id, b.structure_id));
        return { id: component, title: componentLabels[component], tasks: children, ...taskDateRange(children) };
      })
      .filter((group) => group.tasks.length > 0);
  }

  return Object.entries(groupBy(tasks, (task) => task.structure_id))
    .sort(([left], [right]) => compareStructureIds(left, right))
    .map(([structureId, children]) => ({
      id: structureId,
      title: titleWithWorkSectionLabel(children[0].structure_name, children[0], workSectionDisplayById),
      tasks: children.sort(
        (a, b) =>
          componentOrder.indexOf(a.component_type) - componentOrder.indexOf(b.component_type)
          || a.start_offset - b.start_offset
          || a.name.localeCompare(b.name),
      ),
      ...taskDateRange(children),
    }));
}

function buildPredecessorLinksBySuccessor(generated: GeneratedScheduleInput | null): Map<string, PrecedenceLink[]> {
  const links = new Map<string, PrecedenceLink[]>();
  for (const link of generated?.schedule_input.precedence_links ?? []) {
    const current = links.get(link.successor_id) ?? [];
    current.push(link);
    links.set(link.successor_id, current);
  }
  return links;
}

function buildTaskViewRows(
  generated: GeneratedScheduleInput | null,
  scenario: ScenarioInput | null,
  linksBySuccessor: Map<string, PrecedenceLink[]>,
  workSectionDisplayById: Map<string, WorkSectionDisplay>,
): TaskViewRow[] {
  if (!generated) return [];
  const projectMaps = buildTaskViewProjectMaps(scenario?.project ?? null);
  const rows = generated.schedule_input.tasks.map((task) => {
    const bridge = task.bridge_id ? projectMaps.bridges.get(task.bridge_id) : undefined;
    const section = task.work_section_id ? projectMaps.sections.get(task.work_section_id) : undefined;
    const structure = projectMaps.structures.get(task.structure_id);
    const bridgeName = bridge?.name ?? task.bridge_id ?? "-";
    const sectionName = section?.name ?? task.work_section_id ?? "-";
    const sideLabel = workSectionLabelForTask(task, workSectionDisplayById);
    const structureLabel = structure?.label ?? task.structure_name;
    const continuousParent = continuousTaskParentDisplay(task, projectMaps.continuousBeamGroups);
    const componentLabel = componentLabels[task.component_type];
    const searchText = [
      bridgeName,
      sectionName,
      sideLabel,
      structureLabel,
      continuousParent?.label,
      task.structure_name,
      task.name,
      componentLabel,
      task.process_name,
    ].join(" ").toLowerCase();

    return {
      task,
      bridgeName,
      bridgeOrder: bridge?.order ?? Number.MAX_SAFE_INTEGER,
      sectionName,
      sectionOrder: section?.order ?? Number.MAX_SAFE_INTEGER,
      sideLabel,
      structureLabel,
      parentStructureId: continuousParent?.id ?? task.structure_id,
      parentStructureLabel: continuousParent?.label ?? structureLabel,
      predecessorLinks: linksBySuccessor.get(task.id) ?? [],
      searchText,
    };
  });
  return sortTaskViewRows(rows);
}

function buildTaskViewProjectMaps(project: ProjectModel | null) {
  const bridges = new Map<string, { name: string; order: number }>();
  const sections = new Map<string, { name: string; order: number }>();
  const structures = new Map<string, { label: string; order: number }>();
  const continuousBeamGroups = new Map<string, { id: string; label: string }>();

  if (!project) return { bridges, sections, structures, continuousBeamGroups };
  for (const bridge of project.bridges) {
    bridges.set(bridge.id, { name: bridge.name, order: bridge.order });
    for (const section of bridge.work_sections) {
      sections.set(section.id, { name: section.name, order: section.order });
      for (const uppers of groupUpperStructures(section.upper_structures ?? [], isContinuousBeamUpper)) {
        const groupIndex = upperGroupIndex(uppers[0]);
        continuousBeamGroups.set(
          continuousTaskParentKey(bridge.id, section.id, groupIndex),
          {
            id: continuousTaskParentId(bridge.id, section.id, groupIndex),
            label: continuousBeamGroupLabel(section, uppers),
          },
        );
      }
      for (const structure of section.structures) {
        structures.set(structure.id, {
          label: structure.support_no ?? structure.name,
          order: structure.order,
        });
      }
    }
  }
  return { bridges, sections, structures, continuousBeamGroups };
}

function continuousTaskParentDisplay(
  task: Task,
  continuousBeamGroups: Map<string, { id: string; label: string }>,
): { id: string; label: string } | null {
  if (task.component_type !== "cast_in_place_continuous_beam") return null;
  if (!task.bridge_id || !task.work_section_id) return null;
  const groupIndex = continuousTaskGroupIndex(task.structure_id);
  if (groupIndex === null) return null;
  return continuousBeamGroups.get(continuousTaskParentKey(task.bridge_id, task.work_section_id, groupIndex))
    ?? {
      id: continuousTaskParentId(task.bridge_id, task.work_section_id, groupIndex),
      label: fallbackContinuousTaskParentLabel(task),
    };
}

function continuousTaskParentKey(bridgeId: string, sectionId: string, groupIndex: number): string {
  return `${bridgeId}:${sectionId}:${groupIndex}`;
}

function continuousTaskParentId(bridgeId: string, sectionId: string, groupIndex: number): string {
  return `${bridgeId}:${sectionId}:continuous-beam:${groupIndex}`;
}

function continuousTaskGroupIndex(structureId: string): number | null {
  const match = structureId.match(/-CB-G(\d+)/);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

function continuousBeamGroupLabel(section: WorkSection, uppers: UpperStructureModel[]): string {
  const sideLabel = section.side && section.side !== "none" ? sideLabels[section.side] : "";
  const supports = uppers.flatMap((upper) => supportIndicesFromText(upper.support_range));
  const minSupport = supports.length ? Math.min(...supports) : Math.max(0, Math.min(...uppers.map((upper) => upper.span_index)) - 1);
  const maxSupport = supports.length ? Math.max(...supports) : Math.max(...uppers.map((upper) => upper.span_index));
  if (Number.isFinite(minSupport) && Number.isFinite(maxSupport)) {
    return `${sideLabel}${minSupport}#-${maxSupport}#墩现浇连续梁`;
  }
  return `${sideLabel}现浇连续梁`;
}

function supportIndicesFromText(value: string): number[] {
  return Array.from(value.matchAll(/(\d+)\s*(?:#|号)?\s*(?:墩|台)?/g))
    .map((match) => Number(match[1]))
    .filter((item) => Number.isFinite(item));
}

function fallbackContinuousTaskParentLabel(task: Task): string {
  const match = task.structure_id.match(/-CB-G(\d+)/);
  const groupSuffix = match ? `第${Number(match[1])}联` : "";
  const sidePrefix = task.structure_name.includes("左幅") ? "左幅" : task.structure_name.includes("右幅") ? "右幅" : "";
  return `${sidePrefix}${groupSuffix}现浇连续梁`;
}

function sortTaskViewRows(rows: TaskViewRow[]): TaskViewRow[] {
  return [...rows].sort((left, right) => (
    left.bridgeOrder - right.bridgeOrder
    || left.sectionOrder - right.sectionOrder
    || left.task.sequence_order - right.task.sequence_order
    || compareStructureIds(left.task.structure_id, right.task.structure_id)
    || componentSortIndex(left.task.component_type) - componentSortIndex(right.task.component_type)
    || left.task.name.localeCompare(right.task.name)
  ));
}

function filterTaskViewRows(rows: TaskViewRow[], filters: TaskViewFilters): TaskViewRow[] {
  const structureNeedle = filters.structureText.trim().toLowerCase();
  const processNeedle = filters.processText.trim().toLowerCase();

  return rows.filter((row) => {
    if (structureNeedle && !row.searchText.includes(structureNeedle)) return false;
    if (processNeedle) {
      const processText = `${row.task.process_name} ${componentLabels[row.task.component_type]}`.toLowerCase();
      if (!processText.includes(processNeedle)) return false;
    }
    return true;
  });
}

function buildTaskViewGroups(rows: TaskViewRow[], mode: TaskViewMode): TaskViewGroup[] {
  const groups = new Map<string, TaskViewGroup>();
  for (const row of rows) {
    const id = mode === "by_process"
      ? `${row.task.component_type}:${row.task.process_name}`
      : `${row.task.bridge_id ?? "-"}:${row.task.work_section_id ?? "-"}:${row.parentStructureId}`;
    const title = mode === "by_process"
      ? `${componentLabels[row.task.component_type]} / ${row.task.process_name}`
      : taskViewStructureTitle(row);
    if (!groups.has(id)) {
      groups.set(id, { id, title, subtitle: "", rows: [] });
    }
    groups.get(id)!.rows.push(row);
  }
  return Array.from(groups.values()).map((group) => ({
    ...group,
    subtitle: taskViewGroupSubtitle(group.rows, mode),
  }));
}

function taskViewStructureTitle(row: TaskViewRow): string {
  if (row.sideLabel === "-" || row.parentStructureLabel.includes(row.sideLabel)) return row.parentStructureLabel;
  return `${row.sideLabel} ${row.parentStructureLabel}`;
}

function taskViewGroupSubtitle(rows: TaskViewRow[], mode: TaskViewMode, scenario: ScenarioInput | null = null): string {
  if (!rows.length) return "-";
  const first = rows[0];
  const structureCount = new Set(rows.map((row) => `${row.task.work_section_id ?? "-"}:${row.task.structure_id}`)).size;
  const base = mode === "by_process"
    ? `${structureCount} 个结构物`
    : `${first.bridgeName} / ${first.sectionName}`;
  return `${base} · ${rows.length} 项 · 工期合计 ${taskViewDurationTotal(rows, scenario)} 天`;
}

function taskViewDurationTotal(rows: TaskViewRow[], scenario: ScenarioInput | null = null): number {
  return rows.reduce((total, row) => total + effectiveTaskDurationDays(row.task, scenario), 0);
}

function taskViewDurationRange(rows: TaskViewRow[], scenario: ScenarioInput | null = null): string {
  if (!rows.length) return "-";
  const durations = rows.map((row) => effectiveTaskDurationDays(row.task, scenario));
  const min = Math.min(...durations);
  const max = Math.max(...durations);
  return min === max ? `${min} 天` : `${min}-${max} 天`;
}

function flattenStructures(project: ProjectModel) {
  return project.bridges.flatMap((bridge) =>
    bridge.work_sections.flatMap((section) =>
      section.structures.map((structure) => ({ bridge, section, structure })),
    ),
  );
}

function buildStructureRows(project: ProjectModel, processLibrary: ProcessTemplate[]) {
  return project.bridges.flatMap((bridge) =>
    bridge.work_sections.flatMap((section) => {
      const lowerRows = section.structures.flatMap((structure) =>
        structure.components.map((component) => {
          const processes = processOptionsForComponent(component, processLibrary);
          const process = selectedProcessForComponent(component, processLibrary);
          const productivityOption = process ? selectedProductivityOption(component, process) : null;
          return {
            id: component.id,
            workpointLabel: workpointLabels[bridge.workpoint_type ?? "bridge"],
            bridgeAndSection: `${bridge.name} / ${section.name}`,
            structureLevel: "下部结构",
            sideLabel: sideLabels[section.side ?? "none"],
            location: structure.support_no ?? structure.name,
            name: component.name,
            typeLabel: componentLabels[component.component_type],
            dimension: dimensionSummary(component),
            processLabel: processes.length > 1 ? process?.process_name ?? "未匹配工艺" : "-",
            productivityLabel: productivityOption ? productivityOptionLabel(productivityOption) : "-",
            order: structure.order * 100 + componentOrder.indexOf(component.component_type),
            component,
          };
        }),
      );
      const upperRows = (section.upper_structures ?? []).map((upper) => ({
        id: upper.id,
        workpointLabel: workpointLabels[bridge.workpoint_type ?? "bridge"],
        bridgeAndSection: `${bridge.name} / ${section.name}`,
        structureLevel: "上部结构",
        sideLabel: sideLabels[section.side ?? "none"],
        location: `第${upper.span_index}跨 ${upper.support_range}`,
        name: upper.name,
        typeLabel: upper.structure_type,
        dimension: upperStructureDimensionSummary(upper),
        processLabel: "-",
        productivityLabel: "-",
        order: 100000 + upper.span_index,
        component: undefined,
      }));
      return [...lowerRows, ...upperRows].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
    }),
  );
}

function processOptionsForComponent(component: ComponentModel, processLibrary: ProcessTemplate[]): ProcessTemplate[] {
  return processLibrary.filter((process) => process.component_type === component.component_type);
}

function selectedProcessForComponent(component: ComponentModel, processLibrary: ProcessTemplate[]): ProcessTemplate | null {
  const options = processOptionsForComponent(component, processLibrary);
  if (component.method_id) {
    return options.find((process) => process.id === component.method_id || process.method_id === component.method_id) ?? null;
  }
  return options.find((process) => process.is_default) ?? options[0] ?? null;
}

function processProductivityOptions(process: ProcessTemplate): ProductivityOption[] {
  if (process.productivity_options?.length) {
    return process.productivity_options;
  }
  return [
    {
      id: `${process.id}-default`,
      name: "默认工效",
      duration_method: process.duration_method,
      quantity_source: process.quantity_source,
      productivity_value: process.productivity_value,
      productivity_unit: process.productivity_unit,
      standard_section_height_m: defaultStandardSectionHeightForUnit(process.productivity_unit),
      is_default: true,
    },
  ];
}

function defaultProductivityOption(process: ProcessTemplate): ProductivityOption | null {
  const options = processProductivityOptions(process);
  return options.find((option) => option.is_default) ?? options[0] ?? null;
}

function selectedProductivityOption(component: ComponentModel, process: ProcessTemplate): ProductivityOption | null {
  const options = processProductivityOptions(process);
  if (component.productivity_option_id) {
    const selected = options.find((option) => option.id === component.productivity_option_id);
    if (selected) return selected;
  }
  return options.find((option) => option.is_default) ?? options[0] ?? null;
}

function productivityOptionLabel(option: ProductivityOption): string {
  const groupName = option.name.trim() === "默认工效" ? "默认" : option.name.trim() || "工效";
  const base = `${groupName}-${displayValue(option.productivity_value)}${option.productivity_unit}`;
  if (isSectionBasedPierProductivity(option)) {
    return `${base}（${displayValue(sectionHeightForOption(option))}m/节）`;
  }
  return base;
}

function productivityOptionForTask(task: Task, scenario: ScenarioInput | null): ProductivityOption | null {
  if (!scenario) return null;
  const [processId, optionId] = task.productivity_rule_id.split(":");
  const process = scenario.process_library.find((item) => item.id === processId)
    ?? scenario.process_library.find((item) => item.component_type === task.component_type && item.process_name === task.process_name);
  if (!process) return null;
  const options = processProductivityOptions(process);
  return options.find((option) => option.id === optionId)
    ?? options.find((option) => option.is_default)
    ?? options[0]
    ?? null;
}

function durationExpression(task: Task, scenario: ScenarioInput | null): string {
  const option = productivityOptionForTask(task, scenario);
  if (!option) {
    return `${displayValue(task.quantity)} -> ${task.duration_days}天`;
  }

  const isContinuousStandardSegment = isContinuousBeamStandardSegmentTask(task);
  const effectiveOption = isContinuousStandardSegment
    ? { ...option, duration_method: "days_per_unit", quantity_source: "count" }
    : option;
  const quantityName = quantitySourceLabels[effectiveOption.quantity_source] ?? "工程量";
  const quantityText = isContinuousStandardSegment
    ? (task.quantity_label || `${displayValue(task.quantity)}块`)
    : `${quantityName}${displayValue(task.quantity)}${quantityUnitForSource(effectiveOption.quantity_source)}`;
  const resultText = `${effectiveTaskDurationDays(task, scenario)}天`;

  if (isSectionBasedPierProductivity(effectiveOption)) {
    const sectionHeight = sectionHeightForOption(effectiveOption);
    if (sectionHeight) {
      const sectionCount = Math.max(1, Math.ceil(task.quantity / sectionHeight));
      return `${quantityText} / ${displayValue(sectionHeight)}m/节 = ${sectionCount}节；${sectionCount} × ${displayValue(effectiveOption.productivity_value)}天/节 = ${resultText}`;
    }
  }

  if (effectiveOption.duration_method === "units_per_day") {
    return `${quantityText} / ${displayValue(effectiveOption.productivity_value)}${effectiveOption.productivity_unit} = ${resultText}`;
  }

  if (effectiveOption.duration_method === "days_per_unit") {
    return `${quantityText} × ${displayValue(effectiveOption.productivity_value)}${effectiveOption.productivity_unit} = ${resultText}`;
  }

  return `${displayValue(effectiveOption.productivity_value)}${effectiveOption.productivity_unit} = ${resultText}`;
}

function quantityUnitForSource(quantitySource: string): string {
  if (quantitySource.endsWith("_m")) return "m";
  return "";
}

function effectiveTaskDurationDays(task: Task, scenario: ScenarioInput | null): number {
  const option = productivityOptionForTask(task, scenario);
  if (option && isContinuousBeamStandardSegmentTask(task)) {
    return Math.max(1, Math.ceil(task.quantity * option.productivity_value));
  }
  return task.duration_days;
}

function isContinuousBeamStandardSegmentTask(task: Task): boolean {
  return task.component_type === "cast_in_place_continuous_beam"
    && task.productivity_rule_id.startsWith("cast_in_place_continuous_standard_segment:");
}

function filterStructureRows(rows: StructureRow[], filters: StructureFilters): StructureRow[] {
  return rows.filter((row) =>
    Object.entries(filters).every(([key, value]) => {
      const needle = value.trim().toLowerCase();
      if (!needle) return true;
      return String(row[key as keyof StructureFilters]).toLowerCase().includes(needle);
    }),
  );
}

function upperStructureDimensionSummary(upper: UpperStructureModel): string {
  const parts = [`跨径${displayValue(upper.span_length_m)}m`];
  if (upper.beam_count_per_span) {
    parts.push(`${displayValue(upper.beam_count_per_span)}片`);
  }
  if (upper.structure_type.includes("连续") && upper.span_group_expression) {
    parts.push(`联跨${upper.span_group_expression}`);
  }
  return parts.join("，");
}

function buildUpperLowerLogicConstraints(scenario: ScenarioInput): UpperLowerLogicConstraint[] {
  const stats = countUpperLowerLogicTargets(scenario);
  const rulesById = new Map(mergeUpperStructureLogicRules(scenario.upper_structure_logic_rules).map((rule) => [rule.id, rule]));
  const matchedTextById: Record<string, string> = {
    cast_in_place_box_beam_after_lower_structure: `${stats.castInPlaceBoxGroupCount} 联`,
    continuous_beam_zero_block_after_main_pier_lower_structure: `${stats.continuousMainPierCount} 个T构`,
    continuous_beam_side_straight_after_edge_lower_structure: `${stats.continuousSideStraightCount} 个边跨`,
    continuous_beam_t_chain: `${stats.continuousMainPierCount} 个T构`,
    continuous_beam_side_closure: `${stats.continuousSideClosureCount} 个边跨`,
    continuous_beam_middle_closure: `${stats.continuousMiddleClosureCount} 个中跨`,
    continuous_beam_edge_before_middle_closure: `${stats.continuousMiddleClosureCount} 个中跨`,
    continuous_beam_middle_closure_sequence: `${stats.continuousMiddleClosureCount} 个中跨`,
  };
  return upperStructureLogicDefinitions.map((definition) => {
    const rule = rulesById.get(definition.id);
    return {
      ...definition,
      relationship: rule?.relationship ?? "FS",
      lagDays: rule?.lag_days ?? 0,
      matchedText: matchedTextById[definition.id] ?? "-",
      note: rule?.note || definition.note,
    };
  });
}

function countUpperLowerLogicTargets(scenario: ScenarioInput) {
  let castInPlaceBoxGroupCount = 0;
  let continuousMainPierCount = 0;
  let continuousSideStraightCount = 0;
  let continuousSideClosureCount = 0;
  let continuousMiddleClosureCount = 0;

  for (const bridge of scenario.project.bridges) {
    for (const section of bridge.work_sections) {
      const uppers = section.upper_structures ?? [];
      castInPlaceBoxGroupCount += groupUpperStructures(uppers, isCastInPlaceBoxBeamUpper).length;
      const continuousGroups = groupUpperStructures(uppers, isContinuousBeamUpper);
      for (const group of continuousGroups) {
        const mainSupportCount = continuousMainSupportCount(group);
        continuousMainPierCount += mainSupportCount;
        if (mainSupportCount > 0) {
          continuousSideStraightCount += 2;
          continuousSideClosureCount += 2;
          continuousMiddleClosureCount += Math.max(0, mainSupportCount - 1);
        }
      }
    }
  }

  return {
    castInPlaceBoxGroupCount,
    continuousMainPierCount,
    continuousSideStraightCount,
    continuousSideClosureCount,
    continuousMiddleClosureCount,
  };
}

function groupUpperStructures(
  uppers: UpperStructureModel[],
  predicate: (upper: UpperStructureModel) => boolean,
): UpperStructureModel[][] {
  const groups = new Map<number, UpperStructureModel[]>();
  for (const upper of uppers) {
    if (!predicate(upper)) continue;
    const groupIndex = upperGroupIndex(upper);
    groups.set(groupIndex, [...(groups.get(groupIndex) ?? []), upper]);
  }
  return Array.from(groups.values())
    .map((items) => [...items].sort((a, b) => a.span_index - b.span_index))
    .sort((a, b) => Math.min(...a.map((item) => item.span_index)) - Math.min(...b.map((item) => item.span_index)));
}

function isSimpleBeamUpper(upper: UpperStructureModel): boolean {
  if (upperStructureCode(upper) === upperStructureCodes.simpleBeam) return true;
  if (isContinuousBeamUpper(upper) || isCastInPlaceBoxBeamUpper(upper)) return false;
  return upper.structure_type.includes("简支") || upper.structure_type.includes("T梁");
}

function isCastInPlaceBoxBeamUpper(upper: UpperStructureModel): boolean {
  if (upperStructureCode(upper) === upperStructureCodes.castInPlaceBoxBeam) return true;
  return upper.structure_type.includes("现浇")
    && upper.structure_type.includes("箱梁")
    && !isContinuousBeamUpper(upper);
}

function isContinuousBeamUpper(upper: UpperStructureModel): boolean {
  if (upperStructureCode(upper) === upperStructureCodes.continuousBeam) return true;
  return upper.structure_type.includes("连续") || upper.structure_type.includes("刚构");
}

function upperStructureCode(upper: UpperStructureModel): string {
  return String(upper.properties.structure_code ?? "");
}

function upperGroupIndex(upper: UpperStructureModel): number {
  const value = Number(upper.properties.group_index ?? upper.span_index);
  return Number.isFinite(value) ? Math.trunc(value) : upper.span_index;
}

function continuousMainSupportCount(uppers: UpperStructureModel[]): number {
  const configured = continuousNumberListSetting(uppers, ["main_support_indices", "main_pier_indices"]);
  if (configured.length) return new Set(configured).size;
  const spanIndices = uppers.map((upper) => upper.span_index);
  if (spanIndices.length < 2) return 0;
  return Math.max(...spanIndices) - Math.min(...spanIndices);
}

function continuousNumberListSetting(uppers: UpperStructureModel[], keys: string[]): number[] {
  for (const upper of uppers) {
    const nested = upper.properties.continuous_beam;
    if (nested && typeof nested === "object" && !Array.isArray(nested)) {
      const record = nested as Record<string, unknown>;
      for (const key of keys) {
        const numbers = numberListFromUnknown(record[key]);
        if (numbers.length) return numbers;
      }
    }
    for (const key of keys) {
      const numbers = numberListFromUnknown(upper.properties[key]);
      if (numbers.length) return numbers;
    }
  }
  return [];
}

function numberListFromUnknown(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item))
    .map((item) => Math.trunc(item));
}

function buildSummary(
  scenario: ScenarioInput | null,
  generated: GeneratedScheduleInput | null,
  solveResult: ScenarioSolveResult | null,
) {
  const recommendedCounts = recommendedResourceCountsFromResult(solveResult?.result ?? null);
  const resourceCount = recommendedCounts.length
    ? recommendedCounts.reduce((sum, item) => sum + item.recommended_quantity, 0)
    : generated?.schedule_input.resources.length
    ?? scenario?.resource_pools.reduce((sum, pool) => sum + (pool.enabled ? pool.quantity : 0), 0)
    ?? 0;
  const milestoneCount = scenario?.milestones.length ?? 0;
  return {
    days: solveResult?.result.objective_days ? `${solveResult.result.objective_days} 天` : "-",
    tasks: generated?.schedule_input.tasks.length ? `${generated.schedule_input.tasks.length} 项` : "-",
    resourcesAndMilestones: `${resourceCount} / ${milestoneCount}`,
  };
}

function importComponentCountSummary(summary: Record<string, unknown>): string {
  const lower = summary.lowerComponentCount;
  const upper = summary.upperComponentCount;
  if (lower !== undefined || upper !== undefined) {
    return `${displayValue(lower)} 下部 / ${displayValue(upper)} 上部`;
  }
  return `${displayValue(summary.componentCount)} 构件`;
}

function recommendedResourceCountsFromResult(result: ScheduleResult | null): Array<{
  resource_pool_id: string;
  label: string;
  recommended_quantity: number;
  max_quantity: number;
}> {
  const raw = result?.stats?.recommended_resource_counts ?? result?.objective_breakdown?.recommended_resource_counts;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      resource_pool_id: String(item.resource_pool_id ?? item.resource_type ?? item.label ?? ""),
      label: String(item.label ?? item.resource_type ?? "-"),
      recommended_quantity: Number(item.recommended_quantity ?? 0),
      max_quantity: Number(item.max_quantity ?? 0),
    }))
    .filter((item) => item.resource_pool_id);
}

function continuityMetricsFromResult(result: ScheduleResult | null): ContinuityMetrics | null {
  const raw = result?.stats?.continuity_metrics;
  if (!isRecord(raw)) return null;
  const splitDetails = Array.isArray(raw.same_structure_craft_split_details)
    ? raw.same_structure_craft_split_details.filter(isRecord).map((item) => ({
      structure_id: String(item.structure_id ?? ""),
      structure_name: String(item.structure_name ?? "-"),
      component_label: String(item.component_label ?? item.component_type ?? "-"),
      process_name: String(item.process_name ?? "-"),
      resource_count: Number(item.resource_count ?? 0),
      resource_names: Array.isArray(item.resource_names) ? item.resource_names.map(String) : [],
    }))
    : [];
  const jumpDetails = Array.isArray(raw.jump_transition_details)
    ? raw.jump_transition_details.filter(isRecord).map((item) => ({
      resource_id: String(item.resource_id ?? ""),
      resource_name: String(item.resource_name ?? item.resource_id ?? "-"),
      from_location: String(item.from_location ?? "-"),
      to_location: String(item.to_location ?? "-"),
      jump_distance: item.jump_distance === null || item.jump_distance === undefined ? null : Number(item.jump_distance),
      is_jump_pier: Boolean(item.is_jump_pier),
      is_side_switch: Boolean(item.is_side_switch),
      is_cross_side_jump: Boolean(item.is_cross_side_jump),
      is_direction_reversal: Boolean(item.is_direction_reversal),
    }))
    : [];
  return {
    continuity_score: Number(raw.continuity_score ?? 0),
    same_structure_craft_split_count: Number(raw.same_structure_craft_split_count ?? 0),
    jump_pier_count: Number(raw.jump_pier_count ?? 0),
    max_jump_distance: Number(raw.max_jump_distance ?? 0),
    side_switch_count: Number(raw.side_switch_count ?? 0),
    cross_side_jump_count: Number(raw.cross_side_jump_count ?? 0),
    direction_reversal_count: Number(raw.direction_reversal_count ?? 0),
    same_structure_craft_split_details: splitDetails,
    jump_transition_details: jumpDetails,
    resource_paths: Array.isArray(raw.resource_paths)
      ? raw.resource_paths.filter(isRecord).map((item) => ({
          resource_id: String(item.resource_id ?? ""),
          resource_name: String(item.resource_name ?? item.resource_id ?? "-"),
          resource_type: String(item.resource_type ?? ""),
          task_count: Number(item.task_count ?? 0),
          start_date: item.start_date ? String(item.start_date) : null,
          finish_date: item.finish_date ? String(item.finish_date) : null,
          jump_pier_count: Number(item.jump_pier_count ?? 0),
          side_switch_count: Number(item.side_switch_count ?? 0),
          cross_side_jump_count: Number(item.cross_side_jump_count ?? 0),
          path: Array.isArray(item.path)
            ? item.path.filter(isRecord).map((step) => ({
                task_id: String(step.task_id ?? ""),
                task_name: String(step.task_name ?? ""),
                location: String(step.location ?? ""),
                component_type: String(step.component_type ?? "pile") as ComponentType,
                component_label: String(step.component_label ?? ""),
                start_date: String(step.start_date ?? ""),
                finish_date: String(step.finish_date ?? ""),
              }))
            : [],
        }))
      : [],
  };
}

function milestoneStatusClass(milestone: MilestoneResult): string {
  if (milestone.status !== "late") return milestone.status;
  return milestone.mode === "hard" ? "late-hard" : "late-soft";
}

function scopeLabel(milestone: MilestoneConstraint, scenario: ScenarioInput): string {
  const project = scenario.project;
  if (milestone.scope_type === "project") {
    return "全项目下部结构+上部现浇梁完成";
  }

  if (milestone.scope_type === "bridge") {
    const bridge = project.bridges.find((item) => item.id === milestone.scope_id) ?? project.bridges[0];
    return bridge ? `${bridge.name}全桥下部结构+上部现浇梁完成` : "全桥下部结构+上部现浇梁完成";
  }

  if (milestone.scope_type === "work_section") {
    const section = findWorkSection(project, milestone.scope_id ?? "");
    if (!section) return "指定工区下部结构+上部现浇梁完成";
    if (section.side && section.side !== "none") {
      return `${sideLabels[section.side]}下部结构+上部现浇梁完成`;
    }
    return `${section.name}下部结构+上部现浇梁完成`;
  }

  if (milestone.scope_type === "structure") {
    const found = findStructure(project, milestone.scope_id ?? "");
    return found ? `${found.structure.support_no ?? found.structure.name}全部下部结构` : "指定墩台全部下部结构";
  }

  if (milestone.scope_type === "component") {
    if (isComponentType(milestone.scope_id)) {
      return `全部${componentLabels[milestone.scope_id]}`;
    }
    const found = findComponent(project, milestone.scope_id ?? "");
    if (found) {
      const location = found.structure.support_no ?? found.structure.name;
      return `${location}${componentLabels[found.component.component_type]}`;
    }
    return "指定构件";
  }

  return "-";
}

function findWorkSection(project: ProjectModel, sectionId: string): WorkSection | null {
  for (const bridge of project.bridges) {
    const section = bridge.work_sections.find((item) => item.id === sectionId);
    if (section) return section;
  }
  return null;
}

function findStructure(project: ProjectModel, structureId: string): { section: WorkSection; structure: StructureModel } | null {
  for (const bridge of project.bridges) {
    for (const section of bridge.work_sections) {
      const structure = section.structures.find((item) => item.id === structureId);
      if (structure) return { section, structure };
    }
  }
  return null;
}

function findComponent(project: ProjectModel, componentId: string): { section: WorkSection; structure: StructureModel; component: ComponentModel } | null {
  for (const bridge of project.bridges) {
    for (const section of bridge.work_sections) {
      for (const structure of section.structures) {
        const component = structure.components.find((item) => item.id === componentId);
        if (component) return { section, structure, component };
      }
    }
  }
  return null;
}

function isComponentType(value: string | null | undefined): value is ComponentType {
  return Boolean(value && Object.prototype.hasOwnProperty.call(componentLabels, value));
}

function hasProcessLibraryChanged(current: ProcessTemplate[], next: ProcessTemplate[]): boolean {
  if (current.length !== next.length) return true;
  return current.some((process, index) => JSON.stringify(process) !== JSON.stringify(next[index]));
}

function dimensionSummary(component: ComponentModel): string {
  const properties = component.properties;
  const dimensions = properties?.dimensions_m;
  if (component.component_type === "pier_body") {
    const pierSummary = pierBodyDimensionSummary(component, dimensions);
    if (pierSummary) return pierSummary;
  }
  if (Array.isArray(dimensions) && dimensions.length) {
    return dimensions.map((item) => `${displayValue(item)}m`).join(" × ");
  }
  if (isRecord(dimensions)) {
    const parts = Object.entries(dimensions)
      .filter(([, value]) => value !== null && value !== undefined)
      .map(([key, value]) => dimensionPartSummary(component, key, value));
    if (parts.length) return parts.join("，");
  }
  if (isRecord(properties)) {
    const propertyParts = Object.entries(properties)
      .filter(([key, value]) => isDimensionKey(key) && value !== null && value !== undefined)
      .map(([key, value]) => dimensionPartSummary(component, key, value));
    if (propertyParts.length) return propertyParts.join("，");
  }
  const raw = properties?.raw;
  if (isRecord(raw)) {
    const rawValues = Object.values(raw).filter((value) => value !== null && value !== undefined);
    if (rawValues.length) return rawValues.map(displayValue).join(" / ");
  }
  return "-";
}

function pierBodyDimensionSummary(component: ComponentModel, dimensions: unknown): string | null {
  const sectionDimensions = Array.isArray(dimensions) ? dimensions.filter(isNumber) : [];
  const raw = isRecord(component.properties?.raw) ? component.properties.raw : {};
  const pierForm = displayValue(raw.pier_form ?? component.properties?.form ?? "");
  const heightM = numberFromUnknown(component.properties?.height_m)
    ?? numberFromUnknown(component.properties?.heightM)
    ?? cmToM(raw.pier_height);
  const count = numberFromUnknown(component.properties?.count) ?? numberFromUnknown(raw.pier_count);
  const parts: string[] = [];

  if (sectionDimensions.length === 1 || pierForm.includes("柱式")) {
    const diameter = sectionDimensions[0];
    if (diameter !== undefined) parts.push(`直径${displayValue(diameter)}m`);
  } else if (sectionDimensions.length >= 2) {
    parts.push(`截面${sectionDimensions.map((item) => `${displayValue(item)}m`).join(" × ")}`);
  }
  if (heightM !== null) parts.push(`墩高${displayValue(heightM)}m`);
  if (count !== null && count > 1) parts.push(`${displayValue(count)}根`);
  return parts.length ? parts.join("，") : null;
}

function isDimensionKey(key: string): boolean {
  return [
    "diameterM",
    "diameter_m",
    "lengthM",
    "length_m",
    "heightM",
    "height_m",
    "widthM",
    "width_m",
    "thicknessM",
    "thickness_m",
    "totalLengthM",
    "total_length_m",
  ].includes(key);
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function numberFromUnknown(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const match = value.match(/-?\d+(?:\.\d+)?/);
    if (match) return Number(match[0]);
  }
  return null;
}

function cmToM(value: unknown): number | null {
  const number = numberFromUnknown(value);
  return number === null ? null : number / 100;
}

function dimensionPartSummary(component: ComponentModel, key: string, value: unknown): string {
  const unit = key.endsWith("M") || key.endsWith("_m") ? "m" : "";
  return `${dimensionLabel(component, key)}${displayValue(value)}${unit}`;
}

function dimensionLabel(component: ComponentModel, key: string): string {
  const labels: Record<string, string> = {
    diameterM: "直径",
    diameter_m: "直径",
    heightM: "高度",
    height_m: "高度",
    widthM: "宽度",
    width_m: "宽度",
    thicknessM: "厚度",
    thickness_m: "厚度",
    totalLengthM: "总长",
    total_length_m: "总长",
  };
  if (key === "lengthM" || key === "length_m") {
    return component.component_type === "pile" ? "桩长" : "长度";
  }
  return labels[key] ?? key;
}

function sourceSummary(component: ComponentModel): string {
  const source = component.properties?.source_trace;
  if (!isRecord(source)) return "-";
  const sheet = displayValue(source.sheet);
  const row = source.row ? `#${displayValue(source.row)}` : "";
  return `${sheet}${row}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/\.?0+$/, "");
  return String(value);
}

function taskDateRange(tasks: ScheduledTask[]): { startDate: string; finishDate: string } {
  if (!tasks.length) return { startDate: "-", finishDate: "-" };
  const first = tasks.reduce((current, task) => (task.start_offset < current.start_offset ? task : current), tasks[0]);
  const last = tasks.reduce((current, task) => (task.end_offset > current.end_offset ? task : current), tasks[0]);
  return { startDate: first.start_date, finishDate: last.finish_date };
}

function compareStructureIds(left: string, right: string): number {
  const a = structureSortKey(left);
  const b = structureSortKey(right);
  return (
    a.bridgeOrder - b.bridgeOrder
    || a.sideOrder - b.sideOrder
    || a.supportOrder - b.supportOrder
    || left.localeCompare(right)
  );
}

function structureSortKey(structureId: string): { bridgeOrder: number; sideOrder: number; supportOrder: number } {
  const parts = structureId.split("-");
  const bridgeOrder = numericPart(parts[0]);
  const sideOrder = parts[1] === "L" ? 0 : parts[1] === "R" ? 1 : 2;
  const supportPart = parts.length >= 3 ? parts.slice(2).join("-") : structureId;
  return {
    bridgeOrder,
    sideOrder,
    supportOrder: numericPart(supportPart),
  };
}

function numericPart(value: string | undefined): number {
  const match = value?.match(/\d+/);
  return match ? Number(match[0]) : Number.MAX_SAFE_INTEGER;
}

function groupBy<T>(items: T[], keyFn: (item: T) => string): Record<string, T[]> {
  return items.reduce<Record<string, T[]>>((acc, item) => {
    const key = keyFn(item);
    acc[key] = acc[key] ?? [];
    acc[key].push(item);
    return acc;
  }, {});
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function scenarioFingerprintForSolve(scenario: ScenarioInput): string {
  return JSON.stringify(scenario);
}

function formatScheduleStatus(value: unknown): string {
  if (typeof value === "string" && Object.prototype.hasOwnProperty.call(scheduleStatusLabels, value)) {
    return scheduleStatusLabels[value as ScheduleResult["status"]];
  }
  return value == null ? "-" : String(value);
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase}${path}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await responseErrorText(response));
  return response.json() as Promise<T>;
}

async function apiPut<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await responseErrorText(response));
  return response.json() as Promise<T>;
}

async function apiPostFormData<T>(path: string, payload: FormData): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    body: payload,
  });
  if (!response.ok) throw new Error(await responseErrorText(response));
  return response.json() as Promise<T>;
}

async function responseErrorText(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    return typeof payload.detail === "string" ? payload.detail : text;
  } catch {
    return text;
  }
}
