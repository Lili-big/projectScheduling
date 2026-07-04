import { GitCompare, PenLine } from "lucide-react";
import type {
  AiParameterConflictGroup,
  AiParameterSuggestion,
} from "../../../types/scheduler";
import {
  formatAiParameterValue,
  isAiParameterConflictResolved,
} from "../../../domain/aiParameterAssistant";

export function ParameterConflictResolver({
  conflictGroups,
  suggestions,
  resolutions,
  onChange,
}: {
  conflictGroups: AiParameterConflictGroup[];
  suggestions: AiParameterSuggestion[];
  resolutions: Record<string, AiParameterConflictGroup>;
  onChange: (resolution: AiParameterConflictGroup) => void;
}) {
  if (conflictGroups.length === 0) return null;

  const suggestionsById = Object.fromEntries(suggestions.map((suggestion) => [suggestion.suggestion_id, suggestion]));

  return (
    <div className="ai-param-conflicts">
      <div className="ai-param-section-head">
        <strong>冲突处理</strong>
        <span>{conflictGroups.filter((group) => isAiParameterConflictResolved(resolutions[group.conflict_group_id] ?? group)).length}/{conflictGroups.length}</span>
      </div>
      {conflictGroups.map((group) => {
        const resolution = resolutions[group.conflict_group_id] ?? group;
        return (
          <article className="ai-param-conflict-card" key={group.conflict_group_id}>
            <div className="ai-param-conflict-title">
              <GitCompare size={15} />
              <strong>{group.parameter_key}</strong>
              <span>当前值：{formatAiParameterValue(group.current_value)}</span>
            </div>
            <div className="ai-param-conflict-options">
              {group.suggestion_ids.map((suggestionId) => {
                const suggestion = suggestionsById[suggestionId];
                if (!suggestion) return null;
                const selected =
                  resolution.resolution_status === "selected_suggestion" &&
                  resolution.selected_suggestion_id === suggestionId;
                return (
                  <button
                    className={selected ? "is-active" : ""}
                    type="button"
                    key={suggestionId}
                    onClick={() =>
                      onChange({
                        ...group,
                        resolution_status: "selected_suggestion",
                        selected_suggestion_id: suggestionId,
                        manual_value: null,
                      })
                    }
                  >
                    <span>{formatAiParameterValue(suggestion.proposed_value)}{suggestion.unit ? ` ${suggestion.unit}` : ""}</span>
                    <em>{suggestion.confidence_label} {suggestion.confidence_score}</em>
                  </button>
                );
              })}
              <button
                className={resolution.resolution_status === "keep_current" ? "is-active" : ""}
                type="button"
                onClick={() =>
                  onChange({
                    ...group,
                    resolution_status: "keep_current",
                    selected_suggestion_id: null,
                    manual_value: null,
                  })
                }
              >
                <span>保留当前值</span>
                <em>{formatAiParameterValue(group.current_value)}</em>
              </button>
            </div>
            <label className="ai-param-manual-value">
              <PenLine size={14} />
              <input
                value={resolution.resolution_status === "manual_value" ? String(resolution.manual_value ?? "") : ""}
                placeholder="手动填写"
                onChange={(event) =>
                  onChange({
                    ...group,
                    resolution_status: event.target.value.trim() ? "manual_value" : "unresolved",
                    selected_suggestion_id: null,
                    manual_value: event.target.value,
                  })
                }
              />
            </label>
          </article>
        );
      })}
    </div>
  );
}
