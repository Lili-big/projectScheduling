import { AlertTriangle, Check, Image as ImageIcon } from "lucide-react";
import type {
  AiParameterSuggestion,
  AiParameterUploadedMaterialSummary,
} from "../../../contracts";
import {
  aiParameterConfidenceLabels,
  confidenceClassName,
  formatAiParameterValue,
  groupAiParameterSuggestions,
  isAiParameterSuggestionSelectable,
  materialSummaryById,
  sourceHasImageMaterial,
} from "../../../domain/aiParameterAssistant";

export function ParameterSuggestionReview({
  suggestions,
  materials,
  selectedIds,
  onToggle,
}: {
  suggestions: AiParameterSuggestion[];
  materials: AiParameterUploadedMaterialSummary[];
  selectedIds: Set<string>;
  onToggle: (suggestionId: string, checked: boolean) => void;
}) {
  const grouped = groupAiParameterSuggestions(suggestions);
  const materialMap = materialSummaryById(materials);
  const pendingCount = suggestions.filter((suggestion) => suggestion.status === "needs_manual_input").length;

  if (suggestions.length === 0) {
    return <div className="ai-param-empty">暂无可审阅建议</div>;
  }

  return (
    <div className="ai-param-review">
      <div className="ai-param-section-head">
        <strong>建议审阅</strong>
        <span>{suggestions.length} 条建议，{pendingCount} 条待完善</span>
      </div>
      {grouped.map((group) => (
        <section className="ai-param-suggestion-group" key={group.category}>
          <div className="ai-param-group-title">
            <span>{group.label}</span>
            <em>{group.suggestions.length}</em>
          </div>
          <div className="ai-param-suggestion-list">
            {group.suggestions.map((suggestion) => {
              const selectable = isAiParameterSuggestionSelectable(suggestion);
              const selected = selectedIds.has(suggestion.suggestion_id);
              const hasImageSource = suggestion.source_refs.some((source) => sourceHasImageMaterial(source, materialMap));
              return (
                <article
                  className={[
                    "ai-param-suggestion-row",
                    selected ? "is-selected" : "",
                    !selectable ? "is-muted" : "",
                    hasImageSource ? "is-image-source" : "",
                  ].filter(Boolean).join(" ")}
                  key={suggestion.suggestion_id}
                >
                  <label className="ai-param-check">
                    <input
                      type="checkbox"
                      checked={selected}
                      disabled={!selectable}
                      onChange={(event) => onToggle(suggestion.suggestion_id, event.target.checked)}
                    />
                    <span>{selected ? <Check size={14} /> : null}</span>
                  </label>
                  <div className="ai-param-suggestion-body">
                    <div className="ai-param-suggestion-main">
                      <div>
                        <strong>{suggestionTitle(suggestion)}</strong>
                        <span>{targetLabel(suggestion)}</span>
                      </div>
                      <span className={confidenceClassName(suggestion.confidence_label)}>
                        {aiParameterConfidenceLabels[suggestion.confidence_label]} {suggestion.confidence_score}
                      </span>
                    </div>
                    <div className="ai-param-value-change">
                      <span>{formatAiParameterValue(suggestion.current_value)}</span>
                      <b>→</b>
                      <span>{formatAiParameterValue(suggestion.proposed_value)}{suggestion.unit ? ` ${suggestion.unit}` : ""}</span>
                    </div>
                    {suggestion.status === "needs_manual_input" && (
                      <div className="ai-param-warning"><AlertTriangle size={14} />待人工完善</div>
                    )}
                    {suggestion.conflict_group_id && (
                      <div className="ai-param-warning"><AlertTriangle size={14} />存在冲突，需在冲突区处理</div>
                    )}
                    <div className="ai-param-sources">
                      {suggestion.source_refs.map((source, index) => {
                        const material = materialMap[source.material_id];
                        const image = sourceHasImageMaterial(source, materialMap);
                        return (
                          <span className={image ? "is-image" : ""} key={`${source.material_id}-${index}`}>
                            {image ? <ImageIcon size={13} /> : null}
                            {material?.file_name ?? source.material_id}
                            {source.page_or_sheet ? ` · ${source.page_or_sheet}` : ""}
                            {source.cell_or_region ? ` · ${source.cell_or_region}` : ""}
                            {source.excerpt ? `：${source.excerpt}` : ""}
                          </span>
                        );
                      })}
                    </div>
                    {suggestion.validation_messages.length > 0 && (
                      <div className="ai-param-validation">
                        {suggestion.validation_messages.map((message, index) => (
                          <span key={`${message.message}-${index}`}>{message.message}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}

function suggestionTitle(suggestion: AiParameterSuggestion): string {
  if (suggestion.category === "process_method_assignment") return "构件工艺设置";
  if (suggestion.category === "process_productivity") return "工效参数";
  if (suggestion.category === "resource_pool") return "资源配置";
  return "里程碑参数";
}

function targetLabel(suggestion: AiParameterSuggestion): string {
  if (suggestion.category === "process_method_assignment") {
    const count = Number(suggestion.target_ref.matched_count ?? 0);
    const processName = String(suggestion.target_ref.process_name ?? suggestion.proposed_value ?? "目标工艺");
    const action = String(suggestion.target_ref.action ?? "工艺设置");
    return `${action} · ${processName}${count > 0 ? ` · 影响 ${count} 个构件` : ""}`;
  }
  const values = [
    suggestion.target_ref.process_name,
    suggestion.target_ref.resource_label,
    suggestion.target_ref.milestone_name,
    suggestion.target_ref.bridge_name,
    suggestion.target_ref.work_section_name,
    suggestion.parameter_key,
  ]
    .filter((value) => value !== null && value !== undefined && String(value).trim() !== "")
    .map(String);
  return values.slice(0, 2).join(" · ");
}
