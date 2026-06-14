import type { RelationshipType, ScenarioInput, UpperStructureModel } from "../types/scheduler";
import { upperStructureCodes } from "./constants";
import { mergeUpperStructureLogicRules, upperStructureLogicDefinitions } from "./upperStructureLogic";

export type UpperLowerLogicConstraint = {
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

export function buildUpperLowerLogicConstraints(scenario: ScenarioInput): UpperLowerLogicConstraint[] {
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
