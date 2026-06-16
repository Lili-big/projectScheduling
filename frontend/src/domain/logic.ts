import type { LogicRule, RelationshipType, ScenarioInput, StructureModel, UpperStructureModel } from "../types/scheduler";
import { upperStructureCodes } from "./constants";
import { componentLabels } from "./labels";
import { mergeUpperStructureLogicRules, upperStructureLogicDefinitions } from "./upperStructureLogic";

export type UpperLowerLogicConstraint = {
  id: string;
  name: string;
  upperTarget: string;
  lowerPredecessor: string;
  generation: string;
  relationship: RelationshipType;
  lagDays: number;
  matchedCount: number;
  matchedUnit: string;
  matchedText: string;
  note: string;
};

export type LogicRuleRow = {
  id: string;
  source: "lower" | "upper";
  sourceLabel: string;
  name: string;
  successorLabel: string;
  predecessorLabel: string;
  matchModeLabel: string;
  relationship: RelationshipType;
  lagDays: number;
  matchedCount: number;
  matchedUnit: string;
  matchedText: string;
  note: string;
  generation?: string;
  lowerRuleIndex?: number;
};

export type LogicRuleSummary = {
  activeRuleCount: number;
  matchedRuleCount: number;
  unmatchedRuleCount: number;
};

export type LogicRuleTraceInfo = {
  id: string;
  name: string;
  sourceLabel: string;
  note: string;
};

export type DeferredScheduleLogicItem = {
  name: string;
  reason: string;
};

export const deferredScheduleLogicItems: DeferredScheduleLogicItem[] = [
  {
    name: "简支梁架梁",
    reason: "已有架梁工效模板，但本期简支梁仅作为结构参数保留，不生成现场架梁任务。",
  },
  {
    name: "钢箱梁",
    reason: "已有钢箱梁工效模板，当前任务生成逻辑尚未派生钢箱梁现场任务。",
  },
  {
    name: "桥面系",
    reason: "已有桥面系工效模板，当前任务图未按桥面长度生成桥面系任务。",
  },
];

export function buildLogicRuleRows(scenario: ScenarioInput): { rows: LogicRuleRow[]; summary: LogicRuleSummary } {
  const lowerRows = scenario.logic_rules.map((rule, index) => {
    const matchedCount = countLowerLogicMatches(scenario, rule);
    return {
      id: rule.id,
      source: "lower" as const,
      sourceLabel: "下部结构",
      name: logicRuleDisplayName(rule),
      successorLabel: componentLabels[rule.to_component],
      predecessorLabel: rule.predecessor_candidates.map((item) => componentLabels[item]).join(" / "),
      matchModeLabel: predecessorStrategyLabel(rule.predecessor_strategy),
      relationship: rule.relationship,
      lagDays: rule.lag_days,
      matchedCount,
      matchedUnit: "个结构物",
      matchedText: matchText(matchedCount, "个结构物"),
      note: rule.note,
      lowerRuleIndex: index,
    };
  });

  const upperRows = buildUpperLowerLogicConstraints(scenario).map((constraint) => ({
    id: constraint.id,
    source: "upper" as const,
    sourceLabel: "桥梁上部",
    name: constraint.name,
    successorLabel: constraint.upperTarget,
    predecessorLabel: constraint.lowerPredecessor,
    matchModeLabel: "按结构自动生成",
    relationship: constraint.relationship,
    lagDays: constraint.lagDays,
    matchedCount: constraint.matchedCount,
    matchedUnit: constraint.matchedUnit,
    matchedText: constraint.matchedText,
    note: constraint.note,
    generation: constraint.generation,
  }));

  const rows = [...lowerRows, ...upperRows];
  const matchedRuleCount = rows.filter((row) => row.matchedCount > 0).length;
  return {
    rows,
    summary: {
      activeRuleCount: rows.length,
      matchedRuleCount,
      unmatchedRuleCount: rows.length - matchedRuleCount,
    },
  };
}

export function buildLogicRuleTraceMap(scenario: ScenarioInput): Map<string, LogicRuleTraceInfo> {
  return new Map(
    buildLogicRuleRows(scenario).rows.map((row) => [
      row.id,
      {
        id: row.id,
        name: row.name,
        sourceLabel: row.sourceLabel,
        note: row.note,
      },
    ]),
  );
}

export function buildUpperLowerLogicConstraints(scenario: ScenarioInput): UpperLowerLogicConstraint[] {
  const stats = countUpperLowerLogicTargets(scenario);
  const rulesById = new Map(mergeUpperStructureLogicRules(scenario.upper_structure_logic_rules).map((rule) => [rule.id, rule]));
  const matchById: Record<string, { count: number; unit: string }> = {
    cast_in_place_box_beam_after_lower_structure: { count: stats.castInPlaceBoxGroupCount, unit: "联" },
    continuous_beam_zero_block_after_main_pier_lower_structure: { count: stats.continuousMainPierCount, unit: "个T构" },
    continuous_beam_side_straight_after_edge_lower_structure: { count: stats.continuousSideStraightCount, unit: "个边跨" },
    continuous_beam_t_chain: { count: stats.continuousMainPierCount, unit: "个T构" },
    continuous_beam_side_closure: { count: stats.continuousSideClosureCount, unit: "个边跨" },
    continuous_beam_middle_closure: { count: stats.continuousMiddleClosureCount, unit: "个中跨" },
    continuous_beam_edge_before_middle_closure: { count: stats.continuousMiddleClosureCount, unit: "个中跨" },
    continuous_beam_middle_closure_sequence: { count: stats.continuousMiddleClosureCount, unit: "个中跨" },
  };
  return upperStructureLogicDefinitions.map((definition) => {
    const rule = rulesById.get(definition.id);
    const matched = matchById[definition.id] ?? { count: 0, unit: "个对象" };
    return {
      ...definition,
      relationship: rule?.relationship ?? "FS",
      lagDays: rule?.lag_days ?? 0,
      matchedCount: matched.count,
      matchedUnit: matched.unit,
      matchedText: matchText(matched.count, matched.unit),
      note: rule?.note || definition.note,
    };
  });
}

export function countUpperLowerLogicTargets(scenario: ScenarioInput) {
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

export function groupUpperStructures(
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

export function isSimpleBeamUpper(upper: UpperStructureModel): boolean {
  if (upperStructureCode(upper) === upperStructureCodes.simpleBeam) return true;
  if (isContinuousBeamUpper(upper) || isCastInPlaceBoxBeamUpper(upper)) return false;
  return upper.structure_type.includes("简支") || upper.structure_type.includes("T梁");
}

export function isCastInPlaceBoxBeamUpper(upper: UpperStructureModel): boolean {
  if (upperStructureCode(upper) === upperStructureCodes.castInPlaceBoxBeam) return true;
  return upper.structure_type.includes("现浇")
    && upper.structure_type.includes("箱梁")
    && !isContinuousBeamUpper(upper);
}

export function isContinuousBeamUpper(upper: UpperStructureModel): boolean {
  if (upperStructureCode(upper) === upperStructureCodes.continuousBeam) return true;
  return upper.structure_type.includes("连续") || upper.structure_type.includes("刚构");
}

export function upperStructureCode(upper: UpperStructureModel): string {
  return String(upper.properties.structure_code ?? "");
}

export function upperGroupIndex(upper: UpperStructureModel): number {
  const value = Number(upper.properties.group_index ?? upper.span_index);
  return Number.isFinite(value) ? Math.trunc(value) : upper.span_index;
}

export function continuousMainSupportCount(uppers: UpperStructureModel[]): number {
  const configured = continuousNumberListSetting(uppers, ["main_support_indices", "main_pier_indices"]);
  if (configured.length) return new Set(configured).size;
  const spanIndices = uppers.map((upper) => upper.span_index);
  if (spanIndices.length < 2) return 0;
  return Math.max(...spanIndices) - Math.min(...spanIndices);
}

export function continuousNumberListSetting(uppers: UpperStructureModel[], keys: string[]): number[] {
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

export function numberListFromUnknown(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => Number(item))
    .filter((item) => Number.isFinite(item))
    .map((item) => Math.trunc(item));
}

export function logicRuleDisplayName(rule: LogicRule): string {
  const shortNames: Record<string, string> = {
    cap_after_piles: "承台前置",
    ground_tie_after_piles: "地系梁前置",
    pier_body_after_cap: "墩身前置",
    middle_tie_after_pier_body: "中系梁前置",
    cap_beam_after_pier_body: "盖梁前置",
    abutment_body_after_cap: "桥台前置",
  };
  return shortNames[rule.id] ?? `${componentLabels[rule.to_component]}前置`;
}

function predecessorStrategyLabel(strategy: LogicRule["predecessor_strategy"]): string {
  return strategy === "all" ? "所有前置都要完成" : "按顺序回退";
}

function matchText(count: number, unit: string): string {
  return count > 0 ? `适用 ${count} ${unit}` : "当前无适用对象";
}

function countLowerLogicMatches(scenario: ScenarioInput, rule: LogicRule): number {
  let count = 0;
  for (const bridge of scenario.project.bridges) {
    for (const section of bridge.work_sections) {
      for (const structure of section.structures) {
        if (lowerRuleMatchesStructure(rule, structure)) {
          count += 1;
        }
      }
    }
  }
  return count;
}

function lowerRuleMatchesStructure(rule: LogicRule, structure: StructureModel): boolean {
  if (rule.structure_type && rule.structure_type !== structure.structure_type) return false;
  const enabledComponents = structure.components.filter((component) => component.enabled !== false);
  if (!enabledComponents.some((component) => component.component_type === rule.to_component)) return false;
  return selectedPredecessorComponents(enabledComponents, rule).length > 0;
}

function selectedPredecessorComponents(
  components: StructureModel["components"],
  rule: LogicRule,
): StructureModel["components"] {
  if (rule.predecessor_strategy === "all") {
    return components.filter((component) => rule.predecessor_candidates.includes(component.component_type));
  }
  for (const candidate of rule.predecessor_candidates) {
    const matches = components.filter((component) => component.component_type === candidate);
    if (matches.length) return matches;
  }
  return [];
}
