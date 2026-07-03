import {
  Bot,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import type {
  AiParameterApplyRequest,
  AiParameterApplyResponse,
  AiParameterConflictGroup,
  AiParameterParseResponse,
  ScenarioInput,
} from "../../../types/scheduler";
import {
  aiParameterMaterialKindLabels,
  canApplyAiParameterSelection,
  formatAiParameterValue,
  isAiParameterConflictResolved,
  isDefaultAiParameterSelected,
} from "../../../domain/aiParameterAssistant";
import { ParameterCandidateList } from "./ParameterCandidateList";
import { ParameterConflictResolver } from "./ParameterConflictResolver";
import { ParameterSuggestionReview } from "./ParameterSuggestionReview";

const maxFiles = 10;

export function ParameterAssistantPanel({
  scenario,
  busy,
  onParse,
  onApply,
}: {
  scenario: ScenarioInput;
  busy: boolean;
  onParse: (payload: FormData) => Promise<AiParameterParseResponse | null>;
  onApply: (request: AiParameterApplyRequest) => Promise<AiParameterApplyResponse | null>;
}) {
  const [open, setOpen] = useState(true);
  const [textInput, setTextInput] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [parseResult, setParseResult] = useState<AiParameterParseResponse | null>(null);
  const [applyResult, setApplyResult] = useState<AiParameterApplyResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [conflictResolutions, setConflictResolutions] = useState<Record<string, AiParameterConflictGroup>>({});
  const [localError, setLocalError] = useState<string | null>(null);

  const resolvedConflicts = useMemo(
    () => Object.values(conflictResolutions).filter(isAiParameterConflictResolved),
    [conflictResolutions],
  );
  const canApply = parseResult ? canApplyAiParameterSelection(selectedIds, resolvedConflicts) : false;
  const totalFileSize = files.reduce((sum, file) => sum + file.size, 0);

  if (!open) {
    return (
      <button className="ai-param-launcher" type="button" aria-label="打开 AI 参数助手" onClick={() => setOpen(true)}>
        <Bot size={18} />
        <span>参数助手</span>
      </button>
    );
  }

  async function submitParse() {
    const trimmedText = textInput.trim();
    if (busy) return;
    if (!trimmedText && files.length === 0) {
      setLocalError("请先添加文本或文件。");
      return;
    }
    setLocalError(null);
    setApplyResult(null);
    const payload = new FormData();
    payload.append("scenario", JSON.stringify(scenario));
    if (trimmedText) payload.append("text_input", trimmedText);
    files.forEach((file, index) => payload.append(`file_${index}`, file, file.name));
    const result = await onParse(payload);
    if (!result) return;
    setParseResult(result);
    setSelectedIds(new Set(result.suggestions.filter(isDefaultAiParameterSelected).map((item) => item.suggestion_id)));
    setConflictResolutions({});
  }

  async function submitApply() {
    if (!parseResult || !canApply || busy) return;
    setLocalError(null);
    const manualValues = resolvedConflicts
      .filter((group) => group.resolution_status === "manual_value")
      .map((group) => ({
        conflict_group_id: group.conflict_group_id,
        parameter_key: group.parameter_key,
        value: group.manual_value,
      }));
    const result = await onApply({
      scenario,
      run_id: parseResult.run_id,
      selected_suggestion_ids: Array.from(selectedIds),
      conflict_resolutions: resolvedConflicts,
      manual_values: manualValues,
    });
    if (result) setApplyResult(result);
  }

  function updateSelected(id: string, checked: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function updateConflictResolution(resolution: AiParameterConflictGroup) {
    setConflictResolutions((current) => ({
      ...current,
      [resolution.conflict_group_id]: resolution,
    }));
  }

  function removeFile(index: number) {
    setFiles((current) => current.filter((_, fileIndex) => fileIndex !== index));
  }

  return (
    <aside className="ai-param-panel" aria-label="AI 参数输入助手">
      <div className="ai-param-title">
        <div className="nl-process-heading">
          <span className="assistant-mark"><Bot size={16} /></span>
          <div>
            <strong>AI 参数输入助手</strong>
            <span>当前方案 · 工效 / 资源 / 里程碑</span>
          </div>
        </div>
        <button className="icon-button" type="button" aria-label="收起 AI 参数助手" onClick={() => setOpen(false)}>
          <X size={16} />
        </button>
      </div>

      <div className="ai-param-inputs">
        <textarea
          value={textInput}
          onChange={(event) => setTextInput(event.target.value)}
          placeholder="粘贴设计说明、施组、资源计划或里程碑片段"
        />
        <label className="ai-param-upload">
          <Upload size={16} />
          <span>上传资料</span>
          <input
            multiple
            type="file"
            accept=".txt,.md,.csv,.xlsx,.xlsm,.doc,.docx,.pdf,.png,.jpg,.jpeg,.webp,.bmp"
            onChange={(event) => {
              const selected = Array.from(event.target.files ?? []);
              setFiles((current) => [...current, ...selected].slice(0, maxFiles));
              event.currentTarget.value = "";
            }}
          />
        </label>
      </div>

      {files.length > 0 && (
        <div className="ai-param-file-list">
          <div className="ai-param-file-summary">
            <span>{files.length}/{maxFiles} 个文件</span>
            <span>{formatFileSize(totalFileSize)}</span>
          </div>
          {files.map((file, index) => (
            <span key={`${file.name}-${file.lastModified}`}>
              <FileText size={13} />
              {file.name}
              <button type="button" aria-label={`移除 ${file.name}`} onClick={() => removeFile(index)}>
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}

      {localError && <div className="ai-param-error">{localError}</div>}

      <button
        className="primary assistant-submit"
        type="button"
        disabled={busy || (!textInput.trim() && files.length === 0)}
        onClick={submitParse}
      >
        {busy ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
        解析参数
      </button>

      {parseResult && (
        <div className="ai-param-result">
          <div className="ai-param-run-summary">
            <span>Run {parseResult.run_id}</span>
            <span>{parseResult.suggestion_count} 条建议</span>
            <span>{parseResult.manual_completion_count} 待完善</span>
            <span>{formatExpiresAt(parseResult.expires_at)} 过期</span>
          </div>

          <div className="ai-param-materials">
            {parseResult.material_summaries.map((material) => (
              <span className={`is-${material.parse_status}`} key={material.material_id}>
                <b>{aiParameterMaterialKindLabels[material.kind]}</b>
                {material.file_name}
                {material.error_message ? ` · ${material.error_message}` : ""}
              </span>
            ))}
          </div>

          {[...parseResult.errors, ...parseResult.warnings].length > 0 && (
            <div className="ai-param-validation">
              {[...parseResult.errors, ...parseResult.warnings].map((message, index) => (
                <span key={`${message.message}-${index}`}>{message.message}</span>
              ))}
            </div>
          )}

          <ParameterSuggestionReview
            suggestions={parseResult.suggestions}
            materials={parseResult.material_summaries}
            selectedIds={selectedIds}
            onToggle={updateSelected}
          />
          <ParameterConflictResolver
            conflictGroups={parseResult.conflict_groups}
            suggestions={parseResult.suggestions}
            resolutions={conflictResolutions}
            onChange={updateConflictResolution}
          />
          <ParameterCandidateList
            candidates={parseResult.candidate_additions}
            materials={parseResult.material_summaries}
            selectedIds={selectedIds}
            onToggle={updateSelected}
          />

          <div className="ai-param-apply-bar">
            <span>已选 {selectedIds.size} 项，冲突处理 {resolvedConflicts.length} 项</span>
            <button className="primary" type="button" disabled={!canApply || busy} onClick={submitApply}>
              {busy ? <Loader2 className="spin" size={15} /> : <RefreshCw size={15} />}
              应用到当前方案
            </button>
          </div>
        </div>
      )}

      {applyResult && (
        <div className="ai-param-apply-result">
          <strong>应用摘要</strong>
          <span>已应用 {applyResult.application_summary.applied_count} 项</span>
          <span>跳过 {applyResult.application_summary.skipped_count} 项</span>
          <span>失败 {applyResult.application_summary.failed_count} 项</span>
          {applyResult.application_summary.manual_pending_count > 0 && (
            <span>待完善 {applyResult.application_summary.manual_pending_count} 项</span>
          )}
          {applyResult.application_summary.applied_items.slice(0, 5).map((item) => (
            <em key={item.suggestion_id}>
              {item.parameter_key}：{formatAiParameterValue(item.old_value)} → {formatAiParameterValue(item.new_value)}
            </em>
          ))}
          {applyResult.application_summary.failed_items.map((item, index) => (
            <em className="is-error" key={`${item.message}-${index}`}>{item.message}</em>
          ))}
        </div>
      )}
    </aside>
  );
}

function formatFileSize(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function formatExpiresAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}
