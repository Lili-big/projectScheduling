import type { ComponentType, MilestoneResult, ResourceCostType, ResourceMode, ScheduleResult, ValidationMessage, WorkSectionSide } from "../types/scheduler";

export const componentLabels: Record<ComponentType, string> = {
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

export const durationMethodLabels: Record<string, string> = {
  units_per_day: "按日完成量计算",
  days_per_unit: "按单位耗时计算",
  fixed_days: "固定工期",
};

export const quantitySourceLabels: Record<string, string> = {
  pile_length_m: "桩长",
  pier_height_m: "墩高",
  deck_length_m: "桥面长度",
  count: "构件数量",
};

export const componentColors: Record<ComponentType, string> = {
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

export const componentOrder: ComponentType[] = [
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

export function componentSortIndex(componentType: ComponentType): number {
  const index = componentOrder.indexOf(componentType);
  return index >= 0 ? index : componentOrder.length;
}

export const sideLabels: Record<WorkSectionSide, string> = {
  left: "左幅",
  right: "右幅",
  none: "无幅别",
};

export const scheduleStatusLabels: Record<ScheduleResult["status"], string> = {
  OPTIMAL: "最优",
  FEASIBLE: "可行",
  INFEASIBLE: "不可行",
  UNKNOWN: "未知",
  MODEL_INVALID: "模型无效",
};

export const milestoneStatusLabels: Record<MilestoneResult["status"], string> = {
  met: "已满足",
  late: "已迟延",
  not_evaluated: "未评估",
};

export const diagnosticLevelLabels: Record<ValidationMessage["level"], string> = {
  info: "正常",
  warning: "提醒",
  error: "严重偏差",
};
