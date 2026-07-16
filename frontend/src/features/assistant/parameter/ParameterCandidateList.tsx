import { Check, PlusCircle } from "lucide-react";
import type {
  AiParameterCandidateAddition,
  AiParameterUploadedMaterialSummary,
} from "../../../contracts";
import {
  aiParameterCategoryLabels,
  aiParameterConfidenceLabels,
  confidenceClassName,
  formatAiParameterValue,
  isAiParameterCandidateSelectable,
  materialSummaryById,
} from "../../../domain/aiParameterAssistant";

export function ParameterCandidateList({
  candidates,
  materials,
  selectedIds,
  onToggle,
}: {
  candidates: AiParameterCandidateAddition[];
  materials: AiParameterUploadedMaterialSummary[];
  selectedIds: Set<string>;
  onToggle: (candidateId: string, checked: boolean) => void;
}) {
  if (candidates.length === 0) return null;

  const materialMap = materialSummaryById(materials);

  return (
    <div className="ai-param-candidates">
      <div className="ai-param-section-head">
        <strong>候选新增项</strong>
        <span>{candidates.length} 项</span>
      </div>
      <div className="ai-param-candidate-list">
        {candidates.map((candidate) => {
          const selectable = isAiParameterCandidateSelectable(candidate);
          const selected = selectedIds.has(candidate.candidate_id);
          return (
            <article className={`ai-param-candidate ${selected ? "is-selected" : ""}`} key={candidate.candidate_id}>
              <label className="ai-param-check">
                <input
                  type="checkbox"
                  checked={selected}
                  disabled={!selectable}
                  onChange={(event) => onToggle(candidate.candidate_id, event.target.checked)}
                />
                <span>{selected ? <Check size={14} /> : <PlusCircle size={14} />}</span>
              </label>
              <div className="ai-param-candidate-body">
                <div className="ai-param-suggestion-main">
                  <div>
                    <strong>{candidate.display_name}</strong>
                    <span>{aiParameterCategoryLabels[candidate.category]}</span>
                  </div>
                  <span className={confidenceClassName(candidate.confidence_label)}>
                    {aiParameterConfidenceLabels[candidate.confidence_label]} {candidate.confidence_score}
                  </span>
                </div>
                <div className="ai-param-field-grid">
                  {Object.entries(candidate.proposed_fields).slice(0, 6).map(([key, value]) => (
                    <span key={key}><b>{key}</b>{formatAiParameterValue(value)}</span>
                  ))}
                </div>
                <div className="ai-param-sources">
                  {candidate.source_refs.map((source, index) => {
                    const material = materialMap[source.material_id];
                    return (
                      <span key={`${source.material_id}-${index}`}>
                        {material?.file_name ?? source.material_id}
                        {source.excerpt ? `：${source.excerpt}` : ""}
                      </span>
                    );
                  })}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
