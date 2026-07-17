import type {
  AiParameterCandidateAddition,
  AiParameterCategory,
  AiParameterConflictGroup,
  AiParameterConfidence,
  AiParameterMaterialKind,
  AiParameterSourceEvidence,
  AiParameterSuggestion,
  AiParameterUploadedMaterialSummary,
} from "../contracts";

export type AiParameterSuggestionGroup = {
  category: AiParameterCategory;
  label: string;
  suggestions: AiParameterSuggestion[];
};

export const aiParameterCategoryLabels: Record<AiParameterCategory, string> = {
  process_method_assignment: "工艺设置",
  process_productivity: "工艺工效",
  resource_pool: "资源数量",
  milestone: "里程碑",
};

export const aiParameterConfidenceLabels: Record<AiParameterConfidence, string> = {
  High: "高",
  Medium: "中",
  Low: "低",
};

export const aiParameterMaterialKindLabels: Record<AiParameterMaterialKind, string> = {
  text: "文本",
  word: "Word",
  excel: "Excel",
  pdf: "PDF",
  image: "图片",
};

const categoryOrder: AiParameterCategory[] = ["process_method_assignment", "process_productivity", "resource_pool", "milestone"];
const confidenceOrder: Record<AiParameterConfidence, number> = { High: 0, Medium: 1, Low: 2 };

export function groupAiParameterSuggestions(suggestions: AiParameterSuggestion[]): AiParameterSuggestionGroup[] {
  return categoryOrder
    .map((category) => ({
      category,
      label: aiParameterCategoryLabels[category],
      suggestions: suggestions
        .filter((suggestion) => suggestion.category === category)
        .sort((left, right) => {
          const confidenceDiff = confidenceOrder[left.confidence_label] - confidenceOrder[right.confidence_label];
          if (confidenceDiff !== 0) return confidenceDiff;
          if (left.status !== right.status) return left.status.localeCompare(right.status);
          return right.confidence_score - left.confidence_score;
        }),
    }))
    .filter((group) => group.suggestions.length > 0);
}

export function isDefaultAiParameterSelected(suggestion: AiParameterSuggestion): boolean {
  return (
    suggestion.confidence_label === "High" &&
    suggestion.status === "suggested" &&
    !suggestion.conflict_group_id &&
    suggestion.source_refs.length > 0
  );
}

export function isAiParameterSuggestionSelectable(suggestion: AiParameterSuggestion): boolean {
  return suggestion.status === "suggested" && !suggestion.conflict_group_id;
}

export function isAiParameterCandidateSelectable(candidate: AiParameterCandidateAddition): boolean {
  return candidate.validation_status === "valid";
}

export function isAiParameterConflictResolved(group: AiParameterConflictGroup): boolean {
  if (group.resolution_status === "keep_current") return true;
  if (group.resolution_status === "selected_suggestion") return Boolean(group.selected_suggestion_id);
  if (group.resolution_status === "manual_value") {
    return group.manual_value !== null && group.manual_value !== undefined && String(group.manual_value).trim() !== "";
  }
  return false;
}

export function canApplyAiParameterSelection(
  selectedIds: Set<string>,
  conflictResolutions: AiParameterConflictGroup[],
): boolean {
  return selectedIds.size > 0 || conflictResolutions.some(isAiParameterConflictResolved);
}

export function formatAiParameterValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/\.?0+$/, "");
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  if (value === "mixed") return "多个当前值";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function materialSummaryById(
  materials: AiParameterUploadedMaterialSummary[],
): Record<string, AiParameterUploadedMaterialSummary> {
  return Object.fromEntries(materials.map((material) => [material.material_id, material]));
}

export function sourceHasImageMaterial(
  source: AiParameterSourceEvidence,
  materialMap: Record<string, AiParameterUploadedMaterialSummary>,
): boolean {
  return materialMap[source.material_id]?.kind === "image";
}

export function confidenceClassName(confidence: AiParameterConfidence): string {
  return `ai-param-confidence ai-param-confidence-${confidence.toLowerCase()}`;
}
